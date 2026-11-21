# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class EventRafflePrizeDeclineWizard(models.TransientModel):
    """Decline the reserved prize of a draw, with the reason."""

    _name = "event.raffle.prize.decline.wizard"
    _description = "Decline a Raffle Prize"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
    )
    prize_product_id = fields.Many2one(related="draw_id.prize_product_id")
    comment = fields.Text(string="Reason", required=True)

    def action_decline(self):
        self.ensure_one()
        self.draw_id._prize_decline(self.comment)
        return {"type": "ir.actions.act_window_close"}
