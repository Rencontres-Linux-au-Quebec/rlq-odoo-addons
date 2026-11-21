# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import io
import json

from PIL import Image

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.event_raffle_prize_claim.models.event_raffle_draw_notification import (
    TOKEN_MASK,
)

from .common import HandoverDataMixin


@tagged("post_install", "-at_install")
class TestHandover(HandoverDataMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, mail_create_nolog=True)
        )
        cls._handover_setup()

    def _load_fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            [
                "event_raffle",
                "event_raffle_prize",
                "event_raffle_prize_claim",
                "event_raffle_prize_handover",
            ],
            ["fr_CA"],
            overwrite=True,
        )

    # Public name

    def test_public_name_is_shown_when_set_else_the_full_name(self):
        participant = self._participant("Nora Fullname")
        draw = self._draw(participant)
        partner = participant.partner_id
        self.assertEqual(draw._prize_public_name(), "Nora Fullname")
        partner._raffle_set_public_name("  Tux   Fan  ")
        self.assertEqual(partner.raffle_public_name, "Tux Fan")
        self.assertEqual(draw._prize_public_name(), "Tux Fan")
        self.assertEqual(draw.winner_public_name, "Tux Fan")
        partner._raffle_set_public_name("   ")
        self.assertFalse(partner.raffle_public_name)
        self.assertEqual(draw._prize_public_name(), "Nora Fullname")
        partner._raffle_set_public_name("x" * 100)
        self.assertEqual(len(partner.raffle_public_name), 64)
        # Once claimed, the contact of the prize order names the winner,
        # also when the participant is gone.
        draw._prize_claim(self.mug)
        partner._raffle_set_public_name("Penguin")
        participant.unlink()
        self.assertEqual(draw._prize_public_name(), "Penguin")

    def test_public_name_is_the_winner_not_the_booker(self):
        """The contact of a registration may be the person who booked it
        for the winner: the public pages name the winner, not the
        contact, until the contact has a public name."""
        booker = self.env["res.partner"].create(
            {"name": "Bruno Booker", "email": "bruno.booker@example.com"}
        )
        participant = self._participant("Ada Attendee")
        participant.partner_id = booker
        draw = self._draw(participant)
        self.assertEqual(draw._prize_public_name(), "Ada Attendee")
        draw._prize_claim(self.mug)
        self.assertEqual(draw.prize_order_id.partner_id, booker)
        self.assertEqual(draw._prize_public_name(), "Ada Attendee")
        dump = json.dumps(self.event._raffle_winners_data())
        self.assertIn("Ada Attendee", dump)
        self.assertNotIn("Bruno Booker", dump)
        # Without a name on the draw, the participant's name.
        draw.winner_name = False
        self.assertEqual(draw._prize_public_name(), "Ada Attendee")
        # The public name of the contact is still the winner's choice.
        booker._raffle_set_public_name("Quiet Penguin")
        self.assertEqual(draw._prize_public_name(), "Quiet Penguin")

    def test_event_user_sets_the_public_name_on_the_draw(self):
        participant = self._participant("Omar Organized")
        draw = self._draw(participant)
        draw.with_user(self.organizer).winner_public_name = "Omega"
        self.assertEqual(participant.partner_id.raffle_public_name, "Omega")
        portal = new_test_user(
            self.env, login="handover_portal_name", groups="base.group_portal"
        )
        with self.assertRaises(AccessError):
            draw.with_user(portal).winner_public_name = "Hacked"
        self.assertEqual(participant.partner_id.raffle_public_name, "Omega")

    # How the prize reaches the winner

    def test_handover_line_follows_the_prize_and_the_attendance(self):
        onsite = self._draw(self._participant("Ona Site"))
        remote = self._draw(self._participant("Rem Ote", attended=False))
        self.assertEqual(
            onsite._prize_handover_line(self.mug),
            "Pick up your prize at Table 7, hall B.",
        )
        self.assertEqual(
            remote._prize_handover_line(self.mug),
            "Your prize will be shipped to you.",
        )
        for draw in (onsite, remote):
            self.assertEqual(
                draw._prize_handover_line(self.ebook),
                "Your prize will be sent to you by email.",
            )
        self.raffle.prize_pickup_location = False
        self.assertEqual(
            onsite._prize_handover_line(self.mug),
            "Pick up your prize at the event.",
        )
        self._load_fr()
        fr = onsite.with_context(lang="fr_CA")
        self.raffle.prize_pickup_location = "Table 7, hall B"
        self.assertEqual(
            fr._prize_handover_line(self.mug),
            "Lieu de retrait de votre prix : Table 7, hall B.",
        )
        self.assertEqual(
            fr._prize_handover_line(self.ebook),
            "Votre prix vous sera envoyé par courriel.",
        )
        self.assertEqual(
            remote.with_context(lang="fr_CA")._prize_handover_line(self.mug),
            "Votre prix vous sera expédié.",
        )

    def test_your_prize_email_gives_the_pickup_location(self):
        participant = self._participant("Pia Pickup")
        draw = self._draw(participant)
        cart = self._cart(participant, draw, self.mug)
        cart._validate_order()
        self.assertEqual(draw.claim_state, "reserved")
        mails = self._mails(cart, "Your prize")
        self.assertEqual(len(mails), 1)
        body = str(mails.body)
        self.assertIn("Pick up your prize at Table 7, hall B.", body)
        self.assertNotIn("We will contact you", body)
        self.assertIn("Sponsor Example", body)
        self.assertNotIn("20.00", body)

    def test_your_prize_email_for_a_virtual_prize_and_a_shipped_one(self):
        remote = self._participant("Val Virtual", attended=False)
        draw = self._draw(remote)
        cart = self._cart(remote, draw, self.ebook)
        cart._validate_order()
        body = str(self._mails(cart, "Your prize").body)
        self.assertIn("Your prize will be sent to you by email.", body)
        other = self._participant("Sam Shipped", attended=False)
        draw = self._draw(other)
        cart = self._cart(other, draw, self.mug)
        cart._validate_order()
        body = str(self._mails(cart, "Your prize").body)
        self.assertIn("Your prize will be shipped to you.", body)

    def test_your_prize_email_in_french(self):
        self._load_fr()
        participant = self._participant("Fleur Francais")
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant)
        cart = self._cart(participant, draw, self.mug)
        cart._validate_order()
        mails = self._mails(cart, "Votre prix")
        self.assertEqual(len(mails), 1)
        body = str(mails.body)
        self.assertIn("Lieu de retrait de votre prix : Table 7, hall B.", body)
        self.assertIn("Félicitations", body)

    # Virtual prize

    def test_virtual_prize_is_sent_with_its_code_then_delivered(self):
        participant = self._participant("Vic Virtual", attended=False)
        draw = self._draw(participant)
        draw._prize_claim(self.ebook)
        self.assertTrue(draw.prize_virtual)
        before = self.ebook.qty_available
        wizard = (
            self.env["event.raffle.prize.virtual.wizard"]
            .with_user(self.organizer)
            .with_context(default_draw_id=draw.id)
            .create({"code": "INVENTED-CODE-42"})
        )
        self.assertIn("Open the reading app.", str(wizard.body))
        self.assertEqual(wizard.recipient, participant.email)
        wizard.action_send()
        self.assertEqual(draw.claim_state, "delivered")
        self.assertTrue(draw.prize_received)
        self.assertEqual(draw.prize_order_id.picking_ids.state, "done")
        self.assertEqual(self.ebook.qty_available, before - 1)
        mail = draw.notification_ids.mail_id
        self.assertEqual(len(mail), 1)
        self.assertIn("INVENTED-CODE-42", str(mail.body_html))
        self.assertIn("Open the reading app.", str(mail.body_html))
        self.assertIn(participant.partner_id, mail.recipient_ids)
        log = draw.notification_ids.body
        self.assertNotIn("INVENTED-CODE-42", log)
        self.assertIn(TOKEN_MASK, log)
        # Only a reserved virtual prize goes this way.
        with self.assertRaises(UserError):
            draw._prize_send_virtual("<p>Again</p>")
        physical = self._draw(self._participant("Phy Sical"))
        physical._prize_claim(self.mug)
        with self.assertRaises(UserError):
            physical._prize_send_virtual("<p>Not virtual</p>")

    def test_virtual_prize_message_is_in_the_winner_language(self):
        self._load_fr()
        self.ebook.product_tmpl_id.with_context(
            lang="fr_CA"
        ).raffle_virtual_instructions = "<p>Ouvrez l'application.</p>"
        participant = self._participant("Fanny Virtuelle", attended=False)
        participant.partner_id.lang = "fr_CA"
        draw = self._draw(participant)
        draw._prize_claim(self.ebook)
        wizard = (
            self.env["event.raffle.prize.virtual.wizard"]
            .with_context(default_draw_id=draw.id)
            .create({"code": "CODE-FR-7"})
        )
        self.assertIn("Ouvrez l'application.", str(wizard.body))
        wizard.action_send()
        mail = draw.notification_ids.mail_id
        self.assertIn("Votre code :", str(mail.body_html))
        self.assertIn("Vous avez gagné un prix", mail.subject)

    def test_virtual_prize_is_neither_shipped_nor_handed_over(self):
        participant = self._participant("Vera Virtual")
        draw = self._draw(participant)
        draw._prize_claim(self.ebook)
        self.assertEqual(draw._prize_delivery_mode(), "virtual")
        with self.assertRaises(UserError):
            draw._prize_ship("TRACK-1")
        self.assertNotIn(
            draw, self.env["event.raffle.draw"]._prize_handover_search()
        )

    def test_virtual_prize_ignores_the_region_of_a_delivery_address(self):
        """A prize sent by email ships nowhere: the region of the prize
        applies to the winner's contact only, whatever delivery address
        the order gets. A physical prize ships, and its delivery address
        must be in the region."""
        inside = self.env["res.country"].create(
            {"name": "Inlandia", "code": "XI"}
        )
        outside = self.env["res.country"].create(
            {"name": "Outlandia", "code": "XO"}
        )
        region = {"raffle_country_ids": [Command.set(inside.ids)]}
        self.ebook.product_tmpl_id.write(region)
        self.mug.product_tmpl_id.write(region)
        participant = self._participant(
            "Rhea Regional", attended=False, country_id=inside.id
        )
        self.env["res.partner"].create(
            {
                "name": "Rhea Abroad",
                "type": "delivery",
                "parent_id": participant.partner_id.id,
                "country_id": outside.id,
            }
        )
        draw = self._draw(participant)
        self.assertEqual(draw._prize_winner_mode(), "virtual")
        with self.assertRaisesRegex(UserError, "not offered in the winner"):
            draw._prize_claim(self.mug)
        order = draw._prize_claim(self.ebook)
        self.assertEqual(order.partner_shipping_id.country_id, outside)
        self.assertEqual(draw.claim_state, "reserved")

    # Shipping

    def test_shipped_then_received(self):
        self.env.ref(
            "event_raffle_prize_handover.mail_template_prize_shipped"
        ).auto_delete = False
        participant = self._participant("Sid Shipped", attended=False)
        draw = self._draw(participant)
        order = draw._prize_claim(self.mug)
        self.assertEqual(self.mug.raffle_qty_reserved, 1.0)
        with self.assertRaises(UserError):
            draw.with_user(self.organizer)._prize_ship("  ")
        with self.assertRaises(UserError):
            draw.with_user(self.organizer).action_prize_received()
        draw.with_user(self.organizer)._prize_ship("TRK-0001", "Postal")
        self.assertEqual(draw.claim_state, "shipped")
        self.assertEqual(draw.prize_tracking_ref, "TRK-0001")
        self.assertEqual(draw.prize_carrier_name, "Postal")
        self.assertTrue(draw.prize_shipped_date)
        self.assertFalse(draw.prize_received)
        self.assertEqual(order.picking_ids.state, "done")
        picking = order.picking_ids
        if "carrier_tracking_ref" in picking._fields:
            self.assertEqual(picking.carrier_tracking_ref, "TRK-0001")
        self.assertEqual(self.mug.raffle_qty_reserved, 0.0)
        self.assertEqual(self.mug.raffle_qty_delivered, 1.0)
        mails = self._mails(order, "Your prize is shipped")
        self.assertEqual(len(mails), 1)
        self.assertIn("TRK-0001", str(mails.body))
        self.assertIn("Postal", str(mails.body))
        self.assertIn(participant.partner_id, mails.partner_ids)
        # A shipped prize still counts toward the quota and blocks a
        # second claim on the draw; the hand-over path refuses it.
        self.assertTrue(participant._prize_quota_reached())
        with self.assertRaises(UserError):
            draw._prize_claim(self.mug)
        with self.assertRaises(UserError):
            draw.action_prize_deliver()
        # Its prize order belongs to it: the draw cannot be deleted.
        with self.assertRaisesRegex(UserError, "cannot be deleted"):
            draw.unlink()
        self.assertEqual(order.raffle_draw_id, draw)
        # Nor its raffle or its event, whose deletion would take it along.
        for record in (draw.raffle_id, draw.raffle_id.event_id):
            with self.assertRaisesRegex(UserError, "hold a prize"):
                record.unlink()
        self.assertEqual(draw.claim_state, "shipped")
        draw.with_user(self.organizer).action_prize_received()
        self.assertEqual(draw.claim_state, "delivered")
        self.assertTrue(draw.prize_received)
        self.assertTrue(draw.prize_received_date)
        self.assertTrue(participant._prize_quota_reached())

    def test_user_without_email_sends_ships_and_hands_over(self):
        """The virtual and shipping wizards, the hand-over with a photo and
        the reception work for a user without an email: their notes are
        posted by OdooBot with the user's name."""
        user = new_test_user(
            self.env,
            login="handover_no_email",
            groups="base.group_user,event.group_event_user",
            name="Noel Nomail",
        )
        user.partner_id.email = False
        virtual = self._draw(self._participant("Val Nomail", attended=False))
        virtual._prize_claim(self.ebook)
        self.env["event.raffle.prize.virtual.wizard"].with_user(
            user
        ).with_context(default_draw_id=virtual.id).create(
            {"code": "INVENTED-NO-MAIL"}
        ).action_send()
        shipped = self._draw(self._participant("Sam Nomail", attended=False))
        shipped._prize_claim(self.mug)
        self.env["event.raffle.prize.ship.wizard"].with_user(
            user
        ).with_context(default_draw_id=shipped.id).create(
            {"tracking_ref": "TRK-NO-MAIL"}
        ).action_ship()
        shipped.with_user(user).action_prize_received()
        onsite = self._draw(self._participant("Oli Nomail"))
        onsite._prize_claim(self.mug)
        onsite.with_user(user)._prize_hand_over(photo=self._image(20, 10))
        self.assertEqual(
            (virtual | shipped | onsite).mapped("claim_state"),
            ["delivered"] * 3,
        )
        expected = {
            virtual: ["Virtual prize", "handed over."],
            shipped: ["shipped, tracking number", "received by the winner."],
            onsite: ["handed over.", "Hand-over photo added."],
        }
        for draw, texts in expected.items():
            for text in texts:
                notes = draw.message_ids.filtered(
                    lambda m, text=text: text in str(m.body)
                )
                self.assertEqual(len(notes), 1, text)
                self.assertEqual(notes.author_id, self.odoobot)
                self.assertIn("(by Noel Nomail)", str(notes.body))
        photo_note = onsite.message_ids.filtered(
            lambda m: "Hand-over photo added." in str(m.body)
        )
        self.assertEqual(len(photo_note.attachment_ids), 1)

    def test_shipping_fields_are_written_by_the_buttons_only(self):
        draw = self._draw(self._participant("Wanda Write"))
        draw._prize_claim(self.mug)
        for vals in (
            {"prize_tracking_ref": "X"},
            {"claim_state": "shipped"},
            {"prize_handover_photo": base64.b64encode(self._image(2, 2))},
        ):
            with self.assertRaises(AccessError):
                draw.with_user(self.organizer).write(vals)

    def test_onsite_handover_keeps_the_phase_one_path(self):
        draw = self._draw(self._participant("Hugo Hand"))
        draw._prize_claim(self.mug)
        draw.with_user(self.organizer).action_prize_deliver()
        self.assertEqual(draw.claim_state, "delivered")

    # Hand-over screen

    def test_handover_search(self):
        Draw = self.env["event.raffle.draw"].with_user(self.organizer)
        alice = self._participant("Alice Onsite", email="alice@example.net")
        alice.partner_id.raffle_public_name = "Penguin Queen"
        bruno = self._participant("Bruno Onsite")
        remote = self._participant("Remy Remote", attended=False)
        draw_a = self._draw(alice)
        draw_b = self._draw(bruno)
        draw_r = self._draw(remote)
        draw_v = self._draw(self._participant("Vivi Virtual"))
        draw_n = self._draw(self._participant("Nina Nothing"))
        for draw, product in (
            (draw_a, self.mug),
            (draw_b, self.mug),
            (draw_r, self.mug),
            (draw_v, self.ebook),
        ):
            draw._prize_claim(product)
        listed = Draw._prize_handover_search()
        self.assertEqual(set(listed.ids), {draw_a.id, draw_b.id})
        self.assertNotIn(draw_n, listed)
        for term in ("alice", "Penguin", "alice@example.net", "ALICE ONSITE"):
            self.assertEqual(Draw._prize_handover_search(term), draw_a, term)
        for term in (str(draw_b.sequence), f"#{draw_b.sequence}"):
            self.assertIn(draw_b, Draw._prize_handover_search(term), term)
        self.assertFalse(Draw._prize_handover_search("nobody-here"))
        draw_a._prize_hand_over()
        self.assertEqual(Draw._prize_handover_search(), draw_b)

    def test_handover_photo_is_resized_and_kept_private(self):
        draw = self._draw(self._participant("Photo Phil"))
        draw._prize_claim(self.mug)
        draw.with_user(self.organizer)._prize_hand_over(
            photo=self._image(3000, 2000)
        )
        self.assertEqual(draw.claim_state, "delivered")
        image = Image.open(
            io.BytesIO(base64.b64decode(draw.prize_handover_photo))
        )
        self.assertEqual(image.size, (1920, 1280))
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "event.raffle.draw"),
                ("res_id", "=", draw.id),
            ]
        )
        self.assertTrue(attachments)
        self.assertFalse(any(attachments.mapped("public")))
        shown = attachments.filtered(lambda a: not a.res_field)
        self.assertEqual(len(shown), 1)
        self.assertEqual(Image.open(io.BytesIO(shown.raw)).size, (1920, 1280))

    def test_handover_refuses_a_file_that_is_not_an_image(self):
        draw = self._draw(self._participant("Tex Text"))
        draw._prize_claim(self.mug)
        with self.assertRaises(UserError):
            draw._prize_store_handover_photo(b"not an image at all")

    # Winners page data

    def test_winners_are_grouped_by_hour_in_the_event_time_zone(self):
        # India is 5 h 30 ahead of UTC: 14:20 and 14:40 UTC fall in the
        # same UTC hour but in two hours of the event.
        self.event.date_tz = "Asia/Kolkata"
        early = self._draw(self._participant("Early Bird"))
        late = self._draw(self._participant("Late Owl"))
        absent = self._draw(self._participant("Abs Ent"))
        declined = self._draw(self._participant("Dec Lined"))
        nothing = self._draw(self._participant("No Claim"))
        for draw in (early, late, absent, declined):
            draw._prize_claim(self.mug)
        declined._prize_decline("Not for me")
        absent.is_absent = True
        early.date = "2026-01-01 14:20:00"
        late.date = "2026-01-01 14:40:00"
        declined.date = nothing.date = "2026-01-01 13:00:00"
        late.partner_id.raffle_public_name = "Night Owl"
        data = self.event._raffle_winners_data()
        self.assertEqual(
            [group["key"] for group in data["groups"]],
            [
                "2026-01-01T20:00:00+05:30",
                "2026-01-01T19:00:00+05:30",
                "2026-01-01T18:00:00+05:30",
            ],
        )
        self.assertEqual(data["count"], 4)
        names = [g["winners"][0]["name"] for g in data["groups"][:2]]
        self.assertEqual(names, ["Night Owl", "Early Bird"])
        self.assertIn("8:00", data["groups"][0]["label"])
        winner = data["groups"][0]["winners"][0]
        self.assertEqual(
            set(winner),
            {
                "id",
                "name",
                "prize",
                "status",
                "sponsor",
                "sponsor_url",
                "category",
            },
        )
        self.assertEqual(winner["prize"], "Handover Mug")
        self.assertEqual(winner["status"], "chosen")
        self.assertEqual(winner["sponsor"], "Sponsor Example")
        self.assertEqual(winner["sponsor_url"], "https://sponsor.example.org")
        self.assertEqual(winner["category"], "Group A")
        listed = {w["id"] for g in data["groups"] for w in g["winners"]}
        self.assertNotIn(absent.id, listed)
        # Shipped and handed over prizes stay listed.
        remote = self._draw(self._participant("Ship Me", attended=False))
        remote._prize_claim(self.mug)
        remote._prize_ship("TRK-9")
        early._prize_hand_over()
        data = self.event._raffle_winners_data()
        listed = {w["id"] for g in data["groups"] for w in g["winners"]}
        self.assertEqual(
            listed, {early.id, late.id, remote.id, declined.id, nothing.id}
        )

    def _public_lines(self):
        data = self.event._raffle_winners_data()
        return {w["id"]: w for g in data["groups"] for w in g["winners"]}

    def test_winners_list_the_prize_to_choose_and_what_became_of_it(self):
        """A winner is listed as soon as drawn: the prize to choose in the
        token category of the draw, then the prize once chosen; a declined
        or expired claim stays listed with what became of it, and nothing
        of the claim itself."""
        open_claim = self._draw(
            self._participant("Open Claim"), band_id=self.band_a.id
        )
        open_claim._claim_link_issue()
        no_band = self._draw(self._participant("No Band"))
        declined = self._draw(self._participant("Link Decliner"))
        declined._claim_link_issue()
        declined._claim_link_decline("Too far to come back")
        expired = self._draw(self._participant("Late Chooser"))
        expired._claim_link_issue()
        self._expire(expired)
        expired._claim_link_expire()
        lapsed = self._draw(self._participant("Lapsed Link"))
        lapsed._claim_link_issue()
        self._expire(lapsed)
        absent = self._draw(self._participant("Away Winner"))
        absent.is_absent = True
        lines = self._public_lines()
        self.assertNotIn(absent.id, lines)
        line = lines[open_claim.id]
        self.assertEqual(line["name"], "Open Claim")
        self.assertEqual(line["prize"], "Group A, prize to choose")
        self.assertEqual(line["status"], "to_choose")
        self.assertEqual(
            (line["sponsor"], line["sponsor_url"], line["category"]),
            ("", "", ""),
        )
        self.assertEqual(lines[no_band.id]["prize"], "Prize to choose")
        self.assertEqual(
            (lines[declined.id]["prize"], lines[declined.id]["status"]),
            ("Prize declined", "declined"),
        )
        self.assertEqual(
            (lines[expired.id]["prize"], lines[expired.id]["status"]),
            ("No prize chosen", "expired"),
        )
        # A link past its deadline before the cron closes it.
        self.assertEqual(lines[lapsed.id]["status"], "expired")
        dump = json.dumps(lines)
        for text in ("Too far to come back", "@example.com", "token"):
            self.assertNotIn(text, dump)
        # The choice replaces the text with the prize and its sponsor.
        open_claim._prize_claim(self.mug)
        line = self._public_lines()[open_claim.id]
        self.assertEqual(line["prize"], "Handover Mug")
        self.assertEqual(line["status"], "chosen")
        self.assertEqual(line["sponsor"], "Sponsor Example")
        self.assertEqual(line["category"], "Group A")
        # A prize declined after it was reserved names no sponsor.
        open_claim._prize_decline("Changed my mind")
        line = self._public_lines()[open_claim.id]
        self.assertEqual(
            (line["prize"], line["status"], line["sponsor"]),
            ("Prize declined", "declined", ""),
        )

    def test_prize_typed_on_the_wheel_is_not_the_winners_choice(self):
        """A prize typed on the wheel of a draw whose link is issued says
        the prize is still to choose, then "No prize chosen" once the
        link lapses, before and after the cron closes it. A draw that
        never had a link shows the typed prize."""
        typed = self._draw(
            self._participant("Typed Prize"),
            band_id=self.band_a.id,
            prize="Grand prize",
        )
        typed._claim_link_issue()
        self.assertEqual(typed.claim_link_state, "open")
        line = self._public_lines()[typed.id]
        self.assertEqual(
            (line["prize"], line["status"], line["category"]),
            ("Group A, prize to choose", "to_choose", ""),
        )
        self._expire(typed)
        self.assertEqual(typed.claim_state, "none")
        lapsed = self._public_lines()[typed.id]
        typed._claim_link_expire()
        closed = self._public_lines()[typed.id]
        for line in (lapsed, closed):
            self.assertEqual(
                (line["prize"], line["status"]),
                ("No prize chosen", "expired"),
            )
        plain = self._draw(self._participant("No Link"), prize="Door prize")
        self.assertEqual(plain.claim_link_state, "none")
        line = self._public_lines()[plain.id]
        self.assertEqual(
            (line["prize"], line["status"]), ("Door prize", "chosen")
        )

    def test_winners_texts_in_french(self):
        self._load_fr()
        self.band_a.name = "Groupe de prix A"
        draws = [
            self._draw(self._participant(name), band_id=band.id)
            for name, band in (
                ("Ana Choisit", self.band_a),
                ("Bob Choisit", self.env["event.raffle.prize.band"]),
            )
        ]
        refused = self._draw(self._participant("Cleo Refuse"))
        refused._prize_claim(self.mug)
        refused._prize_decline("Non merci")
        late = self._draw(self._participant("Dan Tard"))
        late._claim_link_issue()
        self._expire(late)
        event = self.event.with_context(lang="fr_CA")
        data = event._raffle_winners_data()
        prizes = {
            w["id"]: w["prize"] for g in data["groups"] for w in g["winners"]
        }
        self.assertEqual(
            prizes[draws[0].id], "Groupe de prix A, prix à choisir"
        )
        self.assertEqual(prizes[draws[1].id], "Prix à choisir")
        self.assertEqual(prizes[refused.id], "Prix refusé")
        self.assertEqual(prizes[late.id], "Aucun prix choisi")

    def test_test_raffle_lists_its_chosen_prizes_only(self):
        self.raffle.is_test = True
        chosen = self._draw(self._participant("Rehearsal Chosen"))
        chosen._prize_claim(self.mug)
        waiting = self._draw(self._participant("Rehearsal Waiting"))
        lines = self._public_lines()
        self.assertIn(chosen.id, lines)
        self.assertNotIn(waiting.id, lines)
