# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


def migrate(cr, version):
    """Create the date_planned column empty before the module loads.

    Odoo fills a column it adds with the field default on every existing
    row; the default of date_planned is the current moment, which would
    date every existing raffle at the upgrade and leave nothing for the
    post-migration to set. A column that already exists is left as it is.
    """
    cr.execute(
        "ALTER TABLE event_raffle"
        " ADD COLUMN IF NOT EXISTS date_planned timestamp without time zone"
    )
