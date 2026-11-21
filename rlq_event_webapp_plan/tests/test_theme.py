# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Rencontres Linux theme of the /webapp_event pages: theme assets in the
bundle, images and fonts served by the module, nothing loaded from another
host, the decorative vector Tux and its pose, its inert copy for the
cameos with every part of the actions, the text-only mode without
mascots, the ribbon (inside the header) and its pause button, the poster
card option and its place before the announcement, and the web manifest
of the installable app.

The browser tests drive a headless Chrome and skip themselves without it:
the poses of the vector Tux, from the events of the page and from a real
raffle answer, its sipping pose and its halo in the dark scheme, the
ribbon that covers its band and stands still on demand, the place of the
poster card on a phone and on a wide screen, the flakes behind the
content, and every theme animation stopped on demand. Every name
below is invented for the tests."""

import base64
import io
import re
from datetime import timedelta
from unittest import mock

from lxml import html as lxml_html
from odoo import Command, fields
from odoo.addons.event_webapp_plan.models import bbb_client
from odoo.addons.event_webapp_plan.models.event_webapp_room import (
    PARAM_BBB_DISPLAY,
    PARAM_BBB_SECRET,
    PARAM_BBB_URL,
)
from odoo.addons.event_webapp_plan.tests.test_bbb import (
    SECRET,
    SERVER,
    FakeNetwork,
    fake_network,
)
from odoo.addons.event_webapp_plan.tests.test_browser import (
    CLIENT_PATH,
    JS_CHECK,
    JS_WAIT,
    emulated_media,
)
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from PIL import Image

MODULE_PATH = "/rlq_event_webapp_plan/static/src/webapp/"
# Files of the module and the first bytes each one starts with.
MODULE_FILES = {
    "img/tux-cafe.jpg": b"\xff\xd8\xff",
    "img/tux-avatar.jpg": b"\xff\xd8\xff",
    "img/pause-cafe-linux.jpg": b"\xff\xd8\xff",
    "img/icon-192.png": b"\x89PNG",
    "img/icon-512.png": b"\x89PNG",
    "img/lys.svg": b"<svg",
    "img/lys-motif.svg": b"<svg",
    "fonts/bree-serif-latin-400-normal.woff2": b"wOF2",
    "fonts/bree-serif-latin-ext-400-normal.woff2": b"wOF2",
}
POSES = {
    "idle",
    "greeting",
    "sipping",
    "celebrate",
    "sleeping",
    "coffee",
    "code",
    "speak",
    "wave",
    "walk",
    "peek",
}
# The vector Tux of the page, not its inert copy for the cameos.
PAGE_TUX = (
    "//*[local-name()='svg'][contains(@class, 'o_rlq_tux')]"
    "[not(ancestor::template)]"
)
# Parts of the drawing that the poses of the actions show.
TUX_PARTS = (
    "o_rlq_tux_face",
    "o_rlq_tux_foot_l",
    "o_rlq_tux_foot_r",
    "o_rlq_tux_mug",
    "o_rlq_tux_laptop",
    "o_rlq_tux_glow",
    "o_rlq_tux_glyphs",
    "o_rlq_tux_handmic",
    "o_rlq_tux_waves",
    "o_rlq_tux_bubble",
    "o_rlq_tux_zzz",
    "o_rlq_tux_confetti",
    "o_rlq_tux_live",
)

# settled() resolves with the vector Tux once the wave of the first page
# of the tab is over and its pose is the one of the page.
JS_TUX = """
const settled = async () => {
    const tux = document.querySelector("svg.o_rlq_tux:not(.o_rlq_tux_cameo)");
    check(tux, "no vector Tux");
    await wait(() => document.body.dataset.ewpMotion);
    await wait(() => tux.dataset.rlqTux === "greeting", 3000).catch(() => null);
    await wait(() => tux.dataset.rlqTux !== "greeting", 6000);
    return tux;
};
"""


def _png_b64(width=60, height=40):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (230, 236, 248)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue())


@tagged("post_install", "-at_install")
class TestRlqTheme(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.env["event.webapp"].search([]).write({"active": False})
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="rlq_theme_portal",
            password="rlq_theme_portal",
            groups="base.group_portal",
            name="Theme Visitor Test",
            lang="en_US",
        )
        new_test_user(
            cls.env,
            login="rlq_theme_moderator",
            password="rlq_theme_moderator",
            groups=(
                "base.group_user,"
                "event_webapp_plan.group_event_webapp_moderator"
            ),
            name="Theme Moderator Test",
            lang="en_US",
        )
        event = cls.env["event.event"].create(
            {
                "name": "Theme Test Talk",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=6),
            }
        )
        raffle = cls.env["event.raffle"].create(
            {
                "name": "Theme Test Raffle",
                "event_id": event.id,
                "draw_ids": [
                    Command.create(
                        {
                            "sequence": 1,
                            "prize": "Theme Test Mug",
                            "winner_name": "Ada Testwinner",
                        }
                    ),
                    Command.create({"sequence": 2, "prize": "Theme Test Pen"}),
                ],
            }
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Theme Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "announcement": "<p>Welcome to the theme test</p>",
                "plan_image": _png_b64(),
                "event_ids": [Command.set(event.ids)],
                "raffle_ids": [Command.set(raffle.ids)],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Theme Hall",
                            "pos_x": 10,
                            "pos_y": 10,
                            "pos_width": 30,
                            "pos_height": 30,
                        }
                    )
                ],
            }
        )
        cls.room = cls.day.room_ids
        future_raffle = cls.env["event.raffle"].create(
            {"name": "Theme Future Raffle", "event_id": event.id}
        )
        cls.day_future = cls.env["event.webapp"].create(
            {
                "name": "Theme Future Day",
                "date_start": now + timedelta(days=2),
                "date_end": now + timedelta(days=2, hours=8),
                "raffle_ids": [Command.set(future_raffle.ids)],
            }
        )
        cls.day_past = cls.env["event.webapp"].create(
            {
                "name": "Theme Past Day",
                "date_start": now - timedelta(days=2),
                "date_end": now - timedelta(days=2) + timedelta(hours=8),
            }
        )

    def _get(self, url):
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False)
        self.env.invalidate_all()
        return response

    def _page(self, url):
        response = self._get(url)
        self.assertEqual(response.status_code, 200, url)
        return lxml_html.fromstring(response.text)

    def _home(self):
        return "/webapp_event/%s" % self.day.id

    def _room(self):
        return "/webapp_event/%s/room/%s" % (self.day.id, self.room.id)

    def _pages(self):
        return (
            self._home(),
            self._room(),
            "/webapp_event/%s" % self.day_future.id,
            "/webapp_event/%s" % self.day_past.id,
        )

    def _bundle(self, page, xpath):
        urls = page.xpath(xpath)
        self.assertEqual(len(urls), 1, urls)
        response = self._get(urls[0])
        self.assertEqual(response.status_code, 200)
        return response.text

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------
    def test_pages_render_with_the_theme_assets(self):
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        page = self._page(self._home())
        css = self._bundle(page, "//link[@rel='stylesheet']/@href")
        self.assertIn("Rlq Bree Serif", css)
        self.assertIn(".o_rlq_tux", css)
        self.assertIn("rlq-marquee", css)
        script = self._bundle(
            page, "//script[contains(@src, '/web/assets/')]/@src"
        )
        self.assertIn("rlq:greeted", script)
        # The theme script comes after the page script it listens to.
        self.assertLess(
            script.index("ewp:announce"), script.index("rlq:greeted")
        )
        for url in self._pages():
            with self.subTest(url=url):
                page = self._page(url)
                self.assertIn(
                    "o_ewp_webapp", page.xpath("//body/@class")[0].split()
                )

    def test_images_and_fonts_answer_from_the_module(self):
        self.authenticate(None, None)
        for path, magic in MODULE_FILES.items():
            with self.subTest(path=path):
                response = self._get(MODULE_PATH + path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(magic))
        for path in ("img/lys.svg", "img/lys-motif.svg"):
            svg = self._get(MODULE_PATH + path).text.lower()
            for forbidden in ("<script", "href", "onload", "javascript:"):
                self.assertNotIn(forbidden, svg)
        # The JPEG files carry no metadata block (EXIF, XMP, comment).
        for path in MODULE_FILES:
            if path.endswith(".jpg"):
                image = Image.open(
                    io.BytesIO(self._get(MODULE_PATH + path).content)
                )
                self.assertFalse(image.getexif(), path)
                self.assertFalse(
                    {"exif", "xmp", "comment", "icc_profile"}
                    & set(image.info),
                    path,
                )

    def test_nothing_comes_from_another_host(self):
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for text_only in (False, True):
            self.portal_user.ewp_text_only = text_only
            for url in self._pages():
                with self.subTest(url=url, text_only=text_only):
                    page = self._page(url)
                    for src in page.xpath(
                        "//link/@href | //script/@src | //img/@src"
                    ):
                        self.assertTrue(src.startswith("/"), src)
                        self.assertFalse(src.startswith("//"), src)
        page = self._page(self._home())
        css = self._bundle(page, "//link[@rel='stylesheet']/@href")
        for target in re.findall(r"url\(\s*[\"']?([^\"')]+)", css):
            if target.startswith("data:"):
                continue
            self.assertTrue(target.startswith("/"), target)
            self.assertFalse(target.startswith("//"), target)
        fonts = [
            url
            for url in re.findall(r"url\(\s*[\"']?([^\"')]+\.woff2)", css)
            if url.startswith("/rlq_event_webapp_plan/")
        ]
        self.assertEqual(len(fonts), 2, fonts)
        # The code of the theme script names no URL (its comments hold the
        # licence link).
        script = self._get(MODULE_PATH + "rlq_theme.js").text
        code = [
            line
            for line in script.splitlines()
            if not line.lstrip().startswith("//")
        ]
        self.assertFalse([line for line in code if "://" in line])

    # ------------------------------------------------------------------
    # Mascots
    # ------------------------------------------------------------------
    def test_vector_tux_is_decorative_and_follows_the_page(self):
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        cases = (
            (self._room(), "idle"),
            (self._home(), "idle"),
            ("/webapp_event/%s" % self.day_past.id, "sleeping"),
        )
        for url, pose in cases:
            with self.subTest(url=url):
                page = self._page(url)
                tuxes = page.xpath(PAGE_TUX)
                self.assertEqual(len(tuxes), 1)
                self.assertEqual(tuxes[0].get("aria-hidden"), "true")
                self.assertEqual(tuxes[0].get("focusable"), "false")
                self.assertEqual(tuxes[0].get("data-rlq-tux"), pose)
                self.assertIn(pose, POSES)
                # No text inside the drawing: nothing for a reader to find.
                self.assertFalse(tuxes[0].text_content().strip())
        # Before the opening, Tux holds his coffee on the closed page: the
        # picture, with its alternative text.
        page = self._page("/webapp_event/%s" % self.day_future.id)
        self.assertFalse(page.xpath(PAGE_TUX))
        images = page.xpath("//img[contains(@src, 'tux-cafe.jpg')]")
        self.assertEqual(len(images), 1)
        self.assertIn("Tux", images[0].get("alt"))
        # A moderator sees the day before its opening: Tux sips in the
        # raffle card.
        self.authenticate("rlq_theme_moderator", "rlq_theme_moderator")
        page = self._page("/webapp_event/%s" % self.day_future.id)
        poses = page.xpath(PAGE_TUX + "/@data-rlq-tux")
        self.assertEqual(poses, ["sipping"])
        hero = page.xpath("//header//img[contains(@src, 'tux-cafe.jpg')]")
        self.assertEqual(len(hero), 1)

    def test_room_tux_speaks_while_the_meeting_runs(self):
        """The bar Tux speaks into the microphone while the meeting runs
        and drinks a coffee while it waits; the "conference left" page,
        and the embedded room page rendered after a leave (left=1), show
        him waving."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_URL, SERVER)
        params.set_param(PARAM_BBB_SECRET, SECRET)
        with fake_network(FakeNetwork(running=True)):
            self.room.bbb_meeting_id = "gl-invented-theme-0001"
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for running, pose in ((True, "speak"), (False, "coffee")):
            with self.subTest(running=running):
                with fake_network(FakeNetwork(running=running)):
                    page = self._page(self._room())
                self.assertEqual(
                    page.xpath(PAGE_TUX + "/@data-rlq-tux"), [pose]
                )
        page = self._page(
            "/webapp_event/%s/room/%s/bbb_left?frame=1"
            % (self.day.id, self.room.id)
        )
        self.assertEqual(page.xpath(PAGE_TUX + "/@data-rlq-tux"), ["wave"])
        params.set_param(PARAM_BBB_DISPLAY, "frame")
        with fake_network(FakeNetwork(running=True)):
            page = self._page(self._room() + "?left=1")
        self.assertEqual(page.xpath("//section/@data-ewp-bbb-state"), ["left"])
        self.assertEqual(page.xpath(PAGE_TUX + "/@data-rlq-tux"), ["wave"])

    def test_cameo_drawing_is_inert_decorative_and_complete(self):
        """Each page with mascots holds one copy of the vector Tux for the
        cameos, inside an inert template element: decorative, without id,
        text, link, script or event attribute, and with every part the
        actions need (the code glyphs are four strokes, not text). The
        stylesheet has the poses and keyframes of the actions."""
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for url in self._pages():
            with self.subTest(url=url):
                page = self._page(url)
                sources = page.xpath("//template[@class='o_rlq_tux_source']")
                self.assertEqual(len(sources), 1)
                svgs = sources[0].xpath(".//*[local-name()='svg']")
                self.assertEqual(len(svgs), 1)
                svg = svgs[0]
                self.assertIn("o_rlq_tux_cameo", svg.get("class").split())
                self.assertEqual(svg.get("aria-hidden"), "true")
                self.assertEqual(svg.get("focusable"), "false")
                for tux in page.xpath(
                    "//*[local-name()='svg']"
                    "[contains(concat(' ', @class, ' '), ' o_rlq_tux ')]"
                ):
                    self.assertFalse(tux.xpath(".//@id | @id"))
                    self.assertFalse(tux.text_content().strip())
                    self.assertFalse(
                        tux.xpath(
                            ".//*[local-name()='text' or local-name()="
                            "'script' or local-name()='use' or local-name()"
                            "='image' or local-name()='foreignObject']"
                        )
                    )
                    for attr in tux.xpath(".//@*"):
                        name = attr.attrname.lower()
                        self.assertFalse(name.startswith("on"), name)
                        self.assertNotIn("href", name)
                        self.assertNotIn("url(", str(attr))
                for part in TUX_PARTS:
                    self.assertEqual(
                        len(
                            svg.xpath(
                                ".//*[contains(concat(' ', @class, ' '),"
                                " ' %s ')]" % part
                            )
                        ),
                        1,
                        part,
                    )
                self.assertEqual(
                    len(svg.xpath(".//*[@class='o_rlq_tux_glyph']")), 4
                )
        css = self._bundle(
            self._page(self._home()), "//link[@rel='stylesheet']/@href"
        )
        for pose in POSES - {"idle"}:
            self.assertRegex(css, r"data-rlq-tux=[\"']?%s\b" % pose)
        for name in (
            "rlq-sip-face",
            "rlq-laptop-in",
            "rlq-type-left",
            "rlq-glyph",
            "rlq-talk",
            "rlq-voice",
            "rlq-bubble",
            "rlq-waddle",
            "rlq-step",
            "rlq-pace",
            "rlq-peek",
        ):
            self.assertIn("@keyframes %s" % name, css)

    def test_every_image_has_an_alternative_text(self):
        self.day.rlq_show_poster = True
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for url in self._pages():
            with self.subTest(url=url):
                page = self._page(url)
                for img in page.xpath("//img"):
                    self.assertIsNotNone(img.get("alt"), img.get("src"))
                self.assertFalse(page.xpath("//*[@role='marquee']"))

    def test_text_only_mode_has_no_mascot_and_no_motion(self):
        self.day.rlq_show_poster = True
        self.portal_user.ewp_text_only = True
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for url in self._pages():
            with self.subTest(url=url):
                page = self._page(url)
                body_class = page.xpath("//body/@class")[0].split()
                self.assertIn("o_ewp_text_only", body_class)
                self.assertIn("o_ewp_motion_paused", body_class)
                self.assertFalse(page.xpath("//img"))
                self.assertFalse(
                    page.xpath(
                        "//*[contains(@class, 'o_rlq_tux') "
                        "or contains(@class, 'o_rlq_flake') "
                        "or contains(@class, 'o_rlq_band') "
                        "or contains(@class, 'o_rlq_lights') "
                        "or contains(@class, 'o_rlq_ornament') "
                        "or contains(@class, 'o_rlq_steam')]"
                    )
                )
        # The poster card stays, as text.
        page = self._page(self._home())
        self.assertEqual(
            page.xpath("//h2[@id='o_rlq_h_poster']")[0].text_content(),
            "Pause Café Linux",
        )

    def test_ribbon_is_read_once_and_has_a_pause_button(self):
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        for url in (self._home(), self._room()):
            with self.subTest(url=url):
                page = self._page(url)
                bands = page.xpath("//div[@class='o_rlq_band']")
                self.assertEqual(len(bands), 1)
                band = bands[0]
                # Inside the header, the banner landmark of the page, after
                # the bar.
                self.assertEqual(
                    [el.tag for el in band.xpath("ancestor::header")],
                    ["header"],
                )
                self.assertTrue(
                    band.xpath(
                        "preceding-sibling::div[contains(@class, "
                        "'o_ewp_topbar')]"
                    )
                )
                moving = band.xpath(".//div[@class='o_rlq_marquee']")[0]
                self.assertEqual(moving.get("aria-hidden"), "true")
                # Shown, so no cameo may cover it.
                self.assertIsNotNone(moving.get("data-ewp-cameo-avoid"))
                # The words once, as plain text for screen readers.
                said = band.xpath("./p[@class='o_ewp_sr_only']")
                self.assertEqual(len(said), 1)
                self.assertIn("tips and tricks", said[0].text_content())
                # Six copies of the six words, hidden from screen readers.
                copies = moving.xpath(".//div[@class='o_rlq_copy']")
                self.assertEqual(len(copies), 6)
                for copy in copies:
                    self.assertEqual(
                        len(copy.xpath("./div[@class='o_rlq_word']")), 6
                    )
                buttons = band.xpath(
                    ".//button[@class='o_rlq_marquee_toggle']"
                )
                self.assertEqual(len(buttons), 1)
                self.assertEqual(buttons[0].get("type"), "button")
                self.assertEqual(buttons[0].get("aria-pressed"), "false")
                self.assertEqual(
                    buttons[0].get("aria-label"), "Pause the scrolling words"
                )
        # The closed page has no ribbon.
        page = self._page("/webapp_event/%s" % self.day_past.id)
        self.assertFalse(page.xpath("//div[@class='o_rlq_band']"))

    def test_poster_card_follows_the_option_of_the_day(self):
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        page = self._page(self._home())
        self.assertFalse(
            page.xpath("//section[contains(@class, 'o_rlq_poster')]")
        )
        self.day.rlq_show_poster = True
        page = self._page(self._home())
        cards = page.xpath("//section[contains(@class, 'o_rlq_poster')]")
        self.assertEqual(len(cards), 1)
        image = cards[0].xpath(".//img")[0]
        self.assertIn("pause-cafe-linux.jpg", image.get("src"))
        self.assertTrue(image.get("alt"))
        self.assertEqual(cards[0].get("aria-labelledby"), "o_rlq_h_poster")
        # The first card of the page, before the announcement, as in the
        # phone design; in text-only mode as well.
        self.assertTrue(
            page.xpath(
                "//main/*[1][contains(@class, 'o_ewp_column_lead')]"
                "/section[contains(@class, 'o_rlq_poster')]"
            )
        )
        self.portal_user.ewp_text_only = True
        page = self._page(self._home())
        self.assertEqual(
            [h.text_content().strip() for h in page.xpath("//main//h2")],
            [
                "Pause Café Linux",
                "Announcement",
                "Rooms",
                "Today's events",
                "Raffles",
            ],
        )

    # ------------------------------------------------------------------
    # Installable app
    # ------------------------------------------------------------------
    def test_manifest_and_pages_use_the_theme_colours_and_icons(self):
        self.authenticate(None, None)
        manifest = self._get("/webapp_event/manifest.webmanifest").json()
        self.assertEqual(manifest["theme_color"], "#1F4E9E")
        self.assertEqual(manifest["background_color"], "#1F4E9E")
        self.assertEqual(manifest["name"], "Rencontres Linux event day")
        self.assertEqual(
            [icon["sizes"] for icon in manifest["icons"]],
            ["192x192", "512x512"],
        )
        for icon in manifest["icons"]:
            self.assertTrue(icon["src"].startswith(MODULE_PATH + "img/"))
            response = self._get(icon["src"])
            self.assertEqual(response.status_code, 200)
            size = int(icon["sizes"].split("x")[0])
            self.assertEqual(
                Image.open(io.BytesIO(response.content)).size, (size, size)
            )
        self.authenticate("rlq_theme_portal", "rlq_theme_portal")
        page = self._page(self._home())
        self.assertEqual(
            page.xpath("//meta[@name='theme-color']/@content"), ["#1F4E9E"]
        )
        self.assertEqual(
            page.xpath("//link[@rel='apple-touch-icon']/@href"),
            [MODULE_PATH + "img/icon-192.png"],
        )


