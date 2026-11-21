# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from urllib.parse import urlencode

from werkzeug.exceptions import NotFound

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request, route
from odoo.tools import lazy

from odoo.addons.sale.controllers.portal import (
    PaymentPortal as SalePaymentPortal,
)
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.website_sale.controllers.payment import PaymentPortal
from odoo.addons.website_sale.controllers.product_configurator import (
    WebsiteSaleProductConfiguratorController,
)
from odoo.addons.website_sale.controllers.variant import (
    WebsiteSaleVariantController,
)

from ..models.event_raffle_draw import (
    SESSION_DONE_KEY,
    SESSION_ERROR_KEY,
    SESSION_KEY,
)

COMMENT_MAX_LENGTH = 2000


def _session_draw():
    return request.env["event.raffle.draw"]._prize_claim_session_draw()


def _flush_as_superuser(record):
    """Write the pending changes of `record`'s superuser environment.

    A claim cancels or confirms cart lines as superuser. Left pending, those
    changes are flushed by the next search of the page, in the visitor's
    environment, which may not read sale order lines.
    """
    record.env.flush_all()


def _end_claim_session():
    request.session.pop(SESSION_KEY, None)
    request.session.pop(SESSION_ERROR_KEY, None)
    request.website.sale_reset()


def _invalid_link_page():
    """The one answer to every link that does not open a claim.

    Unknown, forged, expired and used links read the same, with the same
    status, so that the page tells nothing about the token.
    """
    return request.render(
        "event_raffle_prize_claim.claim_link_invalid", {}, status=404
    )


def _login_url(path):
    return "/web/login?" + urlencode({"redirect": path})


