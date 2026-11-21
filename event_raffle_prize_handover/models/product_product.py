# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.depends("raffle_claim_ids.claim_state")
    def _compute_raffle_qty_claims(self):
        """A shipped prize has left the warehouse: it counts as delivered."""
        result = super()._compute_raffle_qty_claims()
        for product in self:
            states = product.raffle_claim_ids.mapped("claim_state")
            product.raffle_qty_delivered += states.count("shipped")
        return result
