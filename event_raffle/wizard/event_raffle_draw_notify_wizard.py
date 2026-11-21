# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from email.utils import formataddr

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mail import plaintext2html


class EventRaffleDrawNotifyWizard(models.TransientModel):
    """Send one notification to the winner of a draw.

    The message takes the placeholders of the raffle messages (see
    event.raffle.draw._message_render()), replaced when it is sent: the
    form shows them as typed, the winner and the log read the result.

    The winner is reached by a private chat in Discuss when its contact has
    an active internal user, and by email otherwise. A portal user has no
    Discuss app and a chat member is only notified by web push, so a chat
    sent to a portal user never reaches it: portal users go by email. The
    sender is a choice between OdooBot and the current user, never another
    user: the selection is the only input, and the author is derived from it.
    """

    _name = "event.raffle.draw.notify.wizard"
    _description = "Notify a Raffle Winner"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        required=True,
        ondelete="cascade",
    )
    sender = fields.Selection(
        [("odoobot", "OdooBot"), ("me", "Me")],
        string="Send as",
        required=True,
        default="odoobot",
    )
    body = fields.Text(
        string="Message",
        required=True,
        compute="_compute_body",
        store=True,
        readonly=False,
        precompute=True,
        help="Placeholders are replaced when the message is sent: {winner} "
        "or {gagnant}, {number} or {numéro}, {raffle} or {tirage}, {prize} "
        "or {prix}, and {link} or {lien}, the prize link when the draw has "
        "one. A placeholder without a value disappears.",
    )
    delivery = fields.Selection(
        [("chat", "Chat"), ("email", "Email"), ("none", "Not possible")],
        string="Delivery",
        compute="_compute_delivery",
    )
    recipient = fields.Char(string="Recipient", compute="_compute_delivery")
    delivery_info = fields.Char(compute="_compute_delivery")

    @api.depends("draw_id")
    def _compute_body(self):
        # The raffle's message while it notifies its winners automatically,
        # so that a manual send repeats the text the winner already got;
        # the standard text otherwise, the raffle's message being hidden.
        for wiz in self:
            raffle = wiz.draw_id.raffle_id
            message = (
                raffle.notify_winner_auto and raffle.notify_winner_message
            )
            wiz.body = (
                message
                or self.env["event.raffle"]._default_notify_winner_message()
            )

    @api.depends(
        "draw_id.partner_id.email",
        "draw_id.partner_id.user_ids",
        "draw_id.winner_email",
    )
    def _compute_delivery(self):
        for wiz in self:
            draw = wiz.draw_id
            partner = draw.partner_id
            email = wiz._winner_email()
            if wiz._winner_user():
                wiz.delivery = "chat"
                wiz.recipient = partner.display_name
                wiz.delivery_info = _(
                    "The winner has an internal user account: the message "
                    "is sent as a private chat in Discuss."
                )
            elif email:
                wiz.delivery = "email"
                wiz.recipient = (
                    f"{partner.name} <{email}>" if partner else email
                )
                wiz.delivery_info = _(
                    "The winner has no internal user account (a portal "
                    "account does not see Discuss): the message is sent by "
                    "email."
                )
            else:
                wiz.delivery = "none"
                wiz.recipient = partner.display_name or draw.winner_name
                wiz.delivery_info = _(
                    "The winner has neither an internal user account nor an "
                    "email address, so no notification can be sent. Add an "
                    "email to the draw or to the winner contact first."
                )

    def _winner_user(self):
        """The active internal user of the winner contact, if any.

        Share users (portal, public) are left out: they cannot open Discuss.
        """
        self.ensure_one()
        partner = self.draw_id.partner_id
        if not partner:
            return self.env["res.users"]
        # sudo: an event user does not read the portal users.
        return partner.sudo().user_ids.filtered(
            lambda u: u.active and not u.share
        )[:1]

    def _winner_email(self):
        """The contact email, else the email typed on the draw."""
        self.ensure_one()
        return self.draw_id.partner_id.email or self.draw_id.winner_email

    def _sender_partner(self):
        self.ensure_one()
        if self.sender == "odoobot":
            return self.env.ref("base.partner_root")
        return self.env.user.partner_id

    def _sender_email_from(self, partner):
        """From header of the email sent on behalf of `partner`.

        OdooBot owns no mailbox: its name goes with the database default
        sender, else the company email. A user writes from its own address
        when it has one, with the same fallback otherwise.
        """
        if partner != self.env.ref("base.partner_root") and partner.email:
            return partner.email_formatted
        address = (
            self.env["ir.mail_server"]._get_default_from_address()
            or self.env.company.email
        )
        if address:
            return formataddr((partner.name or "", address))
        return partner.email_formatted

    def _send_chat(self, author, body_html):
        """Post `body_html` in the chat between `author` and the winner.

        discuss.channel.channel_get() finds or creates the direct-message
        channel between its environment user and the given partner, so it
        runs under OdooBot's user (base.user_root) when OdooBot writes, and
        under the current user otherwise. Returns (channel, message), bound
        to the current environment.
        """
        self.ensure_one()
        winner = self.draw_id.partner_id
        if author == winner:
            raise UserError(
                _(
                    "You cannot send a chat message to yourself. Choose OdooBot."
                )
            )
        if self.sender == "odoobot":
            odoobot_user = self.env.ref("base.user_root")
            channel = (
                self.env["discuss.channel"]
                .with_user(odoobot_user)
                .channel_get([winner.id], pin=False)
            )
            # sudo: the author is forced to OdooBot, the current user cannot
            # post in a conversation it is not a member of.
            message = channel.sudo().message_post(
                author_id=author.id,
                body=body_html,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        else:
            channel = self.env["discuss.channel"].channel_get([winner.id])
            message = channel.message_post(
                body=body_html,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        return channel.with_env(self.env), message.with_env(self.env)

    def _send_email(self, author, body_html):
        """Queue an email to the winner and send it after the commit.

        The mail goes to the contact when the address is the contact's,
        else to the address typed on the draw. auto_delete stays off so the
        mail, its state and its message survive the sending.
        """
        self.ensure_one()
        draw = self.draw_id
        partner = draw.partner_id
        vals = {
            "subject": _("You won a prize: %s")
            % (draw.prize or draw.raffle_id.name),
            "body_html": body_html,
            "author_id": author.id,
            "email_from": self._sender_email_from(author),
            "auto_delete": False,
        }
        if partner.email:
            vals["recipient_ids"] = [(4, partner.id)]
        else:
            vals["email_to"] = draw.winner_email
        # sudo: mail.mail is restricted to administrators.
        mail = self.env["mail.mail"].sudo().create(vals)
        mail.send_after_commit()
        return mail.with_env(self.env)

    def action_send(self):
        self.ensure_one()
        draw = self.draw_id
        draw.check_access("write")
        if self.delivery == "none":
            raise UserError(self.delivery_info)
        # The placeholders render for the winner, who alone reads the text.
        body = draw._message_render(self.body, to_winner=True).strip()
        if not body:
            raise UserError(_("The message is empty."))
        author = self._sender_partner()
        body_html = plaintext2html(body)
        vals = {
            "draw_id": draw.id,
            "author_id": author.id,
            "channel": self.delivery,
            "recipient": self.recipient,
            "body": body,
        }
        if self.delivery == "chat":
            channel, message = self._send_chat(author, body_html)
            vals.update(discuss_channel_id=channel.id, message_id=message.id)
            note = _("Notification sent by chat by %s.") % author.name
        else:
            mail = self._send_email(author, body_html)
            vals.update(mail_id=mail.id, message_id=mail.mail_message_id.id)
            note = _("Notification sent by email by %s.") % author.name
        # sudo: users only read notifications, so that a record cannot be
        # written with a sender, a draw or a message that no send produced.
        # This method is the only writer, after the checks above.
        self.env["event.raffle.draw.notification"].sudo().create(vals)
        draw.message_post(body=note)
        return {"type": "ir.actions.act_window_close"}