class RafflePrizeClaim(http.Controller):
    """Public pages of the prize link.

    The link opens to its winner only: a visitor who is not signed in goes
    to the sign-in page, which comes back to the link, and a user who did
    not win gets a refusal that says nothing of the winner. Every page
    reads the claim from the request (see
    event.raffle.draw._prize_claim_session_draw()) and checks its token and
    its winner again before it acts, as superuser, on that draw only: the
    session holds the draw id and the token the winner opened, never a
    draw id taken from the request.
    """

    @route(
        "/raffle/prize/<string:token>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def raffle_prize_link(self, token, **kwargs):
        draw = request.env["event.raffle.draw"]._claim_link_find(token)
        if not draw:
            return _invalid_link_page()
        path = f"/raffle/prize/{token}"
        user = draw._prize_claim_request_user()
        if not user:
            return request.redirect(_login_url(path))
        if not draw._prize_claim_is_winner(user):
            # Signing out leads back to the sign-in page, then to the link.
            logout_url = "/web/session/logout?" + urlencode(
                {"redirect": _login_url(path)}
            )
            return request.render(
                "event_raffle_prize_claim.claim_link_other_account",
                {"logout_url": logout_url},
                status=403,
            )
        request.session[SESSION_KEY] = {"draw_id": draw.id, "token": token}
        request.session.pop(SESSION_DONE_KEY, None)
        request.session.pop(SESSION_ERROR_KEY, None)
        return request.redirect("/shop")

    @route(
        "/raffle/prize/decline",
        type="http",
        auth="public",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
    )
    def raffle_prize_decline(self, comment=None, **kwargs):
        draw = _session_draw()
        if not draw:
            return _invalid_link_page()
        values = {"comment": "", "error": False}
        if request.httprequest.method == "POST":
            comment = (comment or "").strip()[:COMMENT_MAX_LENGTH]
            if comment:
                draw._claim_link_decline(comment)
                _flush_as_superuser(draw)
                _end_claim_session()
                return request.render(
                    "event_raffle_prize_claim.claim_declined", {}
                )
            values["error"] = True
        return request.render("event_raffle_prize_claim.claim_decline", values)

    @route(
        "/raffle/prize/done",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def raffle_prize_done(self, **kwargs):
        draw = request.env["event.raffle.draw"]._prize_claim_done_draw()
        if not draw:
            return request.redirect("/shop")
        template = draw.prize_product_id.product_tmpl_id
        name = (draw.winner_name or "").strip()
        return request.render(
            "event_raffle_prize_claim.claim_done",
            {
                "first_name": name.split()[0] if name else "",
                "prize_name": draw.prize_product_id.with_context(
                    display_default_code=False
                ).display_name,
                "sponsor_name": template.raffle_sponsor_name,
                "sponsor_url": template.raffle_sponsor_url,
            },
        )


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class WebsiteSaleRafflePrize(WebsiteSale):
    """Guards of the shop routes that a product list does not cover.

    The checkout of a claim cart is the signed-in winner's own, as any
    checkout of the shop: the claim opens to that user only.

    The shop page also gets the remaining quantity of its products
    (`raffle_shop_stock`, see website._raffle_shop_stock()), computed
    once for the page when a card first reads it.
    """

    def _get_additional_extra_shop_values(self, values, **post):
        extra = super()._get_additional_extra_shop_values(values, **post)
        products = values.get("products")
        if products is not None:
            extra["raffle_shop_stock"] = lazy(
                request.website._raffle_shop_stock, products
            )
        return extra

    @route()
    def product(self, product, category="", search="", **kwargs):
        template = product.sudo()
        if template.is_raffle_prize and not (
            request.website._raffle_prize_template_allowed(template)
        ):
            raise NotFound()
        return super().product(product, category, search, **kwargs)

    @route()
    def shop_payment_confirmation(self, **post):
        """A claim order ends on the prize page, which shows no price."""
        order_id = request.session.get("sale_last_order_id")
        if isinstance(order_id, int):
            order = request.env["sale.order"].sudo().browse(order_id).exists()
            if order.raffle_draw_id:
                return request.redirect("/raffle/prize/done")
        return super().shop_payment_confirmation(**post)

    @route()
    def shop_payment_validate(self, sale_order_id=None, **post):
        draw = _session_draw()
        if draw and sale_order_id is None:
            order = request.website.sale_get_order()
            if order and order.raffle_draw_id == draw:
                return self._raffle_prize_confirm(draw, order)
        done_id = request.session.get(SESSION_DONE_KEY)
        if done_id and (
            self._raffle_prize_validated_order(sale_order_id).raffle_draw_id.id
            == done_id
        ):
            # A second submit of the claim cart already confirmed. Any
            # other order of the session goes through website_sale.
            return request.redirect("/raffle/prize/done")
        if self._raffle_prize_stale_cart():
            # The claim of this cart ended in another request: the cart
            # was cancelled, and website_sale must not try to confirm it.
            _end_claim_session()
            request.session.pop("sale_last_order_id", None)
            return _invalid_link_page()
        return super().shop_payment_validate(
            sale_order_id=sale_order_id, **post
        )

    def _raffle_prize_validated_order(self, sale_order_id):
        """The order that website_sale's payment validation reads: the
        given one, else the cart, else the last order of the session."""
        SaleOrder = request.env["sale.order"].sudo()
        if sale_order_id is not None:
            order_id = _int_or_none(sale_order_id)
            return (
                SaleOrder.browse(order_id).exists() if order_id else SaleOrder
            )
        order = request.website.sale_get_order()
        last_id = request.session.get("sale_last_order_id")
        if not order and isinstance(last_id, int):
            order = SaleOrder.browse(last_id).exists()
        return order

    def _raffle_prize_stale_cart(self):
        """Whether the session's cart is a claim cart left unconfirmed."""
        SaleOrder = request.env["sale.order"].sudo()
        for key in ("sale_order_id", "sale_last_order_id"):
            order_id = request.session.get(key)
            if not isinstance(order_id, int):
                continue
            order = SaleOrder.browse(order_id).exists()
            if order.raffle_draw_id and order.state != "sale":
                return True
        return False

    def _raffle_prize_confirm(self, draw, order):
        """Confirm the claim cart: the prize claim of the draw runs in it.

        A refusal (the last unit taken, the quota reached, a rule no longer
        met) rolls the confirmation back, empties the cart and sends the
        winner back to the shop with the reason; the link keeps working
        until its deadline. A serialization error is not caught: the
        request is retried on a fresh snapshot, where the claim of the
        other request shows.
        """
        lines = order._prize_lines()
        if not lines:
            return request.redirect("/shop/cart")
        if self._get_shop_payment_errors(order):
            return request.redirect("/shop/payment")
        # The claim's own rules first: a prize whose last unit went to
        # another winner or a member reads the claim's reason, before the
        # stock check of the cart refuses it with a generic one.
        refusal = draw._prize_refusal(lines.product_id[:1])
        if refusal:
            return self._raffle_prize_refused(order, refusal)
        try:
            order._check_cart_is_ready_to_be_paid()
        except UserError:
            return request.redirect("/shop/checkout")
        try:
            with request.env.cr.savepoint():
                order._validate_order()
        except UserError as error:
            return self._raffle_prize_refused(order, error.args[0])
        _flush_as_superuser(order)
        _end_claim_session()
        request.session[SESSION_DONE_KEY] = draw.id
        request.session["sale_last_order_id"] = order.id
        return request.redirect("/raffle/prize/done")

    def _raffle_prize_refused(self, order, reason):
        """Empty the claim cart and send the winner back to the shop with
        `reason`; the link keeps working until its deadline."""
        order._prize_lines().unlink()
        _flush_as_superuser(order)
        request.session[SESSION_ERROR_KEY] = reason
        return request.redirect("/shop")

    def _get_additional_notification_information(self, line):
        """The add-to-cart notification of a claim line gives its token
        cost, which the notification shows instead of the line's amount
        (see static/src/js/cart_notification.js)."""
        values = super()._get_additional_notification_information(line)
        if line._is_raffle_prize_claim_line():
            values["raffle_token_label"] = (
                line.product_id.product_tmpl_id._raffle_token_cost_label()
            )
        return values

    def _raffle_prize_onsite_claim(self):
        draw = _session_draw()
        return bool(draw) and draw._prize_winner_mode() == "onsite"

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        """An on-site winner takes the prize at the event: a name and an
        email are enough, whatever the country requires."""
        if self._raffle_prize_onsite_claim():
            return {"name", "email"}
        return super()._get_mandatory_delivery_address_fields(country_sudo)

    def _get_mandatory_billing_address_fields(self, country_sudo):
        if self._raffle_prize_onsite_claim():
            return {"name", "email"}
        return super()._get_mandatory_billing_address_fields(country_sudo)


class PaymentPortalRafflePrize(PaymentPortal):
    """A claim cart costs nothing and is confirmed by its claim: the shop
    never opens a payment transaction for it, express checkout
    included."""

    @route()
    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        """Refuse a claim cart once the access token is checked.

        An unknown order or a wrong token goes to website_sale, which
        answers it the same whatever the order is: the refusal of a claim
        cart is read only by whoever holds the cart's token.
        """
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token
            )
        except (AccessError, MissingError):
            return super().shop_payment_transaction(
                order_id, access_token, **kwargs
            )
        if order_sudo.raffle_draw_id:
            raise UserError(_("A prize order is confirmed without payment."))
        return super().shop_payment_transaction(
            order_id, access_token, **kwargs
        )


class SalePortalRafflePrize(SalePaymentPortal):
    """The payment of an order from the customer portal refuses what the
    shop's payment refuses: a claim cart, and a website order holding a
    sponsored prize it may not pay for now (see
    sale.order._raffle_check_payable()).

    The refusal comes once the access token is checked, as on the shop's
    transaction route: an unknown order or a wrong token goes to sale,
    which answers it the same whatever the order is.
    """

    @route()
    def portal_order_transaction(self, order_id, access_token, **kwargs):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token
            )
        except (AccessError, MissingError):
            return super().portal_order_transaction(
                order_id, access_token, **kwargs
            )
        order_sudo._raffle_check_payable()
        return super().portal_order_transaction(
            order_id, access_token, **kwargs
        )


