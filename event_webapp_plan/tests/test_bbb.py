# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""BigBlueButton tests: checksum, join URL, frame check, settings, the
running meetings wizard and the conference block of the room page.

No test reaches the network: FakeNetwork replaces `requests` in
models/bbb_client.py and plays a BigBlueButton server, which checks the
checksum of every API call like the real one. Every host, meeting ID and
secret below is invented; the hosts use reserved example domains.
"""

import hashlib
import json
import traceback
import types
from contextlib import contextmanager
from datetime import timedelta
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

import requests
from lxml import html as lxml_html
from odoo import Command, fields
from odoo.addons.event_webapp_plan.models import bbb_client
from odoo.addons.event_webapp_plan.models.event_webapp_room import (
    PARAM_BBB_DISPLAY,
    PARAM_BBB_SECRET,
    PARAM_BBB_URL,
)
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user

SECRET = "ewp-invented-secret-5d1f0c8e"
SERVER = "https://bbb.example.org/bigbluebutton/"
API = "https://bbb.example.org/bigbluebutton/api"
MEETING = "gl-invented-meeting-0001"
CREATE_TIME = "1700000000123"
ROOM_URL = "https://bbb.example.org/rooms/abc-def-ghi/join"
ROOM_URL_FRAMED = "https://conference.example.com/room/test-one"
ROOM_URL_REFUSED = "https://conference.example.com/room/test-two"
BASE_URL = "https://odoo.example.com"
MODERATOR = "event_webapp_plan.group_event_webapp_moderator"
MANAGER = "event_webapp_plan.group_event_webapp_manager"

GET_MEETINGS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<response>
  <returncode>SUCCESS</returncode>
  <meetings>
    <meeting>
      <meetingName>Main Hall Test</meetingName>
      <meetingID>gl-main-hall-0001</meetingID>
      <participantCount>12</participantCount>
      <running>true</running>
      <isBreakout>false</isBreakout>
    </meeting>
    <meeting>
      <meetingName>Workshop Test</meetingName>
      <meetingID>gl-workshop-0002</meetingID>
      <participantCount>0</participantCount>
      <running>false</running>
      <isBreakout>false</isBreakout>
    </meeting>
    <meeting>
      <meetingName>Main Hall Test (Room - 1)</meetingName>
      <meetingID>gl-breakout-0003</meetingID>
      <participantCount>2</participantCount>
      <running>true</running>
      <isBreakout>true</isBreakout>
    </meeting>
  </meetings>
</response>"""


class FakeResponse:
    def __init__(self, content=b"", status_code=200, headers=None, url=""):
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url

    def close(self):
        pass


def _unreachable(url):
    """ConnectionError worded as requests and urllib3 word it: the path
    and the query of the URL, checksum included, are in the message."""
    parts = urlsplit(url)
    return requests.ConnectionError(
        "HTTPSConnectionPool(host='%s', port=443): Max retries exceeded "
        "with url: %s?%s" % (parts.hostname, parts.path, parts.query)
    )


class FakeNetwork:
    """Plays the BigBlueButton API under API and any other web page.

    `running` answers getMeetingInfo (createTime CREATE_TIME, or the
    FAILED answer notFound of a meeting that does not run); `api_error` is
    None, "network" (no answer) or "http" (status 502); a call whose
    checksum does not match SECRET gets the FAILED answer checksumError.
    `frames` maps a page URL to its response headers; `frame_error` makes
    those pages unreachable. Changing `running` or `api_error` empties the
    cache of bbb_client, as its expiry would on a real server.
    """

    def __init__(self, running=True, api_error=None, frames=None):
        self.running = running
        self.api_error = api_error
        self.frames = frames or {}
        self.frame_error = False
        self.calls = []

    def __setattr__(self, name, value):
        if name in ("running", "api_error"):
            bbb_client.cache_clear()
        super().__setattr__(name, value)

    def api_calls(self, call):
        """Number of API calls `call` received."""
        return sum(
            1
            for url, _kwargs in self.calls
            if url.startswith(API + "/" + call)
        )

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.startswith(API + "/"):
            return self._api(url)
        if self.frame_error:
            raise _unreachable(url)
        return FakeResponse(headers=self.frames.get(url, {}), url=url)

    def _api(self, url):
        if self.api_error == "network":
            raise _unreachable(url)
        if self.api_error == "http":
            return FakeResponse(status_code=502)
        parts = urlsplit(url)
        call = parts.path.rsplit("/", 1)[1]
        query, _sep, signature = parts.query.rpartition("checksum=")
        query = query[:-1] if query.endswith("&") else query
        expected = hashlib.sha256(
            ("%s%s%s" % (call, query, SECRET)).encode()
        ).hexdigest()
        if signature != expected:
            return FakeResponse(
                b"<response><returncode>FAILED</returncode>"
                b"<messageKey>checksumError</messageKey>"
                b"<message>Checksums do not match</message></response>"
            )
        if call == "getMeetingInfo":
            if not self.running:
                return FakeResponse(
                    b"<response><returncode>FAILED</returncode>"
                    b"<messageKey>notFound</messageKey>"
                    b"<message>No meeting found</message></response>"
                )
            return FakeResponse(
                b"<response><returncode>SUCCESS</returncode>"
                b"<createTime>%s</createTime><running>true</running>"
                b"</response>" % CREATE_TIME.encode()
            )
        if call == "getMeetings":
            return FakeResponse(GET_MEETINGS_XML)
        return FakeResponse(b"<html>unexpected call</html>", 404)


@contextmanager
def fake_network(network):
    fake_requests = types.SimpleNamespace(
        get=network.get, RequestException=requests.RequestException
    )
    bbb_client.cache_clear()
    try:
        with mock.patch.object(bbb_client, "requests", fake_requests):
            yield network
    finally:
        bbb_client.cache_clear()


def _query(url):
    """Parameters of a URL as a dict, and its query without checksum."""
    parts = urlsplit(url)
    query = parts.query.rpartition("&checksum=")[0]
    return dict(parse_qsl(parts.query)), query


