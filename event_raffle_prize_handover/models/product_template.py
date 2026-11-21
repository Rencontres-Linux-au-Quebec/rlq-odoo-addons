# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class ProductTemplate(models.Model):
    """Virtual prizes: sent by email, never picked up nor shipped.

    A virtual prize keeps its stock, one unit per code or licence. Its
    claim cart asks for a name and an email only, and an event user sends
    it with the Send the Virtual Prize button of the draw.
    """

    _inherit = "product.template"

    raffle_virtual_prize = fields.Boolean(
        string="Virtual prize (no delivery)",
        help="The winner receives this prize by email: the checkout asks "
        "for no address, and the draw's Send the Virtual Prize button "
        "emails the instructions below with an optional code.",
    )
    raffle_virtual_instructions = fields.Html(
        string="Virtual prize instructions",
        translate=True,
        help="Message emailed to the winner of this virtual prize, in "
        "their language: how to use it. The event user may complete it "
        "before sending, and adds the code apart.",
    )
