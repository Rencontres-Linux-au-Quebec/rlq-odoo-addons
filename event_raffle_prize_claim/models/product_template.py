# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re
from urllib.parse import urlsplit

from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    """Sponsored prizes as the website shows and sells them.

    The sponsor is a contact, which website visitors may not read: its name
    and website are computed as superuser for the shop pages. The link is
    kept only when it is an http or https address; a bare domain gets
    https, and any other scheme drops the link.

    A sponsored prize never sells beyond its stock (`allow_out_of_stock_order`
    is forced off on create and write), since the claims take from the same
    stock. Its shop display depends on the visitor (see
    _raffle_shop_display()).
    """

    _inherit = "product.template"

    raffle_sponsor_name = fields.Char(
        string="Sponsor Name",
        compute="_compute_raffle_sponsor_display",
        compute_sudo=True,
    )
    raffle_sponsor_url = fields.Char(
        string="Sponsor Link",
        compute="_compute_raffle_sponsor_display",
        compute_sudo=True,
    )

    @api.depends("raffle_sponsor_id.name", "raffle_sponsor_id.website")
    def _compute_raffle_sponsor_display(self):
        for template in self:
            sponsor = template.raffle_sponsor_id
            template.raffle_sponsor_name = sponsor.name or False
            template.raffle_sponsor_url = self._raffle_safe_url(
                sponsor.website
            )

    @api.model
    def _raffle_safe_url(self, url):
        url = (url or "").strip()
        if not url:
            return False
        if not re.match(r"^https?://", url, re.IGNORECASE):
            if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.IGNORECASE):
                return False
            url = f"https://{url}"
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return False
        return url

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._raffle_stop_out_of_stock_sales()
        return templates

    def write(self, vals):
        result = super().write(vals)
        if {"is_raffle_prize", "allow_out_of_stock_order"} & set(vals):
            self._raffle_stop_out_of_stock_sales()
        return result

    def _raffle_stop_out_of_stock_sales(self):
        selling = self.filtered(
            lambda t: t.is_raffle_prize and t.allow_out_of_stock_order
        )
        if selling:
            selling.write({"allow_out_of_stock_order": False})

    def _raffle_token_cost_label(self):
        """The cost of this prize for a winner: one token of its category."""
        self.ensure_one()
        return self.raffle_band_id._token_label()

    def _raffle_shop_display(self):
        """How the website shop shows this product, or False for as usual.

        Returns a dict for a sponsored prize whose dollar price is not
        offered to the visitor: `label` replaces the price, and
        `token_only` (no add to cart) is set for a visitor without a claim.
        A winner with an open prize link reads the token cost of each
        prize; any other visitor reads the price of a prize sold to
        members, and "Prize only" with its token for the others.
        """
        self.ensure_one()
        template = self.sudo()
        if not template.is_raffle_prize:
            return False
        if self.env["event.raffle.draw"]._prize_claim_session_draw():
            return {
                "label": template._raffle_token_cost_label(),
                "token_only": False,
            }
        if template.raffle_member_sale_ok:
            return False
        band = template.raffle_band_id
        label = (
            _("Prize only: %s", band._token_label())
            if band
            else _("Prize only")
        )
        return {"label": label, "token_only": True}

    def _get_combination_info(
        self,
        combination=False,
        product_id=False,
        add_qty=1.0,
        parent_combination=False,
        only_template=False,
    ):
        """The prices of a sponsored prize whose shop display replaces the
        price (see _raffle_shop_display()), or that the visitor may not see
        (see website._raffle_prize_template_allowed()), are 0.

        The product page and the shop cards hide those prices, and this
        dict also reaches the visitor as it is, through the variant data
        route of the product page. `prevent_zero_price_sale` keeps the
        value of the real price, so that a winner still adds the prize to
        the cart on a website that hides the add to cart of free products.

        The rule follows the product the dict prices: website_sale prices
        the variant `product_id` without checking that it belongs to this
        template, so the template of that variant decides.
        """
        info = super()._get_combination_info(
            combination=combination,
            product_id=product_id,
            add_qty=add_qty,
            parent_combination=parent_combination,
            only_template=only_template,
        )
        priced = (
            self.env["product.product"].sudo().browse(info.get("product_id"))
        )
        template = (priced.product_tmpl_id or self).with_env(self.env)
        if len(template) == 1 and template._raffle_price_hidden():
            for key in (
                "price",
                "list_price",
                "price_extra",
                "base_unit_price",
            ):
                if key in info:
                    info[key] = 0.0
            info["compare_list_price"] = None
            info["has_discounted_price"] = False
            info.pop("product_tracking_info", None)
        return info

    def _raffle_price_hidden(self):
        """Whether the website hides the price of this product from the
        current visitor."""
        self.ensure_one()
        template = self.sudo()
        if not template.is_raffle_prize:
            return False
        website = self.env["website"].get_current_website()
        return bool(
            self._raffle_shop_display()
            or not website._raffle_prize_template_allowed(template)
        )

    def _search_render_results(self, fetch_fields, mapping, icon, limit):
        """The search suggestions of the shop give the token cost, or
        "Prize only", where the shop cards do."""
        results = super()._search_render_results(
            fetch_fields, mapping, icon, limit
        )
        if "detail" not in mapping:
            return results
        for template, data in zip(self, results, strict=False):
            display = template._raffle_shop_display()
            if display:
                data["price"] = display["label"]
                data.pop("list_price", None)
        return results

    def _website_show_quick_add(self):
        display = self._raffle_shop_display()
        if display and display["token_only"]:
            return False
        return super()._website_show_quick_add()
