# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import mimetypes
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext, image_process
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.event_raffle_prize_claim.models.event_raffle_draw_notification import (
    TOKEN_MASK,
)

# Claim states whose prize the public pages name.
PUBLIC_CHOSEN_STATES = ("reserved", "shipped", "delivered")
# Written by the hand-over methods only, with sudo, after their checks.
HANDOVER_FIELDS = {
    "prize_tracking_ref",
    "prize_carrier_name",
    "prize_shipped_date",
    "prize_handover_photo",
}
# Largest side of a hand-over photo, in pixels.
PHOTO_MAX_SIZE = 1920
# Largest photo upload read, in bytes.
PHOTO_MAX_BYTES = 25 * 1024 * 1024
# Most claims the hand-over screen lists at once.
HANDOVER_LIST_LIMIT = 200
# Seconds during which the same user sending the hand-over form again is
# answered with the success of the hand-over already done.
HANDOVER_REPEAT_SECONDS = 600


class EventRaffleDraw(models.Model):
    """How a reserved prize reaches its winner.

    Three ways, chosen by the prize and the winner's attendance (see
    _prize_delivery_mode()): an on-site winner picks a physical prize up
    at the raffle's pick-up location and an event user hands it over,
    from the draw or from the phone screen /raffle/handover, with an
    optional photo; a virtual prize goes by email, with its instructions
    and an optional code; a physical prize to a virtual winner is shipped,
    then marked received. Each way validates the delivery of the prize
    order through event_raffle_prize, whose access checks apply.
    """

    _inherit = "event.raffle.draw"

    claim_state = fields.Selection(
        selection_add=[("shipped", "Shipped"), ("delivered",)],
        ondelete={"shipped": "set default"},
    )
    prize_virtual = fields.Boolean(
        string="Virtual prize",
        related="prize_product_id.raffle_virtual_prize",
    )
    winner_public_name = fields.Char(
        string="Public name",
        compute="_compute_winner_public_name",
        inverse="_inverse_winner_public_name",
        help="Public name of the winner's contact, shown on the winners "
        "page instead of the winner's name. Empty shows the winner's name.",
    )
    prize_tracking_ref = fields.Char(
        string="Tracking number", readonly=True, copy=False
    )
    prize_carrier_name = fields.Char(
        string="Carrier", readonly=True, copy=False
    )
    prize_shipped_date = fields.Datetime(
        string="Shipped on", readonly=True, copy=False
    )
    prize_handover_photo = fields.Image(
        string="Hand-over photo",
        max_width=PHOTO_MAX_SIZE,
        max_height=PHOTO_MAX_SIZE,
        readonly=True,
        copy=False,
        help="Photo of the winner with the sponsor, taken at the hand-over. "
        "It is never public.",
    )

    @api.model
    def _prize_claim_fields(self):
        return super()._prize_claim_fields() | HANDOVER_FIELDS

    @api.model
    def _prize_holding_states(self):
        """A shipped prize still holds its unit until it is received."""
        return (*super()._prize_holding_states(), "shipped")

    # ------------------------------------------------------------------
    # Public name
    # ------------------------------------------------------------------

    def _prize_public_partner(self):
        """The contact whose public name this draw shows, as superuser.

        The contact of the prize order once the prize is claimed, which
        stays when the participant goes; the winner's contact before.
        """
        self.ensure_one()
        draw = self.sudo()
        order = draw.prize_order_id
        if order and order.raffle_draw_id == draw:
            return order.partner_id
        return draw.partner_id

    def _prize_public_name(self):
        """The winner as the public pages name them.

        The public name of the contact when it has one. Else the name the
        draw keeps for its winner (the name on the draw, else the
        participant's): the contact of a registration may be the person
        who booked it, whose full name is not the winner's. The contact's
        full name comes last, when the draw names nobody.
        """
        self.ensure_one()
        draw = self.sudo()
        partner = self._prize_public_partner()
        public = (partner.raffle_public_name or "").strip()
        return (
            public
            or (draw.winner_name or "").strip()
            or (draw.winner_participant_id.name or "").strip()
            or (partner.name or "").strip()
        )

    @api.depends("partner_id.raffle_public_name", "prize_order_id.partner_id")
    def _compute_winner_public_name(self):
        for draw in self:
            partner = draw._prize_public_partner() if draw.id else False
            draw.winner_public_name = (
                partner.raffle_public_name if partner else False
            )

    def _inverse_winner_public_name(self):
        """An event user who may write the draw sets its winner's public
        name, even without the right to write contacts."""
        for draw in self:
            draw.check_access("write")
            partner = draw._prize_public_partner()
            if not partner:
                raise UserError(
                    _("This draw has no winner contact to name publicly.")
                )
            partner._raffle_set_public_name(draw.winner_public_name)

    def _prize_public_status(self):
        """(status, text) of this draw's prize on the public pages, in the
        current language.

        "chosen" for a prize reserved, shipped or handed over, with the
        prize's name. "declined" and "expired" for a claim that ended
        without a prize, an open claim whose link has expired counting as
        expired. "chosen" again, with the prize written on the draw, for a
        draw that never had a prize link: a prize typed on the wheel of a
        draw whose link is issued is a label, not the winner's choice, so
        it neither hides "prize to choose" nor turns into "No prize
        chosen" later. "to_choose" otherwise: the winner has a prize to
        choose, in the token category of the draw when it has one.
        """
        self.ensure_one()
        draw = self.sudo()
        state = draw.claim_state
        if state in PUBLIC_CHOSEN_STATES:
            product = draw.prize_product_id.with_context(
                display_default_code=False
            )
            return "chosen", product.display_name or draw.prize or ""
        if state == "declined":
            return "declined", self.env._("Prize declined")
        if state == "expired" or draw.claim_link_state == "expired":
            return "expired", self.env._("No prize chosen")
        if draw.prize and state == "none" and draw.claim_link_state == "none":
            return "chosen", draw.prize
        if draw.band_id:
            return "to_choose", self.env._(
                "%(group)s, prize to choose", group=draw.band_id.name
            )
        return "to_choose", self.env._("Prize to choose")

    def _prize_public_line(self):
        """The public fields of this draw's winner, for the winners page.

        {"id", "name", "prize", "status", "sponsor", "sponsor_url",
        "category"}: "status" and "prize" come from _prize_public_status().
        The sponsor is the one of a chosen prize only. The category is
        left empty when the prize text already names it ("to_choose").
        """
        self.ensure_one()
        draw = self.sudo()
        status, prize = self._prize_public_status()
        template = draw.prize_product_id.product_tmpl_id
        band = template.raffle_band_id or draw.band_id
        chosen = status == "chosen"
        return {
            "id": draw.id,
            "name": self._prize_public_name(),
            "prize": prize,
            "status": status,
            "sponsor": (template.raffle_sponsor_name or "") if chosen else "",
            "sponsor_url": (
                (template.raffle_sponsor_url or "") if chosen else ""
            ),
            "category": "" if status == "to_choose" else (band.name or ""),
        }

    # ------------------------------------------------------------------
    # How the prize reaches the winner
    # ------------------------------------------------------------------

    def _prize_delivery_mode(self, product=None):
        """How `product`, else the claimed prize, reaches the winner.

        "virtual" for a virtual prize, sent by email; "pickup" for a
        physical prize to an on-site winner; "shipping" for a physical
        prize to a virtual winner.
        """
        self.ensure_one()
        product = product or self.sudo().prize_product_id
        if product.sudo().raffle_virtual_prize:
            return "virtual"
        if self._prize_winner_mode() == "onsite":
            return "pickup"
        return "shipping"

    def _prize_check_shipping_region(self, product, order):
        """The delivery address of the order matters only when `product`
        ships: a virtual prize goes by email, and its region is checked
        on the winner's contact when the claim starts (see
        _prize_refusal())."""
        if self._prize_delivery_mode(product) != "shipping":
            return
        super()._prize_check_shipping_region(product, order)

    def _prize_handover_line(self, product=None):
        """The sentence that tells the winner how the prize reaches them,
        in the current language."""
        self.ensure_one()
        mode = self._prize_delivery_mode(product)
        if mode == "virtual":
            return self.env._("Your prize will be sent to you by email.")
        if mode == "shipping":
            return self.env._("Your prize will be shipped to you.")
        location = (self.sudo().raffle_id.prize_pickup_location or "").strip()
        if location:
            return self.env._("Pick up your prize at %s.", location)
        return self.env._("Pick up your prize at the event.")

    def _prize_check_reserved(self):
        self.ensure_one()
        self.check_access("write")
        if self.claim_state != "reserved":
            raise UserError(_("Only a reserved prize can be handed over."))

    # Hand-over on site, with a photo

    def _prize_hand_over(self, photo=None):
        """Hand the reserved prize over, then keep the optional photo.

        Runs action_prize_deliver() of event_raffle_prize, with its access
        checks, and stores `photo` (raw image bytes) on the draw only once
        the delivery is validated.
        """
        self.ensure_one()
        self._prize_check_reserved()
        self.action_prize_deliver()
        if photo:
            self._prize_store_handover_photo(photo)
        return True

    def _prize_handover_just_done(self):
        """Whether the current user handed this prize over in the last
        HANDOVER_REPEAT_SECONDS.

        A hand-over form sent twice, by a second tap while the first
        request is on its way, reaches the server once the prize is
        handed over: the hand-over screen then answers with the success of
        the first request instead of a refusal. A hand-over by another
        user, or an older one, is not the same request sent again.
        """
        self.ensure_one()
        draw = self.sudo()
        since = fields.Datetime.now() - timedelta(
            seconds=HANDOVER_REPEAT_SECONDS
        )
        return bool(
            draw.claim_state == "delivered"
            and draw.prize_received_date
            and draw.prize_received_date >= since
            and draw.write_uid == self.env.user
        )

    def _prize_store_handover_photo(self, photo):
        """Store `photo` as the hand-over photo of this draw.

        The image is resized to PHOTO_MAX_SIZE pixels on its largest side,
        its orientation fixed from its EXIF data, then written in the
        prize_handover_photo field and as an attachment of the draw, which
        lists it in the chatter. Neither is public: both are read through
        the draw's access rights. Raises UserError when `photo` is not an
        image.
        """
        self.ensure_one()
        self.check_access("write")
        if len(photo) > PHOTO_MAX_BYTES:
            raise UserError(_("The photo is too large."))
        try:
            resized = image_process(
                photo,
                size=(PHOTO_MAX_SIZE, PHOTO_MAX_SIZE),
                verify_resolution=True,
            )
        except (UserError, ValueError) as error:
            raise UserError(_("The photo could not be read.")) from error
        if not resized:
            raise UserError(_("The photo could not be read."))
        mimetype = guess_mimetype(resized, default="")
        if not mimetype.startswith("image/"):
            raise UserError(_("The photo could not be read."))
        extension = mimetypes.guess_extension(mimetype) or ".jpg"
        name = _("Hand-over photo, %s", self.display_name) + extension
        draw = self.sudo()
        draw.write({"prize_handover_photo": base64.b64encode(resized)})
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": name,
                    "raw": resized,
                    "res_model": self._name,
                    "res_id": self.id,
                    "mimetype": mimetype,
                    "public": False,
                }
            )
        )
        self._prize_post_note(
            _("Hand-over photo added."), attachment_ids=attachment.ids
        )
        return attachment.with_env(self.env)

    @api.model
    def _prize_handover_search(self, search=""):
        """Reserved claims that the hand-over screen lists.

        Runs with the current user's rights. The claims of raffles that
        are not done, whose winner is on site and whose prize is physical;
        `search` matches the winner's name, public name or email, or the
        draw number, with or without its "#".
        """
        domain = [
            ("claim_state", "=", "reserved"),
            ("raffle_id.state", "!=", "done"),
        ]
        term = " ".join((search or "").split())
        if term:
            terms = [
                ("winner_name", "ilike", term),
                ("winner_email", "ilike", term),
                ("partner_id.name", "ilike", term),
                ("partner_id.email", "ilike", term),
                ("partner_id.raffle_public_name", "ilike", term),
            ]
            number = term.removeprefix("#").strip()
            if number.isdigit():
                terms.append(("sequence", "=", int(number)))
            domain += ["|"] * (len(terms) - 1) + terms
        draws = self.search(domain, order="date desc, id desc")
        return draws.filtered(lambda d: d._prize_delivery_mode() == "pickup")[
            :HANDOVER_LIST_LIMIT
        ]

    def _prize_handover_values(self):
        """What the hand-over screen shows of this claim."""
        self.ensure_one()
        draw = self.sudo()
        template = draw.prize_product_id.product_tmpl_id
        public = self._prize_public_name()
        name = (draw.winner_name or draw.partner_id.name or "").strip()
        return {
            "draw": self,
            "number": draw.sequence,
            "name": name or public,
            "public_name": public if public != name else "",
            "prize": draw.prize_product_id.with_context(
                display_default_code=False
            ).display_name,
            "sponsor": template.raffle_sponsor_name or "",
            "category": (template.raffle_band_id or draw.band_id).name or "",
            "raffle": draw.raffle_id.name,
        }

    # Virtual prize

    def _prize_send_virtual(self, body_html, code=False):
        """Email a virtual prize to the winner, then mark it delivered.

        The email carries `body_html` and the optional `code`, in the
        winner's language, through the email sending of the notify wizard
        (event_raffle), which logs it on the draw with the code masked.
        The delivery is then validated by action_prize_deliver(): a
        virtual prize still counts its units, such as codes or licences.
        """
        self.ensure_one()
        self._prize_check_reserved()
        if not self.prize_virtual:
            raise UserError(
                _("%s is not a virtual prize.", self.prize_product_id.name)
            )
        wizard = self.env["event.raffle.draw.notify.wizard"].create(
            {"draw_id": self.id, "sender": "odoobot", "body": "-"}
        )
        if not wizard._winner_email():
            raise UserError(
                _(
                    "The winner has no email address: add one to the draw or "
                    "to the winner contact first."
                )
            )
        lang = self._claim_link_lang()
        code = (code or "").strip()
        body = Markup(body_html or "")
        if code:
            label = self.with_context(lang=lang).env._("Your code:")
            body += Markup("<p>%s <strong>%s</strong></p>") % (
                label,
                escape(code),
            )
        author = wizard._sender_partner()
        mail = wizard.with_context(lang=lang)._send_email(author, body)
        text = html2plaintext(body)
        if code:
            text = text.replace(code, TOKEN_MASK)
        # sudo: see event.raffle.draw.notify.wizard.action_send().
        self.env["event.raffle.draw.notification"].sudo().create(
            {
                "draw_id": self.id,
                "author_id": author.id,
                "channel": "email",
                "recipient": wizard._winner_email(),
                "body": text,
                "mail_id": mail.id,
                "message_id": mail.mail_message_id.id,
            }
        )
        self._prize_post_note(
            _(
                "Virtual prize %s sent by email.",
                self.prize_product_id.display_name,
            )
        )
        self.action_prize_deliver()
        return True

    # Manual shipping

    def _prize_ship(self, tracking_ref, carrier_name=False):
        """Ship the reserved physical prize: its delivery is validated, the
        claim becomes shipped and the winner receives the tracking number.

        The picking that left the warehouse keeps the tracking number when
        the delivery app is installed.
        """
        self.ensure_one()
        self._prize_check_reserved()
        if self.prize_virtual:
            raise UserError(
                _(
                    "A virtual prize is sent by email: use Send the Virtual "
                    "Prize."
                )
            )
        tracking_ref = (tracking_ref or "").strip()
        if not tracking_ref:
            raise UserError(_("Give the tracking number of the parcel."))
        carrier_name = (carrier_name or "").strip() or False
        order = self._prize_validate_delivery()
        pickings = order.sudo().picking_ids.filtered(
            lambda p: p.state == "done" and p.picking_type_code == "outgoing"
        )
        if "carrier_tracking_ref" in pickings._fields:
            pickings.write({"carrier_tracking_ref": tracking_ref})
        self.sudo().write(
            {
                "claim_state": "shipped",
                "prize_tracking_ref": tracking_ref,
                "prize_carrier_name": carrier_name,
                "prize_shipped_date": fields.Datetime.now(),
            }
        )
        self._prize_post_note(
            _(
                "Prize %(prize)s shipped, tracking number %(ref)s.",
                prize=self.prize_product_id.display_name,
                ref=tracking_ref,
            )
        )
        # sudo: event users do not write sale orders, which posting needs.
        order.sudo()._raffle_prize_send_shipped_mail()
        return True

    def action_prize_received(self):
        """The winner received the shipped prize."""
        for draw in self:
            draw.check_access("write")
            if draw.claim_state != "shipped":
                raise UserError(_("Only a shipped prize can be received."))
            draw.sudo().write({"claim_state": "delivered"})
            draw.write(
                {
                    "prize_received": True,
                    "prize_received_date": fields.Datetime.now(),
                }
            )
            draw._prize_post_note(
                _(
                    "Prize %s received by the winner.",
                    draw.prize_product_id.display_name,
                )
            )
        return True

    def _prize_open_wizard(self, model, title):
        self.ensure_one()
        self._prize_check_reserved()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model,
            "view_mode": "form",
            "target": "new",
            "context": {"default_draw_id": self.id},
        }

    def action_open_prize_ship_wizard(self):
        return self._prize_open_wizard(
            "event.raffle.prize.ship.wizard", _("Mark as Shipped")
        )

    def action_open_prize_virtual_wizard(self):
        return self._prize_open_wizard(
            "event.raffle.prize.virtual.wizard", _("Send the Virtual Prize")
        )
