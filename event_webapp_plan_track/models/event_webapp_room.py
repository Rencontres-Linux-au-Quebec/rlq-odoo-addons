# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Room of the plan tied to a track location.

The tracks of the events name their place through event.track.location; a
room that follows a location shows the tracks held there. A location serves
one room per day at most, so a track never lands in two rooms of the same
day; the same location may serve a room of another day.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EventWebappRoom(models.Model):
    _inherit = "event.webapp.room"

    track_location_id = fields.Many2one(
        "event.track.location",
        string="Track location",
        ondelete="set null",
        index=True,
        help="Location of the event tracks held in this room: the web app "
        "shows them in the agenda of the room. One room per location and "
        "per day.",
    )

    @api.constrains("track_location_id", "webapp_id")
    def _check_track_location_unique(self):
        for room in self.filtered("track_location_id"):
            other = self.search(
                [
                    ("id", "!=", room.id),
                    ("webapp_id", "=", room.webapp_id.id),
                    ("track_location_id", "=", room.track_location_id.id),
                ],
                limit=1,
            )
            if other:
                raise ValidationError(
                    _(
                        "The track location %(location)s already serves the "
                        "room %(room)s of this day: a location serves one "
                        "room per day.",
                        location=room.track_location_id.name,
                        room=other.name,
                    )
                )
