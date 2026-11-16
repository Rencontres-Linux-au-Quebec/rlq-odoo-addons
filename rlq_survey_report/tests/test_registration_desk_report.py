# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Unit tests of models/registration_desk_report.py (v1.121.0) - NO DEPENDENCY ON ODOO (pure functions), run by run-all.sh (standalone tests):

    python3 -m unittest tests.test_registration_desk_report -v
"""
import sys
import unittest
from pathlib import Path

try:
    from odoo.addons.rlq_survey_report.models import registration_desk_report as rd
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "models"))
    import registration_desk_report as rd  # noqa: E402


def row(ticket, present=False, hour=None, state="not_started", questions=4, answered=0, answers=()):
    return {"ticket": ticket, "present": present, "hour": hour, "survey_state": state, "questions": questions,
            "answered": answered, "answers": list(answers)}


ROWS = [
    row("Visitor", True, "2026-10-10 09", "done", 4, 4, [("Lunch", ["Yes"]), ("Mode", ["On site"])]),
    row("Visitor", True, "2026-10-10 09", "in_progress", 4, 1, [("Lunch", ["No"]), ("Mode", [])]),
    row("Visitor", False, None, "not_started", 4, 0, [("Lunch", []), ("Mode", [])]),
    row("Volunteer", True, "2026-10-10 10", "done", 2, 2, [("Lunch", ["Yes"])]),
    row("", False, None, "none", 0, 0, []),
]


class TestRegistrationDeskReport(unittest.TestCase):
    def test_question_progress_is_clamped(self):
        self.assertEqual(rd.question_progress(12, 8), (8, 4))
        self.assertEqual(rd.question_progress(3, 9), (3, 0))
        self.assertEqual(rd.question_progress(None, "x"), (0, 0))
        self.assertEqual(rd.question_progress(-2, -1), (0, 0))

    def test_progress_text(self):
        self.assertEqual(rd.progress_text(12, 8), "8/12")
        self.assertEqual(rd.progress_text(12, 0), "0/12")
        self.assertEqual(rd.progress_text(0, 0), "")
        self.assertEqual(rd.progress_text(None, None), "")

    def test_answers_text_skips_questions_without_answer(self):
        self.assertEqual(rd.answers_text([("Lunch", ["Yes"]), ("Workshops", ["A", " B "]), ("Empty", []), ("None", [None, ""])]),
                         "Lunch: Yes | Workshops: A, B")
        self.assertEqual(rd.answers_text(None), "")

    def test_ticket_summary_per_ticket_and_total(self):
        lines, total = rd.ticket_summary(ROWS, "en")
        self.assertEqual([line["name"] for line in lines], ["(no ticket)", "Visitor", "Volunteer"])
        visitor = lines[1]
        self.assertEqual((visitor["registered"], visitor["present"]), (3, 2))
        self.assertEqual((visitor["done"], visitor["in_progress"], visitor["not_started"]), (1, 1, 1))
        self.assertEqual((visitor["answered"], visitor["unanswered"]), (5, 7))
        self.assertEqual((lines[0]["registered"], lines[0]["done"], lines[0]["unanswered"]), (1, 0, 0))   # no survey: no question
        self.assertEqual((total["registered"], total["present"], total["done"]), (5, 3, 2))
        self.assertEqual((total["answered"], total["unanswered"]), (7, 7))
        self.assertEqual(total["name"], "Total")

    def test_hourly_attendance_counts_only_the_people_present(self):
        hourly = rd.hourly_attendance(ROWS + [row("Visitor", True, None)], "en")           # present without hour: not counted
        self.assertEqual(hourly["hours"], ["2026-10-10 09", "2026-10-10 10"])
        self.assertEqual(hourly["tickets"], ["Visitor", "Volunteer"])
        self.assertEqual(hourly["counts"], {("2026-10-10 09", "Visitor"): 2, ("2026-10-10 10", "Volunteer"): 1})
        self.assertEqual(hourly["by_hour"], {"2026-10-10 09": 2, "2026-10-10 10": 1})
        self.assertEqual(hourly["by_ticket"], {"Visitor": 2, "Volunteer": 1})
        self.assertEqual(hourly["total"], 3)
        self.assertEqual(rd.hourly_attendance([], "en")["total"], 0)

    def test_answers_breakdown(self):
        tickets, questions = rd.answers_breakdown(ROWS, "en")
        self.assertEqual(tickets, ["Visitor", "Volunteer"])
        self.assertEqual([q["label"] for q in questions], ["Lunch", "Mode"])
        lunch = {a["value"]: a for a in questions[0]["answers"]}
        self.assertEqual([a["value"] for a in questions[0]["answers"]], ["No", "Yes", "(no answer)"])
        self.assertEqual(lunch["Yes"]["by_ticket"], {"Visitor": 1, "Volunteer": 1})
        self.assertEqual((lunch["Yes"]["total"], lunch["Yes"]["present"]), (2, 2))
        self.assertEqual((lunch["(no answer)"]["total"], lunch["(no answer)"]["present"]), (1, 0))
        mode = {a["value"]: a for a in questions[1]["answers"]}
        self.assertEqual((mode["On site"]["total"], mode["(no answer)"]["total"]), (1, 2))

    def test_answers_breakdown_multiple_choice_counts_each_value_once(self):
        _tickets, questions = rd.answers_breakdown([row("V", answers=[("Meals", ["Lunch", "Dinner", "Lunch"])])], "en")
        self.assertEqual({a["value"]: a["total"] for a in questions[0]["answers"]}, {"Dinner": 1, "Lunch": 1})

    def test_html_french_by_default_and_english(self):
        html = rd.desk_summary_html(ROWS)
        for text in ("Inscriptions et sondages par type de billet", "Questions non répondues", "dont présents", "(sans billet)",
                     "2026-10-10 09 h"):
            self.assertIn(text, html)
        self.assertNotIn("Registered", html)
        html = rd.desk_summary_html(ROWS, "en_CA")
        for text in ("Registered", "Questions not answered", "of which present", "(no ticket)"):
            self.assertIn(text, html)
        self.assertNotIn("Inscrits", html)

    def test_html_empty_cases(self):
        self.assertIn("Aucune inscription", rd.desk_summary_html([]))
        html = rd.desk_summary_html([row("Visitor")], "en")
        self.assertIn("Nobody is marked present yet.", html)
        self.assertIn("No question is checked", html)

    def test_html_is_escaped(self):
        html = rd.desk_summary_html([row("<b>T</b>", True, "2026-10-10 09", "done", 1, 1, [("<i>Q</i>", ["<script>x</script>"])])], "en")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>T</b>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sort_key_ignores_case_and_accents(self):
        names = ["Éric", "eve", "Ève", "Zoé", "adam", "Émile", "éléonore", "Ésope"]
        ordered = sorted(names, key=rd.sort_key)
        self.assertEqual(ordered, ["adam", "éléonore", "Émile", "Éric", "Ésope", "eve", "Ève", "Zoé"])
        self.assertEqual(rd.sort_key("  Élise "), "elise")
        self.assertEqual(rd.sort_key(None), "")

    def test_is_volunteer_ticket(self):
        self.assertTrue(rd.is_volunteer_ticket("Bénévole"))
        self.assertTrue(rd.is_volunteer_ticket("BENEVOLE VIP"))
        self.assertTrue(rd.is_volunteer_ticket("Bénévoles - présentiel"))
        self.assertFalse(rd.is_volunteer_ticket("Visiteur"))
        self.assertFalse(rd.is_volunteer_ticket(""))
        self.assertFalse(rd.is_volunteer_ticket(False))

    def test_volunteer_table_columns_and_rows(self):
        rows = [
            {"name": "Zoé <b>Tremblay</b>", "partner_id": 7, "registered": "2026-10-01 09:00", "type": "Présentiel",
             "languages": "FR, EN", "arrived": "2026-10-10 08:30", "departed": "", "roles": {"Accueil"}},
            {"name": "Éric Roy", "partner_id": None, "registered": "2026-10-02 10:00", "type": "Virtuel",
             "languages": "", "arrived": "", "departed": "2026-10-10 17:00", "roles": {"Accueil", "Salle 2"}},
        ]
        html = rd.volunteer_table_html(rows, ["Accueil", "Salle 2", "Vestiaire"], "fr_CA", "https://odoo.example")
        for text in ("Bénévole", "Inscrit le", "Langues parlées", "Heure d&#x27;arrivée", "Heure de départ", "Accueil", "Salle 2", "Vestiaire"):
            self.assertIn(text, html)
        self.assertIn('href="https://odoo.example/chat/7"', html)
        self.assertNotIn("<b>Tremblay</b>", html)
        self.assertIn("Zoé &lt;b&gt;Tremblay&lt;/b&gt;", html)
        self.assertIn("Bénévoles listés: 2", html)
        self.assertEqual(html.count("<td>X</td>"), 3)                  # Accueil x2, Salle 2 x1
        english = rd.volunteer_table_html(rows, ["Accueil"], "en_US")
        self.assertIn("Volunteer", english)
        self.assertIn("Arrived at", english)
        self.assertIn("Languages", english)
        self.assertNotIn("Bénévole", english)
        self.assertIn("No volunteer is registered", rd.volunteer_table_html([], [], "en"))


if __name__ == "__main__":
    unittest.main()
