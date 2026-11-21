# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.migration import load_script
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user

DEFAULT_EN = "Draw #{number}: {winner} won! ({prize}) {link}"
DEFAULT_FR = "Tir #{numéro} : {gagnant} a gagné ! ({prix}) {lien}"
# The default of 18.0.1.5.0, before the link.
OLD_EN = "Draw #{number}: {winner} won! ({prize})"
LINK = "https://raffle.example.com/raffle/prize/abc"


class TestRaffleAnnounce(TransactionCase):
    """Announcement of each draw in a discussion channel, as OdooBot."""

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
            login="raffle_announce_organizer",
            groups="base.group_user,event.group_event_user",
            email="announce.organizer@example.com",
            name="Announce Organizer",
        )
        cls.member = new_test_user(
            cls.env,
            login="raffle_announce_member",
            groups="base.group_user",
            name="Announce Member",
        )
        cls.channel = cls.env["discuss.channel"].create(
            {"name": "raffle-draws", "channel_type": "channel"}
        )
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Evening",
                "announce_channel_auto": True,
                "announce_channel_id": cls.channel.id,
                "announce_channel_message": DEFAULT_EN,
            }
        )

    def _draw_next(self, name="Alice", raffle=None, **kwargs):
        """Draw the only participant, `name`, as an event user."""
        raffle = raffle or self.raffle
        self.env["event.raffle.participant"].create(
            {"raffle_id": raffle.id, "name": name}
        )
        result = raffle.with_user(self.organizer).action_draw_next(**kwargs)
        return self.env["event.raffle.draw"].browse(result["draw_id"])

    def _posts(self, channel=None):
        channel = channel or self.channel
        return channel.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ).sorted("id")

    def _notes(self, draw):
        return " ".join(str(body) for body in draw.message_ids.mapped("body"))

    def _render(self, template, link="", **vals):
        """Render `template` for draw #7 of Alice, whose {link} is `link`."""
        draw = self.env["event.raffle.draw"].new(
            dict(
                {
                    "raffle_id": self.raffle.id,
                    "sequence": 7,
                    "winner_name": "Alice",
                },
                **vals,
            )
        )
        Draw = type(draw)
        values = Draw._message_values

        def with_link(record, to_winner=False):
            return dict(values(record, to_winner=to_winner), link=link)

        with patch.object(Draw, "_message_values", with_link):
            return draw._message_render(template)

    # Settings

    def test_off_by_default_with_the_standard_message(self):
        raffle = self.env["event.raffle"].create({"name": "Fresh"})
        self.assertFalse(raffle.announce_channel_auto)
        self.assertFalse(raffle.announce_channel_id)
        self.assertEqual(raffle.announce_channel_message, DEFAULT_EN)

    def test_default_message_is_translated(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        Raffle = self.env["event.raffle"].with_context(lang="fr_CA")
        raffle = Raffle.create({"name": "Frais"})
        self.assertEqual(raffle.announce_channel_message, DEFAULT_FR)

    def test_channel_and_message_are_required_when_on(self):
        Raffle = self.env["event.raffle"]
        with self.assertRaises(ValidationError):
            Raffle.create(
                {"name": "No channel", "announce_channel_auto": True}
            )
        with self.assertRaises(ValidationError):
            Raffle.create(
                {
                    "name": "No message",
                    "announce_channel_auto": True,
                    "announce_channel_id": self.channel.id,
                    "announce_channel_message": " ",
                }
            )
        with self.assertRaises(ValidationError):
            self.raffle.announce_channel_id = False
        raffle = Raffle.create(
            {"name": "Off", "announce_channel_message": False}
        )
        self.assertFalse(raffle.announce_channel_auto)

    def test_settings_page_shows_channel_and_message_only_when_on(self):
        Raffle = self.env["event.raffle"]
        view = self.env.ref("event_raffle.event_raffle_view_form")
        arch = etree.fromstring(Raffle.get_view(view.id, "form")["arch"])
        page = arch.xpath("//page[@name='settings']")[0]
        group = page.xpath(".//group[@name='announce_channel']")[0]
        self.assertEqual(
            len(group.xpath("field[@name='announce_channel_auto']")), 1
        )
        for name in ("announce_channel_id", "announce_channel_message"):
            (field,) = group.xpath(f"field[@name='{name}']")
            self.assertEqual(
                field.get("invisible"), "not announce_channel_auto"
            )
            self.assertEqual(field.get("required"), "announce_channel_auto")

    def test_the_form_refuses_a_missing_channel_when_on(self):
        form = Form(self.env["event.raffle"])
        form.name = "Form"
        form.announce_channel_auto = True
        with self.assertRaises(AssertionError):
            form.save()

    def test_the_channel_choice_offers_channels_and_groups(self):
        field = self.env["event.raffle"]._fields["announce_channel_id"]
        self.assertEqual(
            field.domain, "[('channel_type', 'in', ('channel', 'group'))]"
        )

    # Rendering

    def test_placeholders_in_english_and_french(self):
        self.assertEqual(
            self._render(DEFAULT_EN, prize="Bike"),
            "Draw #7: Alice won! (Bike)",
        )
        self.assertEqual(
            self._render(DEFAULT_FR, prize="Vélo"),
            "Tir #7 : Alice a gagné ! (Vélo)",
        )
        self.assertEqual(
            self._render("{raffle}/{tirage} {numero} {PRIZE}", prize="X"),
            "Evening/Evening 7 X",
        )

    def test_a_missing_prize_drops_its_parentheses(self):
        self.assertEqual(self._render(DEFAULT_EN), "Draw #7: Alice won!")
        self.assertEqual(self._render(DEFAULT_FR), "Tir #7 : Alice a gagné !")
        self.assertEqual(self._render("{winner} [{prize}] ()"), "Alice [] ()")

    def test_the_link_in_english_and_french(self):
        self.assertEqual(
            self._render(DEFAULT_EN, link=LINK, prize="Bike"),
            f"Draw #7: Alice won! (Bike) {LINK}",
        )
        self.assertEqual(
            self._render(DEFAULT_FR, link=LINK),
            f"Tir #7 : Alice a gagné ! {LINK}",
        )
        self.assertEqual(
            self._render("{LIEN} {Link}", link=LINK), f"{LINK} {LINK}"
        )

    def test_an_empty_link_leaves_no_space_behind(self):
        self.assertEqual(self._render("Bravo {lien} !"), "Bravo !")
        self.assertEqual(self._render("{link} Bravo"), "Bravo")
        self.assertEqual(self._render("Bravo {lien}\nNext"), "Bravo\nNext")
        self.assertEqual(self._render("A\n {lien} {link} B"), "A\nB")
        self.assertEqual(self._render("A {link}{lien}."), "A.")
        self.assertEqual(self._render("A ({lien})"), "A")
        self.assertEqual(self._render("{lien}"), "")

    def test_stray_braces_and_unknown_names_stay_as_typed(self):
        self.assertEqual(
            self._render("{ {winner}} {unknown} {0} {} {winner"),
            "{ Alice} {unknown} {0} {} {winner",
        )
        self.assertEqual(self._render("({unknown})"), "({unknown})")

    def test_values_are_not_parsed_again(self):
        self.assertEqual(
            self._render("{winner} {prize}", winner_name="{prize}", prize="P"),
            "{prize} P",
        )

    # Posting after a draw

    def test_off_posts_nothing(self):
        self.raffle.announce_channel_auto = False
        draw = self._draw_next()
        self.assertTrue(draw.exists())
        self.assertFalse(self._posts())

    def test_each_draw_is_announced_by_odoobot(self):
        self.raffle.remove_winner = True
        self.env["event.raffle.participant"].create(
            {"raffle_id": self.raffle.id, "name": "Bob"}
        )
        first = self._draw_next("Alice", prize="Bike")
        second = self._draw_next("Carol")
        posts = self._posts()
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts.author_id, self.odoobot)
        self.assertEqual(posts.mapped("model"), ["discuss.channel"] * 2)
        self.assertEqual(
            [str(post.body) for post in posts],
            [
                f"<p>Draw #1: {first.winner_name} won! (Bike)</p>",
                f"<p>Draw #2: {second.winner_name} won!</p>",
            ],
        )

    def test_the_winner_name_is_the_one_shown_on_the_draw(self):
        partner = self.env["res.partner"].create(
            {"name": "Contact Name", "email": "contact.name@example.com"}
        )
        self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle.id,
                "name": "Wheel Name",
                "partner_id": partner.id,
            }
        )
        self.raffle.with_user(self.organizer).action_draw_next()
        self.assertEqual(
            str(self._posts().body), "<p>Draw #1: Wheel Name won!</p>"
        )

    def test_french_message_is_posted_as_typed(self):
        self.raffle.announce_channel_message = DEFAULT_FR
        self._draw_next(prize="Vélo")
        self.assertEqual(
            str(self._posts().body), "<p>Tir #1 : Alice a gagné ! (Vélo)</p>"
        )

    def test_the_text_is_escaped(self):
        self.raffle.announce_channel_message = "<b>{winner}</b> & {prize}"
        self._draw_next("<i>Eve</i>", prize="<script>x</script>")
        body = str(self._posts().body)
        self.assertNotIn("<b>", body)
        self.assertNotIn("<i>", body)
        self.assertNotIn("<script>", body)
        self.assertEqual(
            body,
            "<p>&lt;b&gt;&lt;i&gt;Eve&lt;/i&gt;&lt;/b&gt; &amp; "
            "&lt;script&gt;x&lt;/script&gt;</p>",
        )

    def test_a_group_chat_the_user_is_not_in_gets_the_post(self):
        group = self.env["discuss.channel"].create(
            {
                "name": "organizers",
                "channel_type": "group",
                "channel_member_ids": [
                    Command.create({"partner_id": self.member.partner_id.id})
                ],
            }
        )
        self.assertNotIn(
            self.organizer.partner_id, group.channel_member_ids.partner_id
        )
        self.raffle.announce_channel_id = group
        draw = self._draw_next()
        self.assertEqual(len(self._posts(group)), 1)
        self.assertEqual(self._posts(group).author_id, self.odoobot)
        self.assertNotIn("could not be announced", self._notes(draw))

    def test_an_event_user_edits_the_settings(self):
        raffle = self.raffle.with_user(self.organizer)
        raffle.write({"announce_channel_auto": False})
        raffle.write(
            {"announce_channel_auto": True, "announce_channel_message": "Hi"}
        )
        self.assertEqual(self.raffle.announce_channel_message, "Hi")

    # Who chooses the channel

    def _private_group(self):
        """A group chat whose only member is the member, not the
        organizer."""
        return self.env["discuss.channel"].create(
            {
                "name": "private-organizers",
                "channel_type": "group",
                "channel_member_ids": [
                    Command.create({"partner_id": self.member.partner_id.id})
                ],
            }
        )

    def _direct_chat(self):
        """A direct chat between the member and another user."""
        other = new_test_user(
            self.env,
            login="raffle_announce_other",
            groups="base.group_user",
            name="Announce Other",
        )
        Channel = self.env["discuss.channel"].with_user(self.member)
        chat = Channel.channel_get([other.partner_id.id])
        self.assertEqual(chat.channel_type, "chat")
        return chat.with_env(self.env)

    def test_an_event_user_chooses_a_channel_they_can_read_only(self):
        group = self._private_group()
        raffle = self.raffle.with_user(self.organizer)
        with self.assertRaises(AccessError):
            raffle.write({"announce_channel_id": group.id})
        with self.assertRaises(AccessError):
            self.env["event.raffle"].with_user(self.organizer).create(
                {
                    "name": "Elsewhere",
                    "announce_channel_auto": True,
                    "announce_channel_id": group.id,
                }
            )
        self.assertEqual(self.raffle.announce_channel_id, self.channel)
        group.add_members(partner_ids=self.organizer.partner_id.ids)
        raffle.write({"announce_channel_id": group.id})
        self.assertEqual(self.raffle.announce_channel_id, group)

    def test_a_direct_chat_is_never_an_announcement_channel(self):
        chat = self._direct_chat()
        with self.assertRaises(ValidationError):
            self.raffle.announce_channel_id = chat
        config = self.env.ref("event_raffle.raffle_config_singleton")
        with self.assertRaises(ValidationError):
            config.default_announce_channel_id = chat
        self.assertEqual(self.raffle.announce_channel_id, self.channel)

    def test_a_direct_chat_set_earlier_gets_no_post(self):
        chat = self._direct_chat()
        self.env.cr.execute(
            "UPDATE event_raffle SET announce_channel_id = %s WHERE id = %s",
            (chat.id, self.raffle.id),
        )
        self.raffle.invalidate_recordset(["announce_channel_id"])
        draw = self._draw_next()
        self.assertTrue(draw.exists())
        self.assertFalse(self._posts(chat))
        self.assertIn("is not a channel or a group chat", self._notes(draw))

    def test_the_default_channel_is_one_the_creator_can_read(self):
        group = self._private_group()
        self.env.ref("event_raffle.raffle_config_singleton").write(
            {
                "default_announce_channel_auto": True,
                "default_announce_channel_id": group.id,
            }
        )
        Raffle = self.env["event.raffle"]
        raffle = Raffle.with_user(self.organizer).create({"name": "Mine"})
        self.assertFalse(raffle.announce_channel_id)
        self.assertFalse(raffle.announce_channel_auto)
        self.assertEqual(
            Raffle.create({"name": "Admin"}).announce_channel_id, group
        )

    # Failures keep the draw

    def test_an_archived_channel_keeps_the_draw_and_leaves_a_note(self):
        self.channel.active = False
        draw = self._draw_next()
        self.assertTrue(draw.exists())
        self.assertEqual(self.raffle.state, "in_progress")
        self.assertFalse(self._posts())
        notes = self._notes(draw)
        self.assertIn("could not be announced in the channel", notes)
        self.assertIn("is archived", notes)

    def test_a_deleted_channel_keeps_the_draw_and_leaves_a_note(self):
        self.channel.unlink()
        self.assertFalse(self.raffle.announce_channel_id)
        self.assertTrue(self.raffle.announce_channel_auto)
        draw = self._draw_next()
        self.assertTrue(draw.exists())
        self.assertIn("has no discussion channel", self._notes(draw))

    def test_a_refused_post_keeps_the_draw_and_leaves_a_note(self):
        Channel = self.env.registry["discuss.channel"]
        with patch.object(
            Channel,
            "message_post",
            side_effect=UserError("Post refused"),
            autospec=True,
        ):
            draw = self._draw_next()
        self.assertTrue(draw.exists())
        self.assertEqual(len(self.raffle.draw_ids), 1)
        self.assertFalse(self._posts())
        self.assertIn("Post refused", self._notes(draw))

    def test_a_post_refused_after_writing_leaves_no_message(self):
        Channel = self.env.registry["discuss.channel"]
        message_post = Channel.message_post

        def post_then_refuse(channel, **kwargs):
            message_post(channel, **kwargs)
            channel.env.flush_all()
            raise UserError("Refused after writing")

        with patch.object(
            Channel,
            "message_post",
            side_effect=post_then_refuse,
            autospec=True,
        ):
            draw = self._draw_next()
        self.env.invalidate_all()
        self.assertTrue(draw.exists())
        self.assertFalse(self._posts())
        self.assertFalse(
            self.env["mail.message"].search_count(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", self.channel.id),
                    ("message_type", "=", "comment"),
                ]
            )
        )
        self.assertIn("Refused after writing", self._notes(draw))

    # Upgrade from 18.0.1.4.0

    def test_upgrade_translates_the_message_of_existing_raffles(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        french = new_test_user(
            self.env,
            login="raffle_announce_french",
            groups="base.group_user,event.group_event_user",
            name="Announce French",
            lang="fr_CA",
        )
        Raffle = self.env["event.raffle"]
        by_french = Raffle.with_user(french).create({"name": "Avant"})
        by_english = Raffle.create({"name": "Before"})
        edited = Raffle.with_user(french).create({"name": "Edited"})
        # The upgrade to 18.0.1.5.0 filled the new column from the default
        # of that version, evaluated without a language: its en_US source.
        raffles = by_french | by_english | edited
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE event_raffle SET announce_channel_message = %s"
            " WHERE id = ANY(%s)",
            [OLD_EN, raffles.ids],
        )
        self.env.cr.execute(
            "UPDATE event_raffle SET announce_channel_message = %s"
            " WHERE id = %s",
            ["{winner}!", edited.id],
        )
        raffles.invalidate_recordset()

        script = load_script(
            "event_raffle/migrations/18.0.1.5.0/post-migration.py",
            "event_raffle_post_migration_18_0_1_5_0",
        )
        script.migrate(self.env.cr, "18.0.1.4.0")

        # The script writes the current default, the link included.
        self.assertEqual(by_french.announce_channel_message, DEFAULT_FR)
        self.assertEqual(by_english.announce_channel_message, DEFAULT_EN)
        self.assertEqual(edited.announce_channel_message, "{winner}!")
