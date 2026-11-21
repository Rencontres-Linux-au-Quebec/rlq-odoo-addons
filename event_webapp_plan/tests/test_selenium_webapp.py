# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""End-to-end tests of /webapp_event in a real browser, through Selenium
(see selenium_common.py for the browser and the shared cursor).

They log in through the login form, click and type as a visitor does, and
read the page as the browser renders it: the login redirect, the home page
on a phone and in both colour schemes, the room entry and its chat, the
preview banner and the closed page, a raffle drawn while the page is open,
the conference that starts, is left and joined again, a running meeting
behind the new tab button, the display options kept on the user, the
animations stopped by the toggle and by the system setting, the skip
links, and a keyboard-only path to a room and back.

The polls of the page run every 20 or 30 s; the tests fire the
visibilitychange event instead, on which the page asks the server at once
(the visitor coming back to the tab), so no test waits for a timer.
BigBlueButton is the FakeNetwork of test_bbb, and the join URL a static
file of the module, so the browser reaches no other host. Every name below
is invented for the tests."""

from datetime import timedelta

from odoo import Command, fields
from odoo.addons.event_webapp_plan.models import bbb_client
from odoo.addons.event_webapp_plan.models.event_webapp_room import (
    PARAM_BBB_DISPLAY,
    PARAM_BBB_SECRET,
    PARAM_BBB_URL,
)
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .selenium_common import PHONE, By, Keys, SeleniumCase
from .test_bbb import SECRET, SERVER, FakeNetwork, fake_network
from .test_browser import CLIENT_PATH, _png_b64

# Animation added to a page by the tests: the pause rules of the module
# must stop it as they stop the animations of a theme.
JS_ADD_ANIMATION = """
const style = document.createElement("style");
style.textContent = "@keyframes ewp-test-spin { to { transform: rotate(1turn); } }"
    + " .ewp_test_spin { animation: ewp-test-spin 1s linear infinite; }";
