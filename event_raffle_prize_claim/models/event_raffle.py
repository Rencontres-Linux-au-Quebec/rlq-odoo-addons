# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class EventRaffle(models.Model):
    """Settings of the prize link, and its sending after each draw."""

    _inherit = "event.raffle"

    claim_delay_minutes = fields.Integer(
        string="Link Validity (minutes)",
        default=45,
        help="Minutes during which a prize link lets the winner choose a "
        "prize. Unused, the link expires and the alert channel is told.",
    )
    claim_auto_send = fields.Boolean(
        string="Send the Link After Each Draw",
        default=True,
        help="After each draw, the winner receives a prize link by chat or "
        "email, when at least one prize is available for them. The link "
        "opens once the winner is signed in; a winner without an account "
        "receives a link that creates it first.",
    )
    claim_alert_channel_id = fields.Many2one(
        "discuss.channel",
        string="Alert Channel",
        domain="[('channel_type', '=', 'channel')]",
        help="Discuss channel where OdooBot posts the expired and declined "
        "prize links.",
    )

    _sql_constraints = [  # noqa: RUF012
        (
            "claim_delay_minutes_positive",
            "CHECK(claim_delay_minutes > 0)",
            "The validity of the prize link must be at least one minute.",
        ),
    ]

    @api.ondelete(at_uninstall=False)
    def _unlink_cancel_claim_carts(self):
        """The draws of a deleted raffle go with it in the database, past
        their own delete hooks: their claim carts are cancelled here."""
        self.sudo().draw_ids._unlink_cancel_claim_carts()
