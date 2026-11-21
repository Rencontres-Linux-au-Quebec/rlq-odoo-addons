# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, models


class EventEvent(models.Model):
    _inherit = "event.event"

    @api.ondelete(at_uninstall=False)
    def _unlink_cancel_claim_carts(self):
        """The raffles of a deleted event, and their draws, go with it in
        the database, past their own delete hooks: their claim carts are
        cancelled here, else each one would turn into an ordinary cart
        that still holds its free prize."""
        raffles = (
            self.env["event.raffle"]
            .sudo()
            .search([("event_id", "in", self.ids)])
        )
        raffles._unlink_cancel_claim_carts()
