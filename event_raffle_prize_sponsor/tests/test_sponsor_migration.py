# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.modules.migration import load_script
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import SponsorDataMixin

SPONSORED = "event_raffle_prize_sponsor.public_category_sponsored"


@tagged("post_install", "-at_install")
class TestSponsorMigration(SponsorDataMixin, TransactionCase):
    """Upgrades of the sponsored prizes saved by an earlier version."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()
        cls.category = cls.env.ref(SPONSORED)

    def _migrate(self, version, previous):
        script = load_script(
            f"event_raffle_prize_sponsor/migrations/{version}/"
            "post-migration.py",
            f"event_raffle_prize_sponsor_post_migration_{version}",
        )
        script.migrate(self.env.cr, previous)
        self.env.invalidate_all()

    def _sql(self, query, params):
        self.env.flush_all()
        self.env.cr.execute(query, params)
        self.env.invalidate_all()

    def test_sponsored_prizes_get_an_ecommerce_description(self):
        old = self._submit(
            name="Old Lamp", description_sale="Bright <i>lamp</i>\nfor all."
        )
        edited = self._submit(name="Edited Lamp")
        archived = self._approved_then_archived("Archived Lamp")
        organization = self.env["product.template"].create(
            {"name": "Team Lamp", "description_sale": "Ours."}
        )
        # As saved before this version: no eCommerce description.
        self._sql(
            "UPDATE product_template SET description_ecommerce = NULL"
            " WHERE id IN %s",
            [(old.id, archived.id, organization.id)],
        )
        edited.description_ecommerce = "<p>Written by the team.</p>"
        self._migrate("18.0.1.1.0", "18.0.1.0.0")
        html = str(old.description_ecommerce)
        self.assertRegex(
            html, r"Bright &lt;i&gt;lamp&lt;/i&gt;<br ?/?>for all\."
        )
        self.assertIn(
            "A lamp for the desk.", str(archived.description_ecommerce)
        )
        self.assertEqual(
            str(edited.description_ecommerce), "<p>Written by the team.</p>"
        )
        self.assertFalse(organization.description_ecommerce)
        # A new database runs no migration.
        self._sql(
            "UPDATE product_template SET description_ecommerce = NULL"
            " WHERE id = %s",
            [old.id],
        )
        self._migrate("18.0.1.1.0", None)
        self.assertFalse(old.description_ecommerce)

    def test_approved_sponsored_prizes_enter_the_category(self):
        approved = self._submit(name="Old Kite")
        approved.action_raffle_sponsor_approve()
        archived = self._approved_then_archived("Archived Kite")
        submitted = self._submit(name="Waiting Kite")
        organization = self.env["product.template"].create(
            {
                "name": "Team Kite",
                "type": "consu",
                "is_storable": True,
                "is_raffle_prize": True,
            }
        )
        other = self.env["product.public.category"].create({"name": "Kites"})
        approved.public_categ_ids = other
        # As saved before this version: in no sponsored category.
        self._sql(
            "DELETE FROM product_public_category_product_template_rel"
            " WHERE product_public_category_id = %s",
            [self.category.id],
        )
        self.assertFalse(self.category.product_tmpl_ids)
        self._migrate("18.0.1.2.0", "18.0.1.1.0")
        self.assertEqual(approved.public_categ_ids, other | self.category)
        self.assertEqual(archived.public_categ_ids, self.category)
        self.assertFalse(submitted.public_categ_ids)
        self.assertFalse(organization.public_categ_ids)
        # Without the category, the upgrade does nothing.
        self.category.unlink()
        self._migrate("18.0.1.2.0", "18.0.1.1.0")
        self.assertEqual(approved.public_categ_ids, other)

    def test_portal_descriptions_stay_the_portal_s(self):
        kept = self._submit(name="Kept Lamp", description_sale="Kept.")
        edited = self._submit(name="Edited Lamp", description_sale="Mine.")
        edited.description_ecommerce = "<p>Written by the team.</p>"
        empty = self._submit(name="Empty Lamp", description_sale="Empty.")
        empty.description_ecommerce = False
        # As saved before this version: no copy of the portal's version.
        self._sql(
            "UPDATE product_template"
            " SET raffle_sponsor_ecommerce_portal = NULL WHERE id IN %s",
            [(kept.id, edited.id, empty.id)],
        )
        self._migrate("18.0.1.3.0", "18.0.1.2.0")
        self.assertTrue(kept.raffle_sponsor_ecommerce_portal)
        self.assertFalse(edited.raffle_sponsor_ecommerce_portal)
        self.assertFalse(empty.raffle_sponsor_ecommerce_portal)
        # A backend fix of the sale description changes nothing: the
        # portal still owns the description it wrote.
        kept.with_context(lang="en_US").description_sale = "Kept, fixed."
        for prize, text in ((kept, "Kept, again."), (edited, "Mine too.")):
            prize._raffle_sponsor_portal_write(
                self.open_event, {"description_sale": text}
            )
        self.assertIn("Kept, again.", str(kept.description_ecommerce))
        self.assertEqual(
            str(edited.description_ecommerce), "<p>Written by the team.</p>"
        )
        # A new database runs no migration.
        self._sql(
            "UPDATE product_template"
            " SET raffle_sponsor_ecommerce_portal = NULL WHERE id = %s",
            [kept.id],
        )
        self._migrate("18.0.1.3.0", None)
        self.assertFalse(kept.raffle_sponsor_ecommerce_portal)

    def _approved_then_archived(self, name):
        """A prize approved, then archived by an event manager."""
        prize = self._submit(name=name)
        prize.action_raffle_sponsor_approve()
        prize.active = False
        return prize
