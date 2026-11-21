# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Accessibility of the /webapp_event pages: the display preferences route
(CSRF, own user only, portal users), the text-only mode, the skip links,
landmarks, headings, titles and language of every page, the shared live
region, the frame titles and the screen reader text of the room list.

The browser tests toggle the animations in a headless Chrome and, when the
environment variable EWP_AXE_JS names a copy of axe-core (axe.min.js), run
its WCAG 2.2 A and AA rules on the pages. axe-core is not shipped with the
module: without that variable the audit test skips itself.

Every name below is invented for the tests."""

import json
import os
from datetime import timedelta
from urllib.parse import urlsplit

from lxml import html as lxml_html
from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user

from ..models.res_users import migrate_reduce_motion
from .test_browser import (
    HOST_PAGE,
    JS_CHECK,
    JS_FRAME,
    JS_WAIT,
    emulated_media,
)
from .test_controllers import _png_b64

PREFS_URL = "/webapp_event/preferences"


@tagged("post_install", "-at_install")
class TestWebappAccessibility(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.env["event.webapp"].search([]).write({"active": False})
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_a11y_portal",
            password="ewp_a11y_portal",
            groups="base.group_portal",
            name="Portal Reader Test",
            lang="en_US",
        )
        cls.other_user = new_test_user(
            cls.env,
            login="ewp_a11y_other",
            password="ewp_a11y_other",
            groups="base.group_user",
            name="Other Reader Test",
            lang="en_US",
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Reader Test Talk",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
            }
        )
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Reader Test Raffle",
                "event_id": cls.event.id,
                "draw_ids": [
                    Command.create(
                        {
                            "sequence": 1,
                            "prize": "Reader Test Book",
                            "winner_name": "Ada Testreader",
                        }
                    ),
                    Command.create(
                        {"sequence": 2, "prize": "Reader Test Pen"}
                    ),
                ],
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Reader Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "announcement": "<p>Welcome, readers</p>",
                "plan_image": _png_b64(),
                "event_ids": [Command.set(cls.event.ids)],
                "raffle_ids": [Command.set(cls.raffle.ids)],
                "link_ids": [
                    Command.create(
                        {
                            "name": "Reader Test Schedule",
                            "url": "https://example.org/schedule",
                        }
                    )
                ],
                "room_ids": [
                    Command.create(
                        {
                            "name": "North Hall",
                            "description": "Ground floor",
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 20,
                            "pos_height": 30,
                        }
                    ),
                    # Turned: the audit covers a turned area, and the
                    # position words read its centre, which does not move.
                    Command.create(
                        {
                            "name": "Centre Lab",
                            "pos_x": 40,
                            "pos_y": 40,
                            "pos_width": 20,
                            "pos_height": 20,
                            "pos_rotation": 30,
                        }
                    ),
                    Command.create({"name": "Unplaced Room"}),
                ],
            }
        )
        cls.day_ended = cls.env["event.webapp"].create(
            {
                "name": "Reader Ended Day",
                "date_start": now - timedelta(days=3),
                "date_end": now - timedelta(days=3) + timedelta(hours=8),
            }
        )
        rooms = {room.name: room for room in cls.day.room_ids}
        cls.room_north = rooms["North Hall"]
        cls.room_centre = rooms["Centre Lab"]

    def _get(self, url, **kwargs):
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False, **kwargs)
        self.env.invalidate_all()
        return response

    def _post(self, data, headers=None):
        self.env.flush_all()
        response = self.url_open(
            PREFS_URL, data=data, headers=headers, allow_redirects=False
        )
        self.env.invalidate_all()
        return response

    def _page(self, url):
        response = self._get(url)
        self.assertEqual(response.status_code, 200, url)
        return response, lxml_html.fromstring(response.text)

    def _home(self):
        return "/webapp_event/%s" % self.day.id

    def _room(self, room, suffix=""):
        return "/webapp_event/%s/room/%s%s" % (self.day.id, room.id, suffix)

    def _csrf(self, url=None):
        """CSRF token of the display options form of a page."""
        page = self._page(url or self._home())[1]
        tokens = page.xpath(
            "//form[@data-ewp-pref='text_only']//input[@name='csrf_token']"
            "/@value"
        )
        self.assertEqual(len(tokens), 1)
        return tokens[0]

    def _add_mascot(self):
        self.env["ir.ui.view"].create(
            {
                "name": "Test theme mascot",
                "type": "qweb",
                "inherit_id": (
                    self.env.ref("event_webapp_plan.webapp_slot_mascot").id
                ),
                "arch": (
                    '<xpath expr="." position="inside">'
                    '<img class="test_mascot" src="/web/static/img/logo.png" '
                    'alt=""/></xpath>'
                ),
            }
        )

    # ------------------------------------------------------------------
    # Display preferences route
    # ------------------------------------------------------------------
    def test_preferences_need_a_csrf_token(self):
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        response = self._post({"text_only": "1"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.portal_user.ewp_text_only)

    def test_preferences_refuse_anonymous_visitors(self):
        """The route is auth="user": authentication runs before the CSRF
        check, so an anonymous post is sent to the login page (a route
        opened to the public user would answer 400 for the missing token
        instead), and no user is written, the public one included."""
        public = self.env.ref("base.public_user")
        self.authenticate(None, None)
        response = self._post({"text_only": "1"})
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(
            urlsplit(response.headers["Location"]).path, "/web/login"
        )
        for user in (self.portal_user, self.other_user, public):
            self.assertFalse(user.ewp_text_only, user.login)

    def test_portal_user_writes_own_preferences_only(self):
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        token = self._csrf()
        response = self._post(
            {
                "csrf_token": token,
                "text_only": "1",
                "motion": "off",
                # Ignored: the route writes on the current user only.
                "user_id": str(self.other_user.id),
                "id": str(self.other_user.id),
                "login": "ewp_a11y_changed",
                "redirect": self._room(self.room_north),
            }
        )
        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["Location"].endswith(self._room(self.room_north))
        )
        self.assertTrue(self.portal_user.ewp_text_only)
        self.assertEqual(self.portal_user.ewp_motion, "off")
        self.assertEqual(self.portal_user.login, "ewp_a11y_portal")
        self.assertFalse(self.other_user.ewp_text_only)
        self.assertEqual(self.other_user.ewp_motion, "auto")

        # A missing value is left as is; JSON for the page script.
        response = self._post(
            {"csrf_token": token, "motion": "on"},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.text), {"text_only": True, "motion": "on"}
        )
        self.assertTrue(self.portal_user.ewp_text_only)
        self.assertEqual(self.portal_user.ewp_motion, "on")
        # An unknown mode, or the old boolean parameter, changes nothing.
        for data in ({"motion": "fast"}, {"reduce_motion": "1"}):
            with self.subTest(data=data):
                response = self._post(
                    dict(data, csrf_token=token),
                    headers={"Accept": "application/json"},
                )
                self.assertEqual(json.loads(response.text)["motion"], "on")
        self.assertEqual(self.portal_user.ewp_motion, "on")

    def test_preferences_redirect_stays_in_the_web_app(self):
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        token = self._csrf()
        for target in (
            "https://example.org/webapp_event",
            "//example.org/webapp_event",
            "/\\example.org/webapp_event",
            "/web/login",
            "/webapp_eventx",
            "",
        ):
            with self.subTest(target=target):
                response = self._post(
                    {"csrf_token": token, "text_only": "0", "redirect": target}
                )
                self.assertEqual(response.status_code, 303)
                location = response.headers["Location"]
                self.assertTrue(
                    location.endswith("/webapp_event"), (target, location)
                )

    def test_preferences_are_self_writeable(self):
        """Through the ORM, a portal user writes the two fields on their
        own record, and nothing on another user's."""
        user = self.portal_user.with_user(self.portal_user)
        self.assertEqual(user.ewp_motion, "auto")
        user.write({"ewp_text_only": True, "ewp_motion": "on"})
        self.assertTrue(user.ewp_text_only)
        self.assertEqual(
            user.read(["ewp_text_only", "ewp_motion"])[0]["ewp_motion"], "on"
        )
        with self.assertRaises(ValueError):
            user.write({"ewp_motion": "fast"})
        other = self.other_user.with_user(self.portal_user)
        for values in ({"ewp_text_only": True}, {"ewp_motion": "off"}):
            with self.subTest(values=values):
                with self.assertRaises(AccessError):
                    other.write(values)
        self.assertFalse(self.other_user.ewp_text_only)
        self.assertEqual(self.other_user.ewp_motion, "auto")

    def test_reduce_motion_column_becomes_the_mode(self):
        """migrate_reduce_motion(), run before the models load by the
        update to 18.0.1.4.0: the boolean "pause animations" of the
        earlier versions gives "off" when true, "auto" when false; a mode
        already set stays; without the old column nothing changes."""
        cr = self.env.cr
        admin = self.env.ref("base.user_admin")
        self.env.flush_all()
        self.assertEqual(migrate_reduce_motion(cr), 0)
        cr.execute("ALTER TABLE res_users ADD COLUMN ewp_reduce_motion bool")
        cr.execute(
            "UPDATE res_users SET ewp_motion = NULL,"
            " ewp_reduce_motion = (id = %s) WHERE id IN %s",
            [self.portal_user.id, (self.portal_user.id, self.other_user.id)],
        )
        cr.execute(
            "UPDATE res_users SET ewp_motion = 'on', ewp_reduce_motion = true"
            " WHERE id = %s",
            [admin.id],
        )
        self.assertEqual(migrate_reduce_motion(cr), 2)
        self.env.invalidate_all()
        self.assertEqual(self.portal_user.ewp_motion, "off")
        self.assertEqual(self.other_user.ewp_motion, "auto")
        self.assertEqual(admin.ewp_motion, "on")
        self.assertEqual(migrate_reduce_motion(cr), 0)

    def test_preferences_of_other_users_stay_private(self):
        """A text-only preference says something about the sight of the
        person: no user reads it, nor searches on it, on another user's
        record, through the ORM or the JSON-RPC route of the web client.
        The Settings group keeps the access."""
        self.other_user.ewp_text_only = True
        self.env.flush_all()
        Users = self.env["res.users"].with_user(self.portal_user)
        other = self.other_user.with_user(self.portal_user)
        for fname, value in (("ewp_text_only", True), ("ewp_motion", "off")):
            with self.subTest(field=fname):
                with self.assertRaises(AccessError):
                    other.read([fname])
                with self.assertRaises(AccessError):
                    Users.search_read([(fname, "=", value)], ["name"])
        internal = self.env["res.users"].with_user(self.other_user)
        with self.assertRaises(AccessError):
            internal.search([("ewp_text_only", "=", True)])
        self.assertTrue(
            self.other_user.with_user(self.other_user).ewp_text_only
        )
        admin = self.env["res.users"].with_user(
            self.env.ref("base.user_admin")
        )
        self.assertIn(
            self.other_user, admin.search([("ewp_text_only", "=", True)])
        )

        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        response = self.url_open(
            "/web/dataset/call_kw/res.users/search_read",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "model": "res.users",
                        "method": "search_read",
                        "args": [[["ewp_text_only", "=", True]], ["name"]],
                        "kwargs": {},
                    },
                }
            ),
            headers={"Content-Type": "application/json"},
        )
        answer = response.json()
        self.assertNotIn("result", answer)
        self.assertEqual(
            answer["error"]["data"]["name"], "odoo.exceptions.AccessError"
        )
        self.assertNotIn("Other Reader Test", response.text)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    def test_every_page_has_skip_links_landmarks_and_one_h1(self):
        self._add_mascot()
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        cases = (
            (self._home(), "Home - Reader Test Day"),
            (self._room(self.room_north), "North Hall - Reader Test Day"),
            (
                self._room(self.room_north, "/bbb_left?frame=1"),
                "Conference left - North Hall - Reader Test Day",
            ),
            (
                "/webapp_event/%s" % self.day_ended.id,
                "Over - Reader Ended Day",
            ),
        )
        for url, title in cases:
            with self.subTest(url=url):
                page = self._page(url)[1]
                self.assertEqual(page.xpath("//title")[0].text, title)
                self.assertEqual(page.xpath("//html/@lang"), ["en-US"])
                self.assertEqual(len(page.xpath("//h1")), 1)
                mains = page.xpath("//main")
                self.assertEqual(len(mains), 1)
                self.assertEqual(mains[0].get("id"), "o_ewp_main")
                # The skip links come before any other link or button.
                first = page.xpath(
                    "(//body//a | //body//button | //body//iframe)[1]"
                )[0]
                self.assertEqual(first.get("href"), "#o_ewp_main")
                self.assertTrue(page.xpath("//a[@href='#o_ewp_prefs']"))
                self.assertTrue(page.xpath("//footer[@id='o_ewp_prefs']"))
                toggles = page.xpath(
                    "//footer[@id='o_ewp_prefs']//button[@aria-pressed]"
                )
                self.assertEqual(
                    [t.text_content().strip() for t in toggles],
                    ["Text-only mode", "Follow the device", "On", "Off"],
                )
                self.assertEqual(
                    [t.get("aria-pressed") for t in toggles],
                    ["false", "true", "false", "false"],
                )
                # The three animation buttons form one labelled group.
                group = page.xpath("//*[@id='o_ewp_motion']")[0]
                self.assertEqual(group.get("role"), "group")
                label = page.xpath(
                    "//*[@id='%s']" % group.get("aria-labelledby")
                )[0]
                self.assertEqual(label.text_content().strip(), "Animations")
                # One live region, the shared one.
                regions = page.xpath("//*[@aria-live or @role='status']")
                self.assertEqual(len(regions), 1)
                self.assertEqual(regions[0].get("id"), "o_ewp_announcer")
                self.assertEqual(regions[0].get("aria-live"), "polite")
                messages = json.loads(regions[0].get("data-ewp-messages"))
                self.assertIn("%(winner)s", messages["raffle_winner"])
                self.assertEqual(
                    messages["text_only_on"], "Text-only mode is on."
                )
                # Every frame has a title, every image an alt.
                for frame in page.xpath("//iframe"):
                    self.assertTrue(frame.get("title"))
                for img in page.xpath("//img"):
                    self.assertIsNotNone(img.get("alt"))
                self.assertTrue(page.xpath("//img[@class='test_mascot']"))

    def test_home_page_room_list_for_screen_readers(self):
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        page = self._page(self._home())[1]
        images = page.xpath("//img[contains(@class, 'o_ewp_plan_image')]")
        self.assertIn("listed after the plan", images[0].get("alt"))
        hotspots = page.xpath("//a[contains(@class, 'o_ewp_hotspot')]")
        self.assertEqual(len(hotspots), 2)
        for hotspot in hotspots:
            self.assertEqual(hotspot.get("aria-hidden"), "true")
            self.assertEqual(hotspot.get("tabindex"), "-1")
        positions = [
            el.text_content()
            for el in page.xpath(
                "//*[contains(@class, 'o_ewp_room_position')]"
            )
        ]
        self.assertEqual(
            positions,
            [
                "Area 1 on the plan, in the top left corner.",
                "Area 2 on the plan, in the centre.",
            ],
        )
        rooms = page.xpath("//ul[contains(@class, 'o_ewp_rooms')]")[0]
        self.assertEqual(rooms.get("role"), "list")
        self.assertEqual(len(rooms.xpath("./li/a")), 3)
        self.assertIn("Ground floor", rooms.xpath("./li/a")[0].text_content())
        # The day state is spelled out, and the raffles say how far they
        # are, with one list item per draw.
        self.assertIn(
            "State of the day:",
            page.xpath("//*[contains(@class, 'o_ewp_day_meta')]")[
                0
            ].text_content(),
        )
        self.assertEqual(
            page.xpath("//*[@class='o_ewp_raffle_progress']")[0].text,
            "1 drawn of 2",
        )
        draws = page.xpath("//ol[contains(@class, 'o_ewp_draws')]/li")
        self.assertEqual(len(draws), 2)
        self.assertIn("Winner:", draws[0].text_content())
        self.assertIn("To be drawn", draws[1].text_content())
        # A link that opens a new tab says so, with a text that the
        # text-only mode shows in place of the icon.
        link = page.xpath("//a[contains(@class, 'o_ewp_link')]")[0]
        self.assertEqual(
            link.xpath(".//span[contains(@class, 'o_ewp_external_text')]")[
                0
            ].text,
            "(opens in a new tab)",
        )

    def test_text_only_mode_renders_linear_text(self):
        self._add_mascot()
        self.portal_user.ewp_text_only = True
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        page = self._page(self._home())[1]
        body_class = page.xpath("//body/@class")[0].split()
        self.assertIn("o_ewp_text_only", body_class)
        self.assertIn("o_ewp_motion_paused", body_class)
        self.assertFalse(page.xpath("//img"))
        self.assertFalse(page.xpath("//*[contains(@class, 'o_ewp_hotspot')]"))
        self.assertFalse(page.xpath("//div[@class='o_ewp_plan']"))
        self.assertFalse(page.xpath("//span[@class='o_ewp_logo']"))
        self.assertFalse(
            page.xpath("//*[contains(@class, 'o_ewp_room_badge')]")
        )
        self.assertEqual(
            [
                " ".join(
                    a.xpath(".//*[@class='o_ewp_room_name']")[0].text.split()
                )
                for a in page.xpath("//a[contains(@class, 'o_ewp_room_link')]")
            ],
            ["North Hall", "Centre Lab", "Unplaced Room"],
        )
        self.assertEqual(
            page.xpath("//h2[@id='o_ewp_h_plan']")[0].text_content().strip(),
            "Rooms",
        )
        # Linear order: announcement, links, rooms, events, raffles.
        headings = [h.text_content().strip() for h in page.xpath("//main//h2")]
        self.assertEqual(
            headings,
            ["Announcement", "Links", "Rooms", "Today's events", "Raffles"],
        )
        toggle = page.xpath("//button[@id='o_ewp_text_only_toggle']")[0]
        self.assertEqual(toggle.get("aria-pressed"), "true")
        self.assertEqual(toggle.get("value"), "0")
        # No animation in text-only mode: no choice for it, whatever the
        # stored mode.
        self.assertFalse(page.xpath("//*[@id='o_ewp_motion']"))

        # The room page keeps the chat, without mascot.
        page = self._page(self._room(self.room_north))[1]
        self.assertFalse(page.xpath("//img"))
        chats = page.xpath("//iframe[@class='o_ewp_chat']")
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0].get("title"), "Discussion: North Hall")

        # The closed page has no mascot nor icon either.
        page = self._page("/webapp_event/%s" % self.day_ended.id)[1]
        self.assertFalse(page.xpath("//img"))
        self.assertFalse(
            page.xpath("//*[contains(@class, 'o_ewp_closed_icon')]")
        )

    def test_lead_cards_open_the_reading_order(self):
        """The cards of the home lead slot come first, before the
        announcement, in their own column; without any, neither the column
        nor the class of main that lays it out is there."""
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        page = self._page(self._home())[1]
        self.assertNotIn("o_ewp_home_lead", page.xpath("//main/@class")[0])
        self.assertFalse(
            page.xpath("//*[contains(@class, 'o_ewp_column_lead')]")
        )
        self.env["ir.ui.view"].create(
            {
                "name": "Test theme lead card",
                "type": "qweb",
                "inherit_id": (
                    self.env.ref("event_webapp_plan.webapp_slot_home_lead").id
                ),
                "arch": (
                    '<xpath expr="." position="inside">'
                    '<section class="o_ewp_card test_lead" '
                    'aria-labelledby="test_h_lead">'
                    '<h2 id="test_h_lead">Lead Test Card</h2>'
                    "</section></xpath>"
                ),
            }
        )
        for text_only, plan in ((False, "Site plan"), (True, "Rooms")):
            with self.subTest(text_only=text_only):
                self.portal_user.ewp_text_only = text_only
                page = self._page(self._home())[1]
                main = page.xpath("//main")[0]
                self.assertIn("o_ewp_home_lead", main.get("class"))
                self.assertTrue(
                    main.xpath(
                        "./*[1][contains(@class, 'o_ewp_column_lead')]"
                        "/section[contains(@class, 'test_lead')]"
                    )
                )
                self.assertEqual(
                    [h.text_content().strip() for h in main.xpath(".//h2")],
                    [
                        "Lead Test Card",
                        "Announcement",
                        "Links",
                        plan,
                        "Today's events",
                        "Raffles",
                    ],
                )

    def test_animation_mode_marks_the_body(self):
        """Each mode gives its body class and presses its button; "off"
        also gives o_ewp_motion_paused. The hint of the device setting is
        in the form, shown by the CSS only."""
        self.authenticate("ewp_a11y_portal", "ewp_a11y_portal")
        for mode in ("auto", "on", "off"):
            with self.subTest(mode=mode):
                self.portal_user.ewp_motion = mode
                page = self._page(self._home())[1]
                body_class = page.xpath("//body/@class")[0].split()
                motion = [
                    c for c in body_class if c.startswith("o_ewp_motion")
                ]
                expected = ["o_ewp_motion_%s" % mode]
                if mode == "off":
                    expected.append("o_ewp_motion_paused")
                self.assertEqual(motion, expected)
                pressed = page.xpath(
                    "//*[@id='o_ewp_motion']//button[@aria-pressed='true']"
                )
                self.assertEqual(
                    [b.get("id") for b in pressed],
                    ["o_ewp_motion_choice_%s" % mode],
                )
                hint = page.xpath("//*[@id='o_ewp_motion_hint']")[0]
                self.assertIsNone(hint.get("hidden"))
                button = hint.xpath(".//button")[0]
                self.assertEqual(
                    (button.get("name"), button.get("value")), ("motion", "on")
                )
        self.portal_user.ewp_motion = "off"
        page = self._page(self._home())[1]
        # The plan is still there.
        self.assertTrue(page.xpath("//img[@class='o_ewp_plan_image']"))
        self.assertTrue(
            page.xpath("//button[contains(@class, 'o_ewp_raffles_apply')]")
        )

    def test_offline_page_has_a_language(self):
        self.authenticate(None, None)
        response = self._get("/webapp_event/sw.js")
        self.assertIn("<html lang=", response.text)


