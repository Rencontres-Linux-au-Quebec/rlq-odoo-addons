# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class EventRaffleParticipant(models.Model):
    _name = "event.raffle.participant"
    _description = "Raffle Participant"
    _order = "name"

    raffle_id = fields.Many2one(
        "event.raffle",
        string="Raffle",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email")
    partner_id = fields.Many2one("res.partner", string="Contact")
    registration_id = fields.Many2one(
        "event.registration",
        string="Registration",
        ondelete="set null",
    )
    source = fields.Selection(
        [
            ("registration", "Registration"),
            ("partner", "Contact"),
            ("guest", "Guest"),
        ],
        string="Source",
        default="guest",
        required=True,
    )
    won = fields.Boolean(string="Has Won", default=False)
    present = fields.Boolean(string="Present", default=True)
    excluded = fields.Boolean(string="Excluded", default=False)
    eligible = fields.Boolean(
        string="Eligible",
        compute="_compute_eligible",
        store=True,
    )

    @api.depends("excluded", "won", "raffle_id.remove_winner")
    def _compute_eligible(self):
        for rec in self:
            blocked_by_win = rec.won and rec.raffle_id.remove_winner
            rec.eligible = not rec.excluded and not blocked_by_win

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = self.partner_id.name
            self.email = self.partner_id.email
            self.source = "partner"
