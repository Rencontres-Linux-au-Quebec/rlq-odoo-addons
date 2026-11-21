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
"""

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

MODERATOR_GROUP = "event_webapp_plan.group_event_webapp_moderator"


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

    def write(self, vals):
        result = super().write(vals)
        if "name" in vals:
            self.room_ids._ewp_sync_names()
        return result

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
