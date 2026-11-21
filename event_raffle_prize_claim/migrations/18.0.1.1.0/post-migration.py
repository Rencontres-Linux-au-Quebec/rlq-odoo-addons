# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Sponsored prizes stop selling once out of stock.

    A claim and a member purchase share the prize stock: the prizes saved
    before this version still allow out-of-stock orders, the default of
    website_sale_stock, and are switched off here.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["product.template"].with_context(active_test=False).search(
        [("is_raffle_prize", "=", True)]
    ).write({"allow_out_of_stock_order": False})
