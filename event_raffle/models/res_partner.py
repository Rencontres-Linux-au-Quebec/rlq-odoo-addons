# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    raffle_draw_ids = fields.One2many(
        "event.raffle.draw",
        "partner_id",
        string="Raffle Wins",
    )
    raffle_win_count = fields.Integer(
        compute="_compute_raffle_win_count",
        string="# Raffle Wins",
    )

    @api.depends("raffle_draw_ids", "raffle_draw_ids.winner_participant_id")
    def _compute_raffle_win_count(self):
        # Contacts is open to users with no event rights at all, and reading
        # event.raffle.draw would raise for them instead of simply showing
        # nothing. One grouped query for the whole set, not one per contact.
        Draw = self.env["event.raffle.draw"]
        if not Draw.has_access("read"):
            self.raffle_win_count = 0
            return
        counts = dict(
            Draw._read_group(
                [
                    ("partner_id", "in", self.ids),
                    ("winner_participant_id", "!=", False),
                ],
                groupby=["partner_id"],
                aggregates=["__count"],
            )
        )
        for partner in self:
            partner.raffle_win_count = counts.get(partner, 0)

    def action_view_raffle_wins(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Raffle Wins"),
            "res_model": "event.raffle.draw",
            "view_mode": "list,form",
            "domain": [
                ("partner_id", "=", self.id),
                ("winner_participant_id", "!=", False),
            ],
        }
