# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of the invalid e-mail addresses of registrations (v1.109.0).

⚠️ NOT RUN while writing (no Odoo instance): see test_wizard.py (DISPOSABLE database, never production):

    odoo-bin -d TEST_DB -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestRlqRegistrationEmail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create({"name": "Open house 2026", "date_begin": "2026-10-24 13:00:00", "date_end": "2026-10-24 21:00:00"})
        cls.param = cls.env["ir.config_parameter"].sudo()

    def _registration(self, email, **vals):
        return self.env["event.registration"].create({"event_id": self.event.id, "name": "Marie", "email": email, **vals})

    def test_punctuation_fixed_at_registration_time(self):
        self.param.set_param("rlq_survey_report.registration_email_autofix", "syntax")
        r = self._registration("mariebc33@gmail'com")
        self.assertEqual(r.email, "mariebc33@gmail.com")
        self.assertFalse(r.rlq_email_issue)

    def test_autofix_off_flags_without_changing(self):
        self.param.set_param("rlq_survey_report.registration_email_autofix", "off")
        r = self._registration("mariebc33@gmail'com")
        self.assertEqual(r.email, "mariebc33@gmail'com")
        self.assertEqual(r.rlq_email_issue, "invalid")
        self.assertEqual(r.rlq_email_suggestion, "mariebc33@gmail.com")

    def test_typo_flagged_and_fixed_by_the_wizard_with_the_contact(self):
        partner = self.env["res.partner"].create({"name": "Jean", "email": "jean@gmial.com"})
        r = self._registration("jean@gmial.com", partner_id=partner.id)
        self.assertEqual(r.rlq_email_issue, "typo")
        action = r.action_rlq_fix_email()
        wizard = self.env["rlq.registration.email.fix"].browse(action["res_id"])
        self.assertEqual(wizard.line_ids.new_email, "jean@gmail.com")
        wizard.action_apply()
        self.assertEqual(r.email, "jean@gmail.com")
        self.assertEqual(partner.email, "jean@gmail.com")
        self.assertFalse(r.rlq_email_issue)

    def test_wizard_refuses_an_invalid_correction(self):
        self.param.set_param("rlq_survey_report.registration_email_autofix", "off")
        r = self._registration("x@gmail'com")
        wizard = self.env["rlq.registration.email.fix"].browse(r.action_rlq_fix_email()["res_id"])
        wizard.line_ids.new_email = "still wrong@"
        with self.assertRaises(UserError):
            wizard.action_apply()
