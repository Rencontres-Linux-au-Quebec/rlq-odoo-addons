# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from werkzeug.exceptions import Forbidden, NotFound

from odoo import _, http
from odoo.exceptions import UserError
from odoo.http import request, route

from odoo.addons.event_raffle_prize_claim.controllers.main import (
    RafflePrizeClaim,
    WebsiteSaleRafflePrize,
    _invalid_link_page,
    _session_draw,
)
from odoo.addons.portal.controllers.portal import CustomerPortal

from ..models.event_raffle_draw import PHOTO_MAX_BYTES
from ..models.res_partner import PUBLIC_NAME_MAX_LENGTH

# Seconds between two refreshes of the winners page.
WINNERS_REFRESH_SECONDS = 600


def _done_draw():
    """The draw of the claim this session confirmed, as superuser, or empty.

    See event_raffle_prize_claim's _prize_claim_done_draw(): the draw must
    still hold its prize, and its winner must be the signed-in user.
    """
    return request.env["event.raffle.draw"]._prize_claim_done_draw()


class RafflePrizeHandoverClaim(RafflePrizeClaim):
    """The confirmation page of the prize link says how the prize reaches
    the winner, and lets the winner set their public name.

    The public name form changes the contact of the claim this session
    confirmed, and nothing else: the session names the draw, the request
    gives the name only.
    """

    @route()
    def raffle_prize_done(self, **kwargs):
        response = super().raffle_prize_done(**kwargs)
        qcontext = getattr(response, "qcontext", None)
        draw = _done_draw()
        if qcontext is None or not draw:
            return response
        partner = draw._prize_public_partner()
        qcontext.update(
            {
                "raffle_handover_line": draw._prize_handover_line(),
                "raffle_public_name": partner.raffle_public_name or "",
                "raffle_public_name_shown": draw._prize_public_name(),
                "raffle_public_name_saved": kwargs.get("public_name")
                == "saved",
                "raffle_public_name_max": PUBLIC_NAME_MAX_LENGTH,
            }
        )
        return response

    @route(
        "/raffle/prize/public-name",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        sitemap=False,
    )
    def raffle_prize_public_name(self, public_name=None, **kwargs):
        draw = _done_draw()
        partner = draw._prize_public_partner() if draw else None
        if not partner:
            return _invalid_link_page()
        partner._raffle_set_public_name(public_name)
        return request.redirect("/raffle/prize/done?public_name=saved")


class WebsiteSaleRafflePrizeHandover(WebsiteSaleRafflePrize):
    """A claim cart of a virtual prize asks for a name and an email only,
    as the cart of an on-site winner does: the prize goes by email."""

    def _raffle_prize_virtual_claim(self):
        draw = _session_draw()
        if not draw:
            return False
        order = request.website.sale_get_order()
        return bool(
            order
            and order.raffle_draw_id == draw
            and order._prize_lines().product_id.filtered(
                "raffle_virtual_prize"
            )
        )

    def _get_mandatory_delivery_address_fields(self, country_sudo):
        if self._raffle_prize_virtual_claim():
            return {"name", "email"}
        return super()._get_mandatory_delivery_address_fields(country_sudo)

    def _get_mandatory_billing_address_fields(self, country_sudo):
        if self._raffle_prize_virtual_claim():
            return {"name", "email"}
        return super()._get_mandatory_billing_address_fields(country_sudo)


