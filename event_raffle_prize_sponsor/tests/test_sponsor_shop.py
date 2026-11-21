# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.event_raffle_prize_claim.tests import (
    test_claim_shop as claim_shop,
)

from . import test_sponsor_portal as sponsor_portal
from .common import SponsorDataMixin

NEW = sponsor_portal.NEW
SPONSORED = "event_raffle_prize_sponsor.public_category_sponsored"


@tagged("post_install", "-at_install")
class TestSponsorShop(SponsorDataMixin, HttpCase):
    """A sponsored prize in the shop: its description from the portal and
    the shop category of the sponsors."""

    _use_session = claim_shop.TestClaimShop._use_session
    _session = claim_shop.TestClaimShop._session
    _csrf = claim_shop.TestClaimShop._csrf
    _winner_user = claim_shop.TestClaimShop._winner_user
    _sign_in = claim_shop.TestClaimShop._sign_in
    _open = claim_shop.TestClaimShop._open
    _form = sponsor_portal.TestSponsorPortal._form
    _post = sponsor_portal.TestSponsorPortal._post
    _prizes = sponsor_portal.TestSponsorPortal._prizes

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()
        cls.category = cls.env.ref(SPONSORED)
        cls.other_category = cls.env["product.public.category"].create(
            {"name": "Lamps"}
        )

    def setUp(self):
        super().setUp()
        self._use_session()

    def _login(self, user):
        self._sign_in(user)

    def _approved(self, name, qty=2, **values):
        """A prize submitted by Alice, approved, with `qty` units."""
        prize = self._submit(name=name, **values)
        prize.action_raffle_sponsor_approve()
        if qty:
            self.env["stock.quant"]._update_available_quantity(
                prize.product_variant_id, self.warehouse.lot_stock_id, qty
            )
        return prize

    # Description

    def test_portal_description_fills_the_ecommerce_description(self):
        self._login(self.alice)
        text = "A <script>alert(1)</script> lantern\nfor the night.\n\nFun."
        response = self._post(NEW, self._form(description=text))
        self.assertEqual(response.status_code, 303)
        prize = self._prizes("Portal Lantern")
        # The sale description stays the plain text.
        self.assertEqual(prize.description_sale, text)
        html = str(prize.description_ecommerce)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertRegex(html, r"lantern<br ?/?>for the night\.")
        self.assertEqual(html.count("<p>"), 2)
        # Editing the description in the portal updates it.
        response = self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(description="A brighter lantern."),
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.description_sale, "A brighter lantern.")
        self.assertIn("A brighter lantern.", str(prize.description_ecommerce))
        self.assertNotIn("night", str(prize.description_ecommerce))
        # The organization rewrites it: the sponsor's next edit changes
        # the sale description only.
        prize.description_ecommerce = "<p>Chosen by the <b>team</b>.</p>"
        self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(description="A lantern, again."),
        )
        self.assertEqual(prize.description_sale, "A lantern, again.")
        self.assertIn("Chosen by the", str(prize.description_ecommerce))
        # Emptied by the organization: the portal fills it again.
        prize.description_ecommerce = False
        self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(description="A lantern, at last."),
        )
        self.assertIn("A lantern, at last.", str(prize.description_ecommerce))

    def test_backend_sale_description_keeps_the_portal_updating(self):
        """An organizer who corrects the sale description in the backend
        leaves the eCommerce description to the portal: the sponsor's
        next edit still reaches the product page."""
        self._login(self.alice)
        self._post(NEW, self._form(description="Desk lamp"))
        prize = self._prizes("Portal Lantern")
        self.assertIn("Desk lamp", str(prize.description_ecommerce))
        prize.with_context(lang="en_US").description_sale = "Desk lamp, red"
        self.assertIn("Desk lamp", str(prize.description_ecommerce))
        response = self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(description="Desk lamp, blue"),
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.description_sale, "Desk lamp, blue")
        self.assertIn("Desk lamp, blue", str(prize.description_ecommerce))

    def test_refused_prize_edit_updates_the_description(self):
        prize = self._submit(name="Refused Lamp")
        prize._raffle_sponsor_refuse("Too blurry")
        self._login(self.alice)
        response = self._post(
            f"/my/raffle-prizes/{prize.id}",
            self._form(name="Refused Lamp", description="Sharper photo."),
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(prize.raffle_sponsor_state, "submitted")
        self.assertIn("Sharper photo.", str(prize.description_ecommerce))

    def test_product_page_shows_the_description(self):
        prize = self._approved(
            "Page Lamp",
            description_sale="Warm light <b>x</b>\nfor the desk.",
        )
        url = prize.website_url
        page = self.url_open(url).text
        # A prize for tokens only: no add to cart, the description shown.
        self.assertIn("Prize only", page)
        self.assertRegex(
            page, r"Warm light &lt;b&gt;x&lt;/b&gt;<br ?/?>for the desk\."
        )
        # The winner of a claim, signed in, reads it on the same page.
        draw = self._fair_draw("Wanda Winner")
        response = self._open(draw._claim_link_issue())
        self.assertEqual(response.status_code, 303)
        page = self.url_open(url).text
        self.assertIn("o_raffle_claim_banner", page)
        self.assertRegex(
            page, r"Warm light &lt;b&gt;x&lt;/b&gt;<br ?/?>for the desk\."
        )

    # Shop category

    def test_approval_adds_the_prize_to_the_category(self):
        prize = self._submit(name="Category Lamp")
        prize.public_categ_ids = self.other_category
        self.assertNotIn(self.category, prize.public_categ_ids)
        prize.action_raffle_sponsor_approve()
        self.assertEqual(
            prize.public_categ_ids, self.category | self.other_category
        )
        # The sponsor removed: the prize leaves the category, and keeps
        # the other one.
        prize.raffle_sponsor_id = False
        self.assertEqual(prize.public_categ_ids, self.other_category)

    def test_refused_and_withdrawn_prizes_are_not_in_the_category(self):
        refused = self._submit(name="Refused Kite")
        refused._raffle_sponsor_refuse("Not for this event")
        self.assertFalse(refused.public_categ_ids)
        # An approved prize sent back to review leaves the category.
        approved = self._approved("Reviewed Kite")
        self.assertIn(self.category, approved.public_categ_ids)
        approved.write(approved._raffle_sponsor_availability_vals("refused"))
        self.assertNotIn(self.category, approved.public_categ_ids)
        withdrawn = self._submit(name="Withdrawn Kite")
        withdrawn._raffle_sponsor_portal_withdraw()
        self.assertFalse(withdrawn.exists())
        self.assertNotIn(
            "Withdrawn Kite", self.category.product_tmpl_ids.mapped("name")
        )

    def test_organization_prizes_never_enter_the_category(self):
        prize = self.env["product.template"].create(
            {
                "name": "Organization Mug",
                "type": "consu",
                "is_storable": True,
                "is_raffle_prize": True,
                "is_published": True,
                "list_price": 20.0,
            }
        )
        self.assertEqual(prize.raffle_sponsor_state, "approved")
        self.assertFalse(prize.public_categ_ids)
        prize.write({"raffle_sponsor_state": "approved", "list_price": 25})
        self.assertFalse(prize.public_categ_ids)
        # A sponsor set later on an approved prize puts it in.
        prize.raffle_sponsor_id = self.sponsor
        self.assertEqual(prize.public_categ_ids, self.category)

    def test_deleted_category_does_not_stop_the_approval(self):
        self.category.unlink()
        prize = self._submit(name="Orphan Lamp")
        prize.public_categ_ids = self.other_category
        prize.action_raffle_sponsor_approve()
        self.assertEqual(prize.raffle_sponsor_state, "approved")
        self.assertEqual(prize.public_categ_ids, self.other_category)
        prize.raffle_sponsor_id = False
        self.assertEqual(prize.public_categ_ids, self.other_category)

    def test_category_is_named_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle_prize_sponsor"], ["fr_CA"]
        )
        self.assertEqual(self.category.name, "Sponsored")
        self.assertEqual(
            self.category.with_context(lang="fr_CA").name, "Commandite"
        )

    def test_shop_lists_the_category_while_it_shows_a_prize(self):
        prize = self._approved("Listed Lamp")
        link = f"/shop/category/{self.env['ir.http']._slug(self.category)}"
        page = self.url_open("/shop").text
        self.assertIn(link, page)
        self.assertIn("Listed Lamp", self.url_open(link).text)
        # The sponsored shop closed: the prizes are hidden, and so is the
        # category; its page still answers, empty.
        self._set_shop_window(is_open=False)
        page = self.url_open("/shop").text
        self.assertNotIn(link, page)
        response = self.url_open(link)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Listed Lamp", response.text)
        # A published product of the category shows it again.
        self.env["product.template"].create(
            {
                "name": "Sponsor Sticker",
                "is_published": True,
                "public_categ_ids": [(6, 0, self.category.ids)],
            }
        )
        self.assertIn(link, self.url_open("/shop").text)
        # The winner of a claim sees the category of the allowed prize.
        self.env["product.template"].search(
            [("name", "=", "Sponsor Sticker")]
        ).is_published = False
        draw = self._fair_draw("Willa Winner")
        self._open(draw._claim_link_issue())
        self.assertIn(prize.name, self.url_open("/shop").text)
        self.assertIn(link, self.url_open("/shop").text)
