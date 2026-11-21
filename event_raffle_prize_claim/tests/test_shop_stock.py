# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import html as lxml_html

import odoo
from odoo.tests import tagged
from odoo.tests.common import HttpCase

from odoo.addons.website.tests.test_performance import UtilPerf

from . import test_claim_shop as claim_shop
from .common import ClaimDataMixin

SEARCH = "/shop?search=Stock"


@tagged("post_install", "-at_install")
class TestShopStock(ClaimDataMixin, HttpCase):
    """The remaining quantity on the shop cards."""

    _use_session = claim_shop.TestClaimShop._use_session
    _session = claim_shop.TestClaimShop._session
    _get_url_hot_query = UtilPerf._get_url_hot_query

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._claim_setup()
        cls.mug = cls._prize("Stock Mug", qty=3)
        cls.pen = cls._prize("Stock Pen", qty=1)
        cls.empty = cls._prize("Stock Empty", qty=0)
        cls.book = cls._product("Stock Book", qty=2)
        cls.backorder = cls._product("Stock Backorder", qty=0)
        cls.sold_out = cls._product(
            "Stock Sold Out", qty=0, allow_out_of_stock_order=False
        )
        cls.service = cls._product("Stock Service", type="service")
        cls.consumable = cls._product("Stock Consumable", is_storable=False)
        color = cls.env["product.attribute"].create(
            {
                "name": "Stock Color",
                "value_ids": [
                    (0, 0, {"name": "Red"}),
                    (0, 0, {"name": "Blue"}),
                ],
            }
        )
        cls.shirt = cls.env["product.template"].create(
            {
                "name": "Stock Shirt",
                "type": "consu",
                "is_storable": True,
                "list_price": 15.0,
                "is_published": True,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": color.id,
                            "value_ids": [(6, 0, color.value_ids.ids)],
                        },
                    )
                ],
            }
        )
        for product, qty in zip(
            cls.shirt.product_variant_ids, (2, 3), strict=True
        ):
            cls.env["stock.quant"]._update_available_quantity(
                product, cls.warehouse.lot_stock_id, qty
            )

    @classmethod
    def _product(cls, name, qty=0, **vals):
        """A published product of the shop, storable unless `vals` says
        otherwise, with `qty` units at the warehouse."""
        template = cls.env["product.template"].create(
            dict(
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                    "list_price": 10.0,
                    "is_published": True,
                },
                **vals,
            )
        )
        if qty:
            cls.env["stock.quant"]._update_available_quantity(
                template.product_variant_id, cls.warehouse.lot_stock_id, qty
            )
        return template

    def setUp(self):
        super().setUp()
        self._use_session()

    def _cards(self, url=SEARCH):
        """The remaining quantity of each card of `url`, by product name:
        the text of its stock line, or None without one."""
        tree = lxml_html.fromstring(self.url_open(url).text)
        cards = {}
        for card in tree.xpath("//form[hasclass('oe_product_cart')]"):
            name = card.xpath(".//*[@itemprop='name']")[0].text_content()
            stock = card.xpath(".//*[hasclass('o_raffle_shop_stock')]")
            cards[name.strip()] = (
                stock[0].text_content().strip() if stock else None
            )
        return cards

    def test_cards_give_the_remaining_quantity(self):
        expected = {
            "Stock Mug": "3 left",
            "Stock Pen": "1 left",
            "Stock Empty": "Out of stock",
            "Stock Book": "2 left",
            "Stock Sold Out": "Out of stock",
            # Sold beyond its stock: says nothing, as its product page.
            "Stock Backorder": None,
            # Not storable: no stock to tell.
            "Stock Service": None,
            "Stock Consumable": None,
            # The sum of its variants, 2 and 3.
            "Stock Shirt": "5 left",
        }
        for layout in ("grid", "list"):
            session = self._session()
            session["website_sale_shop_layout_mode"] = layout
            odoo.http.root.session_store.save(session)
            with self.subTest(layout=layout):
                self.assertEqual(self._cards(), expected)
        # The sold out line is told in bold text, not by colour only.
        html = self.url_open(SEARCH).text
        self.assertIn("o_raffle_shop_stock_out fw-bold", html)

    def test_prize_reserved_by_a_claim_shows_one_less(self):
        winner = self._participant("Stock Winner")
        self._draw(winner)._prize_claim(self.mug)
        self.assertEqual(self._cards()["Stock Mug"], "2 left")
        other = self._participant("Stock Other")
        self._draw(other)._prize_claim(self.pen)
        self.assertEqual(self._cards()["Stock Pen"], "Out of stock")

    def test_prizes_count_the_prize_warehouse(self):
        """With a website warehouse that holds none of the stock, a prize
        still counts the free quantity of the prize warehouse, a claim
        included, while an ordinary product counts the website's."""
        website = self.env.ref("website.default_website")
        website.warehouse_id = self.env["stock.warehouse"].create(
            {"name": "Stock Shop Warehouse", "code": "SSHW"}
        )
        self.assertEqual(
            self.env["event.raffle"]._prize_warehouse(self.env.company),
            self.warehouse,
        )
        # Not sold beyond its stock, so its card tells it is sold out.
        self.book.allow_out_of_stock_order = False
        cards = self._cards()
        self.assertEqual(cards["Stock Mug"], "3 left")
        self.assertEqual(cards["Stock Book"], "Out of stock")
        self._draw(self._participant("Stock Winner"))._prize_claim(self.mug)
        self.assertEqual(self._cards()["Stock Mug"], "2 left")

    def test_labels_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        website = self.env["website"].with_context(lang="fr_CA")
        self.assertEqual(website._raffle_shop_stock_label(3), "3 restants")
        self.assertEqual(website._raffle_shop_stock_label(1), "1 restant")
        self.assertEqual(website._raffle_shop_stock_label(0), "Épuisé")
        self.assertEqual(
            website._raffle_shop_stock_label(2.5), "2,50 restants"
        )

    def test_queries_do_not_grow_with_the_products(self):
        """The remaining quantities of a page are computed with the same
        queries for one product of each kind (ordinary, prize, with
        variants) as for several of each."""
        website = self.env.ref("website.default_website")
        bulk = self.env["product.template"]
        for i in range(6):
            bulk |= self._product(f"Stock Bulk {i}", qty=i + 1)
        prizes = (self.mug | self.pen | self.empty).product_tmpl_id
        few = bulk[:1] | prizes[:1] | self.shirt
        many = bulk | prizes | self.shirt
        # The first call fills the registry caches (warehouse, xml ids).
        website._raffle_shop_stock(few)
        counts = {}
        for label, page in (("few", few), ("many", many)):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            stock = website._raffle_shop_stock(page)
            counts[label] = self.env.cr.sql_log_count - before
            self.assertEqual(len(stock), len(page))
        self.assertEqual(counts["few"], counts["many"], counts)

    def test_page_queries_do_not_grow_with_the_stock_lines(self):
        """On the shop page, going from one product to six costs no more
        queries with the stock lines than without them: the lines add a
        fixed cost, and warm the free quantities that website_sale_stock
        reads for each card."""
        view = self.env.ref("event_raffle_prize_claim.products_item_stock")
        for i in range(6):
            self._product(f"Stock Bulk {i}", qty=i + 1)
        growth = {}
        for active in (True, False):
            view.active = active
            one = self._get_url_hot_query("/shop?search=Stock+Bulk+0")
            many = self._get_url_hot_query("/shop?search=Stock+Bulk")
            growth[active] = many - one
        view.active = True
        self.assertEqual(len(self._cards("/shop?search=Stock+Bulk")), 6)
        self.assertLessEqual(growth[True], growth[False], growth)
