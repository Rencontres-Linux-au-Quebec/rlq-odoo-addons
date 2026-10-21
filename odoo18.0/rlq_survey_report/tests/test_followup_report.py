# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Unit tests of models/followup_report.py (v1.113.0, v1.114.0, v1.115.0) — NO DEPENDENCY ON ODOO (pure functions), run by run-all.sh (standalone tests):

    PYTHONPATH=models python3 -m unittest tests.test_followup_report -v
"""
import sys
import unittest
from pathlib import Path

try:
    from odoo.addons.rlq_survey_report.models import followup_report as fr
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "models"))
    import followup_report as fr  # noqa: E402


class TestFollowupReport(unittest.TestCase):
    def test_survey_status_best_state_wins(self):
        self.assertEqual(fr.survey_status([]), "not_started")
        self.assertEqual(fr.survey_status(None), "not_started")
        self.assertEqual(fr.survey_status(["new"]), "not_started")
        self.assertEqual(fr.survey_status(["new", "in_progress"]), "in_progress")
        self.assertEqual(fr.survey_status(["in_progress", "done"]), "done")
        self.assertEqual(fr.survey_status(x for x in ["done"]), "done")

    def test_unique_emails_case_spaces_and_empty(self):
        self.assertEqual(fr.unique_emails(["B@x.ca", "a@x.ca", " b@X.ca ", "", None, False]), ["a@x.ca", "B@x.ca"])
        self.assertEqual(fr.unique_emails(None), [])

    def test_completion_rate(self):
        self.assertEqual(fr.completion_rate(1, 3), 33)
        self.assertEqual(fr.completion_rate(2, 3), 67)
        self.assertIsNone(fr.completion_rate(0, 0))
        self.assertIsNone(fr.completion_rate("x", 3))

    def test_subject(self):
        self.assertEqual(fr.daily_report_subject("  Open\n house ", "2026-10-20"), "Rapport quotidien 2026-10-20 : Open house")
        self.assertEqual(fr.daily_report_subject("  Open\n house ", "2026-10-20", "en_US"), "Daily report 2026-10-20: Open house")

    def test_report_lang_family_and_fallback(self):
        self.assertEqual(fr.report_lang(""), ("fr", True))
        self.assertEqual(fr.report_lang(None), ("fr", True))
        self.assertEqual(fr.report_lang("fr_CA"), ("fr", True))
        self.assertEqual(fr.report_lang("fr_FR"), ("fr", True))
        self.assertEqual(fr.report_lang("en_US"), ("en", True))
        self.assertEqual(fr.report_lang("en-ca"), ("en", True))
        self.assertEqual(fr.report_lang("es_ES"), ("fr", False))
        self.assertEqual(fr.report_lang("xx"), ("fr", False))

    def _html(self, **kw):
        args = dict(event_name="JPOL <26>", begin="2026-10-24", generated="2026-10-20 07:00 EDT",
                    totals={"registered": 3, "new": 1, "cancelled": 0, "expected": 3, "done": 1, "in_progress": 1, "not_started": 1, "done_24h": 1},
                    tickets=[{"name": "Visiteur", "registered": 2, "survey": "Confirmation", "done": 1, "in_progress": 1, "not_started": 0},
                             {"name": "Kiosque", "registered": 1, "survey": "", "done": 0, "in_progress": 0, "not_started": 0}],
                    new_registrations=[{"when": "2026-10-19 21:04", "name": "Marie <b>", "ticket": "Visiteur", "survey_state": "in_progress"}],
                    url="https://odoo.example/odoo/event.event/7")
        args.update(kw)
        return fr.daily_report_html(**args)

    def test_html_is_french_only_escaped_and_without_email(self):
        html = self._html()
        self.assertIn("Inscriptions", html)
        self.assertIn("Sondages", html)
        self.assertIn("JPOL &lt;26&gt;", html)
        self.assertIn("Marie &lt;b&gt;", html)
        self.assertIn("Commencé", html)
        self.assertIn("(33 %)", html)
        self.assertIn('href="https://odoo.example/odoo/event.event/7"', html)
        self.assertNotIn("@", html)
        self.assertIn("Événements > Sondages non complétés", html)
        self.assertNotIn("Registrations", html)
        self.assertNotIn("Started", html)

    def test_html_english_only_when_english_is_chosen(self):
        html = self._html(lang="en_CA")
        self.assertIn("Registrations", html)
        self.assertIn("Started", html)
        self.assertIn("Open the event in Odoo", html)
        self.assertNotIn("Inscriptions", html)
        self.assertNotIn("Commencé", html)
        self.assertNotIn("Bonjour", html)

    def test_html_without_survey_nor_new_registration(self):
        html = self._html(totals={"registered": 2}, tickets=[], new_registrations=[], url=None)
        self.assertIn("aucun sondage associé aux billets.", html)
        self.assertIn("Aucune nouvelle inscription depuis 24 h.", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("Sondages non complétés", html)

    def test_html_limits_the_new_registrations(self):
        rows = [{"when": "", "name": "P%d" % i, "ticket": "", "survey_state": ""} for i in range(7)]
        html = self._html(new_registrations=rows, max_rows=5)
        self.assertIn("P4", html)
        self.assertNotIn("P5", html)
        self.assertIn("… 2 de plus.", html)
        self.assertNotIn(" more.", html)


if __name__ == "__main__":
    unittest.main()
