# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class EventRaffleParticipant(models.Model):
    _inherit = "event.raffle.participant"

    # Uninstalling the module turns these participants into guests rather
    # than deleting them, so the draws that name them stay intact.
    source = fields.Selection(
        selection_add=[("survey", "Survey")],
        ondelete={"survey": "set default"},
    )
