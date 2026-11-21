# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Selenium tests of the animation mode and of the cameo engine
(webapp_cameo.js), on the records of WebappSeleniumCase.

The tests shorten the schedule of the engine through
window.ewpCameo.configure() (JS_FAST: a cameo every 150 to 300 ms, each
under a second) and read what it did from the ewp:cameo events, recorded
by JS_RECORD_CAMEO, or from window.ewpCameo.state().history, which also
holds the events sent before the test could listen. Every check of a
cameo box compares it with the boxes the browser gives for the controls
and the shown texts of the page (aria-hidden ones included) at the moment
the cameo enters. The elements that the tests add to a page carry an
ewp_test_ class and invented texts."""

import time
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from .selenium_common import DESKTOP, PHONE
from .test_selenium_webapp import JS_VISIBLE_AGAIN, WebappSeleniumCase

JS_FAST = """
window.ewpCameo.configure({
    minDelay: 150, maxDelay: 300, enterMs: 100, actionMs: [300, 400],
    exitMs: 100, eventDelay: 50,
});
"""

# Only the cameos of page events: the schedule waits a minute.
JS_EVENTS_ONLY = """
window.ewpCameo.configure({
    minDelay: 60000, maxDelay: 60000, enterMs: 100, actionMs: [300, 400],
    exitMs: 100, eventDelay: 50,
});
"""

# Cameos that stay on screen until the next one replaces them.
JS_LONG = """
window.ewpCameo.configure({
    minDelay: 60000, maxDelay: 60000, enterMs: 100, actionMs: [20000, 20000],
    exitMs: 100, eventDelay: 50,
});
"""

# Keeps the ewp:cameo details in window.ewpTestCameo and, on each enter,
# the controls and texts its box covers in window.ewpTestOverlaps.
# window.ewpTestCovered(rect) lists what `rect` covers now: a text counts
# when it is shown, even under aria-hidden.
JS_RECORD_CAMEO = """
window.ewpTestCameo = [];
window.ewpTestOverlaps = [];
const CONTROLS = "a[href], button, input, select, textarea, iframe, summary, label, "
    + "[tabindex]:not([tabindex='-1'])";
const hits = (r, b) => r.left < b.right && r.left + r.width > b.left
    && r.top < b.bottom && r.top + r.height > b.top;
window.ewpTestCovered = (rect) => {
    const found = [];
    for (const el of document.querySelectorAll(CONTROLS)) {
        if (el.closest(".o_ewp_cameo_layer")) {
            continue;
        }
        const box = el.getBoundingClientRect();
        if (box.width > 0 && box.height > 0 && hits(rect, box)) {
            found.push(el.outerHTML.slice(0, 100));
        }
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const range = document.createRange();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement;
        if (!node.nodeValue.trim() || !parent
            || parent.closest(".o_ewp_cameo_layer, script, style, template")) {
            continue;
        }
        range.selectNodeContents(node);
        for (const box of range.getClientRects()) {
            if (box.width > 1 && box.height > 1 && hits(rect, box)) {
                found.push("text: " + node.nodeValue.trim().slice(0, 60));
            }
        }
    }
    return found;
};
document.addEventListener("ewp:cameo", (ev) => {
    const detail = ev.detail;
    window.ewpTestCameo.push(detail);
    if (detail.phase === "enter") {
        for (const what of window.ewpTestCovered(detail.rect)) {
            window.ewpTestOverlaps.push(`${detail.rect.left},${detail.rect.top}: ${what}`);
        }
    }
});
"""

# Room to scroll by 240 px at least: a block without text at the end of
# the body when the page is too short.
JS_ROOM_TO_SCROLL = """
const root = document.documentElement;
if (root.scrollHeight < window.innerHeight + 300) {
    const room = document.createElement("div");
    room.className = "ewp_test_room";
    room.style.height = "600px";
    document.body.appendChild(room);
}
"""

# A button hidden by a style rule, placed over the box arguments[0]; the
# attribute data-ewp-test-show on main shows it, as a conference that
# starts shows its Join button by an attribute.
JS_HIDDEN_BUTTON = """
const rect = arguments[0];
const style = document.createElement("style");
style.textContent = ".ewp_test_probe { display: none; }"
    + " main[data-ewp-test-show] .ewp_test_probe { display: block; }";
