# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mail import plaintext2html

from .event_raffle import ANNOUNCE_CHANNEL_TYPES

# Placeholders of the raffle messages, in English and in French, each
# mapped to the key of _message_values().
MESSAGE_PLACEHOLDERS = {
    "winner": "winner",
    "gagnant": "winner",
    "number": "number",
    "numéro": "number",
    "numero": "number",
    "raffle": "raffle",
    "tirage": "raffle",
    "prize": "prize",
    "prix": "prize",
    "link": "link",
    "lien": "link",
}
# A word in braces. \w matches accented letters, as in {numéro}.
MESSAGE_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
# A placeholder alone in parentheses, with the spaces before it.
MESSAGE_OPTIONAL_RE = re.compile(r"\s*\(\s*\{(\w+)\}\s*\)")
# Stands for an empty placeholder until the spaces around it are removed.
# NUL never occurs in a stored text: PostgreSQL refuses it.
EMPTY_MARK = "\x00"
# Empty placeholders at the start of a line, with the spaces after them.
EMPTY_LINE_START_RE = re.compile(r"^(?:[ \t]*\x00)+[ \t]*", re.MULTILINE)
# An empty placeholder elsewhere, with the spaces before it.
EMPTY_INNER_RE = re.compile(r"[ \t]*\x00")


