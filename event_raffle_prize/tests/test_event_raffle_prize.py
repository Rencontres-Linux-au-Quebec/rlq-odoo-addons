# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from unittest.mock import patch

import psycopg2
from lxml import etree
from psycopg2.extras import Json

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.migration import load_script
from odoo.sql_db import Cursor
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger

from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG


class PrizeCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The catalogue and the bands start empty: demo data must not add
        # prizes to the lists nor catch a value before the test bands.
        cls.env["product.template"].search(
            [("is_raffle_prize", "=", True)]
        ).write({"is_raffle_prize": False})
        cls.env["event.raffle.prize.band"].search([]).write({"active": False})
        cls.band_a = cls.env["event.raffle.prize.band"].create(
            {"name": "A", "sequence": 1, "value_min": 0, "value_max": 49.99}
        )
        cls.band_b = cls.env["event.raffle.prize.band"].create(
            {"name": "B", "sequence": 2, "value_min": 50, "value_max": 999}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Prize Event",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        cls.other_event = cls.env["event.event"].create(
            {
                "name": "Other Event",
                "date_begin": "2026-02-01 09:00:00",
                "date_end": "2026-02-01 18:00:00",
            }
        )
        cls.ticket_std = cls.env["event.event.ticket"].create(
            {"name": "Standard", "event_id": cls.event.id}
        )
        cls.ticket_high = cls.env["event.event.ticket"].create(
            {"name": "Helper", "event_id": cls.event.id}
        )
        cls.raffle = cls.env["event.raffle"].create(
            {"name": "Morning", "event_id": cls.event.id}
        )
        cls.raffle_2 = cls.env["event.raffle"].create(
            {"name": "Afternoon", "event_id": cls.event.id}
        )
        cls.country_a = cls.env["res.country"].create(
            {"name": "Testland", "code": "ZT"}
        )
        cls.country_b = cls.env["res.country"].create(
            {"name": "Otherland", "code": "ZU"}
        )
        cls.state_a1 = cls.env["res.country.state"].create(
            {"name": "North", "code": "N", "country_id": cls.country_a.id}
        )
        cls.state_a2 = cls.env["res.country.state"].create(
            {"name": "South", "code": "S", "country_id": cls.country_a.id}
        )
        cls.warehouse = cls.env["event.raffle"]._prize_warehouse(
            cls.env.company
        )
        cls.sponsor = cls.env["res.partner"].create({"name": "Sponsor"})

    @classmethod
    def _prize(cls, name, price=20.0, qty=3.0, **vals):
        template = cls.env["product.template"].create(
            dict(
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                    "list_price": price,
                    "is_raffle_prize": True,
                    "raffle_sponsor_id": cls.sponsor.id,
                },
                **vals,
            )
        )
        product = template.product_variant_id
        if qty:
            cls.env["stock.quant"]._update_available_quantity(
                product, cls.warehouse.lot_stock_id, qty
            )
        return product

    @classmethod
    def _participant(
        cls,
        name,
        raffle=None,
        attended=False,
        ticket=None,
        country=None,
        state=None,
        email=None,
    ):
        raffle = raffle or cls.raffle
        email = email or f"{name.lower()}@example.com"
        partner = cls.env["res.partner"].create(
            {
                "name": name,
                "email": email,
                "country_id": country.id if country else False,
                "state_id": state.id if state else False,
            }
        )
        registration = cls.env["event.registration"].create(
            {
                "event_id": raffle.event_id.id,
                "partner_id": partner.id,
                "name": name,
                "email": email,
                "event_ticket_id": ticket.id if ticket else False,
            }
        )
        if attended:
            registration.action_set_done()
        return cls.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": name,
                "email": email,
                "partner_id": partner.id,
                "registration_id": registration.id,
                "source": "registration",
            }
        )

    @classmethod
    def _draw(cls, participant, **vals):
        raffle = participant.raffle_id
        return cls.env["event.raffle.draw"].create(
            dict(
                {
                    "raffle_id": raffle.id,
                    "sequence": len(raffle.draw_ids) + 1,
                    "winner_participant_id": participant.id,
                    "winner_name": participant.name,
                    "winner_email": participant.email,
                },
                **vals,
            )
        )

    def _free(self, product):
        product.invalidate_recordset(["raffle_qty_free"])
        return product.raffle_qty_free


