# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re
from urllib.parse import parse_qs, urlsplit

from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from .common import ClaimDataMixin

NOTIFY_EN = "You won a prize, come and claim it! {link}"
ANNOUNCE_EN = "Draw #{number}: {winner} won! ({prize}) {link}"
ANNOUNCE_FR = "Tir #{numéro} : {gagnant} a gagné ! ({prix}) {lien}"
MASKED = "/raffle/prize/********"


@tagged("post_install", "-at_install")
class TestClaimLinkMessages(ClaimDataMixin, TransactionCase):
    """{link} in the winner notification and the channel announcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, mail_create_nolog=True)
        )
        cls._claim_setup()
        cls.organizer = new_test_user(
            cls.env,
            login="claim_messages_organizer",
            groups="base.group_user,event.group_event_user",
            email="messages.organizer@example.com",
            name="Messages Organizer",
        )
        cls.prize = cls._prize("Mug", price=20.0, qty=2)
        cls.draws_channel = cls.env["discuss.channel"].create(
            {"name": "raffle-draws", "channel_type": "channel"}
        )
        cls.raffle.write(
            {
                "claim_auto_send": True,
                "notify_winner_auto": True,
                "notify_winner_message": NOTIFY_EN,
                "announce_channel_auto": True,
                "announce_channel_id": cls.draws_channel.id,
                "announce_channel_message": ANNOUNCE_EN,
            }
        )

    def _draw_next(self):
        result = self.raffle.with_user(self.organizer).action_draw_next()
        return self.env["event.raffle.draw"].browse(result["draw_id"])

    def _posts(self):
        return self.draws_channel.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ).sorted("id")

    def _mails(self, draw):
        return draw.notification_ids.sorted("id").mail_id

    def _notes(self, draw):
        return " ".join(str(body) for body in draw.message_ids.mapped("body"))

    def _link(self, draw):
        return draw.sudo().claim_link_url

    def _masked(self, draw):
        draw = draw.sudo()
        return draw.claim_link_url.replace(draw.claim_token, "********")

    def _anchor(self, link):
        """`link` as plaintext2html makes it clickable."""
        return f'<a href="{link}"'

    def _invitation_redirect(self, mail):
        """Where the account invitation of `mail` leads once the account
        exists."""
        body = str(mail.body_html).replace("&amp;", "&")
        href = re.search(r'href="([^"]*/web/signup\?[^"]+)"', body)
        self.assertTrue(href, f"no account invitation in {body}")
        return parse_qs(urlsplit(href.group(1)).query)["redirect"][0]

    def _portal_winner(self, name, login):
        user = new_test_user(
            self.env,
            login=login,
            groups="base.group_portal",
            email=f"{login}@example.com",
            name=name,
        )
        participant = self._participant(name)
        participant.partner_id = user.partner_id
        return participant

    # The link in the messages after a draw

    def test_one_message_gives_the_link_and_the_channel_shows_it(self):
        participant = self._portal_winner("Ada Portal", "messages_ada")
        draw = self._draw_next()
        self.assertEqual(draw.winner_participant_id, participant)
        link = self._link(draw)
        self.assertEqual(draw.claim_link_state, "open")
        # The notification carries the link: no second message.
        notification = draw.notification_ids
        self.assertEqual(len(notification), 1)
        self.assertEqual(notification.author_id, self.odoobot)
        self.assertEqual(
            notification.body,
            f"You won a prize, come and claim it! {self._masked(draw)}",
        )
        self.assertTrue(self._masked(draw).endswith(MASKED))
        self.assertIn(link, str(notification.mail_id.body_html))
        self.assertNotIn("/web/signup", str(notification.mail_id.body_html))
        self.assertIn("Prize link sent, valid 45 minutes", self._notes(draw))
        # The channel shows the same link, which opens to the winner only.
        post = self._posts()
        self.assertEqual(len(post), 1)
        self.assertIn(
            f"Draw #1: Ada Portal won! {self._anchor(link)}",
            str(post.body),
        )

    def test_a_winner_without_account_gets_the_invitation_not_the_channel(
        self,
    ):
        self._participant("Bea")
        draw = self._draw_next()
        token = draw.sudo().claim_token
        notification = draw.notification_ids
        self.assertEqual(len(notification), 1)
        mail = notification.mail_id
        self.assertEqual(
            self._invitation_redirect(mail), f"/raffle/prize/{token}"
        )
        # The log shows the bare link, masked, and never the invitation.
        self.assertTrue(notification.body.endswith(MASKED))
        self.assertNotIn("signup", notification.body)
        self.assertNotIn(token, notification.body)
        post = str(self._posts().body)
        self.assertIn(self._link(draw), post)
        self.assertNotIn("/web/signup", post)

    def test_the_internal_winner_reads_the_link_in_the_odoobot_chat(self):
        user = new_test_user(
            self.env,
            login="messages_internal",
            groups="base.group_user",
            email="messages.internal@example.com",
            name="Cy Internal",
        )
        participant = self._participant("Cy")
        participant.partner_id = user.partner_id
        self.raffle.notify_winner_message = "Bravo {gagnant} ! {lien}"
        draw = self._draw_next()
        link = self._link(draw)
        notification = draw.notification_ids
        self.assertEqual(len(notification), 1)
        self.assertEqual(notification.channel, "chat")
        message = notification.message_id
        self.assertEqual(message.author_id, self.odoobot)
        self.assertIn(f"Bravo Cy ! {self._anchor(link)}", str(message.body))
        self.assertEqual(notification.body, f"Bravo Cy ! {self._masked(draw)}")

    def test_a_message_without_link_is_followed_by_the_same_link(self):
        self._portal_winner("Dan Portal", "messages_dan")
        self.raffle.notify_winner_message = "Come to the desk"
        draw = self._draw_next()
        link = self._link(draw)
        first, second = draw.notification_ids.sorted("id")
        self.assertEqual(first.body, "Come to the desk")
        self.assertIn(MASKED, second.body)
        self.assertIn("45", second.body)
        # One token, issued before the messages: the link in the channel
        # is the one the winner receives.
        self.assertIn(link, str(second.mail_id.body_html))
        self.assertIn(link, str(self._posts().body))

    def test_french_placeholders_show_the_link(self):
        self._portal_winner("Eve Portal", "messages_eve")
        self.raffle.write(
            {
                "notify_winner_message": (
                    "Vous avez gagné un prix, venez le réclamer ! {lien}"
                ),
                "announce_channel_message": ANNOUNCE_FR,
            }
        )
        draw = self._draw_next()
        link = self._link(draw)
        self.assertIn(
            f"venez le réclamer ! {self._anchor(link)}",
            str(draw.notification_ids.mail_id.body_html),
        )
        self.assertIn(
            f"Tir #1 : Eve Portal a gagné ! {self._anchor(link)}",
            str(self._posts().body),
        )

    # No link: {link} disappears

    def test_no_prize_for_the_winner_issues_no_link(self):
        self.prize.product_tmpl_id.raffle_attendance = "virtual"
        self._portal_winner("Fay Portal", "messages_fay")
        draw = self._draw_next()
        self.assertFalse(draw.sudo().claim_token)
        self.assertEqual(draw.claim_link_state, "none")
        self.assertEqual(
            draw.notification_ids.body, "You won a prize, come and claim it!"
        )
        self.assertEqual(
            str(self._posts().body),
            "<p>Draw #1: Fay Portal won!</p>",
        )

    def test_links_off_issue_no_link(self):
        self.raffle.claim_auto_send = False
        self._portal_winner("Gus Portal", "messages_gus")
        draw = self._draw_next()
        self.assertFalse(draw.sudo().claim_token)
        self.assertEqual(len(draw.notification_ids), 1)
        self.assertNotIn("/raffle/prize", draw.notification_ids.body)
        self.assertNotIn("/raffle/prize", str(self._posts().body))

    def test_an_unreachable_winner_gets_no_link(self):
        self.env["event.raffle.participant"].create(
            {"raffle_id": self.raffle.id, "name": "Hal Typed"}
        )
        draw = self._draw_next()
        self.assertFalse(draw.sudo().claim_token)
        self.assertFalse(draw.notification_ids)
        notes = self._notes(draw)
        self.assertEqual(notes.count("The prize link could not be sent"), 1)
        self.assertIn("The automatic notification could not be sent", notes)
        self.assertEqual(
            str(self._posts().body),
            "<p>Draw #1: Hal Typed won!</p>",
        )

    def test_a_closed_link_is_not_shown(self):
        self._portal_winner("Ivy Portal", "messages_ivy")
        self.raffle.write(
            {"notify_winner_auto": False, "announce_channel_auto": False}
        )
        draw = self._draw_next()
        self.assertEqual(
            draw._message_render("A {lien} B"), f"A {self._link(draw)} B"
        )
        self._expire(draw)
        self.assertEqual(draw._message_render("A {lien} B"), "A B")

    # The manual Notify wizard

    def test_the_notify_wizard_shows_the_open_link(self):
        self._portal_winner("Jo Portal", "messages_jo")
        self.raffle.write(
            {"notify_winner_auto": False, "announce_channel_auto": False}
        )
        draw = self._draw_next()
        link = self._link(draw)
        Wizard = self.env["event.raffle.draw.notify.wizard"]
        wizard = Wizard.with_user(self.organizer).create(
            {"draw_id": draw.id, "sender": "me"}
        )
        self.assertEqual(wizard.body, NOTIFY_EN)
        wizard.action_send()
        notification = draw.notification_ids.sorted("id")[-1]
        self.assertEqual(notification.author_id, self.organizer.partner_id)
        self.assertIn(link, str(notification.mail_id.body_html))
        self.assertTrue(notification.body.endswith(MASKED))
        self.assertNotIn(draw.sudo().claim_token, notification.body)
