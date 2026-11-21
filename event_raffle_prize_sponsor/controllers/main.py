# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import re

from werkzeug.exceptions import NotFound

from odoo import _
from odoo.exceptions import UserError
from odoo.http import request, route
from odoo.tools import html2plaintext, plaintext2html
from odoo.tools.misc import format_amount

from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.product_template import PHOTO_MAX_BYTES

# Longest name, description and instructions the portal form accepts.
NAME_MAX_LENGTH = 120
TEXT_MAX_LENGTH = 4000
# Largest value in dollars and largest quantity of one prize.
VALUE_MAX = 1_000_000
QUANTITY_MAX = 10_000
# A value in dollars: digits, with a dot or a comma and up to two decimals.
VALUE_PATTERN = re.compile(r"^\d+(?:[.,]\d{1,2})?$")
# Kinds of prize of the form, and the prize fields each one sets: a
# physical prize is picked up on site, a virtual prize is sent by email
# and may go to any winner.
MODES = {
    "physical": {"raffle_virtual_prize": False, "raffle_attendance": "onsite"},
    "virtual": {"raffle_virtual_prize": True, "raffle_attendance": "both"},
}
# Order of the fields in the error summary of the form.
FORM_FIELDS = (
    "event_id",
    "name",
    "description",
    "photo",
    "value",
    "quantity",
    "mode",
    "instructions",
)
# Colour of the badge of each approval state: the subtle background with
# its emphasis text keeps a contrast above 4.5:1, the border outlines it.
STATE_BADGES = {
    state: f"border border-{colour} bg-{colour}-subtle text-{colour}-emphasis"
    for state, colour in (
        ("submitted", "warning"),
        ("approved", "success"),
        ("refused", "danger"),
    )
}