@tagged("post_install", "-at_install")
class TestBbbTools(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.params.set_param("web.base.url", BASE_URL)
        cls.params.set_param(PARAM_BBB_URL, SERVER)
        cls.params.set_param(PARAM_BBB_SECRET, SECRET)
        # BASE_URL and SERVER are two sites: the tests force the embedded
        # display, and the tests of the display modes set their own.
        cls.params.set_param(PARAM_BBB_DISPLAY, "frame")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.portal_user = Users.create(
            {
                "name": "Portal Bbb Tester",
                "login": "ewp_bbb_portal_tester",
                "groups_id": [
                    Command.set([cls.env.ref("base.group_portal").id])
                ],
            }
        )
        cls.internal_user = Users.create(
            {
                "name": "Internal Bbb Tester",
                "login": "ewp_bbb_internal_tester",
                "groups_id": [
                    Command.set([cls.env.ref("base.group_user").id])
                ],
            }
        )
        cls.moderator_user = Users.create(
            {
                "name": "Moderator Bbb Tester",
                "login": "ewp_bbb_moderator_tester",
                "groups_id": [Command.set([cls.env.ref(MODERATOR).id])],
            }
        )
        cls.manager_user = Users.create(
            {
                "name": "Manager Bbb Tester",
                "login": "ewp_bbb_manager_tester",
                "groups_id": [Command.set([cls.env.ref(MANAGER).id])],
            }
        )
        # Settings user and event Administrator: the one who lists the
        # meetings of the server and assigns them to the rooms.
        cls.bbb_admin_user = Users.create(
            {
                "name": "Bbb Admin Tester",
                "login": "ewp_bbb_admin_tester",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref(MANAGER).id,
                            cls.env.ref("base.group_system").id,
                        ]
                    )
                ],
            }
        )
        now = fields.Datetime.now()
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Bbb Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "room_ids": [
                    Command.create(
                        {"name": "Hall", "bbb_meeting_id": MEETING}
                    ),
                    Command.create(
                        {
                            "name": "Workshop",
                            "bbb_meeting_id": "gl-workshop-0002",
                        }
                    ),
                ],
            }
        )
        cls.hall = cls.day.room_ids.filtered(lambda r: r.name == "Hall")
        cls.workshop = cls.day.room_ids - cls.hall

    def test_checksum_matches_the_api_documentation(self):
        # Example of the BigBlueButton API documentation, with its SHA-1
        # value, then the SHA-256 digest of the same input.
        call = "create"
        query = (
            "name=Test+Meeting&meetingID=abc123&attendeePW=111222"
            "&moderatorPW=333444"
        )
        secret = "639259d4-9dd8-4b25-bf01-95f9567eaf4b"
        self.assertEqual(
            bbb_client.checksum(call, query, secret, "sha1"),
            "1fcbb0c4fc1f039f73aa6d697d2db9ba7f803f17",
        )
        self.assertEqual(
            bbb_client.checksum(call, query, secret),
            "da9185f7f333cfdfcd6eeac32dca3777510c4c436020d8b887ba5515bd1d189e",
        )
        url = bbb_client.call_url(API, secret, "getMeetings")
        self.assertEqual(
            url,
            API
            + "/getMeetings?checksum="
            + bbb_client.checksum("getMeetings", "", secret),
        )

    def test_api_url_accepts_the_usual_server_forms(self):
        for value, expected in (
            ("https://bbb.example.org", API),
            ("https://bbb.example.org/", API),
            (SERVER, API),
            (" https://bbb.example.org/bigbluebutton ", API),
            ("https://bbb.example.org/bigbluebutton/api/", API),
            (
                "http://bbb.example.org:8080",
                "http://bbb.example.org:8080" "/bigbluebutton/api",
            ),
            ("ftp://bbb.example.org", False),
            ("javascript:alert(1)", False),
            ("bbb.example.org", False),
            ("", False),
            (False, False),
        ):
            with self.subTest(value=value):
                self.assertEqual(bbb_client.api_url(value), expected)

    def test_frame_allowed_on_header_samples(self):
        bbb_page = "https://bbb.example.org/html5client/join?sessionToken=x"
        odoo_page = BASE_URL + "/some/page"
        csp = "Content-Security-Policy"
        xfo = "X-Frame-Options"
        samples = [
            ("no header", {}, bbb_page, True),
            ("XFO DENY", {xfo: "DENY"}, bbb_page, False),
            (
                "XFO deny, any case",
                {"x-frame-options": "deny"},
                bbb_page,
                False,
            ),
            ("XFO SAMEORIGIN, other", {xfo: "SAMEORIGIN"}, bbb_page, False),
            ("XFO SAMEORIGIN, same", {xfo: "SAMEORIGIN"}, odoo_page, True),
            (
                "XFO ALLOW-FROM",
                {xfo: "ALLOW-FROM " + BASE_URL},
                bbb_page,
                False,
            ),
            ("XFO unknown value", {xfo: "ALLOWALL"}, bbb_page, True),
            ("CSP none", {csp: "frame-ancestors 'none'"}, bbb_page, False),
            ("CSP empty list", {csp: "frame-ancestors"}, bbb_page, False),
            (
                "CSP self, other",
                {csp: "frame-ancestors 'self'"},
                bbb_page,
                False,
            ),
            (
                "CSP self, same",
                {csp: "frame-ancestors 'self'"},
                odoo_page,
                True,
            ),
            ("CSP star", {csp: "frame-ancestors *"}, bbb_page, True),
            ("CSP scheme", {csp: "frame-ancestors https:"}, bbb_page, True),
            (
                "CSP list with the origin",
                {
                    csp: (
                        "default-src 'self'; frame-ancestors 'self' "
                        "https://odoo.example.com"
                    )
                },
                bbb_page,
                True,
            ),
            (
                "CSP wildcard host",
                {csp: "frame-ancestors *.example.com"},
                bbb_page,
                True,
            ),
            (
                "CSP list without the origin",
                {csp: "frame-ancestors https://other.example.net"},
                bbb_page,
                False,
            ),
            (
                "CSP other port",
                {csp: "frame-ancestors https://odoo.example.com:8443"},
                bbb_page,
                False,
            ),
            (
                "CSP overrides XFO",
                {csp: "frame-ancestors *", xfo: "DENY"},
                bbb_page,
                True,
            ),
            (
                "CSP without frame-ancestors, XFO decides",
                {csp: "default-src 'self'", xfo: "SAMEORIGIN"},
                bbb_page,
                False,
            ),
            (
                "two policies, one refuses",
                {csp: "frame-ancestors *, frame-ancestors 'none'"},
                bbb_page,
                False,
            ),
            (
                "report-only enforces nothing",
                {
                    "Content-Security-Policy-Report-Only": (
                        "frame-ancestors 'none'"
                    )
                },
                bbb_page,
                True,
            ),
        ]
        for label, headers, page, expected in samples:
            with self.subTest(label):
                self.assertEqual(
                    bbb_client.frame_allowed(headers, page, BASE_URL),
                    expected,
                )

    def test_get_meetings_answer_is_parsed(self):
        meetings = bbb_client.meetings_from_xml(
            bbb_client.parse_response(GET_MEETINGS_XML)
        )
        self.assertEqual(
            meetings,
            [
                {
                    "name": "Main Hall Test",
                    "meeting_id": "gl-main-hall-0001",
                    "participant_count": 12,
                    "running": True,
                },
                {
                    "name": "Workshop Test",
                    "meeting_id": "gl-workshop-0002",
                    "participant_count": 0,
                    "running": False,
                },
            ],
        )
        with self.assertRaises(bbb_client.BbbError) as caught:
            bbb_client.parse_response(
                b"<response><returncode>FAILED</returncode><messageKey>"
                b"checksumError</messageKey></response>"
            )
        self.assertEqual(caught.exception.kind, "failed")
        self.assertEqual(caught.exception.key, "checksumError")
        with self.assertRaises(bbb_client.BbbError) as caught:
            bbb_client.parse_response(b"not xml at all")
        self.assertEqual(caught.exception.kind, "parse")

    def test_room_url_must_be_http_or_https(self):
        with fake_network(FakeNetwork()):
            for url in (
                "javascript:alert(1)",
                "data:text/html,hello",
                "ftp://bbb.example.org/room",
                "//bbb.example.org/room",
                "https://",
                "https://bbb.example.org/a room",
            ):
                with self.subTest(url=url):
                    with self.assertRaises(ValidationError):
                        self.hall.bbb_room_url = url
            self.hall.bbb_room_url = "  " + ROOM_URL + " "
            self.assertEqual(self.hall.bbb_room_url, ROOM_URL)

    def test_room_url_frame_check_on_write_and_recheck(self):
        network = FakeNetwork(frames={ROOM_URL: {"X-Frame-Options": "DENY"}})
        with fake_network(network):
            self.hall.bbb_room_url = ROOM_URL
            self.assertFalse(self.hall.bbb_frameable)
            self.assertTrue(self.hall.bbb_frame_checked)
            url, kwargs = network.calls[-1]
            self.assertEqual(url, ROOM_URL)
            self.assertTrue(kwargs.get("allow_redirects"))
            self.assertLessEqual(kwargs.get("timeout"), 10)

            network.frames[ROOM_URL] = {}
            self.hall.with_user(self.manager_user).action_bbb_recheck()
            self.assertTrue(self.hall.bbb_frameable)

            # A Moderator reads the rooms only: refused before any request.
            calls = len(network.calls)
            with self.assertRaises(AccessError):
                self.hall.with_user(self.moderator_user).action_bbb_recheck()
            self.assertEqual(len(network.calls), calls)

            network.frame_error = True
            self.hall.action_bbb_recheck()
            self.assertFalse(self.hall.bbb_frameable)

            self.hall.bbb_room_url = False
            self.assertFalse(self.hall.bbb_frameable)
            self.assertFalse(self.hall.bbb_frame_checked)

            # A room created with a URL is checked at once.
            network.frame_error = False
            room = self.env["event.webapp.room"].create(
                {
                    "name": "Framed",
                    "webapp_id": self.day.id,
                    "bbb_room_url": ROOM_URL,
                }
            )
            self.assertTrue(room.bbb_frameable)

    def test_join_url_carries_the_user_and_the_role(self):
        for user, role in (
            (self.portal_user, "VIEWER"),
            (self.internal_user, "VIEWER"),
            (self.moderator_user, "MODERATOR"),
            (self.manager_user, "MODERATOR"),
        ):
            with self.subTest(user=user.login):
                url = self.hall.with_user(user).sudo()._ewp_bbb_join_url()
                self.assertTrue(url.startswith(API + "/join?"))
                params, query = _query(url)
                self.assertEqual(params["fullName"], user.name)
                self.assertEqual(params["meetingID"], MEETING)
                self.assertEqual(params["role"], role)
                self.assertEqual(params["userID"], "odoo-%s" % user.id)
                self.assertEqual(params["redirect"], "true")
                self.assertEqual(
                    params["checksum"],
                    bbb_client.checksum("join", query, SECRET),
                )
                self.assertNotIn(SECRET, url)
                self.assertNotIn("password", url.lower())
                # No logoutURL unless the caller gives one.
                self.assertNotIn("logoutURL", params)

    def test_join_url_carries_the_logout_url(self):
        logout_url = BASE_URL + "/webapp_event/1/room/2/bbb_left"
        url = (
            self.hall.with_user(self.portal_user)
            .sudo()
            ._ewp_bbb_join_url(CREATE_TIME, logout_url=logout_url)
        )
        params, query = _query(url)
        self.assertEqual(params["logoutURL"], logout_url)
        self.assertEqual(params["createTime"], CREATE_TIME)
        # Signed with the rest of the query, as any join parameter.
        self.assertEqual(
            params["checksum"], bbb_client.checksum("join", query, SECRET)
        )
        with fake_network(FakeNetwork(running=True)):
            target = self.hall._ewp_bbb_target(logout_url=logout_url)
        self.assertEqual(_query(target["url"])[0]["logoutURL"], logout_url)

    def test_conference_target_order(self):
        network = FakeNetwork(frames={ROOM_URL: {"X-Frame-Options": "DENY"}})
        with fake_network(network):
            target = self.hall._ewp_bbb_target()
            self.assertEqual(target["state"], "frame")
            self.assertTrue(target["url"].startswith(API + "/join?"))
            self.assertTrue(target["live"])
            params, query = _query(target["url"])
            # The join URL holds for the running session only.
            self.assertEqual(params["createTime"], CREATE_TIME)
            self.assertEqual(
                params["checksum"], bbb_client.checksum("join", query, SECRET)
            )

            network.running = False
            self.assertEqual(self.hall._ewp_bbb_target()["state"], "waiting")

            network.api_error = "network"
            target = self.hall._ewp_bbb_target()
            self.assertEqual(target["state"], "unavailable")
            self.assertTrue(target["error"])
            self.hall.bbb_room_url = ROOM_URL
            target = self.hall._ewp_bbb_target()
            self.assertEqual(target["state"], "button")
            self.assertEqual(target["url"], ROOM_URL)
            self.assertTrue(target["error"])
            self.assertFalse(target["live"])

            # Without secret, the meeting ID is ignored: no API call.
            network.api_error = None
            self.params.set_param(PARAM_BBB_SECRET, False)
            calls = len(network.calls)
            target = self.hall._ewp_bbb_target()
            self.assertEqual(target["state"], "button")
            self.assertFalse(target["error"])
            self.assertEqual(len(network.calls), calls)

            self.hall.bbb_room_url = False
            self.assertFalse(self.hall._ewp_bbb_target()["state"])

    def test_same_site_rule(self):
        """Schemeful same site, ports ignored, by registrable domain; IP
        addresses and single-label hosts only match themselves. Every case
        holds for the built-in rule and, when tldextract is installed, for
        the public suffix list."""
        cases = (
            ("https://bbb.example.org/x", "https://bbb.example.org/y", True),
            ("https://bbb.example.org", "https://bbb.example.org:8443/", True),
            ("https://bbb.example.org/", "https://app.example.org/", True),
            ("https://a.b.example.org", "https://example.org", True),
            ("https://bbb.example.org", "https://bbb.example.net", False),
            ("https://bbb.example.org", "https://app.example.net", False),
            ("http://bbb.example.org", "https://bbb.example.org", False),
            (
                "https://bbb.example.qc.ca",
                "https://events.example.qc.ca",
                True,
            ),
            ("https://bbb.example.qc.ca", "https://events.other.qc.ca", False),
            ("https://example.qc.ca", "https://other.qc.ca", False),
            ("https://bbb.example.co.uk", "https://app.example.co.uk", True),
            ("https://bbb.example.co.uk", "https://app.other.co.uk", False),
            ("http://localhost:8069", "http://localhost:9000", True),
            ("http://localhost", "http://bbb.localhost", False),
            ("http://127.0.0.1:8069", "http://127.0.0.1:9000/", True),
            ("http://127.0.0.1", "http://127.0.0.2", False),
            ("http://127.0.0.1", "http://localhost", False),
            ("http://[::1]:8069/", "http://[::1]/", True),
            ("http://[::1]", "http://127.0.0.1", False),
            ("", "https://bbb.example.org", False),
            (None, None, False),
            ("bbb.example.org", "bbb.example.org", False),
            ("ftp://bbb.example.org", "ftp://bbb.example.org", False),
        )
        rules = [("built-in rule", None)]
        if bbb_client.tldextract is not None:
            rules.append(("public suffix list", bbb_client.tldextract))
        for rule, library in rules:
            with mock.patch.object(bbb_client, "tldextract", library):
                for url_a, url_b, expected in cases:
                    with self.subTest(rule=rule, a=url_a, b=url_b):
                        self.assertIs(
                            bbb_client.same_site(url_a, url_b), expected
                        )
                        self.assertIs(
                            bbb_client.same_site(url_b, url_a), expected
                        )
        with mock.patch.object(bbb_client, "tldextract", None):
            for host, domain in (
                ("bbb.example.org", "example.org"),
                ("a.b.example.com.au", "example.com.au"),
                ("events.example.qc.ca", "example.qc.ca"),
                ("qc.ca", ""),
                ("example.ca", "example.ca"),
                ("localhost", ""),
                ("192.0.2.10", ""),
                ("", ""),
            ):
                with self.subTest(host=host):
                    self.assertEqual(
                        bbb_client.registrable_domain(host), domain
                    )

    def test_display_mode_of_a_running_meeting(self):
        same = "https://app.example.org/"
        other = "https://app.example.net/"
        network = FakeNetwork(running=True)
        with fake_network(network):
            for mode, page_url, state in (
                ("auto", same, "frame"),
                ("auto", other, "button"),
                ("frame", other, "frame"),
                ("frame", same, "frame"),
                ("tab", same, "button"),
                ("tab", other, "button"),
                # Unset, or an unknown value: auto.
                (False, same, "frame"),
                (False, other, "button"),
                ("sideways", same, "frame"),
                ("sideways", other, "button"),
            ):
                with self.subTest(mode=mode, page_url=page_url):
                    self.params.set_param(PARAM_BBB_DISPLAY, mode)
                    target = self.hall._ewp_bbb_target(page_url=page_url)
                    self.assertEqual(target["state"], state)
                    # Behind the button too, the meeting is live and the
                    # button gets a fresh join URL.
                    self.assertTrue(target["live"])
                    self.assertFalse(target["error"])
                    self.assertTrue(target["url"].startswith(API + "/join?"))
            # Without page URL: web.base.url, on another site here.
            self.params.set_param(PARAM_BBB_DISPLAY, "auto")
            self.assertEqual(self.hall._ewp_bbb_target()["state"], "button")
            self.params.set_param("web.base.url", "https://odoo.example.org")
            self.assertEqual(self.hall._ewp_bbb_target()["state"], "frame")
            # The mode leaves a meeting that does not run, or a server
            # that does not answer, as they were.
            for mode in ("auto", "frame", "tab"):
                with self.subTest(mode=mode):
                    self.params.set_param(PARAM_BBB_DISPLAY, mode)
                    network.running = False
                    self.assertEqual(
                        self.hall._ewp_bbb_target(page_url=same)["state"],
                        "waiting",
                    )
                    network.api_error = "network"
                    self.assertEqual(
                        self.hall._ewp_bbb_target(page_url=same)["state"],
                        "unavailable",
                    )
                    network.api_error = None
                    network.running = True

    def test_display_mode_of_a_conference_url(self):
        framed = "https://conference.example.org/room/display-one"
        refused = "https://conference.example.org/room/display-two"
        network = FakeNetwork(frames={refused: {"X-Frame-Options": "DENY"}})
        Room = self.env["event.webapp.room"]
        with fake_network(network):
            room_framed = Room.create(
                {
                    "webapp_id": self.day.id,
                    "name": "Display One",
                    "bbb_room_url": framed,
                }
            )
            room_refused = Room.create(
                {
                    "webapp_id": self.day.id,
                    "name": "Display Two",
                    "bbb_room_url": refused,
                }
            )
        self.assertTrue(room_framed.bbb_frameable)
        self.assertFalse(room_refused.bbb_frameable)
        same = "https://app.example.org/"
        other = "https://app.example.net/"
        for mode, page_url, state in (
            ("auto", same, "frame"),
            ("auto", other, "button"),
            ("frame", other, "frame"),
            ("tab", same, "button"),
            ("sideways", same, "frame"),
            ("sideways", other, "button"),
        ):
            with self.subTest(mode=mode, page_url=page_url):
                self.params.set_param(PARAM_BBB_DISPLAY, mode)
                target = room_framed._ewp_bbb_target(page_url=page_url)
                self.assertEqual(target["state"], state)
                self.assertEqual(target["url"], framed)
                self.assertFalse(target["live"])
                # A page that refuses a frame stays behind the button.
                target = room_refused._ewp_bbb_target(page_url=page_url)
                self.assertEqual(target["state"], "button")
                self.assertEqual(target["url"], refused)

    def test_settings_display_mode(self):
        """The display mode reads "auto" when unset or unknown, and only
        the Settings group writes it."""
        Settings = self.env["res.config.settings"]
        Room = self.env["event.webapp.room"]
        self.params.set_param(PARAM_BBB_DISPLAY, False)
        self.assertEqual(Settings.create({}).ewp_bbb_display, "auto")
        self.assertEqual(Room._ewp_bbb_display(), "auto")
        Settings.create({"ewp_bbb_display": "tab"}).execute()
        self.assertEqual(self.params.get_param(PARAM_BBB_DISPLAY), "tab")
        self.assertEqual(Settings.create({}).ewp_bbb_display, "tab")
        self.assertEqual(Room._ewp_bbb_display(), "tab")
        self.params.set_param(PARAM_BBB_DISPLAY, "sideways")
        self.assertEqual(Settings.create({}).ewp_bbb_display, "auto")
        self.assertEqual(Room._ewp_bbb_display(), "auto")
        for user in (self.manager_user, self.moderator_user, self.portal_user):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    Settings.with_user(user).create(
                        {"ewp_bbb_display": "frame"}
                    )
                with self.assertRaises(AccessError):
                    self.env["ir.config_parameter"].with_user(user).set_param(
                        PARAM_BBB_DISPLAY, "frame"
                    )
        self.assertEqual(self.params.get_param(PARAM_BBB_DISPLAY), "sideways")

    def test_settings_secret_is_write_only(self):
        self.params.set_param(PARAM_BBB_SECRET, False)
        settings = self.env["res.config.settings"].create(
            {"ewp_bbb_server_url": SERVER, "ewp_bbb_secret": SECRET}
        )
        settings.execute()
        self.assertEqual(self.params.get_param(PARAM_BBB_SECRET), SECRET)
        self.assertFalse(settings.ewp_bbb_secret)

        settings = self.env["res.config.settings"].create({})
        values = settings.read(["ewp_bbb_secret", "ewp_bbb_secret_set"])[0]
        self.assertFalse(values["ewp_bbb_secret"])
        self.assertTrue(values["ewp_bbb_secret_set"])
        self.assertEqual(settings.ewp_bbb_server_url, SERVER)
        # Saving with the field empty keeps the stored secret.
        settings.execute()
        self.assertEqual(self.params.get_param(PARAM_BBB_SECRET), SECRET)
        self.assertTrue(self.day.bbb_configured)

        with self.assertRaises(UserError):
            self.env["res.config.settings"].create(
                {"ewp_bbb_server_url": "javascript:alert(1)"}
            ).execute()

        settings.action_ewp_bbb_forget_secret()
        self.assertFalse(self.params.get_param(PARAM_BBB_SECRET))
        self.day.invalidate_recordset(["bbb_configured"])
        self.assertFalse(self.day.bbb_configured)

    def test_running_meetings_wizard(self):
        day = self.day.with_user(self.bbb_admin_user)
        with fake_network(FakeNetwork()):
            action = day.action_open_bbb_meetings()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(action["target"], "new")
        self.assertEqual(
            wizard.line_ids.mapped("meeting_id"),
            ["gl-main-hall-0001", "gl-workshop-0002"],
        )
        main, workshop = wizard.line_ids
        self.assertEqual(main.participant_count, 12)
        self.assertTrue(main.running)
        self.assertEqual(workshop.room_id, self.workshop)
        self.assertFalse(main.room_id)

        with self.assertRaises(UserError):
            main.with_user(self.bbb_admin_user).action_assign()
        main.room_id = self.hall
        main.with_user(self.bbb_admin_user).action_assign()
        self.assertEqual(self.hall.bbb_meeting_id, "gl-main-hall-0001")

        other_day = self.day.copy({"name": "Other Bbb Day"})
        main.room_id = other_day.room_ids[:1]
        with self.assertRaises(UserError):
            main.action_assign()

    def test_meeting_id_is_chosen_by_the_settings_group(self):
        """The secret signs any call on any meeting of the server: only
        the Settings group lists those meetings and points a room at one.
        An event Administrator clears a meeting ID, or keeps one a room
        already carries (a copied room or day), never a new one."""
        foreign = "gl-invented-foreign-0009"
        manager = self.manager_user
        self.assertFalse(manager._is_system())
        network = FakeNetwork()
        with fake_network(network):
            with self.assertRaises(AccessError):
                self.day.with_user(manager).action_open_bbb_meetings()
        self.assertFalse(network.api_calls("getMeetings"))
        Room = self.env["event.webapp.room"].with_user(manager)
        with self.assertRaises(AccessError):
            self.hall.with_user(manager).bbb_meeting_id = foreign
        with self.assertRaises(AccessError):
            Room.create(
                {
                    "webapp_id": self.day.id,
                    "name": "Foreign",
                    "bbb_meeting_id": foreign,
                }
            )
        self.assertEqual(self.hall.bbb_meeting_id, MEETING)
        # Copies keep the meeting a Settings user chose.
        room = self.hall.with_user(manager).copy({"name": "Hall copy"})
        self.assertEqual(room.bbb_meeting_id, MEETING)
        day = self.day.with_user(manager).copy({"name": "Copied Bbb Day"})
        self.assertEqual(
            set(day.room_ids.mapped("bbb_meeting_id")),
            {MEETING, "gl-workshop-0002"},
        )
        room.write({"bbb_meeting_id": "  "})
        self.assertFalse(room.bbb_meeting_id)
        room.write({"name": "Hall copy, no meeting"})

        # The wizard refuses the assignment to a manager.
        with fake_network(FakeNetwork()):
            action = self.day.with_user(
                self.bbb_admin_user
            ).action_open_bbb_meetings()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        line = wizard.line_ids.filtered(
            lambda line_: line_.meeting_id == "gl-main-hall-0001"
        )
        line.room_id = self.hall
        with self.assertRaises(AccessError):
            line.with_user(manager).action_assign()
        with self.assertRaises(AccessError):
            wizard.with_user(manager).action_refresh()
        self.assertEqual(self.hall.bbb_meeting_id, MEETING)
        # A Settings user, also event Administrator, chooses freely.
        self.hall.with_user(self.bbb_admin_user).bbb_meeting_id = foreign
        self.assertEqual(self.hall.bbb_meeting_id, foreign)

    def test_meeting_id_from_a_default_is_checked(self):
        """create() fills a field left out of the values with its default,
        from the context or from a personal ir.default that any internal
        user records for themselves: such a meeting ID is checked like a
        value given by the caller."""
        foreign = "gl-invented-foreign-0010"
        manager = self.manager_user
        Room = self.env["event.webapp.room"].with_user(manager)
        vals = {"webapp_id": self.day.id, "name": "Foreign default"}
        with self.assertRaises(AccessError):
            Room.with_context(default_bbb_meeting_id=foreign).create(vals)
        with self.assertRaises(AccessError):
            self.day.with_user(manager).with_context(
                default_bbb_meeting_id=foreign
            ).write({"room_ids": [Command.create({"name": "Foreign room"})]})
        field = self.env["ir.model.fields"]._get(
            "event.webapp.room", "bbb_meeting_id"
        )
        self.env["ir.default"].with_user(manager).create(
            {
                "field_id": field.id,
                "json_value": json.dumps(foreign),
                "user_id": manager.id,
            }
        )
        with self.assertRaises(AccessError):
            Room.create(vals)
        self.assertFalse(
            self.env["event.webapp.room"].search(
                [("bbb_meeting_id", "=", foreign)]
            )
        )
        # A default that a room already carries stays free, as a value.
        room = Room.with_context(default_bbb_meeting_id=MEETING).create(vals)
        self.assertEqual(room.bbb_meeting_id, MEETING)

    def test_forget_secret_is_reserved_to_the_administrators(self):
        """RPC reaches the button on an empty settings record, which no
        access right covers: the method checks the caller itself."""
        Settings = self.env["res.config.settings"]
        for user in (
            self.portal_user,
            self.internal_user,
            self.moderator_user,
            self.manager_user,
        ):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    Settings.with_user(user).action_ewp_bbb_forget_secret()
                self.assertEqual(
                    self.params.get_param(PARAM_BBB_SECRET), SECRET
                )
        Settings.with_user(self.bbb_admin_user).action_ewp_bbb_forget_secret()
        self.assertFalse(self.params.get_param(PARAM_BBB_SECRET))

    def test_api_timeouts_and_meeting_state_cache(self):
        network = FakeNetwork(running=True)
        clock = [1000.0]
        with fake_network(network), mock.patch.object(
            bbb_client, "_clock", lambda: clock[0]
        ):
            self.assertTrue(self.hall._ewp_bbb_running())
            url, kwargs = network.calls[-1]
            self.assertIn("/getMeetingInfo?", url)
            # (connect, read): a silent server holds a worker 3 s at most
            # before the connection fails.
            self.assertEqual(kwargs["timeout"], bbb_client.API_TIMEOUT)
            self.assertLessEqual(kwargs["timeout"][0], 3)

            # Page views and status polls within RUNNING_TTL share one call.
            for _i in range(5):
                self.assertEqual(self.hall._ewp_bbb_target()["state"], "frame")
            self.assertEqual(network.api_calls("getMeetingInfo"), 1)
            # Each meeting has its own entry.
            self.workshop._ewp_bbb_running()
            self.assertEqual(network.api_calls("getMeetingInfo"), 2)
            clock[0] += bbb_client.RUNNING_TTL + 1
            self.hall._ewp_bbb_running()
            self.assertEqual(network.api_calls("getMeetingInfo"), 3)

            # An unreachable server is called once per FAILURE_TTL, for
            # every meeting of that server.
            network.api_error = "network"
            with self.assertLogs(
                "odoo.addons.event_webapp_plan.models." "event_webapp_room",
                level="WARNING",
            ) as logs:
                self.assertIsNone(self.hall._ewp_bbb_running())
                for room in (self.hall, self.workshop, self.hall):
                    self.assertEqual(
                        room._ewp_bbb_target()["state"], "unavailable"
                    )
            self.assertEqual(len(logs.output), 1)
            self.assertEqual(network.api_calls("getMeetingInfo"), 4)
            clock[0] += bbb_client.FAILURE_TTL - 1
            self.assertIsNone(self.workshop._ewp_bbb_running())
            self.assertEqual(network.api_calls("getMeetingInfo"), 4)
            # Once the delay is over, the server is asked again. The state
            # changes without emptying the cache, as on a real server.
            network.__dict__["api_error"] = None
            clock[0] += 2
            self.assertTrue(self.hall._ewp_bbb_running())
            self.assertEqual(network.api_calls("getMeetingInfo"), 5)

            # A meeting the server does not know is not running, and its
            # answer is cached like any other.
            network.running = False
            self.assertIs(self.hall._ewp_bbb_running(), False)
            self.assertEqual(self.hall._ewp_bbb_target()["state"], "waiting")
            self.assertEqual(network.api_calls("getMeetingInfo"), 6)

    def test_fresh_read_refuses_an_older_meeting_state(self):
        """A read with max_age asks the server again once the cached state
        is older than that, and its answer serves every reader; a younger
        state is shared."""
        network = FakeNetwork(running=True)
        clock = [1000.0]
        fresh = bbb_client.FRESH_TTL
        with fake_network(network), mock.patch.object(
            bbb_client, "_clock", lambda: clock[0]
        ):
            self.assertTrue(self.hall._ewp_bbb_running())
            clock[0] += fresh - 1
            self.assertTrue(self.hall._ewp_bbb_running(max_age=fresh))
            self.assertEqual(network.api_calls("getMeetingInfo"), 1)
            # The meeting ends; the cache still says it runs, without
            # being emptied, as on a real server.
            network.__dict__["running"] = False
            clock[0] += 2
            self.assertTrue(self.hall._ewp_bbb_running())
            self.assertEqual(network.api_calls("getMeetingInfo"), 1)
            self.assertIs(self.hall._ewp_bbb_running(max_age=fresh), False)
            self.assertEqual(network.api_calls("getMeetingInfo"), 2)
            self.assertEqual(self.hall._ewp_bbb_target()["state"], "waiting")
            self.assertEqual(network.api_calls("getMeetingInfo"), 2)

    def test_api_errors_never_chain_the_signed_url(self):
        """The requests exception names the signed URL; neither BbbError
        nor the UserError of the wizard carries it, even in the chain of
        causes that Odoo formats into a JSON-RPC error."""
        signed = bbb_client.call_url(API, SECRET, "getMeetings")
        signature = signed.rpartition("checksum=")[2]
        with fake_network(FakeNetwork(api_error="network")):
            with self.assertRaises(bbb_client.BbbError) as caught:
                bbb_client.get_meetings(API, SECRET)
            text = "".join(traceback.format_exception(caught.exception))
            self.assertNotIn("checksum=", text)
            self.assertNotIn(signature, text)
            with self.assertRaises(UserError) as caught:
                self.day.with_user(
                    self.bbb_admin_user
                ).action_open_bbb_meetings()
            text = "".join(traceback.format_exception(caught.exception))
            self.assertIn("cannot be reached", text)
            self.assertNotIn("checksum=", text)
            self.assertNotIn(signature, text)
            self.assertNotIn(SECRET, text)

    def test_running_meetings_errors(self):
        day = self.day.with_user(self.bbb_admin_user)
        for api_error, text in (
            ("network", "cannot be reached"),
            ("http", "502"),
        ):
            with self.subTest(api_error=api_error):
                with fake_network(FakeNetwork(api_error=api_error)):
                    with self.assertRaises(UserError) as caught:
                        day.action_open_bbb_meetings()
                self.assertIn(text, str(caught.exception))
        self.params.set_param(PARAM_BBB_SECRET, "a-wrong-invented-secret")
        with fake_network(FakeNetwork()):
            with self.assertRaises(UserError) as caught:
                day.action_open_bbb_meetings()
        self.assertIn("shared secret", str(caught.exception))
        self.assertNotIn("a-wrong-invented-secret", str(caught.exception))

        self.params.set_param(PARAM_BBB_SECRET, False)
        self.assertFalse(self.day.bbb_configured)
        with self.assertRaises(UserError):
            day.action_open_bbb_meetings()


