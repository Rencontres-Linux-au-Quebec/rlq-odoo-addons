# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Selenium tests of the Tux of the theme: the cameo actors that come in,
play an action and leave, the animations of each action, the poses of the
page Tux for the conference and the raffle, and the motion settings that
stop them. They run in a real browser on the records of
WebappSeleniumCase (event_webapp_plan), with the schedule of the cameo
engine shortened through window.ewpCameo.configure() and the ewp:cameo
events recorded as in the tests of the engine.

An animation counts when the browser lists it running in
getAnimations() of the cameo or of the page Tux: the class of a pose is
not enough, its keyframes must play. Every name below is invented for the
tests."""

import time

from odoo.addons.event_webapp_plan.tests.selenium_common import (
    DESKTOP,
    PHONE,
    By,
)
from odoo.addons.event_webapp_plan.tests.test_selenium_cameo import (
    JS_EVENTS_ONLY,
    JS_FAST,
    JS_LONG,
    JS_RECORD_CAMEO,
)
from odoo.addons.event_webapp_plan.tests.test_selenium_webapp import (
    JS_VISIBLE_AGAIN,
    WebappSeleniumCase,
)
from odoo.tests import tagged

IDLE_ACTIONS = {"coffee", "code", "wave", "peek", "walk"}
# Keyframes that each cameo action must play, and the pose of its Tux.
ACTION_KEYFRAMES = {
    "coffee": ("coffee", {"rlq-sip-mug", "rlq-sip-face", "rlq-tux-steam"}),
    "code": ("code", {"rlq-type-left", "rlq-type-right", "rlq-glyph"}),
    "speak": ("speak", {"rlq-talk", "rlq-voice", "rlq-dot"}),
    "walk": ("walk", {"rlq-pace", "rlq-waddle", "rlq-step"}),
    "peek": ("peek", {"rlq-peek", "rlq-look"}),
    "wave": ("wave", {"rlq-wave"}),
    "celebrate": ("celebrate", {"rlq-jump", "rlq-confetti"}),
    "sleep": ("sleeping", {"rlq-zzz", "rlq-sleep"}),
}

# Names of the animations running in `arguments[0]` and its subtree.
JS_RUNNING = """
const el = arguments[0];
return el ? el.getAnimations({subtree: true})
    .filter((a) => a.playState === "running")
    .map((a) => a.animationName || a.transitionProperty || "?") : [];
