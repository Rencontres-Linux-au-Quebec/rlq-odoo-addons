# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Browser tests: the embedded room chat, the conference frame left and
joined again, the focus ring and the focus after the page loads again, the
text-only "Show the video conference" button, the live rooms of the home
page, the place of the lead cards of a theme on a phone and on a wide
screen, and the plan editor of the form.

They drive a headless Chrome through `HttpCase.browser_js`, which fails the
test on any console error, and skip themselves when Chrome is absent. A
test that follows the page script across a page load opens the page in a
frame of a static page of the module (JS_FRAME): the frame shares the
sessionStorage of the tab and the test code outlives the load. Every name
below is invented for the tests."""

import base64
import io
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from odoo import Command, fields
from odoo.addons.event_webapp_plan.models import bbb_client
from odoo.addons.event_webapp_plan.models.event_webapp_room import (
    PARAM_BBB_DISPLAY,
    PARAM_BBB_SECRET,
    PARAM_BBB_URL,
)
from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser, new_test_user
from PIL import Image

from .test_bbb import SECRET, SERVER, FakeNetwork, fake_network

# Same-origin page that stands in for the BigBlueButton client: the join
# URL is replaced by it, so the browser reaches no other host.
CLIENT_PATH = "/event_webapp_plan/static/description/icon.png"

# Polls `fn` until it returns a truthy value, or throws after `ms`.
JS_WAIT = """
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
"""


# check(ok, message) throws `message` when `ok` is falsy; sleep(ms).
JS_CHECK = """
const check = (ok, message) => {
    if (!ok) {
        throw new Error(message);
    }
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
"""

# Static page of the module that hosts the frames of JS_FRAME.
HOST_PAGE = "/event_webapp_plan/static/description/index.html"

# openFrame(url) loads `url` in a 1280 x 800 frame of the test page and
# resolves once its page script has started (data-ewp-motion on the body);
# nextPage(frame, doc) resolves once the frame shows a new page started the
# same way. ready(doc) tells whether that page script has started.
JS_FRAME = """
const ready = (doc) =>
    doc && doc.readyState === "complete" && doc.body && doc.body.dataset.ewpMotion;
const openFrame = async (url) => {
    const frame = document.createElement("iframe");
    frame.style.width = "1280px";
    frame.style.height = "800px";
    document.body.appendChild(frame);
    frame.src = url;
    await wait(() => frame.contentDocument.location.pathname === url.split("?")[0]
        && ready(frame.contentDocument));
    return frame;
};
const nextPage = async (frame, doc) => {
    await wait(() => frame.contentDocument !== doc && ready(frame.contentDocument));
    return frame.contentDocument;
};
// JSON answer of a stubbed fetch.
const jsonResponse = (data) =>
    new Response(JSON.stringify(data), {headers: {"Content-Type": "application/json"}});
// The focus is in the conference `frame` and a ring goes around the box
// of the frame, outside the box that clips the frame itself.
const ringShown = (frame) => {
    const box = frame.closest(".o_ewp_video");
    const style = box.ownerDocument.defaultView.getComputedStyle(box);
    return box.matches(":focus-within") && style.outlineStyle === "solid"
        && parseFloat(style.outlineWidth) >= 3 && parseFloat(style.outlineOffset) >= 0;
};
// Resolves once the chat frame of `doc` shows its composer, which takes
// the focus as it loads.
const chatLoaded = async (doc) => {
    const chat = doc.querySelector("iframe.o_ewp_chat");
    await wait(() => chat.contentDocument && chat.contentDocument.querySelector(".o-mail-Composer-input"));
    await sleep(500);
};
"""


@contextmanager
def emulated_media(*features):
    """Every page that browser_js opens matches the media `features`, pairs
    (name, value) such as ("prefers-color-scheme", "dark"), through the
    DevTools call Emulation.setEmulatedMedia."""
    navigate = ChromeBrowser.navigate_to
    params = {"features": [{"name": n, "value": v} for n, v in features]}

    def navigate_with_media(browser, url, wait_stop=False):
        browser._websocket_request("Emulation.setEmulatedMedia", params=params)
        return navigate(browser, url, wait_stop=wait_stop)

    with mock.patch.object(ChromeBrowser, "navigate_to", navigate_with_media):
        yield


def _png_b64(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 220, 230)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue())


@tagged("post_install", "-at_install")
class TestWebappBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The assertions read the English source strings: the test users
        # get English, which a database may have left inactive when it was
        # created in another language.
        cls.env["res.lang"]._activate_lang("en_US")
        now = fields.Datetime.now()
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_webapp_browser_portal",
            password="ewp_webapp_browser_portal",
            groups="base.group_portal",
            name="Portal Browser Test",
            lang="en_US",
        )
        cls.manager_user = new_test_user(
            cls.env,
            login="ewp_webapp_browser_manager",
            password="ewp_webapp_browser_manager",
            groups="base.group_user,"
            "event_webapp_plan.group_event_webapp_manager",
            name="Manager Browser Test",
            lang="en_US",
        )
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Browser Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "plan_image": _png_b64(400, 200),
                "room_ids": [
                    Command.create(
                        {
                            "name": "Epsilon Hall",
                            "pos_x": 5,
                            "pos_y": 5,
                            "pos_width": 10,
                            "pos_height": 10,
                        }
                    ),
                    Command.create({"name": "Zeta Lab"}),
                ],
            }
        )
        cls.room_hall = cls.day.room_ids.filtered(
            lambda r: r.name == "Epsilon Hall"
        )
        cls.room_lab = cls.day.room_ids - cls.room_hall

    def test_portal_user_sees_the_plan_and_its_rooms(self):
        code = "(async () => {" + JS_WAIT + """
            const image = await wait(() => {
                const img = document.querySelector("img.o_ewp_plan_image");
                return img && img.complete && img.naturalWidth > 0 && img;
            });
            const hotspots = document.querySelectorAll("a.o_ewp_hotspot");
            if (hotspots.length !== 1) {
                throw new Error("expected one room on the plan");
            }
            const link = document.querySelector(
                `a.o_ewp_room_link[data-ewp-room-id="${hotspots[0].dataset.ewpRoomId}"]`
            );
            link.dispatchEvent(new MouseEvent("mouseenter"));
            await wait(() => hotspots[0].classList.contains("o_ewp_hotspot_active"));
            if (document.querySelectorAll("a.o_ewp_room_link").length !== 2) {
                throw new Error("expected both rooms in the list");
            }
            // Theme hooks: page and day state copied to the body.
            await wait(() => document.body.dataset.ewpDayState === "open");
            if (document.body.dataset.ewpPage !== "home") {
                throw new Error("page name missing on the body");
            }
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            "/webapp_event/%s" % self.day.id,
            code,
            ready="document.readyState === 'complete'",
            login="ewp_webapp_browser_portal",
        )

    def test_portal_user_posts_in_the_embedded_chat(self):
        text = "Hello from the browser test"
        code = "(async () => {" + JS_WAIT + """
            const frame = document.querySelector("iframe.o_ewp_chat");
            const doc = () => frame.contentDocument;
            const input = await wait(
                () => doc() && doc().querySelector(".o-mail-Composer-input")
            );
            input.focus();
            input.value = %(text)r;
            input.dispatchEvent(
                new frame.contentWindow.Event("input", { bubbles: true })
            );
            const send = await wait(() => {
                const button = doc().querySelector(".o-mail-Composer-send");
                return button && !button.disabled && button;
            });
            send.click();
            await wait(() =>
                [...doc().querySelectorAll(".o-mail-Message-body")].some(
                    (el) => el.textContent.includes(%(text)r)
                )
            );
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """ % {"text": text}
        self.browser_js(
            "/webapp_event/%s/room/%s" % (self.day.id, self.room_hall.id),
            code,
            ready="document.readyState === 'complete'",
            login="ewp_webapp_browser_portal",
        )
        message = self.env["mail.message"].search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.room_hall.channel_id.id),
                ("author_id", "=", self.portal_user.partner_id.id),
            ]
        )
        self.assertEqual(len(message), 1)
        self.assertIn(text, message.body)

    def test_manager_draws_a_room_on_the_plan(self):
        code = "(async () => {" + JS_WAIT + """
            const tab = await wait(() =>
                document.querySelector(".o_notebook a[name='page_plan']")
            );
            tab.click();
            const editor = await wait(() =>
                document.querySelector(".o_ewp_plan_editor")
            );
            await wait(() => editor.querySelectorAll(".o_ewp_plan_room").length === 1);
            const button = [...editor.querySelectorAll(".list-group-item")].find(
                (el) => el.textContent.includes("Zeta Lab")
            );
            button.click();
            const surface = await wait(() =>
                editor.querySelector(".o_ewp_plan_surface.o_ewp_plan_drawing")
            );
            const box = surface.getBoundingClientRect();
            const at = (type, fx, fy) =>
                surface.dispatchEvent(
                    new PointerEvent(type, {
                        bubbles: true,
                        pointerId: 1,
                        pointerType: "mouse",
                        button: 0,
                        clientX: box.left + box.width * fx,
                        clientY: box.top + box.height * fy,
                    })
                );
            at("pointerdown", 0.25, 0.25);
            at("pointermove", 0.5, 0.5);
            at("pointerup", 0.75, 0.75);
            await wait(() => editor.querySelectorAll(".o_ewp_plan_room").length === 2);
            // A sideways swipe is thinner than the minimum size: it must
            // keep the area just drawn.
            at("pointerdown", 0.05, 0.9);
            at("pointerup", 0.6, 0.902);
            await new Promise((resolve) => setTimeout(resolve, 300));
            document.querySelector(".o_form_button_save").click();
            await wait(() => !document.querySelector(".o_form_status_indicator_buttons:not(.invisible) .o_form_button_save"));
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            "/odoo/action-event_webapp_plan.event_webapp_action/%s"
            % self.day.id,
            code,
            ready="!!document.querySelector('.o_form_view')",
            login="ewp_webapp_browser_manager",
        )
        lab = self.room_lab
        lab.invalidate_recordset()
        for value, expected in (
            (lab.pos_x, 25),
            (lab.pos_y, 25),
            (lab.pos_width, 50),
            (lab.pos_height, 50),
        ):
            self.assertAlmostEqual(value, expected, delta=1)

    def _conference_day(self, room_name, meeting_id, running=True):
        """Open day with one room whose meeting `meeting_id` runs, or not,
        on the fake BigBlueButton server (see test_bbb)."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_URL, SERVER)
        params.set_param(PARAM_BBB_SECRET, SECRET)
        # The fake server is on another site than the test server: the
        # frame tests force the embedded display.
        params.set_param(PARAM_BBB_DISPLAY, "frame")
        with fake_network(FakeNetwork(running=running)):
            return self.env["event.webapp"].create(
                {
                    "name": "Browser Day of %s" % room_name,
                    "date_start": fields.Datetime.now() - timedelta(hours=1),
                    "date_end": fields.Datetime.now() + timedelta(hours=8),
                    "plan_image": _png_b64(400, 200),
                    "room_ids": [
                        Command.create(
                            {
                                "name": room_name,
                                "bbb_meeting_id": meeting_id,
                                "pos_x": 10,
                                "pos_y": 10,
                                "pos_width": 30,
                                "pos_height": 30,
                            }
                        ),
                        Command.create({"name": "Kappa Lab"}),
                    ],
                }
            )

    def _room_page(self, day):
        return "/webapp_event/%s/room/%s" % (day.id, day.room_ids[0].id)

    def _run(self, url, code, running=True):
        """browser_js on `url` as the portal user, the fake server playing
        a meeting that runs or not, the join URL replaced by CLIENT_PATH."""
        with fake_network(FakeNetwork(running=running)), mock.patch.object(
            bbb_client, "join_url", return_value=CLIENT_PATH
        ):
            self.browser_js(
                url,
                "(async () => {" + JS_WAIT + JS_CHECK + JS_FRAME + code + """
                    console.log("test successful");
                })().catch((error) => console.error(error.message));
                """,
                ready="document.readyState === 'complete'",
                login="ewp_webapp_browser_portal",
            )

    def test_conference_controls_keep_a_visible_focus_ring(self):
        """From 1024 px the conference block lies on the page ground: its
        controls take the focus ring of the page, the one each colour
        scheme sets on the body. In text-only mode, "Show the video
        conference" gives the frame its src, shows it and moves the focus
        there, with a ring drawn inside the frame, which its box clips."""
        day = self._conference_day("Theta Studio", "gl-invented-browser-0002")
        self._run(
            self._room_page(day),
            """
            check(window.innerWidth >= 1024, "window narrower than 1024 px");
            const link = document.querySelector(".o_ewp_bbb_newtab");
            document.body.style.setProperty("--ewp-focus", "rgb(1, 2, 3)");
            const ring = getComputedStyle(link).getPropertyValue("--ewp-focus").trim();
            check(ring === "rgb(1, 2, 3)", "ring of the conference block: " + ring);
            """,
        )
        self.portal_user.ewp_text_only = True
        self._run(
            self._room_page(day),
            """
            const button = document.querySelector(".o_ewp_bbb_show");
            const video = document.getElementById("o_ewp_video");
            const frame = video.querySelector(".o_ewp_bbb_frame");
            check(video.hidden && !frame.getAttribute("src"), "frame shown at load");
            // "Open in a new tab" says it already: its cue stays hidden.
            const cue = document.querySelector(".o_ewp_bbb_newtab .o_ewp_external_text");
            check(cue.getBoundingClientRect().width <= 1, "new tab cue said twice");
            button.click();
            check(frame.getAttribute("src") === frame.dataset.ewpSrc, "frame src not set");
            check(!video.hidden && video.getBoundingClientRect().height > 0, "frame still hidden");
            check(button.getAttribute("aria-expanded") === "true", "aria-expanded not true");
            check(button.closest(".o_ewp_bbb_ondemand").hidden, "button still shown");
            check(document.activeElement === frame, "focus not on the frame");
            check(ringShown(frame), "focus ring of the frame not visible");
            """,
        )

    def test_conference_reloads_keep_the_focus_on_the_block(self):
        """The page loads again by itself once the meeting starts, and after
        "Join again" on a meeting that ended: the next page says why in the
        shared region and puts the focus on the heading of the conference
        block, not at the top of the page."""
        day = self._conference_day(
            "Iota Studio", "gl-invented-browser-0003", running=False
        )
        self._run(
            HOST_PAGE,
            """
            const frame = await openFrame(%(room)r);
            const doc = frame.contentDocument;
            check(doc.querySelector(".o_ewp_bbb").dataset.ewpBbbState === "waiting", "not waiting");
            const statusUrl = doc.querySelector("[data-ewp-bbb-status-url]").dataset.ewpBbbStatusUrl;
            const realFetch = frame.contentWindow.fetch;
            frame.contentWindow.fetch = (url, options) =>
                String(url).includes(statusUrl)
                    ? Promise.resolve(jsonResponse({running: true, error: false}))
                    : realFetch(url, options);
            doc.dispatchEvent(new Event("visibilitychange"));
            const next = await nextPage(frame, doc);
            await wait(() => next.getElementById("o_ewp_announcer").textContent === "The conference has started.");
            await chatLoaded(next);
            check(next.activeElement.id === "o_ewp_h_bbb", "focus on " + next.activeElement.tagName);
            """ % {"room": self._room_page(day)},
            running=False,
        )
        day = self._conference_day("Lambda Studio", "gl-invented-browser-0004")
        self._run(
            HOST_PAGE,
            """
            const frame = await openFrame(%(room)r);
            const doc = frame.contentDocument;
            const bbb = doc.querySelector("iframe.o_ewp_bbb_frame");
            const notice = doc.querySelector(".o_ewp_bbb_left");
            await wait(() => {
                try {
                    return bbb.contentWindow.location.pathname === %(client)r
                        && bbb.contentDocument.readyState === "complete";
                } catch {
                    return false;
                }
            });
            await sleep(300);
            bbb.contentWindow.location.href = notice.dataset.ewpBbbLeftPath + "?frame=1&reason=left";
            await wait(() => !notice.hidden);
            await wait(() => doc.getElementById("o_ewp_announcer").textContent === "You left the conference.");
            // The meeting ended meanwhile: the page loads again.
            const checkUrl = notice.dataset.ewpBbbCheckUrl;
            const realFetch = frame.contentWindow.fetch;
            frame.contentWindow.fetch = (url, options) =>
                String(url).includes(checkUrl)
                    ? Promise.resolve(jsonResponse({running: false, error: false}))
                    : realFetch(url, options);
            notice.querySelector(".o_ewp_bbb_rejoin").click();
            const next = await nextPage(frame, doc);
            await wait(() => next.getElementById("o_ewp_announcer").textContent === "The conference has not started yet.");
            await chatLoaded(next);
            check(next.activeElement.id === "o_ewp_h_bbb", "focus on " + next.activeElement.tagName);
            """ % {"room": self._room_page(day), "client": CLIENT_PATH},
        )

    def test_lead_cards_open_phones_and_top_the_main_column(self):
        """A card of the home lead slot comes first on a phone, before the
        announcement; on a wide screen it tops the main column, with the
        plan right under it and the announcement beside it."""
        self.day.write(
            {
                "announcement": "<p>Browser lead welcome</p>",
                "link_ids": [
                    Command.create(
                        {
                            "name": "Browser Lead Link",
                            "url": "https://example.org/lead",
                        }
                    )
                ],
            }
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
        self._run(
            "/webapp_event/%s" % self.day.id,
            """
            // Boxes of the cards of the page in a frame `width` px wide.
            const boxes = async (width) => {
                const frame = document.createElement("iframe");
                frame.style.width = `${width}px`;
                frame.style.height = "900px";
                document.body.appendChild(frame);
                frame.src = location.pathname;
                await wait(() => frame.contentDocument.location.pathname === location.pathname
                    && ready(frame.contentDocument));
                // Still cards: an entrance animation would move them.
                frame.contentDocument.body.classList.add("o_ewp_motion_paused");
                await sleep(100);
                const box = (selector) => {
                    const el = frame.contentDocument.querySelector(selector);
                    check(el, "missing " + selector);
                    return el.getBoundingClientRect();
                };
                return {
                    lead: box(".test_lead"),
                    announcement: box(".o_ewp_announcement"),
                    plan: box(".o_ewp_plan_card"),
                };
            };
            const near = (a, b) => Math.abs(a - b) <= 2;
            const phone = await boxes(390);
            check(phone.lead.bottom <= phone.announcement.top,
                `phone: lead ${phone.lead.bottom}, announcement ${phone.announcement.top}`);
            check(near(phone.lead.left, phone.announcement.left), "phone: lead out of the column");
            const wide = await boxes(1280);
            check(near(wide.lead.left, wide.plan.left), "wide: lead out of the main column");
            check(near(wide.plan.top - wide.lead.bottom, 24),
                `wide: plan ${wide.plan.top} under the lead ${wide.lead.bottom}`);
            check(wide.announcement.left >= wide.lead.right, "wide: announcement not beside the lead");
            check(near(wide.announcement.top, wide.lead.top),
                `wide: announcement ${wide.announcement.top}, lead ${wide.lead.top}`);
            """,
            running=False,
        )

    def test_home_page_marks_the_live_rooms(self):
        """The home page asks the live route at start: a running meeting
        marks the area and the link of its room and shows its "Live" pill
        in place of "Video"; a room that goes live later is announced."""
        day = self._conference_day("Mu Hall", "gl-invented-browser-0005")
        self._run(
            "/webapp_event/%s" % day.id,
            """
            const pills = document.querySelectorAll(".o_ewp_pill_live");
            check(pills.length === 1, "pills: " + pills.length);
            const pill = pills[0];
            const link = pill.closest(".o_ewp_room_link");
            const id = link.dataset.ewpRoomId;
            const area = document.querySelector(`.o_ewp_hotspot[data-ewp-room-id="${id}"]`);
            const region = document.getElementById("o_ewp_announcer");
            await wait(() => link.dataset.ewpLive === "true");
            check(area.dataset.ewpLive === "true", "area not marked");
            check(!pill.hidden && pill.getBoundingClientRect().width > 0, "pill hidden");
            check(getComputedStyle(link.querySelector(".o_ewp_pill_video")).display === "none", "Video pill shown");
            check(getComputedStyle(area).boxShadow !== "none", "area without its ring");
            const liveUrl = document.querySelector("[data-ewp-live-url]").dataset.ewpLiveUrl;
            let answer = {live: []};
            const events = [];
            document.addEventListener("ewp:rooms-live", (ev) => events.push(ev.detail.ids.join()));
            const realFetch = window.fetch;
            window.fetch = (url, options) =>
                String(url).includes(liveUrl) ? Promise.resolve(jsonResponse(answer)) : realFetch(url, options);
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => !link.dataset.ewpLive);
            check(pill.hidden && !area.dataset.ewpLive, "room still marked");
            answer = {live: [Number(id)]};
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => region.textContent === "The conference of Mu Hall is live.");
            check(events.join("|") === "|" + id, "events: " + events.join("|"));
            """,
        )

    def test_leaving_the_conference_frame_and_joining_again(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_URL, SERVER)
        params.set_param(PARAM_BBB_SECRET, SECRET)
        params.set_param(PARAM_BBB_DISPLAY, "frame")
        with fake_network(FakeNetwork(running=True)):
            day = self.env["event.webapp"].create(
                {
                    "name": "Browser Conference Day",
                    "date_start": fields.Datetime.now() - timedelta(hours=1),
                    "date_end": fields.Datetime.now() + timedelta(hours=8),
                    "room_ids": [
                        Command.create(
                            {
                                "name": "Eta Studio",
                                "bbb_meeting_id": "gl-invented-browser-0001",
                            }
                        )
                    ],
                }
            )
        code = "(async () => {" + JS_WAIT + """
            const CLIENT = %(client)r;
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const frame = document.querySelector("iframe.o_ewp_bbb_frame");
            const notice = document.querySelector(".o_ewp_bbb_left");
            const button = notice.querySelector("button.o_ewp_bbb_rejoin");
            const src = frame.getAttribute("src");
            const section = document.querySelector(".o_ewp_bbb");
            const states = [];
            document.addEventListener("ewp:bbb-state", (ev) => {
                if (!ev.detail.initial) {
                    states.push(ev.detail.state);
                }
            });
            const loaded = (path) => {
                try {
                    const doc = frame.contentDocument;
                    return frame.contentWindow.location.pathname === path
                        && doc.readyState === "complete";
                } catch {
                    return false;
                }
            };
            const check = (ok, message) => {
                if (!ok) {
                    throw new Error(message);
                }
            };
            // First load: the client. No notice.
            await wait(() => loaded(CLIENT));
            await sleep(300);
            check(notice.hidden && !frame.hidden, "notice on the first load");
            // The client loads the logoutURL once the user leaves.
            frame.contentWindow.location.href =
                notice.dataset.ewpBbbLeftPath + "?frame=1&reason=left";
            await wait(() => !notice.hidden);
            check(frame.hidden, "frame still shown after leaving");
            check(document.activeElement === button, "focus not on Join again");
            check(section.dataset.ewpBbbState === "left", "state not left");
            await wait(() => frame.contentWindow.location.href === "about:blank");
            await sleep(300);
            check(!notice.hidden, "notice gone after the frame was emptied");
            // Join again: the meeting runs, the frame loads its route again
            // and takes the focus, with a ring that its box does not clip.
            button.click();
            await wait(() => notice.hidden && !frame.hidden);
            check(frame.getAttribute("src") === src, "frame src changed");
            check(document.activeElement === frame, "focus not on the frame");
            check(ringShown(frame), "focus ring of the frame not visible");
            await wait(() => loaded(CLIENT));
            await sleep(300);
            check(notice.hidden, "notice on the first load after joining again");
            // Any later load counts as leaving, whatever the page.
            frame.contentWindow.location.href = CLIENT + "?logout=1";
            await wait(() => !notice.hidden);
            check(states.join() === "left,running,left", "events: " + states.join());
            console.log("test successful");
        })().catch((error) => console.error(error.message));
        """ % {"client": CLIENT_PATH}
        code = code.replace("(async () => {", "(async () => {" + JS_FRAME, 1)
        with fake_network(FakeNetwork(running=True)), mock.patch.object(
            bbb_client, "join_url", return_value=CLIENT_PATH
        ):
            self.browser_js(
                "/webapp_event/%s/room/%s" % (day.id, day.room_ids.id),
                code,
                ready="document.readyState === 'complete'",
                login="ewp_webapp_browser_portal",
            )

    def test_automatic_updates_count_down(self):
        """The section "Automatic updates" shows once the refreshers
        report: each row counts down to its next request every second,
        takes the time of an answer, says a failed answer and its retry,
        "paused" while the tab is hidden, and "stopped" after a 403. The
        conference row follows the doubled interval of a failing server."""
        day = self._conference_day(
            "Nu Hall", "gl-invented-browser-0006", running=False
        )
        event = self.env["event.event"].create(
            {
                "name": "Browser Refresh Talk",
                "date_begin": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=8),
            }
        )
        day.raffle_ids = [
            Command.create(
                {
                    "name": "Browser Refresh Raffle",
                    "event_id": event.id,
                    "draw_ids": [
                        Command.create(
                            {"sequence": 1, "prize": "Browser Refresh Mug"}
                        )
                    ],
                }
            )
        ]
        rows = """
            const section = await wait(() => {
                const el = document.getElementById("o_ewp_refresh");
                return el && !el.hidden && el;
            });
            check(!section.closest("[aria-live]") && !section.querySelector("[aria-live]"), "live region");
            const row = (id) => section.querySelector(`li[data-ewp-refresh="${id}"]`);
            const cell = (id, name) => row(id).querySelector(`.o_ewp_refresh_${name}`);
            const seconds = (id) => {
                const match = cell(id, "next").textContent.match(/(?:(\\d+)\\u00a0min\\u00a0)?(\\d+)\\u00a0s$/);
                return match ? Number(match[1] || 0) * 60 + Number(match[2]) : NaN;
            };
            const realFetch = window.fetch;
            const answer = (part, make) => {
                window.fetch = (url, options) =>
                    String(url).includes(part) ? make() : realFetch(url, options);
            };
        """
        self._run(
            "/webapp_event/%s" % day.id,
            rows + """
            const rafflesUrl = document.querySelector("[data-ewp-raffles-url]").dataset.ewpRafflesUrl;
            // The test code starts once the page is ready, a few seconds
            // after the page script on a first load: the bounds below
            // leave room for that.
            await wait(() => !row("live").hidden && /^Updated \\d+ s ago$/.test(cell("live", "last").textContent));
            check(!row("raffles").hidden, "raffle row hidden");
            check(/^Next in \\d+\\u00a0s$/.test(cell("raffles", "next").textContent),
                "raffles: " + cell("raffles", "next").textContent);
            const first = seconds("raffles");
            check(first > 15 && first <= 30, "first countdown " + first);
            await wait(() => seconds("raffles") === first - 1, 2500);
            await wait(() => seconds("raffles") === first - 2, 2500);
            // An answer: the row takes its time and counts from 30 s again.
            const loaded = Date.parse(cell("raffles", "last").getAttribute("datetime"));
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => Date.parse(cell("raffles", "last").getAttribute("datetime")) > loaded);
            check(row("raffles").dataset.ewpRefreshState === "running", "state after the answer");
            check(seconds("raffles") >= 29, "countdown after the answer " + seconds("raffles"));
            // A failed answer, in words.
            answer(rafflesUrl, () => Promise.reject(new TypeError("offline")));
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => row("raffles").dataset.ewpRefreshState === "error");
            check(/^Failed, retrying in \\d+\\u00a0s$/.test(cell("raffles", "next").textContent),
                "error: " + cell("raffles", "next").textContent);
            // Hidden tab: every row is paused and stops counting.
            Object.defineProperty(document, "hidden", {configurable: true, get: () => true});
            document.dispatchEvent(new Event("visibilitychange"));
            for (const id of ["raffles", "live"]) {
                check(row(id).dataset.ewpRefreshState === "paused", id + " not paused");
                check(cell(id, "next").textContent === "Paused while the page is hidden", id + " text");
            }
            await sleep(1200);
            check(cell("raffles", "next").textContent === "Paused while the page is hidden", "rewritten while hidden");
            delete document.hidden;
            // 403: stopped for good.
            answer(rafflesUrl, () => Promise.resolve(new Response("", {status: 403})));
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => row("raffles").dataset.ewpRefreshState === "stopped");
            check(cell("raffles", "next").textContent === "Stopped, reload the page", "stopped text");
            // The live rooms answer the same event through the server:
            // their row goes from "busy" back to "running", not stopped.
            await wait(() => row("live").dataset.ewpRefreshState === "running");
            """,
            running=False,
        )
        self._run(
            self._room_page(day),
            rows + """
            const statusUrl = document.querySelector("[data-ewp-bbb-status-url]").dataset.ewpBbbStatusUrl;
            await wait(() => !row("conference").hidden);
            const first = seconds("conference");
            check(first > 10 && first <= 20, "first countdown " + first);
            // The server fails: the retry comes after 40 s, then 1 min 20 s.
            answer(statusUrl, () => Promise.reject(new TypeError("offline")));
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => row("conference").dataset.ewpRefreshState === "error");
            check(seconds("conference") > 35 && seconds("conference") <= 40,
                "first retry: " + cell("conference", "next").textContent);
            document.dispatchEvent(new Event("visibilitychange"));
            await wait(() => /1\\u00a0min\\u00a0[0-9]{2}\\u00a0s$/.test(cell("conference", "next").textContent));
            check(seconds("conference") > 75 && seconds("conference") <= 80,
                "second retry: " + cell("conference", "next").textContent);
            check(/^Failed, retrying in 1\\u00a0min\\u00a0[0-9]{2}\\u00a0s$/.test(cell("conference", "next").textContent),
                "text: " + cell("conference", "next").textContent);
            """,
            running=False,
        )

    def test_automatic_updates_keep_their_lines(self):
        """Each row of "Automatic updates" keeps its height whatever its
        cells say, on a phone (320 to 412 px) as on a wide screen: an empty
        time before the first answer, the longest French and English
        states, a countdown that goes from "1 min 00 s" to "59 s". The page
        has no horizontal scroll at any of these widths."""
        day = self._conference_day(
            "Xi Hall", "gl-invented-browser-0007", running=False
        )
        self._run(
            HOST_PAGE,
            """
            const frame = await openFrame(%(home)r);
            const doc = frame.contentDocument;
            const rows = await wait(() => {
                const shown = [...doc.querySelectorAll("#o_ewp_refresh li[data-ewp-refresh]")]
                    .filter((li) => !li.hidden);
                return shown.length && shown;
            });
            await doc.fonts.ready;
            const lasts = ["", "Mis à jour il y a 0 s", "Mis à jour il y a 59 min", "Updated 59 min ago"];
            const nexts = [
                ["running", ""],
                ["running", "Prochaine dans 59\\u00a0s"],
                ["running", "Prochaine dans 1\\u00a0min\\u00a000\\u00a0s"],
                ["running", "Next in 4\\u00a0min\\u00a059\\u00a0s"],
                ["error", "Échec, nouvel essai dans 1\\u00a0min\\u00a019\\u00a0s"],
                ["error", "Échec, nouvel essai dans 59\\u00a0s"],
                ["error", "Failed, retrying in 1\\u00a0min\\u00a019\\u00a0s"],
                ["busy", "Mise à jour en cours"],
                ["paused", "En pause tant que la page est cachée"],
                ["stopped", "Arrêtée, rechargez la page"],
            ];
            for (const width of [320, 360, 390, 412, 640, 768, 1024, 1280]) {
                frame.style.width = width + "px";
                await sleep(200);
                check(doc.documentElement.scrollWidth <= doc.documentElement.clientWidth,
                    "horizontal scroll at " + width + " px");
                // Written and measured in one task: the page script, which
                // rewrites the cells every second, cannot run in between.
                for (const row of rows) {
                    const heights = new Set();
                    const last = row.querySelector(".o_ewp_refresh_last");
                    const next = row.querySelector(".o_ewp_refresh_next");
                    for (const lastText of lasts) {
                        for (const [state, nextText] of nexts) {
                            row.dataset.ewpRefreshState = state;
                            last.textContent = lastText;
                            next.textContent = nextText;
                            heights.add(Math.round(row.getBoundingClientRect().height));
                        }
                    }
                    check(heights.size === 1, row.dataset.ewpRefresh + " at " + width + " px: heights "
                        + [...heights].join(", "));
                }
            }
            """ % {"home": "/webapp_event/%s" % day.id},
            running=False,
        )
