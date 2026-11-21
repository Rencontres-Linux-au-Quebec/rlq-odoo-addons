# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, _, models
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    """Carts of a prize claim, and member purchases of sponsored prizes.

    A claim cart is a website order whose `raffle_draw_id` is set from the
    start. It holds one unit of one prize at no charge, besides its free
    delivery line, and only the carriers marked for raffle prizes are
    offered to it. Confirming it runs the prize claim of the draw, under
    the claim's locks and rules, which then confirms it, and sends the
    "Your prize" email instead of the order confirmation.

    An ordinary cart takes a sponsored prize only when the prize is sold
    to members and the sponsored shop window is open; it is then paid and
    confirmed like any other order. A prize that is not sold to members
    never leaves through an ordinary website order.
    """

    _inherit = "sale.order"

    def _raffle_wanted_qty(self, line, add_qty, set_qty):
        """Quantity the cart update asks for, as website_sale reads it.

        A `set_qty` other than 0 sets the quantity; otherwise `add_qty` is
        added to the line's, and an `add_qty` of None (the cart page's
        quantity input and delete button send `set_qty` only) sets 0.
        """
        try:
            set_qty = int(set_qty) if set_qty else 0
        except (TypeError, ValueError):
            set_qty = 0
        if set_qty:
            return set_qty
        if add_qty is None:
            return 0
        try:
            add_qty = int(add_qty) if add_qty else 0
        except (TypeError, ValueError):
            add_qty = 1
        return (line.product_uom_qty if line else 0) + add_qty

    def _cart_update(
        self, product_id, line_id=None, add_qty=0, set_qty=0, **kwargs
    ):
        """Keep prizes out of the ordinary carts, and one prize unit in a
        claim cart.

        website_sale checks whether a product may be added only when
        `add_qty` is given; this check covers `set_qty` as well. A claim
        cart takes a prize that the claim allows and that the website sells
        (see product.product._raffle_website_sellable()). Adding a prize to
        a claim cart replaces the prize it held.

        An update that removes or lowers a line is never refused: it
        reaches website_sale as the quantity it sets, past website_sale's
        own add check, which refuses any non-zero `add_qty` of a product
        that may no longer be added. A prize that stops being for sale
        thus leaves the cart it is in.
        """
        self.ensure_one()
        product = self.env["product.product"].sudo().browse(product_id)
        product = product.exists()
        line = self.env["sale.order.line"]
        if line_id is not False:
            line = self._cart_find_product_line(product_id, line_id, **kwargs)
            line = line[:1]
        wanted = self._raffle_wanted_qty(line, add_qty, set_qty)
        if wanted <= (line.product_uom_qty if line else 0):
            return super()._cart_update(
                product_id,
                line_id=line_id,
                add_qty=None,
                set_qty=max(wanted, 0),
                **kwargs,
            )
        draw = self.sudo().raffle_draw_id
        if not draw:
            if product.is_raffle_prize and not (
                product._raffle_member_sale_open()
            ):
                raise UserError(_("This product is not available."))
            return super()._cart_update(
                product_id,
                line_id=line_id,
                add_qty=add_qty,
                set_qty=set_qty,
                **kwargs,
            )
        if (
            not product
            or not draw._claim_link_is_open()
            or product not in draw._prize_allowed_products().sudo()
            or not product.with_env(self.env)._raffle_website_sellable()
        ):
            raise UserError(_("This prize is not available to you."))
        others = self._prize_lines().filtered(
            lambda sol: sol.product_id != product
        )
        others.unlink()
        return super()._cart_update(
            product_id, line_id=line_id, add_qty=0, set_qty=1, **kwargs
        )

    def _get_delivery_methods(self):
        carriers = super()._get_delivery_methods()
        if self.raffle_draw_id:
            return carriers.filtered("is_raffle_prize_carrier")
        return carriers.filtered(
            lambda carrier: not carrier.is_raffle_prize_carrier
        )

    def _update_address(self, partner_id, fnames=None):
        """A claim cart stays in the winner's name: a visitor who signs in
        does not take it over."""
        draw = self.sudo().raffle_draw_id
        if (
            draw
            and fnames
            and "partner_id" in fnames
            and partner_id != draw._prize_winner_partner().id
        ):
            fnames = [fname for fname in fnames if fname != "partner_id"]
        return super()._update_address(partner_id, fnames=fnames)

    def action_confirm(self):
        """A claim cart is confirmed by its draw's prize claim only.

        The claim locks the prize and the winner's quota, checks the rules
        again, then confirms the order with the context key
        `raffle_prize_claim_draw_id`, which lets it through here. Any other
        confirmation of an order that points to a draw goes through the
        claim as well, whatever the order's state: the claim takes a draft
        only, so a cart sent for payment is refused. A visitor of the
        website confirms as OdooBot, which signs the draw's note.
        """
        claiming = self.env.context.get("raffle_prize_claim_draw_id")
        strays = self.sudo().filtered(
            lambda order: order.website_id
            and not order.raffle_draw_id
            and order._raffle_token_only_lines()
        )
        if strays:
            # A cart whose draw was deleted, or any other website order
            # that got a prize sold for tokens only past the cart checks.
            raise UserError(
                _("A raffle prize is given through the link of its draw only.")
            )
        carts = self.filtered(
            lambda order: order.raffle_draw_id
            and order.raffle_draw_id.id != claiming
        )
        for cart in carts:
            draw = cart.sudo().raffle_draw_id
            if self.env.user.share:
                draw = draw.with_user(SUPERUSER_ID)
            products = cart._prize_lines().product_id
            if len(products) != 1:
                raise UserError(
                    _("A prize cart must hold exactly one prize to confirm.")
                )
            draw._prize_claim(products, order=cart)
        others = self - carts
        if others:
            return super(SaleOrder, others).action_confirm()
        return True

    def _raffle_token_only_lines(self):
        """Lines of sponsored prizes that are not sold to members."""
        self.ensure_one()
        return self.sudo().order_line.filtered(
            lambda line: line.product_id.is_raffle_prize
            and not line.product_id.raffle_member_sale_ok
        )

    def _raffle_check_prize_lines_payable(self):
        """Raise unless this ordinary cart may be paid for its sponsored
        prizes: prizes sold to members only, while the sponsored shop
        window is open."""
        self.ensure_one()
        blocked = self._raffle_token_only_lines().product_id
        if not self.env["event.raffle.config"]._sponsored_shop_is_open():
            blocked = self.sudo().order_line.product_id.filtered(
                "is_raffle_prize"
            )
        if blocked:
            raise ValidationError(
                _(
                    "%s cannot be bought now: remove it from the cart.",
                    ", ".join(blocked.mapped("display_name")),
                )
            )

    def _check_cart_is_ready_to_be_paid(self):
        """An ordinary cart pays for sponsored prizes sold to members only,
        while the sponsored shop window is open."""
        for order in self.filtered(lambda o: not o.sudo().raffle_draw_id):
            order._raffle_check_prize_lines_payable()
        return super()._check_cart_is_ready_to_be_paid()

    def _raffle_check_payable(self):
        """Raise unless a payment transaction may open for this order.

        The rule of the shop's payment, for the payment routes that do not
        go through _check_cart_is_ready_to_be_paid(), such as the payment
        of an order from the customer portal: a claim cart is confirmed by
        its claim and never paid, and a website order still open (draft or
        sent) pays for its sponsored prizes as the shop allows (see
        _raffle_check_prize_lines_payable()). An order made in the backend
        is left to its salesperson.
        """
        self.ensure_one()
        order = self.sudo()
        if order.raffle_draw_id:
            raise UserError(_("A prize order is confirmed without payment."))
        if order.website_id and order.state in ("draft", "sent"):
            order._raffle_check_prize_lines_payable()

    # ------------------------------------------------------------------
    # "Your prize" email
    # ------------------------------------------------------------------

    def _send_order_confirmation_mail(self):
        """A claim order sends the "Your prize" email; any other order the
        confirmation email of sale."""
        claims = self.filtered("raffle_draw_id")
        for order in claims:
            order._raffle_prize_send_mail()
        return super(SaleOrder, self - claims)._send_order_confirmation_mail()

    def _raffle_prize_send_mail(self):
        """Post the "Your prize" email to the winner, in their language.

        The layout shows the company, never the order: no number, no price
        and no access button.
        """
        self.ensure_one()
        template = self._raffle_prize_mail_template()
        if not template:
            return
        order = self
        if self.env.su:
            order = self.with_user(SUPERUSER_ID)
        order.with_context(force_send=True).message_post_with_source(
            template,
            email_layout_xmlid="event_raffle_prize_claim.mail_layout_prize",
            subtype_xmlid="mail.mt_comment",
        )

    def _raffle_prize_mail_template(self):
        """The "Your prize" template, or an empty recordset to send none.

        A module that tells the winner how the prize reaches them returns
        its own template here.
        """
        return self.env.ref(
            "event_raffle_prize_claim.mail_template_prize_reserved",
            raise_if_not_found=False,
        )

    def _raffle_prize_token_label(self):
        """The token this claim cart costs: one of its prize's category,
        else one of its draw's."""
        self.ensure_one()
        order = self.sudo()
        product = order._prize_lines().product_id[:1]
        if product:
            return product.product_tmpl_id._raffle_token_cost_label()
        return order.raffle_draw_id.band_id._token_label()

    def _raffle_prize_mail_values(self):
        """What the "Your prize" email shows: the prize, its token category
        and its sponsor, read as superuser in the current language."""
        self.ensure_one()
        order = self.sudo()
        draw = order.raffle_draw_id
        product = draw.prize_product_id or order._prize_lines().product_id[:1]
        template = product.product_tmpl_id
        return {
            "prize": product.with_context(
                display_default_code=False
            ).display_name,
            "category": template.raffle_band_id.name or "",
            "sponsor_name": template.raffle_sponsor_name or "",
            "sponsor_url": template.raffle_sponsor_url or "",
        }
