# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, Command, api


def migrate(cr, version):
    """Approved sponsored prizes enter the shop category of the sponsors.

    The category is the noupdate record SPONSORED_CATEGORY, which the data
    of this version creates before this script runs. The prizes approved
    before, archived ones included, are added to it, as an approval adds
    them from this version on; their other categories are kept. Without
    the category, nothing is done.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Template = env["product.template"].with_context(active_test=False)
    category = Template._raffle_sponsored_category()
    if not category:
        return
    Template.search(
        [
            ("is_raffle_prize", "=", True),
            ("raffle_sponsor_id", "!=", False),
            ("raffle_sponsor_state", "=", "approved"),
        ]
    ).write({"public_categ_ids": [Command.link(category.id)]})
