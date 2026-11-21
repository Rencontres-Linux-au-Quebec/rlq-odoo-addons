# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Frontend of the event web app: the pages under /webapp_event.

Every page route uses auth="user": Odoo raises SessionExpiredException for an
anonymous visitor and answers with a redirect to /web/login?redirect=<path>,
so the visitor comes back to the same page once logged in. Portal and
internal users both pass.

Portal users have no access right on the event.webapp models. The
controller reads them with sudo and hands the templates plain values built
from a chosen list of fields only: the raffle winner e-mail, for instance, is
never read. Whether a day may be shown is decided by the model helper
_ewp_can_view() (open window, or moderator group); outside the window the
pages render a "closed" page and never the content.

The web manifest and the service worker are auth="public": the browser
fetches the manifest without credentials, and neither file holds anything
specific to a user or to a day.

BigBlueButton: the room page shows the conference chosen by
event.webapp.room._ewp_bbb_target() for the origin of the request, which
decides between the frame and the new tab button. The routes bbb_status
(JSON polled while the page may change: meeting not started, meeting
behind the button, server failing), bbb_join (redirect to a fresh join
URL, for the conference frame, "Open in a new tab" and the button) and
bbb_left (the page the client loads once the user leaves) apply the same
checks as the room page. The shared secret is read by the model only. The
pages and the JSON carry no join URL and no server address: the
conference frame and the button load bbb_join, and only its redirect
names the server.

Display preferences: the route /webapp_event/preferences (POST, CSRF token
required) writes the text-only mode and the animation mode (auto, on, off)
on the current user, through SELF_WRITEABLE_FIELDS, never on another
record. Every page reads them: the text-only mode renders no plan image, no
decorative image and no mascot or banner slot, and adds the body class
o_ewp_text_only. The body carries o_ewp_motion_<mode> for the animation
mode in force ("off" in text-only mode), plus o_ewp_motion_paused when the
user stopped the animations (mode off or text-only mode).

Short address: /w and /w/<id> (auth="public") redirect to /webapp_event
and /webapp_event/<id> with the same query string; the login check is the
one of the target.

