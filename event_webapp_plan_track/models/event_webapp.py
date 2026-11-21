# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Agenda of an event day: the tracks of its events.

`track_ids` holds the tracks the web app may show for the day: those of the
events of the day whose interval overlaps the opening window of the day,
published (`is_published`), in a stage that is not a cancelled one, with a
start date. It is never stored: it is computed again at each read, so it
follows the tracks as they change. The controller reads it through the sudo
day, so the domain below is the whole access rule of the agenda: nothing
outside it reaches a page.
"""

from odoo import api, fields, models


class EventWebapp(models.Model):
    _inherit = "event.webapp"

    track_ids = fields.Many2many(
        "event.track",
        string="Agenda",
        compute="_compute_track_ids",
        help="Published tracks of the events of the day, held during its "
        "opening window, cancelled ones left out.",
    )

    def _ewp_track_domain(self):
        """Search domain of the tracks of this day (see the module
        docstring). A track overlaps the window when it starts before the
        window ends and ends after it starts."""
        self.ensure_one()
        return [
            ("event_id", "in", self.event_ids._origin.ids),
            ("is_published", "=", True),
            ("stage_id.is_cancel", "=", False),
            ("date", "!=", False),
            ("date", "<", self.date_end),
            ("date_end", ">", self.date_start),
        ]

    def _ewp_sort_tracks(self, tracks):
        """``tracks`` by start date, then by the order of their location
        (sequence, then id; tracks without location last), then by id."""
        return tracks.sorted(
            lambda t: (
                t.date,
                not t.location_id,
                t.location_id.sequence or 0,
                t.location_id.id or 0,
                t.id,
            )
        )

    @api.depends("event_ids", "date_start", "date_end")
    def _compute_track_ids(self):
        Track = self.env["event.track"]
        for webapp in self:
            if not (
                webapp.event_ids and webapp.date_start and webapp.date_end
            ):
                webapp.track_ids = Track
                continue
            webapp.track_ids = webapp._ewp_sort_tracks(
                Track.search(webapp._ewp_track_domain())
            )