@tagged("post_install", "-at_install")
class TestRlqThemeBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["event.webapp"].search([]).write({"active": False})
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_URL, SERVER)
        params.set_param(PARAM_BBB_SECRET, SECRET)
        # The fake server is on another site than the test server: the
        # frame tests force the embedded display.
        params.set_param(PARAM_BBB_DISPLAY, "frame")
        now = fields.Datetime.now()
        cls.user = new_test_user(
            cls.env,
            login="rlq_theme_browser",
            password="rlq_theme_browser",
            groups="base.group_portal",
            name="Theme Browser Test",
            lang="en_US",
        )
        event = cls.env["event.event"].create(
            {
                "name": "Theme Browser Talk",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=6),
            }
        )
        raffle = cls.env["event.raffle"].create(
            {
                "name": "Theme Browser Raffle",
                "event_id": event.id,
                "draw_ids": [Command.create({"sequence": 1, "prize": "Cap"})],
            }
        )
        with fake_network(FakeNetwork(running=True)):
            cls.day = cls.env["event.webapp"].create(
                {
                    "name": "Theme Browser Day",
                    "date_start": now - timedelta(hours=1),
                    "date_end": now + timedelta(hours=8),
                    "plan_image": _png_b64(),
                    "raffle_ids": [Command.set(raffle.ids)],
                    "room_ids": [
                        Command.create(
                            {
                                "name": "Theme Browser Hall",
                                "bbb_meeting_id": "gl-invented-theme-0002",
                                "pos_x": 10,
                                "pos_y": 10,
                                "pos_width": 30,
                                "pos_height": 30,
                            }
                        )
                    ],
                }
            )
        cls.day_past = cls.env["event.webapp"].create(
            {
                "name": "Theme Browser Past Day",
                "date_start": now - timedelta(days=2),
                "date_end": now - timedelta(days=2) + timedelta(hours=8),
            }
        )

    def _home(self):
        return "/webapp_event/%s" % self.day.id

    def _room(self):
        return "/webapp_event/%s/room/%s" % (self.day.id, self.day.room_ids.id)

    def _run(self, url, code, running=False):
        """browser_js on `url`, the fake server playing a meeting that runs
        or not, the join URL replaced by a page of the same origin."""
        with fake_network(FakeNetwork(running=running)), mock.patch.object(
            bbb_client, "join_url", return_value=CLIENT_PATH
        ):
            self.browser_js(
                url,
                "(async () => {" + JS_WAIT + JS_CHECK + JS_TUX + code + """
                    console.log("test successful");
                })().catch((error) => console.error(error.message));
                """,
                ready="document.readyState === 'complete'",
                login="rlq_theme_browser",
            )

    def test_tux_pose_follows_the_page_events(self):
        """The wave of the first page, a winner drawn by a real answer of
        the raffle refresh (celebrate), the end of the day (sleeping), and
        on the room page the running meeting (speak, with a microphone)."""
        self._run(
            self._home(),
            """
            const tux = await settled();
            const url = document.querySelector("[data-ewp-raffles-url]").dataset.ewpRafflesUrl;
            const realFetch = window.fetch;
            window.fetch = async (target, options) => {
                const response = await realFetch(target, options);
                if (!String(target).includes(url)) {
                    return response;
                }
                const data = await response.json();
                data.raffles[0].draws[0].drawn = true;
                data.raffles[0].draws[0].winner_name = "Ada Themewinner";
                data.signature = "changed";
                return new Response(JSON.stringify(data), {headers: {"Content-Type": "application/json"}});
            };
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => tux.dataset.rlqTux === "celebrate");
            await wait(() => document.getElementById("o_ewp_announcer").textContent.includes("Ada Themewinner"));
            document.dispatchEvent(new CustomEvent("ewp:day-state", {
                detail: {state: "after", previous: "open", initial: false},
            }));
            await wait(() => tux.dataset.rlqTux === "sleeping", 8000);
            """,
        )
        self._run(
            self._room(),
            """
            const tux = document.querySelector("svg.o_rlq_tux:not(.o_rlq_tux_cameo)");
            check(document.querySelector(".o_ewp_bbb").dataset.ewpBbbState === "running", "meeting not running");
            await wait(() => tux.dataset.rlqTux === "speak", 8000);
            const mic = tux.querySelector(".o_rlq_tux_handmic");
            await wait(() => getComputedStyle(mic).opacity === "1", 3000);
            """,
            running=True,
        )

    def test_tux_speaks_behind_the_new_tab_button(self):
        """A running meeting behind the new tab button (display "tab"):
        the first ewp:bbb-state carries live, so the bar Tux reaches the
        speak pose and keeps it; the block has the navy border."""
        self.env["ir.config_parameter"].sudo().set_param(
            PARAM_BBB_DISPLAY, "tab"
        )
        self._run(
            self._room(),
            """
            check(document.querySelector(".o_ewp_bbb").dataset.ewpBbbState === "button", "not behind the button");
            check(!document.querySelector("iframe.o_ewp_bbb_frame"), "frame rendered");
            // Past the wave of the first page, the pose is the one the
            // script derives from the first ewp:bbb-state.
            const tux = await settled();
            await wait(() => tux.dataset.rlqTux === "speak", 8000);
            await sleep(1500);
            check(tux.dataset.rlqTux === "speak", `pose ${tux.dataset.rlqTux} after the first event`);
            const box = document.querySelector(".o_ewp_bbb_tab_live");
            check(box, "no live block");
            const style = getComputedStyle(box);
            check(style.borderTopStyle === "solid", `border ${style.borderTopStyle}`);
            check(style.borderTopColor === "rgb(22, 59, 120)", `border colour ${style.borderTopColor}`);
            check(parseFloat(style.borderTopWidth) >= 4, `border width ${style.borderTopWidth}`);
            """,
            running=True,
        )

    def test_sipping_tux_holds_its_mug_at_the_beak(self):
        """In the sipping pose the tip of the left flipper is under the
        mug, and the rim of the mug at the beak (units of the viewBox)."""
        self._run(
            self._home(),
            """
            const tux = await settled();
            document.body.classList.add("o_ewp_motion_paused");
            tux.dataset.rlqTux = "sipping";
            await sleep(100);
            const at = (selector, x, y) => {
                const el = tux.querySelector(selector);
                const matrix = tux.getScreenCTM().inverse().multiply(el.getScreenCTM());
                return new DOMPoint(x, y).matrixTransform(matrix);
            };
            const tip = at(".o_rlq_tux_flip_l path", 18, 118);
            const bottom = at(".o_rlq_tux_mug_body", 19, 120);
            const rim = at(".o_rlq_tux_mug_body", 19, 100);
            const gap = Math.hypot(tip.x - bottom.x, tip.y - bottom.y);
            check(gap < 6, `flipper tip ${tip.x},${tip.y} far from the mug ${bottom.x},${bottom.y}`);
            check(rim.x > 48 && rim.x < 76 && rim.y > 46 && rim.y < 68,
                `rim ${rim.x},${rim.y} away from the beak`);
            """,
        )

    def test_card_tux_has_a_halo_in_the_dark_scheme(self):
        for scheme, halo in (("dark", True), ("light", False)):
            with self.subTest(scheme=scheme):
                with emulated_media(("prefers-color-scheme", scheme)):
                    self._run(
                        self._home(),
                        """
                        const filter = getComputedStyle(document.querySelector(".o_rlq_tux_card")).filter;
                        check(filter.includes("drop-shadow") === %s, "filter: " + filter);
                        """ % ("true" if halo else "false"),
                    )

    def test_ribbon_covers_its_band_and_stands_still_on_demand(self):
        """The track still covers the band at the end of each loop, up to a
        2560 px screen; standing still (its button, the animation mode "Off"),
        the ribbon shows every word, wrapped, even in a narrow band."""
        with emulated_media(("prefers-reduced-motion", "no-preference")):
            self._run(
                self._home(),
                """
                const band = document.querySelector(".o_rlq_band");
                const marquee = band.querySelector(".o_rlq_marquee");
                const track = band.querySelector(".o_rlq_marquee_track");
                const copies = [...track.querySelectorAll(".o_rlq_copy")];
                const copy = copies[0].getBoundingClientRect().width;
                const animation = track.getAnimations()[0];
                check(animation, "ribbon not moving");
                animation.pause();
                animation.currentTime = animation.effect.getComputedTiming().duration - 1;
                const shift = new DOMMatrix(getComputedStyle(track).transform).m41;
                check(Math.abs(shift + copy) < 2, `shift ${shift} for a copy of ${copy}`);
                check(track.getBoundingClientRect().width + shift >= marquee.clientWidth,
                    "band partly empty at the end of the loop");
                check((copies.length - 1) * copy >= 2560 - 44, "too few copies for a wide screen");
                animation.play();
                // A narrow band, as on a phone.
                band.style.maxWidth = "390px";
                const words = () => [...copies[0].querySelectorAll(".o_rlq_word")];
                const allSeen = () => {
                    const box = band.getBoundingClientRect();
                    return words().every((word) => {
                        const r = word.getBoundingClientRect();
                        return r.width > 0 && r.left >= box.left - 1 && r.right <= box.right + 1
                            && r.top >= box.top - 1 && r.bottom <= box.bottom + 1;
                    });
                };
                check(!allSeen(), "every word seen while the ribbon moves in a narrow band");
                const button = band.querySelector(".o_rlq_marquee_toggle");
                button.click();
                check(button.getAttribute("aria-pressed") === "true", "button not pressed");
                check(getComputedStyle(track).animationName === "none", "ribbon still moving");
                check(getComputedStyle(copies[1]).display === "none", "second copy shown");
                check(allSeen(), "a word out of the band with the ribbon paused");
                button.click();
                check(button.getAttribute("aria-pressed") === "false", "button still pressed");
                check(track.getAnimations().length === 1, "ribbon not moving again");
                document.getElementById("o_ewp_motion_choice_off").click();
                await wait(() => document.body.dataset.ewpMotion === "paused");
                check(allSeen(), "a word out of the band with every animation paused");
                check(getComputedStyle(button).display === "none", "ribbon button shown");
                """,
            )

    def test_poster_card_opens_phones_and_tops_the_main_column(self):
        """Design version 3: on a phone the Pause Café Linux card comes
        first, before the announcement; on a wide screen it tops the main
        column, over the plan, beside the announcement."""
        self.day.write(
            {
                "announcement": "<p>Theme browser welcome</p>",
                "rlq_show_poster": True,
            }
        )
        self._run(
            self._home(),
            """
            // Boxes of the cards of the page in a frame `width` px wide.
            const boxes = async (width) => {
                const frame = document.createElement("iframe");
                frame.style.width = `${width}px`;
                frame.style.height = "900px";
                document.body.appendChild(frame);
                frame.src = location.pathname;
                await wait(() => {
                    const doc = frame.contentDocument;
                    return doc.location.pathname === location.pathname
                        && doc.readyState === "complete" && doc.body.dataset.ewpMotion;
                });
                // Still cards: an entrance animation would move them.
                frame.contentDocument.body.classList.add("o_ewp_motion_paused");
                await sleep(100);
                const box = (selector) => {
                    const el = frame.contentDocument.querySelector(selector);
                    check(el, "missing " + selector);
                    return el.getBoundingClientRect();
                };
                return {
                    poster: box(".o_rlq_poster"),
                    announcement: box(".o_ewp_announcement"),
                    plan: box(".o_ewp_plan_card"),
                };
            };
            const near = (a, b) => Math.abs(a - b) <= 2;
            const phone = await boxes(390);
            check(phone.poster.bottom <= phone.announcement.top,
                `phone: poster ${phone.poster.bottom}, announcement ${phone.announcement.top}`);
            check(phone.announcement.bottom <= phone.plan.top, "phone: plan before the announcement");
            const wide = await boxes(1280);
            check(near(wide.poster.left, wide.plan.left), "wide: poster out of the main column");
            check(wide.plan.top >= wide.poster.bottom && wide.plan.top - wide.poster.bottom <= 40,
                `wide: plan ${wide.plan.top} not right under the poster ${wide.poster.bottom}`);
            check(wide.announcement.left >= wide.poster.right, "wide: announcement not beside the poster");
            check(near(wide.announcement.top, wide.poster.top),
                `wide: announcement ${wide.announcement.top}, poster ${wide.poster.top}`);
            """,
        )

    def test_flakes_stay_behind_the_content(self):
        """The rising flakes paint under the texts and controls of the bars
        and of the closed page, and fill the whole closed page."""
        behind = """
            // The element at the centre of `selector`, the flakes made
            // hit-testable: the element itself when they lie behind it.
            const behind = (selector) => {
                const el = document.querySelector(selector);
                check(el, "missing " + selector);
                const flakes = document.querySelector(".o_rlq_flakes");
                flakes.style.pointerEvents = "auto";
                const r = el.getBoundingClientRect();
                const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                flakes.style.pointerEvents = "";
                check(el.contains(hit), selector + " under " + (hit && hit.className));
            };
        """
        self._run(
            self._home(),
            behind + """
            behind(".o_ewp_dayhead .o_ewp_day_title");
            behind(".o_ewp_dayhead .o_ewp_logout");
            """,
        )
        self._run(
            self._room(),
            behind + """
            behind(".o_ewp_appbar .o_ewp_back");
            behind(".o_ewp_appbar .o_ewp_room_title");
            """,
        )
        self._run(
            "/webapp_event/%s" % self.day_past.id,
            behind + """
            behind(".o_ewp_closed_text h1");
            const flakes = document.querySelector(".o_rlq_flakes").getBoundingClientRect();
            const page = document.querySelector("main.o_ewp_closed").getBoundingClientRect();
            check(Math.abs(flakes.top - page.top) < 1 && Math.abs(flakes.height - page.height) < 1,
                "flakes do not fill the closed page");
            """,
        )

    def test_every_theme_animation_stops(self):
        """Tux, steam, flakes, ribbon and cards move; the animation mode
        "Off", and the system setting "reduce motion" under "Follow the
        device", stop all of them; the mode "On" plays them even then."""
        moving = """
            const moving = () => document.getAnimations()
                .filter((a) => a.playState === "running")
                .map((a) => a.animationName || a.transitionProperty || "?");
        """
        with emulated_media(("prefers-reduced-motion", "no-preference")):
            self._run(
                self._home(),
                moving + """
                await sleep(500);
                const names = moving();
                for (const name of ["rlq-bob", "rlq-steam", "rlq-rise", "rlq-marquee", "rlq-blink"]) {
                    check(names.includes(name), name + " not running: " + names.join());
                }
                document.getElementById("o_ewp_motion_choice_off").click();
                await wait(() => document.body.dataset.ewpMotion === "paused");
                await sleep(100);
                check(!moving().length, "still moving: " + moving().join());
                """,
            )
        self.user.invalidate_recordset()
        self.assertEqual(self.user.ewp_motion, "off")
        self.user.ewp_motion = "auto"
        with emulated_media(("prefers-reduced-motion", "reduce")):
            self._run(
                self._home(),
                moving + """
                await sleep(500);
                check(!moving().length, "moving: " + moving().join());
                check(getComputedStyle(document.querySelector(".o_rlq_marquee_toggle")).display === "none",
                    "ribbon button shown under reduced motion");
                """,
            )
            self.user.ewp_motion = "on"
            self.env.flush_all()
            self._run(
                self._home(),
                moving + """
                await sleep(500);
                const names = moving();
                for (const name of ["rlq-bob", "rlq-steam", "rlq-rise", "rlq-marquee"]) {
                    check(names.includes(name), name + " not running under On: " + names.join());
                }
                check(getComputedStyle(document.querySelector(".o_rlq_marquee_toggle")).display !== "none",
                    "ribbon button hidden under On");
                """,
            )
