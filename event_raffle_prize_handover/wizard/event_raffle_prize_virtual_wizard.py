# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from markupsafe import Markup

from odoo import api, fields, models


class EventRafflePrizeVirtualWizard(models.TransientModel):
    """Email a virtual prize to the winner of a draw.

    The message starts as the prize's instructions in the winner's
    language; the code, when given, is added under it in the email and
    masked in the draw's notification log.
    """

    _name = "event.raffle.prize.virtual.wizard"
    _description = "Send a Virtual Raffle Prize"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
    )
    prize_product_id = fields.Many2one(related="draw_id.prize_product_id")
    recipient = fields.Char(string="Recipient", compute="_compute_recipient")
    body = fields.Html(
        string="Message",
        compute="_compute_body",
        store=True,
        readonly=False,
    )
    code = fields.Char(
        string="Code",
        help="Code or licence key of this unit, added to the email and "
        "masked in the draw's notification log.",
    )

    @api.depends("draw_id")
    def _compute_recipient(self):
        Notify = self.env["event.raffle.draw.notify.wizard"]
        for wiz in self:
            wiz.recipient = (
                Notify.new({"draw_id": wiz.draw_id.id})._winner_email()
                if wiz.draw_id
                else False
            )

    @api.depends("draw_id")
    def _compute_body(self):
        for wiz in self:
            draw = wiz.draw_id
            if not draw:
                wiz.body = False
                continue
            lang = draw._claim_link_lang()
            template = draw.prize_product_id.product_tmpl_id.with_context(
                lang=lang
            )
            instructions = template.raffle_virtual_instructions
            if not instructions:
                instructions = Markup("<p>%s</p>") % draw.with_context(
                    lang=lang
                ).env._(
                    "Here is your prize: %s.",
                    template.with_context(lang=lang).name,
                )
            wiz.body = instructions

    def action_send(self):
        self.ensure_one()
        self.draw_id._prize_send_virtual(self.body, self.code)
        return {"type": "ir.actions.act_window_close"}
