# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models

from .event_raffle import (
    BELLY_LOGO_SELECTION,
    CELEBRATION_SELECTION,
    POINTER_ANGLE_SELECTION,
    THEME_SELECTION,
    TUX_ANIMATION_SELECTION,
)


class EventRaffleConfig(models.Model):
    _name = "event.raffle.config"
    _description = "Event Raffle Default Settings"

    name = fields.Char(default="Default Settings", readonly=True)
    default_theme = fields.Selection(
        THEME_SELECTION,
        string="Default Theme",
        default="light",
        required=True,
    )
    default_winner_celebration = fields.Selection(
        CELEBRATION_SELECTION,
        string="Default Winner Celebration",
        default="candles",
        required=True,
    )
    default_tux_animation = fields.Selection(
        TUX_ANIMATION_SELECTION,
        string="Default Tux Animation",
        default="rotate",
        required=True,
    )
    default_remove_winner = fields.Boolean(
        string="Default Remove Winner",
        default=True,
    )
    default_show_fireworks = fields.Boolean(
        string="Default Show Fireworks",
        default=True,
    )
    default_show_tux = fields.Boolean(
        string="Default Show Penguin (Tux)",
        default=False,
        help="Show Tux the penguin next to the wheel (hidden by default).",
    )
    default_belly_logo = fields.Selection(
        BELLY_LOGO_SELECTION,
        string="Default Belly Logo",
        default="none",
        required=True,
    )
    default_spin_duration = fields.Float(
        string="Default Spin Duration (s)",
        default=6.0,
    )
    default_spin_turns = fields.Integer(
        string="Default Spin Turns",
        default=5,
    )
    default_pointer_angle = fields.Selection(
        POINTER_ANGLE_SELECTION,
        string="Default Pointer Angle",
        default="0",
        required=True,
    )
    default_flag_text = fields.Text(
        string="Default Flag Text",
        default="Vive le logiciel libre",
    )

    @api.depends_context("lang")
    def _compute_display_name(self):
        # The name is noupdate data that an upgrade never rewrites, so it can
        # hold a label in another language; the breadcrumb shows the reader's
        # label instead.
        for config in self:
            config.display_name = _("Default Settings")
