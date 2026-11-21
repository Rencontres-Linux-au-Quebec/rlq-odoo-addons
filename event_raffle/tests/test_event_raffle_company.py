# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestRaffleCompany(TransactionCase):
    """A raffle, its participants, draws and notifications belong to the
    raffle's company: a user reads them in the companies they work in.

    Post-install: a company created while event_raffle installs misses
    the columns that later modules add to res.company as NOT NULL.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create(
            {"name": "Raffle Company B"}
        )
        cls.user_a = new_test_user(
            cls.env,
            login="raffle_company_user_a",
            groups="base.group_user,event.group_event_user",
            company_id=cls.company_a.id,
            company_ids=[cls.company_a.id],
            name="Company A User",
        )
        cls.raffle_b = cls.env["event.raffle"].create(
            {"name": "Raffle B", "company_id": cls.company_b.id}
        )
        cls.shared = cls.env["event.raffle"].create(
            {"name": "Shared Raffle", "company_id": False}
        )
        cls.participant_b = cls.env["event.raffle.participant"].create(
            {"raffle_id": cls.raffle_b.id, "name": "Bea"}
        )
        cls.draw_b = cls.env["event.raffle.draw"].create(
            {
                "raffle_id": cls.raffle_b.id,
                "winner_participant_id": cls.participant_b.id,
                "winner_name": "Bea",
            }
        )
        cls.notification_b = cls.env["event.raffle.draw.notification"].create(
            {
                "draw_id": cls.draw_b.id,
                "author_id": cls.env.ref("base.partner_root").id,
                "channel": "email",
                "recipient": "bea@example.com",
            }
        )

    def test_the_records_of_another_company_are_out_of_reach(self):
        Raffle = self.env["event.raffle"].with_user(self.user_a)
        raffles = Raffle.search([])
        self.assertNotIn(self.raffle_b, raffles)
        self.assertIn(self.shared, raffles)
        for record in (
            self.raffle_b,
            self.participant_b,
            self.draw_b,
            self.notification_b,
        ):
            self.assertFalse(
                record.with_user(self.user_a).search([("id", "=", record.id)]),
                record._name,
            )
            with self.assertRaises(AccessError, msg=record._name):
                record.with_user(self.user_a).check_access("read")

    def test_a_user_of_both_companies_reads_them(self):
        self.user_a.company_ids = self.company_a | self.company_b
        env = self.env(
            user=self.user_a,
            context={"allowed_company_ids": [self.company_b.id]},
        )
        self.assertEqual(
            env["event.raffle.draw"].search([("id", "=", self.draw_b.id)]),
            self.draw_b,
        )
