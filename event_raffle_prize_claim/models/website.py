# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, models
from odoo.http import request
from odoo.osv import expression
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang


class Website(models.Model):
    """Shop of a prize claim, and of the sponsored prizes.

    With a claim open for the signed-in winner (see
    event.raffle.draw._prize_claim_session_draw()), every product list
    that website_sale
    builds from sale_product_domain() (the shop, its search, the
    alternative products of a product page and the sitemap) holds the
    prizes allowed to its winner only, and the cart is the claim cart, in
    the winner's name. Without a claim, those lists hold the sponsored
    prizes while the sponsored shop window is open
    (event.raffle.config._sponsored_shop_is_open()), and leave them out
    otherwise. The product snippets, which build their lists without
    sale_product_domain(), apply the same rule to sponsored prizes (see
    website.snippet.filter).
    """

    _inherit = "website"

    def sale_product_domain(self):
        domain = super().sale_product_domain()
        draw = self.env["event.raffle.draw"]._prize_claim_session_draw()
        if draw:
            templates = draw._prize_allowed_products().product_tmpl_id
            return expression.AND([domain, [("id", "in", templates.ids)]])
        if self._raffle_sponsored_shop_is_open():
            return domain
        return expression.AND([domain, [("is_raffle_prize", "=", False)]])

    def _raffle_sponsored_shop_is_open(self):
        return self.env["event.raffle.config"]._sponsored_shop_is_open()

    def _raffle_prize_template_allowed(self, template):
        """Whether the visitor may see the sponsored prize `template`: the
        claim of the session allows it, or, without a claim, the sponsored
        shop window is open."""
        draw = self.env["event.raffle.draw"]._prize_claim_session_draw()
        if not draw:
            return self._raffle_sponsored_shop_is_open()
        allowed = draw._prize_allowed_products().product_tmpl_id
        return template.id in allowed.ids

    def _raffle_shop_stock(self, templates):
        """Remaining quantity of the storable products of `templates`, as
        the shop cards show it: {template id: (quantity, label)}.

        A variant counts what this website can still sell of it: the free
        quantity that website_sale_stock gives (_get_product_available_qty(),
        the website's warehouse), and for a raffle prize the free quantity
        of event_raffle_prize (raffle_qty_free), the stock of the prize
        warehouse that no move holds, a prize reserved by a claim included.
        A template sums its variants, each counted from zero up. A product
        that is not storable is left out, and so is a sold out product that
        the shop still sells beyond its stock (allow_out_of_stock_order),
        whose product page shows no out of stock message either.

        The variants are read as one recordset: each free quantity is
        computed once for all of them, so the queries do not grow with the
        number of products.
        """
        self.ensure_one()
        # sudo: stock quants and warehouses are not readable by visitors,
        # as in website_sale_stock.
        templates = templates.sudo().filtered("is_storable")
        stock = {}
        for template in templates:
            quantity = 0.0
            for product in template.product_variant_ids:
                if template.is_raffle_prize:
                    free = product.raffle_qty_free
                else:
                    free = self._get_product_available_qty(product)
                quantity += max(free, 0.0)
            rounding = template.uom_id.rounding
            if float_is_zero(quantity, precision_rounding=rounding):
                if template.allow_out_of_stock_order:
                    continue
                quantity = 0.0
            stock[template.id] = (
                quantity,
                self._raffle_shop_stock_label(quantity),
            )
        return stock

    def _raffle_shop_stock_label(self, quantity):
        """The label of `quantity` on a shop card, in the visitor's
        language: "3 left", "1 left" or "Out of stock". A fractional
        quantity keeps two decimals."""
        if quantity <= 0:
            return self.env._("Out of stock")
        if quantity == 1:
            return self.env._("1 left")
        digits = 0 if float(quantity).is_integer() else 2
        return self.env._(
            "%s left", formatLang(self.env, quantity, digits=digits)
        )

    def sale_get_order(self, force_create=False):
        draw = self.env["event.raffle.draw"]._prize_claim_session_draw()
        if not draw:
            order = super().sale_get_order(force_create=force_create)
            if order.raffle_draw_id:
                # The claim of this cart has ended: start over without it.
                self.sale_reset()
                order = super().sale_get_order(force_create=force_create)
            return order
        return self._raffle_prize_cart(draw, force_create)

    def _raffle_prize_cart(self, draw, force_create):
        """The claim cart of the session for `draw`, created when asked.

        Mirrors website_sale's sale_get_order(): the cart is created as
        superuser, kept in the session, and returned as sudo for the
        current user. It is in the winner's name from the start, so the
        checkout reads the winner's contact and address.
        """
        self.ensure_one()
        website = self.with_company(self.company_id)
        SaleOrder = website.env["sale.order"].sudo()
        order = SaleOrder.browse(request.session.get("sale_order_id")).exists()
        if (
            order.raffle_draw_id != draw
            or order.state != "draft"
            or order.website_id != self
        ):
            order = SaleOrder
        if not order:
            request.session.pop("sale_order_id", None)
            request.session.pop("website_sale_cart_quantity", None)
            if not force_create:
                return self.env["sale.order"]
            partner = draw._prize_winner_partner().sudo()
            values = website._prepare_sale_order_values(partner)
            # The winner's contact is the address too, until the winner
            # picks another one at the checkout.
            values.update(
                raffle_draw_id=draw.id,
                partner_invoice_id=partner.id,
                partner_shipping_id=partner.id,
            )
            order = SaleOrder.with_user(SUPERUSER_ID).create(values)
            request.session["sale_order_id"] = order.id
        request.session["website_sale_cart_quantity"] = order.cart_quantity
        return order.with_user(self.env.user).sudo()
