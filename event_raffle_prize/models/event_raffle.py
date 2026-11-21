# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EventRaffle(models.Model):
    """Prize quotas, and the token category and closing flag of the draws.

    `prize_band_id` is the token category of the raffle: each winner earns
    one token of it. The raffle form sets it, and the wheel reads it with
    `prize_closing_draw` from get_wheel_data() and writes them back when
    the operator changes them between two draws; action_draw_next() copies
    them on the draw it creates, under the raffle lock. Both stay set from
    one draw to the next. An archived category counts as no category: the
    wheel lists the active categories only, so the draw never gets a
    category its selector cannot show.
    """

    _inherit = "event.raffle"

    high_quota_ticket_ids = fields.Many2many(
        "event.event.ticket",
        "event_raffle_high_quota_ticket_rel",
        "raffle_id",
        "ticket_id",
        string="High Quota Tickets",
        domain="[('event_id', '=', event_id)]",
        help="Participants whose registration has one of these tickets may "
        "hold the high quota of prizes; the others the default quota.",
    )
    quota_default = fields.Integer(
        string="Default Quota",
        default=1,
        help="Number of prizes a person may hold over all the raffles of "
        "the event.",
    )
    quota_high = fields.Integer(
        string="High Quota",
        default=2,
        help="Number of prizes a person with a high quota ticket may hold "
        "over all the raffles of the event.",
    )
    prize_band_id = fields.Many2one(
        "event.raffle.prize.band",
        string="Token category of this raffle",
        help="Each winner of this raffle earns one token of this category: "
        "the next draw copies it, and its winner is offered the prizes "
        "of this category only. The wheel can change it between two "
        "draws.",
    )
    prize_closing_draw = fields.Boolean(
        string="Next Draw Is a Closing Draw",
        help="Copied on the next draw: a closing draw may give the closing "
        "prizes.",
    )

    @api.model
    def _prize_warehouse(self, company):
        """Warehouse whose stock the prizes of `company` come from.

        The default warehouse of the current user in that company, which is
        the one a sale order of that user ships from.
        """
        # sudo: an event user does not read the warehouses.
        return (
            self.env.user.sudo()
            .with_company(company)
            ._get_default_warehouse_id()
        )

    def _prize_held_draws(self):
        """Draws of these raffles whose claim holds a unit, as superuser.

        Their claim state is one of event.raffle.draw._prize_holding_states():
        reserved, handed over, or shipped with event_raffle_prize_handover.
        """
        Draw = self.env["event.raffle.draw"].sudo()
        if not self.ids:
            return Draw
        return Draw.search(
            [
                ("raffle_id", "in", self.ids),
                ("claim_state", "in", Draw._prize_holding_states()),
            ],
            order="raffle_id, sequence, id",
        )

    @api.model
    def _prize_held_draws_list(self, draws):
        """One line per draw of `draws`, its raffle and its name, for the
        message that refuses a deletion.

        The lines are translated with self.env._(): the frame of a generator
        expression holds no env, so the module `_` would find no language
        outside a web request and leave them untranslated.
        """
        return "\n".join(
            self.env._(
                "- %(raffle)s: %(draw)s",
                raffle=draw.raffle_id.display_name,
                draw=draw.display_name,
            )
            for draw in draws
        )

    @api.ondelete(at_uninstall=False)
    def _unlink_except_held_prize(self):
        """Keep the raffles whose draws hold a prize.

        The database deletes the draws of a deleted raffle (ondelete
        cascade on event.raffle.draw.raffle_id), past the delete guards of
        the draw: the draws that hold a unit are checked here instead.
        """
        held = self._prize_held_draws()
        if held:
            raise UserError(
                _(
                    "A raffle whose draws hold a prize cannot be deleted. "
                    "Decline the reserved prizes first; a draw whose prize "
                    "was handed over or shipped keeps its raffle.\n%s",
                    self._prize_held_draws_list(held),
                )
            )

    def _eligible_participants(self):
        eligible = super()._eligible_participants()
        return eligible - eligible._prize_quota_reached()

    def _prize_next_band(self):
        """Token category of the next draw: the raffle's one while it is
        active."""
        self.ensure_one()
        return self.prize_band_id.filtered("active")

    def get_wheel_data(self):
        data = super().get_wheel_data()
        bands = self.env["event.raffle.prize.band"].search([])
        data.update(
            {
                "prize_bands": [{"id": b.id, "name": b.name} for b in bands],
                "prize_band_id": self._prize_next_band().id,
                "prize_closing_draw": self.prize_closing_draw,
            }
        )
        return data

    def _draw_next_values(self, winner, sequence, prize, prize_description):
        values = super()._draw_next_values(
            winner, sequence, prize, prize_description
        )
        values.update(
            {
                "band_id": self._prize_next_band().id,
                "is_closing_draw": self.prize_closing_draw,
            }
        )
        return values
