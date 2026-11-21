# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""HTTP tests of the /webapp_event pages: login redirect, opening window,
moderator preview, room membership, access to the room chats through the
room groups, plan access and raffle JSON content.

Every name, address and e-mail below is invented for the tests."""

import base64
import io
import json
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from lxml import html as lxml_html
from odoo import Command, fields
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from PIL import Image

from ..controllers.main import EventWebappController

WINNER_EMAIL = "ewp.webapp.winner@example.invalid"


def _png_b64(width=40, height=20):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 220, 230)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue())


@tagged("post_install", "-at_install")
class TestWebappControllers(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The assertions read the English source strings: the test users
        # get English, which a database may have left inactive when it was
        # created in another language.
        cls.env["res.lang"]._activate_lang("en_US")
        Webapp = cls.env["event.webapp"]
        # /webapp_event picks a default day among the active ones: archive
        # the days already in the database so the test days are the only
        # candidates.
        Webapp.search([]).write({"active": False})
        now = fields.Datetime.now()

        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_webapp_portal",
            password="ewp_webapp_portal",
            groups="base.group_portal",
            name="Portal Visitor Test",
            lang="en_US",
        )
        cls.moderator_user = new_test_user(
            cls.env,
            login="ewp_webapp_moderator",
            password="ewp_webapp_moderator",
            groups="base.group_user,"
            "event_webapp_plan.group_event_webapp_moderator",
            name="Moderator Test",
            lang="en_US",
        )
        cls.internal_user = new_test_user(
            cls.env,
            login="ewp_webapp_internal",
            password="ewp_webapp_internal",
            groups="base.group_user",
            name="Internal Visitor Test",
            lang="en_US",
        )

        cls.event = cls.env["event.event"].create(
            {
                "name": "Webapp Test Conference",
                "date_begin": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
            }
        )
        cls.raffle = cls.env["event.raffle"].create(
            {
                "name": "Morning Test Raffle",
                "event_id": cls.event.id,
                "draw_ids": [
                    Command.create(
                        {
                            "sequence": 1,
                            "prize": "Test Keyboard",
                            "winner_name": "Grace Testwinner",
                            "winner_email": WINNER_EMAIL,
                        }
                    ),
                    Command.create({"sequence": 2, "prize": "Test Mug"}),
                ],
            }
        )
        cls.day_open = Webapp.create(
            {
                "name": "Open Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "announcement": "<p>Welcome to the test day</p>",
                "plan_image": _png_b64(),
                "event_ids": [Command.set(cls.event.ids)],
                "raffle_ids": [Command.set(cls.raffle.ids)],
                "link_ids": [
                    Command.create(
                        {
                            "name": "Test Schedule",
                            "url": "https://example.invalid/schedule",
                        }
                    )
                ],
                "room_ids": [
                    Command.create(
                        {
                            "name": "Alpha Hall",
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 20,
                            "pos_height": 30,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Beta Lab",
                            "pos_x": 40,
                            "pos_y": 10,
                            "pos_width": 25,
                            "pos_height": 25,
                        }
                    ),
                ],
            }
        )
        cls.day_future = Webapp.create(
            {
                "name": "Future Test Day",
                "date_start": now + timedelta(days=30),
                "date_end": now + timedelta(days=30, hours=8),
                "plan_image": _png_b64(),
                "room_ids": [
                    Command.create(
                        {
                            "name": "Gamma Room",
                            "pos_x": 10,
                            "pos_y": 10,
                            "pos_width": 10,
                            "pos_height": 10,
                        }
                    )
                ],
            }
        )
        cls.day_ended = Webapp.create(
            {
                "name": "Ended Test Day",
                "date_start": now - timedelta(days=2),
                "date_end": now - timedelta(days=2) + timedelta(hours=8),
                "room_ids": [Command.create({"name": "Delta Room"})],
            }
        )
        cls.room_alpha = cls.day_open.room_ids.filtered(
            lambda r: r.name == "Alpha Hall"
        )
        cls.room_beta = cls.day_open.room_ids - cls.room_alpha
        cls.room_gamma = cls.day_future.room_ids
        cls.room_delta = cls.day_ended.room_ids

    def _get(self, url, **kwargs):
        """GET without following redirects. The request runs on the test
        cursor with its own cache: pending writes are flushed before it,
        and the cache of the test is dropped after it."""
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False, **kwargs)
        self.env.invalidate_all()
        return response

    def _room_url(self, day, room):
        return "/webapp_event/%s/room/%s" % (day.id, room.id)

    def _member_count(self, room, user):
        return self.env["discuss.channel.member"].search_count(
            [
                ("channel_id", "=", room.channel_id.id),
                ("partner_id", "=", user.partner_id.id),
            ]
        )

    def _assert_closed_room_page(self, day, room, user, text):
        response = self._get(self._room_url(day, room))
        self.assertEqual(response.status_code, 200)
        self.assertIn(text, response.text)
        self.assertNotIn("<iframe", response.text)
        self.assertNotIn(room.name, response.text)
        self.assertEqual(self._member_count(room, user), 0)
        self.assertNotIn(room.access_group_id, user.groups_id)

    def test_anonymous_redirected_to_login(self):
        # A session without user, on the test database: without it the
        # server picks a database through the db filter, and a filter that
        # matches two databases serves no module route at all.
        self.authenticate(None, None)
        response = self._get("/webapp_event")
        self.assertIn(response.status_code, (302, 303))
        location = urlparse(response.headers["Location"])
        self.assertEqual(location.path, "/web/login")
        redirect = parse_qs(location.query).get("redirect", [""])[0]
        self.assertTrue(redirect.startswith("/webapp_event"), redirect)

    def test_portal_inside_window_sees_rooms(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Open Test Day", response.text)
        self.assertIn("Alpha Hall", response.text)
        self.assertIn("Beta Lab", response.text)
        self.assertIn("Welcome to the test day", response.text)
        self.assertIn("Grace Testwinner", response.text)
        self.assertNotIn(WINNER_EMAIL, response.text)
        self.assertNotIn("Preview outside opening hours", response.text)

    def test_home_page_cards_and_values(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s" % self.day_open.id)
        page = lxml_html.fromstring(response.text)

        def texts(xpath):
            return [
                " ".join(e.text_content().split()) for e in page.xpath(xpath)
            ]

        self.assertEqual(
            texts("//*[contains(@class, 'o_ewp_room_badge')]"), ["1", "2"]
        )
        self.assertEqual(
            texts("//*[contains(@class, 'o_ewp_hotspot_number')]"), ["1", "2"]
        )
        self.assertIn(
            "In progress", texts("//*[contains(@class, 'o_ewp_pill_open')]")
        )
        self.assertEqual(
            texts("//*[@class='o_ewp_raffle_progress']"), ["1 drawn of 2"]
        )
        age = page.xpath("//*[@data-ewp-label-seconds]")
        self.assertEqual(len(age), 1)
        self.assertIn("%(seconds)s", age[0].get("data-ewp-label-seconds"))
        self.assertIn("%(minutes)s", age[0].get("data-ewp-label-minutes"))
        link = page.xpath("//a[contains(@class, 'o_ewp_link')]")[0]
        self.assertEqual(link.get("target"), "_blank")
        self.assertIn("noopener", link.get("rel"))

    def test_pages_load_nothing_from_another_host(self):
        """The fonts are served by the module: no stylesheet, script or
        font of the pages comes from another origin, and every font URL of
        the bundle answers."""
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s" % self.day_open.id)
        page = lxml_html.fromstring(response.text)
        urls = page.xpath("//link/@href | //script/@src | //img/@src")
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith("/"), url)
            self.assertFalse(url.startswith("//"), url)
        css_urls = page.xpath("//link[@rel='stylesheet']/@href")
        self.assertEqual(len(css_urls), 1)
        css = self._get(css_urls[0]).text
        fonts = re.findall(r"url\(\s*[\"']?([^\"')]+\.woff2)", css)
        # The 4 font files of this module, plus those of a theme module
        # installed beside it, served from the Odoo server as well.
        own = [url for url in fonts if url.startswith("/event_webapp_plan/")]
        self.assertEqual(len(own), 4, fonts)
        for url in fonts:
            self.assertTrue(url.startswith("/"), url)
            self.assertFalse(url.startswith("//"), url)
            font = self._get(url)
            self.assertEqual(font.status_code, 200, url)
            self.assertEqual(font.content[:4], b"wOF2", url)

    def test_theme_hooks_page_state_and_slots(self):
        """The body and the root element carry the page and the day state,
        and a template inheriting a slot shows on the pages that call
        it."""
        slots = {
            "webapp_slot_mascot": "mascot",
            "webapp_slot_banner": "banner",
            "webapp_slot_home_lead": "lead",
            "webapp_slot_home_cards": "cards",
            "webapp_slot_room_item": "room_item",
            "webapp_slot_room_main": "room_main",
            "webapp_slot_footer": "footer",
        }
        for slot, name in slots.items():
            self.env["ir.ui.view"].create(
                {
                    "name": "Test theme %s" % name,
                    "type": "qweb",
                    "inherit_id": (
                        self.env.ref("event_webapp_plan.%s" % slot).id
                    ),
                    "arch": (
                        '<xpath expr="." position="inside">'
                        '<i class="test_slot_%s" '
                        't-att-data-page="ewp_page" '
                        't-att-data-day="day_state"/></xpath>' % name
                    ),
                }
            )
        self.authenticate("ewp_webapp_moderator", "ewp_webapp_moderator")
        cases = (
            (
                "/webapp_event/%s" % self.day_open.id,
                "home",
                "open",
                {"mascot", "banner", "lead", "cards", "room_item", "footer"},
            ),
            (
                self._room_url(self.day_open, self.room_alpha),
                "room",
                "open",
                {"mascot", "banner", "room_main", "footer"},
            ),
            (
                "/webapp_event/%s" % self.day_future.id,
                "home",
                "before",
                {"mascot", "banner", "lead", "cards", "room_item", "footer"},
            ),
            (
                self._room_url(self.day_open, self.room_alpha)
                + "/bbb_left?frame=1",
                "bbb_left",
                "open",
                {"mascot", "footer"},
            ),
        )
        for url, page_name, state, shown in cases:
            with self.subTest(url=url):
                response = self._get(url)
                self.assertEqual(response.status_code, 200)
                page = lxml_html.fromstring(response.text)
                body_class = page.xpath("//body/@class")[0].split()
                self.assertIn("o_ewp_page_%s" % page_name, body_class)
                self.assertIn("o_ewp_day_%s" % state, body_class)
                app = page.xpath("//div[@class='o_ewp_app']")[0]
                self.assertEqual(app.get("data-ewp-page"), page_name)
                self.assertEqual(app.get("data-ewp-day-state"), state)
                self.assertTrue(app.get("data-ewp-day-start"))
                self.assertTrue(app.get("data-ewp-day-end"))
                found = {
                    name
                    for name in slots.values()
                    if page.xpath("//i[@class='test_slot_%s']" % name)
                }
                self.assertEqual(found, shown)
                # The banner is inside the header, the banner landmark;
                # the lead cards open the home page, in their own column.
                if "banner" in shown:
                    self.assertTrue(
                        page.xpath("//header//i[@class='test_slot_banner']")
                    )
                if "lead" in shown:
                    main = page.xpath("//main")[0]
                    self.assertIn("o_ewp_home_lead", main.get("class"))
                    self.assertTrue(
                        main.xpath(
                            "./*[1][contains(@class, 'o_ewp_column_lead')]"
                            "/i[@class='test_slot_lead']"
                        )
                    )
                # One room item per link of the room list, inside its
                # text; the room block closes the main content.
                if "room_item" in shown:
                    self.assertEqual(
                        len(page.xpath("//i[@class='test_slot_room_item']")),
                        len(page.xpath("//a[@class='o_ewp_room_link']")),
                    )
                    self.assertFalse(
                        page.xpath(
                            "//i[@class='test_slot_room_item']"
                            "[not(parent::span[@class='o_ewp_room_text'])]"
                        )
                    )
                if "room_main" in shown:
                    self.assertTrue(
                        page.xpath(
                            "//main/*[last()][@class='test_slot_room_main']"
                        )
                    )
                for slot in page.xpath("//i[starts-with(@class, 'test_')]"):
                    self.assertEqual(slot.get("data-page"), page_name)
                    self.assertEqual(slot.get("data-day"), state)
        # A portal user outside the window gets the closed page.
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        page = lxml_html.fromstring(
            self._get("/webapp_event/%s" % self.day_ended.id).text
        )
        body_class = page.xpath("//body/@class")[0].split()
        self.assertIn("o_ewp_page_closed", body_class)
        self.assertIn("o_ewp_day_after", body_class)
        self.assertTrue(page.xpath("//i[@class='test_slot_mascot']"))

    def test_closed_page_shows_the_window_and_the_user(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s" % self.day_future.id)
        page = lxml_html.fromstring(response.text)
        self.assertEqual(
            [dt.text_content().strip() for dt in page.xpath("//dt")],
            ["Opening", "Closing"],
        )
        self.assertIn("Signed in as Portal Visitor Test", response.text)
        self.assertTrue(
            page.xpath("//a[contains(@href, '/web/session/logout')]")
        )

    def test_turned_area_style_and_position_words(self):
        """A turned area carries its angle in its style; its centre, and so
        the position words of the room list, do not move."""
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        url = "/webapp_event/%s" % self.day_open.id

        def area_and_words():
            page = lxml_html.fromstring(self._get(url).text)
            area = page.xpath(
                "//a[contains(@class, 'o_ewp_hotspot')]"
                "[@data-ewp-room-id='%s']" % self.room_beta.id
            )[0]
            words = page.xpath(
                "//a[@data-ewp-room-id='%s']"
                "//*[contains(@class, 'o_ewp_room_position')]"
                % self.room_beta.id
            )[0]
            return area.get("style"), " ".join(words.text_content().split())

        style, words = area_and_words()
        self.assertNotIn("--ewp-room-rotate", style)
        self.room_beta.pos_rotation = 270
        turned_style, turned_words = area_and_words()
        self.assertIn("--ewp-room-rotate:-90.00deg", turned_style)
        self.assertEqual(turned_style, style + ";--ewp-room-rotate:-90.00deg")
        self.assertEqual(turned_words, words)
        self.room_beta.pos_rotation = 12.5
        self.assertIn("--ewp-room-rotate:12.50deg", area_and_words()[0])
        controller = EventWebappController()
        self.assertEqual(controller._ewp_rotate_style(0.0), "")
        self.assertEqual(controller._ewp_rotate_style(False), "")
        self.assertEqual(controller._ewp_rotate_style(float("nan")), "")
        self.assertEqual(
            controller._ewp_rotate_style(-45), ";--ewp-room-rotate:-45.00deg"
        )

    def test_badge_text_contrasts_with_the_room_colour(self):
        controller = EventWebappController()
        for color, ink in (
            ("#FFFFFF", "#15191E"),
            ("#fff", "#15191E"),
            ("#F5C04A", "#15191E"),
            ("#2A9D8F", "#15191E"),
            ("#1D5FA8", "#FFFFFF"),
            ("#15191E", "#FFFFFF"),
            ("#B4470F", "#FFFFFF"),
        ):
            with self.subTest(color=color):
                self.assertEqual(controller._ewp_text_color(color), ink)

    def test_portal_outside_window_gets_closed_page(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s" % self.day_future.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Future Test Day", response.text)
        self.assertIn("not open yet", response.text)
        self.assertNotIn("Gamma Room", response.text)

    def test_moderator_outside_window_gets_preview(self):
        self.authenticate("ewp_webapp_moderator", "ewp_webapp_moderator")
        response = self._get("/webapp_event/%s" % self.day_future.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Gamma Room", response.text)
        self.assertIn("Preview outside opening hours", response.text)

    def test_preview_banner_follows_the_user_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.ref("base.module_event_webapp_plan")._update_translations(
            ["fr_CA"]
        )
        self.moderator_user.lang = "fr_CA"
        self.authenticate("ewp_webapp_moderator", "ewp_webapp_moderator")
        response = self._get("/webapp_event/%s" % self.day_future.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Aperçu en dehors des heures", response.text)
        self.assertNotIn("Preview outside opening hours", response.text)

    def test_room_page_adds_member_and_embeds_chat(self):
        channel = self.room_alpha.channel_id
        self.assertTrue(
            channel, "a room gets its discussion channel on creation"
        )
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get(
            "/webapp_event/%s/room/%s" % (self.day_open.id, self.room_alpha.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("<iframe", response.text)
        self.assertIn("/discuss/channel/%s" % channel.id, response.text)
        members = self.env["discuss.channel.member"].search(
            [
                ("channel_id", "=", channel.id),
                ("partner_id", "=", self.portal_user.partner_id.id),
            ]
        )
        self.assertEqual(len(members), 1)
        # A second visit keeps a single membership.
        self._get(
            "/webapp_event/%s/room/%s" % (self.day_open.id, self.room_alpha.id)
        )
        self.assertEqual(
            self.env["discuss.channel.member"].search_count(
                [
                    ("channel_id", "=", channel.id),
                    ("partner_id", "=", self.portal_user.partner_id.id),
                ]
            ),
            1,
        )

    def test_portal_room_page_before_the_window_is_closed(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        self._assert_closed_room_page(
            self.day_future, self.room_gamma, self.portal_user, "not open yet"
        )

    def test_portal_room_page_after_the_window_is_closed(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        self._assert_closed_room_page(
            self.day_ended, self.room_delta, self.portal_user, "is over"
        )

    def test_anonymous_cannot_open_a_room_chat(self):
        # The Discuss page of a room channel is auth="public": the record
        # rule alone keeps anonymous visitors out, for every room. The
        # session pins the test database, and a channel open to everybody
        # answers 200, so a 404 below comes from the record rule.
        self.authenticate(None, None)
        open_channel = self.env["discuss.channel"].create(
            {"name": "Open test channel", "channel_type": "channel"}
        )
        open_channel.group_public_id = False
        response = self._get("/discuss/channel/%s" % open_channel.id)
        self.assertEqual(response.status_code, 200)
        for room in (
            self.room_alpha,
            self.room_beta,
            self.room_gamma,
            self.room_delta,
        ):
            with self.subTest(room=room.name):
                response = self._get(
                    "/discuss/channel/%s" % room.channel_id.id
                )
                self.assertEqual(response.status_code, 404)
        uuid = self.room_alpha.channel_id.uuid
        response = self._get(
            "/chat/%s/%s" % (self.room_alpha.channel_id.id, uuid)
        )
        self.assertEqual(response.status_code, 404)

    def test_room_chat_opens_through_the_room_page_only(self):
        alpha_url = "/discuss/channel/%s" % self.room_alpha.channel_id.id
        beta_url = "/discuss/channel/%s" % self.room_beta.channel_id.id
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        self.assertEqual(self._get(alpha_url).status_code, 404)
        self._get(self._room_url(self.day_open, self.room_alpha))
        self.assertIn(
            self.room_alpha.access_group_id, self.portal_user.groups_id
        )
        self.assertFalse(self.portal_user._is_internal())
        self.assertEqual(self._get(alpha_url).status_code, 200)
        # The group of one room opens no other room.
        self.assertEqual(self._get(beta_url).status_code, 404)

        # Once the day is over, the chat stays open to the visitor; the
        # room page itself is closed.
        self.day_open.date_end = fields.Datetime.now() - timedelta(minutes=1)
        self.assertEqual(self._get(alpha_url).status_code, 200)
        self.assertEqual(
            self._member_count(self.room_alpha, self.portal_user), 1
        )
        response = self._get(self._room_url(self.day_open, self.room_alpha))
        self.assertIn("is over", response.text)
        self.assertNotIn("<iframe", response.text)

    def test_moderator_reads_every_room_chat_without_entering(self):
        self.authenticate("ewp_webapp_moderator", "ewp_webapp_moderator")
        for room in (
            self.room_alpha,
            self.room_beta,
            self.room_gamma,
            self.room_delta,
        ):
            with self.subTest(room=room.name):
                response = self._get(
                    "/discuss/channel/%s" % room.channel_id.id
                )
                self.assertEqual(response.status_code, 200)

    def test_internal_user_inside_the_window(self):
        self.authenticate("ewp_webapp_internal", "ewp_webapp_internal")
        response = self._get("/webapp_event")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alpha Hall", response.text)
        self.assertNotIn("Preview outside opening hours", response.text)
        response = self._get(self._room_url(self.day_open, self.room_alpha))
        self.assertEqual(response.status_code, 200)
        self.assertIn("<iframe", response.text)
        self.assertEqual(
            self._member_count(self.room_alpha, self.internal_user), 1
        )
        response = self._get("/webapp_event/%s" % self.day_future.id)
        self.assertIn("not open yet", response.text)
        self.assertNotIn("Gamma Room", response.text)

    def test_room_of_another_day_is_not_found(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get(
            "/webapp_event/%s/room/%s" % (self.day_open.id, self.room_gamma.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_plan_image_access(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s/plan" % self.day_future.id)
        self.assertEqual(response.status_code, 403)
        response = self._get("/webapp_event/%s/plan" % self.day_open.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["Content-Type"].startswith("image/"))

    def test_raffles_json_hides_winner_email(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s/raffles" % self.day_open.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(WINNER_EMAIL, response.text)
        data = json.loads(response.text)
        draws = data["raffles"][0]["draws"]
        self.assertEqual(draws[0]["winner_name"], "Grace Testwinner")
        self.assertFalse(draws[1]["drawn"])
        self.assertIn("Grace Testwinner", data["html"])
        self.assertTrue(data["signature"])

    def test_raffles_json_forbidden_outside_window(self):
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event/%s/raffles" % self.day_future.id)
        self.assertEqual(response.status_code, 403)

    def test_page_without_day_has_a_translated_title(self):
        self.env["event.webapp"].search([]).active = False
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event")
        self.assertIn("<title>No event day</title>", response.text)

        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.ref("base.module_event_webapp_plan")._update_translations(
            ["fr_CA"]
        )
        # The session takes the language of the user at login.
        self.portal_user.lang = "fr_CA"
        self.authenticate("ewp_webapp_portal", "ewp_webapp_portal")
        response = self._get("/webapp_event")
        page = lxml_html.fromstring(response.text)
        self.assertEqual(
            page.xpath("//title")[0].text, "Aucune journée d'événement"
        )
        # The page language follows the user's.
        self.assertEqual(page.xpath("//html/@lang"), ["fr-CA"])

    def test_pwa_files_are_public(self):
        self.authenticate(None, None)
        response = self._get("/webapp_event/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        manifest = json.loads(response.text)
        self.assertEqual(manifest["start_url"], "/webapp_event")
        # A theme module may change the colours: each stays a hex colour.
        self.assertRegex(manifest["theme_color"], r"^#[0-9A-Fa-f]{6}$")
        self.assertRegex(manifest["background_color"], r"^#[0-9A-Fa-f]{6}$")
        self.assertEqual(len(manifest["icons"]), 2)
        response = self._get("/webapp_event/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["Content-Type"])
