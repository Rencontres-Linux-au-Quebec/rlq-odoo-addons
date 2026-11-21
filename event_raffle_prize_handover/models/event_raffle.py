# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class EventRaffle(models.Model):
    _inherit = "event.raffle"

    prize_pickup_location = fields.Char(
        string="Pick-up location",
        help='Where on-site winners pick up a physical prize. The "Your '
        'prize" email and the confirmation page give it.',
    )
