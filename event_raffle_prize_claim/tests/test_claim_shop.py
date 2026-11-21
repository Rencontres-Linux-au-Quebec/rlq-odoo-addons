# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import json
import os
import re
import secrets
import unittest
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import odoo
from odoo import fields
from odoo.exceptions import UserError
from odoo.service import security
from odoo.tests import new_test_user, tagged
from odoo.tests.common import (
    TEST_CURSOR_COOKIE_NAME,
    HttpCase,
    JsonRpcException,
    Opener,
    get_db_name,
)

from .axe import AXE_ENV, AxeMixin
from .common import ClaimDataMixin


@tagged("post_install", "-at_install")
class TestClaimShop(AxeMixin, ClaimDataMixin, HttpCase):
    """The prize link and the filtered shop, through the website routes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._claim_setup()
        cls.mug = cls._prize("Claim Mug", price=20.0, qty=2)
        cls.pen = cls._prize("Claim Pen", price=5.0, qty=2)
        cls.bike = cls._prize("Claim Bike", price=200.0, qty=1)
        cls.cap = cls._prize(
            "Claim Cap", price=10.0, raffle_attendance="virtual"
        )
        cls.trophy = cls._prize(
            "Claim Trophy", price=30.0, raffle_closing_prize=True
        )
        cls.empty = cls._prize("Claim Empty", price=15.0, qty=0)
        cls.sold = cls._prize(
            "Claim Sold", price=25.0, qty=3, raffle_member_sale_ok=True
        )
        cls.book = (
            cls.env["product.template"]
            .create(
                {
                    "name": "Ordinary Book",
                    "list_price": 12.0,
                    "is_published": True,
                    "sale_ok": True,
                }
            )
            .product_variant_id
        )
        cls.winner = cls._participant("Wendy Winner")
        cls.draw = cls._draw(cls.winner, band_id=cls.band_a.id)
        cls.token = cls.draw._claim_link_issue()

    def setUp(self):
        super().setUp()
        self._use_session()

    # Helpers

    def _use_session(self, sid=None):
        """Browse as a public visitor with the session `sid`, a new one
        when omitted. Unlike authenticate(), the previous session is kept,
        so that a test can switch between two visitors."""
        store = odoo.http.root.session_store
        if sid is None:
            session = store.new()
            session.update(
                odoo.http.get_default_session(),
                db=get_db_name(),
                _trace_disable=True,
            )
            session.context["lang"] = odoo.http.DEFAULT_LANG
            store.save(session)
            sid = session.sid
        self.opener = Opener(self.cr)
        self.opener.cookies["session_id"] = sid
        self.opener.cookies[TEST_CURSOR_COOKIE_NAME] = self.http_request_key
        self.sid = sid
        return sid

    def _winner_user(self, draw):
        """The user of the winner's contact of `draw`: a portal user whose
        password is its login, created when the contact has none."""
        partner = draw._prize_winner_partner()
        user = partner.user_ids[:1]
        if not user:
            user = new_test_user(
                self.env,
                login=f"winner{partner.id}@example.com",
                groups="base.group_portal",
                name=partner.name,
                email=partner.email,
                partner_id=partner.id,
            )
        return user

    def _sign_in(self, user):
        """Sign `user` in, in the current session, which keeps its other
        keys, as the sign-in page does."""
        self.cr.flush()
        session = self._session()
        env = self.env(user=user)
        session.uid = user.id
        session.login = user.login
        session.session_token = security.compute_session_token(session, env)
        session.context = dict(env["res.users"].context_get())
        odoo.http.root.session_store.save(session)

    def _follow_new_session(self):
        """Browse on with the session id the last response set, as a
        browser does: signing in and out move the session to a new id."""
        sids = {
            cookie.value
            for cookie in self.opener.cookies
            if cookie.name == "session_id"
        } - {self.sid}
        self.assertEqual(len(sids), 1, "no new session id was set")
        self._use_session(sids.pop())

    def _open(self, token=None, sign_in=True):
        """Open the link of `token`, `self.token` when omitted. With
        `sign_in`, the session first signs in as the winner of the draw
        the token opens, when the token opens one."""
        token = token or self.token
        if sign_in:
            draw = self.env["event.raffle.draw"]._claim_link_find(token)
            if draw:
                user = self._winner_user(draw)
                if self._session().uid != user.id:
                    self._sign_in(user)
        return self.url_open(f"/raffle/prize/{token}", allow_redirects=False)

    def _session(self):
        return odoo.http.root.session_store.get(self.sid)

    def _csrf(self, url):
        html = self.url_open(url).text
        match = re.search(r'csrf_token: "([^"]+)"', html)
        self.assertTrue(match, f"no CSRF token on {url}")
        return match.group(1)

    def _add(self, product, **params):
        return self.make_jsonrpc_request(
            "/shop/cart/update_json",
            dict({"product_id": product.id, "add_qty": 1}, **params),
        )

    def _jsonrpc_error(self, route, params):
        """The message of the error that the JSON route `route` answers to
        `params`; fails when it answers a result."""
        response = self.url_open(
            route,
            json.dumps(
                {"id": 0, "jsonrpc": "2.0", "method": "call", "params": params}
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        body = response.json()
        self.assertIn("error", body, f"{route} answered {body}")
        return body["error"]["data"]["message"]

    def _snippet_cards(self, xmlid, **params):
        """The cards of the product snippet filter `xmlid`, rendered for
        the current visitor, by product name: the HTML of each card."""
        cards = self.make_jsonrpc_request(
            "/website/snippet/filters",
            dict(
                {
                    "filter_id": self.env.ref(xmlid).id,
                    "template_key": "website_sale."
                    "dynamic_filter_template_product_product_add_to_cart",
                    "limit": 16,
                    "search_domain": [["name", "ilike", "Claim"]],
                },
                **params,
            ),
        )
        found = {}
        for html in cards:
            names = re.findall(r'alt="([^"]+)"', html)
            if names:
                found[names[0]] = html
        return found

    def _cart(self):
        order_id = self._session().get("sale_order_id")
        return self.env["sale.order"].browse(order_id)

    def _checkout(self):
        self.url_open("/shop/checkout?try_skip_step=true")
        self.url_open("/shop/confirm_order")
        csrf = self._csrf("/shop/payment")
        return self.url_open(
            "/shop/payment/validate",
            data={"csrf_token": csrf},
            allow_redirects=False,
        )

    def _path(self, response):
        return urlsplit(response.headers.get("Location", "")).path

    def _submit_address(self, **values):
        csrf = self._csrf("/shop/cart")
        return self.url_open(
            "/shop/address/submit",
            data=dict(
                {"csrf_token": csrf, "address_type": "billing"}, **values
            ),
        )

    # Link

    def test_link_opens_a_claim_in_the_session(self):
        response = self._open()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self._path(response), "/shop")
        claim = self._session().get("raffle_prize_claim")
        self.assertEqual(claim, {"draw_id": self.draw.id, "token": self.token})
        shop = self.url_open("/shop").text
        self.assertIn("o_raffle_claim_banner", shop)
        self.assertIn("Wendy", shop)
        self.assertIn('aria-live="polite"', shop)
        self.assertIn("<time datetime=", shop)

    def test_invalid_links_read_the_same(self):
        expired = self._draw(self._participant("Exp Ired"))
        expired_token = expired._claim_link_issue()
        self._expire(expired)
        used = self._draw(self._participant("Use Ed"))
        used_token = used._claim_link_issue()
        used._prize_claim(self.pen)
        forged = self.token[:-2] + ("AA" if self.token[-2:] != "AA" else "BB")
        pages = []
        for token in (
            secrets.token_urlsafe(32),
            forged,
            expired_token,
            used_token,
            "x",
        ):
            response = self._open(token)
            self.assertEqual(response.status_code, 404, token)
            self.assertIn("This prize link does not work", response.text)
            self.assertFalse(self._session().get("raffle_prize_claim"))
            title = re.search(r"<h1[^>]*>(.*?)</h1>", response.text, re.DOTALL)
            pages.append(title.group(1).strip())
        self.assertEqual(len(set(pages)), 1)

    def test_visitor_signs_in_before_the_link_opens(self):
        response = self._open(sign_in=False)
        self.assertEqual(response.status_code, 303)
        location = urlsplit(response.headers["Location"])
        self.assertEqual(location.path, "/web/login")
        self.assertEqual(
            parse_qs(location.query)["redirect"],
            [f"/raffle/prize/{self.token}"],
        )
        self.assertFalse(self._session().get("raffle_prize_claim"))
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        login = self.url_open(response.headers["Location"])
        self.assertEqual(login.status_code, 200)
        self.assertIn('name="redirect"', login.text)
        # Signed in, the same link opens the claim.
        self.assertEqual(self._path(self._open()), "/shop")
        self.assertIn("o_raffle_claim_banner", self.url_open("/shop").text)

    def test_other_account_is_refused_without_a_claim(self):
        other = new_test_user(
            self.env,
            login="claim_other_member",
            groups="base.group_portal",
            name="Oscar Other",
            email="oscar.other@example.com",
        )
        self._sign_in(other)
        response = self._open(sign_in=False)
        self.assertEqual(response.status_code, 403)
        self.assertIn("This prize link is for another account", response.text)
        self.assertIn("/web/session/logout?redirect=", response.text)
        for text in ("Wendy", "wendy", "Group A", "Claim Mug"):
            self.assertNotIn(text, response.text)
        self.assertFalse(self._session().get("raffle_prize_claim"))
        shop = self.url_open("/shop").text
        self.assertNotIn("o_raffle_claim_banner", shop)
        self.assertIn(
            "Prize only: Group A", self.url_open("/shop?search=Claim").text
        )
        with self.assertRaises(JsonRpcException):
            self._add(self.mug)
        self.assertEqual(
            self.url_open("/raffle/prize/decline").status_code, 404
        )
        self.assertEqual(self.draw.claim_state, "none")

    def test_signed_in_winner_finds_the_claim_without_the_link(self):
        self._sign_in(self._winner_user(self.draw))
        shop = self.url_open("/shop").text
        self.assertIn("o_raffle_claim_banner", shop)
        self.assertIn("Wendy", shop)
        self.assertIn("Your token: Group A, valid 45 minutes.", shop)
        self.assertIn("o_raffle_token_cost", shop)
        self.assertNotIn("Prize only", shop)
        self._add(self.mug)
        cart = self._cart()
        self.assertEqual(cart.raffle_draw_id, self.draw)
        self.assertEqual(cart.partner_id, self.winner.partner_id)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertEqual(self.draw.claim_state, "reserved")
        self.assertEqual(self.draw.prize_order_id, cart)
        self.assertIn("Claim Mug", self.url_open("/raffle/prize/done").text)
        self.assertFalse(self._session().get("raffle_prize_claim"))

    def test_signed_in_winner_gets_the_most_recent_open_claim(self):
        older = self._draw(
            self._participant("Rita Recent"), band_id=self.band_a.id
        )
        older_token = older._claim_link_issue()
        newer = self._draw(
            older.winner_participant_id,
            band_id=self.band_b.id,
            date=fields.Datetime.now() + timedelta(minutes=1),
        )
        newer._claim_link_issue()
        self._sign_in(self._winner_user(older))
        shop = self.url_open("/shop").text
        self.assertIn("Your token: Group B", shop)
        self.assertIn("Claim Bike", shop)
        self.assertNotIn("Claim Mug", shop)
        # The link the session opened comes first.
        self._open(older_token)
        shop = self.url_open("/shop").text
        self.assertIn("Your token: Group A", shop)
        self.assertIn("Claim Mug", shop)

    def test_claim_answers_on_the_website_of_the_raffle_company(self):
        """A draw of a raffle of another company than the website's runs
        no claim there: its link reads as an unknown one, its signed-in
        winner finds no claim, and the confirmation page shows nothing."""
        company_b = self.env["res.company"].create({"name": "Claim Company B"})
        raffle_b = self.env["event.raffle"].create(
            {
                "name": "Company B raffle",
                "event_id": self.event.id,
                "company_id": company_b.id,
                "claim_auto_send": False,
            }
        )
        partner_b = self.env["res.partner"].create(
            {"name": "Bianca Branch", "email": "bianca.branch@example.com"}
        )
        participant_b = self.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle_b.id,
                "name": partner_b.name,
                "email": partner_b.email,
                "partner_id": partner_b.id,
            }
        )
        token_b = self._draw(participant_b)._claim_link_issue()
        response = self._open(token_b)
        self.assertEqual(response.status_code, 404)
        self.assertIn("This prize link does not work", response.text)
        self.assertFalse(self._session().get("raffle_prize_claim"))
        # Signed in as that winner, the shop opens no claim.
        self.assertEqual(self._session().uid, partner_b.user_ids.id)
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        # The confirmation page of a claim made on the website: it shows
        # nothing once the raffle belongs to another company.
        self._use_session()
        self._open()
        self._add(self.mug)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertIn("Claim Mug", self.url_open("/raffle/prize/done").text)
        self.raffle.sudo().company_id = company_b
        response = self.url_open("/raffle/prize/done", allow_redirects=False)
        self.assertEqual(self._path(response), "/shop")

    def test_closed_claims_are_not_picked_up(self):
        user = self._winner_user(self.draw)
        self._sign_in(user)
        self._expire(self.draw)
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        declined = self._draw(self.winner)
        declined._claim_link_issue()
        self.assertIn("o_raffle_claim_banner", self.url_open("/shop").text)
        declined._claim_link_decline("Not for me")
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        reserved = self._draw(self.winner)
        reserved._claim_link_issue()
        reserved._prize_claim(self.pen)
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        with self.assertRaises(JsonRpcException):
            self._add(self.mug)

    def test_session_claim_ends_with_its_user(self):
        other = new_test_user(
            self.env,
            login="claim_next_member",
            groups="base.group_portal",
            name="Nora Next",
            email="nora.next@example.com",
        )
        # Signing out ends the claim.
        self._open()
        self._add(self.mug)
        self.assertIn("o_raffle_claim_banner", self.url_open("/shop").text)
        self.url_open("/web/session/logout", allow_redirects=False)
        self._follow_new_session()
        self.assertFalse(self._session().get("raffle_prize_claim"))
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        self.assertEqual(
            self.url_open("/raffle/prize/decline").status_code, 404
        )
        # Another user signed in on the same browser gets nothing of it,
        # though the session still names the claim.
        self._open()
        self._sign_in(other)
        self.assertTrue(self._session().get("raffle_prize_claim"))
        shop = self.url_open("/shop").text
        self.assertNotIn("o_raffle_claim_banner", shop)
        self.assertNotIn("Wendy", shop)
        self.assertNotIn("Claim Mug", self.url_open("/shop/cart").text)
        with self.assertRaises(JsonRpcException):
            self._add(self.mug)
        self.assertEqual(
            self.url_open("/raffle/prize/decline").status_code, 404
        )
        self.assertEqual(self.draw.claim_state, "none")
        # Nor the confirmation page of a claim the winner confirmed.
        self._open()
        self._add(self.mug)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self._sign_in(other)
        done = self.url_open("/raffle/prize/done", allow_redirects=False)
        self.assertEqual(self._path(done), "/shop")

    def test_winner_without_account_creates_it_from_the_email(self):
        participant = self._participant("Nina Newcomer")
        draw = self._draw(participant, band_id=self.band_a.id)
        partner = participant.partner_id
        self.assertFalse(partner.user_ids)
        draw._claim_link_send()
        token = draw.sudo().claim_token
        notification = draw.notification_ids
        self.assertEqual(notification.channel, "email")
        body = str(notification.mail_id.body_html)
        self.assertIn("creates your account", body)
        href = re.search(r'href="([^"]*/web/signup\?[^"]+)"', body).group(1)
        url = urlsplit(href.replace("&amp;", "&"))
        query = parse_qs(url.query)
        self.assertEqual(query["redirect"], [f"/raffle/prize/{token}"])
        # The log of the draw shows the bare link, masked.
        self.assertIn("/raffle/prize/********", notification.body)
        self.assertNotIn("/web/signup", notification.body)
        self.assertNotIn(query["token"][0], notification.body)
        self.assertNotIn(token, notification.body)
        # The signup page knows the contact, then signs the new user in
        # and opens the link.
        page = self.url_open(f"{url.path}?{url.query}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(partner.email, page.text)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page.text)
        response = self.url_open(
            "/web/signup",
            data={
                "csrf_token": csrf.group(1),
                "token": query["token"][0],
                "redirect": query["redirect"][0],
                "login": partner.email,
                "name": partner.name,
                "password": "nina-newcomer-pass-2026",
                "confirm_password": "nina-newcomer-pass-2026",
            },
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self._path(response), f"/raffle/prize/{token}")
        self._follow_new_session()
        user = partner.user_ids
        self.assertEqual(len(user), 1)
        self.assertTrue(user.share)
        self.assertTrue(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_user"))
        self.assertEqual(self._session().uid, user.id)
        self.assertEqual(self._path(self._open(token, sign_in=False)), "/shop")
        self.assertIn("Nina", self.url_open("/shop").text)
        # The invitation works once: the contact has its user now.
        self._use_session()
        page = self.url_open(f"{url.path}?{url.query}")
        self.assertIn("Invalid signup token", page.text)
        # The next link goes to the account, without an invitation.
        draw._claim_link_send()
        mail = draw.notification_ids.sorted("id")[-1].mail_id
        self.assertNotIn("/web/signup", str(mail.body_html))
        self.assertIn(
            f"/raffle/prize/{draw.sudo().claim_token}", str(mail.body_html)
        )

    # Shop

    def test_closed_shop_hides_the_prizes_from_visitors(self):
        past = fields.Datetime.now() - timedelta(minutes=1)
        for is_open, close_date in ((False, False), (True, past)):
            self._set_shop_window(is_open=is_open, close_date=close_date)
            for url in ("/shop", "/shop?search=Claim"):
                html = self.url_open(url).text
                self.assertNotIn("o_raffle_claim_banner", html)
                for name in ("Claim Mug", "Claim Pen", "Claim Bike"):
                    self.assertNotIn(name, html, url)
            self.assertIn(
                "Ordinary Book", self.url_open("/shop?search=Ordinary").text
            )
            for product in (self.mug, self.bike, self.sold):
                url = product.product_tmpl_id.website_url
                self.assertEqual(self.url_open(url).status_code, 404, url)
            with self.assertRaises(JsonRpcException):
                self._add(self.sold)
        # An open prize link still shows the winner's prizes.
        self._open()
        html = self.url_open("/shop").text
        self.assertIn("Claim Mug", html)
        self._add(self.mug)
        self.assertEqual(self._cart().order_line.product_id, self.mug)

    def test_open_shop_sells_to_members_and_shows_the_other_prizes(self):
        html = self.url_open("/shop?search=Claim").text
        self.assertNotIn("o_raffle_claim_banner", html)
        for name in ("Claim Mug", "Claim Sold"):
            self.assertIn(name, html)
        self.assertIn("Prize only: Group A", html)
        self.assertIn("Prize only: Group B", html)
        # The prize sold to members shows its price and adds to the cart.
        page = self.url_open(self.sold.product_tmpl_id.website_url).text
        self.assertIn('id="add_to_cart"', page)
        self.assertIn("25.00", page)
        self.assertNotIn("Prize only", page)
        # A prize for tokens only shows no price and no add to cart.
        page = self.url_open(self.mug.product_tmpl_id.website_url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Prize only: Group A", page.text)
        self.assertNotIn('id="add_to_cart"', page.text)
        self.assertNotIn("20.00", page.text)
        self.assertIn('href="https://sponsor.example.org"', page.text)
        notified = self._add(self.sold)["notification_info"]["lines"]
        self.assertNotIn("raffle_token_label", notified[0])
        cart = self._cart()
        self.assertFalse(cart.raffle_draw_id)
        line = cart.order_line
        self.assertEqual(line.product_id, self.sold)
        self.assertEqual(line.price_unit, 25.0)
        self.assertEqual(line.discount, 0.0)
        self.assertEqual(line.raffle_prize_sale_type, "purchase")
        for params in ({}, {"add_qty": 0, "set_qty": 1}):
            with self.assertRaises(JsonRpcException):
                self._add(self.mug, **params)
        self.assertEqual(cart.order_line.product_id, self.sold)
        # The cart page shows the member's price, as any cart does.
        self.assertIn("25.00", self.url_open("/shop/cart").text)

    def test_winner_reads_token_costs_instead_of_prices(self):
        self._open()
        shop = self.url_open("/shop").text
        self.assertIn("o_raffle_token_cost", shop)
        self.assertNotIn("Prize only", shop)
        self.assertNotIn("20.00", shop)
        page = self.url_open(self.mug.product_tmpl_id.website_url).text
        self.assertIn('id="add_to_cart"', page)
        self.assertIn("o_raffle_token_cost", page)
        self.assertNotIn("20.00", page)
        self._add(self.mug)
        for url in ("/shop/cart", "/shop/checkout?try_skip_step=true"):
            html = self.url_open(url).text
            self.assertIn("o_raffle_token_total", html, url)
            self.assertIn(">Group A<", html, url)
            self.assertNotIn("20.00", html, url)
            self.assertNotIn('name="website_sale_cart_line_price"', html, url)
            self.assertNotIn('id="amount_total_summary"', html, url)
            # The amounts website_sale's scripts update stay, hidden.
            self.assertIn('class="table mb-0 d-none"', html, url)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        response = self.url_open("/shop/confirmation", allow_redirects=False)
        self.assertEqual(self._path(response), "/raffle/prize/done")
        done = self.url_open("/raffle/prize/done").text
        self.assertNotIn("20.00", done)
        order = self.draw.prize_order_id
        self.assertEqual(order._prize_lines().raffle_prize_sale_type, "claim")
        subjects = order.message_ids.mapped("subject")
        self.assertIn("Your prize: Claim Mug", subjects)
        self.assertFalse([s for s in subjects if s and order.name in s])

    def test_banner_gives_the_token_and_its_validity(self):
        self.band_a.claim_delay_minutes = 15
        draw = self._draw(
            self._participant("Tia Token"), band_id=self.band_a.id
        )
        self._open(draw._claim_link_issue())
        html = self.url_open("/shop").text
        self.assertIn("Your token: Group A, valid 15 minutes.", html)

    def test_winner_sees_only_the_prizes_allowed(self):
        self._open()
        html = self.url_open("/shop").text
        self.assertIn("Claim Mug", html)
        self.assertIn("Claim Pen", html)
        # Band B, virtual winners only, closing draws only, out of stock,
        # and an ordinary product.
        for name in (
            "Claim Bike",
            "Claim Cap",
            "Claim Trophy",
            "Claim Empty",
            "Ordinary Book",
        ):
            self.assertNotIn(name, html)
        self.assertIn('href="https://sponsor.example.org"', html)

    def test_product_page_refuses_a_prize_the_claim_does_not_allow(self):
        self._open()
        for product in (self.bike, self.trophy, self.cap):
            url = product.product_tmpl_id.website_url
            self.assertEqual(self.url_open(url).status_code, 404, url)
        page = self.url_open(self.mug.product_tmpl_id.website_url)
        self.assertEqual(page.status_code, 200)
        self.assertIn("o_raffle_claim_banner", page.text)
        self.assertIn('href="https://sponsor.example.org"', page.text)
        self.assertIn("Sponsor Example", page.text)

    def _combination_info(self, product):
        return self.make_jsonrpc_request(
            "/website_sale/get_combination_info",
            {
                "product_template_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "combination": [],
                "add_qty": 1,
            },
        )

    def test_combination_info_follows_the_shop_display(self):
        """The variant data of a product page gives no price that the page
        hides, and nothing of a prize the visitor may not see."""
        for product in (self.mug, self.sold):
            info = self._combination_info(product)
            self.assertEqual(info["product_id"], product.id)
        info = self._combination_info(self.mug)
        self.assertEqual((info["price"], info["list_price"]), (0.0, 0.0))
        self.assertGreater(self._combination_info(self.sold)["price"], 0.0)
        self.assertGreater(self._combination_info(self.book)["price"], 0.0)
        # The winner reads token costs, never prices.
        self._open()
        info = self._combination_info(self.mug)
        self.assertEqual((info["price"], info["list_price"]), (0.0, 0.0))
        with self.assertRaises(JsonRpcException):
            self._combination_info(self.bike)
        # Once the shop is closed, a prize answers nothing to a visitor.
        self._use_session()
        self._set_shop_window(is_open=False)
        for product in (self.sold, self.mug):
            with self.assertRaises(JsonRpcException):
                self._combination_info(product)
        self.assertGreater(self._combination_info(self.book)["price"], 0.0)

    def test_combination_info_answers_for_the_variant_it_prices(self):
        """The variant data route prices the variant it is given, whatever
        the template sent beside it: a prize variant sent with the
        template of an ordinary product follows the prize's rules."""

        def mixed(product):
            return self.make_jsonrpc_request(
                "/website_sale/get_combination_info",
                {
                    "product_template_id": self.book.product_tmpl_id.id,
                    "product_id": product.id,
                    "combination": [],
                    "add_qty": 1,
                },
            )

        info = mixed(self.mug)
        self.assertEqual(info["product_id"], self.mug.id)
        self.assertEqual((info["price"], info["list_price"]), (0.0, 0.0))
        self.assertGreater(mixed(self.sold)["price"], 0.0)
        self._set_shop_window(is_open=False)
        for product in (self.sold, self.mug):
            with self.assertRaises(JsonRpcException):
                mixed(product)

    def _configurator(self, template, route="get_values"):
        """The product configurator data of `template`, through the
        website route `route`."""
        params = {
            "product_template_id": template.id,
            "quantity": 1,
            "so_date": "2026-01-01 00:00:00",
            "ptav_ids": [],
        }
        return self.make_jsonrpc_request(
            f"/website_sale/product_configurator/{route}", params
        )

    def _configurator_price(self, product, route):
        values = self._configurator(product.product_tmpl_id, route)
        if route == "get_values":
            values = values["products"][0]
        return values["price"]

    def test_configurator_follows_the_shop_display(self):
        """The product configurator routes give no price that the shop
        hides, and nothing of a prize the visitor may not see, whether it
        is the product configured or one of its optional products."""
        book = self.book.product_tmpl_id
        book.optional_product_ids = (self.mug | self.sold).product_tmpl_id
        for route in ("get_values", "update_combination"):
            self.assertEqual(self._configurator_price(self.mug, route), 0.0)
            self.assertGreater(self._configurator_price(self.sold, route), 0)
            self.assertGreater(self._configurator_price(self.book, route), 0)
        options = {
            o["product_tmpl_id"]: o["price"]
            for o in self._configurator(book)["optional_products"]
        }
        self.assertEqual(options[self.mug.product_tmpl_id.id], 0.0)
        self.assertGreater(options[self.sold.product_tmpl_id.id], 0.0)
        # The winner reads token costs, never prices.
        self._open()
        for route in ("get_values", "update_combination"):
            self.assertEqual(self._configurator_price(self.mug, route), 0.0)
            with self.assertRaises(JsonRpcException):
                self._configurator(self.bike.product_tmpl_id, route)
        # Once the shop is closed, a prize answers nothing to a visitor.
        self._use_session()
        self._set_shop_window(is_open=False)
        for route in ("get_values", "update_combination"):
            for product in (self.sold, self.mug):
                with self.assertRaises(JsonRpcException):
                    self._configurator(product.product_tmpl_id, route)
            self.assertGreater(self._configurator_price(self.book, route), 0)
        self.assertEqual(self._configurator(book)["optional_products"], [])

    # Cart

    def test_claim_cart_holds_one_prize_at_no_charge(self):
        self._open()
        self._add(self.mug)
        cart = self._cart()
        self.assertEqual(cart.raffle_draw_id, self.draw)
        self.assertEqual(cart.partner_id, self.winner.partner_id)
        line = cart.order_line
        self.assertEqual(line.product_id, self.mug)
        self.assertEqual(line.product_uom_qty, 1.0)
        self.assertEqual(line.price_unit, 20.0)
        self.assertEqual(line.discount, 100.0)
        self.assertEqual(cart.amount_total, 0.0)
        # The add-to-cart notification gives the token cost of the line,
        # which it shows instead of the line's amount.
        notified = self._add(self.mug)["notification_info"]["lines"]
        self.assertEqual(
            [n.get("raffle_token_label") for n in notified], ["Group A"]
        )
        self._add(self.mug, set_qty=3, line_id=line.id)
        self.assertEqual(cart.order_line.product_uom_qty, 1.0)
        # A second prize replaces the first.
        self._add(self.pen)
        self.assertEqual(cart.order_line.product_id, self.pen)
        self.assertEqual(cart.order_line.product_uom_qty, 1.0)
        for product in (self.book, self.bike):
            with self.assertRaises(JsonRpcException):
                self._add(product)
        self.assertEqual(cart.order_line.product_id, self.pen)

    def test_ordinary_cart_refuses_a_prize(self):
        self._add(self.book)
        cart = self._cart()
        for params in ({}, {"add_qty": 0, "set_qty": 1}):
            with self.assertRaises(JsonRpcException):
                self._add(self.mug, **params)
        self.assertEqual(cart.order_line.product_id, self.book)

    def test_winner_adds_published_and_sellable_prizes_only(self):
        """A prize the claim allows but the website does not sell, being
        unpublished or not sellable, stays out of the claim cart, whether
        the update adds it or sets its quantity."""
        hidden = self._prize("Claim Hidden", price=20.0, is_published=False)
        unsold = self._prize("Claim Unsold", price=20.0, sale_ok=False)
        allowed = self.draw._prize_allowed_products()
        self.assertIn(hidden, allowed)
        self.assertIn(unsold, allowed)
        self._open()
        self._add(self.mug)
        cart = self._cart()
        for product in (hidden, unsold):
            for params in ({}, {"add_qty": 0, "set_qty": 1}):
                with self.assertRaises(JsonRpcException):
                    self._add(product, **params)
        self.assertEqual(cart.order_line.product_id, self.mug)

    def test_prize_no_longer_for_sale_leaves_the_cart(self):
        """The cart page sends `set_qty` only, without `add_qty`: removing
        or lowering a line of a prize no longer for sale goes through."""
        for close in (
            lambda: self._set_shop_window(is_open=False),
            lambda: self.sold.write({"raffle_member_sale_ok": False}),
        ):
            self._use_session()
            self._add(self.sold, add_qty=3)
            line = self._cart().order_line
            self.assertEqual(line.product_uom_qty, 3.0)
            close()
            params = {"product_id": self.sold.id, "line_id": line.id}
            with self.assertRaises(JsonRpcException):
                self.make_jsonrpc_request(
                    "/shop/cart/update_json", dict(params, set_qty=4)
                )
            self.make_jsonrpc_request(
                "/shop/cart/update_json", dict(params, set_qty=2)
            )
            self.assertEqual(line.product_uom_qty, 2.0)
            self.make_jsonrpc_request(
                "/shop/cart/update_json", dict(params, add_qty=-1)
            )
            self.assertEqual(line.product_uom_qty, 1.0)
            self.make_jsonrpc_request(
                "/shop/cart/update_json", dict(params, set_qty=0)
            )
            self.assertFalse(line.exists())
            self._set_shop_window(is_open=True)
            self.sold.raffle_member_sale_ok = True

    def test_winner_removes_the_prize_from_the_claim_cart(self):
        self._open()
        self._add(self.mug)
        cart = self._cart()
        line = cart._prize_lines()
        self.make_jsonrpc_request(
            "/shop/cart/update_json",
            {"product_id": self.mug.id, "line_id": line.id, "set_qty": 0},
        )
        self.assertFalse(cart._prize_lines())
        # website_sale lets go of the emptied cart: the next prize goes to
        # a new claim cart of the same draw.
        self._add(self.pen)
        self.assertEqual(self._cart().raffle_draw_id, self.draw)
        self.assertEqual(self._cart()._prize_lines().product_id, self.pen)

    def test_product_snippets_follow_the_shop(self):
        newest = "website_sale.dynamic_filter_newest_products"
        alternative = (
            "website_sale.dynamic_filter_cross_selling_alternative_products"
        )
        self.book.product_tmpl_id.alternative_product_ids = (
            self.mug.product_tmpl_id | self.sold.product_tmpl_id
        )
        book_page = {"productTemplateId": self.book.product_tmpl_id.id}
        # An ordinary visitor of the open shop: the price of a prize sold
        # to members, "Prize only" and no quick add for the others.
        for cards in (
            self._snippet_cards(newest),
            self._snippet_cards(alternative, **book_page),
        ):
            self.assertIn("25.00", cards["Claim Sold"])
            self.assertIn("js_add_cart", cards["Claim Sold"])
            mug = cards["Claim Mug"]
            self.assertIn("Prize only: Group A", mug)
            self.assertNotIn("20.00", mug)
            self.assertNotIn("js_add_cart", mug)
        # The closed shop shows no sponsored prize.
        self._set_shop_window(is_open=False)
        self.assertFalse(self._snippet_cards(newest))
        self.assertFalse(self._snippet_cards(alternative, **book_page))
        # A winner reads the token cost of the prizes of the claim only.
        self._set_shop_window(is_open=True)
        self._open()
        cards = self._snippet_cards(newest)
        self.assertNotIn("Claim Bike", cards)
        for name, price in (("Claim Mug", "20.00"), ("Claim Pen", "5.00")):
            self.assertIn(">Group A<", cards[name])
            self.assertNotIn(price, cards[name])
            self.assertNotIn("Prize only", cards[name])
        cards = self._snippet_cards(alternative, **book_page)
        self.assertEqual(set(cards), {"Claim Mug", "Claim Sold"})
        self.assertNotIn("25.00", cards["Claim Sold"])

    # Checkout

    def test_checkout_tour_reserves_the_prize(self):
        # The signed-in winner goes to the shop: no link opened.
        user = self._winner_user(self.draw)
        self.start_tour(
            "/shop", "event_raffle_prize_claim_checkout", login=user.login
        )
        self.assertEqual(self.draw.claim_state, "reserved")
        order = self.draw.prize_order_id
        self.assertEqual(order.state, "sale")
        self.assertEqual(order.raffle_draw_id, self.draw)
        self.assertEqual(order.partner_id, self.winner.partner_id)
        self.assertEqual(order.amount_total, 0.0)
        self.assertEqual(order.website_id, self.env["website"].browse(1))
        self.assertEqual(
            order.picking_ids.move_ids.filtered(
                lambda m: m.product_id == self.mug
            ).state,
            "assigned",
        )
        self.assertEqual(self.mug.raffle_qty_reserved, 1.0)
        self.assertFalse(self.draw.sudo().claim_token)
        self.assertEqual(self.draw.claim_link_state, "used")
        self.assertIn(
            "reserved", " ".join(self.draw.message_ids.mapped("body"))
        )

    def test_winner_checks_out_with_their_own_addresses(self):
        """The claim opens to its signed-in winner only, who checks the
        claim cart out as any customer of the shop."""
        portal = new_test_user(
            self.env,
            login="claim_portal_winner",
            groups="base.group_portal",
            name="Pat Portal",
            email="pat.portal@example.com",
        )
        partner = portal.partner_id
        partner.write({"street": "9 Winner Lane", "city": "Sampleville"})
        home = self.env["res.partner"].create(
            {
                "name": "Pat Home",
                "type": "delivery",
                "parent_id": partner.id,
                "street": "1 Invented Road",
                "city": "Sampleville",
            }
        )
        participant = self._participant("Pat Portal")
        participant.partner_id = partner
        draw = self._draw(participant, band_id=self.band_a.id)
        self._open(draw._claim_link_issue())
        self.assertEqual(self._session().uid, portal.id)
        self._add(self.mug)
        cart = self._cart()
        self.assertEqual(cart.partner_id, partner)
        self.assertEqual(cart.partner_shipping_id, partner)
        self.assertIn("Invented Road", self.url_open("/shop/checkout").text)
        self.make_jsonrpc_request(
            "/shop/update_address",
            {"partner_id": home.id, "address_type": "delivery"},
        )
        self.assertEqual(cart.partner_shipping_id, home)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertEqual(draw.prize_order_id, cart)
        self.assertEqual(cart.partner_id, partner)

    def test_ordinary_order_after_a_claim_is_confirmed(self):
        self._open()
        self._add(self.mug)
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        ticket = (
            self.env["product.template"]
            .create(
                {
                    "name": "Free Ticket",
                    "type": "service",
                    "list_price": 0.0,
                    "is_published": True,
                    "sale_ok": True,
                }
            )
            .product_variant_id
        )
        self._add(ticket)
        order = self._cart()
        self.assertFalse(order.raffle_draw_id)
        country = self.env["res.country"].search(
            [("state_required", "=", False), ("zip_required", "=", False)],
            limit=1,
        )
        response = self._submit_address(
            name="Ann Other",
            email="ann.other@example.com",
            phone="555 0100",
            street="2 Sample Street",
            city="Sampleville",
            country_id=country.id,
        )
        self.assertIn("redirectUrl", response.json())
        response = self._checkout()
        self.assertNotEqual(self._path(response), "/raffle/prize/done")
        self.assertEqual(order.state, "sale")
        self.assertEqual(self.draw.prize_order_id.raffle_draw_id, self.draw)

    def test_account_mandatory_website_checks_the_claim_out(self):
        self.env["website"].browse(1).account_on_checkout = "mandatory"
        self._open()
        self._add(self.mug)
        cart_page = self.url_open("/shop/cart").text
        self.assertNotIn("/web/login?redirect=", cart_page)
        checkout = self.url_open(
            "/shop/checkout?try_skip_step=true", allow_redirects=False
        )
        self.assertNotEqual(self._path(checkout), "/web/login")
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertEqual(self.draw.claim_state, "reserved")
        # An ordinary cart of a public visitor still asks for an account.
        self._use_session()
        self._add(self.book)
        response = self.url_open("/shop/checkout", allow_redirects=False)
        self.assertEqual(self._path(response), "/web/login")

    def test_deleted_draw_cancels_its_claim_cart(self):
        draw = self._draw(
            self._participant("Del Eted"), band_id=self.band_a.id
        )
        self._open(draw._claim_link_issue())
        self._add(self.mug)
        cart = self._cart()
        draw.unlink()
        self.assertEqual(cart.state, "cancel")
        self.assertFalse(cart.raffle_draw_id)
        self.assertNotIn("Claim Mug", self.url_open("/shop/cart").text)
        self.assertNotEqual(self._cart(), cart)
        self.assertEqual(self.mug.raffle_qty_reserved, 0.0)

    def test_last_unit_taken_before_confirmation_is_refused(self):
        last = self._prize("Claim Last", price=8.0, qty=1)
        self._open()
        self._add(last)
        rival = self._draw(self._participant("Rival"))
        rival._prize_claim(last)
        response = self._checkout()
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self._path(response), "/shop")
        self.assertEqual(self.draw.claim_state, "none")
        cart = self._cart()
        self.assertEqual(cart.state, "draft")
        self.assertFalse(cart._prize_lines())
        self.assertEqual(
            self.env["event.raffle.draw"]._claim_link_find(self.token),
            self.draw,
        )
        html = self.url_open("/shop").text
        self.assertIn("could not be reserved", html)
        self.assertIn('role="alert"', html)
        self.assertNotIn(last.product_tmpl_id.website_url, html)

    def test_double_confirmation_gives_one_order(self):
        own_sid = self.sid
        self._open()
        self._add(self.mug)
        own_cart = self._cart()
        # A second browser opens the same link and fills its own cart.
        second_sid = self._use_session()
        self._open()
        self._add(self.pen)
        second_cart = self._cart()
        self.url_open("/shop/checkout?try_skip_step=true")
        self.url_open("/shop/confirm_order")
        self.assertNotEqual(own_cart, second_cart)
        # The first browser confirms, then submits again.
        self._use_session(own_sid)
        response = self._checkout()
        self.assertEqual(self._path(response), "/raffle/prize/done")
        done = self.url_open("/raffle/prize/done")
        self.assertIn("Claim Mug", done.text)
        again = self.url_open(
            "/shop/payment/validate",
            data={"csrf_token": self._csrf("/raffle/prize/done")},
            allow_redirects=False,
        )
        self.assertEqual(self._path(again), "/raffle/prize/done")
        # The second browser cannot confirm its cart any more.
        self._use_session(second_sid)
        late = self.url_open(
            "/shop/payment/validate",
            data={"csrf_token": self._csrf("/shop")},
            allow_redirects=False,
        )
        self.assertEqual(late.status_code, 404)
        self.assertIn("This prize link does not work", late.text)
        confirmed = self.env["sale.order"].search(
            [("raffle_draw_id", "=", self.draw.id), ("state", "=", "sale")]
        )
        self.assertEqual(confirmed, own_cart)
        self.assertEqual(second_cart.state, "cancel")
        self.assertEqual(self.draw.prize_order_id, own_cart)

    # Member payments

    def _module_installed(self, name):
        module = self.env["ir.module.module"]._get(name)
        if module.state != "installed":
            self.skipTest(f"{name} is not installed")

    def _member_checkout(self, carrier):
        """Fill an ordinary cart with the prize sold to members, give an
        address and pick `carrier`. Returns the cart."""
        self._add(self.sold)
        cart = self._cart()
        country = self.env["res.country"].search(
            [("state_required", "=", False), ("zip_required", "=", False)],
            limit=1,
        )
        self._submit_address(
            name="Max Member",
            email="max.member@example.com",
            phone="555 0101",
            street="3 Sample Street",
            city="Sampleville",
            country_id=country.id,
        )
        self.url_open("/shop/checkout")
        self.make_jsonrpc_request(
            "/shop/set_delivery_method", {"dm_id": carrier.id}
        )
        self.assertEqual(cart.carrier_id, carrier)
        return cart

    def _pay_params(self, cart, provider, flow):
        """The parameters of the shop's transaction route for `cart`."""
        return {
            "provider_id": provider.id,
            "payment_method_id": provider.payment_method_ids[:1].id,
            "token_id": None,
            "amount": cart.amount_total,
            "flow": flow,
            "tokenization_requested": False,
            "landing_route": "/shop/payment/validate",
            "access_token": cart._portal_ensure_token(),
        }

    def _pay(self, cart, provider, flow):
        """Create the transaction of `cart` through the shop route."""
        self.make_jsonrpc_request(
            f"/shop/payment/transaction/{cart.id}",
            self._pay_params(cart, provider, flow),
        )
        return cart.transaction_ids[-1:]

    def _assert_member_order(self, cart):
        self.assertEqual(cart.state, "sale")
        self.assertFalse(cart.raffle_draw_id)
        self.assertEqual(
            cart.order_line.filtered(
                "product_id.is_raffle_prize"
            ).raffle_prize_sale_type,
            "purchase",
        )
        self.assertEqual(self.draw.claim_state, "none")
        subjects = cart.message_ids.mapped("subject")
        self.assertTrue([s for s in subjects if s and cart.name in s])
        self.assertNotIn("Your prize: Claim Sold", subjects)

    def test_member_buys_a_prize_with_an_online_provider(self):
        self._module_installed("payment_demo")
        provider = self.env.ref("payment.payment_provider_demo")
        provider.write({"state": "test", "is_published": True})
        carrier = self.env["delivery.carrier"].create(
            {
                "name": "Member Delivery",
                "delivery_type": "fixed",
                "fixed_price": 0.0,
                "is_published": True,
                "product_id": self.env["product.product"]
                .create({"name": "Member Delivery", "type": "service"})
                .id,
            }
        )
        cart = self._member_checkout(carrier)
        self.assertIn(
            "o_payment_express_checkout_form",
            self.url_open("/shop/cart").text,
        )
        payment = self.url_open("/shop/payment").text
        self.assertIn(f'data-provider-id="{provider.id}"', payment)
        self.assertIn("25.00", payment)
        tx = self._pay(cart, provider, "direct")
        self.make_jsonrpc_request(
            "/payment/demo/simulate_payment",
            {
                "reference": tx.reference,
                "payment_details": "4242",
                "simulated_state": "done",
            },
        )
        self.assertEqual(tx.state, "done")
        tx._post_process()
        self._assert_member_order(cart)
        self.assertEqual(cart.amount_total, 25.0 + cart.amount_tax)
        # A claim cart offers no express checkout and opens no transaction.
        self._use_session()
        self._open()
        self._add(self.mug)
        claim_cart = self._cart()
        self.assertNotIn(
            "o_payment_express_checkout_form",
            self.url_open("/shop/cart").text,
        )
        self.assertEqual(
            self._jsonrpc_error(
                f"/shop/payment/transaction/{claim_cart.id}",
                self._pay_params(claim_cart, provider, "direct"),
            ),
            "A prize order is confirmed without payment.",
        )
        self.assertFalse(claim_cart.transaction_ids)

    def test_payment_route_checks_the_token_before_the_claim(self):
        """The refusal of a claim cart reaches the holder of its token
        only: a wrong token reads the same on any order."""
        self._open()
        self._add(self.mug)
        claim_cart = self._cart()
        params = {
            "provider_id": 0,
            "payment_method_id": 0,
            "token_id": None,
            "amount": 0,
            "flow": "direct",
            "tokenization_requested": False,
            "landing_route": "/shop/payment/validate",
        }
        self.assertEqual(
            self._jsonrpc_error(
                f"/shop/payment/transaction/{claim_cart.id}",
                dict(params, access_token=claim_cart._portal_ensure_token()),
            ),
            "A prize order is confirmed without payment.",
        )
        ordinary = self.env["sale.order"].create(
            {"partner_id": self.winner.partner_id.id}
        )
        self._use_session()
        answers = {
            self._jsonrpc_error(
                f"/shop/payment/transaction/{order.id}",
                dict(params, access_token="not-the-token"),
            )
            for order in (claim_cart, ordinary)
        }
        self.assertEqual(answers, {"The access token is invalid."})
        self.assertFalse(claim_cart.transaction_ids)

    def _portal_pay_error(self, order, provider):
        """The error that the portal payment route of `order` answers."""
        params = dict(
            self._pay_params(order, provider, "redirect"),
            landing_route=order.get_portal_url(),
        )
        return self._jsonrpc_error(
            f"/my/orders/{order.id}/transaction", params
        )

    def test_portal_payment_route_refuses_what_the_shop_refuses(self):
        """The payment route of the order portal opens no transaction for
        a claim cart, nor for a website cart whose prize is no longer for
        sale."""
        self._module_installed("payment_custom")
        provider = self.env.ref("payment.payment_provider_transfer")
        provider.write({"state": "enabled", "is_published": True})
        self._open()
        self._add(self.mug)
        claim_cart = self._cart()
        self.assertEqual(
            self._portal_pay_error(claim_cart, provider),
            "A prize order is confirmed without payment.",
        )
        self.assertFalse(claim_cart.transaction_ids)
        self.assertEqual(claim_cart.state, "draft")
        self._use_session()
        self._add(self.sold)
        member_cart = self._cart()
        self._set_shop_window(is_open=False)
        self.assertIn(
            "cannot be bought now",
            self._portal_pay_error(member_cart, provider),
        )
        self.assertFalse(member_cart.transaction_ids)
        self.assertEqual(member_cart.state, "draft")

    def test_claim_cart_sent_for_payment_is_confirmed_by_its_claim_only(self):
        self._open()
        self._add(self.mug)
        cart = self._cart()
        cart.action_quotation_sent()
        self.assertEqual(cart.state, "sent")
        with self.assertRaises(UserError):
            cart.action_confirm()
        self.assertEqual(cart.state, "sent")
        self.assertEqual(self.draw.claim_state, "none")
        self.draw._claim_cancel_carts()
        self.assertEqual(cart.state, "cancel")

    def test_member_pays_a_prize_on_site(self):
        self._module_installed("website_sale_collect")
        provider = self.env.ref(
            "website_sale_collect.payment_provider_on_site"
        )
        provider.write({"state": "enabled", "is_published": True})
        carrier = self.env.ref("website_sale_collect.carrier_pick_up_in_store")
        carrier.write(
            {
                "warehouse_ids": [odoo.Command.set(self.warehouse.ids)],
                "is_published": True,
            }
        )
        cart = self._member_checkout(carrier)
        self.make_jsonrpc_request(
            "/website_sale/set_pickup_location",
            {
                "pickup_location_data": json.dumps(
                    {
                        "id": self.warehouse.id,
                        "name": self.warehouse.name,
                        "street": "4 Pick-up Lane",
                        "city": "Sampleville",
                        "zip_code": "",
                        "country_code": "",
                        "state": "",
                    }
                )
            },
        )
        payment = self.url_open("/shop/payment").text
        self.assertIn(f'data-provider-id="{provider.id}"', payment)
        tx = self._pay(cart, provider, "redirect")
        self.url_open(
            "/payment/custom/process", data={"reference": tx.reference}
        )
        self.assertEqual(tx.state, "pending")
        tx._post_process()
        self._assert_member_order(cart)
        # The claim cart of a winner never gets the pick-up, nor a payment.
        self._use_session()
        self._open()
        self._add(self.mug)
        claim_cart = self._cart()
        self.assertEqual(
            claim_cart._get_delivery_methods(),
            self.env.ref("event_raffle_prize_claim.carrier_prize_handover"),
        )
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertEqual(claim_cart.amount_total, 0.0)
        self.assertFalse(claim_cart.transaction_ids)

    # Decline

    def test_decline_from_the_page(self):
        other = self._draw(self._participant("Other Winner"))
        other_token = other._claim_link_issue()
        self._open()
        self._add(self.mug)
        cart = self._cart()
        form = self.url_open("/raffle/prize/decline")
        self.assertEqual(form.status_code, 200)
        self.assertIn('for="o_raffle_decline_comment"', form.text)
        # No CSRF token, no decline.
        response = self.url_open(
            "/raffle/prize/decline", data={"comment": "No token"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.draw.claim_state, "none")
        csrf = self._csrf("/raffle/prize/decline")
        response = self.url_open(
            "/raffle/prize/decline", data={"csrf_token": csrf, "comment": " "}
        )
        self.assertIn("Say why you decline the prize", response.text)
        self.assertIn('aria-invalid="true"', response.text)
        self.assertEqual(self.draw.claim_state, "none")
        response = self.url_open(
            "/raffle/prize/decline",
            data={
                "csrf_token": csrf,
                "comment": "Already have one",
                "draw_id": other.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.draw.claim_state, "declined")
        self.assertEqual(self.draw.decline_comment, "Already have one")
        self.assertFalse(self.draw.sudo().claim_token)
        self.assertEqual(cart.state, "cancel")
        # The other draw is untouched, whatever the form sent.
        self.assertEqual(other.claim_state, "none")
        self.assertEqual(other.sudo().claim_token, other_token)
        self.assertFalse(self._session().get("raffle_prize_claim"))
        self.assertNotIn("o_raffle_claim_banner", self.url_open("/shop").text)
        self.assertEqual(
            self.url_open("/raffle/prize/decline").status_code, 404
        )
        bodies = self._channel_bodies()
        self.assertEqual(len(bodies), 1)
        self.assertIn("Already have one", bodies[0])

    # Accessibility

    def test_axe_source_skips_only_without_the_variable(self):
        missing = {AXE_ENV: "/nonexistent/axe.min.js"}
        with (
            patch.dict(os.environ, missing),
            self.assertRaises(self.failureException),
        ):
            self._axe_source()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(AXE_ENV, None)
            with self.assertRaises(unittest.SkipTest):
                self._axe_source()

    def test_axe_core_finds_no_wcag_violation(self):
        """axe-core, WCAG 2.0/2.1/2.2 A and AA rules plus "region", on what
        the module renders: the claim banner, the sponsor lines, the
        remaining quantities of the shop cards (grid and list layouts) and
        the token costs of the shop, product, cart and checkout pages, for
        a winner and for an ordinary visitor, the decline and invalid link
        pages, and the refusal of a link to another account, at 390 px
        wide and on a desktop width. The rest of those pages is
        website_sale's own markup, left to its audit. The whole page must
        not scroll sideways."""
        code = self._axe_code("""
            await raffleAxeAudit(window, [
                ".o_raffle_claim_banner",
                ".o_raffle_prize_sponsor",
                ".o_raffle_shop_stock",
                ".o_raffle_claim_page",
                ".o_raffle_token_cost",
                ".o_raffle_token_total",
            ]);
            """)
        # A visitor with the claim open and a prize in the cart.
        self._open()
        self._add(self.mug)
        claim_sid = self.sid
        # An ordinary visitor of the open sponsored shop.
        visitor_sid = self._use_session()
        # The same, with the list layout of the shop.
        list_sid = self._use_session()
        session = self._session()
        session["website_sale_shop_layout_mode"] = "list"
        odoo.http.root.session_store.save(session)
        # A member signed in on the winner's link.
        other_sid = self._use_session()
        self._sign_in(
            new_test_user(
                self.env,
                login="claim_axe_member",
                groups="base.group_portal",
                name="Axel Member",
            )
        )
        pages = (
            [
                (claim_sid, url)
                for url in (
                    "/shop",
                    self.mug.product_tmpl_id.website_url,
                    "/shop/cart",
                    "/shop/checkout?try_skip_step=true",
                    "/raffle/prize/decline",
                    "/raffle/prize/" + "z" * 43,
                )
            ]
            + [
                (visitor_sid, url)
                for url in (
                    "/shop?search=Claim",
                    self.mug.product_tmpl_id.website_url,
                )
            ]
            + [(list_sid, "/shop?search=Claim")]
            + [(other_sid, f"/raffle/prize/{self.token}")]
        )
        for width in (390, 1280):
            for sid, url in pages:
                with self.subTest(
                    url=url, width=width, winner=sid == claim_sid
                ):
                    self.browser_size = f"{width}x900"
                    self._axe_browse(url, code, cookies={"session_id": sid})
        # Every page above kept the claim open.
        self.assertEqual(self.draw.claim_state, "none")
