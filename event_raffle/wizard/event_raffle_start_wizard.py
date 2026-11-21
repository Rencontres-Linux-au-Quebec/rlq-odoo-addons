# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models
from odoo.exceptions import UserError

# Only the question types that ask something count as "questionnaire
# filled". The identification types (Name, Email, Phone, Company) say who the
# attendee is, and Odoo copies their answers onto the registration itself; it
# puts the first three on every event by default and the registration form
# answers them on its own. An answer to one of them proves nothing about the
# questionnaire.
QUESTIONNAIRE_QUESTION_TYPES = ("simple_choice", "text_box")


class EventRaffleStartWizard(models.TransientModel):
    _name = "event.raffle.start.wizard"
    _description = "Start a Raffle from an Event"

    event_id = fields.Many2one(
        "event.event",
        string="Event",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    name = fields.Char(string="Raffle Name")
    copy_strategy = fields.Selection(
        [
            ("present_only", "Present only (attended)"),
            ("registered_and_present", "Registered and present"),
            ("question_only", "Questionnaire filled only"),
            ("question_and_present", "Questionnaire filled and present"),
        ],
        string="Participants",
        default="present_only",
        required=True,
        help="Who enters the raffle. Both 'Questionnaire' choices keep only "
        "the attendees who answered the event's registration "
        "questionnaire.",
    )
    context_note = fields.Text(string="Context")
    remove_winner = fields.Boolean(string="Remove Winner", default=True)

    def _registration_domain_states(self):
        self.ensure_one()
        if self.copy_strategy in ("present_only", "question_and_present"):
            return ["done"]
        return ["open", "done"]

    def _requires_questionnaire(self):
        self.ensure_one()
        return self.copy_strategy in ("question_only", "question_and_present")

    def _questionnaire_questions(self):
        """The event's questionnaire questions, identity fields excluded."""
        self.ensure_one()
        return self.event_id.question_ids.filtered(
            lambda q: q.question_type in QUESTIONNAIRE_QUESTION_TYPES
        )

    def _filter_questionnaire_answered(self, regs):
        """Keep the registrations carrying at least one questionnaire answer.

        One query for the whole set, and the order of `regs` is preserved so
        the de-duplication in _copy_participants keeps behaving the same way.
        """
        self.ensure_one()
        questions = self._questionnaire_questions()
        if not questions:
            raise UserError(
                _(
                    "The event '%s' has no questionnaire question: no attendee "
                    "can have filled in the questionnaire. Add a question of "
                    "type Selection or Text Input, or choose another type "
                    "of participants."
                )
                % self.event_id.name
            )
        answers = self.env["event.registration.answer"].search(
            [
                ("registration_id", "in", regs.ids),
                ("question_id", "in", questions.ids),
            ]
        )
        answered_ids = set(answers.registration_id.ids)
        return regs.filtered(lambda r: r.id in answered_ids)

    def _participant_key(self, partner, email, name, fallback):
        """Key under which one person enters the raffle only once.

        A contact identifies a person before an email, and an email before a
        name; the email and the name match whatever their case and outer
        spaces. A row carrying none of the three gets `fallback`, a key of its
        own, so blank guests are never merged.
        """
        email = (email or "").strip().lower()
        name = (name or "").strip().lower()
        if partner:
            return ("p", partner.id)
        if email:
            return ("e", email)
        if name:
            return ("n", name)
        return fallback

    def _copy_participants(self, raffle):
        self.ensure_one()
        states = self._registration_domain_states()
        regs = self.event_id.registration_ids.filtered(
            lambda r: r.state in states
        )
        if self._requires_questionnaire():
            regs = self._filter_questionnaire_answered(regs)
        seen = set()
        Participant = self.env["event.raffle.participant"]
        participant_vals = []
        for reg in regs:
            key = self._participant_key(
                reg.partner_id, reg.email, reg.name, ("i", reg.id)
            )
            if key in seen:
                continue
            seen.add(key)
            participant_vals.append(
                {
                    "raffle_id": raffle.id,
                    "name": reg.name
                    or (reg.partner_id.name if reg.partner_id else _("Guest")),
                    "email": reg.email
                    or (reg.partner_id.email if reg.partner_id else False),
                    "partner_id": reg.partner_id.id or False,
                    "registration_id": reg.id,
                    "source": "registration",
                }
            )
        if participant_vals:
            Participant.create(participant_vals)

    def action_start(self):
        self.ensure_one()
        raffle = self.env["event.raffle"].create(
            {
                "name": self.name or _("Raffle - %s") % self.event_id.name,
                "event_id": self.event_id.id,
                "context_note": self.context_note or False,
                "remove_winner": self.remove_winner,
            }
        )
        self._copy_participants(raffle)
        return {
            "type": "ir.actions.act_window",
            "name": _("Raffle"),
            "res_model": "event.raffle",
            "res_id": raffle.id,
            "view_mode": "form",
            "target": "current",
        }
