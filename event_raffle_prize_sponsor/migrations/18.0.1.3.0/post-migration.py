# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api
from odoo.tools import html_sanitize, is_html_empty

from odoo.addons.event_raffle_prize_sponsor.models.product_template import (
    SOURCE_LANG,
)


def migrate(cr, version):
    """Sponsored prizes keep the eCommerce description that the portal
    wrote.

    From this version on, the portal rewrites the eCommerce description
    while it equals raffle_sponsor_ecommerce_portal, the copy of the one
    the portal wrote last. The prizes saved before have no copy: one whose
    eCommerce description in SOURCE_LANG is still the one the portal makes
    of its sale description gets it, so the portal keeps updating it. Any
    other eCommerce description, rewritten in the backend, stays the
    organization's.
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
            ("raffle_sponsor_ecommerce_portal", "=", False),
            ("description_sale", "!=", False),
        ]
    )
    for template in templates:
        current = template.description_ecommerce
        if is_html_empty(current):
            continue
        vals = Template._raffle_sponsor_ecommerce_vals(
            template.description_sale
        )
        written = vals["raffle_sponsor_ecommerce_portal"]
        if html_sanitize(current, silent=True) == written:
            template.raffle_sponsor_ecommerce_portal = written
