# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Event day served by the web app at /webapp_event.

One record describes one day: its opening window, the content of the page
(announcement, links, events, raffles) and the site plan with its rooms.
Portal and internal users have no access right on this model: the
controller reads it with sudo and exposes only the fields it renders, after
`_ewp_can_view()` allowed the current user.

The room chats are reserved to the access group of each room, which the room
page gives to its visitors (see event.webapp.room).

The raffles of a day are chosen by hand, and pre-filled: a raffle joins the
day when it starts to fit it (see `raffle_fits_day()`), because the day
gained its event, the window of the day moved, or the raffle itself changed
(see event.raffle in this module). Nothing is ever removed automatically,
and a raffle taken off by hand comes back only when its own fit is lost and
found again.
"""

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

MODERATOR_GROUP = "event_webapp_plan.group_event_webapp_moderator"
# Fields of a day that decide which raffles fit it.
RAFFLE_FIT_FIELDS = frozenset(("event_ids", "date_start", "date_end"))
# Context key that turns the pre-fill of the raffles off, for a copy.
NO_RAFFLE_FILL = "ewp_no_raffle_fill"
# Fit state of a day that does not exist yet: no event, no window.
NO_FIT_STATE = (frozenset(), False, False)


def raffle_fits_day(raffle, event_ids, date_start, date_end):
    """Return whether `raffle` belongs on a day listing the events of ids
    `event_ids` (a set) and open from `date_start` to `date_end` (naive
    UTC datetimes, or False).

    A test raffle never fits, nor a raffle whose event the day does not
    list, nor any raffle on a day without window. A raffle with a planned
    date fits when the window holds that moment, bounds included. Without
    one, it fits when its event begins and ends inside the window: a
    raffle of an event spread over several days waits for its date.
    `raffle` is read as given: a sudo record reads the raffles and events
    that the caller may not.
    """
    if (
        raffle.is_test
        or raffle.event_id.id not in event_ids
        or not (date_start and date_end)
    ):
        return False
    if raffle.date_planned:
        return date_start <= raffle.date_planned <= date_end
    event = raffle.event_id
    return bool(
        event.date_begin
        and event.date_end
        and date_start <= event.date_begin
        and event.date_end <= date_end
    )


def _command_ids(commands):
    """Return the set of record ids that x2many `commands` link or set.

    Accepts the LINK and SET commands that the web client sends for a
    many2many field, and bare ids; ignores the others.
    """
    ids = set()
    for command in commands or ():
        if isinstance(command, int):
            ids.add(command)
        elif command[0] == Command.LINK:
            ids.add(command[1])
        elif command[0] == Command.SET:
            ids = set(command[2])
    return ids


class EventWebapp(models.Model):
    _name = "event.webapp"
    _description = "Event Web App Day"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    date_start = fields.Datetime(
        string="Opens on",
        required=True,
        tracking=True,
        help="Before this moment, only moderators and administrators see "
        "the web app.",
    )
    date_end = fields.Datetime(
        string="Closes on",
        required=True,
        tracking=True,
        help="From this moment, only moderators and administrators see the "
        "web app.",
    )
    announcement = fields.Html(
        translate=True,
        sanitize=True,
        help="General announcement shown at the top of the web app.",
    )
    link_ids = fields.One2many(
        "event.webapp.link", "webapp_id", string="Links", copy=True
    )
    event_ids = fields.Many2many(
        "event.event",
        "event_webapp_event_rel",
        "webapp_id",
        "event_id",
        string="Events",
    )
    raffle_ids = fields.Many2many(
        "event.raffle",
        "event_webapp_raffle_rel",
        "webapp_id",
        "raffle_id",
        string="Raffles",
        help="Raffles shown on the web app. A raffle of a listed event is "
        "added when its planned date falls inside the opening window or, "
        "without planned date, when its event lies entirely inside it; test "
        "raffles never are. Nothing is removed automatically.",
    )
    # Memory of the form between two onchanges: the raffles the form
    # already added in the current edit, so that a raffle taken off by hand
    # is not proposed again, and so that saving does not add it back.
    # Never stored: create() and write() drop it from their values.
    ewp_raffle_proposed_ids = fields.Many2many(
        "event.raffle",
        string="Raffles proposed in the form",
        compute="_compute_ewp_raffle_proposed_ids",
    )
    plan_image = fields.Image(
        string="Site plan", max_width=2560, max_height=2560
    )
    room_ids = fields.One2many(
        "event.webapp.room", "webapp_id", string="Rooms", copy=True
    )
    is_open = fields.Boolean(
        string="Open now",
        compute="_compute_is_open",
        help="True between the opening and the closing moment.",
    )
    webapp_url = fields.Char(
        string="Web app URL", compute="_compute_webapp_url"
    )
    room_count = fields.Integer(compute="_compute_room_count")
    bbb_configured = fields.Boolean(
        string="BigBlueButton server set",
        compute="_compute_bbb_configured",
        help="The BigBlueButton server URL and its shared secret are set in "
        "the settings.",
    )

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for webapp in self:
            if (
                webapp.date_start
                and webapp.date_end
                and webapp.date_end <= webapp.date_start
            ):
                raise ValidationError(
                    _(
                        "The closing moment of %(name)s must be after its "
                        "opening moment.",
                        name=webapp.name,
                    )
                )

    # The value depends on the clock, so it is never stored and is computed
    # again at each read.
    @api.depends("date_start", "date_end")
    def _compute_is_open(self):
        now = fields.Datetime.now()
        for webapp in self:
            webapp.is_open = bool(
                webapp.date_start
                and webapp.date_end
                and webapp.date_start <= now < webapp.date_end
            )

    def _compute_webapp_url(self):
        for webapp in self:
            webapp_id = webapp._origin.id
            webapp.webapp_url = (
                "/webapp_event/%d" % webapp_id if webapp_id else False
            )

    @api.depends("room_ids")
    def _compute_room_count(self):
        for webapp in self:
            webapp.room_count = len(webapp.room_ids)

    # Read from the settings at each read, like is_open.
    def _compute_bbb_configured(self):
        api, _secret = self.env["event.webapp.room"]._ewp_bbb_server()
        for webapp in self:
            webapp.bbb_configured = bool(api)

    def _compute_ewp_raffle_proposed_ids(self):
        self.ewp_raffle_proposed_ids = False

    @api.model_create_multi
    def create(self, vals_list):
        skips = [
            _command_ids(vals.pop("ewp_raffle_proposed_ids", None))
            for vals in vals_list
        ]
        webapps = super().create(vals_list)
        if not self.env.context.get(NO_RAFFLE_FILL):
            webapps._ewp_add_fitting_raffles(
                {}, dict(zip(webapps.ids, skips, strict=True))
            )
        return webapps

    def write(self, vals):
        proposed = _command_ids(vals.pop("ewp_raffle_proposed_ids", None))
        fill = bool(RAFFLE_FIT_FIELDS & vals.keys()) and not (
            self.env.context.get(NO_RAFFLE_FILL)
        )
        if fill:
            old_states = self._ewp_raffle_state()
            old_raffles = {
                webapp.id: set(webapp.sudo().raffle_ids.ids) for webapp in self
            }
        result = super().write(vals)
        if "name" in vals:
            self.room_ids._ewp_sync_names()
        if fill:
            # A raffle that this very write takes off stays off.
            skips = {
                webapp.id: proposed
                | (old_raffles[webapp.id] - set(webapp.sudo().raffle_ids.ids))
                for webapp in self
            }
            self._ewp_add_fitting_raffles(old_states, skips)
        return result

    def copy(self, default=None):
        """Copy the days with the raffle list of the original as it is: the
        pre-fill would add back the raffles taken off by hand."""
        webapps = super(
            EventWebapp, self.with_context(**{NO_RAFFLE_FILL: True})
        ).copy(default)
        return webapps.with_env(self.env)

    # ------------------------------------------------------------------
    # Raffles of the day
    # ------------------------------------------------------------------

    def _ewp_raffle_state(self):
        """Return {day id: (event ids, opening, closing)}, the values of
        each day that `raffle_fits_day()` reads."""
        return {
            webapp.id: (
                frozenset(webapp.sudo().event_ids._origin.ids),
                webapp.date_start,
                webapp.date_end,
            )
            for webapp in self
        }

    def _ewp_new_fitting_raffles(self, old_state):
        """Return the raffles that fit this day now and did not fit it in
        `old_state` (a value of `_ewp_raffle_state()`), as sudo records.

        Works on a new record too, as the onchange holds one. The search
        runs as superuser to find the candidates only: the callers keep
        those the user may read.
        """
        self.ensure_one()
        (state,) = self._ewp_raffle_state().values()
        event_ids, date_start, date_end = state
        raffles = self.env["event.raffle"].sudo()
        if not event_ids or not (date_start and date_end):
            return raffles
        candidates = raffles.search(
            [("event_id", "in", list(event_ids)), ("is_test", "=", False)]
        )
        return candidates.filtered(
            lambda raffle: raffle_fits_day(raffle, *state)
            and not raffle_fits_day(raffle, *old_state)
        )

    def _ewp_add_fitting_raffles(self, old_states, skips):
        """Add to each day the raffles that started to fit it since
        `old_states` ({day id: fit state}; a missing day is a new one),
        except the ids of `skips` ({day id: set of raffle ids}).

        Adds only: a raffle already listed, or taken off by hand, is left
        as it is. The write runs as the current user, with the raffles this
        user may read.
        """
        for webapp in self:
            raffles = webapp._ewp_new_fitting_raffles(
                old_states.get(webapp.id, NO_FIT_STATE)
            )
            raffles = raffles.with_env(webapp.env)._filtered_access("read")
            raffle_ids = (
                set(raffles.ids)
                - set(webapp.sudo().raffle_ids.ids)
                - skips.get(webapp.id, set())
            )
            if raffle_ids:
                webapp.write(
                    {
                        "raffle_ids": [
                            Command.link(raffle_id)
                            for raffle_id in sorted(raffle_ids)
                        ]
                    }
                )

    @api.onchange("event_ids", "date_start", "date_end")
    def _onchange_ewp_raffle_ids(self):
        """Show in the form the raffles that saving would add.

        The form keeps the raffles it added in `ewp_raffle_proposed_ids`:
        once taken off by hand, a raffle is not proposed again in the same
        edit, and saving sends that list so the server skips it too.
        """
        for webapp in self:
            origin = webapp._origin
            old_state = (
                origin._ewp_raffle_state()[origin.id]
                if origin
                else NO_FIT_STATE
            )
            raffles = webapp._ewp_new_fitting_raffles(old_state)
            raffles = raffles.with_env(webapp.env)._filtered_access("read")
            known = set(webapp.raffle_ids._origin.ids) | set(
                webapp.ewp_raffle_proposed_ids._origin.ids
            )
            raffles = raffles.filtered(lambda r, k=known: r.id not in k)
            if raffles:
                raffles = raffles.with_env(webapp.env)
                webapp.raffle_ids |= raffles
                webapp.ewp_raffle_proposed_ids |= raffles

    # ------------------------------------------------------------------
    # Helpers of the controller
    # ------------------------------------------------------------------

    @api.model
    def _ewp_is_moderator(self):
        """True when the current user belongs to the Moderator group.

        The Administrator group implies it. `env.user` is the real user
        even on a sudo environment, so the answer holds for sudo callers.
        """
        return self.env.user.has_group(MODERATOR_GROUP)

    @api.model
    def _ewp_find_default(self):
        """Event day shown by /webapp_event, as a SUDO recordset.

        Among the active days: the open one (earliest opening first), else
        the next one to open, else the one that closed most recently.
        Returns an empty recordset when no active day exists.
        """
        webapps = self.sudo().with_context(active_test=True)
        now = fields.Datetime.now()
        webapp = webapps.search(
            [("date_start", "<=", now), ("date_end", ">", now)],
            order="date_start asc, id asc",
            limit=1,
        )
        if not webapp:
            webapp = webapps.search(
                [("date_start", ">", now)],
                order="date_start asc, id asc",
                limit=1,
            )
        if not webapp:
            webapp = webapps.search(
                [("date_end", "<=", now)],
                order="date_end desc, id desc",
                limit=1,
            )
        return webapp

    def _ewp_can_view(self):
        """True when the current user may see the content of this day.

        Everybody may during the opening window; moderators and
        administrators may at any time. The window is read with sudo, so
        the method also answers for users without access right on the model.
        """
        self.ensure_one()
        return bool(self.sudo().is_open or self._ewp_is_moderator())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_open_webapp(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.webapp_url,
            "target": "new",
        }

    def action_create_missing_channels(self):
        """Create the access group and the Discuss channel of every room
        that has none, and restrict each channel to its room group.
        The work runs with sudo: the caller must be allowed to write the
        day, which RPC does not check on its own."""
        self.check_access("write")
        self.room_ids._ewp_ensure_access()
        return True

    def action_open_bbb_meetings(self):
        """Open the list of the meetings known by the BigBlueButton server,
        each line offering to give its meeting ID to a room of this day.
        Raises UserError when the server is not set or fails.

        The list is signed with the shared secret and names every meeting
        of the server, those of other applications included: it is
        reserved to the Settings group, checked before the server is
        called (see event.webapp.room._ewp_bbb_check_meeting_rights())."""
        self.ensure_one()
        self.check_access("write")
        self.env["event.webapp.room"]._ewp_bbb_check_meeting_rights()
        meetings = self.env["event.webapp.room"]._ewp_bbb_get_meetings()
        lines = []
        for meeting in meetings:
            room = self.room_ids.filtered(
                lambda r, m=meeting: r.bbb_meeting_id == m["meeting_id"]
            )[:1]
            lines.append(
                Command.create(
                    {
                        "meeting_name": meeting["name"],
                        "meeting_id": meeting["meeting_id"],
                        "participant_count": meeting["participant_count"],
                        "running": meeting["running"],
                        "room_id": room.id,
                    }
                )
            )
        wizard = self.env["event.webapp.bbb.meetings"].create(
            {"webapp_id": self.id, "line_ids": lines}
        )
        return wizard._ewp_action()
