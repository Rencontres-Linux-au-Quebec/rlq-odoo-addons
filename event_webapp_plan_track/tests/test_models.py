# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Model tests of the agenda: the tracks of a day (window overlap,
publication, cancelled stage, events of the day) and the track location of
the rooms, one room per location and per day.

Every name below is invented for the tests."""

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

# A fixed day: the agenda does not depend on the clock.
WINDOW_START = datetime(2031, 3, 8, 13, 0)
WINDOW_END = datetime(2031, 3, 8, 23, 0)


@tagged("post_install", "-at_install")
class TestAgendaModels(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Location = cls.env["event.track.location"]
        cls.loc_first = Location.create({"name": "Kappa Stage", "sequence": 1})
        cls.loc_second = Location.create(
            {"name": "Lambda Corner", "sequence": 2}
        )
        cls.loc_third = Location.create({"name": "Mu Desk", "sequence": 3})
        cls.stage_cancel = cls.env["event.track.stage"].create(
            {"name": "Test Cancelled", "is_cancel": True}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Agenda Model Fair",
                "date_begin": WINDOW_START,
                "date_end": WINDOW_END,
                "date_tz": "America/Montreal",
            }
        )
        cls.other_event = cls.env["event.event"].create(
            {
                "name": "Agenda Model Elsewhere",
                "date_begin": WINDOW_START,
                "date_end": WINDOW_END,
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Agenda Model Day",
                "date_start": WINDOW_START,
                "date_end": WINDOW_END,
                "event_ids": [Command.set(cls.event.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Kappa Room",
                            "track_location_id": cls.loc_first.id,
                        }
                    ),
                    Command.create({"name": "Nu Room"}),
                ],
            }
        )

    def _track(self, name, start, hours=1.0, **values):
        vals = {
            "name": name,
            "event_id": self.event.id,
            "date": start,
            "duration": hours,
            "is_published": True,
            "location_id": self.loc_first.id,
        }
        vals.update(values)
        return self.env["event.track"].create(vals)

    def test_tracks_of_the_day(self):
        hour = timedelta(hours=1)
        inside = self._track("Inside Talk", WINDOW_START + 2 * hour)
        early = self._track("Early Talk", WINDOW_START - hour, hours=1.5)
        late = self._track("Late Talk", WINDOW_END - hour, hours=3)
        self._track("Before Talk", WINDOW_START - 2 * hour)
        self._track("After Talk", WINDOW_END)
        self._track("Draft Talk", WINDOW_START + hour, is_published=False)
        cancelled = self._track(
            "Cancelled Talk",
            WINDOW_START + hour,
            stage_id=self.stage_cancel.id,
        )
        # A cancelled stage unpublishes its tracks; published again by
        # hand, the track stays out all the same.
        cancelled.is_published = True
        self._track("Undated Talk", False)
        self._track(
            "Elsewhere Talk", WINDOW_START + hour, event_id=self.other_event.id
        )
        self._track("Archived Talk", WINDOW_START + hour, active=False)
        self.env.invalidate_all()
        self.assertEqual(
            self.day.track_ids.mapped("name"),
            [early.name, inside.name, late.name],
        )

    def test_tracks_sorted_by_start_then_location(self):
        start = WINDOW_START + timedelta(hours=1)
        third = self._track(
            "Third Place", start, location_id=self.loc_third.id
        )
        nowhere = self._track("No Place", start, location_id=False)
        first = self._track("First Place", start)
        second = self._track(
            "Second Place", start, location_id=self.loc_second.id
        )
        earlier = self._track(
            "Earlier", start - timedelta(minutes=30), location_id=False
        )
        self.env.invalidate_all()
        self.assertEqual(
            self.day.track_ids.ids,
            [earlier.id, first.id, second.id, third.id, nowhere.id],
        )

    def test_day_without_event_has_no_agenda(self):
        self._track("Lonely Talk", WINDOW_START + timedelta(hours=1))
        day = self.env["event.webapp"].create(
            {
                "name": "Agenda Model Empty Day",
                "date_start": WINDOW_START,
                "date_end": WINDOW_END,
            }
        )
        self.assertFalse(day.track_ids)

    def test_location_serves_one_room_per_day(self):
        with self.assertRaises(ValidationError):
            self.env["event.webapp.room"].create(
                {
                    "name": "Kappa Twin",
                    "webapp_id": self.day.id,
                    "track_location_id": self.loc_first.id,
                }
            )
        nu = self.day.room_ids.filtered(lambda r: r.name == "Nu Room")
        with self.assertRaises(ValidationError):
            nu.track_location_id = self.loc_first
        # Rooms without location, and the same location on another day.
        nu.track_location_id = self.loc_second
        self.env["event.webapp.room"].create(
            {"name": "Xi Room", "webapp_id": self.day.id}
        )
        other = self.day.copy({"name": "Agenda Model Copy"})
        self.assertEqual(
            other.room_ids.mapped("track_location_id"),
            self.loc_first | self.loc_second,
        )

    def test_deleted_location_frees_the_room(self):
        room = self.day.room_ids.filtered("track_location_id")
        self.loc_first.unlink()
        self.assertFalse(room.track_location_id)
