# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64

from markupsafe import escape

# Odoo registers the common Pillow plugins only (odoo.tools.image): the
# WebP plugin is imported to read the WebP photos of the portal.
from PIL import Image, WebPImagePlugin  # noqa: F401

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL, html_sanitize, is_html_empty, plaintext2html
from odoo.tools.image import (
    IMAGE_MAX_RESOLUTION,
    binary_to_image,
    image_apply_opt,
    image_fix_orientation,
)
from odoo.tools.mimetypes import guess_mimetype

from odoo.addons.event_raffle_prize_handover.models.event_raffle_draw import (
    PHOTO_MAX_BYTES,
    PHOTO_MAX_SIZE,
)

SPONSOR_STATE_SELECTION = [
    ("submitted", "Submitted"),
    ("approved", "Approved"),
    ("refused", "Refused"),
]
# States in which the sponsor edits or withdraws the prize in the portal.
SPONSOR_EDITABLE_STATES = ("submitted", "refused")
# Fields the portal writes, once the controller has checked their values.
# The description also fills the eCommerce description (see
# ProductTemplate._raffle_sponsor_ecommerce_from_portal()). Everything
# else (the token category, the approval state, the sale and publication
# flags, the stock, the sponsor and the event) is set by the portal
# methods below or by the organization.
PORTAL_FIELDS = (
    "name",
    "description_sale",
    "image_1920",
    "list_price",
    "raffle_initial_qty",
    "raffle_attendance",
    "raffle_virtual_prize",
    "raffle_virtual_instructions",
)
# Image types the portal accepts for a prize photo. SVG is left out: it
# may carry scripts.
PHOTO_MIMETYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")
# JPEG quality of a re-encoded prize photo.
PHOTO_JPEG_QUALITY = 90
# Language of the source value of the translated fields. The portal reads
# and writes that value only, so the sponsor's text is the text of every
# language until the organization translates it.
SOURCE_LANG = "en_US"
# Public category of the shop that holds the approved sponsored prizes.
SPONSORED_CATEGORY = "event_raffle_prize_sponsor.public_category_sponsored"
# Fields whose change moves a prize in or out of that category.
SPONSORED_CATEGORY_FIELDS = {
    "is_raffle_prize",
    "raffle_sponsor_id",
    "raffle_sponsor_state",
}


