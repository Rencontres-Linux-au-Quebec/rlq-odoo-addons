# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models

TOKEN_MASK = "********"


class EventRaffleDrawNotification(models.Model):
    """The log of a prize link keeps the message without its token.

    The notify wizard logs the text it sends; the draw lists that text.
    While a prize link is sent, the context key `raffle_prize_claim_token`
    names the token, which the log replaces with a mask: the winner's chat
    or email carries the working link, the list of the draw does not. When
    the link went out as an account invitation, the context keys
    `raffle_prize_claim_sent_url` and `raffle_prize_claim_link` name the
    invitation URL and the bare link: the log shows the bare link, masked,
    and never the invitation token.
    """

    _inherit = "event.raffle.draw.notification"

    @api.model_create_multi
    def create(self, vals_list):
        context = self.env.context
        token = context.get("raffle_prize_claim_token")
        sent_url = context.get("raffle_prize_claim_sent_url")
        link = context.get("raffle_prize_claim_link")
        if token:
            for vals in vals_list:
                body = vals.get("body")
                if not body:
                    continue
                if sent_url and link:
                    body = body.replace(sent_url, link)
                vals["body"] = body.replace(token, TOKEN_MASK)
        return super().create(vals_list)