@tagged("post_install", "-at_install")
class TestWebappAccessibilityBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_a11y_browser",
            password="ewp_a11y_browser",
            groups="base.group_portal",
            name="Portal Browser Reader",
            lang="en_US",
        )
        event = cls.env["event.event"].create(
            {
                "name": "Browser Reader Talk",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
            }
        )
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Browser Reader Raffle",
                "event_id": event.id,
                "draw_ids": [
                    Command.create(
                        {
                            "sequence": 1,
                            "prize": "Browser Reader Book",
                            "winner_name": "Ada Pastwinner",
                        }
                    ),
                    Command.create(
                        {"sequence": 2, "prize": "Browser Reader Pen"}
                    ),
                ],
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Browser Reader Day",
                "raffle_ids": [Command.set(cls.raffle.ids)],
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "announcement": "<p>Welcome, readers</p>",
                "plan_image": _png_b64(400, 200),
                "link_ids": [
                    Command.create(
                        {
                            "name": "Reader Browser Schedule",
                            "url": "https://example.org/schedule",
                        }
                    )
                ],
                "room_ids": [
                    # Turned, with corners past the edge of the image: the
                    # audit covers a turned area.
                    Command.create(
                        {
                            "name": "Theta Hall",
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 30,
                            "pos_height": 30,
                            "pos_rotation": 30,
                        }
                    ),
                ],
            }
        )
        cls.day_ended = cls.env["event.webapp"].create(
            {
                "name": "Browser Ended Day",
                "date_start": now - timedelta(days=3),
                "date_end": now - timedelta(days=3) + timedelta(hours=8),
            }
        )

    def test_pause_animations_toggle_and_announcement(self):
        code = "(async () => {" + JS_WAIT + """
            const check = (ok, message) => {
                if (!ok) {
                    throw new Error(message);
                }
            };
            const region = document.getElementById("o_ewp_announcer");
            const toggle = document.getElementById("o_ewp_motion_choice_off");
            check(document.body.dataset.ewpMotion === "running", "motion not running");
            const events = [];
            document.addEventListener("ewp:motion", (ev) => events.push(`${ev.detail.paused}:${ev.detail.mode}`));
            toggle.click();
            await wait(() => toggle.getAttribute("aria-pressed") === "true");
            check(document.getElementById("o_ewp_motion_choice_auto").getAttribute("aria-pressed") === "false",
                "auto still pressed");
            check(document.body.classList.contains("o_ewp_motion_paused"), "body class");
            check(document.body.classList.contains("o_ewp_motion_off")
                && !document.body.classList.contains("o_ewp_motion_auto"), "mode class");
            check(document.body.dataset.ewpMotion === "paused", "data-ewp-motion");
            await wait(() => region.textContent === "Animations are paused.");
            check(events.join() === "true:off", "events: " + events.join());
            // The skip link moves the focus to the text-only toggle.
            document.querySelector("a.o_ewp_skip[href='#o_ewp_prefs']").click();
            check(
                document.activeElement === document.getElementById("o_ewp_text_only_toggle"),
                "focus not on the text-only toggle"
            );
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            "/webapp_event/%s" % self.day.id,
            code,
            ready="document.readyState === 'complete'",
            login="ewp_a11y_browser",
        )
        self.assertEqual(self.portal_user.ewp_motion, "off")
        self.assertFalse(self.portal_user.ewp_text_only)

    def _run(self, url, code, **kwargs):
        self.browser_js(
            url,
            "(async () => {" + JS_WAIT + JS_CHECK + JS_FRAME + code + """
                console.log("test successful");
            })().catch((error) => console.error(error.message));
            """,
            ready="document.readyState === 'complete'",
            login="ewp_a11y_browser",
            **kwargs,
        )

    def test_text_only_toggle_writes_the_preference(self):
        """The toggle posts with fetch and the page loads again, as the
        server renders it: the next page says the new state in the shared
        region and gives the focus back to the toggle. In text-only mode a
        link that opens a new tab says so as text, in place of its icon."""
        self._run(
            HOST_PAGE,
            """
            const frame = await openFrame(%(home)r);
            let doc = frame.contentDocument;
            check(!doc.body.classList.contains("o_ewp_text_only"), "text-only at start");
            doc.getElementById("o_ewp_text_only_toggle").click();
            doc = await nextPage(frame, doc);
            const toggle = doc.getElementById("o_ewp_text_only_toggle");
            check(toggle.getAttribute("aria-pressed") === "true", "toggle not pressed");
            check(!doc.querySelector("img") && doc.body.classList.contains("o_ewp_text_only"),
                "not the text-only page");
            check(doc.body.dataset.ewpMotion === "paused", "animations not paused in text-only mode");
            await wait(() => doc.getElementById("o_ewp_announcer").textContent === "Text-only mode is on.");
            check(doc.activeElement === toggle, "focus not on the toggle");
            const link = doc.querySelector(".o_ewp_link");
            const cue = link.querySelector(".o_ewp_external_text");
            check(cue.getBoundingClientRect().width > 1 && cue.textContent === "(opens in a new tab)",
                "new tab cue not shown");
            check(getComputedStyle(link.querySelector(".o_ewp_icon")).display === "none", "icon shown");
            toggle.click();
            doc = await nextPage(frame, doc);
            await wait(() => doc.getElementById("o_ewp_announcer").textContent === "Text-only mode is off.");
            check(doc.activeElement === doc.getElementById("o_ewp_text_only_toggle"), "focus lost");
            check(doc.querySelector(".o_ewp_external_text").getBoundingClientRect().width <= 1,
                "new tab cue shown beside its icon");
            """ % {"home": "/webapp_event/%s" % self.day.id},
        )
        self.portal_user.invalidate_recordset()
        self.assertFalse(self.portal_user.ewp_text_only)

    def test_raffle_refresh_announcements(self):
        """What the shared region says on each answer of the raffle
        refresh: each new winner (never a winner of the first page), their
        count beyond three, else the drawn count; while the animations are
        paused, the block waits behind "Show the latest results"; and the
        end of the refresh, after a 403 or three failed answers in a row.
        The answers are those of the route, changed in the test."""
        self._run(
            "/webapp_event/%s" % self.day.id,
            """
            const region = document.getElementById("o_ewp_announcer");
            const box = document.querySelector("[data-ewp-raffles-url]");
            const apply = document.querySelector(".o_ewp_raffles_apply");
            const url = box.dataset.ewpRafflesUrl;
            const realFetch = window.fetch;
            let change = null;
            let mode = "json";
            let calls = 0;
            let serial = 0;
            window.fetch = async (target, options) => {
                if (!String(target).includes(url)) {
                    return realFetch(target, options);
                }
                calls += 1;
                if (mode === "forbidden") {
                    return new Response("", {status: 403});
                }
                if (mode === "error") {
                    return new Response("bad gateway", {status: 502});
                }
                const data = await (await realFetch(target, options)).json();
                if (change) {
                    change(data);
                    serial += 1;
                    data.signature = "changed-" + serial;
                }
                return jsonResponse(data);
            };
            // One refresh, as the timer would run it, then its end.
            const poll = async () => {
                const before = calls;
                document.dispatchEvent(new Event("visibilitychange"));
                await wait(() => calls > before);
                await sleep(200);
            };
            const raffle = (data) => data.raffles[0];
            const drawn = [];
            document.addEventListener("ewp:raffle-drawn", (ev) => drawn.push(ev.detail.winner));
            // A new winner: said with the raffle and the prize; the winner
            // of the first page is not said again.
            change = (data) => {
                const draw = raffle(data).draws[1];
                draw.drawn = true;
                draw.winner_name = "Grace Newwinner";
            };
            await poll();
            await wait(() => region.textContent ===
                "New winner, Browser Reader Raffle, Browser Reader Pen: Grace Newwinner.");
            check(drawn.join() === "Grace Newwinner", "events: " + drawn.join());
            // Beyond three new winners, their count.
            change = (data) => {
                const draws = raffle(data).draws;
                draws[1].drawn = true;
                draws[1].winner_name = "Grace Newwinner";
                for (const n of [1, 2, 3, 4]) {
                    draws.push({id: 900000 + n, drawn: true, prize: "", winner_name: "Extra " + n});
                }
            };
            await poll();
            await wait(() => region.textContent === "4 new winners in the raffles.");
            // No new winner: the drawn count.
            change = (data) => {
                raffle(data).draws[1].drawn = true;
            };
            await poll();
            await wait(() => region.textContent === "The raffles were updated: 2 drawn of 2.");
            check(!box.querySelector(".test_marker"), "block replaced too early");
            // Animations paused: the block waits for the button.
            document.getElementById("o_ewp_motion_choice_off").click();
            await wait(() => document.body.dataset.ewpMotion === "paused");
            change = (data) => {
                const draws = raffle(data).draws;
                draws[1].drawn = true;
                draws.push({id: 910000, drawn: true, prize: "Browser Reader Pen", winner_name: "Hedy Heldwinner"});
                data.html = '<p class="test_marker">held</p>';
            };
            await poll();
            await wait(() => region.textContent.startsWith(
                "New winner, Browser Reader Raffle, Browser Reader Pen: Hedy Heldwinner."));
            check(region.textContent.endsWith(
                'Use the button "Show the latest results" to see them.'), "pending part missing");
            check(!apply.hidden && !box.querySelector(".test_marker"), "block not held");
            apply.click();
            check(box.querySelector(".test_marker") && apply.hidden, "held block not shown");
            check(document.activeElement === document.getElementById("o_ewp_h_raffles"), "focus not on the heading");
            // Three failed answers in a row: the refresh is said to be stale.
            mode = "error";
            await poll();
            await poll();
            check(!region.textContent.includes("no longer updated"), "stale after two failures");
            await poll();
            await wait(() => region.textContent ===
                "The raffle results are no longer updated. Reload the page to see the latest draws.");
            // A good answer, then a 403: said again, and the refresh stops.
            mode = "json";
            change = (data) => {
                raffle(data).draws[0].prize = "Browser Reader Book, signed";
            };
            await poll();
            await wait(() => region.textContent.startsWith("The raffles were updated"));
            mode = "forbidden";
            await poll();
            await wait(() => region.textContent ===
                "The raffle results are no longer updated. Reload the page to see the latest draws.");
            const stoppedAt = calls;
            document.dispatchEvent(new Event("visibilitychange"));
            await sleep(500);
            check(calls === stoppedAt, "refresh not stopped");
            """,
        )

    def test_every_animation_stops(self):
        """A theme animation (CSS or SMIL, here a test mascot) stops with
        the mode "Off" and, under "Follow the device", with the system setting
        "reduce motion"; the mode "On" plays it whatever that setting says."""
        self.env["ir.ui.view"].create(
            {
                "name": "Test animated mascot",
                "type": "qweb",
                "inherit_id": (
                    self.env.ref("event_webapp_plan.webapp_slot_mascot").id
                ),
                "arch": (
                    '<xpath expr="." position="inside">'
                    "<style>@keyframes ewp_test_spin "
                    "{ to { transform: rotate(1turn); } }</style>"
                    '<span class="test_spin" style="display: inline-block; '
                    "width: 4px; height: 4px; "
                    'animation: ewp_test_spin 1s linear infinite"/>'
                    '<svg class="test_smil" width="4" height="4" '
                    'aria-hidden="true"><rect width="4" height="4">'
                    '<animate attributeName="x" values="0;2;0" dur="1s" '
                    'repeatCount="indefinite"/></rect></svg>'
                    "</xpath>"
                ),
            }
        )
        moving = """
            const moving = () => document.getAnimations()
                .filter((a) => a.playState === "running")
                .map((a) => (a.animationName || a.transitionProperty || "?"));
            const smil = () => !document.querySelector("svg.test_smil").animationsPaused();
        """
        home = "/webapp_event/%s" % self.day.id
        self._run(
            home,
            moving + """
            check(moving().includes("ewp_test_spin") && smil(), "test mascot not moving");
            document.getElementById("o_ewp_motion_choice_off").click();
            await wait(() => document.body.dataset.ewpMotion === "paused");
            await sleep(100);
            check(!moving().length, "still moving: " + moving().join());
            check(!smil(), "SMIL animation still running");
            """,
        )
        self.portal_user.invalidate_recordset()
        self.assertEqual(self.portal_user.ewp_motion, "off")
        self.portal_user.ewp_motion = "auto"
        with emulated_media(("prefers-reduced-motion", "reduce")):
            self._run(
                home,
                moving + """
                check(document.body.dataset.ewpMotion === "paused", "motion not paused");
                await sleep(300);
                check(!moving().length, "moving: " + moving().join());
                check(!smil(), "SMIL animation running");
                """,
            )
            self.portal_user.ewp_motion = "on"
            self.env.flush_all()
            self._run(
                home,
                moving + """
                check(document.body.dataset.ewpMotion === "running", "motion paused under On");
                check(moving().includes("ewp_test_spin") && smil(), "test mascot not moving under On");
                """,
            )

    def test_axe_core_finds_no_wcag_violation(self):
        """axe-core, WCAG 2.0/2.1/2.2 A and AA rules, plus the "region"
        rule (every content inside a landmark), on the home, room and
        closed pages, normal and text-only. Skipped without EWP_AXE_JS."""
        path = os.environ.get("EWP_AXE_JS")
        if not path or not os.path.isfile(path):
            self.skipTest("EWP_AXE_JS does not name a copy of axe.min.js")
        with open(path, encoding="utf-8") as handle:
            axe_source = handle.read()
        code = axe_source + "\n;(async () => {" + """
            // The chat frame is the Discuss client of Odoo, outside the
            // pages of the module.
            const result = await window.axe.run(document, {
                iframes: false,
                runOnly: {
                    type: "tag",
                    values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
                },
                // A best practice, outside the WCAG tags: a text outside
                // any landmark is missed by landmark navigation.
                rules: {region: {enabled: true}},
            });
            const found = result.violations.map(
                (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`
            );
            if (found.length) {
                throw new Error("axe: " + found.join(" | "));
            }
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        room = self.day.room_ids
        urls = (
            "/webapp_event/%s" % self.day.id,
            "/webapp_event/%s/room/%s" % (self.day.id, room.id),
            "/webapp_event/%s" % self.day_ended.id,
        )
        for text_only in (False, True):
            self.portal_user.ewp_text_only = text_only
            self.env.flush_all()
            for url in urls:
                with self.subTest(url=url, text_only=text_only):
                    self.browser_js(
                        url,
                        code,
                        ready="document.readyState === 'complete'",
                        login="ewp_a11y_browser",
                    )
