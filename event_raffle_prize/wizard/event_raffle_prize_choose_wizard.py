# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EventRafflePrizeChooseWizard(models.TransientModel):
    """Pick the prize of a draw's winner among the prizes allowed to them.

    The list is computed by the draw's rules when the wizard opens; the
    confirmation checks them again under lock, since another claim may take
    the last unit in between.
    """

    _name = "event.raffle.prize.choose.wizard"
    _description = "Choose a Raffle Prize"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
    )
    winner_name = fields.Char(related="draw_id.winner_name")
    attendance_mode = fields.Selection(related="draw_id.attendance_mode")
    band_id = fields.Many2one(related="draw_id.band_id")
    is_closing_draw = fields.Boolean(related="draw_id.is_closing_draw")
    quota_info = fields.Char(string="Prizes Held", compute="_compute_allowed")
    allowed_product_ids = fields.Many2many(
        "product.product",
        string="Prizes Allowed",
        compute="_compute_allowed",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Prize",
        domain="[('id', 'in', allowed_product_ids)]",
    )

    @api.depends("draw_id")
    def _compute_allowed(self):
        for wiz in self:
            draw = wiz.draw_id
            participant = draw.winner_participant_id
            if participant:
                held = participant._prize_claim_counts()[participant.id]
                wiz.quota_info = _(
                    "%(held)s of %(quota)s",
                    held=held,
                    quota=participant._prize_quota(),
                )
            else:
                wiz.quota_info = False
            wiz.allowed_product_ids = (
                draw._prize_allowed_products() if draw else False
            )

    def action_confirm(self):
        self.ensure_one()
        if not self.product_id:
            raise UserError(_("Choose a prize first."))
        self.draw_id._prize_claim(self.product_id)
        return {"type": "ir.actions.act_window_close"}