document.head.appendChild(style);
const spinner = document.createElement("div");
spinner.className = "ewp_test_spin";
spinner.setAttribute("aria-hidden", "true");
document.getElementById("o_ewp_main").appendChild(spinner);
"""

# Keeps the details of the CustomEvents `name` of the page in
# window.ewpTestEvents[name].
JS_RECORD_EVENTS = """
window.ewpTestEvents = window.ewpTestEvents || {};
for (const name of arguments) {
    window.ewpTestEvents[name] = [];
    document.addEventListener(name, (ev) => window.ewpTestEvents[name].push(ev.detail));
}
"""

# The page asks its JSON routes again, as when the visitor comes back to
# the tab.
JS_VISIBLE_AGAIN = "document.dispatchEvent(new Event('visibilitychange'));"


class WebappSeleniumCase(SeleniumCase):
    """Records shared by the Selenium tests of the pages: a portal user, a
    moderator, a day open now with two rooms on its plan, an event and a
    raffle with one draw done; helpers to log in, set up a conference and
    wait for the chat. It holds no test of its own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_selenium_portal",
            password="ewp_selenium_portal",
            groups="base.group_portal",
            name="Portal Selenium Test",
            lang="en_US",
        )
        cls.moderator_user = new_test_user(
            cls.env,
            login="ewp_selenium_moderator",
            password="ewp_selenium_moderator",
            groups="base.group_user,"
            "event_webapp_plan.group_event_webapp_moderator",
            name="Moderator Selenium Test",
            lang="en_US",
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Selenium Test Keynote",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
            }
        )
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Selenium Test Raffle",
                "event_id": cls.event.id,
                "draw_ids": [
                    Command.create(
                        {
                            "sequence": 1,
                            "prize": "Selenium Test Keyboard",
                            "winner_name": "Ada Seleniumwinner",
                        }
                    ),
                    Command.create(
                        {"sequence": 2, "prize": "Selenium Test Mug"}
                    ),
                ],
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Selenium Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "announcement": "<p>Welcome to the Selenium test day</p>",
                "plan_image": _png_b64(400, 200),
                "event_ids": [Command.set(cls.event.ids)],
                "raffle_ids": [Command.set(cls.raffle.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Omicron Hall",
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 20,
                            "pos_height": 30,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Sigma Lab",
                            "pos_x": 60,
                            "pos_y": 50,
                            "pos_width": 25,
                            "pos_height": 25,
                        }
                    ),
                ],
            }
        )
        cls.room_hall = cls.day.room_ids.filtered(
            lambda r: r.name == "Omicron Hall"
        )
        cls.room_lab = cls.day.room_ids - cls.room_hall
        cls.home = "/webapp_event/%s" % cls.day.id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _login_portal(self, path=None):
        self.login("ewp_selenium_portal", redirect=path or self.home)
        self.wait_page_ready()

    def _conference(self, running, display="frame"):
        """Day with one room whose meeting runs, or not, on a FakeNetwork
        kept for the whole test; bbb_join redirects to CLIENT_PATH.
        `display` is the display mode of the conferences: the fake server
        is on another site than the test server, so "auto" shows the
        button and "frame" the frame. Returns (network, room page path).
        The records are written under server_paused(): a page with its
        chat may be open."""
        network = FakeNetwork(running=running)
        context = fake_network(network)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.patch(bbb_client, "join_url", lambda *args, **kwargs: CLIENT_PATH)
        with self.server_paused():
            params = self.env["ir.config_parameter"].sudo()
            params.set_param(PARAM_BBB_URL, SERVER)
            params.set_param(PARAM_BBB_SECRET, SECRET)
            params.set_param(PARAM_BBB_DISPLAY, display)
            day = self.env["event.webapp"].create(
                {
                    "name": "Selenium Conference Day",
                    "date_start": fields.Datetime.now() - timedelta(hours=1),
                    "date_end": fields.Datetime.now() + timedelta(hours=8),
                    "room_ids": [
                        Command.create(
                            {
                                "name": "Upsilon Studio",
                                "bbb_meeting_id": "gl-invented-selenium-0001",
                            }
                        )
                    ],
                }
            )
            path = "/webapp_event/%s/room/%s" % (day.id, day.room_ids.id)
        return network, path

    def _assert_no_server_address(self):
        source = self.driver.page_source
        self.assertNotIn("bbb.example.org", source)
        self.assertNotIn(SECRET, source)

    def _frame_path(self):
        """Path of the document of the conference frame, or None while it
        belongs to another origin or is missing."""
        return self.js(
            "const frame = document.querySelector('iframe.o_ewp_bbb_frame');"
            "try { return frame && frame.contentDocument.readyState"
            " === 'complete' ? frame.contentWindow.location.pathname"
            " : null; } catch (error) { return null; }"
        )

    def _chat_loaded(self):
        """Wait until the chat frame shows its composer."""
        frame = self.wait_for("iframe.o_ewp_chat")
        self.driver.switch_to.frame(frame)
        try:
            self.wait_for(".o-mail-Composer-input", "chat composer missing")
        finally:
            self.driver.switch_to.default_content()
        return frame


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumWebapp(WebappSeleniumCase):
    def test_anonymous_visitor_logs_in_and_comes_back(self):
        """An anonymous visitor lands on the login form, which sends them
        back to the page they asked for."""
        self.open(self.home, ready=False)
        self.wait_until(
            lambda: self.path() == "/web/login", "no redirect to login"
        )
        self.assertIn(
            "redirect=%2Fwebapp_event%2F" + str(self.day.id),
            self.driver.current_url,
        )
        self.submit_login_form("ewp_selenium_portal")
        self.wait_page_ready()
        self.assertEqual(self.path(), self.home)
        self.assertEqual(
            self.js("return document.body.dataset.ewpPage;"), "home"
        )

    def test_home_page_on_a_phone_in_both_colour_schemes(self):
        """On a phone, the home page shows the plan with its room areas,
        the room list, the events and the raffles in one column, without
        horizontal scrolling; the dark colour scheme changes the page
        ground."""
        width = self.set_viewport(*PHONE)
        self._login_portal()
        if self.browser_name == "chromium":
            self.assertEqual(width, PHONE[0])
        # Under the wide layout, which starts at 1024 px.
        self.assertLess(self.js("return window.innerWidth;"), 1024)
        self.wait_js(
            "(() => { const img = document.querySelector('img.o_ewp_plan_image');"
            " return img && img.complete && img.naturalWidth > 0; })()",
            "plan image not loaded",
        )
        self.assertEqual(
            self.text(self.wait_for("h1.o_ewp_day_title")),
            "Selenium Test Day",
        )
        self.assertEqual(len(self.find_all("a.o_ewp_hotspot")), 2)
        names = [
            self.text(el)
            for el in self.find_all(".o_ewp_room_link .o_ewp_room_name")
        ]
        self.assertEqual(sorted(names), ["Omicron Hall", "Sigma Lab"])
        self.assertIn(
            "Selenium Test Keynote",
            self.text(self.wait_for(".o_ewp_events_card")),
        )
        raffles = self.text(self.wait_for(".o_ewp_raffles_card"))
        self.assertIn("Selenium Test Raffle", raffles)
        self.assertIn("Ada Seleniumwinner", raffles)
        self.assertIn(
            "Welcome to the Selenium test day", self.driver.page_source
        )
        self.assertLessEqual(
            self.js("return document.documentElement.scrollWidth;"),
            self.js("return window.innerWidth;"),
            "horizontal scroll on a phone",
        )
        # One column: the plan card and the raffles card share their left
        # edge.
        lefts = self.js(
            "return ['.o_ewp_plan_card', '.o_ewp_raffles_card'].map("
            "(s) => Math.round(document.querySelector(s)"
            ".getBoundingClientRect().left));"
        )
        self.assertEqual(lefts[0], lefts[1])
        light = self.js(
            "return getComputedStyle(document.body).backgroundColor;"
        )
        self.emulate_media(color_scheme="dark")
        self.open(self.home)
        self.assertTrue(
            self.js(
                "return matchMedia('(prefers-color-scheme: dark)').matches;"
            )
        )
        dark = self.js(
            "return getComputedStyle(document.body).backgroundColor;"
        )
        self.assertNotEqual(light, dark, "same page ground in dark mode")

    def test_room_entry_grants_the_room_group_and_loads_the_chat(self):
        """Clicking a room of the list opens its page, gives the visitor
        the access group of the room and embeds its Discuss channel."""
        group = self.room_hall.access_group_id
        self.assertTrue(group)
        self.assertNotIn(group, self.portal_user.groups_id)
        self._login_portal()
        link = self.wait_for(
            ".o_ewp_room_link[data-ewp-room-id='%s']" % self.room_hall.id
        )
        link.click()
        self.wait_page_ready()
        self.assertEqual(
            self.path(),
            "/webapp_event/%s/room/%s" % (self.day.id, self.room_hall.id),
        )
        self.assertEqual(
            self.text(self.wait_for("h1.o_ewp_room_title")),
            "Omicron Hall",
        )
        frame = self._chat_loaded()
        self.assertEqual(
            frame.get_attribute("title"), "Discussion: Omicron Hall"
        )
        with self.server_paused():
            self.assertIn(group, self.portal_user.groups_id)
            self.assertIn(
                self.portal_user.partner_id,
                self.room_hall.channel_id.channel_member_ids.partner_id,
            )

    def test_preview_banner_for_moderators_and_closed_page_for_portal(self):
        """Before the opening, a moderator sees the day under a preview
        banner; a portal user sees the closed page, without the plan."""
        later = fields.Datetime.now() + timedelta(days=2)
        day = self.env["event.webapp"].create(
            {
                "name": "Selenium Future Day",
                "date_start": later,
                "date_end": later + timedelta(hours=8),
                "room_ids": [Command.create({"name": "Phi Room"})],
            }
        )
        path = "/webapp_event/%s" % day.id
        self.login("ewp_selenium_moderator", redirect=path)
        self.wait_page_ready()
        banner = self.wait_for(".o_ewp_preview_banner")
        self.assertIn("Preview outside opening hours.", self.text(banner))
        self.assertEqual(len(self.find_all(".o_ewp_room_link")), 1)
        self.logout()
        self.login("ewp_selenium_portal", redirect=path)
        self.wait_page_ready()
        self.assertEqual(
            self.js("return document.body.dataset.ewpPage;"), "closed"
        )
        self.assertEqual(
            self.text(self.wait_for("main h1")),
            "Selenium Future Day is not open yet",
        )
        self.assertFalse(self.find_all(".o_ewp_preview_banner"))
        self.assertFalse(self.find_all(".o_ewp_room_link"))
        self.assertTrue(
            self.driver.title.startswith("Not open yet - Selenium Future Day")
        )

    def test_raffle_drawn_on_the_server_is_announced(self):
        """A draw that gets a winner while the page is open: the next
        answer of the raffle route replaces the block, says the winner in
        the live region and sends ewp:raffle-drawn."""
        self._login_portal()
        self.js(JS_RECORD_EVENTS, "ewp:raffle-drawn")
        with self.server_paused():
            draw = self.raffle.draw_ids.filtered(lambda d: d.sequence == 2)
            draw.winner_name = "Linus Seleniumwinner"
        self.js(JS_VISIBLE_AGAIN)
        self.wait_announcement(
            "New winner, Selenium Test Raffle, Selenium Test Mug: "
            "Linus Seleniumwinner."
        )
        row = self.wait_for(".o_ewp_draw[data-ewp-draw-id='%s']" % draw.id)
        self.assertIn("o_ewp_draw_done", row.get_attribute("class"))
        self.assertIn("Linus Seleniumwinner", self.text(row))
        events = self.js("return window.ewpTestEvents['ewp:raffle-drawn'];")
        self.assertEqual(
            [(e["drawId"], e["winner"]) for e in events],
            [(draw.id, "Linus Seleniumwinner")],
        )
        self.assertIn(
            "2 drawn of 2", self.text(self.wait_for(".o_ewp_raffle_progress"))
        )

    def test_conference_waiting_then_running_loads_the_frame(self):
        """The waiting page asks the server; once the meeting runs it
        loads itself again with the conference frame, says so and puts
        the focus on the heading of the conference block."""
        network, room = self._conference(running=False)
        self._login_portal(room)
        section = self.wait_for(".o_ewp_bbb", visible=False)
        self.assertEqual(
            section.get_attribute("data-ewp-bbb-state"), "waiting"
        )
        self.assertIn(
            "The conference has not started yet.",
            self.text(self.wait_for(".o_ewp_bbb_waiting")),
        )
        self.assertFalse(self.find_all("iframe.o_ewp_bbb_frame"))
        self._assert_no_server_address()
        with self.server_paused():
            network.running = True
        self.js("window.ewpTestOldPage = true;" + JS_VISIBLE_AGAIN)
        self.wait_js(
            "!window.ewpTestOldPage && document.readyState === 'complete'"
            " && document.body.dataset.ewpMotion",
            "the page did not load again",
        )
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "running",
        )
        self.wait_until(
            lambda: self._frame_path() == CLIENT_PATH,
            "conference frame did not reach the client",
        )
        self.wait_announcement("The conference has started.")
        self._chat_loaded()
        self.wait_until(
            lambda: self.active_element()["id"] == "o_ewp_h_bbb",
            "focus not on the conference heading",
        )
        self._assert_no_server_address()

    def test_leaving_the_conference_and_joining_again(self):
        """The frame reaching bbb_left (the logoutURL of the join URL)
        shows the notice, with the focus on "Join again"; that button asks
        the server and, the meeting still running, loads the frame
        again."""
        _network, room = self._conference(running=True)
        self._login_portal(room)
        self.wait_until(
            lambda: self._frame_path() == CLIENT_PATH,
            "conference frame did not reach the client",
        )
        self._chat_loaded()
        notice = self.driver.find_element(By.CSS_SELECTOR, ".o_ewp_bbb_left")
        self.assertFalse(notice.is_displayed())
        self.js(
            "const frame = document.querySelector('iframe.o_ewp_bbb_frame');"
            "const left = document.querySelector('.o_ewp_bbb_left')"
            ".dataset.ewpBbbLeftPath;"
            "frame.contentWindow.location.href = left"
            " + '?frame=1&reason=left';"
        )
        self.wait_until(notice.is_displayed, "no leave notice")
        self.wait_announcement("You left the conference.")
        frame = self.driver.find_element(
            By.CSS_SELECTOR, "iframe.o_ewp_bbb_frame"
        )
        self.assertFalse(frame.is_displayed())
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "left",
        )
        rejoin = notice.find_element(By.CSS_SELECTOR, ".o_ewp_bbb_rejoin")
        self.wait_until(
            lambda: self.driver.switch_to.active_element == rejoin,
            "focus not on Join again",
        )
        rejoin.click()
        self.wait_until(
            lambda: frame.is_displayed() and not notice.is_displayed(),
            "frame not shown again",
        )
        self.assertEqual(self.driver.switch_to.active_element, frame)
        self.wait_until(
            lambda: self._frame_path() == CLIENT_PATH,
            "conference frame did not load the client again",
        )
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "running",
        )

    def test_tab_that_leaves_an_embedded_meeting_stays_out_of_it(self):
        """A join opened by "Open in a new tab" next to the frame leaves to
        bbb_left, the logoutURL of a join outside the frame: the tab lands
        on the room page, which keeps its frame empty and shows the notice
        of the leave, with the focus on "Join again". That button loads
        the frame, which reaches the client, and drops left=1 from the
        address."""
        _network, room = self._conference(running=True)
        self._login_portal(room)
        newtab = self.wait_for("a.o_ewp_bbb_newtab")
        left = self.js(
            "return document.querySelector('.o_ewp_bbb_left')"
            ".dataset.ewpBbbLeftPath;"
        )
        self.assertTrue(newtab.get_attribute("href").endswith("/bbb_join"))
        self.open(left + "?reason=left")
        self.assertEqual(self.path(), room)
        self.assertIn("left=1", self.driver.current_url)
        notice = self.wait_for(".o_ewp_bbb_left")
        self.wait_announcement("You left the conference.")
        rejoin = notice.find_element(By.CSS_SELECTOR, ".o_ewp_bbb_rejoin")
        # The chat frame takes the focus once loaded; the page gives it
        # back to "Join again".
        self._chat_loaded()
        self.wait_until(
            lambda: self.driver.switch_to.active_element == rejoin,
            "focus not on Join again",
        )
        frame = self.driver.find_element(
            By.CSS_SELECTOR, "iframe.o_ewp_bbb_frame"
        )
        self.assertFalse(frame.is_displayed())
        self.assertFalse(
            self.js("return arguments[0].hasAttribute('src');", frame)
        )
        self.assertNotEqual(self._frame_path(), CLIENT_PATH)
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "left",
        )
        rejoin.click()
        self.wait_until(
            lambda: frame.is_displayed() and not notice.is_displayed(),
            "frame not shown",
        )
        self.wait_until(
            lambda: self._frame_path() == CLIENT_PATH,
            "conference frame did not load the client",
        )
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "running",
        )
        self.assertNotIn("left=1", self.driver.current_url)
        self._assert_no_server_address()

    def test_running_meeting_on_another_site_opens_in_a_new_tab(self):
        """Display mode auto, the fake server on another site than the
        test server: the running meeting shows the new tab button and no
        frame, and nothing goes wrong on the page. Once the meeting ends,
        the page loads itself again with the waiting notice and says so."""
        network, room = self._conference(running=True, display="auto")
        self._login_portal(room)
        section = self.wait_for(".o_ewp_bbb", visible=False)
        self.assertEqual(section.get_attribute("data-ewp-bbb-state"), "button")
        self.assertFalse(self.find_all("iframe.o_ewp_bbb_frame"))
        self.assertFalse(self.find_all(".o_ewp_bbb_notice"))
        link = self.wait_for("a.o_ewp_bbb_join")
        self.assertEqual(link.get_attribute("target"), "_blank")
        self.assertIn("noopener", link.get_attribute("rel"))
        self.assertEqual(
            link.accessible_name,
            "Join the video conference (opens in a new tab)",
        )
        self.assertIn(
            "The video conference is live.",
            self.text(self.wait_for(".o_ewp_bbb_tab_live")),
        )
        self._chat_loaded()
        self.assertNotIn(
            "does not answer",
            self.js(
                "return document.getElementById('o_ewp_announcer')"
                ".textContent;"
            ),
        )
        self._assert_no_server_address()
        with self.server_paused():
            network.running = False
        self.js("window.ewpTestOldPage = true;" + JS_VISIBLE_AGAIN)
        self.wait_js(
            "!window.ewpTestOldPage && document.readyState === 'complete'"
            " && document.body.dataset.ewpMotion",
            "the page did not load again",
        )
        self.assertEqual(
            self.js(
                "return document.querySelector('.o_ewp_bbb')"
                ".dataset.ewpBbbState;"
            ),
            "waiting",
        )
        self.wait_announcement("The conference has ended.")

    def test_text_only_mode_follows_the_user_to_a_new_browser(self):
        """The text-only toggle loads the page again without the plan
        image, says so with the focus back on the toggle, and is kept on
        the user: a new browser session opens in text-only mode."""
        self._login_portal()
        toggle = self.wait_for("#o_ewp_text_only_toggle")
        self.assertEqual(toggle.get_attribute("aria-pressed"), "false")
        self.js("window.ewpTestOldPage = true;")
        toggle.click()
        self.wait_js(
            "!window.ewpTestOldPage && document.body"
            " && document.body.classList.contains('o_ewp_text_only')",
            "text-only page not loaded",
        )
        self.wait_page_ready()
        self.wait_announcement("Text-only mode is on.")
        self.assertEqual(self.active_element()["id"], "o_ewp_text_only_toggle")
        self.assertFalse(self.find_all("img.o_ewp_plan_image"))
        self.assertFalse(self.find_all("#o_ewp_motion"))
        self.assertEqual(self.text(self.wait_for("#o_ewp_h_plan")), "Rooms")
        with self.server_paused():
            self.assertTrue(self.portal_user.ewp_text_only)
        self.restart_browser()
        self._login_portal()
        self.assertTrue(
            self.js(
                "return document.body.classList.contains('o_ewp_text_only');"
            )
        )
        self.assertEqual(
            self.wait_for("#o_ewp_text_only_toggle").get_attribute(
                "aria-pressed"
            ),
            "true",
        )
        self.assertEqual(
            self.js("return document.body.dataset.ewpMotion;"), "paused"
        )

    def test_pause_toggle_stops_every_animation(self):
        """The animation mode "Off" leaves no animation in the document
        and pauses the SVG animations; "Follow the device" starts them
        again. The choice is kept on the user."""
        self._login_portal()
        self.js(JS_ADD_ANIMATION)
        self.assertIn("ewp-test-spin", self.animations(running_only=True))
        toggle = self.wait_for("#o_ewp_motion_choice_off")
        toggle.click()
        self.wait_js(
            "document.body.dataset.ewpMotion === 'paused'",
            "animations not paused",
        )
        self.wait_announcement("Animations are paused.")
        self.assertEqual(toggle.get_attribute("aria-pressed"), "true")
        self.assertEqual(self.animations(), [])
        self.assertTrue(
            self.js(
                "return [...document.querySelectorAll('svg')].every("
                "(svg) => !svg.animationsPaused || svg.animationsPaused());"
            )
        )
        with self.server_paused():
            self.assertEqual(self.portal_user.ewp_motion, "off")
        auto = self.wait_for("#o_ewp_motion_choice_auto")
        auto.click()
        self.wait_js(
            "document.body.dataset.ewpMotion === 'running'",
            "animations not started again",
        )
        self.wait_announcement(
            "Animations follow the device: they are playing."
        )
        self.assertEqual(toggle.get_attribute("aria-pressed"), "false")
        self.assertEqual(auto.get_attribute("aria-pressed"), "true")
        self.assertIn("ewp-test-spin", self.animations(running_only=True))

    def test_reduced_motion_setting_stops_every_animation(self):
        """With the system setting "reduce motion", the page starts
        without animation and without storing a preference; on Chromium,
        where the setting can change on an open page, the animations start
        once it is turned off."""
        self.emulate_media(reduced_motion="reduce")
        self._login_portal()
        self.js(JS_ADD_ANIMATION)
        self.assertEqual(
            self.js("return document.body.dataset.ewpMotion;"), "paused"
        )
        self.assertEqual(self.animations(), [])
        self.assertEqual(
            self.wait_for("#o_ewp_motion_choice_auto").get_attribute(
                "aria-pressed"
            ),
            "true",
        )
        if self.browser_name != "chromium":
            return
        self.js(JS_RECORD_EVENTS, "ewp:motion")
        self.emulate_media(reduced_motion="no-preference")
        self.wait_js(
            "document.body.dataset.ewpMotion === 'running'",
            "animations not started with the setting off",
        )
        self.assertIn("ewp-test-spin", self.animations(running_only=True))
        self.assertEqual(
            self.js("return window.ewpTestEvents['ewp:motion'];"),
            [{"paused": False, "mode": "auto", "initial": False}],
        )

    def test_skip_links_move_the_focus(self):
        """The first Tab reaches "Skip to main content", shown on focus,
        which moves the focus to main; the second link moves it to the
        text-only toggle."""
        self._login_portal()
        self.tab()
        first = self.active_element()
        self.assertIn("o_ewp_skip", first["className"])
        self.assertEqual(first["text"], "Skip to main content")
        self.assertTrue(
            self.js(
                "const box = document.activeElement.getBoundingClientRect();"
                "return box.width > 1 && box.height > 1 && box.top >= 0;"
            ),
            "skip link not shown on focus",
        )
        self.press(Keys.ENTER)
        self.wait_until(
            lambda: self.active_element()["id"] == "o_ewp_main",
            "focus not on main",
        )
        self.open(self.home)
        self.tab(2)
        self.assertEqual(
            self.active_element()["text"], "Display options: text-only mode"
        )
        self.press(Keys.ENTER)
        self.wait_until(
            lambda: self.active_element()["id"] == "o_ewp_text_only_toggle",
            "focus not on the text-only toggle",
        )

    def test_keyboard_only_path_to_a_room_and_back(self):
        """With Tab and Enter only: from the home page to a room of the
        list, whose area on the plan lights up, the plan areas never
        taking the focus; then back to the plan."""
        self._login_portal()
        seen = []
        for _index in range(80):
            self.tab()
            active = self.active_element()
            seen.append(active)
            if "o_ewp_room_link" in active["className"] and (
                "Sigma Lab" in active["text"]
            ):
                break
        else:
            self.fail("Sigma Lab never reached with Tab: %s" % seen)
        self.assertFalse(
            [a for a in seen if "o_ewp_hotspot" in a["className"]],
            "a plan area took the focus",
        )
        self.assertTrue(
            self.js(
                "const el = document.activeElement;"
                "const style = getComputedStyle(el);"
                "return style.outlineStyle !== 'none'"
                " && parseFloat(style.outlineWidth) >= 2;"
            ),
            "no focus ring on the room link",
        )
        area = self.driver.find_element(
            By.CSS_SELECTOR,
            ".o_ewp_hotspot[data-ewp-room-id='%s']" % self.room_lab.id,
        )
        self.assertIn("o_ewp_hotspot_active", area.get_attribute("class"))
        self.press(Keys.ENTER)
        self.wait_until(
            lambda: self.path().endswith("/room/%s" % self.room_lab.id),
            "Enter did not open the room",
        )
        self.wait_page_ready()
        self._chat_loaded()
        # The chat composer takes the focus as it loads: the walk starts
        # again from the first skip link, where a fresh page starts.
        self.js("document.querySelector('a.o_ewp_skip').focus();")
        for _index in range(20):
            self.tab()
            if "o_ewp_back" in self.active_element()["className"]:
                break
        else:
            self.fail("Back to the plan never reached with Tab")
        self.press(Keys.ENTER)
        self.wait_until(lambda: self.path() == self.home, "not back home")
        self.wait_page_ready()
