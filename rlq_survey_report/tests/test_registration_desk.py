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
from odoo.addons.rlq_survey_report.models import registration_desk_report as rd
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

    def test_desk_sort_ignores_case_and_accents_and_sorts_computed_columns(self):
        eric = self._registration("Éric Roy", "eric@example.com")
        zoe = self._registration("zoé Tremblay", "zoe@example.com")
        adam = self._registration("adam Côté", "adam@example.com")
        self._participation("zoe@example.com", "done", lunch="Yes")
        self._participation("adam@example.com", "in_progress")
        everyone = eric | zoe | adam
        self.assertEqual(everyone._rlq_desk_sorted("name").mapped("name"), ["adam Côté", "Éric Roy", "zoé Tremblay"])
        self.assertEqual(everyone._rlq_desk_sorted("name", descending=True).mapped("name"), ["zoé Tremblay", "Éric Roy", "adam Côté"])
        self.assertEqual(everyone._rlq_desk_sorted("rlq_survey_state"), zoe | adam | eric)      # completed, started, not started
        desk = self.env["rlq.registration.desk"].create({"event_id": self.event.id, "sort_by": "name", "sort_desc": True})
        self.assertEqual(desk.registration_ids.mapped("name"), ["zoé Tremblay", "Éric Roy", "adam Côté"])
        desk.write({"sort_by": "event_ticket_id", "sort_desc": False, "survey_filter": "done"})
        self.assertEqual(desk.registration_ids, zoe)
        desk.survey_filter = "not_started"
        self.assertEqual(desk.registration_ids, eric)
        self.assertIn("rlq_survey_report", desk.summary_html)                                    # program name and version

    def test_full_list_orders_by_header_in_sql(self):
        """The full list sorts through SQL: text without case or accents, computed columns, only with the context key."""
        eric = self._registration("Éric Roy", "eric@example.com")
        zoe = self._registration("zoé Tremblay", "zoe@example.com")
        adam = self._registration("adam Côté", "adam@example.com")
        self._participation("zoe@example.com", "done", lunch="Yes")
        registrations = self.env["event.registration"].with_context(rlq_desk_event_id=self.event.id)
        domain = [("event_id", "=", self.event.id)]
        self.assertEqual(registrations.search(domain, order="name").mapped("name"), ["adam Côté", "Éric Roy", "zoé Tremblay"])
        self.assertEqual(registrations.search(domain, order="name desc").mapped("name"), ["zoé Tremblay", "Éric Roy", "adam Côté"])
        self.assertEqual(registrations.search(domain, order="rlq_survey_state, name")[0], zoe)
        self.assertEqual(registrations.search(domain, order="rlq_desk_answers")[0], zoe)
        self.assertEqual(registrations.search(domain, order="rlq_desk_progress desc")[0], zoe)
        self.assertEqual(set(registrations.search(domain, order="create_date desc, event_ticket_id").ids), set((eric | zoe | adam).ids))

    def test_survey_state_is_searchable(self):
        done = self._registration("Done", "done@example.com")
        waiting = self._registration("Waiting", "waiting@example.com")
        self._participation("done@example.com", "done", lunch="Yes")
        registrations = self.env["event.registration"]
        domain = [("event_id", "=", self.event.id)]
        self.assertEqual(registrations.search(domain + [("rlq_survey_state", "=", "done")]), done)
        self.assertEqual(registrations.search(domain + [("rlq_survey_state", "in", ["not_started", "in_progress"])]), waiting)
        self.assertEqual(registrations.search(domain + [("rlq_survey_state", "!=", "done")]), waiting)

    def test_event_selector_lists_the_most_recent_event_first(self):
        events = self.env["event.event"]
        old = events.create({"name": "RLQ selector 2029", "date_begin": "2029-01-10 13:00:00", "date_end": "2029-01-10 21:00:00"})
        new = events.create({"name": "RLQ selector 2031", "date_begin": "2031-01-10 13:00:00", "date_end": "2031-01-10 21:00:00"})
        found = events.with_context(rlq_recent_first=True).name_search("RLQ selector")
        self.assertEqual([item[0] for item in found], [new.id, old.id])
        self.assertEqual([item[0] for item in events.name_search("RLQ selector")], [old.id, new.id])   # elsewhere: unchanged

    def _volunteer_setup(self):
        survey = self.env["survey.survey"].create({"title": "Volunteer survey"})
        question = self.env["survey.question"]

        def choice(title, kind, answers, sequence):
            return question.create({"survey_id": survey.id, "title": title, "question_type": kind, "sequence": sequence,
                                    "suggested_answer_ids": [(0, 0, {"value": value}) for value in answers]})
        self.v_languages = choice("Langues parlées", "multiple_choice", ["Français", "Anglais"], 1)
        self.v_online = choice("Rôles pendant l'événement (en virtuel) ?", "multiple_choice", ["Modérateur en virtuel"], 2)
        self.v_on_site = choice("Rôles pendant l'événement (en présentiel) ?", "multiple_choice", ["Accueil", "Salle 2"], 3)
        self.v_survey = survey
        self.v_ticket = self.env["event.event.ticket"].create({"name": "Bénévole", "event_id": self.event.id, "rlq_survey_id": survey.id})

    def _volunteer(self, name, email, state=None, answers=()):
        registration = self.env["event.registration"].create({"event_id": self.event.id, "event_ticket_id": self.v_ticket.id,
                                                              "name": name, "email": email, "state": "open"})
        if state:
            user_input = self.env["survey.user_input"].create({"survey_id": self.v_survey.id, "email": email, "state": state})
            for question, value in answers:
                answer = question.suggested_answer_ids.filtered(lambda a, value=value: a.value == value)
                self.env["survey.user_input.line"].create({"user_input_id": user_input.id, "question_id": question.id,
                                                           "answer_type": "suggestion", "suggested_answer_id": answer.id})
        return registration

    def test_volunteers_table(self):
        self._volunteer_setup()
        self._volunteer("Hélène Sur Place", "helene@example.com", "done",
                        [(self.v_languages, "Français"), (self.v_languages, "Anglais"), (self.v_on_site, "Accueil")])
        self._volunteer("Omar En Ligne", "omar@example.com", "done", [(self.v_online, "Modérateur en virtuel")])
        self._volunteer("Paul Sans Sondage", "paul@example.com")
        self._registration("Visiteur Ordinaire", "visitor@example.com")       # the visitor ticket: never listed
        coordinator = self.env["rlq.volunteer.coordinator"].create({"event_id": self.event.id})
        html = coordinator.table_html
        for text in ("Hélène Sur Place", "Omar En Ligne", "Paul Sans Sondage", "Français, Anglais", "Accueil", "Salle 2",
                     "Modérateur en virtuel", "rlq_survey_report"):
            self.assertIn(text, html)
        self.assertNotIn("Visiteur Ordinaire", html)
        # Both roles questions are shown, the on-site one first.
        self.assertLess(html.index("(en présentiel)"), html.index("(en virtuel)"))
        # No type question in this survey: the type is deduced from the roles questions answered (labels of the user's language).
        labels = rd.volunteer_texts(self.env.lang)
        self.assertIn("<td>%s</td>" % labels["on_site"], html)
        self.assertIn("<td>%s</td>" % labels["online"], html)
        coordinator.survey_filter = "not_started"
        self.assertIn("Paul Sans Sondage", coordinator.table_html)
        self.assertNotIn("Hélène Sur Place", coordinator.table_html)
