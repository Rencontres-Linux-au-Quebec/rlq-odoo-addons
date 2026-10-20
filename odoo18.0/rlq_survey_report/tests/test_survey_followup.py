# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of « Surveys not completed » (v1.113.0) and of the daily report (v1.114.0).

⚠️ NOT RUN while writing (no Odoo instance): see test_wizard.py (DISPOSABLE database, never production):

    odoo-bin -d TEST_DB -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestRlqSurveyFollowup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey = cls.env["survey.survey"].create({"title": "Visitor confirmation"})
        cls.event = cls.env["event.event"].create({"name": "Open house 2030", "date_begin": "2030-10-24 13:00:00",
                                                   "date_end": "2030-10-24 21:00:00", "rlq_alerte_courriel": "org@example.com"})
        cls.ticket = cls.env["event.event.ticket"].create({"name": "Visitor", "event_id": cls.event.id, "rlq_survey_id": cls.survey.id})

    def _registration(self, name, email, **vals):
        return self.env["event.registration"].create({"event_id": self.event.id, "event_ticket_id": self.ticket.id, "name": name,
                                                      "email": email, "state": "open", **vals})

    def _answer(self, email, state):
        return self.env["survey.user_input"].create({"survey_id": self.survey.id, "email": email, "state": state})

    def test_states_and_pending_emails(self):
        done = self._registration("Done", "done@example.com")
        started = self._registration("Started", "started@example.com")
        waiting = self._registration("Waiting", "Waiting@example.com")
        self._answer("DONE@example.com", "done")                     # case ignored
        self._answer("started@example.com", "in_progress")
        self.assertEqual(done.rlq_survey_state, "done")
        self.assertEqual(started.rlq_survey_state, "in_progress")
        self.assertEqual(waiting.rlq_survey_state, "not_started")
        self.assertEqual(waiting.rlq_expected_survey_id, self.survey)
        wizard = self.env["rlq.survey.pending"].create({"event_ids": [(6, 0, self.event.ids)]})
        self.assertEqual(wizard.emails, "started@example.com; Waiting@example.com")
        self.assertEqual(wizard.registration_ids, started | waiting)
        wizard.include_started = False
        self.assertEqual(wizard.emails, "Waiting@example.com")
        self.assertEqual(self.event.rlq_survey_pending_count, 2)

    def test_test_entries_and_cancelled_registrations_are_ignored(self):
        self._registration("Cancelled", "cancel@example.com").state = "cancel"
        reg = self._registration("Tester", "tester@example.com")
        self.env["survey.user_input"].create({"survey_id": self.survey.id, "email": "tester@example.com", "state": "done", "test_entry": True})
        wizard = self.env["rlq.survey.pending"].create({"event_ids": [(6, 0, self.event.ids)]})
        self.assertEqual(wizard.registration_ids, reg)

    def test_daily_report_sent_once_by_the_scheduled_action(self):
        self.event.rlq_daily_report = True
        self._registration("Marie", "marie@example.com")
        sent = []
        with patch.object(type(self.event), "_rlq_envoyer_courriel", lambda ev, dest, subject, body: sent.append((dest, subject, body))):
            self.env["event.event"]._cron_rlq_daily_report()
            self.env["event.event"]._cron_rlq_daily_report()             # same day: not sent again
        self.assertEqual(len(sent), 1)
        dest, subject, body = sent[0]
        self.assertEqual(dest, "org@example.com")
        self.assertIn("Daily report", subject)
        self.assertIn("Marie", body)
        self.assertNotIn("marie@example.com", body)
        self.assertTrue(self.event.rlq_daily_report_sent)