"""

PAGE_TUX = "svg.o_rlq_tux:not(.o_rlq_tux_cameo)"


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumTux(WebappSeleniumCase):
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_motion(self, mode, text_only=False):
        with self.server_paused():
            self.portal_user.write(
                {"ewp_motion": mode, "ewp_text_only": text_only}
            )

    def _state(self):
        return self.js("return window.ewpCameo.state();")

    def _history_enter(self, message, **match):
        def found():
            for event in self._state()["history"]:
                if event["phase"] == "enter" and all(
                    event.get(k) == v for k, v in match.items()
                ):
                    return event
            return None

        return self.wait_until(found, message, timeout=15)

    def _running(self, element):
        return set(self.js(JS_RUNNING, element))

    def _page_tux(self):
        return self.wait_for(PAGE_TUX, "no vector Tux on the page", False)

    def _wait_pose(self, pose, message=None):
        self.wait_until(
            lambda: self._page_tux().get_attribute("data-rlq-tux") == pose,
            message or "page Tux never took the pose %r" % pose,
        )

    def _play(self, action):
        """Play `action` now (retried until a free spot takes it) and
        return the element of its cameo."""
        self.wait_until(
            lambda: self.js(
                "return window.ewpCameo.play(arguments[0]);", action
            ),
            "no spot for the %s cameo" % action,
        )
        return self.wait_for(
            ".o_ewp_cameo.o_ewp_cameo_do_%s" % action,
            "%s cameo missing" % action,
            visible=False,
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_tux_actors_come_in_play_and_leave(self):
        """The theme replaces the neutral actor by its two Tux actors, at
        its own sizes; with a short schedule a Tux cameo of the idle mix
        enters, drawn from the inert copy of the vector Tux, and leaves."""
        self._login_portal()
        state = self._state()
        self.assertEqual(
            set(state["actors"]),
            {"ewp-neutral", "rlq-tux", "rlq-tux-moments"},
        )
        self.assertEqual(
            (state["options"]["size"], state["options"]["sizePhone"]),
            (88, 60),
        )
        self.js(JS_RECORD_CAMEO + JS_FAST)
        entered = self.wait_until(
            lambda: next(
                (
                    e
                    for e in self.js("return window.ewpTestCameo;")
                    if e["phase"] == "enter"
                ),
                None,
            ),
            "no cameo entered",
        )
        self.assertEqual(entered["actor"], "rlq-tux")
        self.assertIn(entered["action"], IDLE_ACTIONS)
        self.assertEqual(entered["rect"]["width"], 88)
        drawing = self.js(
            "const layer = document.querySelector('.o_ewp_cameo_layer');"
            "const svg = layer.querySelector("
            "'.o_rlq_cameo_stage > svg.o_rlq_tux_cameo');"
            "return svg && {hidden: layer.getAttribute('aria-hidden'),"
            " svgHidden: svg.getAttribute('aria-hidden'),"
            " focusable: svg.getAttribute('focusable'),"
            " ids: layer.querySelectorAll('[id]').length,"
            " text: layer.textContent.trim()};"
        )
        self.assertEqual(
            drawing,
            {
                "hidden": "true",
                "svgHidden": "true",
                "focusable": "false",
                "ids": 0,
                "text": "",
            },
        )
        self.wait_until(
            lambda: any(
                e["phase"] == "exit" and e["reason"] == "done"
                for e in self.js("return window.ewpTestCameo;")
            ),
            "the Tux cameo never left",
        )

    def test_each_action_plays_its_animations_under_on(self):
        """With the mode "On", even on a device that asks for less
        motion, each action gets its class, the pose of its Tux and its
        own keyframes running: coffee, code, speak, walk, peek, wave,
        celebrate and sleep."""
        self._set_motion("on")
        self.emulate_media(reduced_motion="reduce")
        self._login_portal()
        self.js(JS_LONG)
        for action, (pose, keyframes) in ACTION_KEYFRAMES.items():
            with self.subTest(action=action):
                cameo = self._play(action)
                stage = cameo.find_element(
                    By.CSS_SELECTOR, ".o_rlq_cameo_stage"
                )
                self.assertIn(
                    "o_rlq_cameo_%s" % action, stage.get_attribute("class")
                )
                tux = stage.find_element(By.CSS_SELECTOR, "svg")
                self.assertEqual(tux.get_attribute("data-rlq-tux"), pose)
                self.wait_until(
                    lambda cameo=cameo, keyframes=keyframes: keyframes
                    <= self._running(cameo),
                    "%s: %s not all running (running: %s)"
                    % (action, sorted(keyframes), self._running(cameo)),
                    timeout=5,
                )

    def test_off_and_text_only_play_no_tux(self):
        """Under "Off" no Tux cameo plays and neither the page Tux nor
        anything else moves; in text-only mode there is no drawing, no
        Tux actor and no cameo."""
        self._set_motion("off")
        self._login_portal()
        self.js(JS_RECORD_CAMEO + JS_FAST)
        self.assertFalse(self.js("return window.ewpCameo.play('code');"))
        time.sleep(1.2)
        self.assertEqual(self.js("return window.ewpTestCameo;"), [])
        self.assertFalse(self.find_all(".o_rlq_cameo_stage"))
        self.assertEqual(self._running(self._page_tux()), set())
        self.assertEqual(self.animations(), [])
        self._set_motion("on", text_only=True)
        self.open(self.home)
        self.assertFalse(self.find_all("template.o_rlq_tux_source"))
        self.assertFalse(self.find_all("svg.o_rlq_tux"))
        self.assertEqual(self._state()["actors"], ["ewp-neutral"])
        self.js(JS_RECORD_CAMEO + JS_FAST)
        self.assertFalse(self.js("return window.ewpCameo.play('wave');"))
        time.sleep(1.2)
        self.assertEqual(self.js("return window.ewpTestCameo;"), [])
        self.assertEqual(self.animations(), [])

    def test_room_tux_speaks_drinks_coffee_and_waves(self):
        """On the room page the bar Tux drinks a coffee while the
        conference waits; once it runs, Tux speaks into the microphone
        (beak and sound waves moving) and a Tux cameo speaks near the
        conference; leaving it, Tux waves."""
        _network, waiting_room = self._conference(running=False)
        self._login_portal(waiting_room)
        self._wait_pose("coffee")
        self.wait_until(
            lambda: "rlq-sip-mug" in self._running(self._page_tux()),
            "the waiting Tux does not drink",
        )
        _network, room = self._conference(running=True)
        self.open(room)
        self._wait_pose("speak")
        self.wait_until(
            lambda: {"rlq-talk", "rlq-voice"}
            <= self._running(self._page_tux()),
            "the bar Tux does not speak",
        )
        self._history_enter(
            "no Tux cameo for the conference",
            trigger="bbb",
            action="speak",
            actor="rlq-tux-moments",
        )
        self.js(
            "const frame = document.querySelector('iframe.o_ewp_bbb_frame');"
            "const left = document.querySelector('.o_ewp_bbb_left')"
            ".dataset.ewpBbbLeftPath;"
            "frame.contentWindow.location.href = left"
            " + '?frame=1&reason=left';"
        )
        self.wait_js(
            "document.querySelector('.o_ewp_bbb').dataset.ewpBbbState"
            " === 'left'",
            "no leave notice",
        )
        self._wait_pose("wave", "the bar Tux does not wave on leaving")
        self.assertIn("rlq-wave", self._running(self._page_tux()))

    def test_raffle_draw_makes_tux_celebrate(self):
        """A winner drawn on the server: the Tux of the raffle card
        celebrates, and a celebrating Tux cameo enters near the card."""
        self._login_portal()
        self.js(JS_RECORD_CAMEO + JS_EVENTS_ONLY)
        with self.server_paused():
            draw = self.raffle.draw_ids.filtered(lambda d: d.sequence == 2)
            draw.winner_name = "Grace Tuxwinner"
        self.js(JS_VISIBLE_AGAIN)
        self._wait_pose("celebrate")
        self.assertIn("rlq-jump", self._running(self._page_tux()))
        entered = self._history_enter(
            "no Tux cameo for the raffle", trigger="raffle"
        )
        self.assertEqual(
            (entered["actor"], entered["action"]),
            ("rlq-tux-moments", "celebrate"),
        )

    def test_tux_cameos_never_cover_a_control_or_a_text(self):
        """On a phone (60 px Tux) and on a wide screen (88 px), every Tux
        cameo keeps clear of the links, buttons, fields and texts, and of
        the words of the ribbon and of the ornament, which are hidden from
        assistive technologies but shown."""
        self._login_portal()
        for (width, height), size in ((PHONE, 60), (DESKTOP, 88)):
            with self.subTest(width=width):
                self.set_viewport(width, height)
                self.open(self.home)
                self.js(JS_RECORD_CAMEO + JS_EVENTS_ONLY)
                entered = 0
                for action in sorted(IDLE_ACTIONS) * 5:
                    entered += bool(
                        self.js(
                            "return window.ewpCameo.play(arguments[0]);",
                            action,
                        )
                    )
                    time.sleep(0.05)
                self.assertGreaterEqual(
                    entered, 3, "too few free spots at %s px" % width
                )
                rects = [
                    e["rect"]
                    for e in self.js("return window.ewpTestCameo;")
                    if e["phase"] == "enter"
                ]
                self.assertEqual({r["width"] for r in rects}, {size})
                self.assertEqual(self.js("return window.ewpTestOverlaps;"), [])
                covered = self.js(
                    "const boxes = [...document.querySelectorAll("
                    "'[data-ewp-cameo-avoid]')]"
                    ".map((el) => el.getBoundingClientRect())"
                    ".filter((b) => b.width > 0 && b.height > 0);"
                    "return arguments[0].filter((r) => boxes.some((b) =>"
                    " r.left < b.right && r.left + r.width > b.left"
                    " && r.top < b.bottom && r.top + r.height > b.top));",
                    rects,
                )
                self.assertEqual(covered, [])