@tagged("post_install", "-at_install")
class TestEventRafflePrize(PrizeCommon):
    # Band of a product

    def test_band_follows_the_price_and_can_be_overridden(self):
        product = self._prize("Mug", price=20.0)
        template = product.product_tmpl_id
        self.assertEqual(template.raffle_band_id, self.band_a)
        template.list_price = 75.0
        self.assertEqual(template.raffle_band_id, self.band_b)
        template.raffle_band_id = self.band_a
        self.assertEqual(template.raffle_band_id, self.band_a)
        template.list_price = 500.0
        self.assertEqual(template.raffle_band_id, self.band_b)

    def test_band_outside_every_range_is_empty(self):
        product = self._prize("Car", price=5000.0)
        self.assertFalse(product.raffle_band_id)

    def test_prize_must_track_inventory(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                {"name": "Service", "type": "service", "is_raffle_prize": True}
            )

    # Attendance mode

    def test_attendance_mode_follows_the_check_in(self):
        onsite = self._participant("Onsite", attended=True)
        remote = self._participant("Remote")
        guest = self.env["event.raffle.participant"].create(
            {"raffle_id": self.raffle.id, "name": "Guest"}
        )
        self.assertEqual(onsite.attendance_mode, "onsite")
        self.assertEqual(remote.attendance_mode, "virtual")
        self.assertEqual(guest.attendance_mode, "virtual")
        remote.registration_id.action_set_done()
        self.assertEqual(remote.attendance_mode, "onsite")
        draw = self._draw(remote)
        self.assertEqual(draw.attendance_mode, "onsite")

    # Rules of the prize list

    def test_attendance_filter(self):
        onsite_prize = self._prize("Onsite only", raffle_attendance="onsite")
        virtual_prize = self._prize(
            "Virtual only", raffle_attendance="virtual"
        )
        both_prize = self._prize("Both")
        onsite_draw = self._draw(self._participant("Ona", attended=True))
        virtual_draw = self._draw(self._participant("Vic"))
        self.assertEqual(
            onsite_draw._prize_allowed_products(), onsite_prize | both_prize
        )
        self.assertEqual(
            virtual_draw._prize_allowed_products(), virtual_prize | both_prize
        )

    def test_region_filter_for_virtual_winners(self):
        prize_country = self._prize(
            "Country", raffle_country_ids=[Command.set(self.country_a.ids)]
        )
        prize_state = self._prize(
            "State", raffle_state_ids=[Command.set(self.state_a1.ids)]
        )
        prize_mixed = self._prize(
            "Mixed",
            raffle_country_ids=[
                Command.set((self.country_a | self.country_b).ids)
            ],
            raffle_state_ids=[Command.set(self.state_a1.ids)],
        )
        everywhere = self._prize("Everywhere")
        north = self._draw(
            self._participant(
                "Nora", country=self.country_a, state=self.state_a1
            )
        )
        south = self._draw(
            self._participant(
                "Sam", country=self.country_a, state=self.state_a2
            )
        )
        abroad = self._draw(self._participant("Abe", country=self.country_b))
        nowhere = self._draw(self._participant("Nadia"))
        self.assertEqual(
            north._prize_allowed_products(),
            prize_country | prize_state | prize_mixed | everywhere,
        )
        # Country A has a state listed on "Mixed": only that state is open.
        self.assertEqual(
            south._prize_allowed_products(), prize_country | everywhere
        )
        self.assertEqual(
            abroad._prize_allowed_products(), prize_mixed | everywhere
        )
        self.assertEqual(nowhere._prize_allowed_products(), everywhere)
        # On-site winners pick the prize up at the event: no region rule.
        onsite = self._draw(
            self._participant("Olga", attended=True, country=self.country_b)
        )
        self.assertIn(prize_state, onsite._prize_allowed_products())

    def test_closing_prize_only_on_a_closing_draw(self):
        closing = self._prize("Closing", raffle_closing_prize=True)
        regular = self._prize("Regular")
        draw = self._draw(self._participant("Cleo"))
        self.assertEqual(draw._prize_allowed_products(), regular)
        draw.is_closing_draw = True
        self.assertEqual(draw._prize_allowed_products(), closing | regular)
        draw.is_closing_draw = False
        with self.assertRaisesRegex(UserError, "closing prize"):
            draw._prize_claim(closing)

    def test_event_filter(self):
        mine = self._prize(
            "Mine", raffle_event_ids=[Command.set(self.event.ids)]
        )
        other = self._prize(
            "Other", raffle_event_ids=[Command.set(self.other_event.ids)]
        )
        anyone = self._prize("Any")
        draw = self._draw(self._participant("Eve"))
        self.assertEqual(draw._prize_allowed_products(), mine | anyone)
        with self.assertRaisesRegex(UserError, "not a prize of this event"):
            draw._prize_claim(other)

    def test_band_filter(self):
        cheap = self._prize("Cheap", price=10.0)
        dear = self._prize("Dear", price=100.0)
        draw = self._draw(self._participant("Bea"))
        self.assertEqual(draw._prize_allowed_products(), cheap | dear)
        draw.band_id = self.band_b
        self.assertEqual(draw._prize_allowed_products(), dear)
        with self.assertRaisesRegex(UserError, "not in the token category"):
            draw._prize_claim(cheap)

    def test_out_of_stock_filter(self):
        empty = self._prize("Empty", qty=0)
        stocked = self._prize("Stocked", qty=1)
        draw = self._draw(self._participant("Ola"))
        self.assertEqual(draw._prize_allowed_products(), stocked)
        with self.assertRaisesRegex(UserError, "no unit left"):
            draw._prize_claim(empty)

    # Quotas

    def test_default_quota_across_the_raffles_of_the_event(self):
        prize = self._prize("Pen", qty=5)
        first = self._participant("Quinn")
        # Same person (same email) in the second raffle of the event.
        second = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle_2.id,
                "name": "Quinn again",
                "email": "QUINN@example.com",
            }
        )
        other = self._participant("Rita", raffle=self.raffle_2)
        self.assertIn(second, self.raffle_2._eligible_participants())
        self._draw(first)._prize_claim(prize)
        # At quota: out of the wheel of both raffles, and no prize offered.
        self.assertNotIn(second, self.raffle_2._eligible_participants())
        self.assertNotIn(first, self.raffle._eligible_participants())
        self.assertIn(other, self.raffle_2._eligible_participants())
        draw = self._draw(second)
        self.assertFalse(draw._prize_allowed_products())
        with self.assertRaisesRegex(UserError, "quota"):
            draw._prize_claim(prize)
        self.assertNotIn(
            second.id,
            [w["id"] for w in self.raffle_2.get_wheel_data()["eligible"]],
        )

    def test_high_quota_ticket(self):
        prize = self._prize("Sticker", qty=5)
        self.raffle.high_quota_ticket_ids = self.ticket_high
        helper = self._participant("Hal", ticket=self.ticket_high)
        standard = self._participant("Stan", ticket=self.ticket_std)
        self.assertEqual(helper._prize_quota(), 2)
        self.assertEqual(standard._prize_quota(), 1)
        self._draw(helper)._prize_claim(prize)
        self.assertIn(helper, self.raffle._eligible_participants())
        self._draw(helper)._prize_claim(prize)
        self.assertNotIn(helper, self.raffle._eligible_participants())
        with self.assertRaisesRegex(UserError, "quota"):
            self._draw(helper)._prize_claim(prize)
        self._draw(standard)._prize_claim(prize)
        self.assertNotIn(standard, self.raffle._eligible_participants())

    def test_declined_prize_frees_the_quota(self):
        prize = self._prize("Cap", qty=5)
        winner = self._participant("Dora")
        draw = self._draw(winner)
        draw._prize_claim(prize)
        self.assertNotIn(winner, self.raffle._eligible_participants())
        draw._prize_decline("Already has one")
        self.assertIn(winner, self.raffle._eligible_participants())

    def test_quota_leaves_remove_winner_alone(self):
        # Without any claim, the quota filters nobody: a winner stays on the
        # wheel until the next draw and the pool is event_raffle's own.
        self._participant("Ann")
        self._participant("Ben")
        res = self.raffle.action_draw_next()
        winner = self.env["event.raffle.participant"].browse(
            res["winner"]["id"]
        )
        self.assertIn(winner, self.raffle._eligible_participants())
        self.raffle.action_draw_next()
        self.assertTrue(winner.won)

    # Claim, decline, hand over

    def test_claim_reserves_one_unit_at_no_charge(self):
        prize = self._prize("Hoodie", price=40.0, qty=2)
        draw = self._draw(self._participant("Cara"))
        order = draw._prize_claim(prize)
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.partner_id, draw.partner_id)
        self.assertEqual(order.warehouse_id, self.warehouse)
        self.assertEqual(order.amount_total, 0.0)
        self.assertEqual(order.order_line.price_unit, 40.0)
        self.assertEqual(order.order_line.discount, 100.0)
        self.assertEqual(order.picking_ids.move_ids.state, "assigned")
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(draw.prize_product_id, prize)
        self.assertEqual(draw.prize_order_id, order)
        self.assertEqual(draw.prize_value, 40.0)
        self.assertEqual(draw.prize, "Hoodie")
        self.assertTrue(draw.claim_date)
        self.assertEqual(self._free(prize), 1.0)
        self.assertEqual(prize.raffle_qty_reserved, 1.0)
        with self.assertRaisesRegex(UserError, "already has a prize"):
            draw._prize_claim(prize)

    def _draft_order(self, draw, *products, partner=None):
        return self.env["sale.order"].create(
            {
                "partner_id": (partner or draw.partner_id).id,
                "raffle_draw_id": draw.id,
                "order_line": [
                    Command.create({"product_id": p.id, "product_uom_qty": 1})
                    for p in products
                ],
            }
        )

    def test_claim_confirms_a_given_draft_order(self):
        prize = self._prize("Scarf", price=30.0, qty=1)
        draw = self._draw(self._participant("Iris"))
        stranger = self.env["res.partner"].create({"name": "Stranger"})
        draft = self._draft_order(draw, prize, partner=stranger)
        order = draw._prize_claim(prize, order=draft)
        self.assertEqual(order, draft)
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.partner_id, draw.partner_id)
        self.assertEqual(order.warehouse_id, self.warehouse)
        self.assertEqual(order.amount_total, 0.0)
        self.assertEqual(order.order_line.price_unit, 30.0)
        self.assertEqual(order.order_line.discount, 100.0)
        self.assertEqual(draw.prize_order_id, order)
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(draw.prize_value, 30.0)
        self.assertEqual(self._free(prize), 0.0)

    def test_claim_refuses_a_given_order_that_does_not_fit(self):
        prize = self._prize("Cap", qty=2)
        other = self._prize("Pin", qty=2)
        draw = self._draw(self._participant("Joel"))
        other_draw = self._draw(self._participant("Kara"))
        for draft in (
            self._draft_order(other_draw, prize),
            self._draft_order(draw, prize, other),
            self._draft_order(draw, other),
        ):
            with self.assertRaisesRegex(UserError, "cannot hold the prize"):
                draw._prize_claim(prize, order=draft)
            self.assertEqual(draft.state, "draft")
        self.assertEqual(draw.claim_state, "none")
        self.assertEqual(self._free(prize), 2.0)

    def test_claim_with_a_given_order_checks_the_rules(self):
        prize = self._prize("Last", qty=0)
        draw = self._draw(self._participant("Lou"))
        draft = self._draft_order(draw, prize)
        with self.assertRaisesRegex(UserError, "no unit left"):
            draw._prize_claim(prize, order=draft)
        self.assertEqual(draft.state, "draft")

    def test_claim_checks_the_region_of_the_shipping_address(self):
        """A virtual winner of the prize's region who ships it elsewhere is
        refused, whether the order is given or the claim creates it."""
        prize = self._prize(
            "Regional",
            qty=2,
            raffle_country_ids=[Command.set(self.country_a.ids)],
        )
        draw = self._draw(self._participant("Rita", country=self.country_a))
        self.assertIn(prize, draw._prize_allowed_products())
        partner = draw.partner_id
        abroad = self.env["res.partner"].create(
            {
                "name": "Rita Abroad",
                "type": "delivery",
                "parent_id": partner.id,
                "country_id": self.country_b.id,
            }
        )
        draft = self._draft_order(draw, prize)
        draft.partner_shipping_id = abroad
        with self.assertRaisesRegex(UserError, "not offered in the winner"):
            draw._prize_claim(prize, order=draft)
        self.assertEqual(draft.state, "draft")
        self.assertEqual(draw.claim_state, "none")
        # The order a claim creates ships to the winner's delivery address.
        with self.assertRaisesRegex(UserError, "not offered in the winner"):
            draw._prize_claim(prize)
        self.assertEqual(draw.claim_state, "none")
        draft.partner_shipping_id = partner
        self.assertEqual(draw._prize_claim(prize, order=draft), draft)
        self.assertEqual(draw.claim_state, "reserved")

    def test_claim_creates_and_links_the_missing_contact(self):
        prize = self._prize("Bag")
        guest = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle.id,
                "name": "Gus",
                "email": "gus@example.com",
            }
        )
        draw = self._draw(guest)
        order = draw._prize_claim(prize)
        self.assertTrue(guest.partner_id)
        self.assertEqual(guest.partner_id.email, "gus@example.com")
        self.assertEqual(draw.partner_id, guest.partner_id)
        self.assertEqual(order.partner_id, guest.partner_id)

    def test_decline_puts_the_unit_back_in_stock(self):
        prize = self._prize("Lamp", qty=1)
        draw = self._draw(self._participant("Dina"))
        order = draw._prize_claim(prize)
        self.assertEqual(self._free(prize), 0.0)
        with self.assertRaisesRegex(UserError, "why"):
            draw._prize_decline("  ")
        draw._prize_decline("Cannot carry it")
        self.assertEqual(order.state, "cancel")
        self.assertEqual(draw.claim_state, "declined")
        self.assertEqual(draw.decline_comment, "Cannot carry it")
        self.assertFalse(draw.prize)
        self.assertEqual(self._free(prize), 1.0)
        self.assertEqual(prize.raffle_qty_reserved, 0.0)
        # The unit can go to the next winner at once.
        other = self._draw(self._participant("Omar"))
        other._prize_claim(prize)
        self.assertEqual(other.claim_state, "reserved")

    def test_decline_wizard_needs_a_reason(self):
        prize = self._prize("Book")
        draw = self._draw(self._participant("Nell"))
        draw._prize_claim(prize)
        wizard = self.env["event.raffle.prize.decline.wizard"].create(
            {"draw_id": draw.id, "comment": "Has it"}
        )
        wizard.action_decline()
        self.assertEqual(draw.claim_state, "declined")

    # Claim log

    def test_decline_writes_the_claim_log(self):
        prize = self._prize("Kettle", qty=2)
        draw = self._draw(self._participant("Lena"))
        user = new_test_user(
            self.env,
            login="claim_log_user",
            groups="base.group_user,event.group_event_user",
            email="claim.log.user@example.com",
        )
        order = draw.with_user(user)._prize_claim(prize)
        self.assertFalse(draw.claim_log_ids)
        draw.with_user(user)._prize_decline("Too heavy to carry")
        log = draw.claim_log_ids
        self.assertEqual(len(log), 1)
        self.assertEqual(log.kind, "declined")
        self.assertEqual(log.product_id, prize)
        self.assertEqual(log.sale_order_id, order)
        self.assertEqual(log.comment, "Too heavy to carry")
        self.assertEqual(log.user_id, user)
        self.assertTrue(log.date)
        # The event user reads the log, and nobody writes it by hand.
        Log = self.env["event.raffle.prize.claim.log"].with_user(user)
        self.assertEqual(Log.search([("draw_id", "=", draw.id)]), log)
        with self.assertRaises(AccessError):
            Log.create({"draw_id": draw.id, "kind": "expired"})
        with self.assertRaises(AccessError):
            log.with_user(user).write({"comment": "Changed"})
        with self.assertRaises(AccessError):
            log.with_user(user).unlink()

    def test_each_decline_of_a_draw_is_logged(self):
        """A draw that declines, claims again and declines again keeps
        both declines, while the quota counts the held claims only."""
        lamp = self._prize("Desk Lamp", qty=2)
        mug = self._prize("Tea Mug", qty=2)
        winner = self._participant("Mona")
        draw = self._draw(winner)
        draw._prize_claim(lamp)
        draw._prize_decline("Prefers another one")
        self.assertEqual(winner._prize_claim_counts()[winner.id], 0)
        draw._prize_claim(mug)
        self.assertEqual(winner._prize_claim_counts()[winner.id], 1)
        draw._prize_decline("Leaves early")
        self.assertEqual(winner._prize_claim_counts()[winner.id], 0)
        self.assertIn(winner, self.raffle._eligible_participants())
        logs = draw.claim_log_ids.sorted("id")
        self.assertEqual(logs.mapped("kind"), ["declined", "declined"])
        self.assertEqual(logs.product_id.ids, [lamp.id, mug.id])
        self.assertEqual(
            logs.mapped("comment"), ["Prefers another one", "Leaves early"]
        )
        # A write that keeps the state logs nothing more.
        draw.sudo().write({"claim_state": "declined"})
        self.assertEqual(len(draw.claim_log_ids), 2)

    def test_claim_log_outlives_its_draw_raffle_and_event(self):
        """The line copies what it reads of its draw, so deleting the
        draw, then its raffle, then its event keeps it."""
        prize = self._prize("Teapot", qty=2)
        draw = self._draw(self._participant("Lise"), band_id=self.band_a.id)
        draw._prize_claim(prize)
        draw._prize_decline("Too fragile")
        log = draw.claim_log_ids
        self.assertEqual(log.draw_name, "Draw #1 - Lise")
        self.assertEqual(log.display_name, "Draw #1 - Lise")
        self.assertEqual(log.draw_date, draw.date)
        self.assertEqual(log.raffle_id, self.raffle)
        self.assertEqual(log.event_id, self.event)
        self.assertEqual(log.band_id, self.band_a)
        self.assertEqual(log.company_id, self.raffle.company_id)
        date = draw.date
        draw.unlink()
        self.assertTrue(log.exists())
        self.assertFalse(log.draw_id)
        self.assertEqual(log.draw_name, "Draw #1 - Lise")
        self.assertEqual(log.draw_date, date)
        self.assertEqual(log.product_id, prize)
        self.assertEqual(log.comment, "Too fragile")
        Log = self.env["event.raffle.prize.claim.log"]
        self.assertEqual(Log.search([("draw_id", "=", False)]), log)
        self.raffle.unlink()
        self.assertTrue(log.exists())
        self.assertFalse(log.raffle_id)
        self.assertEqual(log.event_id, self.event)
        # The other raffle of the event holds no prize: the event goes,
        # the line stays with no event and still names its prize.
        self.event.registration_ids.unlink()
        self.event.unlink()
        self.assertTrue(log.exists())
        self.assertFalse(log.event_id)
        self.assertEqual(log.band_id, self.band_a)
        self.assertEqual(log.product_id, prize)

    def test_hand_over_validates_the_delivery(self):
        prize = self._prize("Plant", qty=2)
        draw = self._draw(self._participant("Hugo"))
        order = draw._prize_claim(prize)
        draw.action_prize_deliver()
        self.assertEqual(order.picking_ids.state, "done")
        self.assertEqual(order.picking_ids.move_ids.quantity, 1.0)
        self.assertEqual(draw.claim_state, "delivered")
        self.assertTrue(draw.prize_received)
        self.assertTrue(draw.prize_received_date)
        self.assertEqual(prize.qty_available, 1.0)
        self.assertEqual(prize.raffle_qty_delivered, 1.0)
        self.assertEqual(prize.raffle_qty_reserved, 0.0)
        with self.assertRaises(UserError):
            draw._prize_decline("Too late")

    def test_handed_over_draw_cannot_be_deleted(self):
        """Its prize order keeps pointing back to it. Deleting the draw
        would empty the order's draw: the unit would leave the claim
        figures, and the order's prize line would read as a member
        purchase as soon as its sale type is computed again."""
        prize = self._prize("Vase", qty=2)
        draw = self._draw(self._participant("Vera"))
        order = draw._prize_claim(prize)
        draw.action_prize_deliver()
        line = order.order_line.filtered(lambda sol: sol.product_id == prize)
        self.assertEqual(line.raffle_prize_sale_type, "claim")
        with self.assertRaisesRegex(UserError, "cannot be deleted"):
            draw.unlink()
        self.assertTrue(draw.exists())
        self.assertEqual(order.raffle_draw_id, draw)
        # Without the guard: the uninstall flag skips it, the database
        # empties the order's draw, and the stored sale type keeps "claim"
        # until it is computed again, which makes the line a purchase.
        draw.with_context(**{MODULE_UNINSTALL_FLAG: True}).unlink()
        self.env.invalidate_all()
        self.assertFalse(order.raffle_draw_id)
        self.assertEqual(line.raffle_prize_sale_type, "claim")
        line._compute_raffle_prize_sale_type()
        self.assertEqual(line.raffle_prize_sale_type, "purchase")
        # A declined draw holds no unit and goes.
        declined = self._draw(self._participant("Wade"))
        declined._prize_claim(prize)
        declined._prize_decline("Not for me")
        declined.unlink()
        self.assertFalse(declined.exists())

    def test_raffle_or_event_holding_a_prize_cannot_be_deleted(self):
        """The database deletes the draws of a deleted raffle, and the
        raffles of a deleted event, past the delete guards of the draw:
        the raffle and the event refuse the deletion themselves while one
        of their draws holds a prize."""
        prize = self._prize("Clock", qty=3)
        reserved = self._draw(self._participant("Rita"))
        reserved._prize_claim(prize)
        handed = self._draw(self._participant("Hank", raffle=self.raffle_2))
        handed._prize_claim(prize)
        handed.action_prize_deliver()
        for record in (self.raffle, self.raffle_2, self.event):
            with self.assertRaisesRegex(UserError, "hold a prize") as caught:
                record.unlink()
            self.assertTrue(record.exists())
        self.assertIn("Morning: Draw #1 - Rita", str(caught.exception))
        self.assertIn("Afternoon: Draw #1 - Hank", str(caught.exception))
        self.assertTrue(reserved.exists())
        self.assertEqual(handed.claim_state, "delivered")
        # A declined prize frees its raffle; the handed-over one keeps the
        # other raffle, and the event with it.
        reserved._prize_decline("Leaves early")
        self.raffle.unlink()
        self.assertFalse(reserved.exists())
        with self.assertRaisesRegex(UserError, "hold a prize"):
            self.event.unlink()
        # An event whose draws hold nothing goes with its raffles. Its
        # winners have no registration, which would keep the event.
        other_raffle = self.env["event.raffle"].create(
            {"name": "Evening", "event_id": self.other_event.id}
        )
        Participant = self.env["event.raffle.participant"]
        noel, zoe = (
            Participant.create(
                {"raffle_id": other_raffle.id, "name": name, "email": email}
            )
            for name, email in (
                ("Noel", "noel@example.com"),
                ("Zoe", "zoe@example.com"),
            )
        )
        declined = self._draw(noel)
        declined._prize_claim(prize)
        declined._prize_decline("Not for me")
        self._draw(zoe)
        self.other_event.unlink()
        self.assertFalse(other_raffle.exists())
        self.assertFalse(declined.exists())
        self.assertEqual(self._free(prize), 2.0)

    def test_delete_refusal_lines_follow_the_env_language(self):
        """The refusal lists one line per holding draw, translated in the
        language of the environment even outside a web request, with no
        warning from the translation lookup."""
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize"], ["fr_CA"], overwrite=True
        )
        prize = self._prize("Lamp")
        self._draw(self._participant("Rita"))._prize_claim(prize)
        for record in (self.raffle, self.event):
            with (
                self.assertNoLogs("odoo.tools.translate", level="WARNING"),
                self.assertRaises(UserError) as caught,
            ):
                record.with_context(lang="fr_CA").unlink()
            message = str(caught.exception)
            self.assertIn("ne peut pas être supprimé", message)
            # The French line puts a space before the colon.
            self.assertIn("\n- Morning : ", message)

    def test_absent_winner_can_get_a_prize(self):
        prize = self._prize("Poster")
        draw = self._draw(self._participant("Abby"))
        draw.action_mark_absent()
        self.assertTrue(draw.is_absent)
        self.assertIn(prize, draw._prize_allowed_products())
        draw._prize_claim(prize)
        self.assertEqual(draw.claim_state, "reserved")
        self.assertTrue(draw.is_absent)

    def test_choose_wizard_lists_and_reserves(self):
        prize = self._prize("Cup")
        self._prize("Gone", qty=0)
        draw = self._draw(self._participant("Wade"))
        action = draw.action_open_prize_choose_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_context(action["context"])
            .create({})
        )
        self.assertEqual(wizard.allowed_product_ids, prize)
        self.assertEqual(wizard.quota_info, "0 of 1")
        with self.assertRaisesRegex(UserError, "Choose a prize"):
            wizard.action_confirm()
        wizard.product_id = prize
        wizard.action_confirm()
        self.assertEqual(draw.claim_state, "reserved")

    def test_claim_issues_the_lock_queries(self):
        prize = self._prize("Torch")
        winner = self._participant("Lou")
        twin = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.raffle_2.id,
                "name": "Lou",
                "email": winner.email,
            }
        )
        draw = self._draw(winner)
        queries = []
        execute = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            queries.append((str(query), params))
            return execute(cr, query, params, log_exceptions)

        with patch.object(Cursor, "execute", spy):
            draw._prize_claim(prize)
        lock_query = (
            "SELECT id FROM product_product WHERE id IN %s ORDER BY id "
            "FOR UPDATE"
        )
        lock_product = (lock_query, ((prize.id,),))
        self.assertIn(lock_product, queries)
        scope = tuple(sorted((winner | twin).ids))
        self.assertIn(
            (
                (
                    "SELECT id FROM event_raffle_participant "
                    "WHERE id IN %s ORDER BY id FOR UPDATE"
                ),
                (scope,),
            ),
            queries,
        )
        texts = [q for q, __ in queries]
        self.assertLess(
            texts.index(lock_product[0]),
            next(
                i
                for i, q in enumerate(texts)
                if "INSERT INTO" in q and "sale_order" in q
            ),
        )

    # Wheel

    def test_wheel_copies_band_and_closing_on_the_draw(self):
        self._participant("Wes")
        self._participant("Zoe")
        data = self.raffle.get_wheel_data()
        self.assertIn({"id": self.band_b.id, "name": "B"}, data["prize_bands"])
        self.assertFalse(data["prize_band_id"])
        self.raffle.write(
            {"prize_band_id": self.band_b.id, "prize_closing_draw": True}
        )
        data = self.raffle.get_wheel_data()
        self.assertEqual(data["prize_band_id"], self.band_b.id)
        self.assertTrue(data["prize_closing_draw"])
        res = self.raffle.action_draw_next(prize="Free text")
        draw = self.env["event.raffle.draw"].browse(res["draw_id"])
        self.assertEqual(draw.band_id, self.band_b)
        self.assertTrue(draw.is_closing_draw)
        self.assertEqual(draw.prize, "Free text")

    # Access

    def test_event_user_claims_without_sale_or_stock_rights(self):
        user = new_test_user(
            self.env,
            login="raffle_prize_user",
            groups="event.group_event_user",
        )
        self.assertFalse(user.has_group("sales_team.group_sale_salesman"))
        self.assertFalse(user.has_group("stock.group_stock_user"))
        prize = self._prize("Scarf", qty=2)
        draw = self._draw(self._participant("Uma")).with_user(user)
        self.assertEqual(draw._prize_allowed_products(), prize)
        draw._prize_claim(prize.with_user(user))
        self.assertEqual(draw.claim_state, "reserved")
        draw._prize_decline("Changed mind")
        draw._prize_claim(prize.with_user(user))
        draw.action_prize_deliver()
        self.assertEqual(draw.claim_state, "delivered")
        with self.assertRaises(AccessError):
            draw.write({"claim_state": "reserved"})
        with self.assertRaises(AccessError):
            draw.prize_order_id.name  # noqa: B018

    def test_user_without_email_posts_through_odoobot(self):
        """message_post() refuses an author without an email: such a user
        still claims, declines and hands over, and each note is posted by
        OdooBot with the user's name. A user with an email keeps posting
        as themselves."""
        odoobot = self.env.ref("base.partner_root")
        user = new_test_user(
            self.env,
            login="raffle_prize_no_email",
            groups="event.group_event_user",
            name="Nadia Nomail",
        )
        user.partner_id.email = False
        prize = self._prize("Lantern", qty=2)
        draw = self._draw(self._participant("Olga")).with_user(user)
        draw._prize_claim(prize.with_user(user))
        draw._prize_decline("Asked for another one")
        draw._prize_claim(prize.with_user(user))
        draw.action_prize_deliver()
        self.assertEqual(draw.claim_state, "delivered")
        notes = draw.sudo().message_ids.filtered(
            lambda m: "Prize Lantern" in str(m.body)
        )
        self.assertEqual(len(notes), 4)
        self.assertEqual(notes.author_id, odoobot)
        for note in notes:
            self.assertIn("(by Nadia Nomail)", note.body)
        self.assertIn("Prize Lantern handed over.", notes[0].body)
        # A user with an email posts as themselves, without the suffix.
        staff = new_test_user(
            self.env,
            login="raffle_prize_with_email",
            groups="event.group_event_user",
            email="staff.with.email@example.com",
        )
        other = self._draw(self._participant("Pia")).with_user(staff)
        other._prize_claim(prize.with_user(staff))
        other.action_prize_deliver()
        notes = other.sudo().message_ids.filtered(
            lambda m: "Prize Lantern" in str(m.body)
        )
        self.assertEqual(notes.author_id, staff.partner_id)
        self.assertNotIn("(by ", notes[0].body)

    def test_users_outside_the_event_group_cannot_claim(self):
        prize = self._prize("Badge")
        draw = self._draw(self._participant("Pam"))
        internal = new_test_user(
            self.env, login="raffle_prize_internal", groups="base.group_user"
        )
        portal = new_test_user(
            self.env, login="raffle_prize_portal", groups="base.group_portal"
        )
        for user in (internal, portal):
            with self.assertRaises(AccessError):
                draw.with_user(user)._prize_claim(prize.with_user(user))
            with self.assertRaises(AccessError):
                draw.with_user(user).action_open_prize_choose_wizard()
        self.assertEqual(draw.claim_state, "none")
        self.assertFalse(prize.raffle_claim_ids)

    def test_event_manager_configures_prizes_and_bands(self):
        manager = new_test_user(
            self.env,
            login="raffle_prize_manager",
            groups="event.group_event_manager",
        )
        band = (
            self.env["event.raffle.prize.band"]
            .with_user(manager)
            .create({"name": "C", "value_min": 1000, "value_max": 2000})
        )
        template = (
            self.env["product.template"]
            .with_user(manager)
            .create(
                {
                    "name": "Bike",
                    "type": "consu",
                    "is_storable": True,
                    "is_raffle_prize": True,
                    "list_price": 1500,
                }
            )
        )
        self.assertEqual(template.raffle_band_id, band)
        user = new_test_user(
            self.env,
            login="raffle_prize_user2",
            groups="event.group_event_user",
        )
        with self.assertRaises(AccessError):
            self.env["event.raffle.prize.band"].with_user(user).create(
                {"name": "D"}
            )

    # Claim integrity

    def _customer_order(self):
        """A confirmed sale order that no prize claim created."""
        product = self._prize("Stock Item", qty=2)
        product.is_raffle_prize = False
        customer = self.env["res.partner"].create({"name": "Customer"})
        order = self.env["sale.order"].create(
            {
                "partner_id": customer.id,
                "order_line": [Command.create({"product_id": product.id})],
            }
        )
        order.action_confirm()
        self.assertEqual(order.picking_ids.state, "assigned")
        return order

    def test_context_defaults_do_not_forge_a_claim(self):
        user = new_test_user(
            self.env,
            login="raffle_prize_forger",
            groups="event.group_event_user",
        )
        order = self._customer_order()
        prize = self._prize("Hat")
        participant = self._participant("Fay")
        draw = (
            self.env["event.raffle.draw"]
            .with_user(user)
            .with_context(
                default_claim_state="reserved",
                default_prize_order_id=order.id,
                default_prize_product_id=prize.id,
                default_prize_value=99.0,
            )
            .create(
                {
                    "raffle_id": self.raffle.id,
                    "sequence": 1,
                    "winner_participant_id": participant.id,
                }
            )
        )
        self.assertEqual(draw.claim_state, "none")
        self.assertFalse(draw.prize_order_id)
        self.assertFalse(draw.prize_product_id)
        self.assertFalse(draw.prize_value)
        self.assertEqual(prize.raffle_qty_reserved, 0.0)
        # A claim that points to an order of another origin, written here
        # as superuser, is refused by the buttons: the order stays as is.
        draw.sudo().write(
            {
                "claim_state": "reserved",
                "prize_order_id": order.id,
                "prize_product_id": prize.id,
            }
        )
        with self.assertRaisesRegex(UserError, "does not belong"):
            draw._prize_decline("Forged")
        with self.assertRaisesRegex(UserError, "does not belong"):
            draw.action_prize_deliver()
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.picking_ids.state, "assigned")

    def test_claim_links_its_order_to_the_draw(self):
        prize = self._prize("Pen")
        draw = self._draw(self._participant("Lea"))
        order = draw._prize_claim(prize)
        self.assertEqual(order.raffle_draw_id, draw)

    def test_hand_over_refuses_a_delivery_cancelled_elsewhere(self):
        prize = self._prize("Kite", qty=1)
        draw = self._draw(self._participant("Kim"))
        order = draw._prize_claim(prize)
        order.picking_ids.action_cancel()
        self.assertEqual(self._free(prize), 1.0)
        with self.assertRaisesRegex(UserError, "decline the prize"):
            draw.action_prize_deliver()
        self.assertEqual(draw.claim_state, "reserved")
        self.assertFalse(draw.prize_received)
        draw._prize_decline("Delivery cancelled")
        self.assertEqual(draw.claim_state, "declined")
        self.assertEqual(self._free(prize), 1.0)

    def test_hand_over_refuses_an_order_cancelled_elsewhere(self):
        prize = self._prize("Drum", qty=1)
        draw = self._draw(self._participant("Dan"))
        order = draw._prize_claim(prize)
        order.with_context(disable_cancel_warning=True).action_cancel()
        with self.assertRaisesRegex(UserError, "no longer confirmed"):
            draw.action_prize_deliver()
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(prize.qty_available, 1.0)
        draw._prize_decline("Order cancelled")
        self.assertEqual(draw.claim_state, "declined")
        self.assertEqual(order.state, "cancel")
        self.assertEqual(self._free(prize), 1.0)

    def test_deleted_winner_still_counts_toward_the_quota(self):
        prize = self._prize("Bag", qty=3)
        winner = self._participant("Ivy")
        draw = self._draw(winner)
        draw._prize_claim(prize)
        winner.unlink()
        self.assertFalse(draw.winner_participant_id)
        self.assertEqual(draw.claim_state, "reserved")
        # The same person in another raffle of the event, with a new
        # contact: the claim still counts through the stored email.
        again = self._participant("Ivy", raffle=self.raffle_2)
        self.assertNotEqual(again.partner_id, draw.prize_order_id.partner_id)
        self.assertEqual(again._prize_claim_counts()[again.id], 1)
        self.assertEqual(again._prize_quota_reached(), again)
        self.assertNotIn(again, self.raffle_2._eligible_participants())
        with self.assertRaisesRegex(UserError, "quota"):
            self._draw(again)._prize_claim(prize)

    # Inventory and wheel

    def test_initial_quantity_has_one_label(self):
        Product = self.env["product.product"]
        labelled = [
            name
            for name, field in Product._fields.items()
            if field.string == "Initial Quantity"
        ]
        self.assertEqual(labelled, ["raffle_initial_qty"])
        for xmlid in (
            "event_raffle_prize.product_product_view_list_raffle_inventory",
            "event_raffle_prize.product_product_view_pivot_raffle_inventory",
        ):
            arch = self.env.ref(xmlid).arch
            self.assertIn('name="raffle_initial_qty"', arch)
        prize = self._prize("Ball", qty=4, raffle_initial_qty=4)
        [(total,)] = Product._read_group(
            [("id", "=", prize.id)], [], ["raffle_initial_qty:sum"]
        )
        self.assertEqual(total, 4.0)

    def test_remaining_quantity_sums_per_group(self):
        cup = self._prize("Mug", price=10, qty=3)
        self._prize("Cap", price=20, qty=2)
        self._prize("Tent", price=80, qty=1)
        self._draw(self._participant("Rex"))._prize_claim(cup)
        Product = self.env["product.product"]
        self.assertEqual(
            Product.fields_get(["raffle_qty_free"])["raffle_qty_free"][
                "aggregator"
            ],
            "sum",
        )
        groups = dict(
            Product._read_group(
                [("is_raffle_prize", "=", True)],
                ["raffle_band_id"],
                ["raffle_qty_free:sum"],
            )
        )
        self.assertEqual(groups[self.band_a], 4.0)
        self.assertEqual(groups[self.band_b], 1.0)
        pivot = Product.get_views(
            [
                (
                    self.env.ref(
                        "event_raffle_prize."
                        "product_product_view_pivot_raffle_inventory"
                    ).id,
                    "pivot",
                )
            ]
        )["views"]["pivot"]["arch"]
        self.assertIn('name="raffle_qty_free" type="measure"', pivot)

    def test_archived_band_counts_as_no_band(self):
        self._participant("Ada")
        self._participant("Bob")
        self.raffle.prize_band_id = self.band_b
        self.band_b.active = False
        data = self.raffle.get_wheel_data()
        self.assertFalse(data["prize_band_id"])
        self.assertNotIn(
            self.band_b.id, [band["id"] for band in data["prize_bands"]]
        )
        res = self.raffle.action_draw_next(prize="Any")
        draw = self.env["event.raffle.draw"].browse(res["draw_id"])
        self.assertFalse(draw.band_id)

    def test_channel_announcement_names_the_token_category(self):
        """The draw holds its category from its creation, so the channel
        message of the base module already names it as the prize."""
        channel = self.env["discuss.channel"].create(
            {"name": "draws", "channel_type": "channel"}
        )
        self._participant("Ada")
        self._participant("Bob")
        self.raffle.write(
            {
                "remove_winner": True,
                "prize_band_id": self.band_b.id,
                "announce_channel_auto": True,
                "announce_channel_id": channel.id,
                "announce_channel_message": "{winner} ({prize})",
            }
        )
        Draw = self.env["event.raffle.draw"]
        first = Draw.browse(self.raffle.action_draw_next()["draw_id"])
        second = Draw.browse(
            self.raffle.action_draw_next(prize="Bike")["draw_id"]
        )
        self.assertEqual(first.band_id, self.band_b)
        posts = channel.message_ids.filtered(
            lambda m: m.message_type == "comment"
        ).sorted("id")
        self.assertEqual(
            [str(post.body) for post in posts],
            [
                f"<p>{first.winner_name} (B)</p>",
                f"<p>{second.winner_name} (Bike)</p>",
            ],
        )
        self.assertEqual(posts.author_id, self.env.ref("base.partner_root"))

    def test_hand_over_button_asks_for_confirmation(self):
        arch = self.env["event.raffle.draw"].get_views([(False, "form")])[
            "views"
        ]["form"]["arch"]
        tree = etree.fromstring(arch)
        (button,) = tree.xpath("//button[@name='action_prize_deliver']")
        self.assertTrue(button.get("confirm"))

    # Translations

    def test_fr_ca_keeps_the_names_of_inherited_models(self):
        """Loading the module's terms renames none of the models it extends.

        A model's name has a single translation per language, written by
        the module whose terms load last.
        """
        self.env["res.lang"]._activate_lang("fr_CA")
        Module = self.env["ir.module.module"]
        model_names = [
            "event.event",
            "event.raffle",
            "event.raffle.draw",
            "event.raffle.participant",
            "product.template",
            "product.product",
            "sale.order",
        ]

        def names():
            self.env.invalidate_all()
            IrModel = self.env["ir.model"].with_context(lang="fr_CA")
            return {name: IrModel._get(name).name for name in model_names}

        Module._load_module_terms(
            ["product", "sale", "event_raffle"], ["fr_CA"], overwrite=True
        )
        before = names()
        Module._load_module_terms(
            ["event_raffle_prize"], ["fr_CA"], overwrite=True
        )
        self.assertEqual(names(), before)

    # Token categories

    def test_default_token_categories(self):
        # The xml ids of A, B and C keep their former names.
        suffixes = ("gold", "silver", "bronze", "d", "e", "f")
        expected = {
            f"event_raffle_prize.token_category_{suffix}": (
                sequence,
                f"Prize Group {letter}",
                f"Groupe de prix {letter}",
            )
            for sequence, (suffix, letter) in enumerate(
                zip(suffixes, "ABCDEF", strict=True), start=1
            )
        }
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize"], ["fr_CA"], overwrite=True
        )
        for xmlid, (sequence, name, name_fr) in expected.items():
            band = self.env.ref(xmlid).with_context(lang="en_US")
            self.assertEqual(band.sequence, sequence)
            self.assertEqual(band.name, name)
            self.assertEqual(band.claim_delay_minutes, 45)
            self.assertEqual(band.with_context(lang="fr_CA").name, name_fr)
            if sequence > 3:
                # Demo data gives a range to A, B and C only.
                self.assertEqual((band.value_min, band.value_max), (0, 0))
        defaults = self.env["event.raffle.prize.band"].search(
            [
                ("id", "in", [self.env.ref(x).id for x in expected]),
                ("active", "in", (True, False)),
            ]
        )
        self.assertEqual(
            defaults.with_context(lang="fr_CA").mapped("name"),
            [f"Groupe de prix {letter}" for letter in "ABCDEF"],
        )
        Band = self.env["event.raffle.prize.band"].with_context(lang="fr_CA")
        self.assertEqual(
            Band.fields_get(["claim_delay_minutes"])["claim_delay_minutes"][
                "string"
            ],
            "Validité du lien (minutes)",
        )
        Template = self.env["product.template"].with_context(lang="fr_CA")
        strings = Template.fields_get(
            ["is_raffle_prize", "raffle_band_id", "raffle_member_sale_ok"]
        )
        self.assertEqual(
            strings["is_raffle_prize"]["string"], "Prix commandité"
        )
        self.assertEqual(
            strings["raffle_band_id"]["string"], "Catégorie de jeton"
        )
        self.assertEqual(
            strings["raffle_member_sale_ok"]["string"], "En vente aux membres"
        )
        raffle_fields = (
            self.env["event.raffle"]
            .with_context(lang="fr_CA")
            .fields_get(["prize_band_id"])
        )
        self.assertEqual(
            raffle_fields["prize_band_id"]["string"],
            "Catégorie de jeton du tirage",
        )

    def test_token_category_link_validity_is_positive(self):
        self.assertEqual(self.band_a.claim_delay_minutes, 45)
        for minutes in (0, -5):
            with (
                self.assertRaises(psycopg2.IntegrityError),
                mute_logger("odoo.sql_db"),
                self.cr.savepoint(),
            ):
                self.band_a.claim_delay_minutes = minutes
                self.band_a.flush_recordset()

    def test_token_label(self):
        self.assertEqual(self.band_b._token_label(), "B")
        empty = self.env["event.raffle.prize.band"]
        self.assertEqual(empty._token_label(), "1 token")

    def _set_band_name(self, band, names, sequence):
        """Store `names` ({lang: name}) as the whole name of `band`."""
        self.env.cr.execute(
            "UPDATE event_raffle_prize_band SET name = %s, sequence = %s"
            " WHERE id = %s",
            [Json(names), sequence, band.id],
        )
        band.invalidate_recordset(["name", "sequence"])

    def _migrate_prize_group_names(self):
        script = load_script(
            "event_raffle_prize/migrations/18.0.1.2.0/post-migration.py",
            "event_raffle_prize_post_migration_18_0_1_2_0",
        )
        script.migrate(self.env.cr, "18.0.1.1.0")
        self.env.invalidate_all()

    def _names(self, band):
        return (
            band.with_context(lang="en_US").name,
            band.with_context(lang="fr_CA").name,
        )

    def test_migration_renames_the_default_token_categories(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        gold = self.env.ref("event_raffle_prize.token_category_gold")
        silver = self.env.ref("event_raffle_prize.token_category_silver")
        bronze = self.env.ref("event_raffle_prize.token_category_bronze")
        self._set_band_name(
            gold, {"en_US": "Tux Token Gold", "fr_CA": "Jeton Tux or"}, 3
        )
        self._set_band_name(
            silver,
            {"en_US": "Tux Token Silver", "fr_CA": "Jeton Tux argent"},
            2,
        )
        # Without a fr_CA name, only the en_US name is set.
        self._set_band_name(bronze, {"en_US": "Tux Token Bronze"}, 1)

        self._migrate_prize_group_names()

        self.assertEqual(
            self._names(gold), ("Prize Group A", "Groupe de prix A")
        )
        self.assertEqual(
            self._names(silver), ("Prize Group B", "Groupe de prix B")
        )
        self.assertEqual(bronze.name, "Prize Group C")
        self.env.cr.execute(
            "SELECT name FROM event_raffle_prize_band WHERE id = %s",
            [bronze.id],
        )
        self.assertEqual(self.env.cr.fetchone()[0], {"en_US": "Prize Group C"})
        self.assertEqual(
            (gold.sequence, silver.sequence, bronze.sequence), (1, 2, 3)
        )

        # A second run changes nothing.
        self._migrate_prize_group_names()
        self.assertEqual(
            self._names(gold), ("Prize Group A", "Groupe de prix A")
        )
        self.assertEqual(
            (gold.sequence, silver.sequence, bronze.sequence), (1, 2, 3)
        )

    def test_migration_keeps_an_edited_token_category(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        gold = self.env.ref("event_raffle_prize.token_category_gold")
        silver = self.env.ref("event_raffle_prize.token_category_silver")
        bronze = self.env.ref("event_raffle_prize.token_category_bronze")
        # Renamed in fr_CA only, sequence still the old default.
        self._set_band_name(
            gold, {"en_US": "Tux Token Gold", "fr_CA": "Grand prix"}, 3
        )
        # Renamed in en_US only, sequence changed by hand.
        self._set_band_name(
            silver,
            {"en_US": "Main prizes", "fr_CA": "Jeton Tux argent"},
            7,
        )
        # Old names, sequence changed by hand.
        self._set_band_name(
            bronze,
            {"en_US": "Tux Token Bronze", "fr_CA": "Jeton Tux bronze"},
            9,
        )

        self._migrate_prize_group_names()

        self.assertEqual(self._names(gold), ("Tux Token Gold", "Grand prix"))
        self.assertEqual(gold.sequence, 1)
        self.assertEqual(
            self._names(silver), ("Main prizes", "Jeton Tux argent")
        )
        self.assertEqual(silver.sequence, 7)
        self.assertEqual(
            self._names(bronze), ("Prize Group C", "Groupe de prix C")
        )
        self.assertEqual(bronze.sequence, 9)

    def test_raffle_form_shows_its_token_category(self):
        arch = self.env["event.raffle"].get_views([(False, "form")])["views"][
            "form"
        ]["arch"]
        tree = etree.fromstring(arch)
        self.assertTrue(
            tree.xpath("//group[@name='prizes']/field[@name='prize_band_id']")
        )

    # Member purchases

    def _purchase_order(self, *products, partner=None):
        partner = partner or self.env["res.partner"].create({"name": "Member"})
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    Command.create({"product_id": p.id, "product_uom_qty": 1})
                    for p in products
                ],
            }
        )

    def test_member_purchase_locks_the_prizes_and_counts_no_quota(self):
        first = self._prize("Lamp", qty=2, raffle_member_sale_ok=True)
        second = self._prize("Kite", qty=2, raffle_member_sale_ok=True)
        winner = self._participant("Mel")
        draw = self._draw(winner)
        order = self._purchase_order(second, first, partner=winner.partner_id)
        self.assertEqual(
            order.order_line.mapped("raffle_prize_sale_type"),
            ["purchase", "purchase"],
        )
        queries = []
        execute = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            queries.append((str(query), params))
            return execute(cr, query, params, log_exceptions)

        with patch.object(Cursor, "execute", spy):
            order.action_confirm()
        self.assertEqual(order.state, "sale")
        lock_query = (
            "SELECT id FROM product_product WHERE id IN %s ORDER BY id "
            "FOR UPDATE"
        )
        lock = (lock_query, (tuple(sorted((first | second).ids)),))
        self.assertIn(lock, queries)
        texts = [q for q, __ in queries]
        self.assertLess(
            texts.index(lock[0]),
            next(
                i
                for i, q in enumerate(texts)
                if "INSERT INTO" in q and "stock_move" in q
            ),
        )
        self.assertFalse(
            [
                q
                for q in texts
                if "event_raffle_participant" in q and "FOR UPDATE" in q
            ],
            "a purchase locks no participant",
        )
        # No quota, no draw: the winner may still claim a prize.
        self.assertEqual(winner._prize_claim_counts()[winner.id], 0)
        self.assertEqual(draw.claim_state, "none")
        self.assertFalse(order.raffle_draw_id)
        self.assertEqual(self._free(first), 1.0)
        claim = draw._prize_claim(first)
        self.assertEqual(claim.order_line.raffle_prize_sale_type, "claim")
        self.assertEqual(self._free(first), 0.0)

    def test_purchase_after_the_last_unit_was_claimed_waits_for_stock(self):
        last = self._prize("Globe", qty=1, raffle_member_sale_ok=True)
        draw = self._draw(self._participant("Noa"))
        draw._prize_claim(last)
        order = self._purchase_order(last)
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        move = order.picking_ids.move_ids
        self.assertNotEqual(move.state, "assigned")
        self.assertEqual(draw.claim_state, "reserved")
        self.assertEqual(self._free(last), 0.0)

    def test_claim_after_a_purchase_took_the_last_unit_is_refused(self):
        last = self._prize("Drone", qty=1, raffle_member_sale_ok=True)
        self._purchase_order(last).action_confirm()
        draw = self._draw(self._participant("Oli"))
        self.assertFalse(draw._prize_allowed_products())
        with self.assertRaisesRegex(UserError, "no unit left"):
            draw._prize_claim(last)
