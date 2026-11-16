# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of the RLQ registration desk (v1.121.0).

[ATTN] NOT RUN while writing (no Odoo instance): see test_wizard.py (DISPOSABLE database, never production):

    odoo-bin -d TEST_DB -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from odoo.tests.common import TransactionCase


class TestRlqRegistrationDesk(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey = cls.env["survey.survey"].create({"title": "Visitor confirmation"})
        question = cls.env["survey.question"]
        cls.q_lunch = question.create({
            "survey_id": cls.survey.id, "title": "Will you be there for lunch?", "question_type": "simple_choice", "sequence": 1,
            "rlq_registration_desk": True, "rlq_desk_label": "Lunch",
            "suggested_answer_ids": [(0, 0, {"value": "Yes"}), (0, 0, {"value": "No"})]})
        cls.q_name = question.create({"survey_id": cls.survey.id, "title": "Your distribution", "question_type": "char_box", "sequence": 2})
        cls.event = cls.env["event.event"].create({"name": "Open house 2030", "date_begin": "2030-10-24 13:00:00",
                                                   "date_end": "2030-10-24 21:00:00", "date_tz": "America/Toronto"})
        cls.ticket = cls.env["event.event.ticket"].create({"name": "Visitor", "event_id": cls.event.id, "rlq_survey_id": cls.survey.id})

    def _registration(self, name, email, **vals):
        return self.env["event.registration"].create({"event_id": self.event.id, "event_ticket_id": self.ticket.id, "name": name,
                                                      "email": email, "state": "open", **vals})

    def _participation(self, email, state, lunch=None, distribution=None):
        user_input = self.env["survey.user_input"].create({"survey_id": self.survey.id, "email": email, "state": state})
        line = self.env["survey.user_input.line"]
        if lunch:
            answer = self.q_lunch.suggested_answer_ids.filtered(lambda a: a.value == lunch)
            line.create({"user_input_id": user_input.id, "question_id": self.q_lunch.id, "answer_type": "suggestion",
                         "suggested_answer_id": answer.id})
        if distribution:
            line.create({"user_input_id": user_input.id, "question_id": self.q_name.id, "answer_type": "char_box",
                         "value_char_box": distribution})
        return user_input

    def test_progress_and_answers_of_a_registration(self):
        done = self._registration("Done", "done@example.com")
        started = self._registration("Started", "started@example.com")
        waiting = self._registration("Waiting", "waiting@example.com")
        self._participation("DONE@example.com", "done", lunch="Yes", distribution="Debian")
        self._participation("started@example.com", "in_progress", lunch="No")
        self.assertEqual(done.rlq_desk_progress, "2/2")
        self.assertEqual(done.rlq_desk_answers, "Lunch: Yes")
        self.assertEqual(started.rlq_desk_progress, "1/2")
        self.assertEqual(started.rlq_desk_answers, "Lunch: No")
        self.assertEqual(waiting.rlq_desk_progress, "0/2")
        self.assertFalse(waiting.rlq_desk_answers)

    def test_most_advanced_participation_wins(self):
        registration = self._registration("Twice", "twice@example.com")
        self._participation("twice@example.com", "done", lunch="Yes", distribution="Fedora")
        self._participation("twice@example.com", "in_progress", lunch="No")
        self.assertEqual(registration.rlq_desk_progress, "2/2")
        self.assertEqual(registration.rlq_desk_answers, "Lunch: Yes")

    def test_present_and_undo(self):
        registration = self._registration("Marie", "marie@example.com")
        registration.action_rlq_desk_present()
        self.assertEqual(registration.state, "done")
        self.assertTrue(registration.date_closed)
        rows = registration._rlq_desk_rows()
        self.assertTrue(rows[0]["present"])
        self.assertTrue(rows[0]["hour"])
        registration.action_rlq_desk_undo()
        self.assertEqual(registration.state, "open")
        self.assertFalse(registration.date_closed)
        cancelled = self._registration("Cancelled", "cancel@example.com")
        cancelled.state = "cancel"
        cancelled.action_rlq_desk_present()
        self.assertEqual(cancelled.state, "cancel")

    def test_desk_wizard_summary_search_and_filter(self):
        marie = self._registration("Marie Tremblay", "marie@example.com")
        paul = self._registration("Paul Roy", "paul@example.com")
        self._registration("Cancelled", "cancel@example.com").state = "cancel"
        self._participation("marie@example.com", "done", lunch="Yes")
        marie.action_rlq_desk_present()
        desk = self.env["rlq.registration.desk"].create({"event_id": self.event.id})
        self.assertEqual(desk.registration_ids, marie | paul)
        self.assertIn("Visitor", desk.summary_html)
        self.assertIn("Lunch", desk.summary_html)
        self.assertNotIn("marie@example.com", desk.summary_html)
        desk.search_text = "trem"
        self.assertEqual(desk.registration_ids, marie)
        desk.search_text = False
        desk.hide_present = True
        self.assertEqual(desk.registration_ids, paul)
        self.assertEqual(desk.registration_count, 1)

    def test_departure_recorded_once_and_cleared(self):
        registration = self._registration("Julie", "julie@example.com")
        registration.action_rlq_desk_present()
        registration.action_rlq_desk_depart()
        first = registration.rlq_departure
        self.assertTrue(first)
        registration.action_rlq_desk_depart()                            # already left: the time is kept
        self.assertEqual(registration.rlq_departure, first)
        registration.action_rlq_desk_depart_undo()
        self.assertFalse(registration.rlq_departure)
        absent = self._registration("Absent", "absent@example.com")
        absent.action_rlq_desk_depart()                                  # not present: nothing recorded
        self.assertFalse(absent.rlq_departure)

    def test_volunteer_coordinator_lists_only_volunteer_tickets(self):
        volunteer_survey = self.env["survey.survey"].create({"title": "Volunteer survey"})
        self.env["survey.question"].create({"survey_id": volunteer_survey.id, "title": "En virtuel ou pas ?",
                                            "question_type": "simple_choice",
                                            "suggested_answer_ids": [(0, 0, {"value": "Virtuel"}), (0, 0, {"value": "Présentiel"})]})
        roles = self.env["survey.question"].create({"survey_id": volunteer_survey.id,
                                                    "title": "Rôles pendant l'événement (en présentiel) ?", "question_type": "multiple_choice",
                                                    "suggested_answer_ids": [(0, 0, {"value": "Accueil"}), (0, 0, {"value": "Salle 2"})]})
        volunteer = self.env["event.event.ticket"].create({"name": "Bénévole", "event_id": self.event.id,
                                                           "rlq_survey_id": volunteer_survey.id})
        helper = self.env["event.registration"].create({"event_id": self.event.id, "event_ticket_id": volunteer.id,
                                                        "name": "Hélène Bénévole", "email": "helene@example.com", "state": "open"})
        self.env["survey.user_input"].create({"survey_id": volunteer_survey.id, "email": "helene@example.com", "state": "done"})
        self._registration("Visiteur", "visitor@example.com")           # the visitor ticket: never listed
        coordinator = self.env["rlq.volunteer.coordinator"].create({"event_id": self.event.id})
        html = coordinator.table_html
        self.assertIn("Hélène Bénévole", html)
        self.assertNotIn("Visiteur", html)
        self.assertIn("Accueil", html)
        self.assertIn("Salle 2", html)
        self.assertTrue(roles)
        self.assertTrue(helper)
