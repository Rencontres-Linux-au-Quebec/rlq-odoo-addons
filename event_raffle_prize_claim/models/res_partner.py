# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _compute_last_website_so_id(self):
        """A prize cart is never reloaded as the partner's ordinary cart:
        it belongs to the session of its claim."""
        super()._compute_last_website_so_id()
        for partner in self:
            if partner.last_website_so_id.raffle_draw_id:
                partner.last_website_so_id = False
