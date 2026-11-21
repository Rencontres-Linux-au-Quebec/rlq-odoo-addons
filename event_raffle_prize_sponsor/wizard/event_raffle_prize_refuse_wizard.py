# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class EventRafflePrizeRefuseWizard(models.TransientModel):
    """Refuse a prize submitted by a sponsor, with the reason shown to the
    sponsor in the portal."""

    _name = "event.raffle.prize.refuse.wizard"
    _description = "Refuse a Sponsored Prize"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Prize",
        required=True,
        ondelete="cascade",
        context={"active_test": False},
    )
    reason = fields.Text(string="Reason", required=True)

    def action_refuse(self):
        self.ensure_one()
        self.product_tmpl_id._raffle_sponsor_refuse(self.reason)
        return {"type": "ir.actions.act_window_close"}
