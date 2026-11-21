# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import email_normalize

# The survey groups read the answers of these survey types only, which the
# survey module's own record rules call the non-specialised surveys. A
# specialised survey, such as a recruitment one, keeps its answers to its own
# application, and a raffle drawn from it would come out empty without a word.
NON_SPECIALISED_SURVEY_TYPES = [
    "survey",
    "live_session",
    "assessment",
    "custom",
]


class EventRaffleStartWizard(models.TransientModel):
    _inherit = "event.raffle.start.wizard"

    copy_strategy = fields.Selection(
        selection_add=[("survey_only", "Survey filled only")],
        ondelete={"survey_only": "set default"},
    )
    survey_id = fields.Many2one(
        "survey.survey",
        string="Survey",
        domain=[("survey_type", "in", NON_SPECIALISED_SURVEY_TYPES)],
        help="Its respondents enter the raffle instead of the registrations: "
        "every completed answer that is not a test and answers at least one "
        "question.",
    )
    survey_question_ids = fields.Many2many(
        "survey.question",
        string="Required Questions",
        domain="[('survey_id', '=', survey_id), ('is_page', '=', False)]",
        help="Optional. When the list holds questions, only the respondents "
        "who answered them enter the raffle: each of them, or at least one, "
        "as Answered says.",
    )
    survey_question_match = fields.Selection(
        [("all", "Each"), ("any", "At least one")],
        string="Answered",
        default="all",
        required=True,
        help="Which of the required questions a respondent must have "
        "answered: each of them, or at least one.",
    )
    survey_respondent_count = fields.Integer(
        string="Respondents Entering",
        compute="_compute_survey_counts",
        help="How many people Start puts in the raffle, with the choices "
        "made above.",
    )
    survey_anonymous_count = fields.Integer(
        string="Anonymous Among Them",
        compute="_compute_survey_counts",
        help="Respondents with no contact, email or nickname: each enters as "
        "a separate Guest, and a guest who wins cannot be identified.",
    )

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        # A user who may not read survey answers could only end the survey
        # strategy on an access error: the choice is left out for them.
        res = super().fields_get(allfields, attributes)
        strategy = res.get("copy_strategy")
        if (
            strategy
            and strategy.get("selection")
            and not self.env.user.has_group("survey.group_survey_user")
        ):
            strategy["selection"] = [
                choice
                for choice in strategy["selection"]
                if choice[0] != "survey_only"
            ]
        return res

    @api.depends(
        "copy_strategy",
        "survey_id",
        "survey_question_ids",
        "survey_question_match",
    )
    def _compute_survey_counts(self):
        for wizard in self:
            if wizard.copy_strategy != "survey_only" or not wizard.survey_id:
                wizard.survey_respondent_count = 0
                wizard.survey_anonymous_count = 0
                continue
            respondents = wizard._survey_respondents()
            wizard.survey_respondent_count = len(respondents)
            wizard.survey_anonymous_count = sum(
                1 for key, _answers in respondents if key[0] == "u"
            )

    @api.constrains("copy_strategy", "survey_id")
    def _check_survey_id(self):
        # The form requires the survey too, but a record created through RPC
        # skips the form.
        for wizard in self:
            if wizard.copy_strategy == "survey_only" and not wizard.survey_id:
                raise ValidationError(
                    _("Choose the survey whose respondents enter the raffle.")
                )

    @api.constrains("survey_id", "survey_question_ids")
    def _check_survey_question_ids(self):
        # A question of another survey, or a section, has no answer in the
        # chosen survey: the raffle would come out empty without a word. An
        # empty list reads no question, so a user without survey rights can
        # still start the other strategies.
        for wizard in self:
            questions = wizard.survey_question_ids
            if questions and questions - wizard.survey_id.question_ids:
                raise ValidationError(
                    _(
                        "The required questions must be questions of the "
                        "chosen survey."
                    )
                )

    @api.onchange("survey_id")
    def _onchange_survey_id(self):
        # The questions of the previous survey have no answer in this one.
        self.survey_question_ids = False

    def _filled_survey_answers(self):
        """The answers that count as filling the survey, oldest first.

        Completed is not enough: ending a live session marks every answer of
        the survey done, even one opened and never answered, so an answer must
        also answer at least one question. A question saved as the nickname or
        the email proves nothing: Odoo fills it in for a logged-in respondent
        before any answer. Test entries never count. When
        required questions are set, an answer must also answer each of them,
        or at least one, as survey_question_match says; answering means one
        line at least that is not skipped.

        The counts of the form call it on an unsaved wizard, whose questions
        are new records: their database ids come from _origin.
        """
        self.ensure_one()
        domain = [
            ("survey_id", "=", self.survey_id._origin.id),
            ("state", "=", "done"),
            ("test_entry", "=", False),
            (
                "user_input_line_ids",
                "any",
                [
                    ("skipped", "=", False),
                    ("question_id.save_as_nickname", "=", False),
                    ("question_id.save_as_email", "=", False),
                ],
            ),
        ]
        questions = self.survey_question_ids._origin
        if questions and self.survey_question_match == "any":
            domain.append(
                (
                    "user_input_line_ids",
                    "any",
                    [
                        ("question_id", "in", questions.ids),
                        ("skipped", "=", False),
                    ],
                )
            )
        else:
            for question in questions:
                domain.append(
                    (
                        "user_input_line_ids",
                        "any",
                        [
                            ("question_id", "=", question.id),
                            ("skipped", "=", False),
                        ],
                    )
                )
        return self.env["survey.user_input"].search(
            domain, order="create_date, id"
        )

    def _survey_respondents(self):
        """The filled answers grouped by person, oldest first: a list of
        (key, answers) pairs, one per person entering the raffle.

        The contact of an answer identifies its person, under the key
        ("p", contact id). An answer without a contact joins the contact
        whose answers carry its email, unless that email shows on the
        answers of several contacts, a family address for instance, which
        tells nobody apart. Who uses an address is read from every answer of
        the survey, finished or not and whatever it answers, so that a filter
        never hides that an address is shared. The other answers without a
        contact group by email, under ("e", email), then by nickname, under
        ("n", nickname); an answer with none of the three stays alone, under
        ("u", answer id). An email is compared as its bare, lowercased
        address, since an invitation can store it as '"Name" <address>'.

        The answers are read as the current user, never sudo: without read
        access to them, the raffle gets Odoo's access error, not the
        respondents.
        """
        self.ensure_one()

        def bare(email):
            return (email_normalize(email) or email or "").strip().lower()

        owners = defaultdict(set)
        for answer in self.env["survey.user_input"].search(
            [
                ("survey_id", "=", self.survey_id._origin.id),
                ("test_entry", "=", False),
                ("partner_id", "!=", False),
                ("email", "!=", False),
            ]
        ):
            if bare(answer.email):
                owners[bare(answer.email)].add(answer.partner_id.id)
        groups = {}
        for answer in self._filled_survey_answers():
            email = bare(answer.email)
            nickname = (answer.nickname or "").strip().lower()
            if answer.partner_id:
                key = ("p", answer.partner_id.id)
            elif len(owners.get(email, ())) == 1:
                key = ("p", next(iter(owners[email])))
            elif email:
                key = ("e", email)
            elif nickname:
                key = ("n", nickname)
            else:
                key = ("u", answer.id)
            groups.setdefault(key, []).append(answer)
        return list(groups.items())

    def _copy_participants(self, raffle):
        self.ensure_one()
        if self.copy_strategy != "survey_only":
            return super()._copy_participants(raffle)
        participant_vals = []
        Partner = self.env["res.partner"]
        for key, answers in self._survey_respondents():
            # The key names the contact, even when only an answer without a
            # contact, under that contact's address, passed the filters. The
            # oldest answer giving a non-blank value provides the others. The
            # contact's name is read as superuser, as Odoo shows the contact
            # of an answer: the record rules hide a contact whose company is
            # not active for the user. Its email stays unread: the answers
            # carry the one the respondent used.
            partner = Partner.browse(key[1]) if key[0] == "p" else Partner
            nicknames = [(a.nickname or "").strip() for a in answers]
            emails = [(a.email or "").strip() for a in answers]
            nickname = next((n for n in nicknames if n), False)
            email = next((e for e in emails if e), False)
            participant_vals.append(
                {
                    "raffle_id": raffle.id,
                    "name": partner.sudo().name
                    or nickname
                    or email
                    or _("Guest"),
                    "email": email,
                    "partner_id": partner.id or False,
                    "source": "survey",
                }
            )
        if participant_vals:
            self.env["event.raffle.participant"].create(participant_vals)
