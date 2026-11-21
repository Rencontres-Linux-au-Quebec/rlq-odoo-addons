# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Agenda of the /webapp_event pages, controller side.

The class extends the controller of event_webapp_plan: its
_ewp_page_values() hands the home page and the room page the plain values
of the agenda, read by the templates of views/webapp_templates.xml through
the slots of the web app. The tracks come from event.webapp.track_ids, read
through the sudo day once the parent allowed the user: only the fields
rendered below leave the server (no e-mail, no phone, no contact).

Times: each session shows in the time zone of its event (date_tz), else in
the time zone of the page. `<time datetime>` and the data the page script
reads carry ISO 8601 moments with their offset; the labels are the short
time format of the language of the user (babel, through format_time).

States: "past", "now" (started, not ended), "next" (the earliest start
still to come, every session that starts then) and "later". The server
renders them once; the page script recomputes them from the clock.

Filter by room: the home page renders every session and marks hidden
(attribute `hidden`) those outside the room named by the query parameter
agenda_room, so the filter form works without script; the script filters
in place.

JSON route /webapp_event/<day>/agenda: the same checks as the raffle route
(active day, opening window or moderator), a `room` of that day only. It
answers the sessions of the page script, the rendered agenda block and,
with `room`, the rendered list of that room.
"""

import json

import pytz
from odoo import fields, http
from odoo.addons.event_webapp_plan.controllers.main import (
    WEBAPP_ROOT,
    EventWebappController,
)
from odoo.http import request
from odoo.tools import html_sanitize, is_html_empty
from odoo.tools.misc import format_time
from werkzeug.exceptions import Forbidden, NotFound

FILTER_PARAM = "agenda_room"
# Templates of the blocks the JSON route renders again.
AGENDA_TEMPLATE = "event_webapp_plan_track.agenda_content"
ROOM_TEMPLATE = "event_webapp_plan_track.agenda_room_content"


class EventWebappTrackController(EventWebappController):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _ewp_track_tz(self, track, tz):
        """Time zone name of ``track``: its event's, else ``tz``."""
        name = track.event_id.date_tz
        return name if name and name in pytz.all_timezones_set else tz

    def _ewp_local_iso(self, value, tz):
        """UTC datetime ``value`` in ``tz``, ISO 8601 to the second with
        its offset: the `datetime` of a <time> element, read by
        Date.parse()."""
        local = pytz.utc.localize(value).astimezone(pytz.timezone(tz))
        return local.isoformat(timespec="seconds")

    def _ewp_short_time(self, value, tz):
        """Short time of ``value`` in ``tz``, in the language of the user,
        with no-break spaces ("9:00 AM" stays on one line)."""
        return format_time(request.env, value, tz, "short").replace(" ", " ")

    def _ewp_agenda_messages(self):
        """Translated patterns of the agenda; "%(name)s" placeholders,
        filled in here and by the page script."""
        _ = request.env._
        return {
            "room_now": _("Now: %(title)s"),
            "room_next": _("Next at %(time)s: %(title)s"),
            "room_none": _("No more session in this room today."),
            "session_started": _("Now in this room: %(title)s."),
            "filter_all": _("Agenda of all rooms, sessions shown: %(count)s."),
            "filter_room": _("Agenda of %(room)s, sessions shown: %(count)s."),
        }

    def _ewp_selected_room(self, room_ids):
        """Id of the room of the filter (query parameter agenda_room) when
        it is one of ``room_ids``, else False."""
        raw = request.httprequest.args.get(FILTER_PARAM, "")
        try:
            room_id = int(raw)
        except ValueError:
            return False
        return room_id if room_id in room_ids else False

    def _ewp_room_status(self, sessions, room_id, messages):
        """{"state": "now", "next" or "", "text"} of the room ``room_id``:
        its session in progress, else its next one, else nothing."""
        mine = [s for s in sessions if s["room_id"] == room_id]
        for session in mine:
            if session["state"] == "now":
                return {
                    "state": "now",
                    "text": messages["room_now"] % {"title": session["title"]},
                }
        for session in mine:
            if session["state"] in ("next", "later"):
                return {
                    "state": "next",
                    "text": (
                        messages["room_next"] % {
                            "time": session["start_label"],
                            "title": session["title"],
                        }
                    ),
                }
        return {"state": "", "text": ""}

    def _ewp_session_values(self, webapp, tz):
        """Plain values of the sessions of ``webapp`` (sudo), in agenda
        order. `room_id` is the room that follows the location of the
        track, False without one; `room_name` its name, else the name of
        the location."""
        rooms = {
            room.track_location_id.id: room
            for room in webapp.room_ids
            if room.track_location_id
        }
        tracks = webapp._ewp_sort_tracks(webapp.track_ids)
        now = fields.Datetime.now()
        upcoming = [t.date for t in tracks if t.date > now]
        next_start = min(upcoming) if upcoming else False
        sessions = []
        for track in tracks:
            track_tz = self._ewp_track_tz(track, tz)
            end = track.date_end or track.date
            room = rooms.get(track.location_id.id)
            if end <= now:
                state = "past"
            elif track.date <= now:
                state = "now"
            elif track.date == next_start:
                state = "next"
            else:
                state = "later"
            speaker = track.partner_name or ""
            description = (
                html_sanitize(track.description)
                if not is_html_empty(track.description)
                else False
            )
            sessions.append(
                {
                    "id": track.id,
                    "title": track.name,
                    "start": self._ewp_local_iso(track.date, track_tz),
                    "end": self._ewp_local_iso(end, track_tz),
                    "start_label": self._ewp_short_time(track.date, track_tz),
                    "end_label": self._ewp_short_time(end, track_tz),
                    "room_id": room.id if room else False,
                    "room_name": (
                        room.name if room else (track.location_id.name or "")
                    ),
                    "room_url": (
                        self._ewp_room_url(webapp, room) if room else False
                    ),
                    "speaker": speaker,
                    "function": (
                        (track.partner_function or "") if speaker else ""
                    ),
                    # Colourless tags are internal: the website shows none
                    # of them either.
                    "tags": [tag.name for tag in track.tag_ids if tag.color],
                    "description": description,
                    "state": state,
                }
            )
        return sessions

    def _ewp_client_sessions(self, sessions):
        """The fields of ``sessions`` the page script reads."""
        keys = (
            "id",
            "title",
            "start",
            "end",
            "start_label",
            "end_label",
            "room_id",
            "room_name",
        )
        return [{key: s[key] for key in keys} for s in sessions]

    def _ewp_agenda_values(self, webapp, tz, room=None):
        """Values of the agenda blocks, all prefixed with agenda_: the home
        card (groups by start, filter), the line under each room of the
        room list, and with ``room`` (sudo) the block of its room page."""
        messages = self._ewp_agenda_messages()
        sessions = self._ewp_session_values(webapp, tz)
        # The clock changes the states and the query the filter: neither
        # changes the program.
        signature = self._ewp_signature(
            [{k: v for k, v in s.items() if k != "state"} for s in sessions]
        )
        room_ids = [r.id for r in webapp.room_ids]
        busy = {s["room_id"] for s in sessions if s["room_id"]}
        filters = [
            {"id": r.id, "name": r.name}
            for r in webapp.room_ids
            if r.id in busy
        ]
        # The filter applies only where its form is offered: with a single
        # busy room, a choice kept in the address would hide the sessions
        # without room, and no "All rooms" button could show them again.
        if len(filters) < 2:
            filters = []
        selected = self._ewp_selected_room([f["id"] for f in filters])
        groups = []
        for session in sessions:
            session["hidden"] = bool(
                selected and session["room_id"] != selected
            )
            if not groups or groups[-1]["start"] != session["start"]:
                groups.append(
                    {
                        "start": session["start"],
                        "label": session["start_label"],
                        "sessions": [],
                    }
                )
            groups[-1]["sessions"].append(session)
        for group in groups:
            group["hidden"] = all(s["hidden"] for s in group["sessions"])
        first_tz = (
            self._ewp_track_tz(webapp.track_ids[:1], tz)
            if webapp.track_ids
            else tz
        )
        url = "%s/%s/agenda" % (WEBAPP_ROOT, webapp.id)
        values = {
            "agenda_sessions": sessions,
            "agenda_groups": groups,
            "agenda_tz": first_tz,
            "agenda_filters": filters,
            "agenda_selected": selected,
            "agenda_filter_param": FILTER_PARAM,
            "agenda_filter_action": request.httprequest.path,
            "agenda_rooms_status": {
                room_id: self._ewp_room_status(sessions, room_id, messages)
                for room_id in room_ids
                if room_id in busy
            },
            "agenda_url": url,
            "agenda_messages_json": json.dumps(messages),
            "agenda_sessions_json": json.dumps(
                self._ewp_client_sessions(sessions)
            ),
            "agenda_signature": signature,
            "agenda_room": False,
        }
        if room and room.track_location_id:
            status = self._ewp_room_status(sessions, room.id, messages)
            if not status["state"]:
                status["text"] = messages["room_none"]
            values["agenda_room"] = {
                "id": room.id,
                "sessions": [s for s in sessions if s["room_id"] == room.id],
                "status": status,
                "url": "%s?room=%s" % (url, room.id),
            }
        return values

    def _ewp_page_values(self, page, webapp, tz, room=None):
        values = super()._ewp_page_values(page, webapp, tz, room=room)
        if page in ("home", "room"):
            values.update(self._ewp_agenda_values(webapp, tz, room=room))
        return values

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route(
        WEBAPP_ROOT + "/<int:webapp_id>/agenda",
        type="http",
        auth="user",
        methods=["GET"],
    )
    def webapp_agenda(self, webapp_id, room=None, **kwargs):
        """JSON of the agenda for the refresh of the page script:
        ``sessions`` (the fields it reads), ``signature`` (changes with the
        program, not with the clock), ``html`` (the agenda block of the
        home page) and, with ``room`` (a room of this day), ``room_html``
        (the session list of that room). 404 for an unknown day or a room
        of another day, 403 outside the opening window for a visitor."""
        webapp = self._ewp_webapp_sudo(webapp_id)
        room_sudo = None
        if room:
            try:
                room_sudo = self._ewp_room_sudo(webapp, int(room))
            except ValueError as error:
                raise NotFound() from error
        if not webapp._ewp_can_view():
            raise Forbidden()
        values = self._ewp_agenda_values(
            webapp, self._ewp_tz(webapp), room=room_sudo
        )
        qweb = request.env["ir.qweb"]
        payload = {
            "signature": values["agenda_signature"],
            "sessions": self._ewp_client_sessions(values["agenda_sessions"]),
            "html": str(qweb._render(AGENDA_TEMPLATE, values)),
        }
        if values["agenda_room"]:
            payload["room_html"] = str(qweb._render(ROOM_TEMPLATE, values))
        return request.make_json_response(
            payload, headers=[("Cache-Control", "no-store")]
        )
