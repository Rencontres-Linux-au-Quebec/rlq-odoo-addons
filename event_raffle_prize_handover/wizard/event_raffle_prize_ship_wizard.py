# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class EventRafflePrizeShipWizard(models.TransientModel):
    """Mark the reserved prize of a draw as shipped, with its tracking."""

    _name = "event.raffle.prize.ship.wizard"
    _description = "Ship a Raffle Prize"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
    )
    prize_product_id = fields.Many2one(related="draw_id.prize_product_id")
    tracking_ref = fields.Char(string="Tracking number", required=True)
    carrier_name = fields.Char(string="Carrier")

    def action_ship(self):
        self.ensure_one()
        self.draw_id._prize_ship(self.tracking_ref, self.carrier_name)
        return {"type": "ir.actions.act_window_close"}
