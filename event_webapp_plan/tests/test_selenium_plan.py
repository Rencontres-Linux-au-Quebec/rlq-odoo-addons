# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Turned room areas in a real browser, through Selenium (see
selenium_common.py for the browser and the shared cursor).

The plan editor of the form is driven with real pointer moves (W3C
actions, so the browser fires the pointer events itself) and real clicks:
draw an area, turn it with the buttons, with Shift, through the angle field
and with the knob (a click on the knob changes nothing), move it, resize a
turned area by a corner, draw it again upright, resize it past the edges of
the image, straighten it, select rooms by a click on their turned shape and
inside the selected area, save, and read the record. The home page draws a
turned area turned, a click inside its turned shape, outside the box before
it turns, opens the room, and its label stays inside the turned shape
without taking the pointer. Every name below is invented for the tests."""

import math
import time
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .selenium_common import ActionChains, By, Keys, SeleniumCase
from .test_browser import _png_b64

FORM_PATH = "/odoo/action-event_webapp_plan.event_webapp_action/%s"

# Box of the selected area of the editor, read from its style: x, y,
# width, height in percent and the angle in degrees.
JS_SELECTED_BOX = """
const el = document.querySelector(".o_ewp_plan_room_selected");
if (!el) {
    return null;
}
return {
    x: parseFloat(el.style.left),
    y: parseFloat(el.style.top),
    width: parseFloat(el.style.width),
    height: parseFloat(el.style.height),
    rotation: parseFloat(el.style.getPropertyValue("--ewp-room-rotate")),
};
"""

# Centre, in viewport pixels, of the element that matches arguments[0].
JS_CENTRE = """
const el = document.querySelector(arguments[0]);
if (!el) {
    return null;
}
const rect = el.getBoundingClientRect();
return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
"""

# resizeBox() of the editor on a turned box whose handle "e" is dragged
# far beyond the right edge: the resized box, and the pixel positions of
# the anchor (handle "w") before and after.
JS_RESIZE_PAST_EDGE = """
const editor = odoo.loader.modules.get(
    "@event_webapp_plan/backend/room_plan_editor"
);
const size = {width: 600, height: 300};
const box = {x: 55, y: 40, width: 30, height: 20, rotation: 30};
const resized = editor.resizeBox(box, "e", {x: 2000, y: 400}, size);
return {
    box: resized,
    before: editor.handlePoint(box, "w", size),
    after: editor.handlePoint(resized, "w", size),
};
"""


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumTurnedAreas(SeleniumCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_rotation_portal",
            password="ewp_rotation_portal",
            groups="base.group_portal",
            name="Portal Rotation Test",
            lang="en_US",
        )
        cls.manager_user = new_test_user(
            cls.env,
            login="ewp_rotation_manager",
            password="ewp_rotation_manager",
            groups="base.group_user,"
            "event_webapp_plan.group_event_webapp_manager",
            name="Manager Rotation Test",
            lang="en_US",
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Rotation Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "plan_image": _png_b64(600, 300),
                "room_ids": [
                    Command.create(
                        {
                            "name": "Kappa Corridor",
                            # A long thin box across the middle, turned to
                            # stand upright.
                            "pos_x": 30,
                            "pos_y": 45,
                            "pos_width": 40,
                            "pos_height": 10,
                            "pos_rotation": 90,
                        }
                    ),
                    Command.create({"name": "Lambda Studio"}),
                    Command.create(
                        {
                            "name": "Mu Booth",
                            # A small upright box inside the turned
                            # corridor, below its centre.
                            "pos_x": 48,
                            "pos_y": 60,
                            "pos_width": 4,
                            "pos_height": 12,
                        }
                    ),
                ],
            }
        )
        cls.room_corridor = cls.day.room_ids.filtered(
            lambda r: r.name == "Kappa Corridor"
        )
        cls.room_studio = cls.day.room_ids.filtered(
            lambda r: r.name == "Lambda Studio"
        )
        cls.room_booth = cls.day.room_ids.filtered(
            lambda r: r.name == "Mu Booth"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def drag(self, points, shift=False):
        """Press at the first of `points` (viewport pixels), move through
        the others and release at the last, with Shift held when `shift`;
        the browser fires the pointer events itself."""
        chain = ActionChains(self.driver, duration=40)
        pointer = chain.w3c_actions.pointer_action
        keys = chain.w3c_actions.key_action
        if shift:
            keys.key_down(Keys.SHIFT)
            pointer.pause(0)
        first, *rest = [(round(x), round(y)) for x, y in points]
        pointer.move_to_location(*first)
        keys.pause(0)
        pointer.pointer_down()
        keys.pause(0)
        for x, y in rest:
            pointer.move_to_location(x, y)
            keys.pause(0)
        pointer.pointer_up()
        keys.pause(0)
        if shift:
            keys.key_up(Keys.SHIFT)
            pointer.pause(0)
        chain.perform()

    def centre(self, selector):
        point = self.js(JS_CENTRE, selector)
        self.assertTrue(point, "no element %s" % selector)
        return point["x"], point["y"]

    def box(self):
        return self.js(JS_SELECTED_BOX)

    def wait_box(self, check, message):
        """Box of the selected area once `check(box)` is true."""
        return self.wait_until(
            lambda: (lambda box: box if box and check(box) else None)(
                self.box()
            ),
            "%s (box %s)" % (message, self.box()),
        )

    def click_shift(self, selector):
        element = self.driver.find_element(By.CSS_SELECTOR, selector)
        ActionChains(self.driver).key_down(Keys.SHIFT).click(element).key_up(
            Keys.SHIFT
        ).perform()

    def selected_name(self):
        """Name of the selected room of the editor, None without one. The
        side list is read: the areas carry the ids of the web client, not
        the ids of the records."""
        return self.js(
            "const el = document.querySelector("
            "'.o_ewp_plan_rooms .list-group-item.active');"
            "return el ? el.textContent.trim() : null;"
        )

    def type_angle(self, text):
        """Replace the text of the angle field with `text`, then leave the
        field, which fires its change event. clear() is not used: it fires
        a change of its own, on an empty field."""
        field = self.driver.find_element(
            By.CSS_SELECTOR, ".o_ewp_plan_angle_input"
        )
        field.click()
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(text, Keys.TAB)

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_editor_draws_turns_moves_and_resizes_an_area(self):
        self.login("ewp_rotation_manager")
        self.open(FORM_PATH % self.day.id, ready=False)
        self.wait_for(".o_notebook a[name='page_plan']").click()
        surface = self.wait_for(".o_ewp_plan_surface")
        self.js("arguments[0].scrollIntoView({block: 'center'});", surface)
        self.wait_js(
            "document.querySelector('.o_ewp_plan_surface img').complete",
            "plan image not loaded",
        )
        # The saved turned area is drawn turned, its label level.
        self.assertEqual(
            self.js(
                "const el = document.querySelector('.o_ewp_plan_room');"
                "return el.style.getPropertyValue('--ewp-room-rotate').trim();"
            ),
            "90deg",
        )
        button = [
            el
            for el in self.find_all(".o_ewp_plan_rooms .list-group-item")
            if "Lambda Studio" in el.text
        ][0]
        button.click()
        self.wait_for(".o_ewp_plan_surface.o_ewp_plan_drawing")
        self.assertTrue(
            self.driver.find_element(
                By.CSS_SELECTOR, ".o_ewp_plan_rotate_right"
            ).get_attribute("disabled"),
            "rotation offered for a room without area",
        )
        rect = self.js(
            "const r = arguments[0].getBoundingClientRect();"
            "return {left: r.left, top: r.top, width: r.width,"
            " height: r.height};",
            surface,
        )

        def at(fx, fy):
            return (
                rect["left"] + rect["width"] * fx,
                rect["top"] + rect["height"] * fy,
            )

        # Draw.
        self.drag([at(0.3, 0.3), at(0.45, 0.5), at(0.6, 0.7)])
        drawn = self.wait_box(
            lambda b: b["width"] > 20, "the drawn area is missing"
        )
        for key, expected in (
            ("x", 30),
            ("y", 30),
            ("width", 30),
            ("height", 40),
            ("rotation", 0),
        ):
            self.assertAlmostEqual(drawn[key], expected, delta=1, msg=key)
        self.wait_for(".o_ewp_plan_frame .o_ewp_plan_handle_ne")

        # Buttons: 15 degrees, 1 degree with Shift.
        self.driver.find_element(
            By.CSS_SELECTOR, ".o_ewp_plan_rotate_right"
        ).click()
        self.wait_box(lambda b: b["rotation"] == 15, "Rotate right")
        self.click_shift(".o_ewp_plan_rotate_right")
        self.wait_box(lambda b: b["rotation"] == 16, "Shift + Rotate right")
        self.click_shift(".o_ewp_plan_rotate_left")
        self.wait_box(lambda b: b["rotation"] == 15, "Shift + Rotate left")

        # Angle field: decimals kept, an angle beyond 180 normalised.
        self.type_angle("37.5")
        self.wait_box(lambda b: b["rotation"] == 37.5, "typed angle")
        # A click on the knob, without a move, writes nothing: 37.5 is
        # not a multiple of 15 and stays as it is.
        self.drag([self.centre(".o_ewp_plan_rotate")])
        time.sleep(0.5)
        self.assertEqual(self.box()["rotation"], 37.5, "knob click")
        self.type_angle("270")
        self.wait_box(lambda b: b["rotation"] == -90, "typed angle 270")
        self.assertEqual(
            self.driver.find_element(
                By.CSS_SELECTOR, ".o_ewp_plan_angle_input"
            ).get_attribute("value"),
            "-90",
        )

        # Knob: turned by about 49 degrees around the centre (-41, 3.5
        # degrees from both snap boundaries), it snaps to a multiple of 15.
        cx, cy = self.centre(".o_ewp_plan_move")
        kx, ky = self.centre(".o_ewp_plan_rotate")
        radius = math.hypot(kx - cx, ky - cy)
        start = math.atan2(ky - cy, kx - cx)
        path = [
            (
                cx + radius * math.cos(start + math.radians(a)),
                cy + radius * math.sin(start + math.radians(a)),
            )
            for a in (0, 15, 30, 45, 49)
        ]
        self.drag(path)
        turned = self.wait_box(
            lambda b: b["rotation"] != -90, "the knob did not turn the area"
        )
        self.assertEqual(turned["rotation"], -45)
        self.assertEqual(
            (turned["x"], turned["y"], turned["width"], turned["height"]),
            (drawn["x"], drawn["y"], drawn["width"], drawn["height"]),
        )

        # Move: a drag inside the area shifts it, size and angle kept.
        self.drag([(cx, cy), (cx + 20, cy + 10), (cx + 40, cy + 20)])
        moved = self.wait_box(
            lambda b: b["x"] != turned["x"], "the area did not move"
        )
        self.assertAlmostEqual(
            moved["x"] - turned["x"], 40 / rect["width"] * 100, delta=0.5
        )
        self.assertAlmostEqual(
            moved["y"] - turned["y"], 20 / rect["height"] * 100, delta=0.5
        )
        for key in ("width", "height", "rotation"):
            self.assertEqual(moved[key], turned[key], key)

        # Resize a turned area by a corner: the opposite corner stays put.
        sw_before = self.centre(".o_ewp_plan_handle_sw")
        nx, ny = self.centre(".o_ewp_plan_handle_ne")
        self.drag([(nx, ny), (nx + 15, ny - 5), (nx + 30, ny - 10)])
        resized = self.wait_box(
            lambda b: b["width"] != moved["width"], "the area did not resize"
        )
        self.assertEqual(resized["rotation"], -45)
        self.assertGreater(resized["width"], moved["width"])
        sw_after = self.centre(".o_ewp_plan_handle_sw")
        self.assertLess(
            math.hypot(sw_after[0] - sw_before[0], sw_after[1] - sw_before[1]),
            1,
            "the opposite corner moved: %s -> %s" % (sw_before, sw_after),
        )

        # A drag outside the turned area draws a new one, upright.
        start = at(0.03, 0.05)
        self.assertFalse(
            self.js(
                "const el = document.elementFromPoint(...arguments);"
                "return Boolean(el && el.closest('.o_ewp_plan_frame'));",
                *start,
            ),
            "the draw starts on the frame",
        )
        self.drag([start, at(0.1, 0.15), at(0.18, 0.25)])
        redrawn = self.wait_box(
            lambda b: b["x"] < 10, "the area was not drawn again"
        )
        self.assertEqual(redrawn["rotation"], 0)
        # The draft shows the same box until the web client renders the
        # saved one, with its frame.
        self.wait_for(".o_ewp_plan_frame .o_ewp_plan_handle_w")
        for key, expected in (("x", 3), ("y", 5), ("width", 15)):
            self.assertAlmostEqual(redrawn[key], expected, delta=1, msg=key)

        # A side handle dragged past the edge of the image stops the area
        # at that edge; the opposite side does not move.
        wx, wy = self.centre(".o_ewp_plan_handle_w")
        self.drag([(wx, wy), (rect["left"] - 20, wy), (rect["left"] - 40, wy)])
        widened = self.wait_box(lambda b: b["x"] == 0, "the w handle")
        self.assertAlmostEqual(
            widened["x"] + widened["width"],
            redrawn["x"] + redrawn["width"],
            delta=0.02,
        )
        self.assertEqual(
            (widened["y"], widened["height"]),
            (redrawn["y"], redrawn["height"]),
        )
        nx, ny = self.centre(".o_ewp_plan_handle_n")
        self.drag([(nx, ny), (nx, rect["top"] - 20), (nx, rect["top"] - 40)])
        heightened = self.wait_box(lambda b: b["y"] == 0, "the n handle")
        self.assertAlmostEqual(
            heightened["y"] + heightened["height"],
            redrawn["y"] + redrawn["height"],
            delta=0.02,
        )
        self.assertEqual(
            (heightened["x"], heightened["width"]),
            (widened["x"], widened["width"]),
        )
        # The same on a turned box, through the helper of the editor.
        past = self.js(JS_RESIZE_PAST_EDGE)
        self.assertLess(
            math.hypot(
                past["after"]["x"] - past["before"]["x"],
                past["after"]["y"] - past["before"]["y"],
            ),
            0.5,
            "the anchor of a turned box moved: %s" % past,
        )
        edges = (
            past["box"]["x"],
            past["box"]["y"],
            100 - past["box"]["x"] - past["box"]["width"],
            100 - past["box"]["y"] - past["box"]["height"],
        )
        self.assertGreaterEqual(min(edges), 0, past)
        self.assertLess(min(edges), 0.02, "no edge reached: %s" % (past,))

        # Rotate, straighten, then a last turn that the save must keep.
        self.driver.find_element(
            By.CSS_SELECTOR, ".o_ewp_plan_rotate_right"
        ).click()
        self.wait_box(lambda b: b["rotation"] == 15, "Rotate right")
        self.driver.find_element(
            By.CSS_SELECTOR, ".o_ewp_plan_straighten"
        ).click()
        self.wait_box(lambda b: b["rotation"] == 0, "Straighten")
        self.driver.find_element(
            By.CSS_SELECTOR, ".o_ewp_plan_rotate_left"
        ).click()
        final = self.wait_box(lambda b: b["rotation"] == -15, "Rotate left")

        # A click on the turned corridor, above its box before it turns,
        # selects it.
        self.drag([at(0.5, 0.25)])
        self.wait_until(
            lambda: self.selected_name() == "Kappa Corridor",
            "a click on the turned shape did not select the corridor",
        )
        # A click inside the selected corridor, on the booth drawn inside
        # it, selects the booth; a click there again selects the corridor
        # under it. None of these clicks moves anything.
        self.drag([at(0.5, 0.66)])
        self.wait_until(
            lambda: self.selected_name() == "Mu Booth",
            "a click inside the selected area did not select the booth",
        )
        self.drag([at(0.5, 0.66)])
        self.wait_until(
            lambda: self.selected_name() == "Kappa Corridor",
            "a click inside the booth did not select the corridor",
        )
        self.driver.find_element(
            By.CSS_SELECTOR, ".o_form_button_save"
        ).click()
        self.wait_js(
            "!document.querySelector('.o_form_status_indicator_buttons"
            ":not(.invisible) .o_form_button_save')",
            "the form was not saved",
        )
        with self.server_paused():
            studio = self.room_studio
            for field, key in (
                ("pos_x", "x"),
                ("pos_y", "y"),
                ("pos_width", "width"),
                ("pos_height", "height"),
                ("pos_rotation", "rotation"),
            ):
                self.assertAlmostEqual(
                    studio[field], final[key], places=2, msg=field
                )
            self.assertEqual(self.room_corridor.pos_rotation, 90)
            self.assertEqual(
                (
                    self.room_booth.pos_x,
                    self.room_booth.pos_y,
                    self.room_booth.pos_width,
                    self.room_booth.pos_height,
                    self.room_booth.pos_rotation,
                ),
                (48, 60, 4, 12, 0),
            )

    def test_home_page_draws_the_area_turned_and_clicks_inside_it(self):
        self.login(
            "ewp_rotation_portal", redirect="/webapp_event/%s" % self.day.id
        )
        self.wait_page_ready()
        selector = ".o_ewp_hotspot[data-ewp-room-id='%s']" % (
            self.room_corridor.id
        )
        area = self.wait_for(selector)
        self.js("arguments[0].scrollIntoView({block: 'center'});", area)
        matrix = self.js(
            "return getComputedStyle(arguments[0]).transform;", area
        )
        a, b = (float(v) for v in matrix[7:-1].split(",")[:2])
        self.assertAlmostEqual(math.degrees(math.atan2(b, a)), 90, places=1)
        # The number or the label stays level: its box is not turned.
        level = self.js(
            "const spot = arguments[0];"
            "const text = [...spot.children].find("
            " (el) => getComputedStyle(el).display !== 'none');"
            "const rect = text.getBoundingClientRect();"
            "return Math.abs(rect.width - text.offsetWidth) < 1"
            " && Math.abs(rect.height - text.offsetHeight) < 1;",
            area,
        )
        self.assertTrue(level, "the text of the area is turned")
        # Turned upright, the corridor is as wide on screen as its box is
        # high: its label fits that width and never takes the pointer, so
        # a point beside the turned shape, where a longer label would lie,
        # is not the corridor.
        label = self.js(
            "const spot = arguments[0];"
            "const label = spot.querySelector('.o_ewp_hotspot_label');"
            "const number = spot.querySelector('.o_ewp_hotspot_number');"
            "const rect = label.getBoundingClientRect();"
            "return {width: rect.width, short: spot.clientHeight,"
            " events: [getComputedStyle(label).pointerEvents,"
            " getComputedStyle(number).pointerEvents]};",
            area,
        )
        self.assertLessEqual(label["width"], label["short"] + 1, label)
        self.assertEqual(label["events"], ["none", "none"])
        # The box before it turns is wide and flat; turned, it stands
        # upright. A point above the centre is inside the turned shape
        # only, a point beside it inside the box before it turns only.
        geometry = self.js(
            "const plan = document.querySelector('.o_ewp_plan_image')"
            ".getBoundingClientRect();"
            "return {cx: plan.left + plan.width * 0.5,"
            " cy: plan.top + plan.height * 0.5,"
            " w: plan.width, h: plan.height};"
        )
        cx, cy = geometry["cx"], geometry["cy"]
        inside = (cx, cy - geometry["w"] * 0.12)
        beside = (cx + geometry["w"] * 0.15, cy)
        hit = (
            "const el = document.elementFromPoint(arguments[0], arguments[1]);"
            "const spot = el && el.closest('.o_ewp_hotspot');"
            "return spot ? spot.dataset.ewpRoomId : null;"
        )
        self.assertEqual(
            self.js(hit, *inside), str(self.room_corridor.id), "inside"
        )
        self.assertIsNone(self.js(hit, *beside), "beside")
        near = (cx + label["short"] * 0.9, cy)
        self.assertNotEqual(
            self.js(hit, *near), str(self.room_corridor.id), "near"
        )
        chain = ActionChains(self.driver)
        chain.w3c_actions.pointer_action.move_to_location(
            round(inside[0]), round(inside[1])
        )
        chain.w3c_actions.pointer_action.click()
        chain.perform()
        self.wait_until(
            lambda: self.path().endswith("/room/%s" % self.room_corridor.id),
            "a click inside the turned area did not open the room",
        )
