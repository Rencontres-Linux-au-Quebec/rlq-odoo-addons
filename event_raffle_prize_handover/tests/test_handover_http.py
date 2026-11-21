# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import html
import io
import json
import re
from urllib.parse import quote, urlsplit

from PIL import Image

from odoo.tests import new_test_user, tagged
from odoo.tests.common import HttpCase

from odoo.addons.event_raffle_prize_claim.tests import (
    test_claim_shop as claim_shop,
)
from odoo.addons.event_raffle_prize_claim.tests.axe import AxeMixin

from .common import HandoverDataMixin

PUBLIC_KEYS = {
    "id",
    "name",
    "prize",
    "status",
    "sponsor",
    "sponsor_url",
    "category",
}


@tagged("post_install", "-at_install")
class TestHandoverHttp(AxeMixin, HandoverDataMixin, HttpCase):
    """The prize pages, the hand-over screen and the winners page, through
    the website routes."""

    # The visitor sessions, CSRF and checkout helpers of the prize link
    # tests.
    _use_session = claim_shop.TestClaimShop._use_session
    _session = claim_shop.TestClaimShop._session
    _csrf = claim_shop.TestClaimShop._csrf
    _add = claim_shop.TestClaimShop._add
    _checkout = claim_shop.TestClaimShop._checkout
    _path = claim_shop.TestClaimShop._path
    _winner_user = claim_shop.TestClaimShop._winner_user
    _sign_in = claim_shop.TestClaimShop._sign_in
    _open_token = claim_shop.TestClaimShop._open

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._handover_setup()
        cls.portal = new_test_user(
            cls.env,
            login="handover_portal",
            groups="base.group_portal",
            name="Paula Portal",
        )
        cls.employee = new_test_user(
            cls.env,
            login="handover_employee",
            groups="base.group_user",
            name="Emil Employee",
        )

    def _open(self, draw):
        """Issue a link of `draw` and open it, signed in as its winner."""
        return self._open_token(draw._claim_link_issue())

    def _claim_through_the_shop(self, draw, product):
        self._use_session()
        self._open(draw)
        self._add(product)
        response = self._checkout()
        self.assertEqual(self._path(response), "/raffle/prize/done")
        self.assertEqual(draw.claim_state, "reserved")

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _reserved(self, name, product=None, **kwargs):
        participant = self._participant(name, **kwargs)
        draw = self._draw(participant)
        draw._prize_claim(product or self.mug)
        return draw

    # Confirmation page and public name

    def test_done_page_says_where_to_pick_up_and_sets_the_public_name(self):
        participant = self._participant("Dora Done")
        draw = self._draw(participant)
        self._claim_through_the_shop(draw, self.mug)
        page = self.url_open("/raffle/prize/done").text
        self.assertIn("Pick up your prize at Table 7, hall B.", page)
        self.assertNotIn("The event team will tell you how to get it.", page)
        self.assertIn('for="o_raffle_public_name_input"', page)
        self.assertIn("Shown as: <strong", page)
        # No CSRF token, no change.
        response = self.url_open(
            "/raffle/prize/public-name", data={"public_name": "No Token"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(participant.partner_id.raffle_public_name)
        other = self._participant("Otto Other")
        csrf = self._csrf("/raffle/prize/done")
        response = self.url_open(
            "/raffle/prize/public-name",
            data={
                "csrf_token": csrf,
                "public_name": "  Dora   the Penguin ",
                "partner_id": other.partner_id.id,
                "draw_id": other.id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            participant.partner_id.raffle_public_name, "Dora the Penguin"
        )
        self.assertFalse(other.partner_id.raffle_public_name)
        self.assertIn("Your public name is saved.", response.text)
        self.assertIn('role="status"', response.text)

    def test_public_name_form_refuses_a_session_without_a_claim(self):
        participant = self._participant("Gina Guest")
        draw = self._draw(participant)
        # A session with an open link of its own, but no confirmed claim.
        self._use_session()
        self._open(draw)
        csrf = self._csrf("/shop")
        response = self.url_open(
            "/raffle/prize/public-name",
            data={"csrf_token": csrf, "public_name": "Intruder"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(participant.partner_id.raffle_public_name)
        # The guest of another claim changes its own winner only.
        winner = self._participant("Will Winner")
        won = self._draw(winner)
        self._claim_through_the_shop(won, self.mug)
        csrf = self._csrf("/raffle/prize/done")
        self.url_open(
            "/raffle/prize/public-name",
            data={"csrf_token": csrf, "public_name": "Willy"},
        )
        self.assertEqual(winner.partner_id.raffle_public_name, "Willy")
        self.assertFalse(participant.partner_id.raffle_public_name)

    def test_done_page_in_french(self):
        lang = self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            [
                "event_raffle_prize",
                "event_raffle_prize_claim",
                "event_raffle_prize_handover",
            ],
            ["fr_CA"],
            overwrite=True,
        )
        self.env["website"].browse(1).language_ids |= lang
        participant = self._participant("Fred Francais")
        draw = self._draw(participant)
        self._claim_through_the_shop(draw, self.mug)
        self.opener.cookies["frontend_lang"] = "fr_CA"
        page = self.url_open(f"/{lang.url_code}/raffle/prize/done").text
        self.assertIn("Lieu de retrait de votre prix : Table 7, hall B.", page)
        self.assertIn("Nom public", page)

    def test_portal_account_sets_the_public_name(self):
        self._login(self.portal)
        page = self.url_open("/my/account").text
        self.assertIn('name="raffle_public_name"', page)
        self.assertIn('for="o_raffle_public_name_account"', page)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = {
            "csrf_token": csrf,
            "name": "Paula Portal",
            "email": "paula.portal@example.com",
            "phone": "555-0100",
            "street": "1 Invented Road",
            "city": "Sampleville",
            "country_id": str(self.env.ref("base.ca").id),
            "raffle_public_name": "  Paula   P. ",
        }
        self.url_open("/my/account", data=data)
        self.assertEqual(self.portal.partner_id.raffle_public_name, "Paula P.")
        data["raffle_public_name"] = "x" * 80
        page = self.url_open("/my/account", data=data).text
        self.assertIn("The public name holds 64 characters at most.", page)
        self.assertEqual(self.portal.partner_id.raffle_public_name, "Paula P.")

    # Virtual prize checkout

    def test_virtual_prize_checkout_asks_for_no_address(self):
        # A virtual winner whose contact has a name and an email only.
        physical = self._draw(self._participant("Phil Far", attended=False))
        self._use_session()
        self._open(physical)
        self._add(self.mug)
        response = self.url_open(
            "/shop/checkout?try_skip_step=true", allow_redirects=False
        )
        self.assertEqual(self._path(response), "/shop/address")
        virtual = self._draw(self._participant("Vic Far", attended=False))
        self._use_session()
        self._open(virtual)
        self._add(self.ebook)
        response = self.url_open(
            "/shop/checkout?try_skip_step=true", allow_redirects=False
        )
        self.assertNotEqual(self._path(response), "/shop/address")
        self.assertEqual(self._path(self._checkout()), "/raffle/prize/done")
        self.assertEqual(virtual.claim_state, "reserved")
        self.assertEqual(virtual.prize_product_id, self.ebook)
        page = self.url_open("/raffle/prize/done").text
        self.assertIn("Your prize will be sent to you by email.", page)

    # Hand-over screen

    def test_handover_screen_is_for_event_users_only(self):
        self._reserved("Ada Access")
        self._use_session()
        response = self.url_open("/raffle/handover", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self._path(response), "/web/login")
        for user in (self.portal, self.employee):
            self._login(user)
            for url in ("/raffle/handover", "/raffle/handover?search=Ada"):
                response = self.url_open(url)
                self.assertEqual(response.status_code, 403, user.login)
                self.assertNotIn("Ada Access", response.text)
        self._login(self.organizer)
        response = self.url_open("/raffle/handover")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ada Access", response.text)

    def test_pages_ignore_the_draws_of_another_company(self):
        """The hand-over screen reads a draw with the user's companies, and
        the winners page answers on the website of the event's company
        only."""
        company_b = self.env["res.company"].create(
            {"name": "Handover Company B"}
        )
        event_b = self.env["event.event"].create(
            {
                "name": "Company B Fair",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
                "company_id": company_b.id,
                "raffle_winners_published": True,
            }
        )
        raffle_b = self.env["event.raffle"].create(
            {
                "name": "Company B raffle",
                "event_id": event_b.id,
                "company_id": company_b.id,
            }
        )
        participant = self.env["event.raffle.participant"].create(
            {"raffle_id": raffle_b.id, "name": "Bert Elsewhere"}
        )
        draw_b = self._draw(participant)
        self._login(self.organizer)
        response = self.url_open(f"/raffle/handover/{draw_b.id}")
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Bert Elsewhere", response.text)
        self._use_session()
        path = event_b._raffle_winners_path()
        for url in (path, f"{path}/data"):
            response = self.url_open(url)
            self.assertEqual(response.status_code, 404, url)
            self.assertNotIn("Bert Elsewhere", response.text)

    def test_winners_page_lists_the_raffles_of_the_event_company(self):
        """The winners page of an event lists the draws of its raffles of
        the event's company and of those without a company, and leaves
        out a raffle of another company held in the same event."""
        company_b = self.env["res.company"].create(
            {"name": "Handover Company B"}
        )
        names = {}
        for company, name in (
            (company_b, "Bert Elsewhere"),
            (self.env["res.company"], "Nina Nocompany"),
        ):
            raffle = self.env["event.raffle"].create(
                {
                    "name": f"Raffle of {name}",
                    "event_id": self.event.id,
                    "company_id": company.id,
                }
            )
            participant = self.env["event.raffle.participant"].create(
                {"raffle_id": raffle.id, "name": name}
            )
            names[name] = self._draw(participant)
        path = self._published()
        self._use_session()
        page = self.url_open(path).text
        data = self.url_open(f"{path}/data").json()
        listed = {w["id"] for g in data["groups"] for w in g["winners"]}
        self.assertNotIn("Bert Elsewhere", page)
        self.assertNotIn(names["Bert Elsewhere"].id, listed)
        self.assertIn("Nina Nocompany", page)
        self.assertIn(names["Nina Nocompany"].id, listed)

    def test_handover_search_lists_the_matching_claims_only(self):
        alice = self._reserved(
            "Alice Search", email="alice.search@example.net"
        )
        alice.partner_id.raffle_public_name = "Tux Rider"
        self._reserved("Bruno Search")
        self._login(self.organizer)
        for term in ("Tux Rider", "alice.search", f"#{alice.sequence}"):
            page = self.url_open(f"/raffle/handover?search={quote(term)}").text
            self.assertIn("Alice Search", page, term)
            self.assertNotIn("Bruno Search", page, term)
        page = self.url_open("/raffle/handover").text
        self.assertIn("Alice Search", page)
        self.assertIn("Bruno Search", page)
        self.assertIn('role="search"', page)
        self.assertIn("Handover Mug", page)
        self.assertIn("Sponsor Example", page)

    def test_hand_over_with_a_photo_through_the_screen(self):
        draw = self._reserved("Hank Handover")
        self._login(self.organizer)
        step = self.url_open(f"/raffle/handover/{draw.id}").text
        self.assertIn('capture="environment"', step)
        self.assertIn('accept="image/*"', step)
        self.assertIn('enctype="multipart/form-data"', step)
        url = f"/raffle/handover/{draw.id}/confirm"
        photo = self._image(2500, 1000, "JPEG")
        response = self.url_open(url, files={"photo": ("p.jpg", photo)})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(draw.claim_state, "reserved")
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        response = self.url_open(
            url,
            data={"csrf_token": csrf},
            files={"photo": ("photo.jpg", photo, "image/jpeg")},
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        location = urlsplit(response.headers["Location"])
        self.assertEqual(
            (location.path, location.query),
            ("/raffle/handover", f"done={draw.id}"),
        )
        self.assertEqual(draw.claim_state, "delivered")
        self.assertEqual(draw.prize_order_id.picking_ids.state, "done")
        image = Image.open(
            io.BytesIO(base64.b64decode(draw.prize_handover_photo))
        )
        self.assertEqual(image.size, (1920, 768))
        page = self.url_open(f"/raffle/handover?done={draw.id}").text
        self.assertIn("o_raffle_handover_done", page)
        self.assertIn('aria-live="polite"', page)
        self.assertIn("Handover Mug handed over to Hank Handover.", page)
        step = self.url_open(f"/raffle/handover/{draw.id}").text
        self.assertIn("no longer waiting", step)
        self.assertNotIn(f'action="{url}"', step)
        # Neither the field nor the attachment is public.
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "event.raffle.draw"),
                ("res_id", "=", draw.id),
                ("res_field", "=", False),
            ]
        )
        self.assertEqual(len(attachment), 1)
        self.assertFalse(attachment.public)
        stored = attachment.raw
        field_bytes = base64.b64decode(draw.prize_handover_photo)
        for user in (None, self.portal):
            if user:
                self._login(user)
            else:
                self._use_session()
            response = self.url_open(f"/web/content/{attachment.id}")
            self.assertIn(response.status_code, (403, 404))
            self.assertNotEqual(response.content, stored)
            response = self.url_open(
                f"/web/image/event.raffle.draw/{draw.id}/prize_handover_photo"
            )
            self.assertNotIn(response.content, (stored, field_bytes))

    def test_handover_screen_refuses_a_bad_photo_and_keeps_the_claim(self):
        draw = self._reserved("Bea Badphoto")
        self._login(self.organizer)
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        response = self.url_open(
            f"/raffle/handover/{draw.id}/confirm",
            data={"csrf_token": csrf},
            files={"photo": ("note.txt", b"plain text", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('role="alert"', response.text)
        self.assertEqual(draw.claim_state, "reserved")
        self.assertFalse(draw.prize_handover_photo)

    def test_user_without_email_hands_over_through_the_screen(self):
        draw = self._reserved("Nina Screen")
        user = new_test_user(
            self.env,
            login="handover_screen_no_email",
            groups="base.group_user,event.group_event_user",
            name="Nico Nomail",
        )
        user.partner_id.email = False
        self.authenticate(user.login, user.login)
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        response = self.url_open(
            f"/raffle/handover/{draw.id}/confirm",
            data={"csrf_token": csrf},
            files={"photo": ("p.png", self._image(30, 20), "image/png")},
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(draw.claim_state, "delivered")
        notes = draw.message_ids.filtered(
            lambda m: "(by Nico Nomail)" in str(m.body)
        )
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes.author_id, self.odoobot)

    def test_hand_over_form_sent_twice_shows_the_success(self):
        draw = self._reserved("Tia Twice")
        self._login(self.organizer)
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        url = f"/raffle/handover/{draw.id}/confirm"
        for __ in range(2):
            response = self.url_open(
                url, data={"csrf_token": csrf}, allow_redirects=False
            )
            self.assertEqual(response.status_code, 303)
            location = urlsplit(response.headers["Location"])
            self.assertEqual(
                (location.path, location.query),
                ("/raffle/handover", f"done={draw.id}"),
            )
        self.assertEqual(draw.claim_state, "delivered")
        handed = draw.message_ids.filtered(
            lambda m: "handed over" in (m.body or "")
        )
        self.assertEqual(len(handed), 1)
        self.assertEqual(
            draw.prize_order_id.picking_ids.mapped("state"), ["done"]
        )
        page = self.url_open(f"/raffle/handover?done={draw.id}").text
        self.assertIn("Handover Mug handed over to Tia Twice.", page)
        # Another event user is not sending the same form again.
        other = new_test_user(
            self.env,
            login="handover_other",
            groups="base.group_user,event.group_event_user",
            name="Handover Other",
        )
        self._login(other)
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        response = self.url_open(url, data={"csrf_token": csrf})
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer waiting", response.text)
        # Nor is the same user, once the hand-over is older.
        self._login(self.organizer)
        self.env.cr.execute(
            "UPDATE event_raffle_draw SET prize_received_date ="
            " prize_received_date - interval '1 hour' WHERE id = %s",
            (draw.id,),
        )
        self.env.invalidate_all()
        csrf = self._csrf(f"/raffle/handover/{draw.id}")
        response = self.url_open(url, data={"csrf_token": csrf})
        self.assertEqual(response.status_code, 400)

    def test_hand_over_form_is_busy_while_it_is_sent(self):
        draw = self._reserved("Pia Pending")
        code = """
            const form = document.querySelector(".o_raffle_handover_form");
            const button = form.querySelector(".o_raffle_handover_confirm");
            const status = form.querySelector(".o_raffle_handover_pending");
            let sent = 0;
            // Counts the submits that would leave the page, and keeps it.
            form.addEventListener("submit", (ev) => {
                if (!ev.defaultPrevented) {
                    sent += 1;
                }
                ev.preventDefault();
            });
            const check = (ok, message) => {
                if (!ok) {
                    throw new Error(message);
                }
            };
            try {
                check(!form.hasAttribute("aria-busy"), "busy at load");
                button.focus();
                button.click();
                check(form.getAttribute("aria-busy") === "true", "not busy");
                check(
                    button.getAttribute("aria-disabled") === "true",
                    "button not disabled"
                );
                check(button.textContent === "Sending...", "label kept");
                check(status.textContent === "Sending...", "nothing said");
                check(status.getAttribute("role") === "status", "no status");
                check(document.activeElement === button, "focus lost");
                button.click();
                form.requestSubmit(button);
                check(sent === 1, `sent ${sent} times`);
                window.dispatchEvent(
                    new PageTransitionEvent("pageshow", {persisted: true})
                );
                check(!form.hasAttribute("aria-busy"), "busy after back");
                check(
                    button.textContent === "Confirm the hand-over",
                    "label not restored"
                );
                console.log("test successful");
            } catch (error) {
                console.error(error.message);
            }
        """
        self.browser_js(
            f"/raffle/handover/{draw.id}",
            code,
            ready="!!document.querySelector("
            "'.o_raffle_handover_form[data-handover-ready]')",
            login=self.organizer.login,
        )
        self.assertEqual(draw.claim_state, "reserved")

    def test_handover_screen_counts_and_messages(self):
        self._login(self.organizer)
        page = self.url_open("/raffle/handover?search=Nobody%20Here").text
        self.assertIn("No winner is waiting for a prize.", page)
        self.assertNotIn("0 winners", page)
        lang = self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            [
                "event_raffle",
                "event_raffle_prize",
                "event_raffle_prize_claim",
                "event_raffle_prize_handover",
            ],
            ["fr_CA"],
            overwrite=True,
        )
        self.env["website"].browse(1).language_ids |= lang
        draw = self._reserved("Lea Livre")
        draw.with_user(self.organizer)._prize_hand_over()
        self.opener.cookies["frontend_lang"] = "fr_CA"
        page = html.unescape(
            self.url_open(
                f"/{lang.url_code}/raffle/handover?done={draw.id}"
            ).text
        )
        self.assertIn("Prix remis à Lea Livre : Handover Mug.", page)
        self.assertIn("Aucun gagnant n'attend de prix.", page)
        self.assertNotIn("0 gagnants", page)
        waiting = self._reserved("Max Attente")
        step = html.unescape(
            self.url_open(
                f"/{lang.url_code}/raffle/handover/{waiting.id}"
            ).text
        )
        self.assertIn('data-label-sending="Envoi en cours..."', step)

    # Winners page

    def _published(self):
        self.event.raffle_winners_published = True
        return self.event._raffle_winners_path()

    def test_winners_page_exists_only_when_published(self):
        self._reserved("Una Published")
        path = self.event._raffle_winners_path()
        self._use_session()
        for url in (path, f"{path}/data", f"/raffle/winners/{self.event.id}"):
            self.assertEqual(self.url_open(url).status_code, 404, url)
        self._published()
        for url in (path, f"{path}/data", f"/raffle/winners/{self.event.id}"):
            self.assertEqual(self.url_open(url).status_code, 200, url)
        self.assertEqual(
            self.url_open("/raffle/winners/no-such-event-999999").status_code,
            404,
        )

    def test_winners_page_shows_public_fields_only(self):
        named = self._reserved("Real Fullname", email="real.full@example.org")
        named.partner_id.raffle_public_name = "Secret Penguin"
        plain = self._reserved("Plain Person")
        absent = self._reserved("Gone Away")
        absent.is_absent = True
        declined = self._reserved("Said Nope")
        declined._prize_decline("No")
        path = self._published()
        self._use_session()
        html = self.url_open(path).text
        data = self.url_open(f"{path}/data").json()
        dump = json.dumps(data)
        for text in (
            "Secret Penguin",
            "Plain Person",
            "Handover Mug",
            "Said Nope",
            "Prize declined",
        ):
            self.assertIn(text, html)
            self.assertIn(text, dump)
        self.assertIn('href="https://sponsor.example.org"', html)
        own = html[html.index('class="o_raffle_winners') :]
        own = own[: own.index("</main>")]
        for text in (
            "Real Fullname",
            "real.full@example.org",
            "@example.com",
            "Gone Away",
        ):
            self.assertNotIn(text, html, text)
            self.assertNotIn(text, dump, text)
        for text in ("prize_handover_photo", "/web/image", "<img"):
            self.assertNotIn(text, own, text)
            self.assertNotIn(text, dump, text)
        self.assertEqual(
            set(data), {"groups", "count", "updated", "updated_label"}
        )
        for group in data["groups"]:
            self.assertEqual(set(group), {"key", "label", "winners"})
            for winner in group["winners"]:
                self.assertEqual(set(winner), PUBLIC_KEYS)
        self.assertEqual(data["count"], 3)
        self.assertIn(
            plain.id, [w["id"] for g in data["groups"] for w in g["winners"]]
        )
        self.assertIn(
            '<noscript><meta http-equiv="refresh" content="600"', html
        )
        self.assertIn('aria-live="polite"', html)
        self.assertIn("Updated at", html)

    def _winner_item(self, page, draw):
        """The text of the prize line of `draw` on `page`, and its
        status."""
        start = page.index(f'data-winner="{draw.id}"')
        item = page[start : page.index("</li>", start)]
        match = re.search(
            r'class="o_raffle_winner_prize[^"]*" data-status="([a-z_]+)">'
            r"([^<]*)<",
            item,
        )
        self.assertTrue(match, item)
        return html.unescape(match.group(2)).strip(), match.group(1)

    def test_winners_page_lists_winners_whatever_their_claim(self):
        open_claim = self._draw(
            self._participant("Open Olga"), band_id=self.band_a.id
        )
        open_claim._claim_link_issue()
        declined = self._draw(self._participant("Decline Dora"))
        declined._claim_link_issue()
        declined._claim_link_decline("Private reason")
        expired = self._draw(self._participant("Expired Eli"))
        expired._claim_link_issue()
        self._expire(expired)
        expired._claim_link_expire()
        chosen = self._reserved("Chosen Chad")
        absent = self._draw(self._participant("Absent Abe"))
        absent.is_absent = True
        path = self._published()
        self._use_session()
        page = self.url_open(path).text
        data = self.url_open(f"{path}/data").json()
        lines = {w["id"]: w for g in data["groups"] for w in g["winners"]}
        expected = {
            open_claim: ("Group A, prize to choose", "to_choose"),
            declined: ("Prize declined", "declined"),
            expired: ("No prize chosen", "expired"),
            chosen: ("Handover Mug", "chosen"),
        }
        for draw, (text, status) in expected.items():
            self.assertEqual(self._winner_item(page, draw), (text, status))
            self.assertEqual(
                (lines[draw.id]["prize"], lines[draw.id]["status"]),
                (text, status),
            )
        self.assertNotIn("Absent Abe", page)
        self.assertNotIn(absent.id, lines)
        self.assertNotIn("Private reason", page)
        self.assertNotIn("Private reason", json.dumps(data))
        # The page names the token category in the prize line only.
        start = page.index(f'data-winner="{open_claim.id}"')
        item = page[start : page.index("</li>", start)]
        self.assertNotIn("Token category", item)
        self.assertNotIn("Offered by", item)

    def test_winners_page_in_french(self):
        lang = self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize_handover"], ["fr_CA"], overwrite=True
        )
        self.env["website"].browse(1).language_ids |= lang
        self.band_a.name = "Groupe de prix A"
        open_claim = self._draw(
            self._participant("Anne Ouverte"), band_id=self.band_a.id
        )
        declined = self._reserved("Rene Refus")
        declined._prize_decline("Non")
        expired = self._draw(self._participant("Xavier Expire"))
        expired.sudo().claim_state = "expired"
        path = self._published()
        self._use_session()
        self.opener.cookies["frontend_lang"] = "fr_CA"
        page = self.url_open(f"/{lang.url_code}{path}").text
        data = self.url_open(f"/{lang.url_code}{path}/data").json()
        lines = {
            w["id"]: w["prize"] for g in data["groups"] for w in g["winners"]
        }
        for draw, text in (
            (open_claim, "Groupe de prix A, prix à choisir"),
            (declined, "Prix refusé"),
            (expired, "Aucun prix choisi"),
        ):
            self.assertEqual(self._winner_item(page, draw)[0], text)
            self.assertEqual(lines[draw.id], text)

    def test_winners_page_refreshes_in_place(self):
        # Listed newest first: the chosen prize, then the prize to choose.
        self._draw(self._participant("First Winner"), band_id=self.band_a.id)
        self._reserved("Second Winner")
        path = self._published()
        code = """
            (async () => {
                const root = document.querySelector(".o_raffle_winners");
                const items = root.querySelectorAll("[data-winner]");
                if (items.length !== 2) {
                    throw new Error(`expected 2 winners, got ${items.length}`);
                }
                const link = items[0].querySelector("[data-focus-key]");
                link.focus();
                const key = link.dataset.focusKey;
                items[1].remove();
                root.querySelector(".o_raffle_winners_updated time").textContent = "";
                const done = "o-raffle-winners-refreshed";
                await new Promise((resolve) => {
                    root.addEventListener(done, resolve, {once: true});
                    root.dispatchEvent(new CustomEvent("o-raffle-winners-refresh"));
                });
                const live = root.querySelector(".o_raffle_winners_live").textContent;
                if (live !== "1 new winner") {
                    throw new Error(`announced "${live}"`);
                }
                if (root.querySelectorAll("[data-winner]").length !== 2) {
                    throw new Error("the list was not rebuilt");
                }
                const prizes = root.querySelectorAll(".o_raffle_winner_prize");
                const statuses = [...prizes].map((el) => el.dataset.status);
                if (statuses.join() !== "chosen,to_choose") {
                    throw new Error(`prize statuses ${statuses.join()}`);
                }
                if (document.activeElement.dataset.focusKey !== key) {
                    throw new Error("the focus moved");
                }
                if (!root.querySelector(".o_raffle_winners_updated time").textContent) {
                    throw new Error("no update time");
                }
                console.log("test successful");
            })().catch((error) => console.error(error.message));
        """
        self.browser_js(
            path,
            code,
            ready="!!document.querySelector('.o_raffle_winners[data-refresh-ready]')",
        )

    # Accessibility

    def test_axe_core_finds_no_wcag_violation(self):
        """axe-core, WCAG 2.0/2.1/2.2 A and AA rules plus "region", on the
        module's own markup: the winners page at 390 px and on a desktop
        width, and the hand-over list, hand-over step and the public name
        form of the confirmation page at 390 px. The page must not scroll
        sideways, and the buttons and fields of the hand-over screen and of
        the public name form are 48 px high at least."""
        code = self._axe_code("""
            await raffleAxeAudit(
                window,
                [
                    ".o_raffle_winners",
                    ".o_raffle_handover",
                    ".o_raffle_public_name",
                    ".o_raffle_claim_done_handover",
                ],
                [
                    ".o_raffle_handover .btn",
                    ".o_raffle_handover .form-control",
                    ".o_raffle_public_name .btn",
                    ".o_raffle_public_name .form-control",
                ]
            );
            """)
        reserved = self._reserved("Axe Waiting")
        delivered = self._reserved("Axe Delivered")
        delivered.partner_id.raffle_public_name = "Axe Fan"
        delivered._prize_hand_over()
        path = self._published()
        for width in (390, 1280):
            with self.subTest(page="winners", width=width):
                self.browser_size = f"{width}x900"
                self._axe_browse(path, code)
        self.browser_size = "390x900"
        for url in (
            "/raffle/handover",
            f"/raffle/handover?search=Axe&done={delivered.id}",
            f"/raffle/handover/{reserved.id}",
        ):
            with self.subTest(page=url):
                self._axe_browse(url, code, login=self.organizer.login)
        winner = self._participant("Axe Claimer")
        self._claim_through_the_shop(self._draw(winner), self.mug)
        with self.subTest(page="done"):
            self._axe_browse(
                "/raffle/prize/done", code, cookies={"session_id": self.sid}
            )
