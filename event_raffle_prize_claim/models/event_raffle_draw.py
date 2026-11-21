# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import math
import secrets
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import consteq, format_time

# Written by the link methods only, with sudo, after their checks.
CLAIM_LINK_FIELDS = {"claim_token", "claim_deadline", "claim_link_end"}
# Session key of the claim: {"draw_id": int, "token": str}.
SESSION_KEY = "raffle_prize_claim"
# Session key of the last claim confirmed in this session: a draw id.
SESSION_DONE_KEY = "raffle_prize_done"
# Session key of the reason the last confirmation was refused.
SESSION_ERROR_KEY = "raffle_prize_error"
TOKEN_BYTES = 32


class EventRaffleDraw(models.Model):
    """Single-use prize link of a draw.

    The link carries a random token stored on the draw. It opens a claim
    for the winner only: the visitor signs in first, and the signed-in
    user's contact must be the draw's contact. The claim then lets the
    website shop list the prizes of that winner only, until the deadline;
    a signed-in winner gets the same claim in the shop without opening the
    link. The token is cleared when the claim is settled (a prize reserved
    by the winner or in the backend, the prize declined) or when the
    deadline passes: a cleared token matches no draw, so every closed link
    reads the same as an unknown one.
    """

    _inherit = "event.raffle.draw"

    claim_token = fields.Char(
        string="Link Token",
        readonly=True,
        copy=False,
        groups="event.group_event_user",
    )
    claim_deadline = fields.Datetime(
        string="Link Deadline",
        readonly=True,
        copy=False,
        help="The prize link works until this time.",
    )
    claim_link_end = fields.Selection(
        [("used", "Used"), ("expired", "Expired")],
        string="Link Closed",
        readonly=True,
        copy=False,
        help="Why the last prize link stopped working.",
    )
    claim_link_state = fields.Selection(
        [
            ("none", "Not sent"),
            ("open", "Open"),
            ("expired", "Expired"),
            ("used", "Used"),
        ],
        string="Prize Link",
        compute="_compute_claim_link_state",
        compute_sudo=True,
    )
    claim_link_url = fields.Char(
        string="Prize Link URL",
        compute="_compute_claim_link_url",
        compute_sudo=True,
        groups="event.group_event_user",
        help="Opens for the winner's account only: whoever opens it signs "
        "in first.",
    )

    _sql_constraints = [  # noqa: RUF012
        (
            "claim_token_unique",
            "UNIQUE(claim_token)",
            "A prize link token is unique.",
        ),
    ]

    @api.model
    def _prize_claim_fields(self):
        return super()._prize_claim_fields() | CLAIM_LINK_FIELDS

    @api.depends(
        "claim_token", "claim_deadline", "claim_link_end", "claim_state"
    )
    def _compute_claim_link_state(self):
        now = fields.Datetime.now()
        for draw in self:
            if not draw.claim_deadline:
                draw.claim_link_state = "none"
            elif draw.claim_link_end:
                draw.claim_link_state = draw.claim_link_end
            elif (
                draw.claim_token
                and draw.claim_state == "none"
                and draw.claim_deadline > now
            ):
                draw.claim_link_state = "open"
            else:
                draw.claim_link_state = "expired"

    @api.depends("claim_link_state")
    def _compute_claim_link_url(self):
        for draw in self:
            draw.claim_link_url = (
                draw._claim_link_url(draw.claim_token)
                if draw.claim_link_state == "open"
                else False
            )

    # ------------------------------------------------------------------
    # Link
    # ------------------------------------------------------------------

    def _claim_link_base_url(self):
        """Base URL of the link: the event's website, else web.base.url.

        The event has a website when website_event is installed; a website
        without a domain falls back to web.base.url as well.
        """
        self.ensure_one()
        event = self.raffle_id.event_id
        website = self.env["website"]
        if "website_id" in event._fields:
            website = event.sudo().website_id
        if website.domain:
            return website.get_base_url()
        return self.get_base_url()

    def _claim_link_url(self, token):
        self.ensure_one()
        return f"{self._claim_link_base_url()}/raffle/prize/{token}"

    def _claim_link_is_open(self):
        """Whether the link of this draw can open or keep a claim."""
        self.ensure_one()
        draw = self.sudo()
        return bool(
            draw.claim_token
            and draw.claim_state == "none"
            and draw.winner_participant_id
            and draw.claim_deadline
            and draw.claim_deadline > fields.Datetime.now()
        )

    def _prize_claim_website_matches(self):
        """Whether the website of the current request may run this draw's
        claim: its raffle has no company, or the website's company.

        The claim pages read the draw as superuser, past the company rules
        of the raffle records, and the claim cart takes the website's
        company. True outside a website request.
        """
        self.ensure_one()
        website = getattr(request, "website", None) if request else None
        company = self.sudo().raffle_id.company_id
        return not (website and company and company != website.company_id)

    @api.model
    def _claim_link_find(self, token):
        """The draw whose open link carries `token`, as superuser, or empty.

        The lookup is an exact match on the unique index; the stored value
        is then compared in constant time. An unknown, forged, expired or
        used token gives the same empty result, and so does the link of a
        raffle of another company than the website's (see
        _prize_claim_website_matches()).
        """
        draws = self.sudo().browse()
        if (
            not isinstance(token, str)
            or not token.isascii()
            or not 16 <= len(token) <= 128
        ):
            return draws
        draw = draws.search([("claim_token", "=", token)], limit=1)
        if not draw or not consteq(draw.claim_token, token):
            return draws
        if not draw._claim_link_is_open():
            return draws
        return draw if draw._prize_claim_website_matches() else draws

    @api.model
    def _prize_claim_request_user(self):
        """The signed-in user of the current request, or an empty recordset
        outside a request and for a visitor who is not signed in."""
        users = self.env["res.users"]
        if not request or getattr(request, "session", None) is None:
            return users
        user = request.env.user
        if not user or user._is_public():
            return users
        return user

    def _prize_claim_is_winner(self, user):
        """Whether `user` is the winner of this draw: its contact is the
        draw's contact.

        Any user of that contact matches, since each one signs in as that
        person. A contact of the same company does not: a colleague of the
        winner is someone else.
        """
        self.ensure_one()
        partner = self.sudo().partner_id
        return bool(partner and user and user.partner_id == partner)

    @api.model
    def _prize_claim_user_draw(self, user):
        """The most recent draw whose link is open for `user`'s contact, on
        the website of the request, as superuser, or empty."""
        draws = self.sudo().browse()
        if not user:
            return draws
        candidates = draws.search(
            [
                ("partner_id", "=", user.partner_id.id),
                ("claim_state", "=", "none"),
                ("claim_token", "!=", False),
                ("claim_deadline", ">", fields.Datetime.now()),
            ],
            order="date desc, id desc",
        )
        return candidates.filtered(
            lambda d: d._claim_link_is_open()
            and d._prize_claim_website_matches()
        )[:1]

    @api.model
    def _prize_claim_session_draw(self):
        """The draw of the claim open for the current visitor, or empty.

        Only a signed-in winner holds a claim. The link the session opened
        comes first: its draw id and token are checked against the
        database on each call, so a claim settled or expired in another
        request ends here too, and its winner against the signed-in user,
        so a claim opened before another user signed in on the same
        browser ends as well. Without it, the user's most recent open link
        gives the claim.
        """
        draws = self.sudo().browse()
        user = self._prize_claim_request_user()
        if not user:
            return draws
        data = request.session.get(SESSION_KEY)
        if isinstance(data, dict):
            draw = self._claim_link_find(data.get("token"))
            if (
                draw
                and draw.id == data.get("draw_id")
                and draw._prize_claim_is_winner(user)
            ):
                return draw
        return self._prize_claim_user_draw(user)

    @api.model
    def _prize_claim_done_draw(self):
        """The draw whose prize this session reserved, as superuser, or
        empty.

        The session keeps the id of the last draw whose claim it confirmed
        (SESSION_DONE_KEY); the draw must still hold its prize, and its
        winner must be the signed-in user.
        """
        draws = self.sudo().browse()
        user = self._prize_claim_request_user()
        if not user:
            return draws
        draw_id = request.session.get(SESSION_DONE_KEY)
        if not isinstance(draw_id, int):
            return draws
        draw = draws.browse(draw_id).exists()
        if (
            not draw
            or draw.claim_state not in draw._prize_holding_states()
            or not draw._prize_claim_is_winner(user)
            or not draw._prize_claim_website_matches()
        ):
            return draws
        return draw

    def _claim_link_delay_minutes(self):
        """How long a link of this draw works: the link validity of the
        draw's token category, else the raffle's."""
        self.ensure_one()
        draw = self.sudo()
        minutes = (
            draw.band_id.claim_delay_minutes
            or draw.raffle_id.claim_delay_minutes
        )
        return max(minutes, 1)

    def _claim_link_issue(self):
        """Give this draw a new token and deadline, and schedule its expiry.

        A previous token stops working at once. Returns the token.
        """
        self.ensure_one()
        minutes = self._claim_link_delay_minutes()
        deadline = fields.Datetime.now() + timedelta(minutes=minutes)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        self.sudo().write(
            {
                "claim_token": token,
                "claim_deadline": deadline,
                "claim_link_end": False,
            }
        )
        cron = self.env.ref(
            "event_raffle_prize_claim.ir_cron_prize_claim_expire"
        )
        cron.sudo()._trigger(at=deadline)
        return token

    def _claim_link_lang(self):
        """Language of the messages to the winner: the contact's, else the
        current one."""
        self.ensure_one()
        return self.partner_id.lang or self.env.lang

    def _claim_link_message(self, url, signup=False):
        """Text of the message that carries the link, in the winner's
        language: the token earned when the draw has a token category, and
        the minutes the link lasts. With `signup`, `url` creates the
        winner's account first, and the text says so."""
        self.ensure_one()
        draw = self.with_context(lang=self._claim_link_lang())
        minutes = self._claim_link_delay_minutes()
        if draw.band_id:
            message = draw.env._(
                "You won a prize (%(token)s)! Choose it here: %(link)s "
                "(valid %(minutes)s minutes)",
                token=draw.sudo().band_id._token_label(),
                link=url,
                minutes=minutes,
            )
        else:
            message = draw.env._(
                "You won a prize! Choose it here: %(link)s (valid "
                "%(minutes)s minutes)",
                link=url,
                minutes=minutes,
            )
        if signup:
            message += "\n" + draw.env._(
                "This link first creates your account on the website, "
                "then opens your prize."
            )
        return message

    def _claim_link_signup_url(self, token):
        """URL that creates the winner's account, then opens the link of
        `token`; False when the winner's contact has a user, archived ones
        included, or when the draw has no contact.

        The link opens to a signed-in winner only. auth_signup's invitation
        token of the contact creates a portal user for that contact, signs
        it in and redirects to the link; it stops working once the user
        exists. It travels to the winner's own email only: whoever holds
        the bare link signs in, and never creates the winner's account.
        """
        self.ensure_one()
        partner = self.sudo().partner_id
        if not partner or partner.with_context(active_test=False).user_ids:
            return False
        partner.signup_prepare()
        signup = partner.with_context(
            relative_url=True
        )._get_signup_url_for_action(url=f"/raffle/prize/{token}")
        return f"{self._claim_link_base_url()}{signup[partner.id]}"

    def _claim_link_wizard(self):
        """The notify wizard that sends the link of this draw, as OdooBot.

        Refused when the claim is settled, when the draw has no winner, or
        when the winner cannot be reached.
        """
        self.ensure_one()
        self.check_access("write")
        if self.claim_state != "none":
            raise UserError(
                _("The prize of this draw is settled: no link is sent.")
            )
        if not self.winner_participant_id:
            raise UserError(_("This draw has no winner to send a link to."))
        wizard = self.env["event.raffle.draw.notify.wizard"].create(
            {"draw_id": self.id, "sender": "odoobot"}
        )
        if wizard.delivery == "none":
            raise UserError(wizard.delivery_info)
        return wizard

    def _claim_link_sent_note(self):
        """Note on the draw that the link went out, without the token."""
        self.ensure_one()
        self.message_post(
            body=_(
                "Prize link sent, valid %(minutes)s minutes, until "
                "%(deadline)s.",
                minutes=self._claim_link_delay_minutes(),
                deadline=self._claim_deadline_label(),
            )
        )

    def _claim_link_send(self, token=None):
        """Send the link of this draw with the notify wizard, as OdooBot.

        A new link is issued, unless `token` names the open link of this
        draw, which is then sent as it is. The wizard picks the chat or the
        email and logs the notification, whose text keeps the token masked.
        A winner without a contact gets one from the participant, since the
        link opens to the user of that contact only; a contact without a
        user receives the link through an account invitation (see
        _claim_link_signup_url()), which the log shows as the bare link,
        masked. Refused when the claim is settled or when the winner cannot
        be reached; nothing is issued then.
        """
        self.ensure_one()
        wizard = self._claim_link_wizard()
        if not token or self._claim_link_find(token) != self.sudo():
            self._prize_winner_partner()
            token = self._claim_link_issue()
        link = self._claim_link_url(token)
        signup_url = self._claim_link_signup_url(token)
        wizard.body = self._claim_link_message(
            signup_url or link, signup=bool(signup_url)
        )
        wizard.with_context(
            raffle_prize_claim_token=token,
            raffle_prize_claim_link=link,
            raffle_prize_claim_sent_url=signup_url,
        ).action_send()
        self._claim_link_sent_note()
        return True

    def _claim_link_auto_ready(self):
        """Whether the raffle sends this draw a link once it is drawn: the
        raffle sends links after each draw, the claim is open, the draw has
        a winner and at least one prize is available for them."""
        self.ensure_one()
        return bool(
            self.raffle_id.claim_auto_send
            and self.claim_state == "none"
            and self.winner_participant_id
            and self._prize_allowed_products()
        )

    def _claim_link_auto_issue(self):
        """Issue the link of a new draw before the messages that follow it,
        so that their {link} placeholder shows it. Returns the token, or
        False when the draw gets no link or the winner cannot be reached;
        nothing is issued then, and a winner who cannot be reached leaves
        a note on the draw.
        """
        self.ensure_one()
        if not self._claim_link_auto_ready():
            return False
        try:
            with self.env.cr.savepoint():
                self._claim_link_wizard()
                self._prize_winner_partner()
                return self._claim_link_issue()
        except UserError as error:
            self.message_post(
                body=_("The prize link could not be sent: %s", error.args[0])
            )
            return False

    def _claim_link_auto_send(self, token=None):
        """Send the link after a draw, when a prize is there to choose.

        `token` is the link issued before the draw's messages, sent as it
        is while it stays open. A send that fails leaves a note on the draw
        instead of failing the draw itself.
        """
        self.ensure_one()
        if self.claim_state != "none" or not self.winner_participant_id:
            return False
        if not self._prize_allowed_products():
            return False
        try:
            with self.env.cr.savepoint():
                self._claim_link_send(token=token)
        except UserError as error:
            self.message_post(
                body=_("The prize link could not be sent: %s", error.args[0])
            )
            return False
        return True

    def _draw_messages_send(self):
        """The link of a new draw is issued before its messages and sent
        after them.

        The winner notification and the channel announcement then show the
        link through {link}. A winner notification that went out with the
        link already gives it to the winner, so no second message carries
        it; otherwise the link message follows, with the same token.
        """
        self.ensure_one()
        token = self._claim_link_auto_issue()
        notified = super()._draw_messages_send()
        if not token or self._claim_link_find(token) != self.sudo():
            return notified
        if notified and self._message_uses(
            self.raffle_id.notify_winner_message, "link"
        ):
            self._claim_link_sent_note()
        else:
            self._claim_link_auto_send(token=token)
        return notified

    def _message_values(self, to_winner=False):
        """{link} gives the open prize link of this draw, empty otherwise.

        The winner alone may get the account invitation that opens it:
        while the notify wizard sends to a winner without an account, the
        context key `raffle_prize_claim_sent_url` names that URL.
        """
        values = super()._message_values(to_winner=to_winner)
        if not self._claim_link_is_open():
            return values
        token = self.sudo().claim_token
        link = self._claim_link_url(token)
        context = self.env.context
        if to_winner and context.get("raffle_prize_claim_token") == token:
            link = context.get("raffle_prize_claim_sent_url") or link
        values["link"] = link
        return values

    def action_claim_link_send(self):
        for draw in self:
            draw._claim_link_send()
        return True

    # ------------------------------------------------------------------
    # End of the claim
    # ------------------------------------------------------------------

    def _claim_staff(self):
        """This draw as OdooBot, in the language of the event staff.

        The notes and alerts of the link come from OdooBot. Their language
        is the one of the raffle's company contact, else the current one.
        """
        self.ensure_one()
        company = self.raffle_id.company_id or self.env.company
        lang = company.partner_id.lang or self.env.lang
        return self.with_user(SUPERUSER_ID).with_context(lang=lang)

    def _claim_alert(self, body):
        """Post `body` in the alert channel of the raffle, as OdooBot."""
        self.ensure_one()
        channel = self.sudo().raffle_id.claim_alert_channel_id
        if not channel:
            return False
        channel.with_user(SUPERUSER_ID).message_post(
            author_id=self.env.ref("base.partner_root").id,
            body=body,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        return True

    @api.ondelete(at_uninstall=False)
    def _unlink_cancel_claim_carts(self):
        """A deleted draw takes its claim carts along.

        The cart's `raffle_draw_id` becomes empty when the draw goes: left
        in draft, the cart would turn into an ordinary cart that still
        holds the free prize.
        """
        for draw in self:
            draw._claim_cancel_carts()

    def _claim_cancel_carts(self, keep=None):
        """Cancel the open carts of this draw's claim, but `keep`: the
        drafts, and the carts sent for payment, which the claim no longer
        confirms either."""
        self.ensure_one()
        carts = (
            self.env["sale.order"]
            .sudo()
            .search(
                [
                    ("raffle_draw_id", "=", self.id),
                    ("state", "in", ("draft", "sent")),
                ]
            )
        )
        if keep:
            carts -= keep.sudo()
        if carts:
            carts.with_context(disable_cancel_warning=True).action_cancel()
        return carts

    def _prize_claim_log_cart_line(self):
        """The prize line of this draw's most recent draft cart that holds
        one, as superuser, or an empty recordset.

        _claim_link_decline() and _claim_link_expire() write the claim
        state, which logs the claim, before they cancel the carts: the
        carts the winner left are still drafts here. A cart whose prize was
        removed holds no prize line, and the log then names no prize.
        """
        self.ensure_one()
        carts = (
            self.env["sale.order"]
            .sudo()
            .search(
                [("raffle_draw_id", "=", self.id), ("state", "=", "draft")],
                order="id desc",
            )
        )
        for cart in carts:
            lines = cart.order_line.filtered(
                lambda line: line.raffle_prize_sale_type == "claim"
            )
            if lines:
                return lines.sorted("id")[-1]
        return self.env["sale.order.line"].sudo()

    def _prize_claim(self, product, order=None):
        """A reserved prize closes the link: the winner chose it through
        the link, or an event user chose it for them."""
        order = super()._prize_claim(product, order=order)
        draw = self.sudo()
        if draw.claim_token:
            draw.write({"claim_token": False, "claim_link_end": "used"})
        self._claim_cancel_carts(keep=order)
        return order

    def _claim_link_decline(self, comment):
        """The winner declines the prize through the link.

        Nothing was reserved: the claim is declined, the link closed, the
        draft carts cancelled, and the alert channel is told.
        """
        self.ensure_one()
        comment = (comment or "").strip()
        if not comment:
            raise UserError(_("Say why you decline the prize."))
        if not self._claim_link_is_open():
            raise UserError(_("This prize link no longer works."))
        staff = self._claim_staff()
        staff.write(
            {
                "claim_state": "declined",
                "decline_comment": comment,
                "claim_token": False,
                "claim_link_end": "used",
            }
        )
        self._claim_cancel_carts()
        staff.message_post(
            body=staff.env._(
                "The winner declined the prize through the prize link: %s",
                comment,
            )
        )
        self._claim_alert(
            staff.env._(
                "The winner of draw #%(sequence)s (%(winner)s) in "
                "%(raffle)s declined the prize: %(comment)s",
                sequence=self.sequence,
                winner=self.winner_name or "",
                raffle=self.raffle_id.name,
                comment=comment,
            )
        )
        return True

    def _claim_link_expire(self):
        """Close the links whose deadline passed without a claim.

        Nothing was reserved, so no stock moves; any draft cart of the
        claim is cancelled and the alert channel is told.
        """
        now = fields.Datetime.now()
        for draw in self.sudo():
            if (
                draw.claim_state != "none"
                or not draw.claim_token
                or draw.claim_deadline > now
            ):
                continue
            staff = draw._claim_staff()
            staff.write(
                {
                    "claim_state": "expired",
                    "claim_token": False,
                    "claim_link_end": "expired",
                }
            )
            draw._claim_cancel_carts()
            staff.message_post(
                body=staff.env._(
                    "The prize link expired before the winner chose a prize."
                )
            )
            draw._claim_alert(
                staff.env._(
                    "The prize link of draw #%(sequence)s (%(winner)s) in "
                    "%(raffle)s expired.",
                    sequence=draw.sequence,
                    winner=draw.winner_name or "",
                    raffle=draw.raffle_id.name,
                )
            )
        return True

    @api.model
    def _cron_claim_link_expire(self):
        draws = self.sudo().search(
            [
                ("claim_state", "=", "none"),
                ("claim_token", "!=", False),
                ("claim_deadline", "<=", fields.Datetime.now()),
            ]
        )
        draws._claim_link_expire()
        return True

    # ------------------------------------------------------------------
    # Website
    # ------------------------------------------------------------------

    def _claim_deadline_label(self):
        """Deadline of the link as a time of day, in the event's zone."""
        self.ensure_one()
        tz = self.raffle_id.event_id.date_tz or self.env.context.get("tz")
        return format_time(
            self.env, self.claim_deadline, tz=tz or "UTC", time_format="short"
        )

    def _claim_banner_values(self):
        """What the claim banner of the shop shows for this draw."""
        self.ensure_one()
        left = (self.claim_deadline - fields.Datetime.now()).total_seconds()
        name = (self.winner_name or self.partner_id.name or "").strip()
        token = self.sudo().band_id._token_label()
        minutes = self._claim_link_delay_minutes()
        return {
            "first_name": name.split()[0] if name else "",
            "token_label": token,
            "delay_minutes": minutes,
            "token_line": _(
                "Your token: %(token)s, valid %(minutes)s minutes.",
                token=token,
                minutes=minutes,
            ),
            "deadline_label": self._claim_deadline_label(),
            "deadline_iso": self.claim_deadline.isoformat() + "Z",
            "minutes_left": max(0, math.ceil(left / 60)),
        }