Extension: _ewp_page_values() returns extra values for the home page and
the room page, merged last; a module that adds a block to those pages
overrides it and fills the template slots with the values it returns.
"""

import hashlib
import html
import json
import logging
import math
import re
from urllib.parse import urlsplit

import psycopg2
import pytz
from odoo import fields, http
from odoo.http import request
from odoo.tools import is_html_empty
from odoo.tools.misc import format_date, format_time
from werkzeug.exceptions import Forbidden, NotFound

from ..models import bbb_client
from ..models.event_webapp import MODERATOR_GROUP
from ..models.res_users import MOTION_MODES

_logger = logging.getLogger(__name__)

WEBAPP_ROOT = "/webapp_event"
# Short address of the web app, easier to type and to say: redirects to
# WEBAPP_ROOT (see webapp_short()).
SHORT_ROOT = "/w"
ICON_URL = "/event_webapp_plan/static/src/webapp/img/icon-%s.png"
# Colour of the app bar, also used by the browser chrome and the splash
# screen of the installed app.
THEME_COLOR = "#15191E"
BACKGROUND_COLOR = "#15191E"
DEFAULT_ROOM_COLOR = "#2A9D8F"
# Text colours a room badge picks from, by contrast with the room colour.
INK_LIGHT = "#FFFFFF"
INK_DARK = "#15191E"
MANAGER_GROUP = "event_webapp_plan.group_event_webapp_manager"
HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# Schemes a link button may point to; anything else (javascript:, data:...)
# is dropped.
SAFE_URL_RE = re.compile(r"^(?:https?://|mailto:|tel:|/(?!/))", re.IGNORECASE)
# Name of each page for the theme hooks (ewp_page, data-ewp-page and the
# body class o_ewp_page_<name>).
PAGE_NAMES = {
    "event_webapp_plan.webapp_page_main": "home",
    "event_webapp_plan.webapp_page_room": "room",
    "event_webapp_plan.webapp_page_closed": "closed",
    "event_webapp_plan.webapp_page_none": "none",
    "event_webapp_plan.webapp_page_bbb_left": "bbb_left",
}
PREFERENCES_URL = WEBAPP_ROOT + "/preferences"
# Third of the plan (row, column) -> key of the position words of a room.
PLAN_THIRDS = ("top", "middle", "bottom")
PLAN_COLUMNS = ("left", "centre", "right")


class EventWebappController(http.Controller):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ewp_webapp_sudo(self, webapp_id):
        """Return the active day ``webapp_id`` as sudo, or raise NotFound."""
        webapp = request.env["event.webapp"].sudo().browse(webapp_id).exists()
        if not webapp or not webapp.active:
            raise NotFound()
        return webapp

    def _ewp_room_sudo(self, webapp, room_id):
        """Return the room ``room_id`` of ``webapp`` as sudo, or raise
        NotFound."""
        room = request.env["event.webapp.room"].sudo().browse(room_id).exists()
        if not room or room.webapp_id != webapp:
            raise NotFound()
        return room

    def _ewp_room_url(self, webapp, room):
        return "%s/%s/room/%s" % (WEBAPP_ROOT, webapp.id, room.id)

    def _ewp_page_origin(self):
        """Origin of the current request ("<scheme>://<host>[:port]/"), the
        page URL against which the model decides whether the conference
        server is on the same site. Behind a proxy, Odoo in proxy mode
        reads it from the forwarded headers."""
        return request.httprequest.host_url

    @staticmethod
    def _ewp_bbb_page_state(target):
        """data-ewp-bbb-state of the conference block for the target of
        _ewp_bbb_target(): "running" for the frame of a running meeting,
        else the state of the target ("" when there is none). The status
        route answers the same value, which the page script compares with
        the rendered one."""
        if target["state"] == "frame" and target["live"]:
            return "running"
        return target["state"] or ""

    def _ewp_bbb_values(self, webapp, room, left=False):
        """Values of the conference block of the room page, or False when
        the room has no conference. See _ewp_bbb_target() for `state`;
        `page_state` is _ewp_bbb_page_state(), `poll` is true when the
        page asks the status route (see the room template).

        `left` (the room page reached by the redirect of bbb_left) only
        applies to the frame of a running meeting: the block then renders
        as after a leave in the frame, the frame without src and the
        notice "You left the conference." shown, `page_state` "left". A
        frame with its src would join the meeting the user just left."""
        target = room._ewp_bbb_target(page_url=self._ewp_page_origin())
        if not target["state"] and not target["error"]:
            return False
        room_url = self._ewp_room_url(webapp, room)
        left = bool(left and target["state"] == "frame" and target["live"])
        # The frame loads the bbb_join route of the room, which redirects:
        # the page carries neither a signed join URL nor the address of
        # the server. `left_url` is the path the page script recognises
        # in the frame once the user leaves the meeting.
        return {
            "state": target["state"],
            "page_state": (
                "left" if left else self._ewp_bbb_page_state(target)
            ),
            "left": left,
            "error": target["error"],
            "live": target["live"],
            "poll": target["state"] in ("waiting", "unavailable")
            or (
                target["state"] == "button"
                and (target["live"] or target["error"])
            ),
            "join_url": room_url + "/bbb_join",
            "frame_url": room_url + "/bbb_join?frame=1",
            "status_url": room_url + "/bbb_status",
            "check_url": room_url + "/bbb_status?fresh=1",
            "left_url": room_url + "/bbb_left",
            "title": request.env._(
                "Video conference: %(room)s", room=room.name
            ),
        }

    def _ewp_tz(self, webapp):
        """Timezone name used to display dates: the user's, else the browser
        cookie set by the frontend, else the first event's, else UTC."""
        candidates = [
            request.env.user.tz,
            request.httprequest.cookies.get("tz"),
        ]
        candidates += webapp.event_ids.mapped("date_tz") if webapp else []
        for name in candidates:
            if name and name in pytz.all_timezones_set:
                return name
        return "UTC"

    def _ewp_local_date(self, value, tz):
        return pytz.utc.localize(value).astimezone(pytz.timezone(tz)).date()

    def _ewp_range_label(self, start, end, tz):
        """Human range "<full date>, <time> - <time>" in ``tz``; the end date
        is repeated only when the range spans several days."""
        if not start or not end:
            return ""
        env = request.env
        start_day = self._ewp_local_date(start, tz)
        end_day = self._ewp_local_date(end, tz)
        start_label = "%s, %s" % (
            format_date(env, start_day, date_format="full"),
            format_time(env, start, tz, "short"),
        )
        if start_day == end_day:
            return "%s - %s" % (
                start_label,
                format_time(env, end, tz, "short"),
            )
        return "%s - %s, %s" % (
            start_label,
            format_date(env, end_day, date_format="full"),
            format_time(env, end, tz, "short"),
        )

    def _ewp_safe_color(self, color):
        return (
            color
            if color and HEX_COLOR_RE.match(color)
            else DEFAULT_ROOM_COLOR
        )

    def _ewp_pct(self, value):
        """Clamp a percentage to 0..100 and format it with a dot decimal."""
        return "%.3f" % min(max(value or 0.0, 0.0), 100.0)

    def _ewp_rotate_style(self, angle):
        """ ";--ewp-room-rotate:<angle>deg" for an area turned by `angle`
        degrees, two decimals with a dot; "" for an area that does not
        turn or an angle that is not a finite number. The stylesheet turns
        the area by that variable around its centre."""
        angle = angle or 0.0
        if not math.isfinite(angle) or round(angle, 2) == 0:
            return ""
        return ";--ewp-room-rotate:%.2fdeg" % angle

    def _ewp_text_color(self, color):
        """Return INK_LIGHT or INK_DARK, whichever contrasts most with the
        #RRGGBB or #RGB ``color`` (WCAG relative luminance), so a room badge
        stays readable whatever colour the room is given."""
        value = color.lstrip("#")
        if len(value) == 3:
            value = "".join(c * 2 for c in value)
        channels = []
        for i in (0, 2, 4):
            c = int(value[i : i + 2], 16) / 255.0
            channels.append(
                c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            )
        lum = 0.2126 * channels[0] + 0.7152 * channels[1]
        lum += 0.0722 * channels[2]
        # Luminance of INK_DARK, #15191E.
        dark = 0.0095
        light_ratio = 1.05 / (lum + 0.05)
        dark_ratio = (lum + 0.05) / (dark + 0.05)
        return INK_LIGHT if light_ratio >= dark_ratio else INK_DARK

    def _ewp_plan_position(self, room):
        """Words that say where the centre of ``room`` lies on the plan, in
        a 3 x 3 grid ("in the top left corner", "in the centre"...), for
        the screen reader text of the room list. False for a room without
        an area. An area turns around its centre: its rotation leaves the
        words unchanged."""
        _ = request.env._
        words = {
            ("top", "left"): _("in the top left corner"),
            ("top", "centre"): _("at the top"),
            ("top", "right"): _("in the top right corner"),
            ("middle", "left"): _("on the left"),
            ("middle", "centre"): _("in the centre"),
            ("middle", "right"): _("on the right"),
            ("bottom", "left"): _("in the bottom left corner"),
            ("bottom", "centre"): _("at the bottom"),
            ("bottom", "right"): _("in the bottom right corner"),
        }

        def third(start, size):
            centre = min(max((start or 0.0) + (size or 0.0) / 2, 0.0), 100.0)
            return min(int(centre * 3 // 100), 2)

        if not ((room.pos_width or 0.0) > 0 and (room.pos_height or 0.0) > 0):
            return False
        row = PLAN_THIRDS[third(room.pos_y, room.pos_height)]
        column = PLAN_COLUMNS[third(room.pos_x, room.pos_width)]
        return words[(row, column)]

    def _ewp_room_values(self, webapp):
        """Plain values of the rooms of ``webapp``, in their order. `number`
        is the position in that order, shown on the plan and in the list;
        `video` is true when the room has a conference (a meeting ID with
        the server set, or a conference URL), `meeting` when it has a
        meeting ID with the server set. It reads the configuration only,
        so the home page never calls the server, and says nothing about a
        running session: the page script asks the live route for that.
        `position` is the screen reader text that ties the list entry to
        its area on the plan, False without one.
        """
        rooms = []
        bbb_server = webapp.bbb_configured
        for number, room in enumerate(webapp.room_ids, start=1):
            color = self._ewp_safe_color(room.color)
            on_plan = (room.pos_width or 0.0) > 0 and (
                room.pos_height or 0.0
            ) > 0
            position = self._ewp_plan_position(room) if on_plan else False
            rooms.append(
                {
                    "id": room.id,
                    "number": number,
                    "position": (
                        request.env._(
                            "Area %(number)s on the plan, %(where)s.",
                            number=number,
                            where=position,
                        )
                        if position
                        else False
                    ),
                    "name": room.name,
                    "description": room.description or "",
                    "color": color,
                    "text_color": self._ewp_text_color(color),
                    "video": bool(
                        room.bbb_room_url
                        or (bbb_server and room.bbb_meeting_id)
                    ),
                    "meeting": bool(bbb_server and room.bbb_meeting_id),
                    "url": self._ewp_room_url(webapp, room),
                    "on_plan": on_plan,
                    "style": (
                        "left:%s%%;top:%s%%;width:%s%%;height:%s%%;"
                        "--ewp-room-color:%s%s"
                        % (
                            self._ewp_pct(room.pos_x),
                            self._ewp_pct(room.pos_y),
                            self._ewp_pct(room.pos_width),
                            self._ewp_pct(room.pos_height),
                            color,
                            self._ewp_rotate_style(room.pos_rotation),
                        )
                    ),
                }
            )
        return rooms

    def _ewp_event_values(self, webapp, tz):
        """Plain values of the events of ``webapp``, by start date. `time`
        is "<time> - <time>" for an event that starts and ends the same
        local day, else the full range of `dates`."""
        events = []
        for event in webapp.event_ids.sorted(lambda e: (e.date_begin, e.id)):
            dates = self._ewp_range_label(event.date_begin, event.date_end, tz)
            time = dates
            if (
                event.date_begin
                and event.date_end
                and self._ewp_local_date(event.date_begin, tz)
                == self._ewp_local_date(event.date_end, tz)
            ):
                # No-break spaces inside each time: a narrow column wraps
                # the range at the dash only.
                time = "%s - %s" % tuple(
                    format_time(request.env, value, tz, "short").replace(
                        " ", "\u00a0"
                    )
                    for value in (event.date_begin, event.date_end)
                )
            events.append(
                {
                    "name": event.name,
                    "dates": dates,
                    "time": time,
                    "address": event.address_inline or "",
                }
            )
        return events

    def _ewp_link_values(self, webapp):
        return [
            {
                "name": link.name,
                "url": link.url,
                "description": link.description or "",
            }
            for link in webapp.link_ids
            if link.url and SAFE_URL_RE.match(link.url.strip())
        ]

    def _ewp_raffle_values(self, webapp, tz):
        """Plain values of the day's raffles. Only display fields are read:
        the winner e-mail and the participant records never leave the server.
        """
        raffles = []
        for raffle in webapp.raffle_ids.sorted(lambda r: (r.name or "", r.id)):
            states = dict(
                raffle._fields["state"]._description_selection(request.env)
            )
            draws = []
            for draw in raffle.draw_ids.sorted(lambda d: (d.sequence, d.id)):
                winner = (
                    draw.winner_name or draw.winner_participant_id.name or ""
                )
                draws.append(
                    {
                        "id": draw.id,
                        "sequence": draw.sequence,
                        "prize": draw.prize or "",
                        "prize_description": draw.prize_description or "",
                        "winner_name": winner,
                        "drawn": bool(winner),
                        "is_absent": bool(winner and draw.is_absent),
                        "time": (
                            format_time(request.env, draw.date, tz, "short")
                            if winner and draw.date
                            else ""
                        ),
                    }
                )
            raffles.append(
                {
                    "id": raffle.id,
                    "name": raffle.name or "",
                    "state": raffle.state or "draft",
                    "state_label": states.get(raffle.state, ""),
                    "draws": draws,
                    "progress": (
                        request.env._(
                            "%(drawn)s drawn of %(total)s",
                            drawn=sum(1 for d in draws if d["drawn"]),
                            total=len(draws),
                        )
                        if draws
                        else ""
                    ),
                }
            )
        return raffles

    def _ewp_signature(self, payload):
        """Stable digest of JSON-serialisable values; the page script swaps
        the raffle block only when it changes."""
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha1(raw).hexdigest()

    def _ewp_initials(self, name):
        """Up to two initials of ``name``, for the avatar of the app bar."""
        words = [w for w in (name or "").split() if w[:1].isalnum()]
        return "".join(w[0] for w in words[:2]).upper()

    def _ewp_user_role(self):
        """Label of the app role of the current user, or an empty string
        for a visitor."""
        user = request.env.user
        if user.has_group(MANAGER_GROUP):
            return request.env._("Administrator")
        if user.has_group(MODERATOR_GROUP):
            return request.env._("Moderator")
        return ""

    def _ewp_day_state(self, webapp):
        """ "open" inside the opening window, else "before" or "after"."""
        if webapp.is_open:
            return "open"
        if webapp.date_start and webapp.date_start > fields.Datetime.now():
            return "before"
        return "after"

    def _ewp_preferences(self):
        """Display preferences of the current user: {"text_only": bool,
        "motion": "auto", "on" or "off"}. The user reads their own
        record."""
        user = request.env.user
        return {
            "text_only": bool(user.ewp_text_only),
            "motion": user._ewp_motion_mode(),
        }

    def _ewp_messages(self):
        """Translated texts the page script announces in the shared live
        region; "%(name)s" placeholders are filled in by the script."""
        _ = request.env._
        return {
            "raffle_winner": _(
                "New winner, %(raffle)s, %(prize)s: %(winner)s."
            ),
            "raffle_winner_no_prize": _("New winner, %(raffle)s: %(winner)s."),
            "raffle_winners": _("%(count)s new winners in the raffles."),
            "raffle_updated": _(
                "The raffles were updated: %(drawn)s drawn of %(total)s."
            ),
            "raffle_stopped": _(
                "The raffle results are no longer updated. Reload the page "
                "to see the latest draws."
            ),
            "raffle_pending": _(
                "The raffle results changed. Use the button "
                '"Show the latest results" to see them.'
            ),
            "bbb_started": _("The conference has started."),
            "room_live": _("The conference of %(room)s is live."),
            "bbb_waiting": _("The conference has not started yet."),
            "bbb_ended": _("The conference has ended."),
            "bbb_unavailable": _(
                "The video conference server does not answer at the moment."
            ),
            "bbb_left": _("You left the conference."),
            "bbb_moved": _("The conference is open in another tab."),
            "text_only_on": _("Text-only mode is on."),
            "text_only_off": _("Text-only mode is off."),
            "motion_paused": _("Animations are paused."),
            "motion_running": _("Animations are playing."),
            "motion_auto_paused": _(
                "Animations follow the device, which asks for less motion: "
                "they are paused."
            ),
            "motion_auto_running": _(
                "Animations follow the device: they are playing."
            ),
        }

    def _ewp_refresh_texts(self):
        """Translated patterns of the rows of the automatic updates,
        filled in by the page script: %(seconds)s, %(minutes)s, and
        %(delay)s, itself one of the two "delay" patterns."""
        _ = request.env._
        return {
            "updated_seconds": _("Updated %(seconds)s s ago"),
            "updated_minutes": _("Updated %(minutes)s min ago"),
            "next": _("Next in %(delay)s"),
            "retrying": _("Failed, retrying in %(delay)s"),
            "busy": _("Updating now"),
            "paused": _("Paused while the page is hidden"),
            "stopped": _("Stopped, reload the page"),
            "delay_seconds": _("%(seconds)s s"),
            "delay_minutes": _("%(minutes)s min %(seconds)s s"),
        }

    def _ewp_return_path(self):
        """Path and query of the current page, where the preference forms
        send the user back."""
        return request.httprequest.full_path.rstrip("?")

    def _ewp_pwa_values(self):
        """Name, colours and icons of the installed app, shared by the web
        manifest and the pages (theme-color meta, favicon and brand icon).

        Returns {"name", "short_name", "theme_color", "background_color",
        "icon_url" (page icon), "icons" (manifest icon list)}. A theme
        module overrides it in a subclass of this controller."""
        _ = request.env._
        return {
            "name": _("Event day"),
            "short_name": _("Event"),
            "theme_color": THEME_COLOR,
            "background_color": BACKGROUND_COLOR,
            "icon_url": ICON_URL % 192,
            "icons": [
                {
                    "src": ICON_URL % size,
                    "sizes": "%sx%s" % (size, size),
                    "type": "image/png",
                    "purpose": "any maskable",
                }
                for size in (192, 512)
            ],
        }

    def _ewp_base_values(self, webapp=None, tz="UTC"):
        lang = request.env.lang or "en_US"
        prefs = self._ewp_preferences()
        pwa = self._ewp_pwa_values()
        values = {
            "webapp": webapp,
            "user_name": request.env.user.name,
            "user_initials": self._ewp_initials(request.env.user.name),
            "user_role": self._ewp_user_role(),
            "day_state": False,
            "day_start": False,
            "day_end": False,
            "logout_url": "/web/session/logout?redirect=%s" % WEBAPP_ROOT,
            "lang_attr": lang.replace("_", "-"),
            "theme_color": pwa["theme_color"],
            "icon_url": pwa["icon_url"],
            "manifest_url": "%s/manifest.webmanifest" % WEBAPP_ROOT,
            "sw_url": "%s/sw.js" % WEBAPP_ROOT,
            "sw_scope": WEBAPP_ROOT,
            "page_title": webapp.name if webapp else request.env._("Event"),
            "text_only": prefs["text_only"],
            # The choice of the user, pressed in the display options.
            "motion_choice": prefs["motion"],
            # The mode in force: the text-only mode has no animation.
            "motion": "off" if prefs["text_only"] else prefs["motion"],
            "motion_paused": prefs["text_only"] or prefs["motion"] == "off",
            "preferences_url": PREFERENCES_URL,
            "return_path": self._ewp_return_path(),
            "messages_json": json.dumps(self._ewp_messages()),
            "refresh_texts_json": json.dumps(self._ewp_refresh_texts()),
            "is_preview": False,
            "window_label": "",
            "home_url": WEBAPP_ROOT,
        }
        if webapp:
            values.update(
                window_label=self._ewp_range_label(
                    webapp.date_start, webapp.date_end, tz
                ),
                home_url="%s/%s" % (WEBAPP_ROOT, webapp.id),
                is_preview=not webapp.is_open,
                day_state=self._ewp_day_state(webapp),
                day_start=self._ewp_iso(webapp.date_start),
                day_end=self._ewp_iso(webapp.date_end),
            )
        return values

    def _ewp_iso(self, value):
        """UTC datetime ``value`` as an ISO 8601 string with its offset,
        readable by Date.parse(), or False."""
        if not value:
            return False
        return pytz.utc.localize(value).isoformat()

    def _ewp_moment(self, value, tz):
        """``value`` as {"date": full local date, "time": short time}."""
        if not value:
            return False
        return {
            "date": format_date(
                request.env,
                self._ewp_local_date(value, tz),
                date_format="full",
            ),
            "time": format_time(request.env, value, tz, "short"),
        }

    def _ewp_page_values(self, page, webapp, tz, room=None):
        """Extra values of the home page (``page`` "home") and of a room
        page ("room", with the sudo record ``room``), merged last into the
        values the templates and their slots receive. ``webapp`` is the
        sudo day, already allowed by _ewp_can_view(); ``tz`` the timezone
        name of the dates of the page. Returns a dict, empty here: a module
        that adds a block to these pages overrides it in a subclass of this
        controller and reads only the fields it renders."""
        return {}

    def _ewp_render(self, template, values, status=200):
        values.setdefault("ewp_page", PAGE_NAMES.get(template, ""))
        response = request.render(template, values, status=status)
        # Authenticated pages are never stored by the browser or a proxy.
        response.headers["Cache-Control"] = "no-store"
        return response

    def _ewp_render_closed(self, webapp, tz):
        values = self._ewp_base_values(webapp, tz)
        not_started = bool(
            webapp.date_start and webapp.date_start > fields.Datetime.now()
        )
        values.update(
            is_preview=False,
            not_started=not_started,
            page_title=(
                request.env._("Not open yet - %(day)s", day=webapp.name)
                if not_started
                else request.env._("Over - %(day)s", day=webapp.name)
            ),
            opening=self._ewp_moment(webapp.date_start, tz),
            closing=self._ewp_moment(webapp.date_end, tz),
        )
        return self._ewp_render("event_webapp_plan.webapp_page_closed", values)

    def _ewp_render_day(self, webapp):
        tz = self._ewp_tz(webapp)
        if not webapp._ewp_can_view():
            return self._ewp_render_closed(webapp, tz)
        raffles = self._ewp_raffle_values(webapp, tz)
        rooms = self._ewp_room_values(webapp)
        values = self._ewp_base_values(webapp, tz)
        values.update(
            page_title=request.env._("Home - %(day)s", day=webapp.name),
            announcement=(
                webapp.announcement
                if not is_html_empty(webapp.announcement)
                else False
            ),
            links=self._ewp_link_values(webapp),
            events=self._ewp_event_values(webapp, tz),
            rooms=rooms,
            # Polled by the page script for the rooms whose meeting runs;
            # False when no room has a meeting ID with the server set.
            rooms_live_url=(
                "%s/%s/live" % (WEBAPP_ROOT, webapp.id)
                if any(room["meeting"] for room in rooms)
                else False
            ),
            plan_url=(
                "%s/%s/plan?unique=%s"
                % (
                    WEBAPP_ROOT,
                    webapp.id,
                    (
                        int(webapp.write_date.timestamp())
                        if webapp.write_date
                        else 0
                    ),
                )
                if webapp.plan_image
                else False
            ),
            has_raffles=bool(webapp.raffle_ids),
            raffles=raffles,
            raffles_url="%s/%s/raffles" % (WEBAPP_ROOT, webapp.id),
            raffles_signature=self._ewp_signature(raffles),
            # Patterns of the age of the raffle block, filled in by the page
            # script: %(seconds)s and %(minutes)s are replaced there.
            raffles_updated_seconds=request.env._("Updated %(seconds)s s ago"),
            raffles_updated_minutes=request.env._(
                "Updated %(minutes)s min ago"
            ),
        )
        values.update(self._ewp_page_values("home", webapp, tz))
        return self._ewp_render("event_webapp_plan.webapp_page_main", values)

    def _ewp_join_channel(self, channel):
        """Make the current user's partner a member of ``channel`` so the
        embedded Discuss page opens with a composer. _add_members() skips
        partners already members; the savepoint absorbs the unique index
        (channel_id, partner_id) when two page loads race to create it."""
        partner = request.env.user.partner_id
        channel_sudo = channel.sudo()
        try:
            with request.env.cr.savepoint():
                channel_sudo._add_members(
                    partners=partner, post_joined_message=False
                )
        except psycopg2.IntegrityError:
            _logger.debug(
                "channel %s: membership created by a concurrent request",
                channel.id,
            )

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    @http.route(WEBAPP_ROOT, type="http", auth="user", methods=["GET"])
    def webapp_default(self, **kwargs):
        webapp = (
            request.env["event.webapp"].sudo()._ewp_find_default()[:1].sudo()
        )
        if not webapp:
            values = self._ewp_base_values()
            values["page_title"] = request.env._("No event day")
            return self._ewp_render(
                "event_webapp_plan.webapp_page_none", values
            )
        return self._ewp_render_day(webapp)

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_day(self, webapp_id, **kwargs):
        return self._ewp_render_day(self._ewp_webapp_sudo(webapp_id))

    @http.route(
        [SHORT_ROOT, SHORT_ROOT + "/<int:webapp_id>"],
        type="http",
        auth="public",
        methods=["GET"],
    )
    def webapp_short(self, webapp_id=None, **kwargs):
        """302 redirect of /w to WEBAPP_ROOT and of /w/<id> to the day
        <id>, the query string kept as is. The route reads nothing:
        the target route checks the login (an anonymous visitor goes to
        the login page, then back to the target) and the day."""
        target = WEBAPP_ROOT
        if webapp_id is not None:
            target += f"/{webapp_id}"
        query = request.httprequest.query_string.decode("latin-1")
        if query:
            target += "?" + query
        return request.redirect(target, code=302)

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/room/<int:room_id>",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_room(self, webapp_id, room_id, left=None, **kwargs):
        """Room page: conference block, chat. ``left=1`` comes from the
        redirect of bbb_left (see _ewp_bbb_values())."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        room = self._ewp_room_sudo(webapp, room_id)
        tz = self._ewp_tz(webapp)
        if not webapp._ewp_can_view():
            return self._ewp_render_closed(webapp, tz)
        channel = room.channel_id
        chat_url = False
        chat_restricted = False
        # Only a channel of type "channel" is joined and embedded, the rule
        # of the model constraint: the page adds every visitor with sudo,
        # and a private conversation must never receive them.
        if channel and channel.channel_type == "channel":
            # Each room channel is restricted to the access group of its
            # room, which the visitor receives here and keeps afterwards.
            room._ewp_grant_access()
            # A channel restricted to another group is unreadable for users
            # outside it (rule ir_rule_discuss_channel_all): not embedded.
            group = (
                channel.group_public_id
                or channel.parent_channel_id.group_public_id
            )
            if group and group not in request.env.user.sudo().groups_id:
                chat_restricted = True
            else:
                self._ewp_join_channel(channel)
                chat_url = "/discuss/channel/%s" % channel.id
        values = self._ewp_base_values(webapp, tz)
        values.update(
            room={
                "id": room.id,
                "name": room.name,
                "description": room.description or "",
                "color": self._ewp_safe_color(room.color),
            },
            chat_title=request.env._("Discussion: %(room)s", room=room.name),
            page_title="%s - %s" % (room.name, webapp.name),
            chat_url=chat_url,
            chat_restricted=chat_restricted,
            bbb=self._ewp_bbb_values(webapp, room, left=left == "1"),
        )
        values.update(self._ewp_page_values("room", webapp, tz, room=room))
        return self._ewp_render("event_webapp_plan.webapp_page_room", values)

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/room/<int:room_id>/bbb_status",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_room_bbb_status(self, webapp_id, room_id, fresh=None, **kwargs):
        """JSON ``{"running": bool, "error": bool, "state": str}`` of the
        room conference, polled by the room page while it may change, and
        asked by "Join again" with ``fresh=1``, which refuses a state
        cached more than bbb_client.FRESH_TTL seconds ago. ``running`` is
        true when the server says the meeting runs, ``error`` when the
        server could not answer, and ``state`` is the data-ewp-bbb-state
        the room page would render now (_ewp_bbb_page_state())."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        room = self._ewp_room_sudo(webapp, room_id)
        if not webapp._ewp_can_view():
            raise Forbidden()
        target = room._ewp_bbb_target(
            page_url=self._ewp_page_origin(),
            max_age=bbb_client.FRESH_TTL if fresh else None,
        )
        return request.make_json_response(
            {
                "running": target["live"],
                "error": target["error"],
                "state": self._ewp_bbb_page_state(target),
            },
            headers=[("Cache-Control", "no-store")],
        )

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/room/<int:room_id>/bbb_join",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_room_bbb_join(self, webapp_id, room_id, frame=None, **kwargs):
        """Redirect (302) to a fresh join URL of the room meeting, else to
        the conference URL. When there is nothing to join (meeting not
        started, no conference), a tab goes back to the room page, and the
        conference frame of the room page (``frame=1``) gets an empty 204
        answer instead of a copy of the page. Outside the opening window,
        non-moderators get the closed page.

        The join URL names the bbb_left route of the room as logoutURL,
        absolute on ``web.base.url``: the client of the user loads it once
        they leave, instead of the logout page of the meeting. The frame
        gets ``bbb_left?frame=1``, the page its script recognises; a join
        outside the frame gets ``bbb_left``, which leads back to the room
        page without joining again."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        room = self._ewp_room_sudo(webapp, room_id)
        if not webapp._ewp_can_view():
            return self._ewp_render_closed(webapp, self._ewp_tz(webapp))
        logout_url = "%s%s/bbb_left%s" % (
            (webapp.get_base_url() or "").rstrip("/"),
            self._ewp_room_url(webapp, room),
            "?frame=1" if frame else "",
        )
        target = room._ewp_bbb_target(
            logout_url=logout_url, page_url=self._ewp_page_origin()
        )
        if target["state"] in ("frame", "button") and target["url"]:
            response = request.redirect(target["url"], code=302, local=False)
        elif frame:
            response = request.make_response("", status=204)
        else:
            response = request.redirect(self._ewp_room_url(webapp, room))
        response.headers["Cache-Control"] = "no-store"
        return response

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/room/<int:room_id>/bbb_left",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_room_bbb_left(self, webapp_id, room_id, frame=None, **kwargs):
        """logoutURL of the join URLs of the room. With ``frame=1`` (the
        join URL of the conference frame), the page "You left the
        conference.": the script of the room page recognises its path in
        the frame and replaces it with its own notice and a "Join again"
        button. Without it (a join opened in a tab of its own), a 303
        redirect to the room page with ``left=1``, which that tab then
        shows: a room page that embeds the meeting renders its frame
        without src and the notice of the leave, so the redirect never
        joins the user again. The client of BigBlueButton adds ``reason``
        to the query, which is ignored. Same checks as the room page,
        before either answer; the page names neither the server nor a
        join URL."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        room = self._ewp_room_sudo(webapp, room_id)
        tz = self._ewp_tz(webapp)
        if not webapp._ewp_can_view():
            return self._ewp_render_closed(webapp, tz)
        if not frame:
            response = request.redirect(
                self._ewp_room_url(webapp, room) + "?left=1", code=303
            )
            response.headers["Cache-Control"] = "no-store"
            return response
        values = self._ewp_base_values(webapp, tz)
        values.update(
            room={"name": room.name},
            room_url=self._ewp_room_url(webapp, room),
            page_title=request.env._(
                "Conference left - %(room)s - %(day)s",
                room=room.name,
                day=webapp.name,
            ),
        )
        return self._ewp_render(
            "event_webapp_plan.webapp_page_bbb_left", values
        )

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/plan",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_plan(self, webapp_id, **kwargs):
        """Serve the plan image. /web/image cannot be used: portal users have
        no read access on the model."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        if not webapp._ewp_can_view():
            raise Forbidden()
        if not webapp.plan_image:
            raise NotFound()
        stream = request.env["ir.binary"]._get_image_stream_from(
            webapp, "plan_image"
        )
        response = stream.get_response()
        # The URL carries ?unique=<write date>, so a new image gets a new URL.
        response.headers["Cache-Control"] = "private, max-age=3600"
        return response

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/live",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_rooms_live(self, webapp_id, **kwargs):
        """JSON ``{"live": [room ids]}``: the rooms of the day whose meeting
        runs, polled by the home page. Each room is asked through the cache
        of bbb_client, as on the room page; a room the server cannot answer
        for, or without a meeting ID, is not listed. The answer names
        neither the server nor a meeting ID."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        if not webapp._ewp_can_view():
            raise Forbidden()
        live = []
        if webapp.bbb_configured:
            live = [
                room.id
                for room in webapp.room_ids
                if room.bbb_meeting_id and room._ewp_bbb_running()
            ]
        return request.make_json_response(
            {"live": live},
            headers=[("Cache-Control", "no-store")],
        )

    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/raffles",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_raffles(self, webapp_id, **kwargs):
        """JSON of the day's raffles for the live refresh of the page:
        ``raffles`` (plain values), ``signature`` and ``html`` (the rendered
        raffle block, so the script needs no translation of its own)."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        if not webapp._ewp_can_view():
            raise Forbidden()
        raffles = self._ewp_raffle_values(webapp, self._ewp_tz(webapp))
        html = request.env["ir.qweb"]._render(
            "event_webapp_plan.webapp_raffles_content",
            {"raffles": raffles},
        )
        return request.make_json_response(
            {
                "raffles": raffles,
                "signature": self._ewp_signature(raffles),
                "html": str(html),
            },
            headers=[("Cache-Control", "no-store")],
        )

    # ------------------------------------------------------------------
    # Display preferences
    # ------------------------------------------------------------------
    @http.route(
        PREFERENCES_URL,
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def webapp_preferences(
        self, text_only=None, motion=None, redirect=None, **kwargs
    ):
        """Write the display preferences of the current user. ``text_only``
        is "1" or "0", ``motion`` one of MOTION_MODES ("auto", "on",
        "off"); a missing or unknown value is left as is,
        and any other parameter (a user id, for instance) is ignored: the
        route writes on the current user only, through
        SELF_WRITEABLE_FIELDS. A request that accepts JSON gets the
        preferences as JSON; a form gets a 303 redirect to ``redirect``,
        a path under /webapp_event, else to /webapp_event."""
        values = {}
        if text_only in ("0", "1"):
            values["ewp_text_only"] = text_only == "1"
        if motion in MOTION_MODES:
            values["ewp_motion"] = motion
        if values:
            request.env.user.write(values)
        accept = request.httprequest.headers.get("Accept", "")
        if "application/json" in accept:
            return request.make_json_response(
                self._ewp_preferences(),
                headers=[("Cache-Control", "no-store")],
            )
        return request.redirect(self._ewp_safe_return(redirect), code=303)

    def _ewp_safe_return(self, path):
        """``path`` when it is a local path under /webapp_event, else
        /webapp_event: the preference form never redirects elsewhere."""
        parts = urlsplit(path or "")
        if (
            parts.scheme
            or parts.netloc
            or "\\" in (path or "")
            or not (
                parts.path == WEBAPP_ROOT
                or parts.path.startswith(WEBAPP_ROOT + "/")
            )
        ):
            return WEBAPP_ROOT
        return path

    # ------------------------------------------------------------------
    # Progressive web app
    # ------------------------------------------------------------------
    @http.route(
        WEBAPP_ROOT + "/manifest.webmanifest",
        type="http",
        auth="public",
        methods=["GET"],
    )
    def webapp_manifest(self, **kwargs):
        lang = request.env.lang or "en_US"
        pwa = self._ewp_pwa_values()
        manifest = {
            "name": pwa["name"],
            "short_name": pwa["short_name"],
            "lang": lang.replace("_", "-"),
            "start_url": WEBAPP_ROOT,
            "scope": WEBAPP_ROOT,
            "display": "standalone",
            "background_color": pwa["background_color"],
            "theme_color": pwa["theme_color"],
            "icons": pwa["icons"],
        }
        return request.make_response(
            json.dumps(manifest),
            headers=[
                ("Content-Type", "application/manifest+json; charset=utf-8"),
                ("Cache-Control", "public, max-age=86400"),
            ],
        )

    @http.route(
        WEBAPP_ROOT + "/sw.js", type="http", auth="public", methods=["GET"]
    )
    def webapp_service_worker(self, **kwargs):
        """Minimal service worker: navigations go to the network and nothing
        is cached; when the network fails, an inline offline page answers.
        Service-Worker-Allowed lets it control the scope "/webapp_event"
        (without trailing slash), which also covers the start URL."""
        offline = (
            "<!DOCTYPE html><html lang='%s'><head><meta charset='utf-8'>"
            "<meta name='viewport' "
            "content='width=device-width, initial-scale=1'>"
            "<title>%s</title></head>"
            "<body style='font-family:system-ui,sans-serif;padding:2rem;"
            "text-align:center'><h1>%s</h1><p>%s</p></body></html>"
            % tuple(
                html.escape(text)
                for text in (
                    (request.env.lang or "en_US").replace("_", "-"),
                    request.env._("Offline"),
                    request.env._("You are offline"),
                    request.env._(
                        "The event web app needs a network connection. "
                        "Try again once you are back online."
                    ),
                )
            )
        )
        script = """'use strict';
const OFFLINE_HTML = %s;
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (event) => {
    if (event.request.mode !== 'navigate') {
        return;
    }
    event.respondWith(
        fetch(event.request).catch(() => new Response(OFFLINE_HTML, {
            status: 503,
            headers: {'Content-Type': 'text/html; charset=utf-8'},
        }))
    );
});
""" % json.dumps(offline)
        return request.make_response(
            script,
            headers=[
                ("Content-Type", "text/javascript; charset=utf-8"),
                ("Cache-Control", "no-cache"),
                ("Service-Worker-Allowed", WEBAPP_ROOT),
            ],
        )
