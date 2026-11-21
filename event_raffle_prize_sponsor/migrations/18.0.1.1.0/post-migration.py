# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api
from odoo.tools import is_html_empty

from odoo.addons.event_raffle_prize_sponsor.models.product_template import (
    SOURCE_LANG,
)


def migrate(cr, version):
    """Sponsored prizes get an eCommerce description from their sale
    description.

    The portal fills both descriptions of a prize from this version on.
    A sponsored prize saved before, archived ones included, whose
    eCommerce description is empty in SOURCE_LANG gets the one the portal
    makes of its sale description in that language; a filled eCommerce
    description is kept.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Template = env["product.template"].with_context(
        active_test=False, lang=SOURCE_LANG
    )
    templates = Template.search(
        [
            ("is_raffle_prize", "=", True),
            ("raffle_sponsor_id", "!=", False),
            ("description_sale", "!=", False),
        ]
    )
    for template in templates:
        if is_html_empty(template.description_ecommerce):
            template.write(
                Template._raffle_sponsor_ecommerce_vals(
                    template.description_sale
                )
            )
