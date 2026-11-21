# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Example event day of the demo data (demo/event_webapp_demo.xml): five
rooms, each following one track location, the 21 tracks of 21 November
2026 in the time zone of the event, the 7 raffle draws on the times of the
draw tracks, and the agenda of the home page and of a room page with the
clock of the server set to 10:30 on that day.

The tests skip themselves in a database without demo data. The other
tests of the modules do not rely on the demo day being absent or present:
they set every day inactive before creating their own."""

from datetime import datetime

import pytz
from lxml import html as lxml_html
from odoo import fields
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

EVENT_TZ = pytz.timezone("America/Montreal")
DEMO_DAY = "rlq_event_webapp_plan.demo_webapp"
DEMO_DATE = "2026-11-21"
DRAW_TITLE = "Tirage de prix de présence"
# 10:30 in Montreal on the demo day: 15:30 UTC, standard time (UTC-5).
FROZEN_NOW = datetime(2026, 11, 21, 15, 30)
NOW_TRACK = "Reprendre le contrôle de ses données avec le logiciel libre"
NOW_ROOM = "Salle de présentation entreprises"
NEXT_TRACKS = {"Tirage de prix de présence #1", "ERPLibre et ses nouveautés"}


def local(value):
    """Naive UTC datetime ``value`` in the time zone of the event."""
    return pytz.utc.localize(value).astimezone(EVENT_TZ)


@tagged("post_install", "-at_install")
class TestDemoDay(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.day = cls.env.ref(DEMO_DAY, raise_if_not_found=False)
        new_test_user(
            cls.env,
            login="rlq_demo_moderator",
            password="rlq_demo_moderator",
            groups=(
                "base.group_user,"
                "event_webapp_plan.group_event_webapp_moderator"
            ),
            name="Demo Moderator Test",
            lang="en_US",
        )

    def setUp(self):
        super().setUp()
        if not self.day:
            self.skipTest("demo data not loaded")

    def _freeze_now(self):
        """Server clock (fields.Datetime.now) at FROZEN_NOW, for the
        requests of the test too: the HTTP server of the tests runs in
        this process."""
        self.patch(
            fields.Datetime, "now", staticmethod(lambda *args: FROZEN_NOW)
        )

    def _get(self, url):
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200, url)
        return lxml_html.fromstring(response.content)

    def test_rooms_follow_the_locations(self):
        rooms = self.day.room_ids
        self.assertEqual(len(rooms), 5)
        locations = rooms.mapped("track_location_id")
        self.assertEqual(len(locations), 5, "one location per room")
        self.assertTrue(all(room.track_location_id for room in rooms))
        self.assertTrue(self.day.plan_image)
        for room in rooms:
            self.assertEqual(room.name, room.track_location_id.name)
            self.assertTrue(
                0 < room.pos_x + room.pos_width <= 100
                and 0 < room.pos_y + room.pos_height <= 100,
                room.name,
            )

    def test_tracks_of_the_day(self):
        tracks = self.day.track_ids
        self.assertEqual(len(tracks), 21)
        self.assertEqual(
            {local(t.date).date().isoformat() for t in tracks}, {DEMO_DATE}
        )
        self.assertEqual(
            local(tracks[0].date).strftime("%H:%M"),
            "07:30",
        )
        self.assertEqual(
            local(max(tracks.mapped("date_end"))).strftime("%H:%M"),
            "21:00",
        )
        self.assertEqual(
            set(tracks.mapped("location_id").ids),
            set(self.day.room_ids.mapped("track_location_id").ids),
        )
        self.assertEqual(local(self.day.date_start).strftime("%H:%M"), "07:30")
        self.assertEqual(local(self.day.date_end).strftime("%H:%M"), "21:00")

    def test_raffle_draws_on_the_draw_tracks(self):
        draws = self.day.raffle_ids.draw_ids.sorted("sequence")
        self.assertEqual(draws.mapped("sequence"), list(range(1, 8)))
        self.assertFalse(any(draws.mapped("winner_name")))
        draw_tracks = self.day.track_ids.filtered(
            lambda t: t.name.startswith(DRAW_TITLE)
        )
        self.assertEqual(draws.mapped("date"), draw_tracks.mapped("date"))

    def test_home_agenda_at_ten_thirty(self):
        self.authenticate("rlq_demo_moderator", "rlq_demo_moderator")
        self._freeze_now()
        doc = self._get("/webapp_event/%d" % self.day.id)
        sessions = doc.xpath(
            "//section[@id='ewp_track_agenda']//li[@data-ewp-track-id]"
        )
        self.assertEqual(len(sessions), 21)
        starts = [
            datetime.fromisoformat(
                s.xpath(".//*[@class='ewp_track_when']/time/@datetime")[0]
            )
            for s in sessions
        ]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(starts[0].strftime("%H:%M"), "07:30")
        room_by_location = {
            room.track_location_id.id: room for room in self.day.room_ids
        }
        tracks = {t.id: t for t in self.day.track_ids}
        states = {}
        for session in sessions:
            track = tracks[int(session.get("data-ewp-track-id"))]
            room = room_by_location[track.location_id.id]
            link = session.xpath(".//a[@class='ewp_track_room_link']")
            self.assertEqual(len(link), 1, track.name)
            self.assertEqual(
                link[0].get("href"),
                "/webapp_event/%d/room/%d" % (self.day.id, room.id),
            )
            self.assertEqual(link[0].text_content().strip(), room.name)
            states.setdefault(session.get("data-ewp-state"), set()).add(
                track.name
            )
            if track.name == NOW_TRACK:
                self.assertEqual(room.name, NOW_ROOM)
                badge = session.xpath(
                    ".//span[contains(@class, 'ewp_track_badge_now')]"
                )[0]
                self.assertIsNone(badge.get("hidden"))
        self.assertIn(NOW_TRACK, states["now"])
        self.assertEqual(states["next"], NEXT_TRACKS)

    def test_room_page_at_ten_thirty(self):
        self.authenticate("rlq_demo_moderator", "rlq_demo_moderator")
        self._freeze_now()
        room = self.day.room_ids.filtered(lambda r: r.name == NOW_ROOM)
        doc = self._get("/webapp_event/%d/room/%d" % (self.day.id, room.id))
        status = doc.xpath("//p[contains(@class, 'ewp_track_room_status')]")
        self.assertEqual(
            status[0].text_content().strip(), "Now: %s" % NOW_TRACK
        )
        titles = doc.xpath(
            "//section[@id='ewp_track_room']"
            "//*[@class='ewp_track_title_text']/text()"
        )
        self.assertEqual(
            titles,
            [NOW_TRACK, "ERPLibre et ses nouveautés"],
        )
