# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import etree

from odoo import fields
from odoo.modules.migration import load_script
from odoo.tests.common import TransactionCase


class TestEventRafflePlannedDate(TransactionCase):
    def test_planned_date_is_optional_and_not_copied(self):
        raffle = self.env["event.raffle"].create(
            {"name": "Tirage fictif", "date_planned": "2031-06-10 17:00:00"}
        )
        self.assertEqual(
            raffle.date_planned,
            fields.Datetime.to_datetime("2031-06-10 17:00:00"),
        )
        self.assertFalse(raffle.copy().date_planned)
        self.assertFalse(
            self.env["event.raffle"].create({"name": "Sans date"}).date_planned
        )

    def test_planned_date_is_on_the_form_and_the_list(self):
        Raffle = self.env["event.raffle"]
        for view_type in ("form", "list"):
            with self.subTest(view=view_type):
                arch = etree.fromstring(
                    Raffle.get_view(view_type=view_type)["arch"]
                )
                self.assertTrue(arch.xpath("//field[@name='date_planned']"))


class TestEventRafflePlannedDateMigration(TransactionCase):
    """migrations/18.0.1.9.0: the raffles of an upgraded database take the
    start of their event as planned date."""

    def _migrate(self):
        script = load_script(
            "event_raffle/migrations/18.0.1.9.0/post-migration.py",
            "event_raffle_post_migration_18_0_1_9_0",
        )
        script.migrate(self.env.cr, "18.0.1.8.0")
        self.env["event.raffle"].invalidate_model(["date_planned"])

    def test_raffles_take_the_start_of_their_event(self):
        event = self.env["event.event"].create(
            {
                "name": "Journée fictive",
                "date_begin": "2031-06-10 13:00:00",
                "date_end": "2031-06-10 21:00:00",
            }
        )
        Raffle = self.env["event.raffle"]
        past = Raffle.create({"name": "Tirage passé", "event_id": event.id})
        dated = Raffle.create(
            {
                "name": "Tirage daté",
                "event_id": event.id,
                "date_planned": "2031-06-10 17:00:00",
            }
        )
        alone = Raffle.create({"name": "Tirage sans événement"})
        # The column of an upgraded database is empty on every old row.
        self.env.cr.execute(
            "UPDATE event_raffle SET date_planned = NULL WHERE id = %s",
            [past.id],
        )
        self._migrate()
        self.assertEqual(
            past.date_planned,
            fields.Datetime.to_datetime("2031-06-10 13:00:00"),
        )
        self.assertEqual(
            dated.date_planned,
            fields.Datetime.to_datetime("2031-06-10 17:00:00"),
        )
        self.assertFalse(alone.date_planned)
