# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class EventRaffleDrawNotifyWizard(models.TransientModel):
    """The email of a prize link is written in the winner's language.

    The body is built in that language before the wizard sends it; while a
    prize link is sent (context key `raffle_prize_claim_token`), the email
    takes its subject in the same language. The note on the draw stays in
    the language of the user who sends.

    Any notification sent while the draw's link is open is sent as a prize
    link: {link} gives the winner the link, or the account invitation that
    opens it, and the log masks both (see event.raffle.draw.notification).
    """

    _inherit = "event.raffle.draw.notify.wizard"

    def _send_email(self, author, body_html):
        if not self.env.context.get("raffle_prize_claim_token"):
            return super()._send_email(author, body_html)
        lang = self.draw_id._claim_link_lang()
        wizard = self.with_context(lang=lang)
        mail = super(EventRaffleDrawNotifyWizard, wizard)._send_email(
            author, body_html
        )
        return mail.with_env(self.env)

    def action_send(self):
        self.ensure_one()
        draw = self.draw_id
        if (
            self.env.context.get("raffle_prize_claim_token")
            or not draw._claim_link_is_open()
        ):
            return super().action_send()
        token = draw.sudo().claim_token
        signup_url = draw._message_uses(
            self.body, "link"
        ) and draw._claim_link_signup_url(token)
        wizard = self.with_context(
            raffle_prize_claim_token=token,
            raffle_prize_claim_link=draw._claim_link_url(token),
            raffle_prize_claim_sent_url=signup_url,
        )
        return super(EventRaffleDrawNotifyWizard, wizard).action_send()
