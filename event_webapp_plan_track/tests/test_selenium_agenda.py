# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""End-to-end tests of the agenda in a real browser, through Selenium
(SeleniumCase of event_webapp_plan, tests/selenium_common.py).

The tracks are placed around the clock of the test: one in progress, the
next one in an hour, and, for the live announcement, a short track that
starts a few seconds after the room page opens, so the page script sees it
start, says it once in the live region, sends ewp:session and sees it end;
moved a few seconds later, it starts again without being said twice. The
tests also filter the agenda with the mouse and with the keyboard (two
sessions of one slot in two rooms included), go from a session to its room
by keyboard, open a description, and run axe-core (WCAG 2.2 A and AA, plus
"region") on the pages with the agenda when EWP_AXE_JS names a copy of
axe.min.js. Every name below is invented for the tests."""

import os
from datetime import timedelta

from odoo import Command, fields
from odoo.addons.event_webapp_plan.tests.selenium_common import (
    PHONE,
    By,
    Keys,
    SeleniumCase,
)
from odoo.tests import tagged
from odoo.tests.common import new_test_user

EVENT_TZ = "America/Montreal"

# Keeps the details of the CustomEvents `name` of the page in
# window.ewpTestEvents[name].
JS_RECORD_EVENTS = """
window.ewpTestEvents = window.ewpTestEvents || {};
for (const name of arguments) {
    window.ewpTestEvents[name] = [];
    document.addEventListener(name, (ev) => window.ewpTestEvents[name].push(ev.detail));
}
"""

# axe-core run on the document, WCAG 2.0/2.1/2.2 A and AA rules and the
# "region" rule; the chat frame is the Discuss client of Odoo. It waits for
# the animations that end (the entrance of the cards of a theme starts
# from opacity 0, which would read as a missing contrast).
JS_AXE_RUN = """
const done = arguments[arguments.length - 1];
const ending = document.getAnimations().filter((animation) => {
    const timing = animation.effect && animation.effect.getComputedTiming();
    return timing && Number.isFinite(timing.endTime);
});
Promise.all(ending.map((animation) => animation.finished.catch(() => null)))
    .then(() => window.axe.run(document, {
        iframes: false,
        runOnly: {type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]},
        rules: {region: {enabled: true}},
    }))
    .then(
        (result) => done(result.violations.map(
            (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`
        )),
        (error) => done(["axe error: " + error.message]),
    );
"""


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumAgenda(SeleniumCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_agenda_selenium",
            password="ewp_agenda_selenium",
            groups="base.group_portal",
            name="Portal Agenda Selenium",
            lang="en_US",
        )
        Location = cls.env["event.track.location"]
        cls.loc_alpha = Location.create(
            {"name": "Selenium Alpha Spot", "sequence": 1}
        )
        cls.loc_beta = Location.create(
            {"name": "Selenium Beta Spot", "sequence": 2}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Selenium Agenda Fair",
                "date_begin": now - timedelta(hours=2),
                "date_end": now + timedelta(hours=8),
                "date_tz": EVENT_TZ,
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Selenium Agenda Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "event_ids": [Command.set(cls.event.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Selenium Alpha Room",
                            "track_location_id": cls.loc_alpha.id,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Selenium Beta Room",
                            "track_location_id": cls.loc_beta.id,
                        }
                    ),
                ],
            }
        )
        rooms = {room.name: room for room in cls.day.room_ids}
        cls.room_alpha = rooms["Selenium Alpha Room"]
        cls.room_beta = rooms["Selenium Beta Room"]
        tag = cls.env["event.track.tag"].create(
            {"name": "Selenium Onsite", "color": 4}
        )
        Track = cls.env["event.track"]
        cls.t_now = Track.create(
            {
                "name": "Selenium Running Talk",
                "event_id": cls.event.id,
                "date": now - timedelta(minutes=10),
                "duration": 1.0,
                "is_published": True,
                "location_id": cls.loc_alpha.id,
                "partner_name": "Ada Seleniumspeaker",
                "partner_function": "Test Maintainer",
                "tag_ids": [Command.set(tag.ids)],
                "description": "<p>Selenium running description</p>",
            }
        )
        cls.t_next = Track.create(
            {
                "name": "Selenium Coming Talk",
                "event_id": cls.event.id,
                "date": now + timedelta(hours=1),
                "duration": 1.0,
                "is_published": True,
                "location_id": cls.loc_beta.id,
            }
        )
        cls.t_later = Track.create(
            {
                "name": "Selenium Late Talk",
                "event_id": cls.event.id,
                "date": now + timedelta(hours=3),
                "duration": 1.0,
                "is_published": True,
                "location_id": cls.loc_alpha.id,
            }
        )
        cls.home = "/webapp_event/%s" % cls.day.id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _room_path(self, room):
        return "/webapp_event/%s/room/%s" % (self.day.id, room.id)

    def _item(self, track):
        return self.wait_for(
            ".ewp_track_session[data-ewp-track-id='%s']" % track.id,
            visible=False,
        )

    def _shown_ids(self):
        return {
            int(el.get_attribute("data-ewp-track-id"))
            for el in self.find_all(
                "#ewp_track_agenda .ewp_track_session[data-ewp-track-id]"
            )
            if el.is_displayed()
        }

    def _tab_to(self, predicate, message, limit=80):
        """Press Tab until ``predicate(active_element())`` holds."""
        for _index in range(limit):
            self.tab()
            if predicate(self.active_element()):
                return
        self.fail(message)

    def _axe(self, label):
        path = os.environ.get("EWP_AXE_JS")
        with open(path, encoding="utf-8") as handle:
            self.js(handle.read() + "\n;return true;")
        self.driver.set_script_timeout(120)
        violations = self.driver.execute_async_script(JS_AXE_RUN)
        self.assertEqual(violations, [], "axe on %s" % label)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_home_agenda_now_next_and_filter(self):
        self.login("ewp_agenda_selenium", redirect=self.home)
        self.wait_page_ready()
        item_now = self._item(self.t_now)
        self.assertEqual(item_now.get_attribute("data-ewp-state"), "now")
        badge = item_now.find_element(By.CSS_SELECTOR, ".ewp_track_badge_now")
        self.assertTrue(badge.is_displayed())
        # The visible word, after the comma read by screen readers only.
        self.assertTrue(self.text(badge).endswith("Now"))
        self.assertFalse(
            item_now.find_element(
                By.CSS_SELECTOR, ".ewp_track_badge_next"
            ).is_displayed()
        )
        item_next = self._item(self.t_next)
        self.assertEqual(item_next.get_attribute("data-ewp-state"), "next")
        self.assertTrue(
            item_next.find_element(
                By.CSS_SELECTOR, ".ewp_track_badge_next"
            ).is_displayed()
        )
        line = self.wait_for(
            ".ewp_track_room_session[data-ewp-track-room='%s']"
            % self.room_alpha.id
        )
        self.assertEqual(self.text(line), "Now: Selenium Running Talk")
        self.assertEqual(
            self._shown_ids(), {self.t_now.id, self.t_next.id, self.t_later.id}
        )

        beta = self.wait_for(
            ".ewp_track_filter_choice[value='%s']" % self.room_beta.id
        )
        beta.click()
        self.wait_announcement(
            "Agenda of Selenium Beta Room, sessions shown: 1."
        )
        self.assertEqual(beta.get_attribute("aria-pressed"), "true")
        self.assertEqual(self._shown_ids(), {self.t_next.id})
        self.assertIn(
            "agenda_room=%s" % self.room_beta.id, self.driver.current_url
        )
        # The page stays: no reload, the script filtered in place.
        self.assertEqual(self.path(), self.home)
        self.wait_for(".ewp_track_filter_choice[value='']").click()
        self.wait_announcement("Agenda of all rooms, sessions shown: 3.")
        self.assertEqual(
            self._shown_ids(), {self.t_now.id, self.t_next.id, self.t_later.id}
        )
        self.assertNotIn("agenda_room", self.driver.current_url)

    def test_filter_hides_a_session_that_shares_its_slot(self):
        with self.server_paused():
            paired = self.env["event.track"].create(
                {
                    "name": "Selenium Paired Talk",
                    "event_id": self.event.id,
                    "date": self.t_later.date,
                    "duration": 1.0,
                    "is_published": True,
                    "location_id": self.loc_beta.id,
                }
            )
        self.login("ewp_agenda_selenium", redirect=self.home)
        self.wait_page_ready()
        item_paired = self._item(paired)
        item_later = self._item(self.t_later)
        self.assertTrue(item_paired.is_displayed())
        self.assertTrue(item_later.is_displayed())
        self.wait_for(
            ".ewp_track_filter_choice[value='%s']" % self.room_alpha.id
        ).click()
        self.wait_announcement(
            "Agenda of Selenium Alpha Room, sessions shown: 2."
        )
        self.assertEqual(self._shown_ids(), {self.t_now.id, self.t_later.id})
        self.assertFalse(item_paired.is_displayed())
        self.assertEqual(
            self.js(
                "return getComputedStyle(arguments[0]).display;", item_paired
            ),
            "none",
        )
        # Without script, the server hides the same item: the page loaded
        # with the choice in the address shows the same sessions.
        # The entrance of the cards of a theme starts from opacity 0: wait
        # for it to end.
        self.open("%s?agenda_room=%s" % (self.home, self.room_alpha.id))
        self.wait_until(
            lambda: self._shown_ids() == {self.t_now.id, self.t_later.id},
            "the filtered page does not show the sessions of the room",
        )

    def test_session_start_is_announced_in_the_room(self):
        self.login("ewp_agenda_selenium", redirect=self.home)
        self.wait_page_ready()
        with self.server_paused():
            soon = self.env["event.track"].create(
                {
                    "name": "Selenium Soon Talk",
                    "event_id": self.event.id,
                    "date": fields.Datetime.now() + timedelta(seconds=10),
                    # 15 seconds.
                    "duration": 15 / 3600.0,
                    "is_published": True,
                    "location_id": self.loc_beta.id,
                }
            )
        self.open(self._room_path(self.room_beta))
        self.js(JS_RECORD_EVENTS, "ewp:session", "ewp:announce", "ewp:cameo")
        item = self._item(soon)
        self.assertIn(item.get_attribute("data-ewp-state"), ("next", "later"))
        self.wait_announcement(
            "Now in this room: Selenium Soon Talk.", timeout=40
        )
        self.assertEqual(item.get_attribute("data-ewp-state"), "now")
        status = self.wait_for(".ewp_track_room_status")
        self.assertEqual(self.text(status), "Now: Selenium Soon Talk")
        events = self.js("return window.ewpTestEvents['ewp:session'];")
        self.assertEqual(
            [(e["state"], e["track"]["id"], e["room"]["id"]) for e in events],
            [("start", soon.id, self.room_beta.id)],
        )
        # The start plays a "speak" cameo (animations run by default).
        self.assertEqual(
            self.js("return document.body.dataset.ewpMotion;"), "running"
        )
        self.wait_until(
            lambda: [
                c
                for c in self.js("return window.ewpTestEvents['ewp:cameo'];")
                if c["phase"] == "enter"
                and c["trigger"] == "play"
                and c["action"] == "speak"
            ],
            "no speak cameo when the session started",
        )
        # Told once: moved a few seconds later, the session goes back to
        # "later" at the refresh of the program (tab shown again), then
        # starts again; the second start is sent, never said.
        with self.server_paused():
            soon.date = fields.Datetime.now() + timedelta(seconds=8)
        self.set_page_hidden(True)
        self.set_page_hidden(False)
        self.wait_until(
            lambda: self.js(
                "return window.ewpTestEvents['ewp:session'].length;"
            )
            == 4,
            "the moved session did not start and end again",
            timeout=60,
        )
        events = self.js("return window.ewpTestEvents['ewp:session'];")
        # The refresh rendered the blocks again: a new item.
        item = self._item(soon)
        self.assertEqual(
            [(e["state"], e["track"]["id"]) for e in events],
            [
                ("start", soon.id),
                ("end", soon.id),
                ("start", soon.id),
                ("end", soon.id),
            ],
        )
        self.assertEqual(item.get_attribute("data-ewp-state"), "past")
        announces = self.js("return window.ewpTestEvents['ewp:announce'];")
        self.assertEqual(
            [a["text"] for a in announces],
            ["Now in this room: Selenium Soon Talk."],
        )
        status = self.wait_for(".ewp_track_room_status")
        self.wait_until(
            lambda: self.text(status).startswith("Next at "),
            "the state line did not move to the next session",
        )
        self.assertIn("Selenium Coming Talk", self.text(status))

    def test_keyboard_path_filter_room_and_description(self):
        self.set_viewport(*PHONE)
        self.login("ewp_agenda_selenium", redirect=self.home)
        self.wait_page_ready()
        self.js("document.activeElement && document.activeElement.blur();")
        self._tab_to(
            lambda el: "ewp_track_filter_choice" in el["className"]
            and el["text"] == "Selenium Alpha Room",
            "the filter button of a room is not reachable by Tab",
        )
        self.press(Keys.SPACE)
        self.wait_announcement(
            "Agenda of Selenium Alpha Room, sessions shown: 2."
        )
        self.assertEqual(self._shown_ids(), {self.t_now.id, self.t_later.id})
        self._tab_to(
            lambda el: "ewp_track_room_link" in el["className"],
            "the room of a session is not reachable by Tab",
        )
        self.assertEqual(self.active_element()["text"], "Selenium Alpha Room")
        self.press(Keys.ENTER)
        self.wait_until(
            lambda: self.path() == self._room_path(self.room_alpha),
            "Enter on the room link did not open the room",
        )
        self.wait_page_ready()
        # The chat composer takes the focus as it loads; the walk starts
        # again from the first skip link. The second one leads to the
        # display options, right after the room block: one Shift+Tab back
        # is the description of its last session that has one.
        frame = self.wait_for("iframe.o_ewp_chat")
        self.driver.switch_to.frame(frame)
        try:
            self.wait_for(".o-mail-Composer-input", "chat composer missing")
        finally:
            self.driver.switch_to.default_content()
        self.js("document.querySelector('a.o_ewp_skip').focus();")
        self.tab()
        self.assertIn("Display options", self.active_element()["text"])
        self.press(Keys.ENTER)
        self.assertEqual(self.active_element()["id"], "o_ewp_text_only_toggle")
        # Shift stays down for the rest of the keys sent to an element.
        self.driver.switch_to.active_element.send_keys(Keys.SHIFT + Keys.TAB)
        self.assertEqual(self.active_element()["tag"], "summary")
        self.press(Keys.ENTER)
        details = self._item(self.t_now).find_element(
            By.CSS_SELECTOR, "details"
        )
        self.wait_until(
            lambda: details.get_attribute("open") is not None,
            "Enter did not open the description",
        )
        self.assertIn("Selenium running description", self.text(details))

    def test_axe_on_pages_with_the_agenda(self):
        path = os.environ.get("EWP_AXE_JS")
        if not path or not os.path.isfile(path):
            self.skipTest("EWP_AXE_JS does not name a copy of axe.min.js")
        self.login("ewp_agenda_selenium", redirect=self.home)
        self.wait_page_ready()
        self._axe("home")
        self.open(self._room_path(self.room_alpha))
        self._item(self.t_now).find_element(By.CSS_SELECTOR, "summary").click()
        self._axe("room, description open")
        self.emulate_media(color_scheme="dark")
        self.open(self.home)
        self._axe("home, dark scheme")
        self.emulate_media()
        with self.server_paused():
            self.portal_user.ewp_text_only = True
        self.open(self.home)
        self._axe("home, text-only mode")
        self.open(self._room_path(self.room_alpha))
        self._axe("room, text-only mode")
