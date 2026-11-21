# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    is_raffle_prize_carrier = fields.Boolean(
        string="For Raffle Prizes",
        help="Offered to the carts of a prize claim only, and never to "
        "the other carts.",
    )
