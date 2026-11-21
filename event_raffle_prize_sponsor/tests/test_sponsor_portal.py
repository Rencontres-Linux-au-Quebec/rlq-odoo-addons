# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
import io
from datetime import timedelta
from urllib.parse import urlsplit

from lxml import html as lxml_html
from PIL import Image

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.event_raffle_prize_claim.tests import (
    test_claim_shop as claim_shop,
)
from odoo.addons.event_raffle_prize_claim.tests.axe import AxeMixin

from .common import SponsorDataMixin

NEW = "/my/raffle-prizes/new"
LIST = "/my/raffle-prizes"


@tagged("post_install", "-at_install")
class TestSponsorPortal(AxeMixin, SponsorDataMixin, HttpCase):
    """The Prizes for raffle pages of the portal, through their routes."""

    # The visitor sessions of the prize link tests.
    _use_session = claim_shop.TestClaimShop._use_session
    _session = claim_shop.TestClaimShop._session
    _csrf = claim_shop.TestClaimShop._csrf
    _winner_user = claim_shop.TestClaimShop._winner_user
    _sign_in = claim_shop.TestClaimShop._sign_in
    _open = claim_shop.TestClaimShop._open

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()

    def _login(self, user):
        self.authenticate(user.login, user.login)

    def _form(self, **values):
        return dict(
            {
                "name": "Portal Lantern",
                "description": "A lantern\nfor the night.",
                "value": "25,50",
                "quantity": "3",
                "mode": "physical",
                "instructions": "",
            },
            **values,
        )

    def _post(self, url, data, files=None, csrf=True):
        if csrf:
            data = dict(data, csrf_token=self._csrf(LIST))
        return self.url_open(
            url, data=data, files=files, allow_redirects=False
        )

    def _prizes(self, name=None):
        domain = [
            ("raffle_sponsor_id", "=", self.sponsor.id),
            ("raffle_event_ids", "!=", False),
        ]
        if name:
            domain.append(("name", "=", name))
        return (
            self.env["product.template"]
            .with_context(active_test=False)
            .search(domain)
        )

    @staticmethod
    def _jpeg(width, height):
        buffer = io.BytesIO()
        Image.new("RGB", (width, height), (30, 120, 60)).save(buffer, "JPEG")
        return buffer.getvalue()

    # Entry of /my

    def test_my_home_entry_only_for_open_sponsors(self):
        self._login(self.alice)
        self.assertIn('href="/my/raffle-prizes"', self.url_open("/my").text)
        self._login(self.bob)
        self.assertIn('href="/my/raffle-prizes"', self.url_open("/my").text)
        self._login(self.visitor)
        self.assertNotIn("/my/raffle-prizes", self.url_open("/my").text)
        self.assertEqual(self.url_open(LIST).status_code, 404)
        self.assertEqual(self.url_open(NEW).status_code, 404)
        self._login(self.alice)
        for change, undo in (
            (
                lambda: self.alice_registration.action_cancel(),
                lambda: self.alice_registration.action_confirm(),
            ),
            (
                lambda: setattr(
                    self.open_event, "raffle_sponsor_managed", False
                ),
                lambda: setattr(
                    self.open_event, "raffle_sponsor_managed", True
                ),
            ),
            (
                lambda: self.open_event.write(
                    {
                        "date_begin": fields.Datetime.now()
                        - timedelta(days=2),
                        "date_end": fields.Datetime.now() - timedelta(days=1),
                    }
                ),
                None,
            ),
        ):
            # Carol's registration keeps the event open for the other
            # company only.
            change()
            with self.subTest(change=change):
                page = self.url_open("/my").text
                self.assertNotIn("/my/raffle-prizes", page)
                self.assertEqual(self.url_open(LIST).status_code, 404)
            if undo:
                undo()

    # Event choice

    def test_single_event_is_preselected_and_two_events_are_chosen(self):
        self._login(self.alice)
        page = self.url_open(NEW).text
        tree = lxml_html.fromstring(page)
        hidden = tree.xpath("//form//input[@name='event_id']")
        self.assertEqual(hidden[0].get("type"), "hidden")
        self.assertEqual(hidden[0].get("value"), str(self.open_event.id))
        self.assertFalse(tree.xpath("//select[@name='event_id']"))
        for name in ("description", "instructions"):
            self.assertTrue(tree.xpath(f"//textarea[@name='{name}']"), name)
        self.assertIn("Open Fair", page)
        self._sponsor_registration(self.alice, self.second_event)
        page = self.url_open(f"{NEW}?event_id={self.second_event.id}").text
        tree = lxml_html.fromstring(page)
        options = tree.xpath("//select[@name='event_id']/option")
        self.assertEqual(
            [o.get("value") for o in options],
            ["", str(self.open_event.id), str(self.second_event.id)],
        )
        selected = [o.get("value") for o in options if o.get("selected")]
        self.assertEqual(selected, [str(self.second_event.id)])
        # The event of another company is not a choice.
        foreign = self._event("Foreign Fair", self.second_event.date_end)
        response = self._post(NEW, self._form(event_id=str(foreign.id)))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Choose the event of the prize.", response.text)
        response = self._post(
            NEW, self._form(event_id=str(self.second_event.id))
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            self._prizes("Portal Lantern").raffle_event_ids, self.second_event
        )

    # Create, edit, withdraw

    def test_create_edit_and_withdraw(self):
        self._login(self.alice)
        response = self._post(NEW, self._form())
        self.assertEqual(response.status_code, 303)
        location = urlsplit(response.headers["Location"])
        self.assertEqual(
            (location.path, location.query), (LIST, "message=created")
        )
        prize = self._prizes("Portal Lantern")
        self.assertEqual(len(prize), 1)
        self.assertEqual(prize.raffle_sponsor_state, "submitted")
        self.assertFalse(prize.active)
        self.assertEqual(prize.list_price, 25.5)
        self.assertEqual(prize.raffle_initial_qty, 3)
        self.assertEqual(prize.description_sale, "A lantern\nfor the night.")
        self.assertEqual(prize.raffle_attendance, "onsite")
        self.assertFalse(prize.raffle_virtual_prize)
        self.assertEqual(prize.raffle_event_ids, self.open_event)
        self.assertEqual(prize.raffle_sponsor_id, self.sponsor)
        notification = self._notifications(prize)
        self.assertEqual(notification.author_id, self.alice.partner_id)
        self.assertEqual(notification.partner_ids, self.manager.partner_id)
        page = self.url_open(f"{LIST}?message=created").text
        self.assertIn("your prize is submitted", page)
        self.assertIn("Portal Lantern", page)
        self.assertIn("Submitted", page)
        self.assertIn(f'href="/my/raffle-prizes/{prize.id}"', page)
        # Edit: a virtual prize with its instructions, escaped.
        form = self.url_open(f"/my/raffle-prizes/{prize.id}").text
        self.assertIn('value="Portal Lantern"', form)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(
                name="Portal Lantern Code",
                mode="virtual",
                instructions="Open <b>the</b> app & type the code.",
            ),
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.name, "Portal Lantern Code")
        self.assertTrue(prize.raffle_virtual_prize)
        self.assertEqual(prize.raffle_attendance, "both")
        self.assertIn(
            "&lt;b&gt;the&lt;/b&gt;", prize.raffle_virtual_instructions
        )
        self.assertNotIn("<b>", prize.raffle_virtual_instructions)
        # The managers hear that the submitted prize changed.
        changed = self._notifications(prize) - notification
        self.assertEqual(len(changed), 1)
        self.assertIn("changed the prize", str(changed.body))
        # Withdraw, after a confirmation page.
        page = self.url_open(f"/my/raffle-prizes/{prize.id}/withdraw").text
        self.assertIn("Withdraw the prize", page)
        # The page says what withdrawing does, not that it is done.
        self.assertIn("Withdrawing deletes the prize", page)
        self.assertNotIn("The prize is removed", page)
        response = self._post(f"/my/raffle-prizes/{prize.id}/withdraw", {})
        self.assertEqual(response.status_code, 303)
        self.assertFalse(prize.exists())

    def test_approved_prize_is_read_only(self):
        prize = self._submit(name="Approved Kettle")
        prize.action_raffle_sponsor_approve()
        self._login(self.alice)
        page = self.url_open(f"/my/raffle-prizes/{prize.id}").text
        self.assertIn("This prize is approved", page)
        self.assertNotIn("o_raffle_sponsor_form", page)
        listing = self.url_open(LIST).text
        self.assertIn("Approved", listing)
        self.assertIn("Token category", listing)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}", self._form(name="Changed")
        )
        self.assertEqual(response.status_code, 404)
        response = self._post(f"/my/raffle-prizes/{prize.id}/withdraw", {})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(prize.name, "Approved Kettle")

    # Company sharing

    def test_company_contacts_share_prizes_and_others_get_404(self):
        prize = self._submit(name="Shared Kite")
        self._login(self.bob)
        self.assertIn("Shared Kite", self.url_open(LIST).text)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}", self._form(name="Shared Kite 2")
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.name, "Shared Kite 2")
        self._login(self.carol)
        self.assertNotIn("Shared Kite", self.url_open(LIST).text)
        for url in (
            f"/my/raffle-prizes/{prize.id}",
            f"/my/raffle-prizes/{prize.id}/image",
            f"/my/raffle-prizes/{prize.id}/withdraw",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.url_open(url).status_code, 404)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}", self._form(name="Stolen")
        )
        self.assertEqual(response.status_code, 404)
        response = self._post(f"/my/raffle-prizes/{prize.id}/withdraw", {})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(prize.exists())
        self.assertEqual(prize.name, "Shared Kite 2")
        # Carol's own prize is the rival company's.
        response = self._post(NEW, self._form(name="Rival Drum"))
        self.assertEqual(response.status_code, 303)
        drum = (
            self.env["product.template"]
            .with_context(active_test=False)
            .search([("name", "=", "Rival Drum")])
        )
        self.assertEqual(drum.raffle_sponsor_id, self.rival)
        # A staff prize of another sponsor is no portal prize either.
        self.assertEqual(
            self.url_open(
                f"/my/raffle-prizes/{self.mug.product_tmpl_id.id}"
            ).status_code,
            404,
        )

    # Request tampering

    def test_injected_fields_are_ignored(self):
        self._login(self.alice)
        response = self._post(
            NEW,
            self._form(
                name="Injected Fan",
                raffle_band_id=str(self.band_b.id),
                raffle_sponsor_state="approved",
                raffle_sponsor_id=str(self.rival.id),
                sponsor_id=str(self.rival.id),
                sale_ok="0",
                is_published="1",
                website_published="1",
                active="1",
                raffle_member_sale_ok="1",
                raffle_closing_prize="1",
                event_id=str(self.second_event.id),
            ),
        )
        self.assertEqual(response.status_code, 303)
        prize = self._prizes("Injected Fan")
        self.assertEqual(prize.raffle_sponsor_state, "submitted")
        self.assertEqual(prize.raffle_band_id, self.band_a)
        self.assertEqual(prize.raffle_sponsor_id, self.sponsor)
        self.assertTrue(prize.sale_ok)
        self.assertFalse(prize.is_published)
        self.assertFalse(prize.active)
        self.assertFalse(prize.raffle_member_sale_ok)
        self.assertFalse(prize.raffle_closing_prize)
        # Alice sponsors one event: the event sent is ignored.
        self.assertEqual(prize.raffle_event_ids, self.open_event)

    def test_post_without_csrf_token_is_refused(self):
        self._login(self.alice)
        response = self._post(NEW, self._form(name="No Token"), csrf=False)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self._prizes("No Token"))
        prize = self._submit(name="Token Guard")
        response = self._post(
            f"/my/raffle-prizes/{prize.id}/withdraw",
            {"confirm": "1"},
            csrf=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(prize.exists())

    # Photo and errors

    def test_photo_is_resized_and_a_non_image_is_refused(self):
        self._login(self.alice)
        response = self._post(
            NEW,
            self._form(name="Photo Drum"),
            files={
                "photo": ("drum.jpg", self._jpeg(2500, 1000), "image/jpeg")
            },
        )
        self.assertEqual(response.status_code, 303)
        prize = self._prizes("Photo Drum")
        image = Image.open(io.BytesIO(base64.b64decode(prize.image_1920)))
        self.assertEqual(image.size, (1920, 768))
        thumb = self.url_open(f"/my/raffle-prizes/{prize.id}/image")
        self.assertEqual(thumb.status_code, 200)
        self.assertTrue(thumb.headers["Content-Type"].startswith("image/"))
        for name, data, mimetype in (
            ("notes.txt", b"plain text", "text/plain"),
            (
                "drawing.svg",
                b"<svg xmlns='http://www.w3.org/2000/svg'/>",
                "image/svg+xml",
            ),
        ):
            with self.subTest(name=name):
                response = self._post(
                    NEW,
                    self._form(name=f"Bad {name}"),
                    files={"photo": (name, data, mimetype)},
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("JPEG, PNG, GIF or WebP", response.text)
                self.assertFalse(self._prizes(f"Bad {name}"))

    def test_form_errors_are_summarized_and_linked(self):
        self._login(self.alice)
        response = self._post(
            NEW,
            {"name": "", "value": "a lot", "quantity": "0", "mode": "x"},
        )
        self.assertEqual(response.status_code, 400)
        tree = lxml_html.fromstring(response.text)
        summary = tree.xpath("//*[@id='o_raffle_sponsor_errors']")[0]
        self.assertEqual(summary.get("role"), "alert")
        self.assertEqual(summary.get("tabindex"), "-1")
        links = [a.get("href") for a in summary.xpath(".//a")]
        self.assertEqual(
            links,
            [
                "#o_raffle_sponsor_name",
                "#o_raffle_sponsor_value",
                "#o_raffle_sponsor_quantity",
                "#o_raffle_sponsor_mode",
            ],
        )
        self.assertIn("The form has 4 errors:", response.text)
        for field in ("name", "value", "quantity", "mode"):
            with self.subTest(field=field):
                node = tree.xpath(f"//*[@id='o_raffle_sponsor_{field}']")[0]
                self.assertEqual(node.get("aria-invalid"), "true")
                self.assertIn(
                    f"o_raffle_sponsor_{field}_error",
                    node.get("aria-describedby"),
                )
                self.assertTrue(
                    tree.xpath(f"//*[@id='o_raffle_sponsor_{field}_error']")
                )
        for field in ("name", "value", "quantity"):
            label = tree.xpath(f"//label[@for='o_raffle_sponsor_{field}']")
            self.assertTrue(label, field)
        self.assertEqual(
            tree.xpath("//input[@id='o_raffle_sponsor_name']")[0].get(
                "required"
            ),
            "required",
        )
        # The values typed are kept.
        self.assertEqual(
            tree.xpath("//input[@id='o_raffle_sponsor_value']")[0].get(
                "value"
            ),
            "a lot",
        )
        self.assertFalse(self._prizes())

    def test_text_limits_count_a_line_break_once(self):
        """A text the browser lets through maxlength, sent with CRLF line
        breaks, fits the limit of the server too."""
        self._login(self.alice)
        line = "x" * 199
        text = "\r\n".join([line] * 20)
        self.assertEqual(len(text.replace("\r\n", "\n")), 3999)
        self.assertGreater(len(text), 4000)
        response = self._post(
            NEW,
            self._form(
                name="Long Lantern",
                description=text,
                mode="virtual",
                instructions=text,
            ),
        )
        self.assertEqual(response.status_code, 303)
        prize = self._prizes("Long Lantern")
        self.assertEqual(prize.description_sale, "\n".join([line] * 20))
        self.assertNotIn("\r", prize.raffle_virtual_instructions)
        response = self._post(
            NEW, self._form(name="Too Long", description="x" * 4001)
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("The description is too long", response.text)

    def test_value_over_the_maximum_names_the_maximum(self):
        self._login(self.alice)
        response = self._post(
            NEW, self._form(name="Gold Lantern", value="2000000")
        )
        self.assertEqual(response.status_code, 400)
        tree = lxml_html.fromstring(response.text)
        error = " ".join(
            tree.xpath("//*[@id='o_raffle_sponsor_value_error']")[0].itertext()
        )
        self.assertIn("The value is too high", error)
        self.assertIn("1,000,000", error)
        self.assertNotIn("as a number such as", error)
        self.assertFalse(self._prizes("Gold Lantern"))
        response = self._post(
            NEW, self._form(name="Gold Lantern", value="1000000")
        )
        self.assertEqual(response.status_code, 303)

    # Availability

    def test_submitted_prize_is_absent_from_the_shops_until_approved(self):
        prize = self._submit(name="Hidden Globe")
        product = prize.with_context(active_test=False).product_variant_ids
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse.lot_stock_id, 3
        )
        draw = self._fair_draw("Gwen Globe")
        token = draw._claim_link_issue()
        # The shop of a visitor without a claim is searched for the prize:
        # its first page holds the other published products too. The link
        # of the product page tells the prize is listed.
        search = "/shop?search=Hidden+Globe"
        link = f"/shop/hidden-globe-{prize.id}"
        self._use_session()
        self.assertNotIn(link, self.url_open(search).text)
        self._open(token)
        self.assertNotIn(link, self.url_open("/shop").text)
        prize.action_raffle_sponsor_approve()
        self.assertIn(link, self.url_open("/shop").text)
        self._use_session()
        self.assertIn(link, self.url_open(search).text)

    def test_approved_prize_shows_the_units_given_without_winners(self):
        prize = self._submit(name="Given Kite")
        prize.action_raffle_sponsor_approve()
        self._submit(name="Waiting Kite")
        product = prize.product_variant_id
        self.env["stock.quant"]._update_available_quantity(
            product, self.warehouse.lot_stock_id, 3
        )
        handed = self._fair_draw("Kim Kite")
        handed._prize_claim(product)
        handed.action_prize_deliver()
        self._fair_draw("Lou Kite")._prize_claim(product)
        self._login(self.alice)
        response = self.url_open(LIST)
        page = lxml_html.fromstring(response.content)
        given = page.xpath("//dd[contains(@class, 'o_raffle_sponsor_given')]")
        # The approved prize only: one handed over, the reserved one is not
        # given yet.
        self.assertEqual([dd.text_content().strip() for dd in given], ["1"])
        self.assertIn("Units given", response.text)
        self.assertNotIn("Kim Kite", response.text)
        self.assertNotIn("kim.kite", response.text)

    def test_refused_prize_shows_its_reason_and_an_edit_resubmits(self):
        prize = self._submit(name="Refused Fan")
        prize._raffle_sponsor_refuse("The value looks too high.")
        self._login(self.alice)
        listing = self.url_open(LIST).text
        self.assertIn("Refused", listing)
        self.assertIn("The value looks too high.", listing)
        form = self.url_open(f"/my/raffle-prizes/{prize.id}").text
        self.assertIn("The organization refused this prize", form)
        self.assertIn("The value looks too high.", form)
        before = self._notifications(prize)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(name="Refused Fan", value="20"),
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.raffle_sponsor_state, "submitted")
        self.assertFalse(prize.raffle_sponsor_refusal_reason)
        self.assertEqual(len(self._notifications(prize) - before), 1)

    def test_pages_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["portal", "event_raffle_prize_sponsor"], ["fr_CA"], overwrite=True
        )
        self.env.ref("website.default_website").language_ids |= self.env.ref(
            "base.lang_fr_CA"
        )
        self.alice.lang = "fr_CA"
        self._login(self.alice)
        prefix = "/" + self.env.ref("base.lang_fr_CA").url_code
        home = self.url_open(f"{prefix}/my").text
        self.assertIn("Prix pour tirage", home)
        form = self.url_open(f"{prefix}{NEW}").text
        self.assertIn("Ajouter un prix", form)
        self.assertIn("Commanditaire", form)
        prize = self._submit(name="French Lamp")
        page = self.url_open(
            f"{prefix}/my/raffle-prizes/{prize.id}/withdraw"
        ).text
        self.assertIn("Retirer le prix le supprime", page)

    # Accessibility

    def test_axe_core_finds_no_wcag_violation(self):
        """axe-core, WCAG 2.0/2.1/2.2 A and AA rules plus "region", on the
        module's pages at 390 px and on a desktop width: the prize list,
        the form with one event and with two, and the form sent back with
        errors, whose summary must have the focus. The page must not
        scroll sideways, and the buttons, fields and choices are 48 px
        high at least."""
        code = self._axe_code("""
            const include = [".o_raffle_sponsor"];
            const touch = [
                ".o_raffle_sponsor .btn",
                ".o_raffle_sponsor .form-control",
                ".o_raffle_sponsor .form-select",
                ".o_raffle_sponsor .form-check",
            ];
            if ("__MODE__" === "errors") {
                // The form sent empty, in a frame of the page's size. The
                // frame's page is audited once it has started, as the
                // page itself is.
                const frame = document.createElement("iframe");
                frame.name = "o_axe_frame";
                frame.title = "form sent";
                frame.style.cssText =
                    "position:fixed;inset:0;width:100%;height:100%;" +
                    "border:0;z-index:9999;background:#fff";
                document.body.appendChild(frame);
                const form = document.querySelector(".o_raffle_sponsor_form");
                form.querySelector("[name=name]").value = "";
                form.target = "o_axe_frame";
                const loaded = new Promise((resolve) => {
                    frame.addEventListener("load", resolve, {once: true});
                });
                form.submit();
                await loaded;
                const win = frame.contentWindow;
                await raffleFrontendReady(win);
                const active = win.document.activeElement;
                if (!active || active.id !== "o_raffle_sponsor_errors") {
                    throw new Error("the error summary has not the focus");
                }
                await raffleAxeAudit(win, include, touch);
            } else {
                await raffleAxeAudit(window, include, touch);
            }
            """)
        prize = self._submit(name="Axe Lamp")
        prize._raffle_sponsor_refuse("Invented reason for the test.")
        approved = self._submit(name="Axe Clock")
        approved.action_raffle_sponsor_approve()
        pages = [
            (LIST, "page"),
            (NEW, "page"),
            (f"/my/raffle-prizes/{prize.id}", "page"),
            (f"/my/raffle-prizes/{approved.id}", "page"),
            (f"/my/raffle-prizes/{prize.id}/withdraw", "page"),
            (NEW, "errors"),
        ]
        for width in (390, 1280):
            self.browser_size = f"{width}x900"
            for url, mode in pages:
                with self.subTest(url=url, mode=mode, width=width):
                    self._axe_browse(
                        url,
                        code.replace("__MODE__", mode),
                        login=self.alice.login,
                    )
        self._sponsor_registration(self.alice, self.second_event)
        self.browser_size = "390x900"
        for mode in ("page", "errors"):
            with self.subTest(url=NEW, mode=mode, events=2):
                self._axe_browse(
                    NEW,
                    code.replace("__MODE__", mode),
                    login=self.alice.login,
                )