class ProductTemplate(models.Model):
    """Approval of the prizes that sponsors submit in the portal.

    A prize is offered only once approved. The approval state decides the
    `active` flag of the product (see _raffle_sponsor_availability_vals()):
    a submitted or refused prize is archived, so every list that offers a
    prize leaves it out (the choice of a draw and its wheel, the winner's
    shop, the member sales, the product snippets, the winners page), and
    event_raffle_prize's _prize_refusal() refuses it. Approving it restores
    it and publishes it on the website. Prizes created in the backend are
    approved from the start.

    The event managers approve and refuse any prize. A sponsorship manager
    (event.event.raffle_sponsor_manager_ids) approves and refuses the
    sponsored prizes whose events are all managed by them, without any
    write access on the products: _raffle_sponsor_check_review() checks
    the events, then the approval fields are written as superuser. Only a
    submitted or refused prize is approved, so the approval never restores
    nor publishes a prize that an event manager archived or unpublished.
    Neither the approval nor the refusal is sent to the sponsor, who reads
    the state in the portal.

    An approved prize with a sponsor is in the public category
    SPONSORED_CATEGORY of the shop (see _raffle_sponsored_category_due()).
    A create, or a write of SPONSORED_CATEGORY_FIELDS, adds the prizes
    that become due and removes the ones that stop being due; the other
    public categories of a prize, and a category set by hand on a prize
    whose state does not change, are left as they are. A withdrawn prize is
    deleted, and leaves the category with it.
    """

    _inherit = "product.template"

    raffle_sponsor_state = fields.Selection(
        SPONSOR_STATE_SELECTION,
        string="Sponsor approval",
        default="approved",
        required=True,
        copy=False,
        tracking=True,
        help="A prize submitted by a sponsor in the portal waits for the "
        "organization: it is offered nowhere until it is approved.",
    )
    raffle_sponsor_refusal_reason = fields.Text(
        string="Refusal reason",
        copy=False,
        help="Shown to the sponsor in the portal. Editing the prize there "
        "submits it again.",
    )
    raffle_sponsor_ecommerce_portal = fields.Text(
        string="eCommerce description from the portal",
        readonly=True,
        help="The eCommerce description that the portal wrote last, "
        "sanitized. The portal rewrites the eCommerce description only "
        "while it still equals this value, or is empty.",
    )
    raffle_sponsor_can_review = fields.Boolean(
        string="May approve the prize",
        compute="_compute_raffle_sponsor_can_review",
        search="_search_raffle_sponsor_can_review",
        help="The current user is an event manager, or a sponsorship "
        "manager of every event of this sponsored prize.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        templates._raffle_sponsored_category_move(
            templates.filtered(lambda t: t._raffle_sponsored_category_due()),
            self.browse(),
        )
        return templates

    def write(self, vals):
        if not SPONSORED_CATEGORY_FIELDS & set(vals):
            return super().write(vals)
        due_before = {
            template.id: template._raffle_sponsored_category_due()
            for template in self
        }
        result = super().write(vals)
        due_now = {
            template.id: template._raffle_sponsored_category_due()
            for template in self
        }
        self._raffle_sponsored_category_move(
            self.filtered(lambda t: due_now[t.id] and not due_before[t.id]),
            self.filtered(lambda t: due_before[t.id] and not due_now[t.id]),
        )
        return result

    def _raffle_sponsored_category_due(self):
        """Whether this prize belongs in SPONSORED_CATEGORY: a raffle prize
        with a sponsor, approved. A prize of the organization never does."""
        self.ensure_one()
        template = self.sudo()
        return bool(
            template.is_raffle_prize
            and template.raffle_sponsor_id
            and template.raffle_sponsor_state == "approved"
        )

    @api.model
    def _raffle_sponsored_category(self):
        """The public category SPONSORED_CATEGORY, or None once the
        organization deleted it."""
        return self.env.ref(SPONSORED_CATEGORY, raise_if_not_found=False)

    @api.model
    def _raffle_sponsored_category_move(self, entering, leaving):
        """Add the prizes `entering` to SPONSORED_CATEGORY and remove the
        prizes `leaving` from it. Without the category, nothing moves: the
        approval goes on, and the prizes keep their other categories."""
        if not (entering or leaving):
            return
        category = self._raffle_sponsored_category()
        if not category:
            return
        # sudo: the category follows the approval state, which a
        # sponsorship manager and the portal write as superuser too (see
        # action_raffle_sponsor_approve()).
        if entering:
            entering.sudo().write(
                {"public_categ_ids": [Command.link(category.id)]}
            )
        if leaving:
            leaving.sudo().write(
                {"public_categ_ids": [Command.unlink(category.id)]}
            )

    @api.constrains("active", "raffle_sponsor_state")
    def _check_raffle_sponsor_state_active(self):
        for template in self:
            if template.active and template.raffle_sponsor_state != "approved":
                raise ValidationError(
                    _(
                        "%s waits for the approval of the organization: "
                        "approve it instead of restoring it.",
                        template.display_name,
                    )
                )

    @api.depends("raffle_event_ids", "raffle_sponsor_id")
    @api.depends_context("uid")
    def _compute_raffle_sponsor_can_review(self):
        for template in self:
            template.raffle_sponsor_can_review = (
                template._raffle_sponsor_reviewer_allowed()
            )

    def _search_raffle_sponsor_can_review(self, operator, value):
        """Domain of the prizes the current user may review, as
        _raffle_sponsor_reviewer_allowed() decides for one prize: every
        prize for an event manager; for anyone else, the sponsored prizes
        whose events, one at least, are all managed by the user. Only `=`
        and `!=` with a boolean are supported.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise UserError(_("Operation not supported"))
        positive = (operator == "=") == value
        user = self.env.user
        if self.env.su or user.has_group("event.group_event_manager"):
            return [(1, "=", 1)] if positive else [(0, "=", 1)]
        events = (
            self.env["event.event"]
            .sudo()
            .with_context(active_test=False)
            .search([("raffle_sponsor_manager_ids", "in", user.ids)])
        )
        template_ids = []
        if events:
            # A prize qualifies when every row of its event list names one
            # of these events. The pending writes of the event lists are
            # flushed first: the query reads the table.
            self.flush_model(["raffle_event_ids"])
            self.env.cr.execute(
                SQL(
                    """
                    SELECT rel.product_tmpl_id
                      FROM product_template_raffle_event_rel rel
                     GROUP BY rel.product_tmpl_id
                    HAVING bool_and(rel.event_id = ANY(%s))
                    """,
                    events.ids,
                )
            )
            template_ids = [row[0] for row in self.env.cr.fetchall()]
        if positive:
            return [
                ("raffle_sponsor_id", "!=", False),
                ("id", "in", template_ids),
            ]
        return [
            "|",
            ("raffle_sponsor_id", "=", False),
            ("id", "not in", template_ids),
        ]

    def _raffle_sponsor_reviewer_allowed(self):
        """Whether the current user may approve or refuse this prize: an
        event manager, or a sponsorship manager of all the events of a
        sponsored prize. A prize offered to any event (no event set), or
        without a sponsor, is left to the event managers.
        """
        self.ensure_one()
        user = self.env.user
        if self.env.su or user.has_group("event.group_event_manager"):
            return True
        template = self.sudo()
        return bool(
            template.raffle_sponsor_id
        ) and template.raffle_event_ids._raffle_sponsor_managed_by(user)

    def _raffle_sponsor_check_review(self):
        """Raise AccessError unless the current user may approve or refuse
        every prize of self (see _raffle_sponsor_reviewer_allowed())."""
        if self.env.su:
            return
        if self.env.user.has_group("event.group_event_manager"):
            self.check_access("write")
            return
        for template in self:
            if not template._raffle_sponsor_reviewer_allowed():
                raise AccessError(
                    _(
                        "Only an event manager, or a sponsorship manager of "
                        "every event of %s, approves or refuses it.",
                        template.sudo().display_name,
                    )
                )

    @api.model
    def _raffle_sponsor_availability_vals(self, state):
        """Values that put a prize in the approval state `state`: only an
        approved prize is active, and so offered anywhere."""
        return {"raffle_sponsor_state": state, "active": state == "approved"}

    # ------------------------------------------------------------------
    # Organization
    # ------------------------------------------------------------------

    def action_raffle_sponsor_approve(self):
        """Approve the submitted or refused prizes: they are restored,
        published, and offered to the winners. Each one needs its token
        category. An approved prize is refused here, archived or not: its
        availability is the event managers' business."""
        self._raffle_sponsor_check_review()
        if self.filtered(
            lambda t: not t.is_raffle_prize
            or t.raffle_sponsor_state not in ("submitted", "refused")
        ):
            raise UserError(
                _("Only a submitted or refused prize can be approved.")
            )
        for template in self:
            if not template.raffle_band_id:
                raise UserError(
                    _(
                        "Set the token category of %s before approving it: "
                        "winners take a prize with a token of its category.",
                        template.display_name,
                    )
                )
        vals = self._raffle_sponsor_availability_vals("approved")
        vals.update(is_published=True, raffle_sponsor_refusal_reason=False)
        # sudo: restoring a product restores its variants and their stock
        # rules, which event managers may not write, and a sponsorship
        # manager writes no product. The reviewer is checked above.
        self.sudo().write(vals)
        return True

    def _raffle_sponsor_refuse(self, reason):
        """Refuse the submitted prizes with `reason`, shown to the sponsor
        in the portal."""
        self._raffle_sponsor_check_review()
        reason = (reason or "").strip()
        if not reason:
            raise UserError(_("Say why the prize is refused."))
        if self.filtered(lambda t: t.raffle_sponsor_state != "submitted"):
            raise UserError(_("Only a submitted prize can be refused."))
        vals = self._raffle_sponsor_availability_vals("refused")
        vals.update(raffle_sponsor_refusal_reason=reason, is_published=False)
        # sudo: see action_raffle_sponsor_approve().
        self.sudo().write(vals)
        return True

    def action_open_raffle_sponsor_refuse_wizard(self):
        self.ensure_one()
        self._raffle_sponsor_check_review()
        return {
            "type": "ir.actions.act_window",
            "name": _("Refuse the Prize"),
            "res_model": "event.raffle.prize.refuse.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_product_tmpl_id": self.id},
        }

    # ------------------------------------------------------------------
    # Sponsor portal (called as superuser by the controller, which checks
    # the user, the event and the ownership first)
    # ------------------------------------------------------------------

    @api.model
    def _raffle_sponsor_portal_prizes(self, partner, events):
        """Prizes of the commercial entity of `partner` for `events`, as
        superuser, archived ones included unless approved: the submitted
        and refused prizes are archived until approved."""
        commercial = partner.commercial_partner_id
        return (
            self.sudo()
            .with_context(active_test=False, lang=SOURCE_LANG)
            .search(
                [
                    ("is_raffle_prize", "=", True),
                    ("raffle_sponsor_id", "child_of", commercial.id),
                    ("raffle_event_ids", "in", events.ids),
                    "|",
                    ("active", "=", True),
                    ("raffle_sponsor_state", "!=", "approved"),
                ],
                order="name, id",
            )
        )

    @api.model
    def _raffle_sponsor_photo(self, photo):
        """`photo` (raw bytes from the portal) as the base64 value of
        image_1920.

        The image is always decoded and encoded again, whatever its size
        and type: its orientation is applied from its EXIF data, it is
        reduced to PHOTO_MAX_SIZE pixels on its largest side, and it is
        saved as a JPEG, or as a PNG when it has transparency, without its
        metadata. An approved prize is published with this image, so the
        position, device and time a camera writes in a photo are dropped;
        Odoo's image_process() keeps the original bytes of an image it does
        not resize, and never resizes a WebP image. Raises UserError for a
        file over PHOTO_MAX_BYTES or IMAGE_MAX_RESOLUTION pixels, and for
        one that is not a JPEG, PNG, GIF or WebP image.
        """
        if len(photo) > PHOTO_MAX_BYTES:
            raise UserError(_("The photo is too large."))
        if guess_mimetype(photo, default="") not in PHOTO_MIMETYPES:
            raise UserError(
                _("The photo must be a JPEG, PNG, GIF or WebP image.")
            )
        try:
            # Opening reads the header only: the size is known before the
            # pixels are decoded.
            image = binary_to_image(photo)
            width, height = image.size
        except (UserError, ValueError, OSError, Image.DecompressionBombError):
            raise UserError(_("The photo could not be read.")) from None
        if width * height > IMAGE_MAX_RESOLUTION:
            raise UserError(_("The photo is too large."))
        try:
            image = image_fix_orientation(image)
            image.thumbnail(
                (PHOTO_MAX_SIZE, PHOTO_MAX_SIZE), Image.Resampling.LANCZOS
            )
            transparent = image.mode in ("RGBA", "LA", "PA") or (
                image.mode == "P" and "transparency" in image.info
            )
            image = image.convert("RGBA" if transparent else "RGB")
            # convert() copies the metadata of the source (EXIF, XMP, ICC
            # profile, comments): the saved image carries none of it.
            image.info = {}
            if transparent:
                data = image_apply_opt(image, "PNG", optimize=True)
            else:
                data = image_apply_opt(
                    image, "JPEG", quality=PHOTO_JPEG_QUALITY, optimize=True
                )
        except (ValueError, OSError) as error:
            raise UserError(_("The photo could not be read.")) from error
        return base64.b64encode(data)

    def _raffle_sponsor_given_count(self):
        """Units of this prize given to winners: shipped or handed over
        (a virtual prize sent counts as handed over). A count only: the
        portal never shows who won."""
        self.ensure_one()
        products = self.sudo().with_context(active_test=False)
        return (
            self.env["event.raffle.draw"]
            .sudo()
            .search_count(
                [
                    (
                        "prize_product_id",
                        "in",
                        products.product_variant_ids.ids,
                    ),
                    ("claim_state", "in", ("shipped", "delivered")),
                ]
            )
        )

    @api.model
    def _raffle_sponsor_ecommerce_html(self, description):
        """The eCommerce description that the portal makes of the plain
        text `description`, or False for no text.

        The text is escaped, so markup typed by the sponsor stays text; a
        line break becomes <br/>, an empty line starts a paragraph, and a
        web address becomes a link.
        """
        return plaintext2html(description) if description else False

    @api.model
    def _raffle_sponsor_ecommerce_vals(self, description):
        """Write values of the eCommerce description that the portal makes
        of the plain text `description`: the description, and the
        sanitized copy of it that raffle_sponsor_ecommerce_portal keeps
        for _raffle_sponsor_ecommerce_from_portal()."""
        html = self._raffle_sponsor_ecommerce_html(description)
        return {
            "description_ecommerce": html,
            "raffle_sponsor_ecommerce_portal": (
                html_sanitize(html, silent=True) if html else False
            ),
        }

    def _raffle_sponsor_ecommerce_from_portal(self):
        """Whether the portal may write the eCommerce description of this
        prize: it is empty, or it still equals the one the portal wrote
        last (raffle_sponsor_ecommerce_portal).

        An organization that reworks the eCommerce description in the
        backend keeps its version: the sponsor's next edit changes the sale
        description only. A change of the sale description by anyone else
        does not matter: the comparison never reads it. The description is
        read in SOURCE_LANG, the language the portal writes. It goes
        through the sanitizer before the comparison: a write stores the
        value sanitized or as given, depending on the writer's groups, and
        the sanitizer gives both forms the same markup as the kept copy.
        """
        self.ensure_one()
        template = self.sudo().with_context(lang=SOURCE_LANG)
        current = template.description_ecommerce
        if is_html_empty(current):
            return True
        written = template.raffle_sponsor_ecommerce_portal
        return bool(written) and html_sanitize(current, silent=True) == written

    def _raffle_sponsor_portal_editable(self):
        self.ensure_one()
        return self.raffle_sponsor_state in SPONSOR_EDITABLE_STATES

    @api.model
    def _raffle_sponsor_portal_vals(self, values, event):
        """Write values of the portal form: the fields of PORTAL_FIELDS
        found in `values`, plus the event. Any other key is dropped."""
        vals = {key: values[key] for key in PORTAL_FIELDS if key in values}
        vals["raffle_event_ids"] = [Command.set(event.ids)]
        return vals

    @api.model
    def _raffle_sponsor_portal_create(self, partner, event, values):
        """Create the prize that `partner` submits for `event`.

        The sponsor is the commercial entity of `partner`: the company of a
        contact that has one, else the person. The prize starts submitted,
        archived and unpublished, without member sales; the managers of
        the event are notified.
        """
        vals = self._raffle_sponsor_portal_vals(values, event)
        if "description_sale" in vals:
            vals.update(
                self._raffle_sponsor_ecommerce_vals(vals["description_sale"])
            )
        vals.update(
            self._raffle_sponsor_availability_vals("submitted"),
            is_raffle_prize=True,
            type="consu",
            is_storable=True,
            raffle_sponsor_id=partner.commercial_partner_id.id,
            raffle_member_sale_ok=False,
            is_published=False,
        )
        template = (
            self.sudo()
            .with_context(lang=SOURCE_LANG, mail_create_nosubscribe=True)
            .create(vals)
        )
        template._raffle_sponsor_notify(event)
        return template

    def _raffle_sponsor_portal_write(self, event, values):
        """Write the sponsor's changes of a submitted or refused prize.

        Only the values that differ from the prize's are written (see
        _raffle_sponsor_changed_vals()): a form saved unchanged writes
        nothing. A refused prize is submitted again and the managers are
        notified; a submitted prize stays submitted, and the managers are
        told that it changed, whenever a value did.

        A sales price that changes recomputes the token category, unless
        the category differs from the one the current price gives: a
        reviewer chose it, and it stays (see
        _raffle_sponsor_band_set_by_hand()).
        """
        self.ensure_one()
        if not self._raffle_sponsor_portal_editable():
            raise UserError(_("An approved prize can no longer be changed."))
        vals = self._raffle_sponsor_changed_vals(
            self._raffle_sponsor_portal_vals(values, event)
        )
        if (
            "description_sale" in vals
            and self._raffle_sponsor_ecommerce_from_portal()
        ):
            vals.update(
                self._raffle_sponsor_ecommerce_vals(vals["description_sale"])
            )
        if "list_price" in vals and self._raffle_sponsor_band_set_by_hand():
            vals["raffle_band_id"] = self.raffle_band_id.id
        resubmitted = self.raffle_sponsor_state == "refused"
        if resubmitted:
            vals.update(
                self._raffle_sponsor_availability_vals("submitted"),
                raffle_sponsor_refusal_reason=False,
            )
        if vals:
            self.sudo().with_context(lang=SOURCE_LANG).write(vals)
        if resubmitted:
            self._raffle_sponsor_notify(event, resubmitted=True)
        elif vals:
            self._raffle_sponsor_notify(event, changed=True)
        return True

    def _raffle_sponsor_changed_vals(self, vals):
        """The items of the write values `vals` that change this prize.

        Each value is compared with the prize's, read as superuser in
        SOURCE_LANG, the language the portal writes, once converted the way
        the field stores it: a float to its precision, a list of commands to
        its records.
        """
        self.ensure_one()
        template = self.sudo().with_context(lang=SOURCE_LANG)
        changed = {}
        for name, value in vals.items():
            field = template._fields[name]
            new = field.convert_to_record(
                field.convert_to_cache(value, template), template
            )
            if new != template[name]:
                changed[name] = value
        return changed

    def _raffle_sponsor_band_set_by_hand(self):
        """Whether the token category of this prize was chosen by hand: it
        differs from the one its sales price gives."""
        self.ensure_one()
        template = self.sudo()
        Band = self.env["event.raffle.prize.band"].sudo()
        return template.raffle_band_id != Band._band_for_value(
            template.list_price
        )

    def _raffle_sponsor_portal_withdraw(self):
        """Delete the submitted or refused prize, unless a stock move or
        an order line already holds it."""
        self.ensure_one()
        if not self._raffle_sponsor_portal_editable():
            raise UserError(_("An approved prize can no longer be withdrawn."))
        template = self.sudo().with_context(active_test=False)
        products = template.product_variant_ids
        used = self.env["stock.move"].sudo().search_count(
            [("product_id", "in", products.ids)], limit=1
        ) or self.env["sale.order.line"].sudo().search_count(
            [("product_id", "in", products.ids)], limit=1
        )
        if used:
            raise UserError(
                _(
                    "The organization already holds %s in its inventory or "
                    "an order: ask the organization to withdraw it.",
                    template.name,
                )
            )
        template.unlink()
        return True

    def _raffle_sponsor_notify(self, event, resubmitted=False, changed=False):
        """Notify the recipients of `event` that the sponsor submitted this
        prize, submitted it again once refused (`resubmitted`), or changed
        it while it waits for review (`changed`), in their inbox or by
        email as each one prefers.

        The recipients are the sponsorship managers of the event, else its
        responsible user (see event.event._raffle_sponsor_recipients());
        nobody is notified when both are empty. One message goes to each
        language of the recipients, with a link to the prize. The author
        is the current user, or OdooBot when the user has no email address,
        which message_notify() requires.
        """
        self.ensure_one()
        recipients = event._raffle_sponsor_recipients()
        if not recipients:
            return self.env["mail.message"]
        author = self.env.user.partner_id
        if not author.email:
            author = self.env.ref("base.partner_root")
        template = self.sudo()
        sponsor = template.raffle_sponsor_id.display_name
        messages = self.env["mail.message"]
        for lang in set(recipients.mapped("lang")):
            partners = recipients.filtered(lambda p, lang=lang: p.lang == lang)
            prize = template.with_context(lang=lang)
            env_lang = prize.env
            if changed:
                subject = env_lang._("Prize changed: %s", prize.name)
                body = env_lang._(
                    "%(sponsor)s changed the prize %(prize)s for %(event)s, "
                    "which waits for review: check it again, its token "
                    "category included, before approving it.",
                    sponsor=sponsor,
                    prize=prize.name,
                    event=event.with_context(lang=lang).name,
                )
            elif resubmitted:
                subject = env_lang._("Prize to review again: %s", prize.name)
                body = env_lang._(
                    "%(sponsor)s changed the refused prize %(prize)s for "
                    "%(event)s: review it again.",
                    sponsor=sponsor,
                    prize=prize.name,
                    event=event.with_context(lang=lang).name,
                )
            else:
                subject = env_lang._("Prize to review: %s", prize.name)
                body = env_lang._(
                    "%(sponsor)s submitted the prize %(prize)s for "
                    "%(event)s: set its token category, then approve or "
                    "refuse it.",
                    sponsor=sponsor,
                    prize=prize.name,
                    event=event.with_context(lang=lang).name,
                )
            messages |= prize.message_notify(
                partner_ids=partners.ids,
                author_id=author.id,
                subject=subject,
                body=escape(body),
            )
        return messages
