# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class EventRaffleParticipant(models.Model):
    _inherit = "event.raffle.participant"

    attendance_mode = fields.Selection(
        [("onsite", "On site"), ("virtual", "Virtual")],
        string="Attendance",
        compute="_compute_attendance_mode",
        help="On site when the registration is marked attended, which the "
        "check-in scan does. Every other participant, including one "
        "without a registration, is virtual.",
    )

    @api.depends("registration_id.state")
    def _compute_attendance_mode(self):
        for rec in self:
            attended = rec.registration_id.state == "done"
            rec.attendance_mode = "onsite" if attended else "virtual"

    def _prize_person_keys(self):
        """Keys that identify the person behind this participant.

        Two participants are the same person when their keys meet: the
        same record, the same contact, or the same email (its own or its
        contact's), compared without case.
        """
        self.ensure_one()
        keys = {("participant", self.id)}
        if self.partner_id:
            keys.add(("partner", self.partner_id.id))
        for email in (self.email, self.partner_id.email):
            if email and email.strip():
                keys.add(("email", email.strip().lower()))
        return keys

    def _prize_quota(self):
        """Number of prizes this participant may hold.

        The high quota of the raffle applies when the ticket of the
        registration is one of the raffle's high quota tickets.
        """
        self.ensure_one()
        raffle = self.raffle_id
        ticket = self.registration_id.event_ticket_id
        if ticket and ticket in raffle.high_quota_ticket_ids:
            return raffle.quota_high
        return raffle.quota_default

    def _prize_scope_raffles(self):
        """Raffles whose claims count toward the quota: those of the event."""
        raffle = self.raffle_id
        if not raffle.event_id:
            return raffle
        return self.env["event.raffle"].search(
            [("event_id", "=", raffle.event_id.id)]
        )

    def _prize_scope_participants(self):
        """Participants of the event's raffles who are the same person."""
        self.ensure_one()
        keys = self._prize_person_keys()
        candidates = self.search(
            [("raffle_id", "in", self._prize_scope_raffles().ids)]
        )
        return candidates.filtered(
            lambda p: p == self or p._prize_person_keys() & keys
        )

    def _prize_claim_counts(self):
        """Prizes held by the person behind each participant.

        Returns {participant id: count}. A claim counts while its state is
        one of event.raffle.draw._prize_holding_states(), in any raffle of
        the same event, whichever of the person's participants won it, and
        still when that participant is deleted (see
        event.raffle.draw._prize_claim_person_keys()).
        Participants of one raffle share the claims read here, so a whole
        raffle costs one search.
        """
        counts = {}
        claims_by_raffle = {}
        holding = self.env["event.raffle.draw"]._prize_holding_states()
        for rec in self:
            raffle = rec.raffle_id
            if raffle not in claims_by_raffle:
                claims_by_raffle[raffle] = [
                    claim._prize_claim_person_keys()
                    for claim in self.env["event.raffle.draw"].search(
                        [
                            (
                                "raffle_id",
                                "in",
                                rec._prize_scope_raffles().ids,
                            ),
                            ("claim_state", "in", holding),
                        ]
                    )
                ]
            keys = rec._prize_person_keys()
            counts[rec.id] = sum(
                1
                for claim_keys in claims_by_raffle[raffle]
                if claim_keys & keys
            )
        return counts

    def _prize_quota_reached(self):
        """Participants of `self` who already hold their quota of prizes."""
        counts = self._prize_claim_counts()
        return self.filtered(lambda p: counts[p.id] >= p._prize_quota())