document.head.appendChild(style);
const probe = document.createElement("button");
probe.type = "button";
probe.className = "ewp_test_probe";
probe.textContent = "Zeta join";
probe.style.cssText = `position: fixed; left: ${rect.left}px;`
    + ` top: ${rect.top}px; width: ${rect.width}px; height: ${rect.height}px;`;
document.querySelector("main").appendChild(probe);
"""

# An empty block placed over the box arguments[0]; JS_SWAP_BLOCK then
# fills it by innerHTML, as the live refresh swaps the raffle block.
JS_EMPTY_BLOCK = """
const rect = arguments[0];
const block = document.createElement("div");
block.className = "ewp_test_block";
block.style.cssText = `position: fixed; left: ${rect.left}px;`
    + ` top: ${rect.top}px; width: ${rect.width}px;`;
document.querySelector("main").appendChild(block);
"""
JS_SWAP_BLOCK = """
document.querySelector(".ewp_test_block").innerHTML =
    "<p style='margin: 0'>Winner: Zeta Swapline</p>";
"""

# A text hidden from assistive technologies but shown over the whole
# window, in lines that touch.
JS_ARIA_HIDDEN_WALL = """
const wall = document.createElement("div");
wall.className = "ewp_test_wall";
wall.setAttribute("aria-hidden", "true");
wall.style.cssText = "position: fixed; inset: 0; overflow: hidden;"
    + " font: 120px/1 monospace; word-break: break-all; z-index: 1;";
