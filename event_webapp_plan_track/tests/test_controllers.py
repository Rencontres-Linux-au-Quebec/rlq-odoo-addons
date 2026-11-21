# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""HTTP tests of the agenda: the home card (slots, states, room links,
speaker, tags, filter without script), the line under each room, the room
block, the text-only mode, the time zone and the language of the times, and
the JSON route (anonymous, closed day, room of another day, no unpublished
track).

Every name below is invented for the tests."""

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytz
from lxml import html as lxml_html
from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools.misc import format_time

EVENT_TZ = "America/Montreal"


@tagged("post_install", "-at_install")
class TestAgendaControllers(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.env["event.webapp"].search([]).write({"active": False})
        now = fields.Datetime.now()
        cls.now = now
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_agenda_portal",
            password="ewp_agenda_portal",
            groups="base.group_portal",
            name="Portal Agenda Test",
            lang="en_US",
        )
        cls.moderator_user = new_test_user(
            cls.env,
            login="ewp_agenda_moderator",
            password="ewp_agenda_moderator",
            groups="base.group_user,"
            "event_webapp_plan.group_event_webapp_moderator",
            name="Moderator Agenda Test",
            lang="en_US",
        )
        Location = cls.env["event.track.location"]
        cls.loc_alpha = Location.create({"name": "Alpha Spot", "sequence": 1})
        cls.loc_beta = Location.create({"name": "Beta Spot", "sequence": 2})
        cls.loc_hall = Location.create(
            {"name": "Omega Hallway", "sequence": 3}
        )
        Tag = cls.env["event.track.tag"]
        cls.tag_onsite = Tag.create({"name": "Onsite Test", "color": 3})
        cls.tag_hidden = Tag.create({"name": "Hidden Test Tag", "color": 0})
        cls.stage_cancel = cls.env["event.track.stage"].create(
            {"name": "Agenda Test Cancelled", "is_cancel": True}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Agenda Test Fair",
                "date_begin": now - timedelta(hours=2),
                "date_end": now + timedelta(hours=8),
                "date_tz": EVENT_TZ,
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Agenda Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "event_ids": [Command.set(cls.event.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Alpha Room",
                            "track_location_id": cls.loc_alpha.id,
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 20,
                            "pos_height": 20,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Beta Room",
                            "track_location_id": cls.loc_beta.id,
                        }
                    ),
                    Command.create({"name": "Gamma Room"}),
                ],
            }
        )
        rooms = {room.name: room for room in cls.day.room_ids}
        cls.room_alpha = rooms["Alpha Room"]
        cls.room_beta = rooms["Beta Room"]
        cls.room_gamma = rooms["Gamma Room"]

        def track(name, start, hours=1.0, **values):
            vals = {
                "name": name,
                "event_id": cls.event.id,
                "date": start,
                "duration": hours,
                "is_published": True,
            }
            vals.update(values)
            return cls.env["event.track"].create(vals)

        cls.t_past = track(
            "Past Agenda Talk",
            now - timedelta(minutes=50),
            hours=0.5,
            location_id=cls.loc_beta.id,
        )
        cls.t_now = track(
            "Running Agenda Talk",
            now - timedelta(minutes=10),
            location_id=cls.loc_alpha.id,
            partner_name="Ada Speakerson",
            partner_function="Test Engineer",
            tag_ids=[Command.set((cls.tag_onsite | cls.tag_hidden).ids)],
            description=(
                "<p>Running description</p>"
                "<script>alert('agenda')</script>"
                '<p onclick="alert(1)">Click text</p>'
            ),
        )
        cls.t_next = track(
            "Coming Agenda Talk",
            now + timedelta(hours=1),
            location_id=cls.loc_beta.id,
        )
        cls.t_hall = track(
            "Hall Agenda Talk",
            now + timedelta(hours=2),
            location_id=cls.loc_hall.id,
        )
        cls.t_later = track(
            "Late Agenda Talk",
            now + timedelta(hours=3),
            location_id=cls.loc_alpha.id,
        )
        track(
            "Draft Agenda Talk",
            now + timedelta(hours=1),
            location_id=cls.loc_alpha.id,
            is_published=False,
        )
        cancelled = track(
            "Cancelled Agenda Talk",
            now + timedelta(minutes=30),
            location_id=cls.loc_beta.id,
            stage_id=cls.stage_cancel.id,
        )
        cancelled.is_published = True
        cls.shown = [
            cls.t_past,
            cls.t_now,
            cls.t_next,
            cls.t_hall,
            cls.t_later,
        ]
        cls.hidden_titles = ("Draft Agenda Talk", "Cancelled Agenda Talk")

        other_event = cls.env["event.event"].create(
            {
                "name": "Agenda Test Past Fair",
                "date_begin": now - timedelta(days=3),
                "date_end": now - timedelta(days=3) + timedelta(hours=8),
            }
        )
        cls.day_ended = cls.env["event.webapp"].create(
            {
                "name": "Agenda Test Ended Day",
                "date_start": now - timedelta(days=3),
                "date_end": now - timedelta(days=3) + timedelta(hours=8),
                "event_ids": [Command.set(other_event.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Delta Room",
                            "track_location_id": cls.loc_alpha.id,
                        }
                    )
                ],
            }
        )
        cls.room_delta = cls.day_ended.room_ids
        track(
            "Ended Agenda Talk",
            now - timedelta(days=3) + timedelta(hours=1),
            event_id=other_event.id,
            location_id=cls.loc_alpha.id,
        )
        cls.home = "/webapp_event/%s" % cls.day.id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get(self, url):
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False)
        self.env.invalidate_all()
        return response

    def _page(self, url):
        response = self._get(url)
        self.assertEqual(response.status_code, 200)
        return lxml_html.fromstring(response.text), response.text

    def _room_url(self, day, room):
        return "/webapp_event/%s/room/%s" % (day.id, room.id)

    def _item(self, page, track):
        items = page.xpath(
            "//li[contains(@class, 'ewp_track_session')]"
            "[@data-ewp-track-id='%s']" % track.id
        )
        self.assertEqual(len(items), 1, track.name)
        return items[0]

    def _text(self, element):
        return " ".join(element.text_content().split())

    def _badges(self, item):
        """Classes of the badges of ``item`` that are shown."""
        return {
            badge.get("class").split()[-1]
            for badge in item.xpath(
                ".//span[contains(@class, 'ewp_track_badge')]"
            )
            if badge.get("hidden") is None
        }

    def _local_iso(self, value):
        local = pytz.utc.localize(value).astimezone(pytz.timezone(EVENT_TZ))
        return local.isoformat(timespec="seconds")

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    def test_home_agenda_card(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, text = self._page(self.home)
        card = page.xpath("//section[@id='ewp_track_agenda']")[0]
        self.assertEqual(
            self._text(card.xpath(".//h2")[0]),
            "Agenda",
        )
        self.assertIn(EVENT_TZ, self._text(card))
        titles = [
            self._text(el)
            for el in card.xpath(".//span[@class='ewp_track_title_text']")
        ]
        self.assertEqual(titles, [t.name for t in self.shown])
        for title in self.hidden_titles:
            self.assertNotIn(title, text)
        # One heading per start, its time readable by machines.
        slots = card.xpath(".//li[@class='ewp_track_slot']/h3/time")
        self.assertEqual(
            [slot.get("datetime") for slot in slots],
            [self._local_iso(t.date) for t in self.shown],
        )
        # Session titles are headings under the time headings.
        self.assertEqual(len(card.xpath(".//li/h4")), len(self.shown))
        item_now = self._item(page, self.t_now)
        self.assertEqual(item_now.get("data-ewp-state"), "now")
        self.assertEqual(self._badges(item_now), {"ewp_track_badge_now"})
        item_next = self._item(page, self.t_next)
        self.assertEqual(item_next.get("data-ewp-state"), "next")
        self.assertEqual(self._badges(item_next), {"ewp_track_badge_next"})
        self.assertEqual(
            self._item(page, self.t_past).get("data-ewp-state"), "past"
        )
        self.assertEqual(
            self._item(page, self.t_later).get("data-ewp-state"), "later"
        )
        self.assertFalse(self._badges(self._item(page, self.t_later)))
        times = item_now.xpath(".//span[@class='ewp_track_when']/time")
        self.assertEqual(
            [t.get("datetime") for t in times],
            [
                self._local_iso(self.t_now.date),
                self._local_iso(self.t_now.date_end),
            ],
        )
        # The room of a mapped location is a link to its page; a location
        # without room is plain text.
        links = item_now.xpath(".//a[@class='ewp_track_room_link']")
        self.assertEqual(len(links), 1)
        self.assertEqual(
            links[0].get("href"), self._room_url(self.day, self.room_alpha)
        )
        self.assertEqual(self._text(links[0]), "Alpha Room")
        item_hall = self._item(page, self.t_hall)
        self.assertFalse(item_hall.xpath(".//a"))
        self.assertIn("Omega Hallway", self._text(item_hall))
        self.assertIn("Ada Speakerson, Test Engineer", self._text(item_now))
        self.assertIn("Onsite Test", self._text(item_now))
        self.assertNotIn("Hidden Test Tag", text)
        # The description is for the room page.
        self.assertNotIn("Running description", text)
        # Data of the page script: the sessions shown, nothing more.
        sessions = json.loads(card.get("data-ewp-agenda-sessions"))
        self.assertEqual(
            [s["id"] for s in sessions], [t.id for t in self.shown]
        )
        self.assertEqual(
            set(sessions[0]),
            {
                "id",
                "title",
                "start",
                "end",
                "start_label",
                "end_label",
                "room_id",
                "room_name",
            },
        )
        self.assertTrue(card.get("data-ewp-signature"))
        self.assertIn(
            "room_now", json.loads(card.get("data-ewp-agenda-messages"))
        )

    def test_room_list_says_now_and_next(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)

        def line(room):
            return page.xpath(
                "//a[@class='o_ewp_room_link'][@data-ewp-room-id='%s']"
                "//span[@class='ewp_track_room_session']" % room.id
            )

        alpha = line(self.room_alpha)
        self.assertEqual(len(alpha), 1)
        self.assertEqual(alpha[0].get("data-ewp-state"), "now")
        self.assertEqual(self._text(alpha[0]), "Now: Running Agenda Talk")
        beta = line(self.room_beta)[0]
        self.assertEqual(beta.get("data-ewp-state"), "next")
        label = format_time(self.env, self.t_next.date, EVENT_TZ, "short")
        self.assertEqual(
            self._text(beta),
            " ".join(("Next at %s: Coming Agenda Talk" % label).split()),
        )
        self.assertFalse(line(self.room_gamma))

    def test_filter_by_room_without_script(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)
        buttons = page.xpath("//form[@class='ewp_track_filter']//button")
        self.assertEqual(
            [self._text(b) for b in buttons],
            ["All rooms", "Alpha Room", "Beta Room"],
        )
        self.assertEqual(
            [b.get("aria-pressed") for b in buttons],
            ["true", "false", "false"],
        )
        self.assertEqual({b.get("name") for b in buttons}, {"agenda_room"})
        form = page.xpath("//form[@class='ewp_track_filter']")[0]
        self.assertEqual(form.get("method"), "get")
        self.assertEqual(form.get("action"), self.home + "#ewp_track_agenda")
        self.assertFalse(page.xpath("//li[@data-ewp-track-id][@hidden]"))

        page, _text = self._page(
            "%s?agenda_room=%s" % (self.home, self.room_beta.id)
        )
        buttons = page.xpath("//form[@class='ewp_track_filter']//button")
        self.assertEqual(
            [b.get("aria-pressed") for b in buttons],
            ["false", "false", "true"],
        )
        shown = {
            int(item.get("data-ewp-track-id"))
            for item in page.xpath("//li[@data-ewp-track-id][not(@hidden)]")
        }
        self.assertEqual(shown, {self.t_past.id, self.t_next.id})
        # A slot without any shown session is hidden as a whole.
        self.assertEqual(
            len(page.xpath("//li[@class='ewp_track_slot'][not(@hidden)]")), 2
        )
        for value in ("abc", str(self.room_gamma.id), "999999"):
            with self.subTest(value=value):
                page, _text = self._page(
                    "%s?agenda_room=%s" % (self.home, value)
                )
                self.assertFalse(
                    page.xpath("//li[@data-ewp-track-id][@hidden]")
                )
                pressed = page.xpath(
                    "//form[@class='ewp_track_filter']"
                    "//button[@aria-pressed='true']"
                )
                self.assertEqual(
                    [self._text(b) for b in pressed], ["All rooms"]
                )

    def test_filter_kept_in_address_with_one_busy_room(self):
        # Only the alpha room keeps sessions; the hall session has a place
        # without room. A choice still in the address filters nothing: no
        # form is offered to take it back.
        (self.t_past | self.t_next).is_published = False
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(
            "%s?agenda_room=%s" % (self.home, self.room_alpha.id)
        )
        self.assertFalse(page.xpath("//form[@class='ewp_track_filter']"))
        self.assertFalse(page.xpath("//li[@hidden][@data-ewp-track-id]"))
        self.assertFalse(page.xpath("//li[@class='ewp_track_slot'][@hidden]"))
        shown = {
            int(item.get("data-ewp-track-id"))
            for item in page.xpath("//li[@data-ewp-track-id]")
        }
        self.assertEqual(
            shown, {self.t_now.id, self.t_hall.id, self.t_later.id}
        )

    def test_room_page_block(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, text = self._page(self._room_url(self.day, self.room_alpha))
        block = page.xpath("//section[@id='ewp_track_room']")[0]
        self.assertEqual(self._text(block.xpath("./h2")[0]), "In this room")
        # The block closes the main content, after the chat.
        self.assertTrue(
            page.xpath("//main/section[last()][@id='ewp_track_room']")
        )
        self.assertEqual(
            [
                self._text(el)
                for el in block.xpath(
                    ".//li/h3/span[@class='ewp_track_title_text']"
                )
            ],
            ["Running Agenda Talk", "Late Agenda Talk"],
        )
        status = block.xpath(".//p[@class='ewp_track_room_status']")[0]
        self.assertEqual(status.get("data-ewp-state"), "now")
        self.assertEqual(self._text(status), "Now: Running Agenda Talk")
        self.assertEqual(
            block.get("data-ewp-agenda-room"), str(self.room_alpha.id)
        )
        # No room line on the page of that room.
        self.assertFalse(block.xpath(".//*[@class='ewp_track_where']"))
        details = self._item(page, self.t_now).xpath(".//details")
        self.assertEqual(len(details), 1)
        self.assertIn("Running description", self._text(details[0]))
        self.assertIn("Click text", self._text(details[0]))
        self.assertFalse(details[0].xpath(".//script"))
        self.assertNotIn("alert(", text)
        self.assertNotIn("onclick", text)
        for title in self.hidden_titles:
            self.assertNotIn(title, text)

        page, _text = self._page(self._room_url(self.day, self.room_beta))
        status = page.xpath("//p[@class='ewp_track_room_status']")[0]
        self.assertEqual(status.get("data-ewp-state"), "next")
        self.assertIn("Coming Agenda Talk", self._text(status))

        page, _text = self._page(self._room_url(self.day, self.room_gamma))
        self.assertFalse(page.xpath("//section[@id='ewp_track_room']"))

    def _refresh_rows(self, page):
        """(id, label) of each row of the automatic updates of ``page``."""
        return [
            (
                row.get("data-ewp-refresh"),
                self._text(row.xpath(".//*[@class='o_ewp_refresh_label']")[0]),
            )
            for row in page.xpath(
                "//section[@id='o_ewp_refresh']//li[@data-ewp-refresh]"
            )
        ]

    def test_automatic_updates_row(self):
        """The row "Agenda" of the automatic updates is on the home page and
        on the page of a room with its block, not on a room without one;
        in French too."""
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)
        self.assertIn(("agenda", "Agenda"), self._refresh_rows(page))
        page, _text = self._page(self._room_url(self.day, self.room_alpha))
        self.assertIn(("agenda", "Agenda"), self._refresh_rows(page))
        page, _text = self._page(self._room_url(self.day, self.room_gamma))
        self.assertNotIn("agenda", dict(self._refresh_rows(page)))
        self.env["res.lang"]._activate_lang("fr_CA")
        for module in ("event_webapp_plan", "event_webapp_plan_track"):
            self.env.ref(f"base.module_{module}")._update_translations(
                ["fr_CA"]
            )
        self.portal_user.lang = "fr_CA"
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)
        rows = self._refresh_rows(page)
        self.assertIn(("agenda", "Agenda"), rows)
        self.assertEqual(
            page.xpath("//section[@id='o_ewp_refresh']/h2")[0].text_content(),
            "Mises à jour automatiques",
        )

    def test_automatic_updates_count_to_the_next_session(self):
        """In the browser, the row "Agenda" counts down to the start of the
        next session when it comes before the next request of the program
        (every 5 minutes)."""
        self.env["event.track"].create(
            {
                "name": "Soon Agenda Talk",
                "event_id": self.event.id,
                "date": fields.Datetime.now() + timedelta(seconds=90),
                "duration": 0.5,
                "is_published": True,
                "location_id": self.loc_alpha.id,
            }
        )
        self.env.flush_all()
        code = """(async () => {
            const wait = async (fn, ms = 20000) => {
                const start = Date.now();
                while (Date.now() - start < ms) {
                    const result = fn();
                    if (result) {
                        return result;
                    }
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                throw new Error("timeout waiting for " + fn);
            };
            const row = await wait(() => {
                const el = document.querySelector('#o_ewp_refresh li[data-ewp-refresh="agenda"]');
                return el && !el.hidden && el;
            });
            const next = row.querySelector(".o_ewp_refresh_next");
            const match = await wait(() => next.textContent.match(/^Next in (?:(\\d+)\\smin\\s)?(\\d+)\\ss$/));
            const seconds = Number(match[1] || 0) * 60 + Number(match[2]);
            if (seconds > 91 || seconds < 30) {
                throw new Error("not the next session: " + next.textContent);
            }
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            self.home,
            code,
            ready="document.readyState === 'complete'",
            login="ewp_agenda_portal",
        )

    def test_text_only_mode_keeps_the_agenda(self):
        self.portal_user.ewp_text_only = True
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)
        self.assertIn("o_ewp_text_only", page.xpath("//body/@class")[0])
        card = page.xpath("//section[@id='ewp_track_agenda']")[0]
        self.assertEqual(len(card.xpath(".//li[@data-ewp-track-id]")), 5)
        self.assertTrue(card.xpath(".//form[@class='ewp_track_filter']"))
        self.assertFalse(page.xpath("//a[contains(@class, 'o_ewp_hotspot')]"))
        page, _text = self._page(self._room_url(self.day, self.room_alpha))
        self.assertTrue(page.xpath("//section[@id='ewp_track_room']"))

    def test_day_without_track_shows_no_agenda(self):
        day = self.env["event.webapp"].create(
            {
                "name": "Agenda Test Quiet Day",
                "date_start": self.now - timedelta(hours=1),
                "date_end": self.now + timedelta(hours=8),
                "room_ids": [
                    Command.create(
                        {
                            "name": "Quiet Room",
                            "track_location_id": self.loc_alpha.id,
                        }
                    )
                ],
            }
        )
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page("/webapp_event/%s" % day.id)
        self.assertFalse(page.xpath("//section[@id='ewp_track_agenda']"))
        self.assertFalse(page.xpath("//span[@class='ewp_track_room_session']"))
        page, text = self._page(self._room_url(day, day.room_ids))
        self.assertIn("No session is planned in this room for this day.", text)

    def test_times_in_the_event_time_zone_and_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        for module in ("event_webapp_plan", "event_webapp_plan_track"):
            self.env.ref("base.module_%s" % module)._update_translations(
                ["fr_CA"]
            )
        self.portal_user.lang = "fr_CA"
        # The time zone of the event wins over the one of the user.
        self.portal_user.tz = "Asia/Tokyo"
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, text = self._page(self.home)
        self.assertIn("Maintenant", text)
        expected = format_time(
            self.env(context={"lang": "fr_CA"}),
            self.t_next.date,
            EVENT_TZ,
            "short",
        )
        item = self._item(page, self.t_next)
        start = item.xpath(".//span[@class='ewp_track_when']/time")[0]
        self.assertEqual(start.text_content(), expected.replace(" ", " "))
        self.assertEqual(
            start.get("datetime"), self._local_iso(self.t_next.date)
        )

    # ------------------------------------------------------------------
    # JSON route
    # ------------------------------------------------------------------
    def _agenda_url(self, day, room=None):
        url = "/webapp_event/%s/agenda" % day.id
        return url + ("?room=%s" % room if room else "")

    def test_json_route_anonymous_goes_to_login(self):
        self.authenticate(None, None)
        response = self._get(self._agenda_url(self.day))
        self.assertIn(response.status_code, (302, 303))
        location = urlparse(response.headers["Location"])
        self.assertEqual(location.path, "/web/login")
        self.assertTrue(
            parse_qs(location.query)["redirect"][0].startswith("/webapp_event")
        )

    def test_json_route_content(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        page, _text = self._page(self.home)
        response = self._get(self._agenda_url(self.day))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        data = response.json()
        self.assertEqual(set(data), {"signature", "sessions", "html"})
        self.assertEqual(
            data["signature"],
            page.xpath(
                "//section[@id='ewp_track_agenda']/@data-ewp-signature"
            )[0],
        )
        self.assertEqual(
            [s["id"] for s in data["sessions"]], [t.id for t in self.shown]
        )
        self.assertIn("Late Agenda Talk", data["html"])
        for title in self.hidden_titles:
            self.assertNotIn(title, response.text)
        self.assertNotIn("Ended Agenda Talk", response.text)

        response = self._get(self._agenda_url(self.day, self.room_alpha.id))
        data = response.json()
        self.assertIn("Late Agenda Talk", data["room_html"])
        self.assertNotIn("Coming Agenda Talk", data["room_html"])
        self.assertIn("Running description", data["room_html"])
        self.assertNotIn("<script", data["room_html"])

    def test_json_route_access(self):
        self.authenticate("ewp_agenda_portal", "ewp_agenda_portal")
        cases = (
            (self._agenda_url(self.day_ended), 403),
            (self._agenda_url(self.day, self.room_delta.id), 404),
            (self._agenda_url(self.day, "abc"), 404),
            ("/webapp_event/999999/agenda", 404),
        )
        for url, status in cases:
            with self.subTest(url=url):
                response = self._get(url)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Agenda Talk", response.text)
        self.authenticate("ewp_agenda_moderator", "ewp_agenda_moderator")
        response = self._get(self._agenda_url(self.day_ended))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [s["title"] for s in response.json()["sessions"]],
            ["Ended Agenda Talk"],
        )
