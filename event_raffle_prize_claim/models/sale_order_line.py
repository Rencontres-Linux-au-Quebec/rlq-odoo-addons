# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends("order_id.raffle_draw_id")
    def _compute_discount(self):
        """The prize line of a claim cart is free: it keeps the sales
        price, which is the prize value, with a full discount."""
        super()._compute_discount()
        for line in self:
            if line._is_raffle_prize_claim_line():
                line.discount = 100.0

    def _is_raffle_prize_claim_line(self):
        self.ensure_one()
        return bool(
            self.order_id.raffle_draw_id
            and not self.display_type
            and not self.is_delivery
            and self.product_id.sudo().is_raffle_prize
        )
