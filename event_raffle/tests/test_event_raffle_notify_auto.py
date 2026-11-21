# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.modules.migration import load_script
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.mail import plaintext2html

DEFAULT_EN = "You won a prize, come and claim it! {link}"
DEFAULT_FR = "Vous avez gagné un prix, venez le réclamer ! {lien}"
# The default of 18.0.1.4.0, before the link.
OLD_EN = "You won a prize, come and claim it!"
MESSAGE = "Bravo! Your prize waits at the welcome desk."


class TestRaffleNotifyAuto(TransactionCase):
    """Automatic notification of each winner, as OdooBot, after a draw."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_notrack=True,
                no_reset_password=True,
            )
        )
        cls.odoobot = cls.env.ref("base.partner_root")
        cls.organizer = new_test_user(
            cls.env,
            login="raffle_auto_organizer",
            groups="base.group_user,event.group_event_user",
            email="auto.organizer@example.com",
            name="Auto Organizer",
        )
        cls.internal_winner = new_test_user(
            cls.env,
            login="raffle_auto_internal_winner",
            groups="base.group_user",
            email="auto.internal@example.com",
            name="Auto Internal Winner",
        )
        cls.contact = cls.env["res.partner"].create(
            {"name": "Auto Mail Winner", "email": "auto.mail@example.com"}
        )
        cls.nobody = cls.env["res.partner"].create({"name": "Auto Nobody"})
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Auto",
                "notify_winner_auto": True,
                "notify_winner_message": MESSAGE,
            }
        )

    def _enter(self, partner):
        return self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle.id,
                "name": partner.name,
                "partner_id": partner.id,
            }
        )

    def _draw_next(self, partner):
        """Draw the only participant, `partner`, as an event user."""
        self._enter(partner)
        result = self.raffle.with_user(self.organizer).action_draw_next()
        return self.env["event.raffle.draw"].browse(result["draw_id"])

    def _chats_with(self, partner):
        return self.env["discuss.channel"].search(
            [
                ("channel_type", "=", "chat"),
                ("channel_member_ids.partner_id", "=", partner.id),
            ]
        )

    def _notes(self, draw):
        return " ".join(str(body) for body in draw.message_ids.mapped("body"))

    # Settings

    def test_off_by_default_with_the_standard_message(self):
        raffle = self.env["event.raffle"].create({"name": "Fresh"})
        self.assertFalse(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, DEFAULT_EN)

    def test_default_message_is_translated(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        Raffle = self.env["event.raffle"].with_context(lang="fr_CA")
        raffle = Raffle.create({"name": "Frais"})
        self.assertEqual(raffle.notify_winner_message, DEFAULT_FR)

    def test_the_message_is_required_when_on(self):
        with self.assertRaises(ValidationError):
            self.env["event.raffle"].create(
                {
                    "name": "Empty",
                    "notify_winner_auto": True,
                    "notify_winner_message": False,
                }
            )
        with self.assertRaises(ValidationError):
            self.raffle.notify_winner_message = "   "
        raffle = self.env["event.raffle"].create(
            {"name": "Off", "notify_winner_message": False}
        )
        self.assertFalse(raffle.notify_winner_auto)

    def test_an_event_user_edits_the_settings(self):
        raffle = self.raffle.with_user(self.organizer)
        raffle.write({"notify_winner_auto": False})
        raffle.write(
            {"notify_winner_auto": True, "notify_winner_message": "Hi"}
        )
        self.assertEqual(self.raffle.notify_winner_message, "Hi")

    def test_settings_page_shows_the_message_only_when_on(self):
        Raffle = self.env["event.raffle"]
        view = self.env.ref("event_raffle.event_raffle_view_form")
        arch = etree.fromstring(Raffle.get_view(view.id, "form")["arch"])
        page = arch.xpath("//page[@name='settings']")[0]
        toggle = page.xpath(".//field[@name='notify_winner_auto']")
        message = page.xpath(".//field[@name='notify_winner_message']")
        self.assertEqual(len(toggle), 1)
        self.assertEqual(len(message), 1)
        self.assertEqual(message[0].get("invisible"), "not notify_winner_auto")
        self.assertEqual(message[0].get("required"), "notify_winner_auto")

    def test_the_form_refuses_an_empty_message_when_on(self):
        form = Form(self.env["event.raffle"])
        form.name = "Form"
        form.notify_winner_auto = True
        form.notify_winner_message = False
        with self.assertRaises(AssertionError):
            form.save()

    # Sending after a draw

    def test_off_sends_nothing(self):
        self.raffle.notify_winner_auto = False
        draw = self._draw_next(self.internal_winner.partner_id)
        self.assertTrue(draw.exists())
        self.assertFalse(draw.notification_ids)
        self.assertFalse(self._chats_with(self.internal_winner.partner_id))

    def test_internal_winner_gets_a_private_chat_from_odoobot(self):
        winner = self.internal_winner.partner_id
        draw = self._draw_next(winner)
        notification = draw.notification_ids
        self.assertEqual(len(notification), 1)
        self.assertEqual(notification.channel, "chat")
        self.assertEqual(notification.author_id, self.odoobot)
        self.assertEqual(notification.body, MESSAGE)
        channel = notification.discuss_channel_id
        self.assertEqual(channel, self._chats_with(winner))
        self.assertEqual(
            channel.channel_member_ids.partner_id, self.odoobot | winner
        )
        message = notification.message_id
        self.assertEqual(message.author_id, self.odoobot)
        self.assertEqual(str(message.body), str(plaintext2html(MESSAGE)))
        self.assertEqual(message.model, "discuss.channel")
        self.assertEqual(message.res_id, channel.id)
        self.assertTrue(draw.notified)
        self.assertIn(
            "Notification sent by chat by OdooBot.", self._notes(draw)
        )

    def test_winner_without_user_gets_an_email_from_odoobot(self):
        draw = self._draw_next(self.contact)
        notification = draw.notification_ids
        self.assertEqual(notification.channel, "email")
        self.assertEqual(notification.author_id, self.odoobot)
        self.assertEqual(notification.body, MESSAGE)
        mail = notification.mail_id
        self.assertEqual(mail.recipient_ids, self.contact)
        self.assertEqual(mail.author_id, self.odoobot)
        self.assertIn("OdooBot", mail.email_from)
        self.assertIn(MESSAGE, str(mail.body_html))
        self.assertNotIn(DEFAULT_EN, str(mail.body_html))
        self.assertIn(
            "Notification sent by email by OdooBot.", self._notes(draw)
        )

    def test_unreachable_winner_still_gets_the_draw_and_a_note(self):
        draw = self._draw_next(self.nobody)
        self.assertEqual(draw.winner_participant_id.partner_id, self.nobody)
        self.assertEqual(self.raffle.state, "in_progress")
        self.assertFalse(draw.notification_ids)
        self.assertFalse(draw.notified)
        notes = self._notes(draw)
        self.assertIn("The automatic notification could not be sent", notes)
        self.assertIn("neither an internal user account nor an email", notes)

    def test_a_refused_send_keeps_the_draw(self):
        Wizard = self.env.registry["event.raffle.draw.notify.wizard"]
        with patch.object(
            Wizard,
            "_send_chat",
            side_effect=UserError("Chat refused"),
            autospec=True,
        ):
            draw = self._draw_next(self.internal_winner.partner_id)
        self.assertTrue(draw.exists())
        self.assertEqual(len(self.raffle.draw_ids), 1)
        self.assertFalse(draw.notification_ids)
        self.assertIn("Chat refused", self._notes(draw))

    def test_each_draw_notifies_its_own_winner(self):
        self.raffle.remove_winner = True
        self._enter(self.contact)
        self._enter(self.internal_winner.partner_id)
        Raffle = self.raffle.with_user(self.organizer)
        first = self.env["event.raffle.draw"].browse(
            Raffle.action_draw_next()["draw_id"]
        )
        second = self.env["event.raffle.draw"].browse(
            Raffle.action_draw_next()["draw_id"]
        )
        self.assertNotEqual(first.partner_id, second.partner_id)
        self.assertEqual(len(first.notification_ids), 1)
        self.assertEqual(len(second.notification_ids), 1)

    def test_the_message_takes_the_placeholders_by_chat_and_email(self):
        # Without a link, {lien} and {link} disappear, and so does the prize
        # alone in its parentheses.
        self.raffle.write(
            {
                "remove_winner": True,
                "notify_winner_message": (
                    "Bravo {gagnant}, tir #{numéro} de {tirage} ({prix}) "
                    "{lien}\n{winner} #{number} {raffle} {prize} {link}"
                ),
            }
        )
        expected = "Bravo {name}, tir #{n} de Auto\n{name} #{n} Auto"
        chat = self._draw_next(self.internal_winner.partner_id)
        sent = expected.format(name=self.internal_winner.name, n=1)
        self.assertEqual(chat.notification_ids.body, sent)
        self.assertEqual(
            str(chat.notification_ids.message_id.body).replace(
                "<br>", "<br/>"
            ),
            str(plaintext2html(sent)),
        )
        email = self._draw_next(self.contact)
        sent = expected.format(name=self.contact.name, n=2)
        self.assertEqual(email.notification_ids.body, sent)
        self.assertIn(
            str(plaintext2html(sent)),
            str(email.notification_ids.mail_id.body_html),
        )

    # Manual wizard

    def test_the_notify_wizard_replaces_the_placeholders_when_sent(self):
        self.raffle.notify_winner_auto = False
        draw = self._draw_next(self.contact)
        Wizard = self.env["event.raffle.draw.notify.wizard"]
        wizard = Wizard.with_user(self.organizer).create(
            {"draw_id": draw.id, "body": "{gagnant}: {lien} #{number}"}
        )
        self.assertEqual(wizard.body, "{gagnant}: {lien} #{number}")
        wizard.action_send()
        self.assertEqual(
            draw.notification_ids.body, f"{self.contact.name}: #1"
        )

    def test_the_notify_wizard_proposes_the_raffle_message(self):
        draw = self._draw_next(self.contact)
        Wizard = self.env["event.raffle.draw.notify.wizard"]
        wizard = Wizard.with_user(self.organizer).create({"draw_id": draw.id})
        self.assertEqual(wizard.body, MESSAGE)
        form = Form(
            Wizard.with_user(self.organizer).with_context(
                default_draw_id=draw.id
            )
        )
        self.assertEqual(form.body, MESSAGE)

    def test_the_notify_wizard_keeps_the_standard_message_when_off(self):
        self.raffle.notify_winner_auto = False
        draw = self._draw_next(self.contact)
        Wizard = self.env["event.raffle.draw.notify.wizard"]
        wizard = Wizard.with_user(self.organizer).create({"draw_id": draw.id})
        self.assertEqual(wizard.body, DEFAULT_EN)
        typed = Wizard.create({"draw_id": draw.id, "body": "Typed"})
        self.assertEqual(typed.body, "Typed")

    # Upgrade from 18.0.1.3.0

    def test_upgrade_translates_the_message_of_existing_raffles(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        french = new_test_user(
            self.env,
            login="raffle_auto_french",
            groups="base.group_user,event.group_event_user",
            name="Auto French",
            lang="fr_CA",
        )
        french_company = self.env["res.company"].create(
            {"name": "Auto French Company"}
        )
        french_company.partner_id.lang = "fr_CA"
        Raffle = self.env["event.raffle"]
        by_french = Raffle.with_user(french).create({"name": "Avant"})
        by_english = Raffle.create({"name": "Before"})
        orphan = Raffle.create(
            {"name": "Orphan", "company_id": french_company.id}
        )
        edited = Raffle.with_user(french).create({"name": "Edited"})
        # The upgrade to 18.0.1.4.0 filled the new column from the default
        # of that version, evaluated without a language: its en_US source.
        raffles = by_french | by_english | orphan | edited
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE event_raffle SET notify_winner_message = %s"
            " WHERE id = ANY(%s)",
            [OLD_EN, raffles.ids],
        )
        self.env.cr.execute(
            "UPDATE event_raffle SET create_uid = NULL WHERE id = %s",
            [orphan.id],
        )
        self.env.cr.execute(
            "UPDATE event_raffle SET notify_winner_message = %s WHERE id = %s",
            [MESSAGE, edited.id],
        )
        raffles.invalidate_recordset()

        script = load_script(
            "event_raffle/migrations/18.0.1.4.0/post-migration.py",
            "event_raffle_post_migration_18_0_1_4_0",
        )
        script.migrate(self.env.cr, "18.0.1.3.0")

        # The script writes the current default, the link included.
        self.assertEqual(by_french.notify_winner_message, DEFAULT_FR)
        self.assertEqual(orphan.notify_winner_message, DEFAULT_FR)
        self.assertEqual(by_english.notify_winner_message, DEFAULT_EN)
        self.assertEqual(edited.notify_winner_message, MESSAGE)
        # Ticked afterwards, the raffle proposes its French message to the
        # manual wizard too.
        by_french.notify_winner_auto = True
        participant = self.env["event.raffle.participant"].create(
            {
                "raffle_id": by_french.id,
                "name": self.nobody.name,
                "partner_id": self.nobody.id,
            }
        )
        draw = self.env["event.raffle.draw"].create(
            {
                "raffle_id": by_french.id,
                "winner_participant_id": participant.id,
            }
        )
        wizard = (
            self.env["event.raffle.draw.notify.wizard"]
            .with_user(french)
            .create({"draw_id": draw.id})
        )
        self.assertEqual(wizard.body, DEFAULT_FR)
