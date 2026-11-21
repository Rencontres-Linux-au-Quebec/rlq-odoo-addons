# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import etree

from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestEventRaffleTestFlag(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Soirée fictive",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        cls.prod_raffle = cls.env["event.raffle"].create(
            {"name": "Tirage réel", "event_id": cls.event.id}
        )
        cls.test_raffle = cls.env["event.raffle"].create(
            {
                "name": "Tirage répétition",
                "event_id": cls.event.id,
                "is_test": True,
            }
        )
        cls.raffles = cls.prod_raffle | cls.test_raffle

    def _filter_domain(self, model, filter_name):
        """Return the domain of the named filter of ``model``'s search view,
        as the web client reads it."""
        arch = self.env[model].get_view(view_type="search")["arch"]
        nodes = etree.fromstring(arch).xpath(
            f"//filter[@name='{filter_name}']"
        )
        self.assertEqual(len(nodes), 1, filter_name)
        return safe_eval(nodes[0].get("domain"))

    def _search_with_filter(self, model, filter_name, records):
        return self.env[model].search(
            [("id", "in", records.ids)]
            + self._filter_domain(model, filter_name)
        )

    def test_default_is_production(self):
        self.assertFalse(self.prod_raffle.is_test)

    def test_raffle_filters(self):
        self.assertEqual(
            self._search_with_filter(
                "event.raffle", "production", self.raffles
            ),
            self.prod_raffle,
        )
        self.assertEqual(
            self._search_with_filter("event.raffle", "test", self.raffles),
            self.test_raffle,
        )

    def test_filters_share_one_group(self):
        """Adjacent filters form one group, which the web client ORs: no
        separator may stand between Prod and Test."""
        arch = self.env["event.raffle"].get_view(view_type="search")["arch"]
        prod = etree.fromstring(arch).xpath("//filter[@name='production']")[0]
        self.assertEqual(prod.getnext().get("name"), "test")

    def test_menu_action_applies_prod_filter(self):
        action = self.env.ref("event_raffle.action_event_raffle")
        context = safe_eval(action.context)
        self.assertEqual(context.get("search_default_production"), 1)

    def test_event_button_applies_prod_filter(self):
        action = self.event.action_view_raffles()
        self.assertEqual(action["context"]["search_default_production"], 1)
        self.assertEqual(action["context"]["default_event_id"], self.event.id)

    def test_draw_filters_follow_raffle(self):
        draws = self.env["event.raffle.draw"].create(
            [
                {"raffle_id": self.prod_raffle.id, "winner_name": "Alice"},
                {"raffle_id": self.test_raffle.id, "winner_name": "Bob"},
            ]
        )
        self.assertEqual(draws.mapped("raffle_is_test"), [False, True])
        self.assertEqual(
            self._search_with_filter("event.raffle.draw", "production", draws),
            draws[0],
        )
        self.assertEqual(
            self._search_with_filter("event.raffle.draw", "test", draws),
            draws[1],
        )
        # The draw list action does not apply the filter by default.
        action = self.env.ref("event_raffle.action_event_raffle_draw")
        self.assertNotIn("search_default_production", action.context or "")

    def test_form_shows_ribbon_and_checkbox(self):
        arch = etree.fromstring(
            self.env["event.raffle"].get_view(view_type="form")["arch"]
        )
        ribbon = arch.xpath("//widget[@name='web_ribbon']")
        self.assertEqual(len(ribbon), 1)
        self.assertEqual(ribbon[0].get("invisible"), "not is_test")
        self.assertTrue(
            arch.xpath("//page[@name='settings']//field[@name='is_test']")
        )
        list_arch = etree.fromstring(
            self.env["event.raffle"].get_view(view_type="list")["arch"]
        )
        self.assertTrue(list_arch.xpath("//field[@name='is_test']"))
