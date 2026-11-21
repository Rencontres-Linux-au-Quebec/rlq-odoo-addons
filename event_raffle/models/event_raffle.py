# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import random

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import sql

THEME_SELECTION = [
    ("light", "Light"),
    ("dark", "Dark"),
    ("spectacle", "Show (spotlights)"),
    ("theatre", "Theater (gold & angels)"),
    ("linux", "Linux techno (dark)"),
    ("linux_light", "Linux techno (light)"),
    ("rave", "Rave (lasers)"),
]
CELEBRATION_SELECTION = [
    ("random", "Random (any of the below)"),
    ("candles", "Candles (Tux dances)"),
    ("confetti", "Confetti cannon"),
    ("fireworks", "Fireworks cannon"),
    ("trumpet", "Trumpet fanfare"),
    ("diabolo", "Diabolo juggling"),
]
TUX_ANIMATION_SELECTION = [
    ("rotate", "Rotate (cycle through all)"),
    ("peace", "Peace"),
    ("jump", "Jump with a smile"),
    ("flag", "Free software flag"),
    ("dance", "Dance"),
]
BELLY_LOGO_SELECTION = [
    ("none", "None"),
    ("fleur_de_lys", "Fleur-de-lys (Québec)"),
]
# Where the pointer sits on the rim, in degrees CLOCKWISE FROM THE TOP, the
# way a clock face reads. The winning segment stops under it wherever it is.
POINTER_ANGLE_SELECTION = [
    ("0", "Top (0°)"),
    ("90", "Right (90°)"),
    ("180", "Bottom (180°)"),
    ("-90", "Left (-90°)"),
]
# Discuss channel types where OdooBot announces the draws. A direct chat
# is never one: it belongs to its two members.
ANNOUNCE_CHANNEL_TYPES = ("channel", "group")


def _config_value(records, field, fallback):
    """Return `field` of the raffle default-settings singleton.

    `fallback` comes back instead when the singleton is missing, or while
    the registry loads and its column is not in database yet.
    """
    cfg = records.env.ref(
        "event_raffle.raffle_config_singleton", raise_if_not_found=False
    )
    if not cfg:
        return fallback
    # Adding a field to an already-installed database calls the defaults
    # from _init_column(), to fill the new column on the rows already there.
    # event.raffle is auto-init'd before event.raffle.config -- class
    # registration order, which event_raffle_config.py importing this
    # module pins -- so the twin column on the singleton may not exist in
    # database yet, and reading it would abort the upgrade. Only while
    # loading: once the registry is ready this costs nothing.
    if not records.env.registry.ready and not sql.column_exists(
        records.env.cr, cfg._table, field
    ):
        return fallback
    return cfg[field]


def _check_announce_channel_choice(records, channel_id):
    """Refuse `channel_id` as the announcement channel that the env user
    sets on `records`.

    OdooBot posts in that channel as superuser at each draw, with a text
    the raffle's users write: the user must be able to read the channel,
    and it must be a channel or a group chat (ANNOUNCE_CHANNEL_TYPES).
    The superuser skips the read check, not the type check. An empty
    `channel_id` passes. Raises AccessError or ValidationError.
    """
    if not channel_id:
        return
    channel = records.env["discuss.channel"].browse(channel_id)
    if not records.env.su:
        channel.check_access("read")
    if channel.sudo().channel_type not in ANNOUNCE_CHANNEL_TYPES:
        raise ValidationError(
            records.env._(
                "%s is not a channel or a group chat: the draws are "
                "announced in one of those only.",
                channel.sudo().name,
            )
        )


def _default(field, fallback):
    """Field default reading the raffle default-settings singleton."""

    def getter(self):
        return _config_value(self, field, fallback)

    return getter