def _plain_text(value):
    """`value` of a textarea with its line breaks as one LF each.

    A browser counts a line break as one character against maxlength but
    sends it as CRLF: measuring the text sent would exceed the limit the
    browser applied.
    """
    return (value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class RafflePrizeSponsorPortal(CustomerPortal):
    """Prizes for raffle, in the portal of a sponsor.

    A signed-in user reaches these pages while their contact, or another
    contact of the same commercial entity, has a sponsor registration on
    a sponsor-managed event that is not over (see
    event.event._raffle_sponsor_events()); any other user gets 404.

    Portal users have no access to products: the pages read and write the
    prizes as superuser, after these checks. A prize id from the request
    is looked up among the prizes of the user's commercial entity for the
    allowed events only, so the prize of another entity answers 404. The
    form writes the fields of product.template.PORTAL_FIELDS only, from
    values parsed here; the event comes from the allowed events, and the
    sponsor, the approval state, the token category, the sale and
    publication flags and the stock are never read from the request. Every
    POST goes through Odoo's CSRF check.
    """

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def _raffle_sponsor_events(self):
        return request.env["event.event"]._raffle_sponsor_events(
            request.env.user.partner_id
        )

    def _raffle_sponsor_check(self):
        """The allowed events, or 404 for a user who sponsors none."""
        events = self._raffle_sponsor_events()
        if not events:
            raise NotFound()
        return events

    def _raffle_sponsor_prize(self, prize_id, events):
        """The prize `prize_id` of the user's commercial entity for
        `events`, as superuser, or 404."""
        prizes = request.env["product.template"]._raffle_sponsor_portal_prizes(
            request.env.user.partner_id, events
        )
        prize = prizes.filtered(lambda p: p.id == prize_id)
        if not prize:
            raise NotFound()
        return prize

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if not counters:
            values["raffle_sponsor_open"] = bool(self._raffle_sponsor_events())
        return values

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _raffle_sponsor_layout_values(self, events, **values):
        result = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        result.update(
            sponsor_name=partner.commercial_partner_id.name,
            events=events,
            **values,
        )
        return result

    def _raffle_sponsor_prize_values(self, prize):
        """What the pages show of `prize`, in the current language."""
        Template = request.env["product.template"]
        states = dict(
            Template._fields["raffle_sponsor_state"]._description_selection(
                request.env
            )
        )
        state = prize.raffle_sponsor_state
        band = prize.raffle_band_id.with_context(lang=request.env.lang)
        return {
            "id": prize.id,
            "name": prize.name,
            "description": prize.description_sale or "",
            "has_image": bool(prize.image_128),
            "state": state,
            "state_label": states[state],
            "state_class": STATE_BADGES[state],
            "value": format_amount(
                request.env, prize.list_price, prize.currency_id
            ),
            "quantity": int(prize.raffle_initial_qty),
            "virtual": prize.raffle_virtual_prize,
            "instructions": html2plaintext(
                prize.raffle_virtual_instructions or ""
            ).strip(),
            "band": band.name if band else "",
            "reason": (
                prize.raffle_sponsor_refusal_reason
                if state == "refused"
                else ""
            ),
            "editable": prize._raffle_sponsor_portal_editable(),
            "given": (
                prize._raffle_sponsor_given_count()
                if state == "approved"
                else None
            ),
            "events": prize.raffle_event_ids,
        }

    def _raffle_sponsor_message(self, key):
        return {
            "created": _(
                "Thank you: your prize is submitted. The organization "
                "reviews it before offering it."
            ),
            "saved": _("Your changes are saved."),
            "withdrawn": _("The prize is withdrawn."),
        }.get(key, "")

    @route(
        "/my/raffle-prizes",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def raffle_sponsor_prizes(self, message=None, **kwargs):
        events = self._raffle_sponsor_check()
        prizes = request.env["product.template"]._raffle_sponsor_portal_prizes(
            request.env.user.partner_id, events
        )
        groups = []
        for event in events:
            event_prizes = prizes.filtered(
                lambda p, event=event: event in p.raffle_event_ids
            )
            groups.append(
                {
                    "event": event,
                    "prizes": [
                        self._raffle_sponsor_prize_values(p)
                        for p in event_prizes
                    ],
                }
            )
        return request.render(
            "event_raffle_prize_sponsor.portal_raffle_sponsor_prizes",
            self._raffle_sponsor_layout_values(
                events,
                page_name="raffle_prizes",
                groups=groups,
                message=self._raffle_sponsor_message(message),
            ),
        )

    @route(
        "/my/raffle-prizes/<int:prize_id>/image",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def raffle_sponsor_prize_image(self, prize_id, **kwargs):
        prize = self._raffle_sponsor_prize(
            prize_id, self._raffle_sponsor_check()
        )
        stream = request.env["ir.binary"]._get_image_stream_from(
            prize, "image_256", placeholder="web/static/img/placeholder.png"
        )
        return stream.get_response()

    # ------------------------------------------------------------------
    # Form
    # ------------------------------------------------------------------

    def _raffle_sponsor_form_values(self, prize):
        """Values of the form fields for the prize being edited."""
        if not prize:
            return {"mode": "physical", "quantity": "1"}
        values = self._raffle_sponsor_prize_values(prize)
        return {
            "event_id": str(prize.raffle_event_ids[:1].id),
            "name": prize.name,
            "description": values["description"],
            "value": f"{prize.list_price:.2f}",
            "quantity": str(values["quantity"]),
            "mode": "virtual" if prize.raffle_virtual_prize else "physical",
            "instructions": values["instructions"],
        }

    def _raffle_sponsor_render_form(
        self, events, prize, form, errors=None, status=200
    ):
        errors = errors or {}
        if prize:
            title = _("Change the prize %s", prize.name)
        else:
            title = _("Add a prize")
        error_list = [
            {"field": field, "message": errors[field]}
            for field in FORM_FIELDS
            if field in errors
        ]
        if len(error_list) == 1:
            errors_title = _("The form has 1 error:")
        else:
            errors_title = _("The form has %s errors:", len(error_list))
        return request.render(
            "event_raffle_prize_sponsor.portal_raffle_sponsor_prize_form",
            self._raffle_sponsor_layout_values(
                events,
                page_name="raffle_prize",
                breadcrumb_title=title,
                title=title,
                prize=(
                    self._raffle_sponsor_prize_values(prize)
                    if prize
                    else False
                ),
                form=form,
                errors=errors,
                error_list=error_list,
                errors_title=errors_title,
                action=(
                    f"/my/raffle-prizes/{prize.id}"
                    if prize
                    else "/my/raffle-prizes/new"
                ),
                photo_max_mb=PHOTO_MAX_BYTES // (1024 * 1024),
                name_max=NAME_MAX_LENGTH,
                text_max=TEXT_MAX_LENGTH,
            ),
            status=status,
        )

    def _raffle_sponsor_parse(self, post, events):
        """Parse the form: (values, event, form, errors).

        `values` holds the prize fields of the portal (see
        product.template.PORTAL_FIELDS), `event` the chosen event among
        `events`, `form` the strings sent, to fill the form again, and
        `errors` the message of each field in error. Any other parameter
        of the request is ignored.
        """
        Template = request.env["product.template"]
        form = {
            key: (post.get(key) or "").strip()
            for key in FORM_FIELDS
            if key != "photo"
        }
        errors = {}
        values = {}
        event = events.browse()
        if len(events) == 1:
            event = events
        else:
            event_id = _int_or_zero(form["event_id"])
            event = events.filtered(lambda e: e.id == event_id)
            if not event:
                errors["event_id"] = _("Choose the event of the prize.")
        name = form["name"]
        if not name:
            errors["name"] = _("Give the name of the prize.")
        elif len(name) > NAME_MAX_LENGTH:
            errors["name"] = _(
                "The name is too long: %s characters at most.",
                NAME_MAX_LENGTH,
            )
        else:
            values["name"] = name
        description = _plain_text(post.get("description"))
        if len(description) > TEXT_MAX_LENGTH:
            errors["description"] = _(
                "The description is too long: %s characters at most.",
                TEXT_MAX_LENGTH,
            )
        else:
            values["description_sale"] = description or False
        value = form["value"].replace(" ", "").replace("$", "")
        if not VALUE_PATTERN.match(value):
            errors["value"] = _(
                "Give the value in dollars, as a number such as 25 or 25.50."
            )
        elif float(value.replace(",", ".")) > VALUE_MAX:
            errors["value"] = _(
                "The value is too high: %s at most.",
                format_amount(
                    request.env, VALUE_MAX, request.env.company.currency_id
                ),
            )
        else:
            values["list_price"] = float(value.replace(",", "."))
        quantity = form["quantity"]
        if not quantity.isdigit() or not 1 <= int(quantity) <= QUANTITY_MAX:
            errors["quantity"] = _(
                "Give the quantity as a whole number from 1 to %s.",
                QUANTITY_MAX,
            )
        else:
            values["raffle_initial_qty"] = int(quantity)
        mode = form["mode"]
        if mode not in MODES:
            errors["mode"] = _("Choose the kind of prize.")
        else:
            values.update(MODES[mode])
        instructions = _plain_text(post.get("instructions"))
        if len(instructions) > TEXT_MAX_LENGTH:
            errors["instructions"] = _(
                "The instructions are too long: %s characters at most.",
                TEXT_MAX_LENGTH,
            )
        elif mode == "virtual":
            values["raffle_virtual_instructions"] = (
                plaintext2html(instructions) if instructions else False
            )
        elif mode == "physical":
            values["raffle_virtual_instructions"] = False
        form["description"] = description
        form["instructions"] = instructions
        upload = request.httprequest.files.get("photo")
        photo = upload.read(PHOTO_MAX_BYTES + 1) if upload else b""
        if photo:
            try:
                values["image_1920"] = Template._raffle_sponsor_photo(photo)
            except UserError as error:
                errors["photo"] = error.args[0]
        if errors and photo and "photo" not in errors:
            errors["photo"] = _(
                "Choose the photo again: it is not kept while the form has "
                "errors."
            )
        return values, event, form, errors

    @route(
        "/my/raffle-prizes/new",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
    )
    def raffle_sponsor_prize_new(self, **post):
        events = self._raffle_sponsor_check()
        if request.httprequest.method != "POST":
            form = self._raffle_sponsor_form_values(None)
            event_id = _int_or_zero(post.get("event_id"))
            if event_id in events.ids:
                form["event_id"] = str(event_id)
            return self._raffle_sponsor_render_form(events, None, form)
        values, event, form, errors = self._raffle_sponsor_parse(post, events)
        if errors:
            return self._raffle_sponsor_render_form(
                events, None, form, errors, status=400
            )
        request.env["product.template"]._raffle_sponsor_portal_create(
            request.env.user.partner_id, event, values
        )
        return request.redirect("/my/raffle-prizes?message=created")

    @route(
        "/my/raffle-prizes/<int:prize_id>",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
    )
    def raffle_sponsor_prize(self, prize_id, **post):
        events = self._raffle_sponsor_check()
        prize = self._raffle_sponsor_prize(prize_id, events)
        if not prize._raffle_sponsor_portal_editable():
            if request.httprequest.method == "POST":
                raise NotFound()
            return request.render(
                "event_raffle_prize_sponsor.portal_raffle_sponsor_prize_view",
                self._raffle_sponsor_layout_values(
                    events,
                    page_name="raffle_prize",
                    breadcrumb_title=prize.name,
                    prize=self._raffle_sponsor_prize_values(prize),
                ),
            )
        if request.httprequest.method != "POST":
            return self._raffle_sponsor_render_form(
                events, prize, self._raffle_sponsor_form_values(prize)
            )
        values, event, form, errors = self._raffle_sponsor_parse(post, events)
        if errors:
            return self._raffle_sponsor_render_form(
                events, prize, form, errors, status=400
            )
        prize._raffle_sponsor_portal_write(event, values)
        return request.redirect("/my/raffle-prizes?message=saved")

    @route(
        "/my/raffle-prizes/<int:prize_id>/withdraw",
        type="http",
        auth="user",
        website=True,
        methods=["GET", "POST"],
        sitemap=False,
    )
    def raffle_sponsor_prize_withdraw(self, prize_id, **post):
        events = self._raffle_sponsor_check()
        prize = self._raffle_sponsor_prize(prize_id, events)
        if not prize._raffle_sponsor_portal_editable():
            raise NotFound()
        error = False
        if request.httprequest.method == "POST":
            try:
                with request.env.cr.savepoint():
                    prize._raffle_sponsor_portal_withdraw()
            except UserError as exc:
                error = exc.args[0]
            else:
                return request.redirect("/my/raffle-prizes?message=withdrawn")
        return request.render(
            "event_raffle_prize_sponsor.portal_raffle_sponsor_prize_withdraw",
            self._raffle_sponsor_layout_values(
                events,
                page_name="raffle_prize",
                breadcrumb_title=prize.name,
                title=_("Withdraw %s?", prize.name),
                prize=self._raffle_sponsor_prize_values(prize),
                error=error,
            ),
            status=400 if error else 200,
        )
