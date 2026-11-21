# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .event_raffle import (
    BELLY_LOGO_SELECTION,
    CELEBRATION_SELECTION,
    POINTER_ANGLE_SELECTION,
    THEME_SELECTION,
    TUX_ANIMATION_SELECTION,
    _check_announce_channel_choice,
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

    # Messages of a new raffle. The labels are those of the raffle fields
    # they fill; event.raffle reads them in its _settings_* defaults.
    default_notify_winner_auto = fields.Boolean(
        string="Notify the Winner Automatically",
        default=False,
        help="Value of this option on each new raffle: after each draw, "
        "OdooBot sends the notification message to the winner. The "
        "existing raffles keep their own value.",
    )
    default_notify_winner_message = fields.Text(
        string="Notification Message",
        help="Notification message of each new raffle. Empty, a new raffle "
        "gets the standard message, in the language of the user who "
        "creates it. It takes the placeholders of the raffle message: "
        "{winner} or {gagnant}, {number} or {numéro}, {raffle} or "
        "{tirage}, {prize} or {prix}, and {link} or {lien}, the prize link "
        "when the draw has one. A placeholder without a value disappears.",
    )
    default_announce_channel_auto = fields.Boolean(
        string="Announce Each Draw in a Channel",
        default=False,
        help="Value of this option on each new raffle: after each draw, "
        "OdooBot posts the channel message in the discussion channel. A "
        "new raffle has it on only while the discussion channel below is "
        "active. The existing raffles keep their own value.",
    )
    default_announce_channel_id = fields.Many2one(
        "discuss.channel",
        string="Discussion Channel",
        ondelete="set null",
        domain="[('channel_type', 'in', ('channel', 'group'))]",
        help="Discussion channel of each new raffle, channel or group chat "
        "of Discuss. A channel archived or deleted since is not given to "
        "the new raffles.",
    )
    default_announce_channel_message = fields.Text(
        string="Channel Message",
        help="Channel message of each new raffle. Empty, a new raffle gets "
        "the standard message, in the language of the user who creates "
        "it. {winner} or {gagnant} gives the winner name shown on the "
        "draw, {number} or {numéro} the draw number, {raffle} or {tirage} "
        "the raffle name, {prize} or {prix} the prize of the draw, {link} "
        "or {lien} the prize link when the draw has one. A placeholder "
        "without a value disappears, and so do its parentheses when it "
        "stands alone in them, such as ({prize}).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _check_announce_channel_choice(
                self, vals.get("default_announce_channel_id")
            )
        return super().create(vals_list)

    def write(self, vals):
        if "default_announce_channel_id" in vals:
            _check_announce_channel_choice(
                self, vals["default_announce_channel_id"]
            )
        return super().write(vals)

    @api.constrains(
        "default_announce_channel_auto", "default_announce_channel_id"
    )
    def _check_default_announce_channel(self):
        for config in self.filtered("default_announce_channel_auto"):
            if not config.default_announce_channel_id:
                raise ValidationError(
                    self.env._(
                        "Choose the discussion channel where the new raffles "
                        "announce each draw, or stop announcing the draws by "
                        "default."
                    )
                )

    @api.depends_context("lang")
    def _compute_display_name(self):
        # The name is noupdate data that an upgrade never rewrites, so it can
        # hold a label in another language; the breadcrumb shows the reader's
        # label instead.
        for config in self:
            config.display_name = _("Default Settings")