class EventRaffle(models.Model):
    _name = "event.raffle"
    _description = "Event Raffle"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(
        string="Name", required=True, default=lambda self: _("Raffle")
    )
    event_id = fields.Many2one(
        "event.event",
        string="Event",
        ondelete="cascade",
        index=True,
    )
    context_note = fields.Text(string="Context")
    is_test = fields.Boolean(
        string="Test Raffle",
        default=False,
        help="Marks a rehearsal or trial raffle, kept apart from the real "
        "ones: the raffle list opens on the Prod filter, which hides it, "
        "and its form shows a Test ribbon.",
    )
    remove_winner = fields.Boolean(
        string="Remove Winner",
        default=_default("default_remove_winner", True),
        help="Removes the winner from the pool at the next draw.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "In Progress"), ("done", "Done")],
        string="Status",
        default="draft",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    participant_ids = fields.One2many(
        "event.raffle.participant",
        "raffle_id",
        string="Participants",
    )
    draw_ids = fields.One2many(
        "event.raffle.draw",
        "raffle_id",
        string="Draws",
    )
    participant_count = fields.Integer(
        compute="_compute_counts",
        string="# Participants",
    )
    eligible_count = fields.Integer(
        compute="_compute_counts",
        string="# Eligible",
    )
    draw_count = fields.Integer(
        compute="_compute_counts",
        string="# Draws",
    )
    spin_duration = fields.Float(
        string="Spin Duration (s)",
        default=_default("default_spin_duration", 6.0),
        help="How long the wheel spins, in seconds.",
    )
    spin_turns = fields.Integer(
        string="Spin Turns",
        default=_default("default_spin_turns", 5),
        help="Number of full turns before the wheel stops.",
    )
    pointer_angle = fields.Selection(
        POINTER_ANGLE_SELECTION,
        string="Pointer Angle",
        default=_default("default_pointer_angle", "0"),
        required=True,
        help="Position of the pointer on the wheel, in degrees clockwise from "
        "the top: 0 at the top, 90 on the right, 180 at the bottom, -90 on "
        "the left. The winner stops under the pointer.",
    )
    show_fireworks = fields.Boolean(
        string="Show Fireworks",
        default=_default("default_show_fireworks", True),
    )
    show_tux = fields.Boolean(
        string="Show Penguin (Tux)",
        default=_default("default_show_tux", False),
        help="Show Tux the penguin next to the wheel (hidden by default).",
    )
    belly_logo = fields.Selection(
        BELLY_LOGO_SELECTION,
        string="Belly Logo",
        default=_default("default_belly_logo", "none"),
        required=True,
        help="Logo shown on Tux's belly (none by default).",
    )
    tux_animation = fields.Selection(
        TUX_ANIMATION_SELECTION,
        string="Tux Animation",
        default=_default("default_tux_animation", "rotate"),
        required=True,
        help="Animation that Tux plays before each draw. 'Rotate' cycles "
        "through all the available animations.",
    )
    flag_text = fields.Text(
        string="Flag Text",
        default=_default("default_flag_text", "Vive le logiciel libre"),
        help="Text of the flag shown by the 'Free software flag' animation. "
        "A random line is shown at each draw.",
    )
    theme = fields.Selection(
        THEME_SELECTION,
        string="Theme",
        default=_default("default_theme", "light"),
        required=True,
        help="Visual theme of the wheel.",
    )
    winner_celebration = fields.Selection(
        CELEBRATION_SELECTION,
        string="Winner Celebration",
        default=_default("default_winner_celebration", "candles"),
        required=True,
        help="Effect played when a winner is announced. 'Random' picks "
        "one at random at each draw.",
    )
    notify_winner_auto = fields.Boolean(
        string="Notify the Winner Automatically",
        default=_default("default_notify_winner_auto", False),
        help="After each draw, OdooBot sends the notification message to "
        "the winner: a private chat in Discuss when the winner contact has "
        "an internal user account, an email otherwise. A winner with "
        "neither gets no message, and a note on the draw says so.",
    )
    notify_winner_message = fields.Text(
        string="Notification Message",
        default=lambda self: self._settings_notify_winner_message(),
        help="Message sent to each winner when the winner is notified "
        "automatically. While that is on, the Notify button of a draw "
        "proposes it too. It takes the placeholders of the channel "
        "message: {winner} or {gagnant}, {number} or {numéro}, {raffle} or "
        "{tirage}, {prize} or {prix}, and {link} or {lien}, the prize link "
        "when the draw has one. A placeholder without a value disappears.",
    )

    announce_channel_auto = fields.Boolean(
        string="Announce Each Draw in a Channel",
        default=lambda self: self._settings_announce_channel_auto(),
        help="After each draw, OdooBot posts the channel message in the "
        "discussion channel, which the user who draws does not need to "
        "join. An archived or deleted channel gets no message, and a note "
        "on the draw says so.",
    )
    announce_channel_id = fields.Many2one(
        "discuss.channel",
        string="Discussion Channel",
        default=lambda self: self._settings_announce_channel(),
        ondelete="set null",
        domain="[('channel_type', 'in', ('channel', 'group'))]",
        help="Channel or group chat of Discuss where OdooBot announces each "
        "draw.",
    )
    announce_channel_message = fields.Text(
        string="Channel Message",
        default=lambda self: self._settings_announce_channel_message(),
        help="Text posted in the channel after each draw. {winner} or "
        "{gagnant} gives the winner name shown on the draw, {number} or "
        "{numéro} the draw number, {raffle} or {tirage} the raffle name, "
        "{prize} or {prix} the prize of the draw, {link} or {lien} the "
        "prize link when the draw has one. A placeholder without a value "
        "disappears, and so do its parentheses when it stands alone in "
        "them, such as ({prize}). Any other text in braces stays as typed.",
    )

    def _default_notify_winner_message(self):
        """Return the standard notification message in the env language.

        A model method rather than an inline default, so the term resolves to
        this module's translations from any caller: the field default, the
        notify wizard and the migrations, whose upgrade env has no language.
        The link is empty unless a module gives the draw one, and an empty
        placeholder disappears.
        """
        return self.env._("You won a prize, come and claim it! {link}")

    def _default_announce_channel_message(self):
        """Return the standard channel message in the env language.

        A model method for the same reason as the notification message: the
        field default and the migrations share it. The prize sits in
        parentheses, so a draw without a prize drops it.
        """
        return self.env._("Draw #{number}: {winner} won! ({prize}) {link}")

    # The defaults below read the messages section of the raffle default
    # settings. They only fill a new raffle: a raffle keeps its values when
    # the settings change afterwards.

    def _settings_notify_winner_message(self):
        """Return the notification message of a new raffle.

        The message of the default settings when it holds text, the
        standard message in the env language otherwise: a new raffle never
        gets an empty message from the settings.
        """
        message = _config_value(self, "default_notify_winner_message", False)
        if (message or "").strip():
            return message
        return self._default_notify_winner_message()

    def _settings_announce_channel_message(self):
        """Return the channel message of a new raffle.

        The message of the default settings when it holds text, the
        standard message in the env language otherwise.
        """
        message = _config_value(
            self, "default_announce_channel_message", False
        )
        if (message or "").strip():
            return message
        return self._default_announce_channel_message()

    def _settings_announce_channel(self):
        """Return the id of the default channel, False unless the user who
        creates the raffle could choose it.

        A channel archived since it was chosen is left out, as a deleted one
        is, which the settings no longer reference, and so is a channel of a
        type that announces nothing (ANNOUNCE_CHANNEL_TYPES). A user who
        may not read the channel does not get it either: the raffle would
        then post in it a message that user writes, as
        _check_announce_channel_choice() refuses. The superuser reads every
        channel.
        """
        channel = _config_value(self, "default_announce_channel_id", False)
        if not channel:
            return False
        channel_sudo = channel.sudo()
        if (
            not channel_sudo.active
            or channel_sudo.channel_type not in ANNOUNCE_CHANNEL_TYPES
        ):
            return False
        if not self.env.su and not channel.with_env(self.env).has_access(
            "read"
        ):
            return False
        return channel.id

    def _settings_announce_channel_auto(self):
        """Return whether a new raffle announces its draws in a channel.

        On when the default settings say so and their channel is active:
        without a channel to post in, the announcement stays off, which
        keeps the new raffle valid against _check_announce_channel().
        """
        return bool(
            _config_value(self, "default_announce_channel_auto", False)
            and self._settings_announce_channel()
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _check_announce_channel_choice(
                self, vals.get("announce_channel_id")
            )
        return super().create(vals_list)

    def write(self, vals):
        if "announce_channel_id" in vals:
            _check_announce_channel_choice(self, vals["announce_channel_id"])
        return super().write(vals)

    @api.depends(
        "participant_ids",
        "participant_ids.eligible",
        "draw_ids",
    )
    def _compute_counts(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)
            rec.eligible_count = len(rec.participant_ids.filtered("eligible"))
            rec.draw_count = len(rec.draw_ids)

    @api.constrains("notify_winner_auto", "notify_winner_message")
    def _check_notify_winner_message(self):
        for rec in self:
            if (
                rec.notify_winner_auto
                and not (rec.notify_winner_message or "").strip()
            ):
                raise ValidationError(
                    self.env._(
                        "Write the notification message sent to the winners, "
                        "or stop notifying them automatically."
                    )
                )

    @api.constrains(
        "announce_channel_auto",
        "announce_channel_id",
        "announce_channel_message",
    )
    def _check_announce_channel(self):
        for rec in self.filtered("announce_channel_auto"):
            if not rec.announce_channel_id:
                raise ValidationError(
                    self.env._(
                        "Choose the discussion channel where each draw is "
                        "announced, or stop announcing the draws."
                    )
                )
            if not (rec.announce_channel_message or "").strip():
                raise ValidationError(
                    self.env._(
                        "Write the message posted in the channel after each "
                        "draw, or stop announcing the draws."
                    )
                )

    def action_include_all(self):
        self.participant_ids.write({"excluded": False})
        return True

    def action_exclude_all(self):
        self.participant_ids.write({"excluded": True})
        return True

    def _eligible_participants(self):
        self.ensure_one()
        return self.participant_ids.filtered("eligible")

    def get_wheel_data(self):
        self.ensure_one()
        eligible = self._eligible_participants()
        last = (
            self.draw_ids.sorted("sequence")[-1:]
            if self.draw_ids
            else self.env["event.raffle.draw"]
        )
        # The next draw first removes the previous winner (deferred removal),
        # so a draw is only possible if at least one participant would remain
        # eligible afterwards. Guards the "next draw" button against a
        # "no eligible participant" error when a single name is left.
        remaining = eligible
        if self.remove_winner and last:
            remaining = eligible - last.winner_participant_id
        return {
            "raffle_id": self.id,
            "name": self.name,
            "remove_winner": self.remove_winner,
            "spin_duration": self.spin_duration,
            "spin_turns": self.spin_turns,
            "pointer_angle": self.pointer_angle,
            "show_fireworks": self.show_fireworks,
            "show_tux": self.show_tux,
            "belly_logo": self.belly_logo,
            "tux_animation": self.tux_animation,
            "flag_text": self.flag_text or "Vive le logiciel libre",
            "theme": self.theme,
            "winner_celebration": self.winner_celebration,
            "eligible": [{"id": p.id, "name": p.name} for p in eligible],
            "can_draw_next": bool(remaining),
            "draw_count": len(self.draw_ids),
            "last_winner": last.winner_name or False,
            "history": [
                {
                    "id": d.id,
                    "sequence": d.sequence,
                    "winner_name": d.winner_name or "",
                    "prize": d.prize or "",
                    "prize_description": d.prize_description or "",
                    "is_absent": d.is_absent,
                    "present": not d.is_absent,
                    "date": (
                        d.date.strftime("%Y-%m-%d %H:%M") if d.date else ""
                    ),
                }
                for d in self.draw_ids.sorted("sequence")
            ],
        }

    def action_open_fullscreen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "event_raffle.wheel",
            "target": "fullscreen",
            "params": {"raffle_id": self.id},
        }

    def _draw_next_values(self, winner, sequence, prize, prize_description):
        """Return the values of the draw that action_draw_next() creates.

        `winner` is the drawn participant and `sequence` the draw number. A
        module that stores more on each draw extends these values: the draw
        then holds them from its creation, before the winner notification
        and the channel announcement read it.
        """
        self.ensure_one()
        return {
            "raffle_id": self.id,
            "sequence": sequence,
            "winner_participant_id": winner.id,
            "winner_name": winner.name,
            "winner_email": winner.email,
            "prize": prize or False,
            "prize_description": prize_description or False,
        }

    def action_draw_next(self, prize=False, prize_description=False):
        self.ensure_one()
        # Serialize concurrent draws on the same raffle (the wheel can be
        # open in both the embedded widget and the fullscreen action): lock
        # the raffle row so two spins cannot pick from the same pool or
        # create draws with a duplicate sequence.
        self.env.cr.execute(
            "SELECT id FROM event_raffle WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        self.env["event.raffle.draw"].invalidate_model(["sequence"])
        # Deferred removal: the previous winner stays on the wheel after
        # winning and is only removed here, when the next draw is launched.
        if self.remove_winner and self.draw_ids:
            prev = self.draw_ids.sorted("sequence")[-1].winner_participant_id
            if prev:
                prev.won = True
        eligible = self._eligible_participants()
        if not eligible:
            raise UserError(_("No eligible participant for the raffle."))
        wheel = [{"id": p.id, "name": p.name} for p in eligible]
        winner = random.choice(eligible)
        winner_index = eligible.ids.index(winner.id)
        sequence = len(self.draw_ids) + 1
        draw = self.env["event.raffle.draw"].create(
            self._draw_next_values(winner, sequence, prize, prize_description)
        )
        # Do NOT mark the new winner as removed yet (see above).
        if self.state == "draft":
            self.state = "in_progress"
        draw._draw_messages_send()
        return {
            "draw_id": draw.id,
            "winner": {"id": winner.id, "name": winner.name},
            "winner_index": winner_index,
            "wheel": wheel,
        }
