# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from datetime import timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from .test_sponsor_report import SponsorReportScenario

THANKS_MODEL = "event.raffle.sponsor.thanks"


@tagged("post_install", "-at_install")
class TestSponsorThanks(SponsorReportScenario, TransactionCase):
    """Thank the Sponsors on the scenario of the sponsor report.

    The sponsor's contact Alice and the rival's contact Carol have a
    sponsor registration of the open event; a third sponsor, without any
    email, has one prize handed over. The sponsor also has a virtual
    prize sent by email. Every value is invented.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()
        cls.env.company.email = "prizes@example.com"

    def setUp(self):
        super().setUp()
        self._scenario()
        self.virtual = self._fair_draw("Val Virtual")
        self.virtual._prize_claim(self.ebook)
        self.virtual._prize_send_virtual("<p>Open the reading app.</p>")
        self.quiet = self.env["res.partner"].create(
            {"name": "Quiet Example", "is_company": True}
        )
        quiet_prize = self._prize(
            "Quiet Pen",
            price=5.0,
            qty=1,
            raffle_sponsor_id=self.quiet.id,
            raffle_event_ids=[Command.set(self.open_event.ids)],
        )
        quiet_draw = self._fair_draw("Quin Quiet")
        quiet_draw._prize_claim(quiet_prize)
        quiet_draw.action_prize_deliver()

    def _wizard(self, user=None, event=None):
        event = (event or self.open_event).with_user(user or self.organizer)
        action = event.action_open_raffle_sponsor_thank_wizard()
        return event.env[action["res_model"]].browse(action["res_id"])

    def _line(self, wizard, sponsor):
        return wizard.line_ids.filtered(
            lambda line: line.sponsor_id == sponsor
        )

    def _mails(self):
        return self.env["mail.mail"].search([("model", "=", THANKS_MODEL)])

    def test_one_line_per_sponsor_with_its_recipients(self):
        wizard = self._wizard()
        self.assertEqual(
            wizard.line_ids.mapped("sponsor_id.name"),
            ["Quiet Example", "Rival Example", "Sponsor Example"],
        )
        line = self._line(wizard, self.sponsor)
        self.assertEqual(line.recipient_ids, self.alice.partner_id)
        self.assertEqual(line.recipient_emails, self.alice.email)
        # Reserved, handed over, shipped, and the virtual prize sent.
        self.assertEqual(line.winner_count, 4)
        self.assertTrue(line.include)
        self.assertFalse(line.thanked_label)
        rival = self._line(wizard, self.rival)
        self.assertEqual(rival.recipient_ids, self.carol.partner_id)
        self.assertEqual(rival.winner_count, 1)
        quiet = self._line(wizard, self.quiet)
        self.assertFalse(quiet.recipient_ids)
        self.assertFalse(quiet.can_include)
        self.assertFalse(quiet.include)
        self.assertIn("No email", quiet.no_email_reason)
        # The status column holds the whole reason, and wraps as a text
        # field; the sponsor and email columns have a width.
        self.assertEqual(quiet.status, quiet.no_email_reason)
        self.assertFalse(line.status)
        arch = wizard.get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn('name="status"', arch)
        self.assertNotIn('name="no_email_reason"', arch)
        self.assertNotIn('name="thanked_label"', arch)
        for name in ("sponsor_id", "recipient_emails"):
            self.assertRegex(arch, rf'name="{name}"[^>]*width="\d+px"')
        for name in ("status", "recipient_emails"):
            self.assertEqual(wizard.line_ids._fields[name].type, "text")
        with self.assertRaises(ValidationError):
            quiet.include = True
        # The preview starts on the first sponsor that has an email.
        self.assertEqual(wizard.preview_line_id, rival)

    def test_recipients_fall_back_on_the_sponsor_email(self):
        self.carol_registration.action_cancel()
        rival = self._line(self._wizard(), self.rival)
        self.assertFalse(rival.recipient_ids)
        self.rival.email = "hello@rival.example.com"
        rival = self._line(self._wizard(), self.rival)
        self.assertEqual(rival.recipient_ids, self.rival)
        # A sponsor contact without an email is skipped for the sponsor.
        self.carol_registration.write({"state": "open"})
        self.carol.partner_id.email = False
        rival = self._line(self._wizard(), self.rival)
        self.assertEqual(rival.recipient_ids, self.rival)

    def test_email_lists_public_names_and_prizes_only(self):
        wizard = self._wizard()
        wizard.preview_line_id = self._line(wizard, self.sponsor)
        body = str(wizard.preview_body)
        self.assertIn("Open Fair", wizard.preview_subject)
        for text in (
            "Hello Sponsor Example",
            "Rae Reserved",
            "Hal Handed",
            "Sky Shipped",
            "Val Virtual",
            "Report Lamp",
            "Handover Ebook",
            "Reserved",
            "Shipped",
            "Handed over on site",
            "Sent by email",
        ):
            self.assertIn(text, body)
        self.assertEqual(body.count("o_raffle_sponsor_thanks_winners"), 1)
        for text in ("Rival Mug", "Quiet Pen", "Exa Expired", "Dee Declined"):
            self.assertNotIn(text, body)
        self.assertNotIn("@example.com", body)
        # The date column never wraps inside a date.
        self.assertEqual(body.count('<td style="white-space: nowrap;">'), 4)
        wizard.preview_line_id = self._line(wizard, self.rival)
        body = str(wizard.preview_body)
        self.assertIn("Lucky Star", body)
        self.assertIn("Rival Mug", body)
        self.assertNotIn("Rob Rival", body)
        self.assertNotIn("rob.rival", body)

    def test_email_in_the_recipient_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize_sponsor"], ["fr_CA"], overwrite=True
        )
        self.alice.partner_id.lang = "fr_CA"
        wizard = self._wizard()
        wizard.preview_line_id = self._line(wizard, self.sponsor)
        body = str(wizard.preview_body)
        self.assertIn("Merci pour vos prix", wizard.preview_subject)
        for text in (
            "Bonjour Sponsor Example",
            "Gagnant",
            "Réservé",
            "Expédié",
            "Remis sur place",
            "Envoyé par courriel",
        ):
            self.assertIn(text, body)
        self.assertNotIn("Handed over on site", body)
        # The rival's contact reads English.
        wizard.preview_line_id = self._line(wizard, self.rival)
        self.assertIn("Handed over on site", str(wizard.preview_body))

    def test_sending_queues_one_mail_per_sponsor_and_logs_it(self):
        before = self._mails()
        wizard = self._wizard()
        wizard.action_send()
        mails = self._mails() - before
        self.assertEqual(len(mails), 2)
        self.assertEqual(set(mails.mapped("state")), {"outgoing"})
        self.assertEqual(
            mails.recipient_ids, self.alice.partner_id | self.carol.partner_id
        )
        rival_mail = mails.filtered(
            lambda m: self.carol.partner_id in m.recipient_ids
        )
        self.assertIn("Lucky Star", str(rival_mail.body_html))
        self.assertNotIn("rob.rival", str(rival_mail.body_html))
        self.assertIn("prizes@example.com", rival_mail.email_from)
        logs = self.open_event.message_ids.filtered(
            lambda m: "Thank-you email sent to the sponsor" in str(m.body)
        )
        self.assertEqual(len(logs), 2)
        self.assertTrue(
            logs.filtered(
                lambda m: "Rival Example" in str(m.body)
                and "1 winner(s)" in str(m.body)
            )
        )
        for sponsor in (self.sponsor, self.rival):
            self.assertTrue(
                sponsor.message_ids.filtered(
                    lambda m: "Thank-you email for Open Fair" in str(m.body)
                )
            )
        thanks = self.env[THANKS_MODEL].search(
            [("event_id", "=", self.open_event.id)]
        )
        self.assertEqual(
            thanks.filtered("sent_date").sponsor_id, self.sponsor | self.rival
        )
        sent = thanks.filtered(lambda t: t.sponsor_id == self.sponsor)
        self.assertEqual(sent.sent_winner_count, 4)
        self.assertEqual(sent.sent_by_id, self.organizer)

    def test_second_send_warns_and_needs_a_tick(self):
        self._wizard().action_send()
        before = self._mails()
        wizard = self._wizard()
        line = self._line(wizard, self.sponsor)
        self.assertIn("Already thanked on", line.thanked_label)
        # The date is shown to the minute: no seconds in the label.
        line.thanks_id.sudo().sent_date = "2026-01-15 15:04:37"
        line.invalidate_recordset(["thanked_date", "thanked_label", "status"])
        self.assertNotIn("37", line.thanked_label)
        self.assertEqual(line.status, line.thanked_label)
        # A sponsor without an email thanked before shows both facts.
        quiet = self._line(wizard, self.quiet)
        quiet.thanks_id.sudo().sent_date = "2026-01-15 15:00:00"
        quiet.invalidate_recordset(["thanked_date", "thanked_label", "status"])
        self.assertEqual(
            quiet.status.split("\n"),
            [quiet.no_email_reason, quiet.thanked_label],
        )
        self.assertFalse(line.include)
        with self.assertRaises(UserError):
            wizard.action_send()
        line.include = True
        wizard.action_send()
        mails = self._mails() - before
        self.assertEqual(mails.recipient_ids, self.alice.partner_id)

    def test_who_may_thank_the_sponsors(self):
        reviewer = new_test_user(
            self.env,
            login="thanks_reviewer",
            groups="base.group_user",
            email="thanks.reviewer@example.com",
        )
        self.open_event.raffle_sponsor_manager_ids = [
            Command.link(reviewer.id)
        ]
        wizard = self._wizard(user=reviewer)
        self.assertEqual(len(wizard.line_ids), 3)
        self.assertIn("Rival Mug", str(wizard.preview_body))
        with self.assertRaises(AccessError):
            self._wizard(user=reviewer, event=self.second_event)
        plain = new_test_user(
            self.env,
            login="thanks_plain",
            groups="base.group_user",
            email="thanks.plain@example.com",
        )
        for user in (plain, self.alice):
            with self.assertRaises(AccessError):
                self._wizard(user=user)
            with self.assertRaises(AccessError):
                self.env["event.raffle.sponsor.thank.wizard"].with_user(
                    user
                ).create({"event_id": self.open_event.id})
        # A line of another event's sponsor is refused at the sending.
        other = self.env[THANKS_MODEL]._raffle_get(
            self.second_event, self.sponsor
        )
        self._line(wizard, self.sponsor).sudo().thanks_id = other
        with self.assertRaises(AccessError):
            wizard.action_send()

    def test_template_link_for_template_editors(self):
        wizard = self._wizard()
        self.assertFalse(wizard.can_edit_template)
        with self.assertRaises(AccessError):
            wizard.action_open_template()
        editor = new_test_user(
            self.env,
            login="thanks_editor",
            groups="base.group_user,event.group_event_user,"
            "mail.group_mail_template_editor",
            email="thanks.editor@example.com",
        )
        wizard = self._wizard(user=editor)
        self.assertTrue(wizard.can_edit_template)
        action = wizard.action_open_template()
        self.assertEqual(
            action["res_id"],
            self.env.ref(
                "event_raffle_prize_sponsor.mail_template_sponsor_thanks"
            ).id,
        )

    def test_button_and_wizard_without_a_sponsored_winner(self):
        """An event whose winners hold prizes without a sponsor only: no
        button, and the wizard says there is no sponsor to thank."""
        self.assertEqual(self.open_event.raffle_sponsor_thanks_count, 6)
        event = self._event(
            "Staff Fair", self.open_event.date_end + timedelta(days=5)
        )
        raffle = self.env["event.raffle"].create(
            {
                "name": "Staff raffle",
                "event_id": event.id,
                "claim_auto_send": False,
            }
        )
        participant = self.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": "Stu Staff",
                "email": "stu.staff@example.com",
            }
        )
        draw = self._draw(participant)
        staff_prize = self._prize(
            "Staff Cap",
            price=6.0,
            qty=1,
            raffle_sponsor_id=False,
            raffle_event_ids=[Command.set(event.ids)],
        )
        draw._prize_claim(staff_prize)
        draw.action_prize_deliver()
        self.assertEqual(event.raffle_winner_count, 1)
        self.assertEqual(event.raffle_sponsor_thanks_count, 0)
        form = event.get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertRegex(
            form,
            r'name="action_open_raffle_sponsor_thank_wizard"'
            r'[^>]*invisible="not raffle_sponsor_thanks_count"',
        )
        wizard = self._wizard(event=event)
        self.assertFalse(wizard.line_ids)
        with self.assertRaisesRegex(UserError, "has a winner yet"):
            wizard.action_send()
        arch = wizard.get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertRegex(
            arch, r'name="action_send"[^>]*invisible="not line_ids"'
        )
