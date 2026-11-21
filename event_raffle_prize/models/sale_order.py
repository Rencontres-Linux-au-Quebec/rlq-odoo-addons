# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class SaleOrder(models.Model):
    """Orders that hold sponsored prizes.

    A prize claim's order points back to its draw (`raffle_draw_id`); any
    other order holding a sponsored prize is a member purchase, which no
    quota counts and no draw sees. Confirming any order that holds a
    sponsored prize first locks the prize rows, as the claim does, so the
    last unit goes to one of them only.
    """

    _inherit = "sale.order"

    raffle_draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Raffle Draw",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="Draw whose prize claim created this order. The claim cancels "
        "or delivers an order only when it points back to its draw.",
    )

    def _prize_lines(self):
        """Lines of the order besides its delivery and note lines."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda line: not line.display_type
            and not getattr(line, "is_delivery", False)
        )

    def action_confirm(self):
        """Lock the sponsored prizes of the orders, then confirm them.

        The rows are locked in ascending id order over all the orders,
        through the lock a claim takes
        (product.product._raffle_prize_lock_rows()), before any stock move
        is created. A purchase confirmed once the last unit went to a
        winner follows Odoo's standard: the order confirms and its
        delivery waits for stock.
        """
        # sudo: the products of an order are read by whoever confirms it,
        # a website visitor included.
        prizes = self.sudo().order_line.product_id.filtered("is_raffle_prize")
        prizes._raffle_prize_lock_rows()
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    raffle_prize_sale_type = fields.Selection(
        [
            ("claim", "Claimed with a token"),
            ("purchase", "Bought by a member"),
        ],
        string="Sponsored Prize Sale",
        compute="_compute_raffle_prize_sale_type",
        store=True,
        help="How the sponsored prize of this line leaves: claimed with a "
        "raffle token (the order belongs to a draw), or bought by a "
        "member at its sales price.",
    )

    @api.depends("product_id", "order_id.raffle_draw_id", "display_type")
    def _compute_raffle_prize_sale_type(self):
        """Set when the line's product or the order's draw changes.

        The product's Sponsored Prize flag is read then, and a later change
        of that flag leaves the lines already written as they are.
        """
        for line in self:
            # sudo: a website visitor reads the flag of the cart's product.
            product = line.product_id.sudo()
            if line.display_type or not product.is_raffle_prize:
                line.raffle_prize_sale_type = False
            elif line.order_id.raffle_draw_id:
                line.raffle_prize_sale_type = "claim"
            else:
                line.raffle_prize_sale_type = "purchase"
