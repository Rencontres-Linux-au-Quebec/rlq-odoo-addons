# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Raffle prizes of the /webapp_event pages, controller side.

The class extends the controller of event_webapp_plan: its
_ewp_page_values() hands the home page the plain values of two blocks,
read by the templates of views/webapp_templates.xml through the slot
webapp_slot_home_cards:

- "My prize" (prize_*): one line per draw of the day won by the partner
  of the current user (event.webapp._ewp_prize_draws()), with its state:
  "open" (the prize link works: the button "Choose my prize" and its
  deadline), "waiting" (no link yet), "link_expired", then the claim
  states of event_raffle_prize_handover: "reserved" (how the prize reaches
  the winner, from draw._prize_handover_line()), "shipped" (tracking
  number), "delivered", "declined" and "expired". The card also holds the
  public name form. When the user won nothing the card is not rendered:
  its box stays empty and hidden, and the page script fills it when a draw
  comes in.
- "On site" (presence): the self-declared attendance of the registrations
  of the current user to the events of the day, a toggle button.

Access: every route runs as the logged-in user, reads the day through the
sudo record of the parent controller once _ewp_can_view() allowed the
user (403 otherwise), and reads the draws and registrations of the
partner of that user only; no partner, draw or registration id of the
request is ever read. Only the fields rendered below leave the server: the
prize link (a token) is sent to its own winner only, and no e-mail, no
address and no photo is sent at all.

Forms: POST with the CSRF token. A request that accepts JSON gets the
re-rendered block and the message to say; a plain form gets a 303
redirect to the home page, which shows the message once (kept in the
session under NOTICE_KEY).

