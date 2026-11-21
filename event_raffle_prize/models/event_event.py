# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, models
from odoo.exceptions import UserError


class EventEvent(models.Model):
    _inherit = "event.event"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_held_raffle_prize(self):
        """Keep the events whose raffle draws hold a prize.

        The database deletes the raffles of a deleted event (ondelete
        cascade on event.raffle.event_id), and their draws with them, past
        the delete guards of both models: the draws that hold a unit are
        checked here instead (see event.raffle._prize_held_draws()).
        """
        Raffle = self.env["event.raffle"].sudo()
        raffles = Raffle.search([("event_id", "in", self.ids)])
        held = raffles._prize_held_draws()
        if held:
            raise UserError(
                _(
                    "An event whose raffle draws hold a prize cannot be "
                    "deleted. Decline the reserved prizes first; a draw "
                    "whose prize was handed over or shipped keeps its "
                    "event.\n%s",
                    Raffle._prize_held_draws_list(held),
                )
            )
