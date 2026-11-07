# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of the pivot table opened from a survey form (v1.119.0).

NOT RUN while writing (no Odoo instance). Run on a disposable database only:

    odoo-bin -d TEST_DB -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from odoo.tests.common import TransactionCase


class TestRlqSurveyPivot(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey = cls.env["survey.survey"].create({"title": "Pivot test survey"})
        cls.other_survey = cls.env["survey.survey"].create({"title": "Other survey"})

    def test_action_opens_pivot_on_answer_lines(self):
        action = self.survey.action_rlq_tableau_croise()
        self.assertEqual(action["res_model"], "survey.user_input.line")
        self.assertEqual(action["view_mode"], "pivot")
        self.assertEqual(action["views"][0][1], "pivot")
        self.assertEqual(action["views"][0][0], self.env.ref("rlq_survey_report.view_survey_user_input_line_pivot_rlq").id)

    def test_domain_restricts_to_this_survey_and_completed_submissions(self):
        action = self.survey.action_rlq_tableau_croise()
        self.assertIn(("user_input_id.survey_id", "=", self.survey.id), action["domain"])
        self.assertIn(("user_input_id.state", "=", "done"), action["domain"])
        self.assertNotIn(self.other_survey.id, [value for _f, _o, value in action["domain"]])
