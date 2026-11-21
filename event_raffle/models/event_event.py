# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models


class EventEvent(models.Model):
    _inherit = "event.event"

    raffle_ids = fields.One2many(
        "event.raffle",
        "event_id",
        string="Raffles",
    )
    raffle_count = fields.Integer(
        compute="_compute_raffle_counts",
        string="# Raffles",
    )
    raffle_winner_count = fields.Integer(
        compute="_compute_raffle_counts",
        string="# Winners",
    )

    @api.depends("raffle_ids", "raffle_ids.draw_ids.winner_participant_id")
    def _compute_raffle_counts(self):
        for event in self:
            event.raffle_count = len(event.raffle_ids)
            event.raffle_winner_count = len(
                event.raffle_ids.draw_ids.filtered("winner_participant_id")
            )

    def action_start_raffle(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Start a Raffle"),
            "res_model": "event.raffle.start.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_event_id": self.id},
        }

    def action_view_raffles(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Raffles"),
            "res_model": "event.raffle",
            "view_mode": "list,form",
            "domain": [("event_id", "=", self.id)],
            "context": {"default_event_id": self.id},
        }

    def action_view_raffle_winners(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Winners"),
            "res_model": "event.raffle.draw",
            "view_mode": "list,form",
            "domain": [
                ("raffle_id.event_id", "=", self.id),
                ("winner_participant_id", "!=", False),
            ],
        }
