# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from markupsafe import escape

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

CLAIM_STATE_SELECTION = [
    ("none", "No prize"),
    ("reserved", "Reserved"),
    ("delivered", "Handed over"),
    ("declined", "Declined"),
    ("expired", "Expired"),
]
CLAIM_HOLDING_STATES = ("reserved", "delivered")
# Claim states that end a claim without a prize: each change to one of
# them writes a line of event.raffle.prize.claim.log.
CLAIM_LOG_STATES = ("declined", "expired")
# Written by the claim methods only, with sudo, after their checks.
CLAIM_FIELDS = {
    "prize_product_id",
    "prize_order_id",
    "prize_value",
    "claim_state",
    "claim_date",
    "decline_comment",
}


class EventRaffleDraw(models.Model):
    """Prize claim of a draw.

    Claiming a prize creates a sale order at no charge for the winner and
    confirms it, which reserves one unit at the warehouse. Declining it
    cancels the order and frees the unit; handing it over validates the
    delivery. The claim fields are written by those methods only: event
    users read them, and the sale and stock records are handled with sudo
    once the draw's write access is checked.
    """

    _inherit = "event.raffle.draw"

    band_id = fields.Many2one(
        "event.raffle.prize.band",
        string="Token Category",
        tracking=True,
        help="The winner earns one token of this category: only its prizes "
        "are offered, and its prize link lasts the category's link "
        "validity. Empty offers every category.",
    )
    is_closing_draw = fields.Boolean(
        string="Closing Draw",
        tracking=True,
        help="A closing draw may give the closing prizes.",
    )
    attendance_mode = fields.Selection(
        related="winner_participant_id.attendance_mode",
        string="Attendance",
    )
    prize_product_id = fields.Many2one(
        "product.product",
        string="Prize Product",
        readonly=True,
        copy=False,
        tracking=True,
        index="btree_not_null",
    )
    prize_order_id = fields.Many2one(
        "sale.order",
        string="Prize Order",
        readonly=True,
        copy=False,
    )
    prize_value = fields.Float(
        string="Prize Value",
        digits="Product Price",
        readonly=True,
        copy=False,
        help="Sales price of the prize when it was claimed.",
    )
    claim_state = fields.Selection(
        CLAIM_STATE_SELECTION,
        string="Prize Claim",
        default="none",
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
    )
    claim_date = fields.Datetime(
        string="Claim Date", readonly=True, copy=False
    )
    decline_comment = fields.Text(
        string="Decline Reason", readonly=True, copy=False
    )
    claim_log_ids = fields.One2many(
        "event.raffle.prize.claim.log",
        "draw_id",
        string="Claims Ended",
        readonly=True,
        help="Each decline and each expiry of this draw's claim, with the "
        "prize it held or the winner had chosen.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        draws = self
        if not self.env.su:
            for vals in vals_list:
                self._check_claim_fields(vals)
            # Context defaults fill the missing fields inside create(),
            # after the check above: those of the claim fields are dropped,
            # so a draw always starts without a claim.
            claim_defaults = {
                f"default_{fname}" for fname in self._prize_claim_fields()
            }
            if claim_defaults & set(self.env.context):
                draws = self.with_context(
                    {
                        key: value
                        for key, value in self.env.context.items()
                        if key not in claim_defaults
                    }
                )
        return super(EventRaffleDraw, draws).create(vals_list)

    def write(self, vals):
        if not self.env.su:
            self._check_claim_fields(vals)
        if vals.get("claim_state") in CLAIM_LOG_STATES:
            self._prize_claim_log(vals)
        return super().write(vals)

    def _prize_claim_log(self, vals):
        """Log the claims that `vals` ends, before they are written.

        One event.raffle.prize.claim.log line per draw whose claim state
        changes to the declined or expired state of `vals`; a draw already
        in that state logs nothing. The line names the prize and the order
        of a claim that holds a unit (see _prize_holding_states()), else
        the claim line returned by _prize_claim_log_cart_line(), else no
        prize. The reason is the `decline_comment` of `vals`. The line
        copies the draw's name, date, token category, raffle, event and
        company, which it keeps once the draw is deleted. Runs before the
        write, so it reads the state, the prize and the carts the claim
        had.
        """
        kind = vals["claim_state"]
        holding = self._prize_holding_states()
        log_vals = []
        for draw in self.sudo():
            if draw.claim_state == kind:
                continue
            if draw.claim_state in holding:
                product = draw.prize_product_id
                order = draw.prize_order_id
            else:
                line = draw._prize_claim_log_cart_line()
                product = line.product_id
                order = line.order_id
            raffle = draw.raffle_id
            log_vals.append(
                {
                    "draw_id": draw.id,
                    "draw_name": draw.display_name,
                    "draw_date": draw.date,
                    "raffle_id": raffle.id,
                    "event_id": raffle.event_id.id,
                    "band_id": draw.band_id.id,
                    "company_id": (
                        raffle.company_id or raffle.event_id.company_id
                    ).id,
                    "kind": kind,
                    "product_id": product.id,
                    "sale_order_id": order.id,
                    "comment": vals.get("decline_comment") or False,
                    "user_id": self.env.uid,
                }
            )
        # sudo: the access rights grant read only on the log.
        if log_vals:
            self.env["event.raffle.prize.claim.log"].sudo().create(log_vals)

    def _prize_claim_log_cart_line(self):
        """The cart line of the prize the winner chose, for the claim log.

        Called for a claim that ends without holding a unit. Returns a
        sale.order.line, empty here: the winner's carts come with the
        module of the prize link, which overrides this method.
        """
        self.ensure_one()
        return self.env["sale.order.line"]

    @api.model
    def _prize_claim_fields(self):
        """Fields written by the claim methods only, with sudo.

        A module that adds such fields extends this set: create() and
        write() refuse them from a user, and create() drops their context
        defaults.
        """
        return set(CLAIM_FIELDS)

    @api.model
    def _prize_holding_states(self):
        """Claim states that hold a unit for the winner.

        A claim in one of them counts toward the winner's quota and keeps
        the draw from claiming a second prize. A module that adds a state
        between the reservation and the hand-over extends this tuple.
        """
        return CLAIM_HOLDING_STATES

    @api.model
    def _check_claim_fields(self, vals):
        if self._prize_claim_fields() & set(vals):
            raise AccessError(
                _(
                    "The prize claim of a draw changes through its buttons "
                    "only: Choose the Prize, Decline the Prize and Prize "
                    "Handed Over."
                )
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_reserved_claim(self):
        if any(draw.claim_state == "reserved" for draw in self):
            raise UserError(
                _(
                    "A draw whose prize is reserved cannot be deleted: "
                    "decline the prize first, which frees its unit."
                )
            )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_given_claim(self):
        """Keep the draws whose prize left the warehouse.

        A claim in a holding state other than reserved (handed over, or
        shipped with event_raffle_prize_handover) has a confirmed prize
        order that points back to its draw. Deleting the draw empties the
        order's draw, which takes the unit out of the claim figures and
        makes the order's prize line a member purchase once its sale type
        is computed again.
        """
        given = set(self._prize_holding_states()) - {"reserved"}
        if any(draw.claim_state in given for draw in self):
            raise UserError(
                _(
                    "A draw whose prize was handed over or shipped cannot be "
                    "deleted: its prize order belongs to it."
                )
            )

    def _announce_prize_label(self):
        """The typed prize, else the claimed product, else the token
        category: a fresh draw has no product yet and names its category."""
        label = super()._announce_prize_label()
        if label:
            return label
        draw = self.sudo()
        return draw.prize_product_id.display_name or draw.band_id.name or ""

    def _prize_claim_person_keys(self):
        """Keys of the person who holds this draw's claim.

        The keys of the winner's participant, plus the contact of the prize
        order and the winner's email that the draw stores: those two still
        name the person once the participant is deleted, so the claim keeps
        counting toward their quota.
        """
        self.ensure_one()
        keys = set()
        if self.winner_participant_id:
            keys |= self.winner_participant_id._prize_person_keys()
        # sudo: event users do not read the sale orders.
        partner = self.sudo().prize_order_id.partner_id
        if partner:
            keys.add(("partner", partner.id))
        for email in (partner.email, self.winner_email):
            if email and email.strip():
                keys.add(("email", email.strip().lower()))
        return keys

    def _prize_post_note(self, body, **kwargs):
        """Post `body` as a note in this draw's chatter, as the current user.

        message_post() refuses an author without an email address. A user
        without one posts through OdooBot (base.partner_root) instead, and
        the note ends with the user's name, so the chatter still tells who
        acted. `body` is plain text or Markup; `kwargs` go to
        message_post(). Returns the mail.message.
        """
        self.ensure_one()
        user = self.env.user
        if user.email:
            return self.message_post(body=body, **kwargs)
        note = escape(_("%(note)s (by %(user)s)")) % {
            "note": body,
            "user": user.name,
        }
        return self.message_post(
            body=note,
            author_id=self.env.ref("base.partner_root").id,
            **kwargs,
        )

    def _prize_order(self):
        """The prize order of this draw, as superuser, once it is checked.

        The order must point back to this draw, which only a claim sets:
        the claim buttons never cancel nor deliver another order.
        """
        self.ensure_one()
        order = self.sudo().prize_order_id
        if not order or order.raffle_draw_id.id != self.id:
            raise UserError(
                _("The prize order of this draw does not belong to it.")
            )
        return order

    # ------------------------------------------------------------------
    # Rules of the prize choice
    # ------------------------------------------------------------------

    def _prize_winner_mode(self):
        """On site or virtual: on site needs a checked-in registration."""
        self.ensure_one()
        return self.winner_participant_id.attendance_mode or "virtual"

    def _prize_region_matches(self, template, address=None):
        """Whether the winner's address is in the prize's region.

        The address is `address`, a contact, else the winner's contact. A
        listed state admits its own residents. A listed country admits all
        of its residents when none of its states is listed, and defers to
        the states otherwise.
        """
        self.ensure_one()
        countries = template.raffle_country_ids
        states = template.raffle_state_ids
        if not countries and not states:
            return True
        partner = address or self.partner_id
        if partner.state_id and partner.state_id in states:
            return True
        country = partner.country_id
        return bool(
            country
            and country in countries
            and country not in states.country_id
        )

    def _prize_refusal(self, product, check_stock=True, check_quota=True):
        """Why `product` cannot go to this draw's winner, or False.

        Rules: the product is a sponsored prize, of the draw's event, of the
        draw's token category when it has one, for the winner's attendance
        mode, of the winner's region for a virtual winner, a closing prize
        only on a closing draw, with a unit left at the warehouse, and the
        winner is under quota.
        """
        self.ensure_one()
        template = product.product_tmpl_id
        if not template.is_raffle_prize or not product.active:
            return _("%s is not a sponsored prize.", product.display_name)
        event = self.raffle_id.event_id
        if (
            template.raffle_event_ids
            and event not in template.raffle_event_ids
        ):
            return _("%s is not a prize of this event.", product.display_name)
        if self.band_id and template.raffle_band_id != self.band_id:
            return _(
                "%(prize)s is not in the token category %(band)s of this "
                "draw.",
                prize=product.display_name,
                band=self.band_id.name,
            )
        mode = self._prize_winner_mode()
        if template.raffle_attendance not in ("both", mode):
            labels = dict(
                template._fields["raffle_attendance"]._description_selection(
                    self.env
                )
            )
            return _(
                "%(prize)s is for %(allowed)s winners only.",
                prize=product.display_name,
                allowed=labels[template.raffle_attendance],
            )
        if mode == "virtual" and not self._prize_region_matches(template):
            return _(
                "%s is not offered in the winner's region.",
                product.display_name,
            )
        if template.raffle_closing_prize and not self.is_closing_draw:
            return _(
                "%s is a closing prize: only a closing draw gives it.",
                product.display_name,
            )
        company = self.raffle_id.company_id or self.env.company
        free = product.with_company(company).raffle_qty_free
        if check_stock and free <= 0:
            return _("%s has no unit left.", product.display_name)
        if check_quota and self._prize_quota_reached():
            return _("The winner already holds their quota of prizes.")
        return False

    def _prize_quota_reached(self):
        self.ensure_one()
        participant = self.winner_participant_id
        return bool(participant and participant._prize_quota_reached())

    def _prize_allowed_products(self):
        """Prize products that this draw's winner may take."""
        self.ensure_one()
        if self._prize_quota_reached():
            return self.env["product.product"]
        company = self.raffle_id.company_id or self.env.company
        products = (
            self.env["product.product"]
            .with_company(company)
            .search(
                [
                    ("is_raffle_prize", "=", True),
                    ("company_id", "in", (False, company.id)),
                ]
            )
        )
        return products.filtered(
            lambda p: not self._prize_refusal(p, check_quota=False)
        ).with_env(self.env)

    # ------------------------------------------------------------------
    # Claim, decline, hand over
    # ------------------------------------------------------------------

    def _prize_lock(self, product):
        """Serialize the claims on `product` and on the winner's quota.

        Locks the product row, then the rows of the winner's participants
        over the event's raffles, in id order so that two claims never wait
        on each other in a cycle. A member purchase takes the same product
        lock when its order confirms (see
        product.product._raffle_prize_lock_rows()), and never locks a
        participant. Each locked row is also updated in place: under
        REPEATABLE READ, a transaction that waited on the lock then fails
        with a serialization error when the other one commits, and the RPC
        layer retries it on a fresh snapshot, where the stock and the quota
        it re-checks include the first claim or purchase. A lock alone
        would let the waiter go on with the counts it read before the
        commit.
        """
        self.ensure_one()
        cr = self.env.cr
        product._raffle_prize_lock_rows()
        scope = self.winner_participant_id._prize_scope_participants()
        if scope:
            ids = tuple(sorted(scope.ids))
            cr.execute(
                "SELECT id FROM event_raffle_participant "
                "WHERE id IN %s ORDER BY id FOR UPDATE",
                (ids,),
            )
            cr.execute(
                "UPDATE event_raffle_participant SET write_date = write_date "
                "WHERE id IN %s",
                (ids,),
            )
        # Re-read the stock and the claims after taking the locks.
        self.env.invalidate_all()

    def _prize_winner_partner(self):
        """The winner's contact, created from the participant if missing.

        A new contact is linked back on the participant, so the draw's
        contact and the next claims of that person use it.
        """
        self.ensure_one()
        participant = self.winner_participant_id
        if participant.partner_id:
            return participant.partner_id
        # sudo: an event user may not create contacts.
        partner = (
            self.env["res.partner"]
            .sudo()
            .create(
                {
                    "name": participant.name or self.winner_name,
                    "email": participant.email or self.winner_email,
                }
            )
        )
        participant.partner_id = partner
        return partner.with_env(self.env)

    def _prize_claim(self, product, order=None):
        """Reserve one unit of `product` for this draw's winner.

        Runs in the caller's transaction: the locks, the checks, the sale
        order and its stock reservation commit or roll back together. The
        order costs nothing: its line keeps the sales price with a full
        discount, and the draw stores that price as the prize value.

        Without `order`, the claim creates the sale order. A draft `order`
        that points back to this draw and holds one unit of `product` (and
        nothing else but delivery lines) is used instead, once the same
        checks pass under the same locks. The order is confirmed with the
        context key `raffle_prize_claim_draw_id` set to this draw.

        The rules read the winner's contact; for a virtual winner, the
        region of the prize is checked again on the delivery address of the
        order, the one the prize ships to, once the order holds its final
        contact (see _prize_check_shipping_region()).
        """
        self.ensure_one()
        self.check_access("write")
        if self.claim_state in self._prize_holding_states():
            raise UserError(_("This winner already has a prize."))
        if not self.winner_participant_id:
            raise UserError(_("This draw has no winner to give a prize to."))
        if order is not None:
            self._prize_check_claim_order(order, product)
        self._prize_lock(product)
        refusal = self._prize_refusal(product)
        if refusal:
            raise UserError(refusal)
        partner = self._prize_winner_partner()
        company = self.raffle_id.company_id or self.env.company
        warehouse = self.env["event.raffle"]._prize_warehouse(company)
        value = product.lst_price
        line_vals = {
            "product_id": product.id,
            "product_uom_qty": 1.0,
            "price_unit": value,
            "discount": 100.0,
        }
        # sudo: event users have no sale or stock rights. The write access
        # on the draw is checked above and the order carries one prize.
        if order is None:
            order = (
                self.env["sale.order"]
                .sudo()
                .with_company(company)
                .create(
                    {
                        "partner_id": partner.id,
                        "company_id": company.id,
                        "warehouse_id": warehouse.id,
                        "user_id": self.env.uid,
                        "origin": self._prize_order_origin(),
                        "raffle_draw_id": self.id,
                        "order_line": [Command.create(line_vals)],
                    }
                )
            )
        else:
            order = order.sudo().with_company(company)
            order_vals = {
                "warehouse_id": warehouse.id,
                "origin": order.origin or self._prize_order_origin(),
            }
            if order.partner_id != partner:
                order_vals["partner_id"] = partner.id
            order.write(order_vals)
            order._prize_lines().write(line_vals)
        self._prize_check_shipping_region(product, order)
        order.with_context(raffle_prize_claim_draw_id=self.id).action_confirm()
        moves = order.picking_ids.move_ids
        if not moves.filtered(lambda m: m.state == "assigned"):
            raise UserError(
                _("No unit of %s could be reserved.", product.display_name)
            )
        self.sudo().write(
            {
                "prize_product_id": product.id,
                "prize_order_id": order.id,
                "prize_value": value,
                "claim_state": "reserved",
                "claim_date": fields.Datetime.now(),
                "decline_comment": False,
                "prize": product.with_context(
                    display_default_code=False
                ).display_name,
            }
        )
        self._prize_post_note(
            _(
                "Prize %(prize)s reserved for %(winner)s (order %(order)s).",
                prize=product.display_name,
                winner=partner.display_name,
                order=order.name,
            )
        )
        return order.with_env(self.env)

    def _prize_check_shipping_region(self, product, order):
        """Refuse `order` when it ships `product` out of the prize's region.

        A virtual winner's contact meets the region when the claim starts,
        but the order may ship elsewhere: a delivery address picked at the
        checkout, or the contact's own delivery address. The order's
        delivery address, else its contact, must then be in the region. An
        on-site winner takes the prize at the event: no region applies.
        """
        self.ensure_one()
        if self._prize_winner_mode() != "virtual":
            return
        order = order.sudo()
        address = order.partner_shipping_id or order.partner_id
        if not self._prize_region_matches(product.product_tmpl_id, address):
            raise UserError(
                _(
                    "%s is not offered in the winner's region.",
                    product.display_name,
                )
            )

    def _prize_order_origin(self):
        self.ensure_one()
        return f"{self.raffle_id.name} - {self.display_name}"

    def _prize_check_claim_order(self, order, product):
        """Refuse an order that cannot become this draw's prize order.

        It must be a draft that points back to this draw, with exactly one
        line besides the delivery lines: one unit of `product`.
        """
        self.ensure_one()
        order = order.sudo()
        lines = order._prize_lines()
        if (
            len(order) != 1
            or order.raffle_draw_id.id != self.id
            or order.state != "draft"
            or len(lines) != 1
            or lines.product_id != product
            or lines.product_uom_qty != 1.0
        ):
            raise UserError(
                _(
                    "This order cannot hold the prize of %s: it must be a "
                    "draft of this draw with one unit of one prize.",
                    self.display_name,
                )
            )

    def _prize_decline(self, comment):
        """Cancel the reserved prize: its unit is back in stock at once."""
        self.ensure_one()
        self.check_access("write")
        if self.claim_state != "reserved":
            raise UserError(_("Only a reserved prize can be declined."))
        comment = (comment or "").strip()
        if not comment:
            raise UserError(_("Say why the prize is declined."))
        # sudo: see _prize_claim(). An order already cancelled from the
        # Sales or Inventory app stays as it is.
        order = self._prize_order()
        if order.state != "cancel":
            if order.locked:
                order.action_unlock()
            order.with_context(disable_cancel_warning=True).action_cancel()
        prize = self.prize_product_id.display_name
        self.sudo().write(
            {
                "claim_state": "declined",
                "decline_comment": comment,
                "prize": False,
            }
        )
        self._prize_post_note(
            _(
                "Prize %(prize)s declined: %(comment)s",
                prize=prize,
                comment=comment,
            )
        )
        return True

    def action_prize_deliver(self):
        """Validate the delivery of the reserved prize to the winner."""
        for draw in self:
            draw.check_access("write")
            if draw.claim_state != "reserved":
                raise UserError(_("Only a reserved prize can be handed over."))
            draw._prize_validate_delivery()
            now = fields.Datetime.now()
            draw.sudo().write({"claim_state": "delivered"})
            draw.write({"prize_received": True, "prize_received_date": now})
            draw._prize_post_note(
                _("Prize %s handed over.", draw.prize_product_id.display_name)
            )
        return True

    def _prize_validate_delivery(self):
        """Validate the delivery of this draw's prize order, as superuser.

        The caller checks the draw's write access and its claim state, and
        sets the claim state afterwards: the hand-over sets it delivered, a
        module that ships the prize may set another state. Raises when the
        order is no longer confirmed or when no unit left through a done
        move to the winner.
        """
        self.ensure_one()
        # sudo: see _prize_claim(). A multi-step delivery validates its
        # steps in order: each one makes the next one ready.
        order = self._prize_order()
        if order.state != "sale":
            raise UserError(
                _(
                    "The order of %s is no longer confirmed: decline the "
                    "prize, then choose it again.",
                    self.prize_product_id.display_name,
                )
            )
        for __ in range(len(order.picking_ids) + 1):
            ready = order.picking_ids.filtered(lambda p: p.state == "assigned")
            if not ready:
                break
            for move in ready.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            ready.with_context(
                skip_backorder=True, skip_sms=True
            ).button_validate()
        # The prize leaves only through a done move to the winner: a
        # delivery cancelled elsewhere leaves nothing delivered.
        lines = order.order_line.filtered_domain(
            [("product_id", "=", self.prize_product_id.id)]
        )
        delivered = sum(lines.mapped("qty_delivered"))
        if order.picking_ids.filtered(
            lambda p: p.state not in ("done", "cancel")
        ) or (
            float_compare(
                delivered,
                1.0,
                precision_rounding=self.prize_product_id.uom_id.rounding,
            )
            < 0
        ):
            raise UserError(
                _(
                    "The delivery of %s could not be validated. If its "
                    "order or delivery was cancelled, decline the prize, "
                    "then choose it again.",
                    self.prize_product_id.display_name,
                )
            )
        return order.with_env(self.env)

    def action_open_prize_choose_wizard(self):
        self.ensure_one()
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "name": _("Choose the Prize"),
            "res_model": "event.raffle.prize.choose.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_draw_id": self.id},
        }

    def action_open_prize_decline_wizard(self):
        self.ensure_one()
        self.check_access("write")
        return {
            "type": "ir.actions.act_window",
            "name": _("Decline the Prize"),
            "res_model": "event.raffle.prize.decline.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_draw_id": self.id},
        }
