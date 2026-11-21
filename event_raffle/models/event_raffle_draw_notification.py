# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class EventRaffleDrawNotification(models.Model):
    """One notification sent to the winner of a draw.

    A record is written by the notify wizard for each send and is never
    edited afterwards: it keeps who sent what, how, and the message it
    produced, so that the draw can count its notifications and tell whether
    the winner read the last chat message. The access rights grant no create
    and no write: the wizard creates the record with sudo once it has
    checked the draw and derived the sender, so no record names a sender, a
    draw or a message that no send produced. A manager can delete one.
    """

    _name = "event.raffle.draw.notification"
    _description = "Raffle Draw Notification"
    _order = "date desc, id desc"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date = fields.Datetime(
        string="Date", default=fields.Datetime.now, required=True
    )
    author_id = fields.Many2one(
        "res.partner",
        string="Sender",
        required=True,
        ondelete="restrict",
    )
    channel = fields.Selection(
        [("chat", "Chat"), ("email", "Email")],
        string="Delivery",
        required=True,
    )
    recipient = fields.Char(
        string="Recipient",
        help="Name of the winner contact, or the email address the "
        "notification was sent to.",
    )
    body = fields.Text(string="Message")
    message_id = fields.Many2one(
        "mail.message",
        string="Posted Message",
        ondelete="set null",
        help="Chat message posted in Discuss, or the message behind the "
        "queued email.",
    )
    mail_id = fields.Many2one(
        "mail.mail",
        string="Email",
        ondelete="set null",
    )
    discuss_channel_id = fields.Many2one(
        "discuss.channel",
        string="Conversation",
        ondelete="set null",
    )
    is_read = fields.Boolean(
        string="Read",
        compute="_compute_is_read",
        compute_sudo=True,
        help="The winner has seen this chat message in Discuss. Always "
        "unticked for an email, whose reading Odoo cannot know.",
    )

    @api.depends(
        "channel",
        "message_id",
        "discuss_channel_id.channel_member_ids.seen_message_id",
    )
    def _compute_is_read(self):
        # The winner's member in the conversation moves seen_message_id
        # forward when Discuss marks the conversation as read; a message is
        # read once that pointer reaches it. Nothing on the notification is
        # written when that happens, which is why the field is not stored.
        for rec in self:
            partner = rec.draw_id.partner_id
            if rec.channel != "chat" or not rec.message_id or not partner:
                rec.is_read = False
                continue
            member = rec.discuss_channel_id.channel_member_ids.filtered(
                lambda m, p=partner: m.partner_id == p
            )[:1]
            rec.is_read = bool(
                member and member.seen_message_id.id >= rec.message_id.id
            )