def _raffle_prize_hidden(templates):
    """Whether `templates` holds a sponsored prize that the visitor may not
    see (see website._raffle_prize_template_allowed())."""
    website = request.website
    return any(
        template.is_raffle_prize
        and not website._raffle_prize_template_allowed(template)
        for template in templates.sudo().exists()
    )


class WebsiteSaleVariantRafflePrize(WebsiteSaleVariantController):
    """The variant data of a product page answers for the sponsored prizes
    that the visitor may see only, as the product page does (see
    website._raffle_prize_template_allowed()); the prices it holds follow
    product.template._get_combination_info().

    website_sale prices the variant `product_id` without checking that it
    belongs to `product_template_id`: the template of that variant is
    checked as well.
    """

    @route()
    def get_combination_info_website(
        self,
        product_template_id,
        product_id,
        combination,
        add_qty,
        parent_combination=None,
        **kwargs,
    ):
        env = request.env
        templates = env["product.template"].browse(
            _int_or_none(product_template_id)
        )
        variant = (
            env["product.product"].sudo().browse(_int_or_none(product_id))
        )
        templates |= variant.exists().product_tmpl_id
        if _raffle_prize_hidden(templates):
            raise NotFound()
        return super().get_combination_info_website(
            product_template_id,
            product_id,
            combination,
            add_qty,
            parent_combination=parent_combination,
            **kwargs,
        )


class WebsiteSaleProductConfiguratorRafflePrize(
    WebsiteSaleProductConfiguratorController
):
    """The product configurator of the website follows the shop display of
    the sponsored prizes, as the variant data route does.

    Its routes read a template by id in the visitor's environment, which
    reads any published product, and price it through the configurator
    hooks, not through product.template._get_combination_info(). A prize
    the visitor may not see answers 404 as the configured product, and is
    left out of the optional products; a prize whose shop display
    replaces the price (see product.template._raffle_price_hidden()) is
    priced 0. `can_be_sold` keeps the value of the real price, as
    `prevent_zero_price_sale` does on the product page. The routes of the
    backend (outside a website request) are left as they are.
    """

    def _get_product_template(self, product_template_id):
        template = super()._get_product_template(product_template_id)
        if request.is_frontend and _raffle_prize_hidden(template):
            raise NotFound()
        return template

    def _should_show_product(self, product_template, parent_combination):
        if request.is_frontend and _raffle_prize_hidden(product_template):
            return False
        return super()._should_show_product(
            product_template, parent_combination
        )

    def _get_basic_product_information(
        self, product_or_template, pricelist, combination, **kwargs
    ):
        values = super()._get_basic_product_information(
            product_or_template, pricelist, combination, **kwargs
        )
        if _raffle_price_hidden(product_or_template):
            values["price"] = 0.0
            values.pop("strikethrough_price", None)
        return values

    def _get_ptav_price_extra(self, ptav, currency, date, product_or_template):
        if _raffle_price_hidden(product_or_template):
            return 0.0
        return super()._get_ptav_price_extra(
            ptav, currency, date, product_or_template
        )


def _raffle_price_hidden(product_or_template):
    """Whether the website hides the price of `product_or_template`, a
    product or a template, from the visitor; False outside a website
    request."""
    if not request.is_frontend:
        return False
    template = product_or_template
    if template._name == "product.product":
        template = template.product_tmpl_id
    return len(template) == 1 and template._raffle_price_hidden()
