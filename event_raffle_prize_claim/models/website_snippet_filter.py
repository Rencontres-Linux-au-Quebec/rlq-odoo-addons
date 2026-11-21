# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class WebsiteSnippetFilter(models.Model):
    """Sponsored prizes in the product snippets.

    The product snippets (newest, recently sold or viewed, alternative
    products and accessories) build their own product lists, outside
    website.sale_product_domain(). Their values follow the shop instead:
    a sponsored prize the visitor may not see in the shop is left out
    (see website._raffle_prize_template_allowed()), and one whose dollar
    price is not offered to the visitor carries `raffle_shop_label`, which
    the price template of the snippets shows instead of the price (see
    product.template._raffle_shop_display()).
    """

    _inherit = "website.snippet.filter"

    def _filter_records_to_values(self, records, is_sample=False):
        values = super()._filter_records_to_values(records, is_sample)
        if is_sample or self.model_name != "product.product":
            return values
        website = self.env["website"].get_current_website()
        kept = []
        for data in values:
            record = data.get("_record")
            template = record
            if record._name == "product.product":
                template = record.product_tmpl_id
            if template and template.sudo().is_raffle_prize:
                if not website._raffle_prize_template_allowed(template):
                    continue
                display = template._raffle_shop_display()
                if display:
                    data["raffle_shop_label"] = display["label"]
            kept.append(data)
        return kept
