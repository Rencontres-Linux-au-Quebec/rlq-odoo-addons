# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import etree
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, new_test_user
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestRaffleSurveyStrategy(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The labels asserted below are English sources, such as "Guest": a
        # database whose superuser speaks another language translates them.
        cls.env = cls.env(context=dict(cls.env.context, lang="en_US"))
        cls.event = cls.env["event.event"].create(
            {
                "name": "Event",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        # An attendee who answers nothing: the survey strategy leaves them
        # out, the registration strategies take them in.
        cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "name": "Attendee",
                "email": "attendee@example.com",
                "state": "done",
            }
        )
        cls.survey = cls._create_survey("Raffle survey")
        cls.other_survey = cls._create_survey("Other survey")
        # A survey of three questions, for the required-questions filter.
        cls.quiz = cls.env["survey.survey"].create({"title": "Quiz"})
        cls.q1, cls.q2, cls.q3 = cls.env["survey.question"].create(
            [
                {
                    "survey_id": cls.quiz.id,
                    "title": title,
                    "question_type": "char_box",
                }
                for title in ("Distribution?", "Desktop?", "Editor?")
            ]
        )

    @classmethod
    def _create_survey(cls, title):
        survey = cls.env["survey.survey"].create({"title": title})
        cls.env["survey.question"].create(
            {
                "survey_id": survey.id,
                "title": "Favourite distribution?",
                "question_type": "char_box",
            }
        )
        return survey

    def _answer(
        self,
        survey=None,
        partner=None,
        email=False,
        nickname=False,
        state="done",
        test_entry=False,
        line="answered",
    ):
        """One answer to `survey` (self.survey by default). Its single
        question is "answered" or "skipped", or it has no line at all when
        `line` is None."""
        survey = survey or self.survey
        answer = self.env["survey.user_input"].create(
            {
                "survey_id": survey.id,
                "partner_id": partner.id if partner else False,
                "email": email,
                "nickname": nickname,
                "state": state,
                "test_entry": test_entry,
            }
        )
        if line:
            vals = {
                "user_input_id": answer.id,
                "question_id": survey.question_ids.id,
            }
            if line == "skipped":
                vals["skipped"] = True
            else:
                vals.update(answer_type="char_box", value_char_box="Debian")
            self.env["survey.user_input.line"].create(vals)
        return answer

    def _run_wizard(self, user=None, context=None, **vals):
        """Start a raffle on the event, drawing from self.survey unless
        `vals` says otherwise."""
        Wizard = self.env["event.raffle.start.wizard"]
        if user:
            Wizard = Wizard.with_user(user)
        if context:
            Wizard = Wizard.with_context(**context)
        wizard = Wizard.create(
            {
                "event_id": self.event.id,
                "copy_strategy": "survey_only",
                "survey_id": self.survey.id,
                **vals,
            }
        )
        return self.env["event.raffle"].browse(wizard.action_start()["res_id"])

    def _names(self, raffle):
        # Sorted here, not by the database: its collation decides where a
        # lowercase name falls among capitalised ones.
        return sorted(raffle.participant_ids.mapped("name"))

    def _pickable_survey_ids(self, name):
        """Ids of the surveys the wizard's dropdown offers for `name`, under
        the context the form gives the field and the field's own domain."""
        Wizard = self.env["event.raffle.start.wizard"]
        arch = Wizard.get_views([(False, "form")])["views"]["form"]["arch"]
        node = etree.fromstring(arch).xpath("//field[@name='survey_id']")[0]
        context = safe_eval(node.get("context", "{}"))
        domain = Wizard._fields["survey_id"].domain
        surveys = self.env["survey.survey"].with_context(**context)
        return [row[0] for row in surveys.name_search(name, domain)]

    # ---- who enters -------------------------------------------------------

    def test_survey_respondents_enter_not_the_registrations(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann, email="ann@example.com")
        self._answer(nickname="Bob")
        raffle = self._run_wizard()
        self.assertEqual(self._names(raffle), ["Ann", "Bob"])
        ann_participant = raffle.participant_ids.filtered("partner_id")
        self.assertEqual(ann_participant.partner_id, ann)
        self.assertEqual(ann_participant.email, "ann@example.com")
        self.assertEqual(
            set(raffle.participant_ids.mapped("source")), {"survey"}
        )

    def test_unfinished_answers_stay_out(self):
        self._answer(nickname="New", state="new")
        self._answer(nickname="Started", state="in_progress")
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_test_entries_stay_out(self):
        self._answer(nickname="Tester", test_entry=True)
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_answer_skipping_every_question_stays_out(self):
        # A page submitted with every question left blank still completes
        # the answer: completion alone proves nothing.
        self._answer(nickname="Skipper", line="skipped")
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_answer_without_any_line_stays_out(self):
        # A live-session attendee who never answers has no line at all, yet
        # ending the session marks every answer of the survey done.
        self._answer(nickname="Joined", line=None)
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_answers_to_another_survey_stay_out(self):
        self._answer(survey=self.other_survey, nickname="Elsewhere")
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_closed_survey_can_be_picked_and_feeds_the_raffle(self):
        # Closing a survey archives it, and the draw usually comes after.
        self._answer(nickname="Done")
        self.survey.action_archive()
        self.assertIn(
            self.survey.id, self._pickable_survey_ids("Raffle survey")
        )
        self.assertEqual(self._names(self._run_wizard()), ["Done"])

    def test_every_non_specialised_survey_type_can_be_picked(self):
        # Live sessions and assessments are drawn from like any survey; only
        # a specialised survey keeps its answers to its own application.
        survey_types = ("survey", "live_session", "assessment", "custom")
        surveys = self.env["survey.survey"].create(
            [{"title": "Pick %s" % t, "survey_type": t} for t in survey_types]
        )
        picked = set(self._pickable_survey_ids("Pick "))
        self.assertEqual(picked & set(surveys.ids), set(surveys.ids))

    # ---- the same person enters once --------------------------------------
    # Which of the duplicate answers names the participant is not the point
    # here: each test asks for exactly one participant, and from the survey.

    def _sources(self, raffle):
        return raffle.participant_ids.mapped("source")

    def test_a_contact_answering_twice_enters_once(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann, email="ann@example.com")
        self._answer(partner=ann, email="ann.b@example.com")
        self.assertEqual(self._sources(self._run_wizard()), ["survey"])

    def test_an_email_enters_once_whatever_its_form(self):
        # An invitation can store the address as '"Name" <address>'.
        self._answer(email='"Ann" <ann@example.com>')
        self._answer(email="ANN@example.com")
        self.assertEqual(self._sources(self._run_wizard()), ["survey"])

    def test_a_nickname_enters_once_without_contact_or_email(self):
        self._answer(nickname="Bob")
        self._answer(nickname=" bob")
        self.assertEqual(self._sources(self._run_wizard()), ["survey"])

    def test_a_shared_nickname_with_different_emails_stays_two(self):
        # An email identifies a person before a nickname, which anyone can
        # pick in a live session.
        self._answer(nickname="Alex", email="alex.one@example.com")
        self._answer(nickname="Alex", email="alex.two@example.com")
        self.assertEqual(self._names(self._run_wizard()), ["Alex", "Alex"])

    def test_the_oldest_answer_of_a_person_fills_the_participant(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann, email="ann.new@example.com")
        older = self._answer(partner=ann, email="ann.old@example.com")
        # Created second but dated a day earlier, so that the date order and
        # the id order disagree.
        self.env.cr.execute(
            "UPDATE survey_user_input"
            " SET create_date = create_date - interval '1 day'"
            " WHERE id = %s",
            [older.id],
        )
        older.invalidate_recordset(["create_date"])
        raffle = self._run_wizard()
        self.assertEqual(raffle.participant_ids.email, "ann.old@example.com")

    def test_anonymous_answers_stay_distinct_guests(self):
        self._answer()
        self._answer()
        self.assertEqual(self._names(self._run_wizard()), ["Guest", "Guest"])

    def test_name_comes_from_contact_then_nickname_then_email(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann, nickname="Pseudo", email="ann@example.com")
        self._answer(nickname="Bob", email="bob@example.com")
        self._answer(email="carol@example.com")
        self.assertEqual(
            self._names(self._run_wizard()),
            ["Ann", "Bob", "carol@example.com"],
        )

    def test_an_answer_without_contact_joins_the_contact_owning_its_email(
        self,
    ):
        # Answering once through a contact and once without one, with the
        # same address, is one person: the contact names them, whatever the
        # order.
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(nickname="Annie", email="ANN@example.com")
        self._answer(partner=ann, email="ann@example.com")
        raffle = self._run_wizard()
        self.assertEqual(self._names(raffle), ["Ann"])
        self.assertEqual(raffle.participant_ids.partner_id, ann)

    def test_contacts_sharing_an_email_stay_apart(self):
        # A shared address, a family one for instance, tells nobody apart: two
        # contacts stay two, and an anonymous answer with that address joins
        # neither of them.
        ann = self.env["res.partner"].create({"name": "Ann"})
        bob = self.env["res.partner"].create({"name": "Bob"})
        self._answer(partner=ann, email="family@example.com")
        self._answer(partner=bob, email="family@example.com")
        self._answer(email="family@example.com")
        self.assertEqual(
            self._names(self._run_wizard()),
            ["Ann", "Bob", "family@example.com"],
        )

    def test_a_shared_address_counts_unfinished_answers_too(self):
        # Bob's answer is not finished, yet it shows that Bob uses the family
        # address: Carol, without a contact, joins nobody.
        ann = self.env["res.partner"].create({"name": "Ann"})
        bob = self.env["res.partner"].create({"name": "Bob"})
        self._answer(partner=ann, email="family@example.com")
        self._answer(
            partner=bob, email="family@example.com", state="in_progress"
        )
        self._answer(nickname="Carol", email="family@example.com")
        self.assertEqual(self._names(self._run_wizard()), ["Ann", "Carol"])

    def test_a_contact_without_email_absorbs_nobody(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann)
        self._answer()
        self._answer(nickname="Bob")
        self.assertEqual(self._counts(), (3, 1))
        self.assertEqual(
            self._names(self._run_wizard()), ["Ann", "Bob", "Guest"]
        )

    def test_the_oldest_nickname_names_the_person(self):
        self._answer(nickname="Old", email="x@example.com")
        self._answer(nickname="New", email="X@example.com")
        self.assertEqual(self._names(self._run_wizard()), ["Old"])

    def test_an_accented_email_enters_once_whatever_its_case(self):
        # Odoo's normalisation keeps the case of a non-ASCII local part.
        self._answer(email="Élise@example.com")
        self._answer(email="élise@example.com")
        self.assertEqual(self._sources(self._run_wizard()), ["survey"])

    def test_an_unparsable_email_enters_once_whatever_its_case(self):
        # An address typed into a survey link is not validated: compared
        # raw, lowercased and stripped, it still identifies its person.
        self._answer(email="Ann at home")
        self._answer(email=" ANN AT HOME ")
        self.assertEqual(self._sources(self._run_wizard()), ["survey"])

    def test_a_prefilled_identity_line_proves_no_answer(self):
        # Odoo writes a logged-in respondent's nickname into the question
        # saved as nickname before any answer, and ending a live session
        # marks that answer done.
        survey = self.env["survey.survey"].create({"title": "Session"})
        nickname_question = self.env["survey.question"].create(
            {
                "survey_id": survey.id,
                "title": "Your nickname?",
                "question_type": "char_box",
                "save_as_nickname": True,
            }
        )
        self.env["survey.question"].create(
            {
                "survey_id": survey.id,
                "title": "Distribution?",
                "question_type": "char_box",
            }
        )
        user = new_test_user(
            self.env, login="raffle_session_user", name="Logged Attendee"
        )
        answer = survey._create_answer(user=user)
        answer.state = "done"
        self.assertEqual(
            answer.user_input_line_ids.filtered(
                lambda line: not line.skipped
            ).question_id,
            nickname_question,
        )
        raffle = self._run_wizard(survey_id=survey.id)
        self.assertEqual(raffle.participant_count, 0)

    # ---- the wizard's counts ----------------------------------------------

    def _counts(self, **vals):
        wizard = self.env["event.raffle.start.wizard"].create(
            {
                "event_id": self.event.id,
                "copy_strategy": "survey_only",
                "survey_id": self.survey.id,
                **vals,
            }
        )
        return wizard.survey_respondent_count, wizard.survey_anonymous_count

    def test_an_email_alone_is_not_anonymous(self):
        self._answer(email="solo@example.com")
        self.assertEqual(self._counts(), (1, 0))

    def test_a_contact_alone_is_not_anonymous(self):
        solo = self.env["res.partner"].create({"name": "Solo"})
        self._answer(partner=solo)
        self.assertEqual(self._counts(), (1, 0))

    def test_a_blank_nickname_is_anonymous(self):
        self._answer(nickname="   ")
        self.assertEqual(self._counts(), (1, 1))
        self.assertEqual(self._names(self._run_wizard()), ["Guest"])

    def test_wizard_counts_the_respondents_before_the_draw(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._answer(partner=ann, email="ann@example.com")
        self._answer(email="ann@example.com")
        self._answer(nickname="Bob")
        self._answer()
        self._answer()
        self._answer(nickname="Unfinished", state="in_progress")
        wizard = self.env["event.raffle.start.wizard"].create(
            {
                "event_id": self.event.id,
                "copy_strategy": "survey_only",
                "survey_id": self.survey.id,
            }
        )
        self.assertEqual(wizard.survey_respondent_count, 4)
        self.assertEqual(wizard.survey_anonymous_count, 2)
        raffle = self.env["event.raffle"].browse(
            wizard.action_start()["res_id"]
        )
        self.assertEqual(raffle.participant_count, 4)

    def test_counts_follow_the_required_questions_live(self):
        self._quiz_respondents()
        form = Form(
            self.env["event.raffle.start.wizard"].with_context(
                default_event_id=self.event.id
            )
        )
        form.copy_strategy = "survey_only"
        form.survey_id = self.quiz
        self.assertEqual(form.survey_respondent_count, 4)
        form.survey_question_ids.add(self.q1)
        form.survey_question_ids.add(self.q2)
        self.assertEqual(form.survey_respondent_count, 1)
        form.survey_question_match = "any"
        self.assertEqual(form.survey_respondent_count, 3)

    def test_counts_stay_empty_for_the_other_strategies(self):
        self._answer(nickname="Respondent")
        wizard = self.env["event.raffle.start.wizard"].create(
            {
                "event_id": self.event.id,
                "copy_strategy": "present_only",
                "survey_id": self.survey.id,
            }
        )
        self.assertEqual(wizard.survey_respondent_count, 0)
        self.assertEqual(wizard.survey_anonymous_count, 0)

    # ---- required questions -----------------------------------------------

    def _quiz_answer(self, nickname, answered=(), skipped=(), **vals):
        """A completed answer to self.quiz that answers the `answered`
        questions and leaves the `skipped` ones blank; `vals` adds or
        overrides user_input values (partner_id, email, state)."""
        answer = self.env["survey.user_input"].create(
            {
                "survey_id": self.quiz.id,
                "nickname": nickname,
                "state": "done",
                **vals,
            }
        )
        self.env["survey.user_input.line"].create(
            [
                {
                    "user_input_id": answer.id,
                    "question_id": question.id,
                    "answer_type": "char_box",
                    "value_char_box": "Debian",
                }
                for question in answered
            ]
            + [
                {
                    "user_input_id": answer.id,
                    "question_id": question.id,
                    "skipped": True,
                }
                for question in skipped
            ]
        )
        return answer

    def _quiz_respondents(self):
        self._quiz_answer("Both", answered=self.q1 | self.q2)
        self._quiz_answer("First", answered=self.q1, skipped=self.q2)
        self._quiz_answer("Second", answered=self.q2)
        self._quiz_answer("Third", answered=self.q3, skipped=self.q1 | self.q2)

    def _run_quiz(self, questions, **vals):
        return self._run_wizard(
            survey_id=self.quiz.id,
            survey_question_ids=[Command.set(questions.ids)],
            **vals,
        )

    def test_required_questions_must_each_be_answered_by_default(self):
        self._quiz_respondents()
        raffle = self._run_quiz(self.q1 | self.q2)
        self.assertEqual(self._names(raffle), ["Both"])

    def test_required_questions_can_need_only_one_answer(self):
        self._quiz_respondents()
        raffle = self._run_quiz(self.q1 | self.q2, survey_question_match="any")
        self.assertEqual(self._names(raffle), ["Both", "First", "Second"])

    def test_no_required_question_filters_nobody(self):
        self._quiz_respondents()
        for match in ("all", "any"):
            raffle = self._run_quiz(
                self.env["survey.question"], survey_question_match=match
            )
            self.assertEqual(
                self._names(raffle), ["Both", "First", "Second", "Third"]
            )

    def test_a_shared_address_stays_shared_whatever_the_filter(self):
        # Bob's answer misses the required question, yet it still shows that
        # Bob uses the family address: Carol, without a contact, joins nobody.
        ann = self.env["res.partner"].create({"name": "Ann"})
        bob = self.env["res.partner"].create({"name": "Bob"})
        family = "family@example.com"
        self._quiz_answer("Ann", self.q1, partner_id=ann.id, email=family)
        self._quiz_answer("Bob", self.q2, partner_id=bob.id, email=family)
        self._quiz_answer("Carol", self.q1, email=family)
        self.assertEqual(
            self._names(self._run_quiz(self.q1)), ["Ann", "Carol"]
        )

    def test_an_answer_enters_as_the_contact_owning_its_email(self):
        # Ann's own answer misses the required question; her answer without
        # a contact, under her address, answers it and brings her in.
        ann = self.env["res.partner"].create({"name": "Ann"})
        self._quiz_answer(
            "Ann", self.q2, partner_id=ann.id, email="ann@example.com"
        )
        self._quiz_answer("Annie", self.q1, email="ANN@example.com")
        raffle = self._run_quiz(self.q1)
        self.assertEqual(self._names(raffle), ["Ann"])
        self.assertEqual(raffle.participant_ids.partner_id, ann)

    def test_required_questions_belong_to_the_chosen_survey(self):
        section = self.env["survey.question"].create(
            {"survey_id": self.quiz.id, "title": "Section", "is_page": True}
        )
        for stranger in (self.survey.question_ids, section):
            with self.assertRaises(ValidationError):
                self.env["event.raffle.start.wizard"].create(
                    {
                        "event_id": self.event.id,
                        "copy_strategy": "survey_only",
                        "survey_id": self.quiz.id,
                        "survey_question_ids": [Command.set(stranger.ids)],
                    }
                )

    def test_form_offers_the_questions_of_the_picked_survey(self):
        form = Form(
            self.env["event.raffle.start.wizard"].with_context(
                default_event_id=self.event.id
            )
        )
        form.copy_strategy = "survey_only"
        with self.assertRaisesRegex(AssertionError, "not visible"):
            form.survey_question_ids.add(self.q1)
        form.survey_id = self.quiz
        form.survey_question_ids.add(self.q1)
        form.survey_question_match = "any"
        # Another survey's questions cannot stay: picking it empties the
        # list, and the match choice goes with it.
        form.survey_id = self.survey
        self.assertEqual(len(form.survey_question_ids), 0)
        with self.assertRaisesRegex(AssertionError, "invisible field"):
            form.survey_question_match = "all"

    # ---- the wizard -------------------------------------------------------

    def test_survey_strategy_requires_a_survey(self):
        with self.assertRaises(ValidationError):
            self.env["event.raffle.start.wizard"].create(
                {"event_id": self.event.id, "copy_strategy": "survey_only"}
            )

    def test_form_shows_and_requires_the_survey_with_its_strategy(self):
        form = Form(
            self.env["event.raffle.start.wizard"].with_context(
                default_event_id=self.event.id
            )
        )
        with self.assertRaisesRegex(AssertionError, "invisible field"):
            form.survey_id = self.survey
        form.copy_strategy = "survey_only"
        with self.assertRaisesRegex(
            AssertionError, "survey_id is a required field"
        ):
            form.save()
        form.survey_id = self.survey
        self.assertEqual(form.save().survey_id, self.survey)

    def test_other_strategies_ignore_the_survey(self):
        self._answer(nickname="Respondent")
        raffle = self._run_wizard(copy_strategy="present_only")
        self.assertEqual(self._names(raffle), ["Attendee"])

    def test_uninstall_keeps_survey_participants_as_guests(self):
        self._answer(nickname="Winner")
        raffle = self._run_wizard()
        raffle.action_draw_next()
        winner = raffle.participant_ids
        # What uninstalling the module does to the rows holding its value.
        self.env["ir.model.fields.selection"].search(
            [
                ("field_id.model", "=", "event.raffle.participant"),
                ("field_id.name", "=", "source"),
                ("value", "=", "survey"),
            ]
        )._process_ondelete()
        self.assertTrue(winner.exists())
        self.assertEqual(winner.source, "guest")
        self.assertEqual(raffle.draw_ids.winner_participant_id, winner)

    # ---- access rights ----------------------------------------------------
    # No sudo on the answers: whoever may not read them may not draw from
    # them either, and the form does not offer them the survey strategy.

    def _wizard_form_view(self, user):
        return (
            self.env["event.raffle.start.wizard"]
            .with_user(user)
            .get_views([(False, "form")])
        )

    def test_survey_strategy_hidden_without_survey_rights(self):
        event_user = new_test_user(
            self.env,
            login="raffle_no_survey",
            groups="event.group_event_user",
        )
        survey_user = new_test_user(
            self.env,
            login="raffle_with_survey",
            groups="event.group_event_user,survey.group_survey_user",
        )
        for user, shown in ((event_user, False), (survey_user, True)):
            views = self._wizard_form_view(user)
            fields = views["models"]["event.raffle.start.wizard"]["fields"]
            choices = [
                value for value, _label in fields["copy_strategy"]["selection"]
            ]
            self.assertEqual("survey_only" in choices, shown)
            arch = views["views"]["form"]["arch"]
            self.assertEqual('name="survey_id"' in arch, shown)

    def test_event_user_without_survey_rights_is_refused(self):
        user = new_test_user(
            self.env,
            login="raffle_event_user",
            groups="event.group_event_user",
        )
        self._answer(nickname="Done")
        with self.assertRaises(AccessError):
            self._run_wizard(user=user)

    def test_counts_need_the_right_to_read_answers(self):
        user = new_test_user(
            self.env,
            login="raffle_counts_user",
            groups="event.group_event_user",
        )
        self._answer(nickname="Done")
        wizard = (
            self.env["event.raffle.start.wizard"]
            .with_user(user)
            .create(
                {
                    "event_id": self.event.id,
                    "copy_strategy": "survey_only",
                    "survey_id": self.survey.id,
                }
            )
        )
        with self.assertRaises(AccessError):
            wizard.survey_respondent_count  # noqa: B018

    def test_event_user_with_survey_rights_draws_from_the_survey(self):
        user = new_test_user(
            self.env,
            login="raffle_survey_user",
            groups="event.group_event_user,survey.group_survey_user",
        )
        self._answer(nickname="Done")
        self.assertEqual(self._names(self._run_wizard(user=user)), ["Done"])

    def test_contact_of_an_inactive_company_still_names_the_participant(self):
        # The record rules hide a contact of a company outside the user's
        # active ones, while its answer stays readable.
        company_b = self.env["res.company"].create({"name": "Company B"})
        user = new_test_user(
            self.env,
            login="raffle_two_companies",
            groups="event.group_event_user,survey.group_survey_user",
            company_ids=[Command.set((self.env.company | company_b).ids)],
        )
        contact = self.env["res.partner"].create(
            {"name": "Contact of B", "company_id": company_b.id}
        )
        self._answer(partner=contact)
        # Creating the records cached the contact, and a cached value skips
        # the record rules: empty the cache so the wizard reads the database.
        self.env.invalidate_all()
        raffle = self._run_wizard(
            user=user, context={"allowed_company_ids": self.env.company.ids}
        )
        self.assertEqual(self._names(raffle), ["Contact of B"])