@tagged("post_install", "-at_install")
class TestBbbRoomPage(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_URL, SERVER)
        params.set_param(PARAM_BBB_SECRET, SECRET)
        # The fake server is on another site than the test server: the
        # frame tests force the embedded display, and the tests of the
        # display modes set the mode they check.
        params.set_param(PARAM_BBB_DISPLAY, "frame")
        cls.env["event.webapp"].search([]).write({"active": False})
        cls.portal_user = new_test_user(
            cls.env,
            login="ewp_bbb_portal",
            password="ewp_bbb_portal",
            groups="base.group_portal",
            name="Portal Bbb Visitor",
            lang="en_US",
        )
        cls.internal_user = new_test_user(
            cls.env,
            login="ewp_bbb_internal",
            password="ewp_bbb_internal",
            groups="base.group_user",
            name="Internal Bbb Visitor",
            lang="en_US",
        )
        cls.moderator_user = new_test_user(
            cls.env,
            login="ewp_bbb_moderator",
            password="ewp_bbb_moderator",
            groups="base.group_user," + MODERATOR,
            name="Moderator Bbb Visitor",
            lang="en_US",
        )
        now = fields.Datetime.now()
        network = FakeNetwork(
            frames={
                ROOM_URL: {"X-Frame-Options": "SAMEORIGIN"},
                ROOM_URL_REFUSED: {
                    "Content-Security-Policy": "frame-ancestors 'self'"
                },
            }
        )
        with fake_network(network):
            cls.day = cls.env["event.webapp"].create(
                {
                    "name": "Bbb Page Day",
                    "date_start": now - timedelta(hours=1),
                    "date_end": now + timedelta(hours=8),
                    "room_ids": [
                        Command.create(
                            {"name": "Api Room", "bbb_meeting_id": MEETING}
                        ),
                        Command.create(
                            {
                                "name": "Fallback Room",
                                "bbb_meeting_id": MEETING,
                                "bbb_room_url": ROOM_URL,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Framed Room",
                                "bbb_room_url": ROOM_URL_FRAMED,
                            }
                        ),
                        Command.create(
                            {
                                "name": "Refused Room",
                                "bbb_room_url": ROOM_URL_REFUSED,
                            }
                        ),
                        Command.create({"name": "Plain Room"}),
                    ],
                }
            )
            cls.day_future = cls.env["event.webapp"].create(
                {
                    "name": "Bbb Future Day",
                    "date_start": now + timedelta(days=30),
                    "date_end": now + timedelta(days=30, hours=8),
                    "room_ids": [
                        Command.create(
                            {"name": "Later Room", "bbb_meeting_id": MEETING}
                        )
                    ],
                }
            )
        rooms = {room.name: room for room in cls.day.room_ids}
        cls.room_api = rooms["Api Room"]
        cls.room_fallback = rooms["Fallback Room"]
        cls.room_framed = rooms["Framed Room"]
        cls.room_refused = rooms["Refused Room"]
        cls.room_plain = rooms["Plain Room"]
        cls.room_later = cls.day_future.room_ids

    def _get(self, url):
        self.env.flush_all()
        response = self.url_open(url, allow_redirects=False)
        self.env.invalidate_all()
        return response

    def _room_url(self, room, suffix=""):
        return "/webapp_event/%s/room/%s%s" % (
            room.webapp_id.id,
            room.id,
            suffix,
        )

    def _page(self, room):
        response = self._get(self._room_url(room))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(SECRET, response.text)
        return response, lxml_html.fromstring(response.text)

    def test_running_meeting_is_framed_with_a_join_url(self):
        for login, user, role in (
            ("ewp_bbb_portal", self.portal_user, "VIEWER"),
            ("ewp_bbb_internal", self.internal_user, "VIEWER"),
            ("ewp_bbb_moderator", self.moderator_user, "MODERATOR"),
        ):
            with self.subTest(login=login):
                self.authenticate(login, login)
                with fake_network(FakeNetwork(running=True)):
                    response, page = self._page(self.room_api)
                    frames = page.xpath(
                        "//iframe[contains(@class, 'o_ewp_bbb')]"
                    )
                    self.assertEqual(len(frames), 1)
                    # The frame loads the room route, which redirects to a
                    # fresh join URL: the page names no server.
                    src = frames[0].get("src")
                    self.assertEqual(
                        src, self._room_url(self.room_api, "/bbb_join?frame=1")
                    )
                    self.assertNotIn("bbb.example.org", response.text)
                    self.assertNotIn("checksum", response.text)
                    redirect = self._get(src)
                self.assertEqual(redirect.status_code, 302)
                location = redirect.headers["Location"]
                self.assertTrue(location.startswith(API + "/join?"), location)
                params, query = _query(location)
                self.assertEqual(params["role"], role)
                self.assertEqual(params["fullName"], user.name)
                self.assertEqual(params["userID"], "odoo-%s" % user.id)
                self.assertEqual(params["meetingID"], MEETING)
                self.assertEqual(params["createTime"], CREATE_TIME)
                self.assertEqual(
                    params["checksum"],
                    bbb_client.checksum("join", query, SECRET),
                )
                # Every feature is granted to any origin: the join URL
                # redirects to the client, possibly on another host.
                allow = [
                    item.strip() for item in frames[0].get("allow").split(";")
                ]
                for feature in ("camera", "microphone", "display-capture"):
                    self.assertIn(feature + " *", allow)
                self.assertTrue(all(item.endswith(" *") for item in allow))
                self.assertIsNotNone(frames[0].get("allowfullscreen"))
                # The meeting runs: the app bar says Live.
                self.assertTrue(
                    page.xpath("//header//*[contains(@class, 'o_ewp_pill')]")
                )
                # The notice that replaces the frame once the conference
                # opens in a new tab is there, hidden.
                moved = page.xpath("//*[contains(@class, 'o_ewp_bbb_moved')]")
                self.assertEqual(len(moved), 1)
                self.assertIsNotNone(moved[0].get("hidden"))
                links = page.xpath("//a[contains(@class, 'o_ewp_bbb_newtab')]")
                self.assertEqual(
                    links[0].get("href"),
                    self._room_url(self.room_api, "/bbb_join"),
                )
                self.assertEqual(links[0].get("target"), "_blank")
                self.assertIn("noopener", links[0].get("rel"))
                # The room chat stays next to the conference.
                self.assertTrue(page.xpath("//iframe[@class='o_ewp_chat']"))

    def test_text_only_mode_shows_the_conference_on_demand(self):
        """In text-only mode the conference frame ships hidden and without
        src, behind "Show the video conference"; the link that opens it in
        a new tab and the chat stay."""
        self.portal_user.ewp_text_only = True
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        with fake_network(FakeNetwork(running=True)):
            response, page = self._page(self.room_api)
        frame = page.xpath("//iframe[contains(@class, 'o_ewp_bbb_frame')]")[0]
        self.assertIsNone(frame.get("src"))
        self.assertEqual(
            frame.get("data-ewp-src"),
            self._room_url(self.room_api, "/bbb_join?frame=1"),
        )
        self.assertTrue(frame.get("title"))
        video = page.xpath("//div[@id='o_ewp_video']")[0]
        self.assertIsNotNone(video.get("hidden"))
        buttons = page.xpath("//button[contains(@class, 'o_ewp_bbb_show')]")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("aria-controls"), "o_ewp_video")
        self.assertEqual(buttons[0].get("aria-expanded"), "false")
        self.assertEqual(
            buttons[0].text_content().strip(), "Show the video conference"
        )
        links = page.xpath("//a[contains(@class, 'o_ewp_bbb_newtab')]")
        self.assertEqual(
            links[0].get("href"), self._room_url(self.room_api, "/bbb_join")
        )
        self.assertTrue(page.xpath("//iframe[@class='o_ewp_chat']"))
        self.assertNotIn("bbb.example.org", response.text)

        # Outside text-only mode, the frame loads at once.
        self.portal_user.ewp_text_only = False
        with fake_network(FakeNetwork(running=True)):
            response, page = self._page(self.room_api)
        self.assertFalse(page.xpath("//*[contains(@class, 'o_ewp_bbb_show')]"))
        frame = page.xpath("//iframe[contains(@class, 'o_ewp_bbb_frame')]")[0]
        self.assertEqual(
            frame.get("src"),
            self._room_url(self.room_api, "/bbb_join?frame=1"),
        )
        self.assertIsNone(
            page.xpath("//div[@id='o_ewp_video']")[0].get("hidden")
        )

    def test_live_route_lists_the_rooms_whose_meeting_runs(self):
        """The home page carries the live route on its room list and a
        hidden "Live" pill on each room with a meeting ID; the route lists
        the rooms whose meeting runs, never a conference URL alone, and
        names neither the server nor a meeting ID."""
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        live_url = "/webapp_event/%s/live" % self.day.id
        response = self._get("/webapp_event/%s" % self.day.id)
        page = lxml_html.fromstring(response.text)
        self.assertEqual(
            page.xpath(
                "//ul[contains(@class, 'o_ewp_rooms')]/@data-ewp-live-url"
            ),
            [live_url],
        )
        pills = page.xpath(
            "//a[contains(@class, 'o_ewp_room_link')]"
            "[.//span[contains(@class, 'o_ewp_pill_live')]]"
            "//span[@class='o_ewp_room_name']"
        )
        self.assertEqual(
            [pill.text for pill in pills], ["Api Room", "Fallback Room"]
        )
        for pill in page.xpath("//span[contains(@class, 'o_ewp_pill_live')]"):
            self.assertIsNotNone(pill.get("hidden"))
            self.assertIn("Live", pill.text_content())
        with fake_network(FakeNetwork(running=True)):
            response = self._get(live_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(
            sorted(response.json()["live"]),
            sorted((self.room_api | self.room_fallback).ids),
        )
        self.assertNotIn("example.org", response.text)
        self.assertNotIn(MEETING, response.text)
        for network in (
            FakeNetwork(running=False),
            FakeNetwork(api_error="network"),
        ):
            with self.subTest(network=vars(network)):
                with fake_network(network):
                    response = self._get(live_url)
                self.assertEqual(response.json(), {"live": []})
        # Outside the opening window the route is closed to visitors, and
        # anonymous visitors are sent to the login page.
        response = self._get("/webapp_event/%s/live" % self.day_future.id)
        self.assertEqual(response.status_code, 403)
        self.authenticate(None, None)
        response = self._get(live_url)
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(
            urlsplit(response.headers["Location"]).path, "/web/login"
        )

    def test_home_page_without_meeting_has_no_live_route(self):
        self.env["ir.config_parameter"].sudo().set_param(PARAM_BBB_SECRET, "")
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        response = self._get("/webapp_event/%s" % self.day.id)
        page = lxml_html.fromstring(response.text)
        self.assertFalse(page.xpath("//*[@data-ewp-live-url]"))
        self.assertFalse(
            page.xpath("//*[contains(@class, 'o_ewp_pill_live')]")
        )
        with fake_network(FakeNetwork(running=True)):
            response = self._get("/webapp_event/%s/live" % self.day.id)
        self.assertEqual(response.json(), {"live": []})

    def test_room_pills_are_part_of_the_link_name(self):
        """WCAG 2.5.3, label in name: the words that the pills of a room
        link show ("Video", "Live") are part of the name that screen
        readers give the link, in English and in French."""
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.ref("base.module_event_webapp_plan")._update_translations(
            ["fr_CA"]
        )

        def text(node, skip):
            """Text of `node` without the subtrees for which `skip` is
            true; the tail of a skipped element is kept."""
            if skip(node):
                return ""
            parts = [node.text or ""]
            for child in node:
                parts.append(text(child, skip))
                parts.append(child.tail or "")
            return "".join(parts)

        def words(value):
            return " ".join(value.split())

        def aria_hidden(node):
            return node.get("aria-hidden") == "true"

        def sr_only(node):
            return "o_ewp_sr_only" in (node.get("class") or "").split()

        for lang, expected in (
            ("en_US", {"Video", "Live"}),
            ("fr_CA", {"Vidéo", "En direct"}),
        ):
            with self.subTest(lang=lang):
                # The session takes the language of the user at login.
                self.portal_user.lang = lang
                self.env.flush_all()
                self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
                response = self._get("/webapp_event/%s" % self.day.id)
                page = lxml_html.fromstring(response.text)
                shown = set()
                for link in page.xpath(
                    "//a[contains(@class, 'o_ewp_room_link')]"
                ):
                    name = words(text(link, aria_hidden))
                    for pill in link.xpath(
                        ".//span[contains(concat(' ', @class, ' '), "
                        "' o_ewp_pill ')]"
                    ):
                        seen = words(text(pill, sr_only))
                        shown.add(seen)
                        self.assertIn(seen, name)
                self.assertEqual(shown, expected)

    def test_meeting_not_started_waits_and_polls(self):
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        network = FakeNetwork(running=False)
        with fake_network(network):
            response, page = self._page(self.room_api)
            self.assertIn("The conference has not started yet", response.text)
            self.assertFalse(
                page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")
            )
            self.assertEqual(page.xpath("//@data-ewp-bbb-error"), ["0"])
            self.assertFalse(
                page.xpath("//header//*[contains(@class, 'o_ewp_pill')]")
            )
            status_url = page.xpath("//@data-ewp-bbb-status-url")[0]
            self.assertEqual(
                status_url, self._room_url(self.room_api, "/bbb_status")
            )
            response = self._get(status_url)
            self.assertEqual(
                json.loads(response.text),
                {"running": False, "error": False, "state": "waiting"},
            )
            network.running = True
            response = self._get(status_url)
            self.assertEqual(
                json.loads(response.text),
                {"running": True, "error": False, "state": "running"},
            )
            self.assertNotIn(SECRET, response.text)
            self.assertNotIn("checksum", response.text)

    def test_server_error_falls_back_to_the_conference_url(self):
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        for api_error in ("network", "http"):
            with self.subTest(api_error=api_error), fake_network(
                FakeNetwork(api_error=api_error)
            ):
                # Conference URL refused in a frame: the button.
                response, page = self._page(self.room_fallback)
                self.assertIn("does not answer", response.text)
                buttons = page.xpath("//a[contains(@class, 'o_ewp_bbb_join')]")
                self.assertEqual(
                    buttons[0].get("href"),
                    self._room_url(self.room_fallback, "/bbb_join"),
                )
                self.assertIn("Join the conference", response.text)
                self.assertFalse(
                    page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")
                )
                # No conference URL: the notice, and the page keeps polling.
                response, page = self._page(self.room_api)
                self.assertIn("does not answer", response.text)
                self.assertTrue(page.xpath("//@data-ewp-bbb-status-url"))
                # Rendered in error: the script reloads once the server
                # answers again.
                self.assertEqual(page.xpath("//@data-ewp-bbb-error"), ["1"])
                response = self._get(
                    self._room_url(self.room_api, "/bbb_status")
                )
                self.assertEqual(
                    json.loads(response.text),
                    {"running": False, "error": True, "state": "unavailable"},
                )

    def test_conference_url_framed_or_behind_a_button(self):
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        self.assertTrue(self.room_framed.bbb_frameable)
        self.assertFalse(self.room_refused.bbb_frameable)
        with fake_network(FakeNetwork()) as network:
            response, page = self._page(self.room_framed)
            frames = page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")
            src = frames[0].get("src")
            self.assertEqual(
                src, self._room_url(self.room_framed, "/bbb_join?frame=1")
            )
            self.assertNotIn(ROOM_URL_FRAMED, response.text)
            redirect = self._get(src)
            self.assertEqual(redirect.status_code, 302)
            self.assertEqual(redirect.headers["Location"], ROOM_URL_FRAMED)
            # A conference URL tells nothing about a running session.
            self.assertFalse(
                page.xpath("//header//*[contains(@class, 'o_ewp_pill')]")
            )
            self.assertTrue(
                page.xpath("//a[contains(@class, 'o_ewp_bbb_newtab')]")
            )

            response, page = self._page(self.room_refused)
            self.assertIn("Join the conference", response.text)
            self.assertFalse(
                page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")
            )

            response, page = self._page(self.room_plain)
            self.assertFalse(page.xpath("//*[contains(@class, 'o_ewp_bbb')]"))
            self.assertTrue(page.xpath("//iframe[@class='o_ewp_chat']"))
            # Rooms without meeting ID never call the server.
            self.assertFalse(network.calls)

    def test_running_meeting_on_another_site_behind_the_button(self):
        """Mode auto, server on another site than the page (the test
        server answers on 127.0.0.1): the running meeting is behind the new
        tab button, never in a frame; the status route reports the state
        the page renders, and the page polls it."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(PARAM_BBB_DISPLAY, "auto")
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        status = self._room_url(self.room_api, "/bbb_status")
        network = FakeNetwork(running=True)
        with fake_network(network):
            response, page = self._page(self.room_api)
            self.assertFalse(
                page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")
            )
            self.assertFalse(
                page.xpath("//*[contains(@class, 'o_ewp_bbb_left')]")
            )
            self.assertFalse(
                page.xpath("//*[contains(@class, 'o_ewp_bbb_notice')]")
            )
            section = page.xpath("//section[contains(@class, 'o_ewp_bbb')]")[0]
            self.assertEqual(section.get("data-ewp-bbb-state"), "button")
            self.assertEqual(section.get("data-ewp-bbb-live"), "1")
            box = section.xpath(
                ".//div[contains(@class, 'o_ewp_bbb_tab_live')]"
            )[0]
            text = " ".join(box.text_content().split())
            self.assertIn("The video conference is live.", text)
            self.assertIn(
                "It opens in a new tab: this page and its discussion stay "
                "open.",
                text,
            )
            self.assertEqual(box.get("data-ewp-bbb-status-url"), status)
            self.assertEqual(box.get("data-ewp-bbb-error"), "0")
            links = box.xpath(".//a[contains(@class, 'o_ewp_bbb_join')]")
            self.assertEqual(len(links), 1)
            link = links[0]
            self.assertEqual(
                link.get("href"), self._room_url(self.room_api, "/bbb_join")
            )
            self.assertEqual(link.get("target"), "_blank")
            self.assertIn("noopener", link.get("rel"))
            name = " ".join(link.text_content().split())
            self.assertEqual(
                name, "Join the video conference (opens in a new tab)"
            )
            # The app bar still says Live, the chat stays.
            self.assertTrue(
                page.xpath("//header//*[contains(@class, 'o_ewp_pill')]")
            )
            self.assertTrue(page.xpath("//iframe[@class='o_ewp_chat']"))
            self.assertNotIn("bbb.example.org", response.text)
            self.assertNotIn("checksum", response.text)
            self.assertEqual(
                self._get(status).json(),
                {"running": True, "error": False, "state": "button"},
            )
            # A join outside the frame leads back to the room page.
            redirect = self._get(link.get("href"))
            self.assertEqual(redirect.status_code, 302)
            params_join, _query_string = _query(redirect.headers["Location"])
            self.assertEqual(
                params_join["logoutURL"],
                self.base_url() + self._room_url(self.room_api, "/bbb_left"),
            )
            # The meeting ends: the status route and the page agree.
            network.running = False
            self.assertEqual(
                self._get(status).json(),
                {"running": False, "error": False, "state": "waiting"},
            )
            response, page = self._page(self.room_api)
            self.assertEqual(
                page.xpath("//section/@data-ewp-bbb-state"), ["waiting"]
            )
            # Forced modes.
            network.running = True
            for mode, state in (("frame", "running"), ("tab", "button")):
                with self.subTest(mode=mode):
                    params.set_param(PARAM_BBB_DISPLAY, mode)
                    response, page = self._page(self.room_api)
                    self.assertEqual(
                        page.xpath("//section/@data-ewp-bbb-state"), [state]
                    )
                    self.assertEqual(self._get(status).json()["state"], state)

    def test_conference_url_display_modes(self):
        """A framed conference URL is embedded in mode auto only when it
        is on the same site as the page; behind the button it keeps the
        "Join the conference" text and the hint, without polling."""
        params = self.env["ir.config_parameter"].sudo()
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        with fake_network(FakeNetwork()):
            room_same = self.env["event.webapp.room"].create(
                {
                    "webapp_id": self.day.id,
                    "name": "Same Site Room",
                    "bbb_room_url": self.base_url() + "/conference/display",
                }
            )
        self.assertTrue(room_same.bbb_frameable)
        self.assertTrue(self.room_framed.bbb_frameable)
        for mode, room, state in (
            ("auto", room_same, "frame"),
            ("auto", self.room_framed, "button"),
            ("frame", self.room_framed, "frame"),
            ("tab", room_same, "button"),
        ):
            with self.subTest(mode=mode, room=room.name):
                params.set_param(PARAM_BBB_DISPLAY, mode)
                with fake_network(FakeNetwork()) as network:
                    response, page = self._page(room)
                    self.assertFalse(network.calls)
                section = page.xpath(
                    "//section[contains(@class, 'o_ewp_bbb')]"
                )[0]
                self.assertEqual(section.get("data-ewp-bbb-state"), state)
                self.assertEqual(section.get("data-ewp-bbb-live"), "0")
                frames = page.xpath(
                    "//iframe[contains(@class, 'o_ewp_bbb_frame')]"
                )
                if state == "frame":
                    self.assertEqual(len(frames), 1)
                    continue
                self.assertFalse(frames)
                self.assertFalse(
                    page.xpath("//*[contains(@class, 'o_ewp_bbb_tab_live')]")
                )
                box = section.xpath(
                    ".//div[contains(@class, 'o_ewp_bbb_tab')]"
                )[0]
                # A conference URL alone never changes on the server.
                self.assertIsNone(box.get("data-ewp-bbb-status-url"))
                text = " ".join(box.text_content().split())
                self.assertIn("Join the conference", text)
                self.assertIn("this page and its discussion stay open", text)
                link = box.xpath(".//a[contains(@class, 'o_ewp_bbb_join')]")[0]
                self.assertEqual(link.get("target"), "_blank")

    def test_bbb_join_redirects_to_a_fresh_join_url(self):
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        network = FakeNetwork(running=True)
        with fake_network(network):
            response = self._get(self._room_url(self.room_api, "/bbb_join"))
            self.assertEqual(response.status_code, 302)
            location = response.headers["Location"]
            self.assertTrue(location.startswith(API + "/join?"), location)
            params, _query_string = _query(location)
            self.assertEqual(params["role"], "VIEWER")
            self.assertNotIn(SECRET, location)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

            response = self._get(
                self._room_url(self.room_refused, "/bbb_join")
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], ROOM_URL_REFUSED)

            # Not started yet, or no conference: back to the room page; the
            # conference frame gets an empty answer, not a copy of the page.
            network.running = False
            for room in (self.room_api, self.room_plain):
                with self.subTest(room=room.name):
                    response = self._get(self._room_url(room, "/bbb_join"))
                    self.assertIn(response.status_code, (302, 303))
                    self.assertEqual(
                        urlsplit(response.headers["Location"]).path,
                        self._room_url(room),
                    )
                    response = self._get(
                        self._room_url(room, "/bbb_join?frame=1")
                    )
                    self.assertEqual(response.status_code, 204)
                    self.assertNotIn("Location", response.headers)
                    self.assertFalse(response.text)
                    self.assertEqual(
                        response.headers.get("Cache-Control"), "no-store"
                    )

    def test_bbb_routes_check_access(self):
        with fake_network(FakeNetwork(running=True)):
            # Anonymous visitors go to the login page. The session pins the
            # test database, whatever the db filter matches.
            self.authenticate(None, None)
            for suffix in ("/bbb_join", "/bbb_status"):
                response = self._get(self._room_url(self.room_api, suffix))
                self.assertIn(response.status_code, (302, 303))
                self.assertEqual(
                    urlsplit(response.headers["Location"]).path, "/web/login"
                )

            self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
            response = self._get(self._room_url(self.room_later, "/bbb_join"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("not open yet", response.text)
            self.assertNotIn(API, response.text)
            response = self._get(
                self._room_url(self.room_later, "/bbb_status")
            )
            self.assertEqual(response.status_code, 403)
            # A room through another day: not found.
            for suffix in ("/bbb_join", "/bbb_status"):
                response = self._get(
                    "/webapp_event/%s/room/%s%s"
                    % (self.day.id, self.room_later.id, suffix)
                )
                self.assertEqual(response.status_code, 404)

            self.authenticate("ewp_bbb_moderator", "ewp_bbb_moderator")
            response = self._get(self._room_url(self.room_later, "/bbb_join"))
            self.assertEqual(response.status_code, 302)
            params, _query_string = _query(response.headers["Location"])
            self.assertEqual(params["role"], "MODERATOR")

    def test_join_again_check_skips_the_cached_state(self):
        """The meeting ends and every client loads the logoutURL at once:
        the check of "Join again" (fresh=1) asks the server instead of
        the state cached before the end, which the status poll keeps."""
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        network = FakeNetwork(running=True)
        clock = [1000.0]
        status = self._room_url(self.room_api, "/bbb_status")
        with fake_network(network), mock.patch.object(
            bbb_client, "_clock", lambda: clock[0]
        ):
            self.assertTrue(self._get(status).json()["running"])
            network.__dict__["running"] = False
            clock[0] += bbb_client.FRESH_TTL + 1
            self.assertTrue(self._get(status).json()["running"])
            self.assertEqual(network.api_calls("getMeetingInfo"), 1)
            answer = self._get(status + "?fresh=1")
            self.assertEqual(answer.status_code, 200)
            self.assertEqual(
                answer.json(),
                {"running": False, "error": False, "state": "waiting"},
            )
            self.assertEqual(network.api_calls("getMeetingInfo"), 2)
            # The fresh answer replaced the entry: no join URL now.
            redirect = self._get(
                self._room_url(self.room_api, "/bbb_join?frame=1")
            )
            self.assertEqual(redirect.status_code, 204)

    def test_leaving_the_meeting_shows_a_notice(self):
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        left_path = self._room_url(self.room_api, "/bbb_left")
        with fake_network(FakeNetwork(running=True)):
            response, page = self._page(self.room_api)
            # The notice and its button ship hidden in the frame block.
            notices = page.xpath(
                "//div[contains(@class, 'o_ewp_video')]"
                "/div[contains(@class, 'o_ewp_bbb_left')]"
            )
            self.assertEqual(len(notices), 1)
            notice = notices[0]
            self.assertIsNotNone(notice.get("hidden"))
            self.assertEqual(notice.get("data-ewp-bbb-left-path"), left_path)
            self.assertEqual(
                notice.get("data-ewp-bbb-check-url"),
                self._room_url(self.room_api, "/bbb_status?fresh=1"),
            )
            # The notice is no live region of its own: the page script
            # says "You left the conference." in the shared region.
            self.assertEqual(
                notice.xpath(".//p")[0].text_content().strip(),
                "You left the conference.",
            )
            self.assertFalse(notice.xpath(".//*[@role or @aria-live]"))
            self.assertIn(
                "You left the conference.",
                json.loads(
                    page.xpath("//*[@id='o_ewp_announcer']")[0].get(
                        "data-ewp-messages"
                    )
                )["bbb_left"],
            )
            buttons = notice.xpath(".//button[@type='button']")
            self.assertEqual(buttons[0].text_content().strip(), "Join again")
            self.assertIn("o_ewp_bbb_rejoin", buttons[0].get("class"))
            # The join URL sends the client back to the same origin once
            # the user leaves: the frame to the page its script
            # recognises, a join of its own tab to the redirect.
            redirect = self._get(
                self._room_url(self.room_api, "/bbb_join?frame=1")
            )
            params, query = _query(redirect.headers["Location"])
            self.assertEqual(
                params["logoutURL"], self.base_url() + left_path + "?frame=1"
            )
            self.assertEqual(
                params["checksum"], bbb_client.checksum("join", query, SECRET)
            )
            redirect = self._get(self._room_url(self.room_api, "/bbb_join"))
            params, query = _query(redirect.headers["Location"])
            self.assertEqual(params["logoutURL"], self.base_url() + left_path)
            self.assertEqual(
                params["checksum"], bbb_client.checksum("join", query, SECRET)
            )

            # Outside the frame: back to the room page, marked left, which
            # that tab then shows.
            response = self._get(left_path + "?reason=You+left")
            self.assertEqual(response.status_code, 303)
            location = urlsplit(response.headers["Location"])
            self.assertEqual(location.path, self._room_url(self.room_api))
            self.assertEqual(location.query, "left=1")
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")

            # In the frame, the client adds the reason of the leave to the
            # query.
            response = self._get(left_path + "?frame=1&reason=You+left")
            self.assertEqual(response.status_code, 200)
            self.assertIn("You left the conference.", response.text)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
            # Framed by the room page of the same origin.
            self.assertNotIn(
                "DENY", response.headers.get("X-Frame-Options", "")
            )
            page = lxml_html.fromstring(response.text)
            links = page.xpath(
                "//a[@href='%s']" % self._room_url(self.room_api)
            )
            self.assertEqual(links[0].get("target"), "_top")
            self.assertNotIn("bbb.example.org", response.text)
            self.assertNotIn("checksum", response.text)

            # A framed conference URL loads pages of its own: no notice.
            response, page = self._page(self.room_framed)
            self.assertTrue(
                page.xpath("//iframe[contains(@class, 'o_ewp_bbb_frame')]")
            )
            self.assertFalse(
                page.xpath("//*[contains(@class, 'o_ewp_bbb_left')]")
            )

    def test_bbb_left_checks_access(self):
        """bbb_left applies the checks of the room page before it answers,
        with or without frame=1: the redirect to the room page tells an
        outsider nothing more than the page."""
        for suffix in ("/bbb_left", "/bbb_left?frame=1"):
            with self.subTest(suffix=suffix):
                self.authenticate(None, None)
                response = self._get(self._room_url(self.room_api, suffix))
                self.assertIn(response.status_code, (302, 303))
                self.assertEqual(
                    urlsplit(response.headers["Location"]).path, "/web/login"
                )

                self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
                response = self._get(self._room_url(self.room_later, suffix))
                self.assertEqual(response.status_code, 200)
                self.assertIn("not open yet", response.text)
                # The texts of the page script (data-ewp-messages) hold the
                # phrase on every page: the heading tells which page this
                # is.
                heading = lxml_html.fromstring(response.text).xpath("//h1")[0]
                self.assertNotIn(
                    "You left the conference.", heading.text_content()
                )
                # A room through another day, or a room that does not
                # exist.
                for url in (
                    "/webapp_event/%s/room/%s%s"
                    % (self.day.id, self.room_later.id, suffix),
                    "/webapp_event/%s/room/0%s" % (self.day.id, suffix),
                ):
                    with self.subTest(url=url):
                        self.assertEqual(self._get(url).status_code, 404)

        self.authenticate("ewp_bbb_moderator", "ewp_bbb_moderator")
        response = self._get(
            self._room_url(self.room_later, "/bbb_left?frame=1")
        )
        self.assertEqual(response.status_code, 200)
        heading = lxml_html.fromstring(response.text).xpath("//h1")[0]
        self.assertIn("You left the conference.", heading.text_content())
        response = self._get(self._room_url(self.room_later, "/bbb_left"))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            urlsplit(response.headers["Location"]).path,
            self._room_url(self.room_later),
        )

    def test_tab_that_leaves_an_embedded_meeting_does_not_join_again(self):
        """A join opened by "Open in a new tab" next to the frame leaves to
        bbb_left, which redirects to the room page with left=1. That page
        embeds the meeting: it renders the frame hidden and without src,
        the notice "You left the conference." shown with "Join again", and
        the state "left", so the tab does not join the meeting again. The
        marker changes nothing behind the new tab button, nor on a meeting
        that does not run, and the status route keeps its answer."""
        self.authenticate("ewp_bbb_portal", "ewp_bbb_portal")
        left_url = self._room_url(self.room_api, "/bbb_left?reason=left")
        with fake_network(FakeNetwork(running=True)):
            redirect = self._get(left_url)
            self.assertEqual(redirect.status_code, 303)
            location = urlsplit(redirect.headers["Location"])
            response = self._get(location.path + "?" + location.query)
            self.assertEqual(response.status_code, 200)
            page = lxml_html.fromstring(response.text)
            section = page.xpath("//section[contains(@class, 'o_ewp_bbb')]")[0]
            self.assertEqual(section.get("data-ewp-bbb-state"), "left")
            self.assertEqual(section.get("data-ewp-bbb-live"), "1")
            frame = section.xpath(".//iframe[contains(@class, 'o_ewp_bbb')]")[
                0
            ]
            self.assertIsNone(frame.get("src"))
            self.assertIsNotNone(frame.get("hidden"))
            self.assertEqual(
                frame.get("data-ewp-src"),
                self._room_url(self.room_api, "/bbb_join?frame=1"),
            )
            video = section.xpath(".//div[@id='o_ewp_video']")[0]
            self.assertIsNone(video.get("hidden"))
            notice = video.xpath("./div[contains(@class, 'o_ewp_bbb_left')]")[
                0
            ]
            self.assertIsNone(notice.get("hidden"))
            self.assertEqual(
                notice.xpath(".//button")[0].text_content().strip(),
                "Join again",
            )
            self.assertTrue(page.xpath("//iframe[@class='o_ewp_chat']"))
            self.assertEqual(
                self._get(self._room_url(self.room_api, "/bbb_status")).json(),
                {"running": True, "error": False, "state": "running"},
            )

            # Text-only mode: the notice too, not the on-demand button.
            self.portal_user.ewp_text_only = True
            response = self._get(self._room_url(self.room_api, "?left=1"))
            page = lxml_html.fromstring(response.text)
            self.assertEqual(
                page.xpath("//section/@data-ewp-bbb-state"), ["left"]
            )
            self.assertFalse(
                page.xpath("//*[contains(@class, 'o_ewp_bbb_ondemand')]")
            )
            frame = page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")[0]
            self.assertIsNone(frame.get("src"))
            notice = page.xpath("//div[contains(@class, 'o_ewp_bbb_left')]")[0]
            self.assertIsNone(notice.get("hidden"))
            self.portal_user.ewp_text_only = False

            # Without the marker, the frame joins at once.
            response, page = self._page(self.room_api)
            self.assertEqual(
                page.xpath("//section/@data-ewp-bbb-state"), ["running"]
            )
            notice = page.xpath("//div[contains(@class, 'o_ewp_bbb_left')]")[0]
            self.assertIsNotNone(notice.get("hidden"))

            # Behind the new tab button the page joins no one: the marker
            # changes nothing.
            self.env["ir.config_parameter"].sudo().set_param(
                PARAM_BBB_DISPLAY, "tab"
            )
            response = self._get(self._room_url(self.room_api, "?left=1"))
            page = lxml_html.fromstring(response.text)
            self.assertEqual(
                page.xpath("//section/@data-ewp-bbb-state"), ["button"]
            )
            self.assertTrue(
                page.xpath("//*[contains(@class, 'o_ewp_bbb_tab_live')]")
            )

        # A meeting that does not run: the waiting notice, as without it.
        self.env["ir.config_parameter"].sudo().set_param(
            PARAM_BBB_DISPLAY, "frame"
        )
        with fake_network(FakeNetwork(running=False)):
            response = self._get(self._room_url(self.room_api, "?left=1"))
        page = lxml_html.fromstring(response.text)
        self.assertEqual(
            page.xpath("//section/@data-ewp-bbb-state"), ["waiting"]
        )
        self.assertFalse(page.xpath("//*[contains(@class, 'o_ewp_bbb_left')]"))
        # A framed conference URL has no notice of a leave: it keeps its
        # frame with its src.
        with fake_network(FakeNetwork(running=True)):
            response = self._get(self._room_url(self.room_framed, "?left=1"))
        page = lxml_html.fromstring(response.text)
        frame = page.xpath("//iframe[contains(@class, 'o_ewp_bbb')]")[0]
        self.assertTrue(frame.get("src"))
        self.assertEqual(
            page.xpath("//section/@data-ewp-bbb-state"), ["frame"]
        )

    def test_secret_never_reaches_the_browser(self):
        rooms = (
            self.room_api,
            self.room_fallback,
            self.room_framed,
            self.room_refused,
            self.room_plain,
        )
        for login in ("ewp_bbb_portal", "ewp_bbb_moderator"):
            self.authenticate(login, login)
            for running in (True, False):
                with fake_network(FakeNetwork(running=running)):
                    urls = ["/webapp_event", "/webapp_event/%s" % self.day.id]
                    for room in rooms:
                        urls += [
                            self._room_url(room),
                            self._room_url(room, "/bbb_status"),
                            self._room_url(room, "/bbb_join"),
                            self._room_url(room, "/bbb_left"),
                        ]
                    for url in urls:
                        with self.subTest(login=login, url=url):
                            response = self._get(url)
                            self.assertNotIn(SECRET, response.text)
                            for value in response.headers.values():
                                self.assertNotIn(SECRET, value)
                            # Only the redirect of bbb_join names the
                            # server: no page nor JSON carries its address.
                            if not url.endswith("/bbb_join"):
                                self.assertNotIn(
                                    "bbb.example.org", response.text
                                )
