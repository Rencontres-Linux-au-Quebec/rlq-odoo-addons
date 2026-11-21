# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase

from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

from .common import SponsorDataMixin

MEASURES = (
    "qty_offered",
    "value_offered",
    "qty_won",
    "qty_reserved",
    "value_reserved",
    "qty_shipped",
    "qty_delivered",
    "qty_declined",
    "qty_expired",
    "qty_purchased",
    "amount_purchased",
    "value_distributed",
    "qty_remaining",
)


class SponsorReportScenario(SponsorDataMixin):
    """Prizes of the open event and what became of them.

    The lamp of the sponsor (value 30, 5 offered and in stock) is reserved
    once, handed over once, shipped once, declined once, left in the cart
    of an expired link once, and bought by a member (2 units, one of them
    delivered); a cancelled member order holds one more. The rival's mug
    is handed over once, with a winner who has a public name. A prize of
    the second event is handed over once; a submitted prize is never
    approved. Every value is invented.
    """

    def _scenario(self):
        event = self.open_event
        self.lamp = self._prize(
            "Report Lamp",
            price=30.0,
            qty=5,
            raffle_initial_qty=5,
            raffle_event_ids=[Command.set(event.ids)],
        )
        self.rival_mug = self._prize(
            "Rival Mug",
            price=12.0,
            qty=3,
            raffle_initial_qty=3,
            raffle_sponsor_id=self.rival.id,
            raffle_event_ids=[Command.set(event.ids)],
        )
        self.reserved = self._fair_draw("Rae Reserved")
        self.reserved._prize_claim(self.lamp)
        self.handed = self._fair_draw("Hal Handed")
        self.handed._prize_claim(self.lamp)
        self.handed.action_prize_deliver()
        self.shipped = self._fair_draw("Sky Shipped")
        self.shipped._prize_claim(self.lamp)
        self.shipped._prize_ship("TRACK-0001", "Parcel Example")
        declined = self._fair_draw("Dee Declined")
        declined._prize_claim(self.lamp)
        declined._prize_decline("Already has one.")
        expired = self._fair_draw("Exa Expired")
        self._cart(expired.winner_participant_id, expired, self.lamp)
        self._expire(expired)
        expired._claim_link_expire()
        self.assertEqual(expired.claim_state, "expired")
        self.rival_draw = self._fair_draw("Rob Rival")
        self.rival_draw.partner_id.raffle_public_name = "Lucky Star"
        self.rival_draw._prize_claim(self.rival_mug)
        self.rival_draw.action_prize_deliver()
        # Member purchases: two units confirmed, one of them delivered,
        # and one unit on an order cancelled afterwards.
        buyer = self.env["res.partner"].create(
            {"name": "Mel Member", "email": "mel.member@example.com"}
        )
        purchase = self._member_order(buyer, self.lamp, 2)
        purchase.action_confirm()
        picking = purchase.picking_ids
        picking.move_ids.write({"quantity": 1, "picked": True})
        picking._action_done()
        cancelled = self._member_order(buyer, self.lamp, 1)
        cancelled.action_confirm()
        cancelled.with_context(disable_cancel_warning=True).action_cancel()
        # Another event, and a prize never approved.
        self.second_prize = self._prize(
            "Second Fair Kite",
            price=8.0,
            qty=1,
            raffle_initial_qty=1,
            raffle_event_ids=[Command.set(self.second_event.ids)],
        )
        self.second_raffle = self.env["event.raffle"].create(
            {
                "name": "Second raffle",
                "event_id": self.second_event.id,
                "claim_auto_send": False,
            }
        )
        participant = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.second_raffle.id,
                "name": "Kai Kite",
                "email": "kai.kite@example.com",
            }
        )
        second_draw = self._draw(participant)
        second_draw._prize_claim(self.second_prize)
        second_draw.action_prize_deliver()
        self.submitted = self._submit(name="Never Approved Lamp")
        self.env["stock.quant"]._update_available_quantity(
            self.submitted.with_context(active_test=False).product_variant_ids,
            self.warehouse.lot_stock_id,
            4,
        )

    def _member_order(self, partner, product, qty):
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "warehouse_id": self.warehouse.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": 30.0,
                        }
                    )
                ],
            }
        )


