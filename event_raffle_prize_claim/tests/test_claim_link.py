# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from .common import ClaimDataMixin


@tagged("post_install", "-at_install")
class TestClaimLink(ClaimDataMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, mail_create_nolog=True)
        )
        cls._claim_setup()
        cls.organizer = new_test_user(
            cls.env,
            login="claim_organizer",
            groups="base.group_user,event.group_event_user",
            email="organizer@example.com",
            name="Claim Organizer",
        )
        cls.prize = cls._prize("Mug", price=20.0, qty=2)

    def _send(self, draw):
        draw.with_user(self.organizer).action_claim_link_send()
        return draw.sudo().claim_token

    def _invitation_redirect(self, mail):
        """Where the account invitation of the link email `mail` leads
        once the account exists."""
        body = str(mail.body_html).replace("&amp;", "&")
        href = re.search(r'href="([^"]*/web/signup\?[^"]+)"', body)
        self.assertTrue(href, f"no account invitation in {body}")
        query = parse_qs(urlsplit(href.group(1)).query)
        self.assertTrue(query.get("token"))
        return query["redirect"][0]

    # Token

    def test_send_issues_a_token_and_a_deadline(self):
        draw = self._draw(self._participant("Ada"))
        self.assertEqual(draw.claim_link_state, "none")
        token = self._send(draw)
        self.assertGreaterEqual(len(token), 43)
        self.assertEqual(draw.claim_link_state, "open")
        delay = (draw.claim_deadline - draw.create_date).total_seconds()
        self.assertAlmostEqual(delay, 45 * 60, delta=120)
        self.assertEqual(
            self.env["event.raffle.draw"]._claim_link_find(token), draw
        )
        url = draw.claim_link_url
        self.assertTrue(url.endswith(f"/raffle/prize/{token}"))
        self.assertTrue(url.startswith(draw.get_base_url()))

    def test_send_again_replaces_the_token(self):
        draw = self._draw(self._participant("Ben"))
        first = self._send(draw)
        second = self._send(draw)
        self.assertNotEqual(first, second)
        Draw = self.env["event.raffle.draw"]
        self.assertFalse(Draw._claim_link_find(first))
        self.assertEqual(Draw._claim_link_find(second), draw)
        self.assertEqual(len(draw.notification_ids), 2)

    def test_find_refuses_forged_and_closed_tokens(self):
        Draw = self.env["event.raffle.draw"]
        draw = self._draw(self._participant("Cleo"))
        token = self._send(draw)
        forged = token[:-1] + ("A" if token[-1] != "A" else "B")
        for value in (None, "", "short", forged, token + "x", 42, "é" * 43):
            self.assertFalse(Draw._claim_link_find(value), value)
        self._expire(draw)
        self.assertFalse(Draw._claim_link_find(token))
        self.assertEqual(draw.claim_link_state, "expired")

    def test_token_fields_are_written_by_the_link_only(self):
        draw = self._draw(self._participant("Dora"))
        for vals in (
            {"claim_token": "x" * 43},
            {"claim_deadline": "2030-01-01 00:00:00"},
            {"claim_link_end": "used"},
        ):
            with self.assertRaises(AccessError):
                draw.with_user(self.organizer).write(vals)
        Draw = self.env["event.raffle.draw"].with_user(self.organizer)
        created = Draw.with_context(default_claim_token="y" * 43).create(
            {"raffle_id": self.raffle.id, "winner_name": "Nobody"}
        )
        self.assertFalse(created.sudo().claim_token)

    def test_token_is_hidden_from_users_outside_the_event_group(self):
        draw = self._draw(self._participant("Edo"))
        self._send(draw)
        field = self.env["event.raffle.draw"]._fields["claim_token"]
        self.assertEqual(field.groups, "event.group_event_user")
        url_field = self.env["event.raffle.draw"]._fields["claim_link_url"]
        self.assertEqual(url_field.groups, "event.group_event_user")
        for view in self.env["ir.ui.view"].search(
            [("model", "=", "event.raffle.draw"), ("type", "=", "list")]
        ):
            arch = view.arch_db or ""
            self.assertNotIn("claim_token", arch)
            self.assertNotIn("claim_link_url", arch)

    def test_no_link_once_the_claim_is_settled(self):
        draw = self._draw(self._participant("Fay"))
        draw._prize_claim(self.prize)
        with self.assertRaisesRegex(UserError, "settled"):
            draw.with_user(self.organizer).action_claim_link_send()
        self.assertFalse(draw.notification_ids)

    def test_no_link_without_a_way_to_reach_the_winner(self):
        guest = self.env["event.raffle.participant"].create(
            {"raffle_id": self.raffle.id, "name": "Gus"}
        )
        draw = self._draw(guest, winner_email=False)
        with self.assertRaises(UserError):
            draw.with_user(self.organizer).action_claim_link_send()
        self.assertFalse(draw.sudo().claim_token)

    # Sending

    def test_auto_send_after_a_draw_sends_one_message_with_the_link(self):
        self.raffle.claim_auto_send = True
        participant = self._participant("Hana")
        mails_before = self.env["mail.mail"].search([])
        result = self.raffle.with_user(self.organizer).action_draw_next()
        draw = self.env["event.raffle.draw"].browse(result["draw_id"])
        self.assertEqual(draw.winner_participant_id, participant)
        self.assertEqual(len(draw.notification_ids), 1)
        notification = draw.notification_ids
        self.assertEqual(notification.channel, "email")
        self.assertEqual(notification.author_id, self.odoobot)
        token = draw.sudo().claim_token
        # The log on the draw masks the token; the email carries it.
        self.assertIn("/raffle/prize/********", notification.body)
        self.assertNotIn(token, notification.body)
        self.assertIn("45", notification.body)
        mails = self.env["mail.mail"].search([]) - mails_before
        self.assertEqual(len(mails), 1)
        self.assertEqual(
            self._invitation_redirect(mails), f"/raffle/prize/{token}"
        )
        self.assertEqual(mails.recipient_ids, participant.partner_id)
        # The draw's chatter tells that a link went out, never the token.
        for message in draw.message_ids:
            self.assertNotIn(token, str(message.body))

    def test_auto_notify_and_link_both_go_out_after_a_draw(self):
        # A notification message without {link} does not give the link:
        # the link message follows it, so the winner reads the message
        # first and the link second.
        self.raffle.write(
            {
                "claim_auto_send": True,
                "notify_winner_auto": True,
                "notify_winner_message": "Come to the desk",
            }
        )
        self._participant("Noa")
        mails_before = self.env["mail.mail"].search([])
        result = self.raffle.with_user(self.organizer).action_draw_next()
        draw = self.env["event.raffle.draw"].browse(result["draw_id"])
        first, second = draw.notification_ids.sorted("id")
        self.assertEqual(first.body, "Come to the desk")
        self.assertIn("/raffle/prize/********", second.body)
        self.assertNotIn("Come to the desk", second.body)
        self.assertEqual((first | second).author_id, self.odoobot)
        token = draw.sudo().claim_token
        mails = (self.env["mail.mail"].search([]) - mails_before).sorted("id")
        self.assertEqual(len(mails), 2)
        self.assertIn("Come to the desk", str(mails[0].body_html))
        self.assertEqual(
            self._invitation_redirect(mails[1]), f"/raffle/prize/{token}"
        )
        self.assertEqual(draw.claim_link_state, "open")

    def test_auto_send_needs_a_prize_for_the_winner(self):
        self.raffle.claim_auto_send = True
        self.prize.product_tmpl_id.raffle_attendance = "virtual"
        self._participant("Ivo", attended=True)
        result = self.raffle.with_user(self.organizer).action_draw_next()
        draw = self.env["event.raffle.draw"].browse(result["draw_id"])
        self.assertFalse(draw.notification_ids)
        self.assertEqual(draw.claim_link_state, "none")

    def test_auto_send_off_sends_nothing(self):
        self._participant("Jade")
        result = self.raffle.with_user(self.organizer).action_draw_next()
        draw = self.env["event.raffle.draw"].browse(result["draw_id"])
        self.assertFalse(draw.notification_ids)

    def test_message_is_translated_with_the_delay(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.raffle.claim_delay_minutes = 30
        participant = self._participant("Kai")
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant)
        token = self._send(draw)
        body = str(draw.notification_ids.mail_id.body_html)
        self.assertIn("Vous avez gagné un prix", body)
        self.assertIn("30 minutes", body)
        self.assertIn(token, body)

    def test_email_subject_and_body_share_the_winner_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.organizer.lang = "en_US"
        participant = self._participant("Lou")
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant)
        self._send(draw)
        mail = draw.notification_ids.mail_id
        self.assertIn("Vous avez gagné un prix", mail.subject)
        self.assertIn("Vous avez gagné un prix", str(mail.body_html))
        # The note on the draw stays in the language of the sender.
        notes = " ".join(draw.message_ids.mapped("body"))
        self.assertIn("Notification sent by email", notes)

    def test_portal_winner_gets_the_bare_link_by_email(self):
        user = new_test_user(
            self.env,
            login="claim_portal_member",
            groups="base.group_portal",
            email="portal.member@example.com",
        )
        participant = self._participant("Pia")
        participant.partner_id = user.partner_id
        draw = self._draw(participant)
        token = self._send(draw)
        body = str(draw.notification_ids.mail_id.body_html)
        self.assertIn(f"/raffle/prize/{token}", body)
        self.assertNotIn("/web/signup", body)
        self.assertNotIn("creates your account", body)

    def test_archived_account_gets_no_invitation(self):
        user = new_test_user(
            self.env,
            login="claim_archived_member",
            groups="base.group_portal",
            email="archived.member@example.com",
        )
        user.active = False
        participant = self._participant("Abe")
        participant.partner_id = user.partner_id
        draw = self._draw(participant)
        token = self._send(draw)
        body = str(draw.notification_ids.mail_id.body_html)
        self.assertIn(f"/raffle/prize/{token}", body)
        self.assertNotIn("/web/signup", body)

    def test_winner_without_contact_gets_one_and_an_invitation(self):
        guest = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle.id,
                "name": "Remy Typed",
                "email": "remy.typed@example.com",
            }
        )
        draw = self._draw(guest)
        self.assertFalse(draw.partner_id)
        token = self._send(draw)
        partner = draw.partner_id
        self.assertTrue(partner)
        self.assertEqual(guest.partner_id, partner)
        self.assertEqual(partner.email, "remy.typed@example.com")
        self.assertFalse(partner.user_ids)
        mail = draw.notification_ids.mail_id
        self.assertEqual(mail.recipient_ids, partner)
        self.assertEqual(
            self._invitation_redirect(mail), f"/raffle/prize/{token}"
        )
        # The log of the draw names neither token.
        body = draw.notification_ids.body
        self.assertIn("/raffle/prize/********", body)
        self.assertNotIn("signup", body)
        self.assertNotIn(token, body)

    def test_invitation_is_in_the_winner_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize_claim"], ["fr_CA"], overwrite=True
        )
        participant = self._participant("Zoe")
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant)
        self._send(draw)
        body = str(draw.notification_ids.mail_id.body_html)
        self.assertIn("votre compte sur le site web", body)

    def test_internal_winner_gets_the_link_by_chat(self):
        user = new_test_user(
            self.env,
            login="claim_internal_winner",
            groups="base.group_user",
            email="internal.winner@example.com",
        )
        participant = self._participant("Lia")
        participant.partner_id = user.partner_id
        draw = self._draw(participant)
        token = self._send(draw)
        notification = draw.notification_ids
        self.assertEqual(notification.channel, "chat")
        self.assertIn(token, str(notification.message_id.body))

    # Expiry

    def test_issue_schedules_the_expiry_at_the_deadline(self):
        cron = self.env.ref(
            "event_raffle_prize_claim.ir_cron_prize_claim_expire"
        )
        draw = self._draw(self._participant("Mia"))
        self._send(draw)
        triggers = self.env["ir.cron.trigger"].search(
            [("cron_id", "=", cron.id)]
        )
        self.assertIn(draw.claim_deadline, triggers.mapped("call_at"))

    def test_expiry_closes_the_link_and_alerts_the_channel(self):
        participant = self._participant("Noe")
        draw = self._draw(participant)
        token = self._send(draw)
        cart = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        free = self.prize.raffle_qty_free
        # Not yet due: nothing happens.
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertEqual(draw.claim_state, "none")
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertEqual(draw.claim_state, "expired")
        self.assertEqual(draw.claim_link_state, "expired")
        self.assertFalse(draw.sudo().claim_token)
        self.assertFalse(self.env["event.raffle.draw"]._claim_link_find(token))
        self.assertEqual(cart.state, "cancel")
        self.prize.invalidate_recordset(["raffle_qty_free"])
        self.assertEqual(self.prize.raffle_qty_free, free)
        bodies = self._channel_bodies()
        self.assertEqual(len(bodies), 1)
        self.assertIn("expired", bodies[0])
        self.assertIn("Noe", bodies[0])
        self.assertIn(f"#{draw.sequence}", bodies[0])
        self.assertNotIn(token, bodies[0])

    def test_expiry_leaves_a_reserved_claim_alone(self):
        draw = self._draw(self._participant("Olga"))
        self._send(draw)
        order = draw._prize_claim(self.prize)
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(order.state, "sale")
        self.assertFalse(self._channel_bodies())

    def test_expiry_alert_is_translated(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.company.partner_id.lang = "fr_CA"
        draw = self._draw(self._participant("Paz"))
        self._send(draw)
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertIn("expiré", self._channel_bodies()[0])

    # Assisted choice and decline

    def test_assisted_choice_revokes_the_link(self):
        draw = self._draw(self._participant("Quin"))
        token = self._send(draw)
        wizard = (
            self.env["event.raffle.prize.choose.wizard"]
            .with_user(self.organizer)
            .create({"draw_id": draw.id, "product_id": self.prize.id})
        )
        wizard.action_confirm()
        self.assertEqual(draw.claim_state, "reserved")
        self.assertFalse(draw.sudo().claim_token)
        self.assertEqual(draw.claim_link_state, "used")
        self.assertFalse(self.env["event.raffle.draw"]._claim_link_find(token))

    def test_decline_through_the_link(self):
        participant = self._participant("Rae")
        draw = self._draw(participant)
        token = self._send(draw)
        found = self.env["event.raffle.draw"]._claim_link_find(token)
        with self.assertRaisesRegex(UserError, "why"):
            found._claim_link_decline("   ")
        found._claim_link_decline("I cannot come back for it")
        self.assertEqual(draw.claim_state, "declined")
        self.assertEqual(draw.decline_comment, "I cannot come back for it")
        self.assertEqual(draw.claim_link_state, "used")
        self.assertFalse(draw.sudo().claim_token)
        bodies = self._channel_bodies()
        self.assertEqual(len(bodies), 1)
        self.assertIn("I cannot come back for it", bodies[0])
        with self.assertRaises(UserError):
            found._claim_link_decline("Twice")
        # No cart: the log names no prize.
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "declined")
        self.assertFalse(log.product_id)
        self.assertFalse(log.sale_order_id)
        self.assertEqual(log.comment, "I cannot come back for it")

    # Claim log

    def test_link_decline_logs_the_prize_of_the_cart(self):
        """The log reads the cart before the decline cancels it."""
        participant = self._participant("Rex")
        draw = self._draw(participant)
        token = self._send(draw)
        cart = self._claim_cart(participant, draw)
        found = self.env["event.raffle.draw"]._claim_link_find(token)
        found._claim_link_decline("Changed my mind")
        self.assertEqual(cart.state, "cancel")
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "declined")
        self.assertEqual(log.product_id, self.prize)
        self.assertEqual(log.sale_order_id, cart)
        self.assertEqual(log.comment, "Changed my mind")

    def test_expiry_logs_the_prize_of_the_last_cart(self):
        """The most recent draft cart that holds a prize names it; a cart
        cancelled before the expiry is not read."""
        other = self._prize("Scarf", price=15.0, qty=2)
        participant = self._participant("Sol")
        draw = self._draw(participant)
        self._send(draw)
        first = self._claim_cart(participant, draw)
        first.order_line.product_id = other
        first.with_context(disable_cancel_warning=True).action_cancel()
        cart = self._claim_cart(participant, draw)
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertEqual(draw.claim_state, "expired")
        self.assertEqual(cart.state, "cancel")
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "expired")
        self.assertEqual(log.product_id, self.prize)
        self.assertEqual(log.sale_order_id, cart)
        self.assertFalse(log.comment)

    def test_expiry_without_a_cart_logs_no_prize(self):
        draw = self._draw(self._participant("Tia"))
        self._send(draw)
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "expired")
        self.assertFalse(log.product_id)
        self.assertFalse(log.sale_order_id)

    def test_prize_removed_from_the_cart_is_not_logged(self):
        """A prize added, then removed before the expiry, was not chosen."""
        participant = self._participant("Uma")
        draw = self._draw(participant)
        self._send(draw)
        cart = self._claim_cart(participant, draw)
        cart.order_line.unlink()
        self._expire(draw)
        self.env["event.raffle.draw"]._cron_claim_link_expire()
        self.assertEqual(cart.state, "cancel")
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "expired")
        self.assertFalse(log.product_id)

    # Claim cart confirmation

    def test_confirming_a_claim_cart_runs_the_claim(self):
        participant = self._participant("Sol")
        draw = self._draw(participant)
        self._send(draw)
        cart = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        other = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        self.assertEqual(cart.order_line.discount, 100.0)
        self.assertEqual(cart.amount_total, 0.0)
        cart.action_confirm()
        self.assertEqual(cart.state, "sale")
        self.assertEqual(draw.prize_order_id, cart)
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(draw.prize_value, 20.0)
        self.assertEqual(draw.claim_link_state, "used")
        self.assertEqual(other.state, "cancel")
        self.assertEqual(cart.picking_ids.move_ids.state, "assigned")

    def test_confirming_a_claim_cart_checks_the_rules(self):
        participant = self._participant("Tao")
        draw = self._draw(participant)
        self._send(draw)
        gone = self._prize("Gone", qty=0)
        cart = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "order_line": [Command.create({"product_id": gone.id})],
            }
        )
        with self.assertRaisesRegex(UserError, "no unit left"):
            cart.action_confirm()
        self.assertEqual(draw.claim_state, "none")

    def _claim_cart(self, participant, draw):
        return self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "website_id": self.env["website"].browse(1).id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )

    def test_deleting_a_draw_or_its_raffle_cancels_the_claim_carts(self):
        participant = self._participant("Vic")
        draw = self._draw(participant)
        self._send(draw)
        cart = self._claim_cart(participant, draw)
        draw.unlink()
        self.assertEqual(cart.state, "cancel")
        # The draws of a deleted raffle go with it, past their own hooks.
        raffle = self.env["event.raffle"].create(
            {"name": "Evening", "event_id": self.event.id}
        )
        other = self.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": "Wes",
                "email": "wes@example.com",
                "partner_id": participant.partner_id.id,
            }
        )
        draw = self._draw(other)
        cart = self._claim_cart(other, draw)
        raffle.unlink()
        self.assertFalse(draw.exists())
        self.assertEqual(cart.state, "cancel")

    def test_deleting_an_event_cancels_the_claim_carts_of_its_raffles(self):
        """The raffles of a deleted event go with it in the database, past
        their own hooks: the event cancels their claim carts."""
        participant = self._participant("Yan")
        event = self.env["event.event"].create(
            {
                "name": "Other Day",
                "date_begin": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(hours=8),
            }
        )
        raffle = self.env["event.raffle"].create(
            {"name": "Night", "event_id": event.id}
        )
        other = self.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": "Yan",
                "email": "yan@example.com",
                "partner_id": participant.partner_id.id,
            }
        )
        draw = self._draw(other)
        cart = self._claim_cart(other, draw)
        event.unlink()
        self.assertFalse(draw.exists())
        self.assertEqual(cart.state, "cancel")
        self.assertFalse(cart.raffle_draw_id)

    def test_website_order_without_draw_refuses_a_prize(self):
        participant = self._participant("Xia")
        order = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "website_id": self.env["website"].browse(1).id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        with self.assertRaisesRegex(UserError, "link of its draw only"):
            order.action_confirm()
        self.assertEqual(order.state, "draft")
        self.assertEqual(self.prize.raffle_qty_reserved, 0.0)

    def test_prize_carrier_is_offered_to_claim_carts_only(self):
        carrier = self.env.ref(
            "event_raffle_prize_claim.carrier_prize_handover"
        )
        participant = self._participant("Uma")
        draw = self._draw(participant)
        cart = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        ordinary = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "order_line": [Command.create({"product_id": self.prize.id})],
            }
        )
        self.assertEqual(cart._get_delivery_methods(), carrier)
        self.assertNotIn(carrier, ordinary._get_delivery_methods())
        in_store = self.env.ref(
            "website_sale_collect.carrier_pick_up_in_store",
            raise_if_not_found=False,
        )
        if in_store:
            # Click and Collect installed: its pick-up stays off the claim
            # carts, which keep the free prize handover only.
            in_store.write(
                {
                    "warehouse_ids": [Command.set(self.warehouse.ids)],
                    "is_published": True,
                }
            )
            self.assertEqual(cart._get_delivery_methods(), carrier)
            self.assertIn(in_store, ordinary._get_delivery_methods())

    def test_sponsor_link_is_kept_for_web_addresses_only(self):
        Template = self.env["product.template"]
        self.assertEqual(
            Template._raffle_safe_url("sponsor.example.org"),
            "https://sponsor.example.org",
        )
        self.assertEqual(
            Template._raffle_safe_url("http://sponsor.example.org/a"),
            "http://sponsor.example.org/a",
        )
        for value in ("javascript:alert(1)", "ftp://x.example.org", "", None):
            self.assertFalse(Template._raffle_safe_url(value), value)
        template = self.prize.product_tmpl_id
        self.assertEqual(template.raffle_sponsor_name, "Sponsor Example")
        self.assertEqual(
            template.raffle_sponsor_url, "https://sponsor.example.org"
        )

    # Token categories

    def test_link_lasts_the_validity_of_the_draw_category(self):
        self.band_a.claim_delay_minutes = 10
        participant = self._participant("Abi")
        draw = self._draw(participant, band_id=self.band_a.id)
        self._send(draw)
        delay = (draw.claim_deadline - draw.create_date).total_seconds()
        self.assertAlmostEqual(delay, 10 * 60, delta=120)
        body = draw.notification_ids.body
        self.assertIn("(Group A)", body)
        self.assertIn("10 minutes", body)
        notes = " ".join(draw.message_ids.mapped("body"))
        self.assertIn("valid 10 minutes", notes)
        values = draw._claim_banner_values()
        self.assertEqual(values["token_label"], "Group A")
        self.assertEqual(values["delay_minutes"], 10)
        # Without a category, the raffle's own validity applies.
        self.raffle.claim_delay_minutes = 20
        other = self._draw(self._participant("Bram"))
        self._send(other)
        delay = (other.claim_deadline - other.create_date).total_seconds()
        self.assertAlmostEqual(delay, 20 * 60, delta=120)
        self.assertEqual(
            other._claim_banner_values()["token_label"], "1 token"
        )

    # Member sales

    def test_sponsored_prize_never_sells_beyond_its_stock(self):
        template = self.prize.product_tmpl_id
        self.assertFalse(template.allow_out_of_stock_order)
        template.allow_out_of_stock_order = True
        self.assertFalse(template.allow_out_of_stock_order)
        ordinary = self.env["product.template"].create(
            {"name": "Ordinary", "type": "consu", "is_storable": True}
        )
        self.assertTrue(ordinary.allow_out_of_stock_order)
        ordinary.is_raffle_prize = True
        self.assertFalse(ordinary.allow_out_of_stock_order)

    def _website_order(self, product, partner=None):
        partner = partner or self.env["res.partner"].create(
            {"name": "Member", "email": "member@example.com"}
        )
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "website_id": self.env["website"].browse(1).id,
                "order_line": [Command.create({"product_id": product.id})],
            }
        )

    def test_website_order_buys_a_prize_sold_to_members_only(self):
        member = self._prize("Sold Cap", qty=2, raffle_member_sale_ok=True)
        winner = self._participant("Cora")
        draw = self._draw(winner)
        order = self._website_order(member, partner=winner.partner_id)
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertFalse(order.raffle_draw_id)
        self.assertEqual(order.order_line.raffle_prize_sale_type, "purchase")
        self.assertEqual(draw.claim_state, "none")
        self.assertEqual(winner._prize_claim_counts()[winner.id], 0)
        token_only = self._website_order(self.prize)
        with self.assertRaisesRegex(ValidationError, "cannot be bought"):
            token_only._check_cart_is_ready_to_be_paid()
        with self.assertRaisesRegex(UserError, "link of its draw only"):
            token_only.action_confirm()
        # Closed window: the member cart can no longer be paid.
        self._set_shop_window(is_open=False)
        late = self._website_order(member)
        with self.assertRaisesRegex(ValidationError, "cannot be bought"):
            late._check_cart_is_ready_to_be_paid()

    def test_shop_window_follows_the_switch_and_the_date(self):
        Config = self.env["event.raffle.config"]
        self.assertTrue(Config._sponsored_shop_is_open())
        future = fields.Datetime.now() + timedelta(hours=1)
        past = fields.Datetime.now() - timedelta(minutes=1)
        self._set_shop_window(is_open=True, close_date=future)
        self.assertTrue(Config._sponsored_shop_is_open())
        self._set_shop_window(is_open=True, close_date=past)
        self.assertFalse(Config._sponsored_shop_is_open())
        self._set_shop_window(is_open=False)
        self.assertFalse(Config._sponsored_shop_is_open())
        self._set_shop_window(is_open=False, close_date=future)
        self.assertFalse(Config._sponsored_shop_is_open())
        # Reopening: tick again, and move or clear the date.
        self._set_shop_window(is_open=True)
        self.assertTrue(Config._sponsored_shop_is_open())

    def test_event_manager_edits_the_shop_window(self):
        manager = new_test_user(
            self.env,
            login="claim_shop_manager",
            groups="base.group_user,event.group_event_manager",
        )
        config = self.env.ref("event_raffle.raffle_config_singleton")
        config.with_user(manager).sponsored_shop_open = False
        self.assertFalse(config.sponsored_shop_open)
        with self.assertRaises(AccessError):
            config.with_user(self.organizer).sponsored_shop_open = True
        arch = self.env["event.raffle.config"].get_views([(False, "form")])[
            "views"
        ]["form"]["arch"]
        self.assertIn('name="sponsored_shop_open"', arch)
        self.assertIn('name="sponsored_shop_close_date"', arch)

    # "Your prize" email

    def _claim_messages(self, order, text):
        return order.message_ids.filtered(lambda m: text in (m.subject or ""))

    def _own_prize_template(self):
        """Send this module's "Your prize" template, whatever template a
        module installed on top returns from the hook."""
        template = self.env.ref(
            "event_raffle_prize_claim.mail_template_prize_reserved"
        )
        patcher = patch.object(
            type(self.env["sale.order"]),
            "_raffle_prize_mail_template",
            lambda order: template,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return template

    def test_claim_sends_your_prize_and_purchase_the_order_email(self):
        self._own_prize_template().auto_delete = False
        participant = self._participant("Dina")
        draw = self._draw(participant)
        self._send(draw)
        cart = self._claim_cart(participant, draw)
        cart._validate_order()
        self.assertEqual(draw.claim_state, "reserved")
        mails = self._claim_messages(cart, "Your prize")
        self.assertEqual(len(mails), 1)
        self.assertEqual(mails.subject, "Your prize: Mug")
        body = str(mails.body)
        for text in (
            "Mug",
            "Sponsor Example",
            'href="https://sponsor.example.org"',
            "We will contact you about pick-up or delivery.",
        ):
            self.assertIn(text, body)
        for text in ("20.00", "$", cart.name):
            self.assertNotIn(text, body)
        self.assertIn(participant.partner_id, mails.partner_ids)
        self.assertFalse(self._claim_messages(cart, "(Ref"))
        sent = self.env["mail.mail"].search(
            [("mail_message_id", "=", mails.id)]
        )
        self.assertTrue(sent)
        html = " ".join(str(body) for body in sent.mapped("body_html"))
        self.assertIn("We will contact you", html)
        self.assertNotIn(cart.name, html)
        # A member purchase keeps the order confirmation of sale.
        member = self._prize("Sold Mug", qty=2, raffle_member_sale_ok=True)
        order = self._website_order(member)
        order._validate_order()
        self.assertEqual(order.state, "sale")
        self.assertTrue(self._claim_messages(order, order.name))
        self.assertFalse(self._claim_messages(order, "Your prize"))

    def test_your_prize_email_is_in_the_winner_language(self):
        self._own_prize_template()
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize", "event_raffle_prize_claim"],
            ["fr_CA"],
            overwrite=True,
        )
        silver = self.env.ref("event_raffle_prize.token_category_silver")
        silver.write({"active": True, "value_min": 1000, "value_max": 2000})
        prize = self._prize("Tent", price=1500.0, qty=1)
        self.assertEqual(prize.raffle_band_id, silver)
        participant = self._participant("Elie")
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant, band_id=silver.id)
        self._send(draw)
        cart = self.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "website_id": self.env["website"].browse(1).id,
                "order_line": [Command.create({"product_id": prize.id})],
            }
        )
        cart._validate_order()
        mails = self._claim_messages(cart, "Votre prix")
        self.assertEqual(len(mails), 1)
        body = str(mails.body)
        self.assertIn("Groupe de prix B", body)
        self.assertIn("Nous communiquerons avec vous", body)
        self.assertIn("(Groupe de prix B)", draw.notification_ids.body)
