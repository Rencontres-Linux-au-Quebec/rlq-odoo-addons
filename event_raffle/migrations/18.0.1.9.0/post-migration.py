# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Give the raffles that predate the planned date the start of their
    event.

    Version 18.0.1.9.0 adds date_planned; the pre-migration creates its
    column empty, so the existing rows do not take the field default, the
    moment of the upgrade. A
    raffle that has an event and no planned date takes the event's
    date_begin; a raffle without an event, or whose event has no start,
    stays without a date, and a date already set is kept.

    The rows are written in SQL, outside the ORM: writing date_planned
    through the ORM would pre-fill the raffle lists of the event web app
    days, and past days keep the raffles they were given.
    """
    cr.execute("""
        UPDATE event_raffle raffle
           SET date_planned = event.date_begin
          FROM event_event event
         WHERE raffle.event_id = event.id
           AND raffle.date_planned IS NULL
           AND event.date_begin IS NOT NULL
        """)
    _logger.info(
        "event_raffle %s: planned date set from the event on %s raffles",
        version,
        cr.rowcount,
    )