The raffle block of the web app, which lists the raffles listed on the
day, names a winner by their public name when their contact has one, and
shows the prize of each winner as the winners page does, the prize to
choose included (_ewp_raffle_values()).
"""

from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request
from odoo.tools.misc import format_time

from odoo.addons.event_webapp_plan.controllers.main import (
    WEBAPP_ROOT,
    EventWebappController,
)

# Templates of the blocks the routes render again.
PRIZE_TEMPLATE = "event_webapp_plan_raffle.prize_content"
PRESENCE_TEMPLATE = "event_webapp_plan_raffle.presence_content"
# Session key of the message the next home page shows once: a key of
# _ewp_prize_notices().
NOTICE_KEY = "ewp_raffle_notice"
PUBLIC_NAME_MAX_LENGTH = 64


class EventWebappRaffleController(EventWebappController):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ewp_prize_notices(self):
        """Translated messages of the two forms, by key."""
        _ = request.env._
        return {
            "public_name": _("Your public name is saved."),
            "on_site": _("You are marked on site."),
            "off_site": _("You are no longer marked on site."),
        }

    def _ewp_pop_notice(self, block):
        """Message kept in the session for ``block`` ("prize" or
        "presence"), removed once read; "" otherwise."""
        key = request.session.get(NOTICE_KEY)
        owner = "prize" if key == "public_name" else "presence"
        if not key or owner != block:
            return ""
        request.session.pop(NOTICE_KEY, None)
        return self._ewp_prize_notices().get(key, "")

    def _ewp_short_label(self, value, tz):
        """Short time of the UTC datetime ``value`` in ``tz``, kept on one
        line."""
        return format_time(request.env, value, tz, "short").replace(" ", " ")

    def _ewp_prize_status(self, draw, tz):
        """(state, status sentence, link, deadline) of ``draw`` (sudo)."""
        _ = request.env._
        state = draw.claim_state
        if state == "none":
            if draw._claim_link_is_open():
                label = self._ewp_short_label(draw.claim_deadline, tz)
                return (
                    "open",
                    _("Choose your prize before %(time)s.", time=label),
                    draw.claim_link_url,
                    self._ewp_iso(draw.claim_deadline),
                )
            if draw.claim_link_state == "expired":
                return (
                    "link_expired",
                    _(
                        "The link to choose your prize has expired. Ask the "
                        "organizers of the raffle."
                    ),
                    False,
                    False,
                )
            return (
                "waiting",
                _(
                    "You won this draw. The organizers will send you how to "
                    "get your prize."
                ),
                False,
                False,
            )
        if state == "reserved":
            return state, draw._prize_handover_line(), False, False
        if state == "shipped":
            return state, _("Your prize was shipped."), False, False
        if state == "delivered":
            mode = draw._prize_delivery_mode()
            if mode == "virtual":
                text = _("Your prize was sent to you by email.")
            elif mode == "shipping":
                text = _("You received your prize.")
            else:
                text = _("Your prize was handed over to you.")
            return state, text, False, False
        if state == "declined":
            return state, _("You declined this prize."), False, False
        return state, _("The time to choose this prize is over."), False, False

    def _ewp_prize_line(self, draw, tz):
        """Plain values of the line of ``draw`` (sudo) in the card."""
        _ = request.env._
        product = draw.prize_product_id
        template = product.product_tmpl_id
        band = template.raffle_band_id or draw.band_id
        state, status, link, deadline = self._ewp_prize_status(draw, tz)
        title = _(
            "%(raffle)s, draw %(number)s",
            raffle=draw.raffle_id.name or "",
            number=draw.sequence,
        )
        shipped = state in ("shipped", "delivered")
        return {
            "id": draw.id,
            "title": title,
            "state": state,
            "status": status,
            "prize": (
                product.with_context(display_default_code=False).display_name
                if product
                else (draw.prize or "")
            ),
            "sponsor": template.raffle_sponsor_name or "",
            "category": band.name or "",
            "link_url": link or False,
            "deadline": deadline,
            "tracking": (draw.prize_tracking_ref or "") if shipped else "",
            "carrier": (draw.prize_carrier_name or "") if shipped else "",
            "say": _(
                "Your prize, %(title)s: %(status)s",
                title=title,
                status=status,
            ),
        }

    def _ewp_public_partners(self, draws):
        """Contacts whose public name the card changes: the partner of the
        current user, and the contact each draw of ``draws`` (sudo) is
        named after on the winners page when it is another contact without
        a user account (a contact made for the prize order). A contact
        that belongs to another account is never changed."""
        partner = request.env.user.partner_id
        partners = partner
        for draw in draws:
            other = draw._prize_public_partner()
            if (
                other
                and other != partner
                and not other.sudo().with_context(active_test=False).user_ids
            ):
                partners |= other
        return partners

    def _ewp_prize_values(self, webapp, tz, notice=""):
        """Values of the "My prize" card, all prefixed with prize_.
        ``webapp`` is the sudo day, already allowed."""
        partner = request.env.user.partner_id
        draws = webapp._ewp_prize_draws(partner)
        lines = [self._ewp_prize_line(draw, tz) for draw in draws]
        partners = self._ewp_public_partners(draws)
        current = next(
            (p.raffle_public_name for p in partners if p.raffle_public_name),
            "",
        )
        shown = (
            draws[:1]._prize_public_name()
            if draws
            else partner._raffle_public_display_name()
        )
        base = f"{WEBAPP_ROOT}/{webapp.id}"
        return {
            "prize_lines": lines,
            "prize_url": base + "/my_prize",
            "prize_signature": self._ewp_signature(
                {"lines": lines, "shown": shown, "current": current}
            ),
            "prize_public_name": current,
            "prize_public_shown": shown,
            "prize_public_name_url": base + "/public_name",
            "prize_public_name_max": PUBLIC_NAME_MAX_LENGTH,
            "prize_notice": notice,
        }

    def _ewp_presence_values(self, webapp, tz, notice=""):
        """Values of the "On site" block: {"declared", "time", "url",
        "notice"}, or False when the current user has no registration to
        the events of the day."""
        registrations = webapp._ewp_partner_registrations(
            request.env.user.partner_id
        )
        if not registrations:
            return False
        declared = registrations.filtered("attendance_declared")
        dates = [d for d in declared.mapped("attendance_declared_date") if d]
        return {
            "declared": bool(declared),
            "time": (
                request.env._(
                    "Declared at %(time)s.",
                    time=self._ewp_short_label(max(dates), tz),
                )
                if dates
                else ""
            ),
            "url": f"{WEBAPP_ROOT}/{webapp.id}/presence",
            "notice": notice,
        }

    def _ewp_page_values(self, page, webapp, tz, room=None):
        values = super()._ewp_page_values(page, webapp, tz, room=room)
        if page == "home":
            values.update(
                self._ewp_prize_values(
                    webapp, tz, notice=self._ewp_pop_notice("prize")
                )
            )
            values["presence"] = self._ewp_presence_values(
                webapp, tz, notice=self._ewp_pop_notice("presence")
            )
        return values

    def _ewp_raffle_values(self, webapp, tz):
        """The raffle block names each winner by the public name of their
        contact when it has one (rule of event_raffle_prize_handover: the
        public name, else the full name), and gives the prize of a drawn
        draw not marked absent as the winners page does
        (draw._prize_public_status()): the prize once chosen, else the
        token category and "prize to choose", "Prize declined" or "No
        prize chosen". Such a draw also gets "prize_status", the status
        key of that text."""
        raffles = super()._ewp_raffle_values(webapp, tz)
        ids = [d["id"] for r in raffles for d in r["draws"] if d["drawn"]]
        draws = request.env["event.raffle.draw"].sudo().browse(ids)
        named = {}
        prizes = {}
        for draw in draws:
            partner = draw._prize_public_partner()
            if partner and partner.raffle_public_name:
                named[draw.id] = draw._prize_public_name()
            if not draw.is_absent:
                prizes[draw.id] = draw._prize_public_status()
        for raffle in raffles:
            for draw in raffle["draws"]:
                if draw["id"] in named:
                    draw["winner_name"] = named[draw["id"]]
                if draw["id"] in prizes:
                    draw["prize_status"], draw["prize"] = prizes[draw["id"]]
        return raffles

    def _ewp_allowed_day(self, webapp_id):
        """The sudo day ``webapp_id`` once the user may see it: 404 for an
        unknown or archived day, 403 outside its window for a visitor."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        if not webapp._ewp_can_view():
            raise Forbidden()
        return webapp

    def _ewp_wants_json(self):
        accept = request.httprequest.headers.get("Accept", "")
        return "application/json" in accept

    def _ewp_prize_payload(self, webapp, tz):
        values = self._ewp_prize_values(webapp, tz)
        html = request.env["ir.qweb"]._render(PRIZE_TEMPLATE, values)
        return {
            "signature": values["prize_signature"],
            "count": len(values["prize_lines"]),
            "html": str(html),
        }

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/my_prize",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_my_prize(self, webapp_id, **kwargs):
        """JSON of the "My prize" card for the refresh of the page script:
        ``signature`` (changes with the lines and the public name),
        ``count`` (lines of the card) and ``html`` (the body of the card).
        The same checks as the raffle route of the web app."""
        webapp = self._ewp_allowed_day(webapp_id)
        return request.make_json_response(
            self._ewp_prize_payload(webapp, self._ewp_tz(webapp)),
            headers=[("Cache-Control", "no-store")],
        )

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/public_name",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def webapp_public_name(self, webapp_id, public_name=None, **kwargs):
        """Write ``public_name`` (cleaned, empty clears it) on the contacts
        of _ewp_public_partners(): the partner of the current user and the
        contacts made for the prize orders of their draws. Any other
        parameter (a partner or draw id) is ignored."""
        webapp = self._ewp_allowed_day(webapp_id)
        draws = webapp._ewp_prize_draws(request.env.user.partner_id)
        for partner in self._ewp_public_partners(draws):
            partner._raffle_set_public_name(public_name or "")
        if self._ewp_wants_json():
            payload = self._ewp_prize_payload(webapp, self._ewp_tz(webapp))
            payload["message"] = self._ewp_prize_notices()["public_name"]
            return request.make_json_response(
                payload, headers=[("Cache-Control", "no-store")]
            )
        request.session[NOTICE_KEY] = "public_name"
        return request.redirect(
            f"{WEBAPP_ROOT}/{webapp.id}#ewp_prize_card", code=303
        )

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/presence",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def webapp_presence(self, webapp_id, on_site=None, **kwargs):
        """Write the self-declared attendance (``on_site`` "1" or "0") on
        the registrations of the current user to the events of the day;
        another value changes nothing. It never changes the state of a
        registration, which the check-in scan sets."""
        webapp = self._ewp_allowed_day(webapp_id)
        registrations = webapp._ewp_partner_registrations(
            request.env.user.partner_id
        )
        key = False
        if registrations and on_site in ("0", "1"):
            registrations._ewp_declare_attendance(on_site == "1")
            key = "on_site" if on_site == "1" else "off_site"
        if self._ewp_wants_json():
            tz = self._ewp_tz(webapp)
            presence = self._ewp_presence_values(webapp, tz)
            html = (
                request.env["ir.qweb"]._render(
                    PRESENCE_TEMPLATE, {"presence": presence}
                )
                if presence
                else ""
            )
            return request.make_json_response(
                {
                    "declared": bool(presence and presence["declared"]),
                    "html": str(html),
                    "message": (self._ewp_prize_notices()[key] if key else ""),
                },
                headers=[("Cache-Control", "no-store")],
            )
        if key:
            request.session[NOTICE_KEY] = key
        return request.redirect(
            f"{WEBAPP_ROOT}/{webapp.id}#ewp_presence", code=303
        )
