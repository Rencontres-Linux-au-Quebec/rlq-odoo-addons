# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Claims run in two real transactions, as two RPC requests would.

TransactionCase shares one connection between its cursors, so these tests
use BaseCase and the registry's own cursors: the data is committed first,
and removed by the cleanup. Each test opens transaction B and reads in it,
which fixes its REPEATABLE READ snapshot, then lets transaction A claim and
commit. B's claim then sees the state of before A's commit, as a request
that started while A was running does.
"""

from contextlib import contextmanager
from unittest.mock import patch

import psycopg2.errors
from odoo import Command, api
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.sql_db import Cursor
from odoo.tests import common, tagged
from odoo.tests.common import BaseCase
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestPrizeClaimConcurrency(BaseCase):
    def setUp(self):
        super().setUp()
        self.registry = Registry(common.get_db_name())
        with self._env() as env:
            event = env["event.event"].create(
                {
                    "name": "Concurrency Event",
                    "date_begin": "2026-03-01 09:00:00",
                    "date_end": "2026-03-01 18:00:00",
                }
            )
            raffles = env["event.raffle"].create(
                [
                    {"name": "First", "event_id": event.id},
                    {"name": "Second", "event_id": event.id},
                ]
            )
            partners = env["res.partner"].create(
                [
                    {"name": "Twin", "email": "twin@example.com"},
                    {"name": "Solo", "email": "solo@example.com"},
                ]
            )
            participants = env["event.raffle.participant"].create(
                [
                    {
                        "raffle_id": raffle.id,
                        "name": partner.name,
                        "email": partner.email,
                        "partner_id": partner.id,
                    }
                    for raffle, partner in (
                        (raffles[0], partners[0]),
                        (raffles[0], partners[1]),
                        (raffles[1], partners[0]),
                    )
                ]
            )
            draws = env["event.raffle.draw"].create(
                [
                    {
                        "raffle_id": participant.raffle_id.id,
                        "sequence": index + 1,
                        "winner_participant_id": participant.id,
                        "winner_name": participant.name,
                    }
                    for index, participant in enumerate(participants)
                ]
            )
            templates = env["product.template"].create(
                [
                    {
                        "name": name,
                        "type": "consu",
                        "is_storable": True,
                        "is_raffle_prize": True,
                        "list_price": 10.0,
                        "raffle_event_ids": [Command.set(event.ids)],
                    }
                    for name in ("Last unit", "Plenty A", "Plenty B")
                ]
            )
            location = (
                env["event.raffle"]._prize_warehouse(env.company).lot_stock_id
            )
            for template, qty in zip(templates, (1.0, 5.0, 5.0), strict=True):
                env["stock.quant"]._update_available_quantity(
                    template.product_variant_id, location, qty
                )
            self.event_id = event.id
            self.raffle_ids = raffles.ids
            self.partner_ids = partners.ids
            self.draw_ids = draws.ids
            self.product_ids = templates.product_variant_ids.ids
            self.order_ids = []
        self.addCleanup(self._cleanup)

    @contextmanager
    def _env(self):
        """An admin environment on a new cursor, committed at the end."""
        with self.registry.cursor() as cr:
            yield api.Environment(cr, common.ADMIN_USER_ID, {})

    def _cleanup(self):
        with self._env() as env:
            draws = env["event.raffle.draw"].browse(self.draw_ids)
            orders = draws.prize_order_id | env["sale.order"].browse(
                self.order_ids
            )
            pickings = orders.picking_ids
            for order in orders.filtered(lambda o: o.state != "cancel"):
                if order.locked:
                    order.action_unlock()
                order.with_context(disable_cancel_warning=True).action_cancel()
            orders.unlink()
            pickings.unlink()
            draws.sudo().write({"claim_state": "declined"})
            # The claim log outlives the draws and its lines keep their
            # prize (ondelete restrict): they go first. sudo: the log is
            # read only for every group.
            env["event.raffle.prize.claim.log"].sudo().search(
                [("raffle_id", "in", self.raffle_ids)]
            ).unlink()
            env["event.raffle"].browse(self.raffle_ids).unlink()
            env["event.event"].browse(self.event_id).unlink()
            products = env["product.product"].browse(self.product_ids)
            # sudo: quants are deleted by the superuser only.
            env["stock.quant"].sudo().search(
                [("product_id", "in", products.ids)]
            ).unlink()
            products.product_tmpl_id.unlink()
            env["res.partner"].browse(self.partner_ids).unlink()

    def _purchase(self, env, product_id):
        """Confirm a member purchase of one unit of `product_id`."""
        order = env["sale.order"].create(
            {
                "partner_id": self.partner_ids[1],
                "order_line": [
                    Command.create(
                        {"product_id": product_id, "product_uom_qty": 1}
                    )
                ],
            }
        )
        self.order_ids.append(order.id)
        order.action_confirm()
        return order

    @staticmethod
    def _claim(env, draw_id, product_id):
        draw = env["event.raffle.draw"].browse(draw_id)
        return draw._prize_claim(env["product.product"].browse(product_id))

    def _assert_b_fails_at_the_lock(self, env_b, draw_id, product_id):
        """B's claim fails on the lock, before creating any sale order."""
        queries = []
        execute = Cursor.execute

        def spy(cr, query, params=None, log_exceptions=True):
            queries.append(str(query))
            return execute(cr, query, params, log_exceptions)

        with (
            mute_logger("odoo.sql_db"),
            patch.object(Cursor, "execute", spy),
            self.assertRaises(psycopg2.errors.SerializationFailure),
        ):
            self._claim(env_b, draw_id, product_id)
        self.assertFalse(
            [q for q in queries if 'INSERT INTO "sale_order"' in q],
            "transaction B went past the lock with a stale snapshot",
        )

    def test_last_unit_goes_once(self):
        last_unit = self.product_ids[0]
        with self._env() as env_a, self._env() as env_b:
            # B's snapshot: the last unit is still free.
            draw_b = env_b["event.raffle.draw"].browse(self.draw_ids[1])
            self.assertEqual(draw_b.claim_state, "none")
            self._claim(env_a, self.draw_ids[0], last_unit)
            env_a.cr.commit()
            self._assert_b_fails_at_the_lock(
                env_b, self.draw_ids[1], last_unit
            )
            # The RPC layer retries B on a new snapshot: no unit is left.
            env_b.cr.rollback()
            with self.assertRaisesRegex(UserError, "no unit left"):
                self._claim(env_b, self.draw_ids[1], last_unit)
            env_b.cr.rollback()
        with self._env() as env:
            draws = env["event.raffle.draw"].browse(self.draw_ids)
            self.assertEqual(
                draws.mapped("claim_state"), ["reserved", "none", "none"]
            )
            product = env["product.product"].browse(last_unit)
            self.assertEqual(product.raffle_qty_free, 0.0)

    def test_quota_holds_across_raffles(self):
        # The same person won in both raffles of the event, quota 1.
        plenty_a, plenty_b = self.product_ids[1:]
        with self._env() as env_a, self._env() as env_b:
            draw_b = env_b["event.raffle.draw"].browse(self.draw_ids[2])
            self.assertEqual(draw_b.claim_state, "none")
            self._claim(env_a, self.draw_ids[0], plenty_a)
            env_a.cr.commit()
            self._assert_b_fails_at_the_lock(env_b, self.draw_ids[2], plenty_b)
            env_b.cr.rollback()
            with self.assertRaisesRegex(UserError, "quota"):
                self._claim(env_b, self.draw_ids[2], plenty_b)
            env_b.cr.rollback()
            # Another person is not held up by that quota.
            self._claim(env_b, self.draw_ids[1], plenty_b)
            env_b.cr.commit()
        with self._env() as env:
            draws = env["event.raffle.draw"].browse(self.draw_ids)
            self.assertEqual(
                draws.mapped("claim_state"), ["reserved", "reserved", "none"]
            )

    def test_member_purchase_and_claim_of_the_last_unit_serialize(self):
        last_unit = self.product_ids[0]
        with self._env() as env_a, self._env() as env_b:
            draw_b = env_b["event.raffle.draw"].browse(self.draw_ids[1])
            self.assertEqual(draw_b.claim_state, "none")
            # A member buys the last unit while B's snapshot still has it.
            self._purchase(env_a, last_unit)
            env_a.cr.commit()
            self._assert_b_fails_at_the_lock(
                env_b, self.draw_ids[1], last_unit
            )
            env_b.cr.rollback()
            with self.assertRaisesRegex(UserError, "no unit left"):
                self._claim(env_b, self.draw_ids[1], last_unit)
            env_b.cr.rollback()
        with self._env() as env:
            draw = env["event.raffle.draw"].browse(self.draw_ids[1])
            self.assertEqual(draw.claim_state, "none")

    def test_claim_and_member_purchase_of_the_last_unit_serialize(self):
        last_unit = self.product_ids[0]
        with self._env() as env_a, self._env() as env_b:
            # B's snapshot: the last unit is still free.
            product_b = env_b["product.product"].browse(last_unit)
            self.assertEqual(product_b.raffle_qty_free, 1.0)
            self._claim(env_a, self.draw_ids[0], last_unit)
            env_a.cr.commit()
            with (
                mute_logger("odoo.sql_db"),
                self.assertRaises(psycopg2.errors.SerializationFailure),
            ):
                self._purchase(env_b, last_unit)
            env_b.cr.rollback()
            # Retried, the purchase confirms and its delivery waits.
            self.order_ids.clear()
            order = self._purchase(env_b, last_unit)
            env_b.cr.commit()
            self.assertEqual(order.state, "sale")
            self.assertNotEqual(order.picking_ids.move_ids.state, "assigned")
        with self._env() as env:
            draw = env["event.raffle.draw"].browse(self.draw_ids[0])
            self.assertEqual(draw.claim_state, "reserved")
