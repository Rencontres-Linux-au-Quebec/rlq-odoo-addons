# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of the manual changes of survey answers (v1.127.0).

[ATTN] NOT RUN while writing (no Odoo instance): see test_wizard.py (DISPOSABLE database, never production):

    odoo-bin -d TEST_DB -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestRlqSurveyAnswerEdit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey = cls.env["survey.survey"].create({"title": "Answer edit survey"})
        question = cls.env["survey.question"]
        cls.q_lunch = question.create({
            "survey_id": cls.survey.id, "title": "Lunch?", "question_type": "simple_choice", "sequence": 1,
            "suggested_answer_ids": [(0, 0, {"value": "Yes"}), (0, 0, {"value": "No"})]})
        cls.q_name = question.create({"survey_id": cls.survey.id, "title": "Distribution", "question_type": "char_box", "sequence": 2})
        cls.q_count = question.create({"survey_id": cls.survey.id, "title": "How many?", "question_type": "numerical_box", "sequence": 3})
        cls.user_input = cls.env["survey.user_input"].create({"survey_id": cls.survey.id, "email": "marie@example.com", "state": "done"})
        cls.user_input._save_lines(cls.q_lunch, cls.q_lunch.suggested_answer_ids.filtered(lambda a: a.value == "No").id)
        cls.user_input._save_lines(cls.q_name, "Debian")

    def _wizard(self):
        return self.env["rlq.survey.answer.edit"].create({"user_input_id": self.user_input.id})

    def _line(self, wizard, question):
        return wizard.line_ids.filtered(lambda line: line.question_id == question)

    def test_lines_show_the_current_answers_and_nothing_is_changed(self):
        wizard = self._wizard()
        self.assertEqual(self._line(wizard, self.q_lunch).current_text, "No")
        self.assertEqual(self._line(wizard, self.q_name).current_text, "Debian")
        self.assertEqual(self._line(wizard, self.q_count).current_text, "")
        self.assertFalse(wizard.line_ids.filtered("changed"))
        with self.assertRaises(UserError):
            wizard.action_apply()

    def test_change_is_saved_and_written_in_the_history(self):
        wizard = self._wizard()
        wizard.reason = "Asked on the phone"
        self._line(wizard, self.q_lunch).new_choice_id = self.q_lunch.suggested_answer_ids.filtered(lambda a: a.value == "Yes")
        count = self._line(wizard, self.q_count)
        count.write({"erase": False, "new_number": 0.0})                    # zero is an answer, not « skipped »
        wizard.action_apply()
        lines = self.user_input.user_input_line_ids
        lunch = lines.filtered(lambda line: line.question_id == self.q_lunch)
        self.assertEqual(lunch.suggested_answer_id.value, "Yes")
        number = lines.filtered(lambda line: line.question_id == self.q_count)
        self.assertFalse(number.skipped)
        self.assertEqual(number.value_numerical_box, 0.0)
        history = self.env["rlq.survey.answer.change"].search([("user_input_id", "=", self.user_input.id)], order="id")
        self.assertEqual(history.mapped("question_title"), ["Lunch?", "How many?"])
        self.assertEqual((history[0].old_value, history[0].new_value, history[0].reason), ("No", "Yes", "Asked on the phone"))
        self.assertEqual(history[0].email, "marie@example.com")
        self.assertFalse(history[0].sent_date)
        self.assertEqual(self.user_input.rlq_change_count, 2)
        with self.assertRaises(UserError):
            history[0].write({"new_value": "Something else"})

    def test_update_e_mail_sends_only_the_changes_not_sent(self):
        wizard = self._wizard()
        self._line(wizard, self.q_name).new_text = "Fedora"
        wizard.send_email = True
        wizard.action_apply()
        change = self.env["rlq.survey.answer.change"].search([("user_input_id", "=", self.user_input.id)])
        self.assertTrue(change.sent_date)
        mail = self.env["mail.mail"].search([("email_to", "=", "marie@example.com")], order="id desc", limit=1)
        self.assertIn("Fedora", mail.body_html)
        self.assertIn("Debian", mail.body_html)                             # the answer before
        with self.assertRaises(UserError):
            change.action_send_update()                                     # already sent

    def test_no_e_mail_address(self):
        nobody = self.env["survey.user_input"].create({"survey_id": self.survey.id, "state": "done"})
        wizard = self.env["rlq.survey.answer.edit"].create({"user_input_id": nobody.id, "send_email": True})
        self._line(wizard, self.q_name).new_text = "Arch"
        wizard.action_apply()
        change = self.env["rlq.survey.answer.change"].search([("user_input_id", "=", nobody.id)])
        self.assertFalse(change.sent_date)