@tagged("post_install", "-at_install")
class TestSponsorReport(SponsorReportScenario, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()

    def _totals(self, domain, user=None):
        Report = self.env["event.raffle.sponsor.report"]
        if user:
            Report = Report.with_user(user)
        [row] = Report._read_group(
            domain, [], [f"{name}:sum" for name in MEASURES]
        )
        return dict(zip(MEASURES, row, strict=True))

    def test_figures_of_a_prize(self):
        self._scenario()
        totals = self._totals(
            [("product_tmpl_id", "=", self.lamp.product_tmpl_id.id)]
        )
        free = self.lamp.with_context(warehouse_id=self.warehouse.id).free_qty
        self.assertEqual(
            totals,
            {
                "qty_offered": 5.0,
                "value_offered": 150.0,
                "qty_won": 3.0,
                "qty_reserved": 1.0,
                "value_reserved": 30.0,
                "qty_shipped": 1.0,
                "qty_delivered": 1.0,
                "qty_declined": 1.0,
                "qty_expired": 1.0,
                "qty_purchased": 2.0,
                "amount_purchased": 60.0,
                "value_distributed": 60.0,
                "qty_remaining": free,
            },
        )
        # 5 received, 3 gone: the hand-over, the shipping and the unit of
        # the purchase delivered. The remaining stock is Odoo's free
        # quantity of what is left.
        self.assertEqual(
            self.lamp.with_context(
                warehouse_id=self.warehouse.id
            ).qty_available,
            2.0,
        )
        rows = self.env["event.raffle.sponsor.report"].search(
            [("product_tmpl_id", "=", self.lamp.product_tmpl_id.id)]
        )
        self.assertEqual(rows.event_id, self.open_event)
        self.assertEqual(rows.sponsor_id, self.sponsor)
        self.assertEqual(rows.band_id, self.band_a)
        self.assertEqual(rows.currency_id, self.env.company.currency_id)
        self.assertEqual(
            sorted(rows.mapped("line_type")),
            [
                "declined",
                "delivered",
                "expired",
                "offer",
                "purchase",
                "reserved",
                "shipped",
            ],
        )

    def test_unapproved_prizes_are_left_out(self):
        self._scenario()
        Report = self.env["event.raffle.sponsor.report"]
        self.assertFalse(
            Report.search([("product_tmpl_id", "=", self.submitted.id)])
        )
        # The sponsor of a contact is its company.
        self.lamp.raffle_sponsor_id = self.alice.partner_id
        rows = Report.search(
            [("product_tmpl_id", "=", self.lamp.product_tmpl_id.id)]
        )
        self.assertEqual(rows.sponsor_id, self.sponsor)
        # A refused prize leaves the report with its history.
        self.lamp.product_tmpl_id.sudo().write(
            {"raffle_sponsor_state": "refused", "active": False}
        )
        self.assertFalse(
            Report.search(
                [("product_tmpl_id", "=", self.lamp.product_tmpl_id.id)]
            )
        )

    def test_a_prize_of_several_events_is_offered_once(self):
        self._scenario()
        template = self.lamp.product_tmpl_id
        template.raffle_event_ids = [Command.link(self.second_event.id)]
        Report = self.env["event.raffle.sponsor.report"]
        offer = Report.search(
            [
                ("product_tmpl_id", "=", template.id),
                ("line_type", "=", "offer"),
            ]
        )
        self.assertEqual(len(offer), 1)
        self.assertFalse(offer.event_id)
        self.assertEqual(
            self._totals([("product_tmpl_id", "=", template.id)])[
                "qty_offered"
            ],
            5.0,
        )

    def test_sponsorship_manager_reads_their_events_only(self):
        self._scenario()
        reviewer = new_test_user(
            self.env,
            login="report_reviewer",
            groups="base.group_user",
            email="report.reviewer@example.com",
        )
        self.open_event.raffle_sponsor_manager_ids = [
            Command.link(reviewer.id)
        ]
        Report = self.env["event.raffle.sponsor.report"]
        rows = Report.with_user(reviewer).search([])
        self.assertTrue(rows)
        self.assertEqual(rows.event_id, self.open_event)
        self.assertEqual(
            self._totals([], user=reviewer)["value_distributed"],
            # Lamp handed over and shipped (2 x 30), rival mug (12).
            72.0,
        )
        # An event user reads every event, listed or not.
        self.assertIn(
            self.second_event,
            Report.with_user(self.organizer).search([]).event_id,
        )
        # Listed on the second event only, an event user still reads the
        # open event: the rules of their groups add up.
        self.second_event.raffle_sponsor_manager_ids = [
            Command.link(self.organizer.id)
        ]
        self.assertIn(
            self.open_event,
            Report.with_user(self.organizer).search([]).event_id,
        )
        plain = new_test_user(
            self.env,
            login="report_plain",
            groups="base.group_user",
            email="report.plain@example.com",
        )
        for user in (plain, self.alice):
            with self.assertRaises(AccessError):
                Report.with_user(user).search([])

    def test_report_opens_the_thank_wizard_for_one_event(self):
        self._scenario()
        Report = self.env["event.raffle.sponsor.report"]
        rows = Report.search([("event_id", "=", self.open_event.id)])
        action = rows.action_open_raffle_sponsor_thank_wizard()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(wizard.event_id, self.open_event)
        with self.assertRaises(UserError):
            Report.search(
                [("event_id", "in", (self.open_event | self.second_event).ids)]
            ).action_open_raffle_sponsor_thank_wizard()

    def test_date_filter_keeps_the_offer_and_the_stock(self):
        """The offer row is dated at the start of the prize's first event,
        else at the prize's creation, so that a period keeps it."""
        self._scenario()
        template = self.lamp.product_tmpl_id
        Report = self.env["event.raffle.sponsor.report"]
        offer = Report.search(
            [
                ("product_tmpl_id", "=", template.id),
                ("line_type", "=", "offer"),
            ]
        )
        self.assertEqual(offer.date, self.open_event.date_begin)
        now = fields.Datetime.now()
        period = [
            ("product_tmpl_id", "=", template.id),
            ("date", ">=", now - timedelta(days=1)),
            ("date", "<=", now + timedelta(days=60)),
        ]
        everything = self._totals([("product_tmpl_id", "=", template.id)])
        self.assertEqual(self._totals(period), everything)
        self.assertEqual(everything["qty_offered"], 5.0)
        before = self._totals(
            [
                ("product_tmpl_id", "=", template.id),
                ("date", "<", now - timedelta(days=1)),
            ]
        )
        self.assertFalse(before["qty_offered"])
        self.assertFalse(before["qty_won"])
        # A prize of several events: the start of the first one. The row
        # keeps its id, so the values read before are dropped from the
        # cache.
        template.raffle_event_ids = [Command.link(self.second_event.id)]
        Report.invalidate_model()
        offer = Report.search(
            [
                ("product_tmpl_id", "=", template.id),
                ("line_type", "=", "offer"),
            ]
        )
        self.assertEqual(offer.date, self.open_event.date_begin)
        # A prize of any event: its creation.
        template.raffle_event_ids = [Command.clear()]
        Report.invalidate_model()
        offer = Report.search(
            [
                ("product_tmpl_id", "=", template.id),
                ("line_type", "=", "offer"),
            ]
        )
        self.assertEqual(offer.date, template.create_date)

    def test_offer_belongs_to_the_company_of_its_event(self):
        """A prize without a company is offered in the company of its
        events, which a user of that company alone reads."""
        currency = self.env.ref("base.EUR")
        currency.active = True
        if currency == self.env.company.currency_id:
            currency = self.env.ref("base.CAD")
            currency.active = True
        second_company = self.env["res.company"].create(
            {"name": "Second Company Example", "currency_id": currency.id}
        )
        event = self._event(
            "Second Company Fair",
            fields.Datetime.now() + timedelta(days=30),
            company_id=second_company.id,
        )
        other = self._event(
            "Second Company Gala",
            fields.Datetime.now() + timedelta(days=50),
            company_id=second_company.id,
        )
        kite = self._prize(
            "Company Kite",
            price=10.0,
            qty=0,
            raffle_initial_qty=2,
            raffle_event_ids=[Command.set(event.ids)],
        ).product_tmpl_id
        self.assertFalse(kite.company_id)
        user = new_test_user(
            self.env,
            login="second_company_user",
            groups="base.group_user,event.group_event_user",
            email="second.company.user@example.com",
            company_id=second_company.id,
            company_ids=[Command.set(second_company.ids)],
        )
        Report = self.env["event.raffle.sponsor.report"]
        offer = Report.with_user(user).search(
            [("product_tmpl_id", "=", kite.id)]
        )
        self.assertEqual(len(offer), 1)
        self.assertEqual(offer.company_id, second_company)
        self.assertEqual(offer.currency_id, currency)
        self.assertEqual(offer.value_offered, 20.0)
        # Two events of that company: still that company.
        kite.raffle_event_ids = [Command.link(other.id)]
        Report.invalidate_model()
        offer = Report.with_user(user).search(
            [("product_tmpl_id", "=", kite.id)]
        )
        self.assertEqual(offer.company_id, second_company)
        # Events of two companies, prize without a company: the first
        # company, which the user of the second company does not read.
        kite.raffle_event_ids = [Command.link(self.open_event.id)]
        Report.invalidate_model()
        self.assertFalse(
            Report.with_user(user).search([("product_tmpl_id", "=", kite.id)])
        )
        offer = Report.search([("product_tmpl_id", "=", kite.id)])
        self.assertEqual(
            offer.company_id,
            self.env["res.company"].search([], order="sequence, id", limit=1),
        )


@tagged("post_install", "-at_install")
class TestSponsorReportClaimLog(SponsorDataMixin, TransactionCase):
    """Declines and expiries read from the claim log: each one counts, and
    a claim that ended with no prize chosen has a line of its own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()
        event = cls.open_event
        cls.lamp = cls._prize(
            "Log Lamp",
            price=30.0,
            qty=2,
            raffle_initial_qty=2,
            raffle_event_ids=[Command.set(event.ids)],
        )
        cls.mug = cls._prize(
            "Log Mug",
            price=12.0,
            qty=2,
            raffle_initial_qty=2,
            raffle_event_ids=[Command.set(event.ids)],
        )

    def _totals(self, domain, user=None):
        Report = self.env["event.raffle.sponsor.report"]
        if user:
            Report = Report.with_user(user)
        [row] = Report._read_group(
            domain, [], [f"{name}:sum" for name in MEASURES]
        )
        return dict(zip(MEASURES, row, strict=True))

    def _prize_totals(self, product):
        return self._totals(
            [("product_tmpl_id", "=", product.product_tmpl_id.id)]
        )

    def _unchosen(self, line_type, event=None):
        return self.env["event.raffle.sponsor.report"].search(
            [
                ("event_id", "=", (event or self.open_event).id),
                ("line_type", "=", line_type),
            ]
        )

    def test_every_decline_of_a_draw_counts(self):
        draw = self._fair_draw("Lou Log")
        draw._prize_claim(self.lamp)
        draw._prize_decline("Too large")
        draw._prize_claim(self.mug)
        draw._prize_decline("Has one already")
        draw._prize_claim(self.lamp)
        lamp = self._prize_totals(self.lamp)
        self.assertEqual(lamp["qty_won"], 1.0)
        self.assertEqual(lamp["qty_reserved"], 1.0)
        self.assertEqual(lamp["value_reserved"], 30.0)
        self.assertEqual(lamp["qty_declined"], 1.0)
        mug = self._prize_totals(self.mug)
        self.assertEqual(mug["qty_won"], 0.0)
        self.assertEqual(mug["qty_declined"], 1.0)
        sponsor = self._totals([("sponsor_id", "=", self.sponsor.id)])
        self.assertEqual(sponsor["qty_declined"], 2.0)
        self.assertEqual(sponsor["qty_won"], 1.0)

    def test_expiry_then_backend_reservation(self):
        draw = self._fair_draw("Eli Expired")
        self._cart(draw.winner_participant_id, draw, self.lamp)
        self._expire(draw)
        draw._claim_link_expire()
        self.assertEqual(draw.claim_state, "expired")
        draw._prize_claim(self.lamp)
        lamp = self._prize_totals(self.lamp)
        self.assertEqual(lamp["qty_expired"], 1.0)
        self.assertEqual(lamp["qty_reserved"], 1.0)
        self.assertEqual(lamp["qty_won"], 1.0)
        rows = self.env["event.raffle.sponsor.report"].search(
            [("product_tmpl_id", "=", self.lamp.product_tmpl_id.id)]
        )
        self.assertEqual(
            sorted(rows.mapped("line_type")), ["expired", "offer", "reserved"]
        )
        self.assertEqual(len(set(rows.ids)), len(rows))

    def test_expiry_without_a_cart_has_its_own_line(self):
        draw = self._fair_draw("Nia Nothing")
        draw.band_id = self.band_b
        draw._claim_link_issue()
        self._expire(draw)
        draw._claim_link_expire()
        row = self._unchosen("expired_unchosen")
        self.assertEqual(len(row), 1)
        self.assertFalse(row.product_tmpl_id)
        self.assertFalse(row.sponsor_id)
        self.assertEqual(row.band_id, self.band_b)
        self.assertEqual(row.qty_expired, 1.0)
        self.assertFalse(row.qty_declined)
        self.assertEqual(row.date, draw.date)
        self.assertEqual(row.company_id, self.env.company)
        # No prize is charged with it.
        self.assertFalse(self._prize_totals(self.lamp)["qty_expired"])
        self.assertFalse(
            self._totals([("sponsor_id", "=", self.sponsor.id)])["qty_expired"]
        )
        # The Expired filter and the No choice filter both keep it.
        Report = self.env["event.raffle.sponsor.report"]
        self.assertIn(
            row,
            Report.search(
                [("line_type", "in", ("expired", "expired_unchosen"))]
            ),
        )
        self.assertIn(
            row,
            Report.search(
                [
                    (
                        "line_type",
                        "in",
                        ("declined_unchosen", "expired_unchosen"),
                    )
                ]
            ),
        )

    def test_prize_removed_before_the_expiry_is_not_counted(self):
        draw = self._fair_draw("Ray Removed")
        cart = self._cart(draw.winner_participant_id, draw, self.lamp)
        cart.order_line.unlink()
        self._expire(draw)
        draw._claim_link_expire()
        self.assertFalse(self._prize_totals(self.lamp)["qty_expired"])
        self.assertEqual(len(self._unchosen("expired_unchosen")), 1)

    def test_link_declined_without_a_cart_has_its_own_line(self):
        draw = self._fair_draw("Dan Declined")
        draw._claim_link_issue()
        draw._claim_link_decline("Cannot stay")
        row = self._unchosen("declined_unchosen")
        self.assertEqual(len(row), 1)
        self.assertFalse(row.product_tmpl_id)
        self.assertFalse(row.sponsor_id)
        self.assertEqual(row.qty_declined, 1.0)
        self.assertFalse(
            self._totals([("sponsor_id", "=", self.sponsor.id)])[
                "qty_declined"
            ]
        )

    def test_declines_outlive_their_draw_raffle_and_event(self):
        """The claim log keeps what the report reads of the draw: its
        lines count once the draw, its raffle, then its event are
        deleted, the last with no event."""
        draw = self._fair_draw("Del Deleted")
        draw._prize_claim(self.lamp)
        draw._prize_decline("Too large")
        unchosen = self._fair_draw("Uma Unchosen")
        unchosen.band_id = self.band_b
        unchosen._claim_link_issue()
        unchosen._claim_link_decline("Cannot stay")
        dates = {draw.id: draw.date, unchosen.id: unchosen.date}
        lamp_row = self.env["event.raffle.sponsor.report"].search(
            [
                ("product_tmpl_id", "=", self.lamp.product_tmpl_id.id),
                ("line_type", "=", "declined"),
            ]
        )
        self.assertEqual(lamp_row.date, dates[draw.id])
        (draw | unchosen).unlink()
        self.assertEqual(self._prize_totals(self.lamp)["qty_declined"], 1.0)
        lamp_row.invalidate_recordset()
        self.assertEqual(lamp_row.event_id, self.open_event)
        self.assertEqual(lamp_row.date, dates[draw.id])
        self.assertEqual(lamp_row.company_id, self.env.company)
        row = self._unchosen("declined_unchosen")
        self.assertEqual(len(row), 1)
        self.assertEqual(row.band_id, self.band_b)
        self.assertEqual(row.date, dates[unchosen.id])
        self.assertEqual(row.qty_declined, 1.0)
        # The sponsorship manager of the event still reads them.
        rows = (
            self.env["event.raffle.sponsor.report"]
            .with_user(self.manager)
            .search([("line_type", "in", ("declined", "declined_unchosen"))])
        )
        self.assertEqual(len(rows), 2)
        # The raffle, then the event go: the lines count with no event.
        self.fair_raffle.unlink()
        self.open_event.registration_ids.unlink()
        self.open_event.unlink()
        self.assertEqual(self._prize_totals(self.lamp)["qty_declined"], 1.0)
        rows = self.env["event.raffle.sponsor.report"].search(
            [("line_type", "in", ("declined", "declined_unchosen"))]
        )
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows.event_id)
        self.assertEqual(
            rows.filtered(lambda r: not r.product_tmpl_id).band_id,
            self.band_b,
        )

    def test_claims_of_a_raffle_with_no_event_count(self):
        """A raffle needs no event. The claims of its draws count for
        their prize, with no event: a reserved one from the draw, a
        declined one from the claim log."""
        lantern = self._prize("No Event Lantern", price=25.0, qty=2)
        raffle = self.env["event.raffle"].create(
            {"name": "Raffle with no event", "claim_auto_send": False}
        )
        self.assertFalse(raffle.event_id)
        Participant = self.env["event.raffle.participant"]
        kept, declined = (
            self._draw(
                Participant.create(
                    {"raffle_id": raffle.id, "name": name, "email": email}
                )
            )
            for name, email in (
                ("Nell Noevent", "nell.noevent@example.com"),
                ("Ned Noevent", "ned.noevent@example.com"),
            )
        )
        kept._prize_claim(lantern)
        declined._prize_claim(lantern)
        declined._prize_decline("Not for me")
        self.assertEqual(kept.claim_state, "reserved")
        rows = self.env["event.raffle.sponsor.report"].search(
            [
                ("product_tmpl_id", "=", lantern.product_tmpl_id.id),
                ("line_type", "in", ("reserved", "declined")),
            ]
        )
        self.assertEqual(
            sorted(rows.mapped("line_type")), ["declined", "reserved"]
        )
        self.assertFalse(rows.event_id)
        self.assertEqual(rows.company_id, self.env.company)
        totals = self._prize_totals(lantern)
        self.assertEqual(totals["qty_won"], 1.0)
        self.assertEqual(totals["qty_reserved"], 1.0)
        self.assertEqual(totals["value_reserved"], 25.0)
        self.assertEqual(totals["qty_declined"], 1.0)

    def test_deleted_handed_over_draw_would_read_as_a_purchase(self):
        """The guard keeps a handed-over unit a claim. Once its draw is
        gone and the order's line computed again, the report reads the
        unit as a member purchase and no longer as a won prize."""
        draw = self._fair_draw("Dee Deleted")
        order = draw._prize_claim(self.lamp)
        draw.action_prize_deliver()
        lamp = self._prize_totals(self.lamp)
        self.assertEqual(lamp["qty_won"], 1.0)
        self.assertEqual(lamp["qty_delivered"], 1.0)
        self.assertFalse(lamp["qty_purchased"])
        with self.assertRaisesRegex(UserError, "cannot be deleted"):
            draw.unlink()
        # The uninstall flag skips the guard.
        draw.with_context(**{MODULE_UNINSTALL_FLAG: True}).unlink()
        self.env.invalidate_all()
        order.order_line._compute_raffle_prize_sale_type()
        self.env.flush_all()
        lamp = self._prize_totals(self.lamp)
        self.assertEqual(lamp["qty_won"], 0.0)
        self.assertEqual(lamp["qty_delivered"], 0.0)
        self.assertEqual(lamp["qty_purchased"], 1.0)

    def test_sponsorship_manager_reads_the_unchosen_lines_of_their_events(
        self,
    ):
        draw = self._fair_draw("Ivy Open")
        draw._claim_link_issue()
        self._expire(draw)
        draw._claim_link_expire()
        raffle = self.env["event.raffle"].create(
            {
                "name": "Second log raffle",
                "event_id": self.second_event.id,
                "claim_auto_send": False,
            }
        )
        participant = self.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": "Gus Second",
                "email": "gus.second@example.com",
            }
        )
        other = self._draw(participant)
        other._claim_link_issue()
        self._expire(other)
        other._claim_link_expire()
        self.assertTrue(self._unchosen("expired_unchosen", self.second_event))
        reviewer = new_test_user(
            self.env,
            login="log_reviewer",
            groups="base.group_user",
            email="log.reviewer@example.com",
        )
        self.open_event.raffle_sponsor_manager_ids = [
            Command.link(reviewer.id)
        ]
        rows = (
            self.env["event.raffle.sponsor.report"]
            .with_user(reviewer)
            .search([("line_type", "=", "expired_unchosen")])
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.event_id, self.open_event)