class EventRaffleDraw(models.Model):
    _name = "event.raffle.draw"
    _description = "Raffle Draw"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    raffle_id = fields.Many2one(
        "event.raffle",
        string="Raffle",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Draw #", default=1)
    name = fields.Char(string="Name", compute="_compute_name", store=True)
    prize = fields.Char(string="Prize")
    prize_description = fields.Text(string="Prize Description")
    winner_participant_id = fields.Many2one(
        "event.raffle.participant",
        string="Winner",
        ondelete="set null",
    )
    winner_name = fields.Char(string="Winner Name", tracking=True)
    winner_email = fields.Char(string="Winner Email")
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        related="winner_participant_id.partner_id",
        store=True,
        index=True,
        help="Winning contact, taken from the participant. Stored so that "
        "the contact form can list its draws without going through the "
        "participants.",
    )
    is_absent = fields.Boolean(string="Absent", default=False, tracking=True)
    date = fields.Datetime(string="Date", default=fields.Datetime.now)
    comment = fields.Text(string="Comment")
    prize_received = fields.Boolean(
        string="Prize Received",
        default=False,
        tracking=True,
    )
    prize_received_date = fields.Datetime(string="Prize Received Date")
    notification_ids = fields.One2many(
        "event.raffle.draw.notification",
        "draw_id",
        string="Notifications Sent",
    )
    notification_count = fields.Integer(
        string="Notifications",
        compute="_compute_notification_count",
        store=True,
        help="Number of notifications sent to the winner from this draw.",
    )
    notified = fields.Boolean(
        string="Notified",
        compute="_compute_notification_count",
        store=True,
        help="At least one notification was sent to the winner.",
    )
    notification_read = fields.Boolean(
        string="Read",
        compute="_compute_notification_read",
        help="The winner has seen the latest chat notification in Discuss. "
        "An email notification never counts as read.",
    )

    @api.onchange("prize_received_date")
    def _onchange_prize_received_date(self):
        # Dating the hand-over says it happened. The flag stays editable on
        # its own, and emptying the date deliberately leaves it alone: only
        # the person who ticked it knows whether the prize came back.
        if self.prize_received_date:
            self.prize_received = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("prize_received_date"):
                vals["prize_received"] = True
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("prize_received_date"):
            vals["prize_received"] = True
        return super().write(vals)

    @api.depends("notification_ids")
    def _compute_notification_count(self):
        for rec in self:
            rec.notification_count = len(rec.notification_ids)
            rec.notified = bool(rec.notification_ids)

    @api.depends("notification_ids.is_read")
    def _compute_notification_read(self):
        # The latest chat notification decides, taken by id since the
        # one2many cache keeps creation order rather than the model order.
        # An email sent after it does not hide a read chat message.
        for rec in self:
            chats = rec.notification_ids.filtered(
                lambda n: n.channel == "chat"
            )
            latest = chats.sorted("id")[-1:]
            rec.notification_read = bool(latest.is_read)

    @api.depends("sequence", "winner_name")
    def _compute_name(self):
        for rec in self:
            label = rec.winner_name or ""
            name = _("Draw #%s") % rec.sequence
            if label:
                name = "%s - %s" % (name, label)
            rec.name = name

    def action_mark_absent(self):
        for rec in self:
            rec.is_absent = True
            if rec.winner_participant_id:
                rec.winner_participant_id.present = False
            rec.message_post(body=_("Winner marked absent."))
        return True

    def action_mark_present(self):
        for rec in self:
            rec.is_absent = False
            if rec.winner_participant_id:
                rec.winner_participant_id.present = True
            rec.message_post(body=_("Winner marked present."))
        return True

    def _notify_winner_auto_send(self):
        """Send the raffle's notification message to the winner, as OdooBot.

        Does nothing unless the raffle notifies its winners automatically.
        The notify wizard replaces the placeholders, picks the chat or the
        email and records the notification, as a manual send does. A winner
        who cannot be reached, or a send that is refused, leaves a note on
        the draw and rolls back the send only, never the draw. Returns
        whether a notification was sent.
        """
        self.ensure_one()
        raffle = self.raffle_id
        if not raffle.notify_winner_auto or not self.winner_participant_id:
            return False
        try:
            with self.env.cr.savepoint():
                wizard = self.env["event.raffle.draw.notify.wizard"].create(
                    {
                        "draw_id": self.id,
                        "sender": "odoobot",
                        "body": raffle.notify_winner_message,
                    }
                )
                wizard.action_send()
        except UserError as error:
            self.message_post(
                body=self.env._(
                    "The automatic notification could not be sent: %s",
                    error.args[0],
                )
            )
            return False
        return True

    def _announce_prize_label(self):
        """Prize of this draw as the raffle messages name it, or "".

        The prize typed on the wheel. A module that gives prizes another
        way extends this label.
        """
        self.ensure_one()
        return self.prize or ""

    @api.model
    def _message_placeholders(self):
        """Placeholder names of the raffle messages, lowercase, each mapped
        to its key in _message_values()."""
        return dict(MESSAGE_PLACEHOLDERS)

    def _message_values(self, to_winner=False):
        """Values of the placeholders of the raffle messages, all strings.

        `to_winner` is true when the text goes to the winner alone, false
        when others read it, as in a channel. The link is empty here: a
        module that gives the winner a link fills it, and may give the
        winner a URL that others must not get.
        """
        self.ensure_one()
        return {
            "winner": self.winner_name or "",
            "number": str(self.sequence),
            "raffle": self.raffle_id.name or "",
            "prize": self._announce_prize_label() or "",
            "link": "",
        }

    def _message_uses(self, template, key):
        """Whether `template` names a placeholder of `key`."""
        names = self._message_placeholders()
        return any(
            names.get(name.lower()) == key
            for name in MESSAGE_PLACEHOLDER_RE.findall(template or "")
        )

    def _message_render(self, template, to_winner=False):
        """Return `template` with the placeholders of this draw replaced.

        Plain text in, plain text out, in one pass of plain substitution: a
        value is never parsed again, a stray brace stays as typed, and so
        does a word in braces that names no placeholder. Names ignore case.
        A known placeholder alone in parentheses whose value is empty is
        removed with its parentheses and the spaces before them. Any other
        known placeholder whose value is empty is removed with the spaces
        before it, or with the spaces after it at the start of a line, so
        that no doubled or dangling space is left. `to_winner` is passed to
        _message_values().
        """
        self.ensure_one()
        names = self._message_placeholders()
        values = self._message_values(to_winner=to_winner)

        def value_of(name):
            key = names.get(name.lower())
            return values.get(key, "") if key else None

        def drop_empty(match):
            return match.group(0) if value_of(match.group(1)) != "" else ""

        def replace(match):
            value = value_of(match.group(1))
            if value is None:
                return match.group(0)
            return value or EMPTY_MARK

        text = (template or "").replace(EMPTY_MARK, "")
        text = MESSAGE_OPTIONAL_RE.sub(drop_empty, text)
        text = MESSAGE_PLACEHOLDER_RE.sub(replace, text)
        text = EMPTY_LINE_START_RE.sub("", text)
        return EMPTY_INNER_RE.sub("", text)

    def _draw_messages_send(self):
        """Send the messages that follow a new draw, as OdooBot: the
        winner notification, then the channel announcement.

        action_draw_next() calls it once the draw is created. A module that
        adds a message, or a value its placeholders show, extends it.
        Returns whether the winner notification went out.
        """
        self.ensure_one()
        notified = self._notify_winner_auto_send()
        self._announce_channel_post()
        return notified

    def _announce_channel_post(self):
        """Announce this draw in the raffle's discussion channel, as OdooBot.

        Does nothing unless the raffle announces its draws. The channel
        message, rendered for this draw and HTML-escaped, goes to the channel
        under OdooBot's user, so the current user does not need to be a
        member. A missing or archived channel, a channel that is neither a
        channel nor a group chat (ANNOUNCE_CHANNEL_TYPES), or a post that is
        refused, leaves a note on the draw and rolls back the post only,
        never the draw. Returns the posted mail.message, or False.
        """
        self.ensure_one()
        raffle = self.raffle_id.sudo()
        if not raffle.announce_channel_auto:
            return False
        channel = raffle.announce_channel_id
        try:
            if not channel.exists():
                raise UserError(
                    self.env._("the raffle has no discussion channel.")
                )
            if not channel.active:
                raise UserError(
                    self.env._(
                        "the discussion channel %s is archived.", channel.name
                    )
                )
            if channel.channel_type not in ANNOUNCE_CHANNEL_TYPES:
                raise UserError(
                    self.env._(
                        "%s is not a channel or a group chat.", channel.name
                    )
                )
            body = self.sudo()._message_render(raffle.announce_channel_message)
            with self.env.cr.savepoint():
                message = channel.with_user(SUPERUSER_ID).message_post(
                    author_id=self.env.ref("base.partner_root").id,
                    body=plaintext2html(body),
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
        except UserError as error:
            self.message_post(
                body=self.env._(
                    "The draw could not be announced in the channel: %s",
                    error.args[0],
                )
            )
            return False
        return message.with_env(self.env)

    def action_open_notify_wizard(self):
        """Open the wizard that sends a notification to this winner."""
        self.ensure_one()
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "name": _("Notify the Winner"),
            "res_model": "event.raffle.draw.notify.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_draw_id": self.id},
        }
