# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class SaleOrder(models.Model):
    """The emails of a prize order say how the prize reaches the winner.

    The "Your prize" email of event_raffle_prize_claim becomes this
    module's own template, which adds the pick-up location, the email or
    the shipping (see event.raffle.draw._prize_handover_line()). Shipping
    the prize sends a second email with the tracking number, through the
    same sending: context key `raffle_prize_mail` set to "shipped".
    """

    _inherit = "sale.order"

    def _raffle_prize_mail_template(self):
        xmlid = "event_raffle_prize_handover.mail_template_prize_reserved"
        if self.env.context.get("raffle_prize_mail") == "shipped":
            xmlid = "event_raffle_prize_handover.mail_template_prize_shipped"
        return self.env.ref(xmlid, raise_if_not_found=False)

    def _raffle_prize_mail_values(self):
        """Besides the prize, its category and sponsor: `handover`, the
        sentence on how the prize reaches the winner, and the tracking
        number and carrier once it is shipped."""
        values = super()._raffle_prize_mail_values()
        order = self.sudo()
        draw = order.raffle_draw_id
        product = draw.prize_product_id or order._prize_lines().product_id[:1]
        values.update(
            {
                "handover": draw._prize_handover_line(product) if draw else "",
                "tracking_ref": draw.prize_tracking_ref or "",
                "carrier": draw.prize_carrier_name or "",
            }
        )
        return values

    def _raffle_prize_send_shipped_mail(self):
        """Email the winner that the prize is shipped, in their language."""
        self.ensure_one()
        return self.with_context(
            raffle_prize_mail="shipped"
        )._raffle_prize_send_mail()
