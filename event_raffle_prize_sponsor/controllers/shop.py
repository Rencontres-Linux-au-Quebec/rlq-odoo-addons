# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.http import request
from odoo.osv import expression
from odoo.tools import lazy

from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleRaffleSponsor(WebsiteSale):
    """The shop category of the sponsored prizes, in the shop filters.

    website_sale lists every top-level public category of the website,
    whatever the visitor may buy. The sponsored category holds prizes,
    which the shop hides from most visitors (see website
    sale_product_domain() in event_raffle_prize_claim): it is listed only
    while it holds a published product of that domain, so a visitor never
    opens an empty category. A search lists it as before, among the
    categories of the products found.
    """

    def _get_additional_extra_shop_values(self, values, **post):
        extra = super()._get_additional_extra_shop_values(values, **post)
        categories = extra.get("categories", values.get("categories"))
        if categories is not None:
            extra["categories"] = lazy(
                self._raffle_sponsor_shop_categories, categories
            )
        return extra

    def _raffle_sponsor_shop_categories(self, categories):
        """`categories` without the sponsored category when the visitor
        may see none of its products. One count query, made only when the
        category is in the list."""
        category = request.env["product.template"]._raffle_sponsored_category()
        if not category or category not in categories:
            return categories
        domain = expression.AND(
            [
                request.website.sale_product_domain(),
                [
                    ("is_published", "=", True),
                    ("public_categ_ids", "child_of", category.id),
                ],
            ]
        )
        if request.env["product.template"].search_count(domain, limit=1):
            return categories
        return categories - category