class RafflePrizeHandover(http.Controller):
    """The hand-over screen of the event team, made for a phone.

    Event users only: a portal or internal user without the event rights
    gets 403, a visitor the sign-in page. Every record is read with the
    user's own rights, and the hand-over runs event_raffle_prize's
    delivery with its access checks.
    """

    def _check_event_user(self):
        if not request.env.user.has_group("event.group_event_user"):
            raise Forbidden()

    def _handover_draw(self, draw_id):
        draw = request.env["event.raffle.draw"].browse(draw_id).exists()
        if not draw:
            raise NotFound()
        draw.check_access("read")
        return draw

    @route(
        "/raffle/handover",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def raffle_handover(self, search="", done=None, **kwargs):
        self._check_event_user()
        search = (search or "")[:200]
        Draw = request.env["event.raffle.draw"]
        draws = Draw._prize_handover_search(search)
        done_draw = Draw
        try:
            done_id = int(done) if done else 0
        except ValueError:
            done_id = 0
        if done_id:
            done_draw = Draw.browse(done_id).exists()
            if done_draw:
                done_draw.check_access("read")
                if done_draw.claim_state != "delivered":
                    done_draw = Draw
        done_message = False
        if done_draw:
            done = done_draw._prize_handover_values()
            done_message = _(
                "%(prize)s handed over to %(name)s.",
                prize=done["prize"],
                name=done["name"],
            )
        if search:
            title = _('Prizes to hand over matching "%s"', search)
        else:
            title = _("Prizes to hand over")
        if not draws:
            count = _("No winner is waiting for a prize.")
        elif len(draws) == 1:
            count = _("1 winner is waiting for a prize.")
        else:
            count = _("%s winners are waiting for a prize.", len(draws))
        return request.render(
            "event_raffle_prize_handover.handover_list",
            {
                "search": search,
                "claims": [draw._prize_handover_values() for draw in draws],
                "done": bool(done_draw),
                "done_message": done_message,
                "results_title": title,
                "results_count": count,
            },
        )

    def _render_step(self, draw, error=False, status=200):
        return request.render(
            "event_raffle_prize_handover.handover_step",
            {
                "claim": draw._prize_handover_values(),
                "reserved": draw.claim_state == "reserved",
                "error": error,
            },
            status=status,
        )

    @route(
        "/raffle/handover/<int:draw_id>",
        type="http",
        auth="user",
        website=True,
        sitemap=False,
    )
    def raffle_handover_step(self, draw_id, **kwargs):
        self._check_event_user()
        return self._render_step(self._handover_draw(draw_id))

    @route(
        "/raffle/handover/<int:draw_id>/confirm",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        sitemap=False,
    )
    def raffle_handover_confirm(self, draw_id, **kwargs):
        """Hand the prize over, with the photo of the form when given.

        A refusal (the claim no longer reserved, an unreadable photo, a
        delivery that cannot be validated) rolls everything back and shows
        the step again with the reason. The same form sent again by the
        user who just handed the prize over leads to the success message
        of that hand-over (see _prize_handover_just_done()).
        """
        self._check_event_user()
        draw = self._handover_draw(draw_id)
        if draw._prize_handover_just_done():
            return request.redirect(f"/raffle/handover?done={draw.id}")
        upload = request.httprequest.files.get("photo")
        photo = upload.read(PHOTO_MAX_BYTES + 1) if upload else b""
        try:
            with request.env.cr.savepoint():
                draw._prize_hand_over(photo=photo or None)
        except UserError as error:
            return self._render_step(draw, error=error.args[0], status=400)
        return request.redirect(f"/raffle/handover?done={draw.id}")


class RaffleWinners(http.Controller):
    """Public winners page of an event, and its JSON data.

    Both answer 404 unless the event publishes its winners page, and read
    the public fields only (see event.event._raffle_winners_data()).
    """

    def _published_event(self, event_ref):
        __, event_id = request.env["ir.http"]._unslug(event_ref)
        if event_id is None and event_ref.isdigit():
            event_id = int(event_ref)
        if not event_id:
            raise NotFound()
        event = request.env["event.event"].sudo().browse(event_id).exists()
        if not event or not event.raffle_winners_published:
            raise NotFound()
        website = getattr(request, "website", None)
        if (
            "website_id" in event._fields
            and event.website_id
            and website
            and event.website_id != website
        ):
            raise NotFound()
        # The event is read as superuser, past the company rules: its
        # page answers on the website of its company only.
        if (
            website
            and event.company_id
            and event.company_id != website.company_id
        ):
            raise NotFound()
        return event

    @route(
        "/raffle/winners/<string:event_ref>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def raffle_winners(self, event_ref, **kwargs):
        event = self._published_event(event_ref)
        path = event._raffle_winners_path()
        return request.render(
            "event_raffle_prize_handover.winners_page",
            {
                "event_name": event.name,
                "data": event._raffle_winners_data(),
                "data_url": f"{path}/data",
                "refresh_seconds": WINNERS_REFRESH_SECONDS,
            },
        )

    @route(
        "/raffle/winners/<string:event_ref>/data",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
        sitemap=False,
    )
    def raffle_winners_data(self, event_ref, **kwargs):
        event = self._published_event(event_ref)
        return request.make_json_response(
            event._raffle_winners_data(),
            headers={"Cache-Control": "no-store"},
        )


class CustomerPortalRafflePublicName(CustomerPortal):
    """The account form of the portal sets the user's public name."""

    def _get_optional_fields(self):
        return [*super()._get_optional_fields(), "raffle_public_name"]

    def details_form_validate(self, data, partner_creation=False):
        error, error_message = super().details_form_validate(
            data, partner_creation=partner_creation
        )
        if len(data.get("raffle_public_name") or "") > PUBLIC_NAME_MAX_LENGTH:
            error["raffle_public_name"] = "error"
            error_message.append(
                _(
                    "The public name holds %s characters at most.",
                    PUBLIC_NAME_MAX_LENGTH,
                )
            )
        return error, error_message

    def on_account_update(self, values, partner):
        result = super().on_account_update(values, partner)
        if "raffle_public_name" in values:
            values["raffle_public_name"] = partner._raffle_clean_public_name(
                values["raffle_public_name"]
            )
        return result