wall.textContent = "W".repeat(3000);
document.body.appendChild(wall);
"""


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumCameo(WebappSeleniumCase):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_motion(self, mode, text_only=False):
        with self.server_paused():
            self.portal_user.write(
                {"ewp_motion": mode, "ewp_text_only": text_only}
            )

    def _start_recording(self, script=JS_FAST):
        self.js(JS_RECORD_CAMEO + script)

    def _events(self, phase=None):
        return [
            event
            for event in self.js("return window.ewpTestCameo;")
            if phase is None or event["phase"] == phase
        ]

    def _wait_enter(self, message="no cameo entered", **match):
        """Detail of the first recorded enter whose keys equal `match`."""

        def found():
            for event in self._events("enter"):
                if all(event.get(k) == v for k, v in match.items()):
                    return event
            return None

        return self.wait_until(found, message, timeout=10)

    def _wait_history(self, message, **match):
        """Detail of the first enter of state().history matching."""

        def found():
            for event in self.js("return window.ewpCameo.state().history;"):
                if event["phase"] == "enter" and all(
                    event.get(k) == v for k, v in match.items()
                ):
                    return event
            return None

        return self.wait_until(found, message, timeout=15)

    def _cameo_state(self):
        return self.js("return window.ewpCameo.state();")

    def _present(self):
        return [
            c for c in self._cameo_state()["active"] if c["phase"] != "exit"
        ]

    def _assert_scroll_sends_covering_cameos_away(self):
        """Cameos that stay are on screen; a scroll of 240 px brings
        content under them: each one then covers nothing, or has left
        with the reason "overlap"."""
        self.js(JS_LONG)
        # The short cameos of the caller are gone.
        time.sleep(0.8)
        self.js("window.ewpTestCameo = [];")
        for _index in range(10):
            self.js("window.ewpCameo.play();")
        before = [c["rect"] for c in self._present()]
        self.assertTrue(before, "no cameo on screen before the scroll")
        self.js(JS_ROOM_TO_SCROLL)
        start = self.js("return window.scrollY;")
        self.js("window.scrollBy(0, 240);")
        self.assertGreater(self.js("return window.scrollY;"), start)
        self.wait_until(
            lambda: not self.js(
                "return arguments[0].flatMap("
                "(c) => window.ewpTestCovered(c.rect));",
                self._present(),
            ),
            "a cameo still covers a control or a text after the scroll",
        )
        overlap = [
            e["rect"] for e in self._events("exit") if e["reason"] == "overlap"
        ]
        still = [c["rect"] for c in self._present()]
        for rect in before:
            self.assertIn(rect, still + overlap)
        for rect in still:
            self.assertEqual(
                self.js("return window.ewpTestCovered(arguments[0]);", rect),
                [],
            )

    def _assert_quiet(self, seconds=1.2):
        """No cameo enters for `seconds` with the fast schedule, none is
        in the layer and the document runs no animation."""
        self.assertFalse(self.js("return window.ewpCameo.play('wave');"))
        time.sleep(seconds)
        self.assertEqual(self._events("enter"), [])
        self.assertFalse(self._cameo_state()["running"])
        self.assertFalse(self.find_all(".o_ewp_cameo"))
        self.assertEqual(self.animations(), [])

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_mode_on_plays_even_when_the_device_asks_for_less(self):
        """The mode "On" is an explicit choice: with prefers-reduced-motion
        emulated, the page runs its animations and a cameo enters, in an
        aria-hidden layer that takes no pointer, plays and leaves."""
        self._set_motion("on")
        self.emulate_media(reduced_motion="reduce")
        self._login_portal()
        self.assertTrue(
            self.js(
                "return matchMedia('(prefers-reduced-motion: reduce)')"
                ".matches;"
            )
        )
        self.assertEqual(
            self.js("return document.body.dataset.ewpMotion;"), "running"
        )
        self.assertIn(
            "o_ewp_motion_on", self.js("return document.body.className;")
        )
        self.assertFalse(
            self.wait_for("#o_ewp_motion_hint", visible=False).is_displayed()
        )
        self._start_recording()
        entered = self._wait_enter()
        # The neutral actor, or the actors of an installed theme.
        self.assertIn(entered["actor"], self._cameo_state()["actors"])
        self.assertEqual(entered["trigger"], "schedule")
        layer = self.js(
            "const layer = document.querySelector('.o_ewp_cameo_layer');"
            "return {hidden: layer.getAttribute('aria-hidden'),"
            " pointer: getComputedStyle(layer).pointerEvents,"
            " position: getComputedStyle(layer).position,"
            " focusable: layer.querySelectorAll('a, button, [tabindex]')"
            ".length};"
        )
        self.assertEqual(
            layer,
            {
                "hidden": "true",
                "pointer": "none",
                "position": "fixed",
                "focusable": 0,
            },
        )
        self.wait_until(
            lambda: any(
                name.startswith("ewp-cameo-")
                for name in self.animations(running_only=True)
            ),
            "no cameo animation running",
        )
        self.wait_until(
            lambda: [e for e in self._events("exit") if e["reason"] == "done"],
            "the cameo never left",
        )

    def test_default_schedule_first_cameo_comes_soon(self):
        """With the default delays, the first scheduled cameo enters 2 to
        3 s after the schedule starts, the next ones every 4 to 8 s, and
        two at most share a wide screen."""
        self._set_motion("on")
        self._login_portal()
        options = self._cameo_state()["options"]
        self.assertEqual(
            (
                options["firstMinDelay"],
                options["firstMaxDelay"],
                options["minDelay"],
                options["maxDelay"],
                options["maxActive"],
            ),
            (2000, 3000, 4000, 8000, 2),
        )
        # The schedule starts again on a tab shown again: the short first
        # delay applies from there.
        self.set_page_hidden(True)
        self.set_page_hidden(False)
        self._start_recording("")
        start = time.monotonic()
        entered = self.wait_until(
            lambda: next(iter(self._events("enter")), None),
            "no scheduled cameo after the tab showed again",
            timeout=8,
        )
        self.assertEqual(entered["trigger"], "schedule")
        self.assertLess(time.monotonic() - start, 4.5)

    def test_auto_with_reduced_motion_shows_the_hint_that_turns_them_on(self):
        """Under "Follow the device", a device that asks for less motion
        gets no animation and no cameo, and the hint says so; its button
        turns the animations on, keeps the choice and gives the focus to
        the pressed "On"."""
        self.emulate_media(reduced_motion="reduce")
        self._login_portal()
        self._start_recording()
        self.assertEqual(
            self.js("return document.body.dataset.ewpMotion;"), "paused"
        )
        self._assert_quiet()
        hint = self.wait_for("#o_ewp_motion_hint")
        self.assertIn(
            "Your device asks for less motion, animations are off.",
            self.text(hint),
        )
        self.wait_for("#o_ewp_motion_hint_on").click()
        self.wait_js(
            "document.body.dataset.ewpMotion === 'running'",
            "animations not turned on by the hint",
        )
        self.wait_announcement("Animations are playing.")
        self.wait_until(lambda: not hint.is_displayed(), "hint still shown")
        self.assertEqual(
            self.wait_for("#o_ewp_motion_choice_on").get_attribute(
                "aria-pressed"
            ),
            "true",
        )
        self.assertEqual(self.active_element()["id"], "o_ewp_motion_choice_on")
        with self.server_paused():
            self.assertEqual(self.portal_user.ewp_motion, "on")
        self._wait_enter()

    def test_off_and_text_only_play_no_cameo(self):
        """A cameo on screen leaves at once with "Off", which also leaves
        the document without animation; under "Off" and in text-only mode
        (even with "On" stored) no cameo plays."""
        self._login_portal()
        # Cameos that stay: one is on screen when "Off" is pressed.
        self._start_recording(JS_FAST.replace("[300, 400]", "[20000, 20000]"))
        entered = self._wait_enter()
        self.wait_for("#o_ewp_motion_choice_off").click()
        self.wait_js(
            "document.body.dataset.ewpMotion === 'paused'",
            "animations not paused",
        )
        self.assertEqual(self._cameo_state()["active"], [])
        self.assertEqual(self.animations(), [])
        stops = [e for e in self._events("exit") if e["reason"] == "stop"]
        self.assertIn(entered["rect"], [e["rect"] for e in stops])
        self.js("window.ewpTestCameo = [];")
        self._assert_quiet()
        self.open(self.home)
        self._start_recording()
        self._assert_quiet()
        self._set_motion("on", text_only=True)
        self.open(self.home)
        self.assertIn(
            "o_ewp_motion_off", self.js("return document.body.className;")
        )
        self._start_recording()
        self._assert_quiet()

    def test_cameo_never_covers_a_control_or_a_text(self):
        """On a phone and on a wide screen, every cameo that enters keeps
        clear of the links, buttons, fields, frames and texts of the page,
        also after a scroll; at most one plays on a phone, two on a wide
        screen."""
        self._login_portal()
        for width, height in (PHONE, DESKTOP):
            with self.subTest(width=width):
                self.set_viewport(width, height)
                self.open(self.home)
                self._start_recording(JS_EVENTS_ONLY)
                entered = 0
                for _index in range(30):
                    entered += bool(self.js("return window.ewpCameo.play();"))
                    active = self._cameo_state()["active"]
                    present = [c for c in active if c["phase"] != "exit"]
                    self.assertLessEqual(len(present), 1 if width < 640 else 2)
                    time.sleep(0.05)
                self.assertGreaterEqual(
                    entered, 3, "too few free spots at %s px" % width
                )
                self.assertEqual(self.js("return window.ewpTestOverlaps;"), [])
                self._assert_scroll_sends_covering_cameos_away()

    def test_page_events_play_their_action(self):
        """A raffle drawn plays "celebrate", a conference that runs
        "speak" and a day before its opening "coffee"."""
        self._login_portal()
        self._start_recording(JS_EVENTS_ONLY)
        with self.server_paused():
            draw = self.raffle.draw_ids.filtered(lambda d: d.sequence == 2)
            draw.winner_name = "Grace Cameowinner"
        self.js(JS_VISIBLE_AGAIN)
        entered = self._wait_enter("no cameo for the raffle", trigger="raffle")
        self.assertEqual(entered["action"], "celebrate")

        _network, room = self._conference(running=True)
        self.open(room)
        self._wait_history(
            "no cameo for the conference", trigger="bbb", action="speak"
        )

        later = fields.Datetime.now() + timedelta(days=2)
        # The room page and its chat are open: the test writes under the
        # lock of the shared cursor.
        with self.server_paused():
            day = self.env["event.webapp"].create(
                {
                    "name": "Cameo Future Day",
                    "date_start": later,
                    "date_end": later + timedelta(hours=8),
                    "room_ids": [Command.create({"name": "Kappa Room"})],
                }
            )
            day_id = day.id
        self.open("/webapp_event/%s" % day_id)
        self.assertEqual(
            self.js("return document.body.dataset.ewpDayState;"), "before"
        )
        self._wait_history(
            "no cameo before the opening", trigger="day", action="coffee"
        )

    def test_hidden_tab_pauses_the_cameos(self):
        """A hidden tab sends the cameos away and plays none; shown
        again, the schedule starts again."""
        self._login_portal()
        self._start_recording()
        self._wait_enter()
        self.set_page_hidden(True)
        self.wait_until(
            lambda: not self._cameo_state()["active"],
            "cameos still on screen in a hidden tab",
        )
        self.assertFalse(self._cameo_state()["running"])
        self.js("window.ewpTestCameo = [];")
        time.sleep(1.2)
        self.assertEqual(self._events("enter"), [])
        self.set_page_hidden(False)
        self._wait_enter("no cameo once the tab is shown again")

    def test_cameo_leaves_when_the_page_changes_under_it(self):
        """Without a scroll or a resize, a cameo leaves with the reason
        "overlap" once a change of the page brings a control or a text
        under it: an attribute that shows a button, then a block swapped
        by innerHTML, as the live refresh of the raffles does. A change
        that covers nothing keeps it."""
        self._login_portal()
        self.set_viewport(*DESKTOP)
        self.open(self.home)
        self._start_recording(JS_LONG)
        # An attribute shows a button over the cameo.
        self.assertTrue(self.js("return window.ewpCameo.play('wave');"))
        rect = self._wait_enter()["rect"]
        start = self.js("return window.scrollY;")
        self.js(JS_HIDDEN_BUTTON, rect)
        time.sleep(0.6)
        self.assertIn(rect, [c["rect"] for c in self._present()])
        self.js("document.querySelector('main').dataset.ewpTestShow = '1';")
        self.wait_until(
            lambda: [
                e
                for e in self._events("exit")
                if e["reason"] == "overlap" and e["rect"] == rect
            ],
            "the cameo stayed over the button shown by an attribute",
        )
        # A block swapped by innerHTML: a line of text over the cameo.
        self.js("window.ewpTestCameo = [];")
        self.assertTrue(self.js("return window.ewpCameo.play('code');"))
        rect = self._wait_enter()["rect"]
        self.js(JS_EMPTY_BLOCK, rect)
        time.sleep(0.6)
        self.assertIn(rect, [c["rect"] for c in self._present()])
        self.js(JS_SWAP_BLOCK)
        self.wait_until(
            lambda: [
                e
                for e in self._events("exit")
                if e["reason"] == "overlap" and e["rect"] == rect
            ],
            "the cameo stayed over the line of the swapped block",
        )
        self.assertEqual(self.js("return window.scrollY;"), start)

    def test_shown_aria_hidden_text_is_kept_clear(self):
        """A text hidden from assistive technologies but shown, such as
        the age of the raffle results, counts as a text: shown over the
        whole window it sends the cameo away and leaves no spot, and the
        cameos of a raffle never land on the age label."""
        self._login_portal()
        self.set_viewport(*DESKTOP)
        self.open(self.home)
        self._start_recording(JS_EVENTS_ONLY)
        self.assertTrue(self.js("return window.ewpCameo.play('wave');"))
        self.js(JS_ARIA_HIDDEN_WALL)
        self.wait_until(
            lambda: [
                e for e in self._events("exit") if e["reason"] == "overlap"
            ],
            "the cameo stayed under the aria-hidden text",
        )
        self.assertFalse(self.js("return window.ewpCameo.play('wave');"))
        self.js("document.querySelector('.ewp_test_wall').remove();")
        self.assertTrue(self.js("return window.ewpCameo.play('wave');"))
        label = self.js(
            "const el = document.querySelector('.o_ewp_updated');"
            "el.textContent = 'Updated 12 s ago';"
            "const b = el.getBoundingClientRect();"
            "return {left: b.left, top: b.top, right: b.right,"
            " bottom: b.bottom};"
        )
        self.assertGreater(label["right"], label["left"])
        self.js("window.ewpTestCameo = [];")
        for _index in range(20):
            self.js(
                "window.ewpCameo.play('celebrate',"
                " {near: '.o_ewp_raffles_card'});"
            )
            time.sleep(0.05)
        rects = [e["rect"] for e in self._events("enter")]
        self.assertTrue(rects, "no cameo near the raffle card")
        on_label = [
            r
            for r in rects
            if r["left"] < label["right"]
            and r["left"] + r["width"] > label["left"]
            and r["top"] < label["bottom"]
            and r["top"] + r["height"] > label["top"]
        ]
        self.assertEqual(on_label, [])
        self.assertEqual(self.js("return window.ewpTestOverlaps;"), [])

    def test_cameo_exit_plays_its_own_animation(self):
        """A cameo that leaves runs an exit animation of its own
        (ewp-cameo-*-out) for exitMs, from its place: it does not vanish
        at once."""
        self._login_portal()
        self._start_recording(
            "window.ewpCameo.configure({minDelay: 60000, maxDelay: 60000,"
            " enterMs: 100, actionMs: [500, 500], exitMs: 3000,"
            " eventDelay: 50});"
        )
        self.assertTrue(self.js("return window.ewpCameo.play('wave');"))
        self.wait_js(
            "document.querySelector('.o_ewp_cameo[data-ewp-phase=\"exit\"]')",
            "the cameo never started to leave",
        )
        exits = self.js(
            "const el = document.querySelector("
            "'.o_ewp_cameo[data-ewp-phase=\"exit\"]');"
            "const box = el.getBoundingClientRect();"
            "return {animations: el.getAnimations().map((a) =>"
            " [a.animationName, a.playState]),"
            " opacity: Number(getComputedStyle(el).opacity),"
            " inView: box.bottom > 0 && box.top < innerHeight"
            " && box.right > 0 && box.left < innerWidth};"
        )
        names = [
            name
            for name, state in exits["animations"]
            if name.startswith("ewp-cameo-")
            and name.endswith("-out")
            and state == "running"
        ]
        self.assertTrue(names, exits["animations"])
        self.assertTrue(exits["inView"])
        self.assertGreater(exits["opacity"], 0)

    def test_motion_choice_without_submitter(self):
        """On a browser whose submit event has no submitter, the pressed
        button still gives the choice: "Off" stores and applies "off",
        then "On" stores and applies "on"."""
        self._login_portal()
        self.js(
            "Object.defineProperty(SubmitEvent.prototype, 'submitter',"
            " {configurable: true, get() { return null; }});"
        )
        self.assertIsNone(
            self.js(
                "return new SubmitEvent('submit',"
                " {submitter: document.body}).submitter;"
            )
        )
        for choice, state in (("off", "paused"), ("on", "running")):
            self.wait_for("#o_ewp_motion_choice_%s" % choice).click()
            self.wait_js(
                "document.querySelector('#o_ewp_motion_choice_%s')"
                ".getAttribute('aria-pressed') === 'true'" % choice,
                "%s not pressed" % choice,
            )
            self.assertEqual(
                self.js("return document.body.dataset.ewpMotion;"), state
            )
            with self.server_paused():
                self.assertEqual(self.portal_user.ewp_motion, choice)
