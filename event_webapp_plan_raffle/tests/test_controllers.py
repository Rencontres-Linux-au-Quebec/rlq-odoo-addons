# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""HTTP tests of the raffle prize blocks of the web app: the "My prize"
card (hidden without a draw, the prize link of its own winner only, the
states of the claim with the pick-up location, the e-mail and the
tracking number), its JSON route (anonymous, closed day, unknown day),
the public name form (CSRF, own contact only, the raffle block), the
"On site" toggle (CSRF, own registrations only, the attendance mode
unchanged, absent with its route while the setting "On-site card" is
off), the text-only mode and French. The class ticks the setting; the
test of the setting off clears it.

Every name below is invented for the tests."""

import json
import re
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

from ..models.res_config_settings import PARAM_ONSITE_CARD
from .common import PrizeWebappMixin

# In the browser: wait(fn, ms) polls `fn` until it returns a truthy value,
# or throws after `ms`; prizeRow() resolves to the row "My prize" of the
# automatic updates once it shows; seconds(row) reads its countdown, whose
# spaces are no-break spaces (\s in a JS pattern).
JS_PRIZE_ROW = """
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
const prizeRow = () => wait(() => {
    const el = document.querySelector('#o_ewp_refresh li[data-ewp-refresh="my_prize"]');
    return el && !el.hidden && el;
});
const seconds = (row) => {
    const text = row.querySelector(".o_ewp_refresh_next").textContent;
    const match = text.match(/^Next in (?:(\\d+)\\smin\\s)?(\\d+)\\ss$/);
    return match ? Number(match[1] || 0) * 60 + Number(match[2]) : NaN;
};
"""


@tagged("post_install", "-at_install")
class TestPrizeWebappControllers(PrizeWebappMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._webapp_setup("ewp_prize_http")
        cls.winner = cls._participant_of(cls.winner_user)
        cls.other = cls._participant_of(cls.other_user)
        cls.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _get(self, url, **kwargs):
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False, **kwargs)
        self.env.invalidate_all()
        return response

    def _page(self, url=None):
        response = self._get(url or self.home)
        self.assertEqual(response.status_code, 200)
        return lxml_html.fromstring(response.text), response.text

    def _json(self, path="/my_prize"):
        response = self._get(self.home + path)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _csrf(self, page):
        return page.xpath("//input[@name='csrf_token']/@value")[0]

    def _post(self, path, data, as_json=False):
        self.env.flush_all()
        headers = {"Accept": "application/json"} if as_json else {}
        response = self.url_open(
            self.home + path,
            data=data,
            headers=headers,
            allow_redirects=False,
        )
        self.env.invalidate_all()
        return response

    def _items(self, page):
        return page.xpath("//li[contains(@class, 'ewp_prize_item')]")

    def _item(self, page, draw):
        items = page.xpath(
            "//li[contains(@class, 'ewp_prize_item')]"
            f"[@data-ewp-prize-draw='{draw.id}']"
        )
        self.assertEqual(len(items), 1)
        return items[0]

    def _text(self, element):
        return re.sub(r"\s+", " ", element.text_content()).strip()

    def _card(self, page):
        cards = page.xpath("//section[@id='ewp_prize_card']")
        self.assertEqual(len(cards), 1)
        return cards[0]

    # ------------------------------------------------------------------
    # "My prize" card
    # ------------------------------------------------------------------
    def test_card_is_hidden_without_a_draw(self):
        self._login(self.other_user)
        page, _text = self._page()
        box = page.xpath("//div[@id='ewp_prize_box']")[0]
        self.assertEqual(box.get("hidden"), "hidden")
        self.assertFalse(len(box))
        # No heading of an empty card enters the outline of the page.
        self.assertFalse(page.xpath("//section[@id='ewp_prize_card']"))
        self.assertNotIn(
            "My prize", [h.text_content() for h in page.xpath("//main//h2")]
        )
        self.assertFalse(self._items(page))
        self.assertFalse(
            page.xpath("//form[contains(@class, 'ewp_prize_name_form')]")
        )
        data = self._json()
        self.assertEqual(data["count"], 0)
        self.assertNotIn("ewp_prize_item", data["html"])

    def test_open_link_belongs_to_its_winner_only(self):
        draw = self._draw(self.winner, band_id=self.band_a.id)
        token = draw._claim_link_issue()
        self._login(self.winner_user)
        page, _text = self._page()
        self._card(page)
        box = page.xpath("//div[@id='ewp_prize_box']")[0]
        self.assertIsNone(box.get("hidden"))
        item = self._item(page, draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "open")
        self.assertTrue(item.get("data-ewp-prize-deadline"))
        links = item.xpath(".//a[contains(@class, 'ewp_prize_choose')]")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].get("href"), draw.sudo().claim_link_url)
        self.assertIn(token, links[0].get("href"))
        self.assertIn("Choose my prize", self._text(links[0]))
        self.assertIn("Choose your prize before", self._text(item))
        self.assertIn(f"Morning, draw {draw.sequence}", self._text(item))
        self.assertEqual(self._json()["count"], 1)
        # Another attendee sees neither the draw nor its token.
        self._login(self.other_user)
        _page, text = self._page()
        self.assertNotIn(token, text)
        data = self._json()
        self.assertEqual(data["count"], 0)
        self.assertNotIn(token, json.dumps(data))
        # The link closes: the button goes, the state says it.
        self._expire(draw)
        self._login(self.winner_user)
        page, text = self._page()
        self.assertNotIn(token, text)
        item = self._item(page, draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "link_expired")
        self.assertFalse(
            item.xpath(".//a[contains(@class, 'ewp_prize_choose')]")
        )

    def test_reserved_pickup_says_the_location(self):
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        self._login(self.winner_user)
        page, _text = self._page()
        item = self._item(page, draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "reserved")
        text = self._text(item)
        self.assertIn("Handover Mug", text)
        self.assertIn("Sponsor Example", text)
        self.assertIn("Pick up your prize at Table 7, hall B.", text)
        self.assertNotIn("handover.organizer", text)
        draw._prize_hand_over()
        page, _text = self._page()
        item = self._item(page, draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "delivered")
        self.assertIn("Your prize was handed over to you.", self._text(item))

    def test_virtual_prize_and_shipping_states(self):
        virtual = self._draw(self.winner)
        virtual._prize_claim(self.ebook)
        self._login(self.winner_user)
        page, _text = self._page()
        self.assertIn(
            "Your prize will be sent to you by email.",
            self._text(self._item(page, virtual)),
        )
        virtual._prize_send_virtual("<p>Read it.</p>", code="CODE-77")
        page, text = self._page()
        self.assertIn(
            "Your prize was sent to you by email.",
            self._text(self._item(page, virtual)),
        )
        self.assertNotIn("CODE-77", text)
        # A physical prize to a winner who is not on site is shipped.
        remote_user = self._portal_user("ewp_prize_http_remote", "Rémi Remote")
        remote = self._participant_of(remote_user, attended=False)
        remote_draw = self._draw(remote)
        remote_draw._prize_claim(self.mug)
        self._login(remote_user)
        page, _text = self._page()
        item = self._item(page, remote_draw)
        self.assertIn("Your prize will be shipped to you.", self._text(item))
        remote_draw._prize_ship("TRK-4242", "Postal Test")
        page, _text = self._page()
        item = self._item(page, remote_draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "shipped")
        self.assertIn("Your prize was shipped.", self._text(item))
        self.assertEqual(
            item.xpath(".//span[@class='ewp_prize_tracking_ref']")[0].text,
            "TRK-4242",
        )
        self.assertIn("Postal Test", self._text(item))
        remote_draw.action_prize_received()
        page, _text = self._page()
        item = self._item(page, remote_draw)
        self.assertEqual(item.get("data-ewp-prize-state"), "delivered")
        self.assertIn("You received your prize.", self._text(item))
        self.assertIn("TRK-4242", self._text(item))

    def test_declined_and_waiting_states(self):
        waiting = self._draw(self.winner)
        declined = self._draw(self.winner)
        declined._prize_claim(self.mug)
        declined._prize_decline("Not for me")
        self._login(self.winner_user)
        page, _text = self._page()
        self.assertEqual(
            self._item(page, waiting).get("data-ewp-prize-state"), "waiting"
        )
        self.assertIn(
            "You declined this prize.", self._text(self._item(page, declined))
        )

    def test_json_route_access(self):
        draw = self._draw(self.winner)
        draw._claim_link_issue()
        # A visitor is sent to the login page.
        response = self._get(self.home + "/my_prize")
        self.assertIn(response.status_code, (302, 303))
        self.assertIn("/web/login", response.headers["Location"])
        self._login(self.winner_user)
        self.assertEqual(
            self._get("/webapp_event/999999/my_prize").status_code, 404
        )
        self.day.date_end = fields.Datetime.now() - timedelta(minutes=5)
        self.day.date_start = fields.Datetime.now() - timedelta(hours=5)
        self.assertEqual(self._get(self.home + "/my_prize").status_code, 403)
        page, text = self._page()
        self.assertNotIn("ewp_prize_card", text)
        csrf = self._csrf(page)
        for path, data in (
            ("/public_name", {"public_name": "Closed"}),
            ("/presence", {"on_site": "1"}),
        ):
            data["csrf_token"] = csrf
            self.assertEqual(self._post(path, data).status_code, 403)
        self.assertFalse(self.winner_user.partner_id.raffle_public_name)
        self.assertFalse(self.winner.registration_id.attendance_declared)

    # ------------------------------------------------------------------
    # Public name
    # ------------------------------------------------------------------
    def test_public_name_form(self):
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        other_partner = self.other_user.partner_id
        self._login(self.winner_user)
        page, _text = self._page()
        form = page.xpath("//form[contains(@class, 'ewp_prize_name_form')]")[0]
        self.assertEqual(form.get("action"), self.home + "/public_name")
        self.assertEqual(
            page.xpath("//input[@id='ewp_prize_name_input']/@maxlength"),
            ["64"],
        )
        # Without the CSRF token: refused, nothing written.
        response = self._post("/public_name", {"public_name": "No Token"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.winner_user.partner_id.raffle_public_name)
        # The ids of the request are ignored: the own contact only.
        response = self._post(
            "/public_name",
            {
                "csrf_token": self._csrf(page),
                "public_name": "  Tux   Rider ",
                "partner_id": other_partner.id,
                "draw_id": draw.id,
            },
        )
        self.assertEqual(response.status_code, 303)
        self.assertTrue(
            response.headers["Location"].endswith("#ewp_prize_card")
        )
        self.assertEqual(
            self.winner_user.partner_id.raffle_public_name, "Tux Rider"
        )
        self.assertFalse(other_partner.raffle_public_name)
        page, _text = self._page()
        self.assertEqual(
            page.xpath("//p[@class='ewp_prize_notice']")[0].text,
            "Your public name is saved.",
        )
        self.assertEqual(
            page.xpath("//strong[@class='ewp_prize_shown_name']")[0].text,
            "Tux Rider",
        )
        # The message shows once.
        _page, text = self._page()
        self.assertNotIn("Your public name is saved.", text)
        # The raffle block of the web app and the winners page use it.
        self.day.raffle_ids = [Command.set(self.raffle.ids)]
        raffles = self._json("/raffles")
        names = [
            d["winner_name"] for r in raffles["raffles"] for d in r["draws"]
        ]
        self.assertIn("Tux Rider", names)
        self.assertEqual(draw._prize_public_name(), "Tux Rider")
        # As JSON: the new card body and the message; empty clears it.
        response = self._post(
            "/public_name",
            {"csrf_token": self._csrf(page), "public_name": " "},
            as_json=True,
        )
        data = response.json()
        self.assertEqual(data["message"], "Your public name is saved.")
        self.assertEqual(data["count"], 1)
        self.assertIn("Wanda Winner", data["html"])
        self.assertFalse(self.winner_user.partner_id.raffle_public_name)

    def test_public_name_reaches_the_order_contact_without_account(self):
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        order = draw.sudo().prize_order_id
        guest = self.env["res.partner"].create({"name": "Guest Contact"})
        order.partner_id = guest
        self._login(self.winner_user)
        page, _text = self._page()
        self._post(
            "/public_name",
            {"csrf_token": self._csrf(page), "public_name": "Penguin"},
        )
        self.assertEqual(guest.raffle_public_name, "Penguin")
        self.assertEqual(draw._prize_public_name(), "Penguin")
        # A contact of another account is never changed.
        order.partner_id = self.other_user.partner_id
        self._post(
            "/public_name",
            {"csrf_token": self._csrf(page), "public_name": "Puffin"},
        )
        self.assertEqual(
            self.winner_user.partner_id.raffle_public_name, "Puffin"
        )
        self.assertFalse(self.other_user.partner_id.raffle_public_name)

    # ------------------------------------------------------------------
    # On site
    # ------------------------------------------------------------------
    def test_presence_toggle(self):
        remote = self._participant_of(self.winner_user, attended=False)
        registrations = self.winner.registration_id | remote.registration_id
        self._login(self.winner_user)
        page, _text = self._page()
        button = page.xpath("//button[@id='ewp_presence_toggle']")[0]
        self.assertEqual(button.get("aria-pressed"), "false")
        self.assertEqual(button.get("value"), "1")
        response = self._post("/presence", {"on_site": "1"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(any(registrations.mapped("attendance_declared")))
        response = self._post(
            "/presence", {"csrf_token": self._csrf(page), "on_site": "1"}
        )
        self.assertEqual(response.status_code, 303)
        self.assertTrue(all(registrations.mapped("attendance_declared")))
        self.assertTrue(all(registrations.mapped("attendance_declared_date")))
        self.assertFalse(self.other.registration_id.attendance_declared)
        # Information only: the attendance mode follows the scan.
        self.assertEqual(remote.attendance_mode, "virtual")
        self.assertEqual(remote.registration_id.state, "open")
        page, _text = self._page()
        button = page.xpath("//button[@id='ewp_presence_toggle']")[0]
        self.assertEqual(button.get("aria-pressed"), "true")
        self.assertEqual(button.get("value"), "0")
        self.assertIn(
            "Declared at",
            self._text(page.xpath("//section[@id='ewp_presence']")[0]),
        )
        self.assertEqual(
            page.xpath("//section[@id='ewp_presence']//p[@role='status']")[
                0
            ].text,
            "You are marked on site.",
        )
        data = self._post(
            "/presence",
            {"csrf_token": self._csrf(page), "on_site": "0"},
            as_json=True,
        ).json()
        self.assertEqual(data["message"], "You are no longer marked on site.")
        self.assertFalse(data["declared"])
        self.assertIn('aria-pressed="false"', data["html"])
        self.assertFalse(any(registrations.mapped("attendance_declared")))
        self.assertEqual(remote.attendance_mode, "virtual")
        self.assertEqual(self.winner.attendance_mode, "onsite")

    def test_presence_off_hides_the_card_and_refuses_the_route(self):
        registration = self.winner.registration_id
        self.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, False)
        self._login(self.winner_user)
        page, text = self._page()
        self.assertNotIn("ewp_presence", text)
        self.assertNotIn("I am on site", text)
        csrf = self._csrf(page)
        for as_json in (False, True):
            response = self._post(
                "/presence",
                {"csrf_token": csrf, "on_site": "1"},
                as_json=as_json,
            )
            self.assertEqual(response.status_code, 404)
        self.assertFalse(registration.attendance_declared)
        # A declaration saved while the card was on is kept, and shows
        # again once the card is back.
        self.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, True)
        page, _text = self._page()
        response = self._post(
            "/presence", {"csrf_token": self._csrf(page), "on_site": "1"}
        )
        self.assertEqual(response.status_code, 303)
        self.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, False)
        _page, text = self._page()
        self.assertNotIn("ewp_presence", text)
        self.assertTrue(registration.attendance_declared)
        self.assertTrue(registration.attendance_declared_date)
        self.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, True)
        page, _text = self._page()
        button = page.xpath("//button[@id='ewp_presence_toggle']")[0]
        self.assertEqual(button.get("aria-pressed"), "true")

    def test_presence_needs_a_registration_of_the_day(self):
        user = self._portal_user("ewp_prize_http_nobody", "Nora Nobody")
        self._login(user)
        page, text = self._page()
        self.assertNotIn("ewp_presence", text)
        response = self._post(
            "/presence", {"csrf_token": self._csrf(page), "on_site": "1"}
        )
        self.assertEqual(response.status_code, 303)
        self.assertFalse(
            self.env["event.registration"].search(
                [("attendance_declared", "=", True)]
            )
        )

    # ------------------------------------------------------------------
    # Display modes and language
    # ------------------------------------------------------------------
    def test_text_only_mode_keeps_the_blocks(self):
        draw = self._draw(self.winner)
        draw._claim_link_issue()
        self.winner_user.ewp_text_only = True
        self._login(self.winner_user)
        page, _text = self._page()
        self.assertIn("o_ewp_text_only", page.xpath("//body/@class")[0])
        self.assertEqual(
            self._item(page, draw).get("data-ewp-prize-state"), "open"
        )
        self.assertTrue(page.xpath("//button[@id='ewp_presence_toggle']"))

    def test_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        for module in (
            "event_webapp_plan",
            "event_raffle_prize_handover",
            "event_webapp_plan_raffle",
        ):
            self.env.ref(f"base.module_{module}")._update_translations(
                ["fr_CA"]
            )
        self.winner_user.lang = "fr_CA"
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        link_draw = self._draw(self.winner)
        link_draw._claim_link_issue()
        self._login(self.winner_user)
        page, _text = self._page()
        card = self._card(page)
        self.assertEqual(card.xpath(".//h2")[0].text, "Mon prix")
        self.assertIn("Table 7, hall B", self._text(self._item(page, draw)))
        self.assertNotIn(
            "Pick up your prize", self._text(self._item(page, draw))
        )
        link = self._item(page, link_draw).xpath(
            ".//a[contains(@class, 'ewp_prize_choose')]"
        )[0]
        self.assertIn("Choisir mon prix", self._text(link))
        self.assertIn(
            "Je suis sur place",
            self._text(page.xpath("//button[@id='ewp_presence_toggle']")[0]),
        )

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
        """The automatic updates of the home page have the row "My prize",
        for a winner and for a user whose card is still empty and hidden
        (it polls all the same), in French too."""
        self._draw(self.winner)
        for user in (self.winner_user, self.other_user):
            with self.subTest(user=user.name):
                self._login(user)
                page, _text = self._page()
                self.assertIn(
                    ("my_prize", "My prize"), self._refresh_rows(page)
                )
        self.env["res.lang"]._activate_lang("fr_CA")
        for module in ("event_webapp_plan", "event_webapp_plan_raffle"):
            self.env.ref(f"base.module_{module}")._update_translations(
                ["fr_CA"]
            )
        self.other_user.lang = "fr_CA"
        self._login(self.other_user)
        page, _text = self._page()
        self.assertIn(("my_prize", "Mon prix"), self._refresh_rows(page))

    def test_automatic_updates_count_to_the_link_deadline(self):
        """In the browser, the row "My prize" counts down to the earliest
        planned request: the deadline of an open link when it comes before
        the next minute, two seconds after a raffle draw."""
        draw = self._draw(self.winner)
        draw._claim_link_issue()
        draw.sudo().claim_deadline = fields.Datetime.now() + timedelta(
            seconds=40
        )
        self.env.flush_all()
        code = """(async () => {""" + JS_PRIZE_ROW + """
            const row = await prizeRow();
            const next = row.querySelector(".o_ewp_refresh_next");
            await wait(() => seconds(row) > 0);
            if (seconds(row) > 42 || seconds(row) < 15) {
                throw new Error("not the deadline: " + next.textContent);
            }
            if (!row.querySelector(".o_ewp_refresh_last").textContent.startsWith("Updated")) {
                throw new Error("no last update");
            }
            document.dispatchEvent(new CustomEvent("ewp:raffle-drawn", {detail: {}}));
            await wait(() => seconds(row) <= 2, 1500);
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            self.home,
            code,
            ready="document.readyState === 'complete'",
            login=self.winner_user.login,
        )

    def test_automatic_updates_follow_the_minute_tick(self):
        """The row "My prize" counts the next minute from the moment the
        interval really runs, not from the page load: with Date.now() 25 s
        ahead of the timers (a device that slept, a clock that changed),
        the countdown starts again from a full minute after the tick. The
        test waits for that tick, a minute after the page load."""
        code = """(async () => {""" + JS_PRIZE_ROW + """
            const row = await prizeRow();
            const last = row.querySelector(".o_ewp_refresh_last");
            const loaded = Date.parse(last.getAttribute("datetime"));
            const realNow = Date.now.bind(Date);
            Date.now = () => realNow() + 25000;
            await wait(() => Date.parse(last.getAttribute("datetime")) > loaded, 75000);
            await wait(() => row.dataset.ewpRefreshState === "running");
            if (!(seconds(row) >= 55)) {
                throw new Error("not from the tick: " + row.querySelector(".o_ewp_refresh_next").textContent);
            }
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            self.home,
            code,
            ready="document.readyState === 'complete'",
            login=self.other_user.login,
            timeout=120,
        )

    def test_raffle_listed_on_the_day_and_other_events(self):
        event_b = self.env["event.event"].create(
            {
                "name": "Prize Listed Event",
                "date_begin": "2026-03-01 09:00:00",
                "date_end": "2026-03-01 18:00:00",
            }
        )
        raffle_b = self.env["event.raffle"].create(
            {"name": "Listed", "event_id": event_b.id}
        )
        draw = self._draw(
            self._participant_of(self.winner_user, raffle=raffle_b)
        )
        self._login(self.winner_user)
        _page, text = self._page()
        self.assertNotIn(f'data-ewp-prize-draw="{draw.id}"', text)
        self.day.raffle_ids = [Command.set(raffle_b.ids)]
        page, _text = self._page()
        self._item(page, draw)

    # ------------------------------------------------------------------
    # Raffle block of the web app
    # ------------------------------------------------------------------
    def _block_draw(self, page, draw):
        items = page.xpath(f"//li[@data-ewp-draw-id='{draw.id}']")
        self.assertEqual(len(items), 1, f"draw {draw.id} in the block")
        return items[0]

    def _block_prize(self, item):
        prize = item.xpath(".//span[contains(@class, 'o_ewp_draw_prize')]")[0]
        return self._text(prize), prize.get("data-ewp-prize-status")

    def test_raffle_block_shows_a_winner_who_has_not_chosen(self):
        """A raffle listed on the day shows its winner once drawn, with
        the prize to choose, then with the prize once chosen."""
        self.day.raffle_ids = [Command.set(self.raffle.ids)]
        self.raffle.prize_band_id = self.band_a
        result = self.raffle.action_draw_next()
        draw = self.env["event.raffle.draw"].browse(result["draw_id"])
        draw._claim_link_issue()
        self._login(self.other_user)
        page, _text = self._page()
        self.assertTrue(
            page.xpath("//section[contains(@class, 'o_ewp_raffles_card')]")
        )
        item = self._block_draw(page, draw)
        self.assertIn("o_ewp_draw_done", item.get("class"))
        self.assertIn(
            draw.winner_name,
            self._text(item.xpath(".//span[@class='o_ewp_winner_name']")[0]),
        )
        self.assertEqual(
            self._block_prize(item), ("Group A, prize to choose", "to_choose")
        )
        data = self._json("/raffles")
        line = data["raffles"][0]["draws"][0]
        self.assertEqual(
            (line["id"], line["drawn"], line["prize"], line["prize_status"]),
            (draw.id, True, "Group A, prize to choose", "to_choose"),
        )
        self.assertIn("Group A, prize to choose", data["html"])
        signature = data["signature"]
        # The choice changes the line and the signature of the block.
        draw._prize_claim(self.mug)
        data = self._json("/raffles")
        line = data["raffles"][0]["draws"][0]
        self.assertEqual(
            (line["prize"], line["prize_status"]), ("Handover Mug", "chosen")
        )
        self.assertNotEqual(data["signature"], signature)

    def test_raffle_block_says_what_became_of_each_prize(self):
        self.day.raffle_ids = [Command.set(self.raffle.ids)]
        declined = self._draw(self.winner)
        declined._claim_link_issue()
        declined._claim_link_decline("Not my size")
        expired = self._draw(self.other)
        expired.sudo().claim_state = "expired"
        absent = self._draw(self.winner, is_absent=True)
        self._login(self.winner_user)
        page, text = self._page()
        self.assertEqual(
            self._block_prize(self._block_draw(page, declined)),
            ("Prize declined", "declined"),
        )
        self.assertEqual(
            self._block_prize(self._block_draw(page, expired)),
            ("No prize chosen", "expired"),
        )
        # An absent draw keeps the line of event_webapp_plan.
        item = self._block_draw(page, absent)
        self.assertIn("o_ewp_draw_absent", item.get("class"))
        self.assertIsNone(self._block_prize(item)[1])
        self.assertNotIn("Not my size", text)
        self.assertNotIn("Not my size", json.dumps(self._json("/raffles")))

    def test_raffle_block_leaves_out_a_raffle_not_listed_on_the_day(self):
        """The raffle block lists the raffles listed on the day only: a
        raffle of the day's event left off the day, whose winners page is
        not published, shows neither its draws nor its winners, in the
        page or in its JSON route, until it is listed on the day."""
        # The day holds the current moment, the default planned date of a
        # new raffle: the test raffles are taken off the day, and this one
        # has no date, so that nothing lists it on the day by itself.
        self.day.raffle_ids = [Command.clear()]
        volunteers = self.env["event.raffle"].create(
            {
                "name": "Volunteers Raffle",
                "event_id": self.event.id,
                "date_planned": False,
            }
        )
        self.assertFalse(volunteers.is_test)
        self.assertFalse(self.event.raffle_winners_published)
        draw = self._draw(
            self._participant_of(self.other_user, raffle=volunteers)
        )
        self.assertFalse(self.day.raffle_ids)
        self._login(self.winner_user)
        page, text = self._page()
        self.assertNotIn(f'data-ewp-draw-id="{draw.id}"', text)
        self.assertNotIn("Volunteers Raffle", text)
        self.assertFalse(
            page.xpath("//section[contains(@class, 'o_ewp_raffles_card')]")
        )
        data = self._json("/raffles")
        self.assertEqual(data["raffles"], [])
        self.assertNotIn(draw.winner_name, json.dumps(data))
        self.day.raffle_ids = [Command.set(volunteers.ids)]
        page, _text = self._page()
        self._block_draw(page, draw)
        data = self._json("/raffles")
        self.assertEqual(
            [d["id"] for r in data["raffles"] for d in r["draws"]], [draw.id]
        )

    def test_raffle_block_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.ref(
            "base.module_event_raffle_prize_handover"
        )._update_translations(["fr_CA"])
        self.other_user.lang = "fr_CA"
        self.band_a.name = "Groupe de prix A"
        self.day.raffle_ids = [Command.set(self.raffle.ids)]
        draw = self._draw(self.winner, band_id=self.band_a.id)
        self._login(self.other_user)
        page, _text = self._page()
        self.assertEqual(
            self._block_prize(self._block_draw(page, draw)),
            ("Groupe de prix A, prix à choisir", "to_choose"),
        )
