# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.tests import HttpCase, tagged

from .common import ClaimDataMixin


@tagged("post_install", "-at_install")
class TestShopProductPage(ClaimDataMixin, HttpCase):
    """The product page of a prize, in a browser."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._claim_setup()
        cls.mug = cls._prize("Page Mug", price=20.0, qty=2)

    def test_token_only_prize_page_runs_its_scripts(self):
        """A prize for tokens only has no add to cart. The page keeps an
        empty call-to-action wrapper: website_sale_stock's variant script
        reads it on load and fails with an uncaught error when it is
        missing, which fails the tour."""
        self.start_tour(
            self.mug.product_tmpl_id.website_url,
            "event_raffle_prize_claim_token_only_page",
        )
