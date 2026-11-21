# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _is_add_to_cart_allowed(self):
        """A prize goes to the cart of a claim that allows it, or, without
        a claim, to an ordinary cart when it is sold to members while the
        sponsored shop window is open. Either way the website must sell it
        (see _raffle_website_sellable()). A claim session takes prizes
        only."""
        self.ensure_one()
        draw = self.env["event.raffle.draw"]._prize_claim_session_draw()
        if self.sudo().is_raffle_prize:
            if draw:
                return (
                    self.id in draw._prize_allowed_products().ids
                    and self._raffle_website_sellable()
                )
            return (
                self._raffle_member_sale_open()
                and super()._is_add_to_cart_allowed()
            )
        if draw:
            return False
        return super()._is_add_to_cart_allowed()

    def _raffle_website_sellable(self):
        """Whether the current website sells this product: website_sale's
        own add-to-cart rule (active, sellable, published on this website),
        without the claim rules of this module. The claim list of a draw
        (_prize_allowed_products()) holds every prize the winner may take
        in the backend, unpublished ones included: a website cart adds this
        check."""
        return super()._is_add_to_cart_allowed()

    def _raffle_member_sale_open(self):
        """Whether an ordinary cart may take this sponsored prize now."""
        self.ensure_one()
        return bool(
            self.sudo().raffle_member_sale_ok
            and self.env["event.raffle.config"]._sponsored_shop_is_open()
        )

    def _website_show_quick_add(self):
        """No quick add for a prize the visitor may only win (see
        product.template._raffle_shop_display())."""
        display = self.product_tmpl_id._raffle_shop_display()
        if display and display["token_only"]:
            return False
        return super()._website_show_quick_add()
