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

    def test_find_volunteer_questions(self):
        questions = [
            {"id": 1, "title": "Votre nom", "choices": [], "is_choice": False},
            {"id": 2, "title": "Langues parlées", "choices": ["Français", "Anglais", "Autre"], "is_choice": True},
            {"id": 3, "title": "Rôles pendant l'événement (en virtuel) ?", "choices": ["Modérateur en virtuel", "Autre"], "is_choice": True},
            {"id": 4, "title": "RÔLES pendant l'événement (en présentiel) ?", "choices": ["Accueil", "Salle 2"], "is_choice": True},
            {"id": 5, "title": "Comment participerez-vous ?", "choices": ["Sur place", "En ligne"], "is_choice": True},
        ]
        found = rd.find_volunteer_questions(questions)
        self.assertEqual(found, {"roles": [4, 3], "languages": 2, "type": 5})                # the on-site roles first
        # A roles question that speaks of « virtuel » is never taken for the type question.
        self.assertEqual(rd.find_volunteer_questions(questions[:4]), {"roles": [4, 3], "languages": 2, "type": None})
        # The type question can also be recognized by its title alone.
        by_title = rd.find_volunteer_questions([{"id": 9, "title": "En virtuel ou pas ?", "choices": ["Oui", "Non"], "is_choice": True}])
        self.assertEqual(by_title, {"roles": [], "languages": None, "type": 9})
        self.assertEqual(rd.find_volunteer_questions([]), {"roles": [], "languages": None, "type": None})

    def test_role_kind_and_deduced_type(self):
        self.assertEqual(rd.role_kind("Rôles pendant l'événement (en présentiel) ?"), "on_site")
        self.assertEqual(rd.role_kind("Rôles pendant l'événement (en virtuel) ?"), "online")
        self.assertIsNone(rd.role_kind("Rôles"))
        self.assertIsNone(rd.role_kind("Rôles en présentiel ou en virtuel"))
        self.assertEqual(rd.deduced_type(["online", "on_site", "online"]), "Présentiel, Virtuel")
        self.assertEqual(rd.deduced_type(["online"], "en"), "Online")
        self.assertEqual(rd.deduced_type([]), "")

    def test_role_cells(self):
        self.assertEqual(rd.role_cells(["Accueil", "Salle 2", "Autre"], ["accueil"]), ["X", "", ""])
        self.assertEqual(rd.role_cells(["Accueil", "Autre"], ["Autre", "Photographe"]), ["", "Photographe"])   # free text replaces X
        self.assertEqual(rd.role_cells(["A", "B"], ["B", "libre"]), ["", "X libre"])                         # no « Autre » column
        self.assertEqual(rd.role_cells(["A", "B"], []), ["", ""])
        self.assertEqual(rd.role_cells([], ["x"]), [])

    def _volunteers(self):
        return [
            {"name": "Zoé <b>Tremblay</b>", "chat_url": "/rlq_survey_report/chat/7", "registered": "2026-10-01 09:00", "survey": "done",
             "type": "Présentiel", "languages": "Français, Anglais", "arrived": "2026-10-10 08:30", "departed": "",
             "roles": [["Accueil"], []], "extra": ["Oui"]},
            {"name": "éric Roy", "chat_url": None, "registered": "2026-10-02 10:00", "survey": "not_started",
             "type": "", "languages": "", "arrived": "", "departed": "2026-10-10 17:00", "roles": [[], []], "extra": [""]},
            {"name": "Eve Côté", "chat_url": None, "registered": "2026-09-30 10:00", "survey": "in_progress",
             "type": "Virtuel", "languages": "anglais", "arrived": "", "departed": "",
             "roles": [["Accueil", "Salle 2"], ["Modérateur"]], "extra": [""]},
        ]

    def test_sort_volunteer_rows(self):
        rows = self._volunteers()

        def names(sort_by, descending=False):
            return [row["name"].split()[0] for row in rd.sort_volunteer_rows(rows, sort_by, descending)]
        self.assertEqual(names("name"), ["éric", "Eve", "Zoé"])                                # case and accents ignored
        self.assertEqual(names("name", True), ["Zoé", "Eve", "éric"])
        self.assertEqual(names("registered"), ["Eve", "Zoé", "éric"])
        self.assertEqual(names("survey"), ["Zoé", "Eve", "éric"])                              # completed, started, not started
        self.assertEqual(names("languages"), ["Eve", "Zoé", "éric"])                           # « anglais » before « Français »; empty last
        self.assertEqual(names("arrived"), ["Zoé", "éric", "Eve"])                             # empty dates last, then by name
        self.assertEqual(names("roles"), ["Eve", "Zoé", "éric"])                               # most roles first
        self.assertEqual(names("unknown"), ["éric", "Eve", "Zoé"])

    def test_volunteer_table(self):
        groups = [{"title": "Rôles (en présentiel)", "choices": ["Accueil", "Salle 2"]}, {"title": "Rôles (en virtuel)", "choices": ["Modérateur"]}]
        html = rd.volunteer_table_html(self._volunteers(), groups, "fr_CA", extra_columns=["Dîner"], notes=["Une <note>"])
        for text in ("Bénévole", "Inscrit le", "Sondage", "Langues parlées", "Heure d&#x27;arrivée", "Heure de départ", "Dîner",
                     "Rôles (en présentiel)", "Rôles (en virtuel)", "Accueil", "Salle 2", "Modérateur",
                     "Complété", "Commencé", "Non commencé", "Bénévoles listés: 3", "Une &lt;note&gt;"):
            self.assertIn(text, html)
        self.assertIn('<a href="/rlq_survey_report/chat/7" target="_blank">Zoé &lt;b&gt;Tremblay&lt;/b&gt;</a>', html)
        self.assertNotIn("<b>Tremblay</b>", html)
        self.assertIn('colspan="2"', html)
        self.assertIn('rowspan="2"', html)
        self.assertEqual(html.count(">X</span>"), 4)                                           # Accueil x2, Salle 2, Modérateur
        english = rd.volunteer_table_html(self._volunteers(), groups, "en_US")
        for text in ("Volunteer", "Registered on", "Survey", "Languages spoken", "Arrived at", "Left at", "Completed", "Not started"):
            self.assertIn(text, english)
        self.assertNotIn("Bénévole", english)
        self.assertIn("No volunteer to show", rd.volunteer_table_html([], lang="en"))
        self.assertIn("Aucun bénévole", rd.volunteer_table_html([], notes=["n"]))

    def test_volunteer_table_escapes_answers_that_look_like_links(self):
        row = dict(self._volunteers()[0], type='<a href="https://evil.example">x</a>', languages="<script>x</script>")
        html = rd.volunteer_table_html([row], [], "fr")
        self.assertNotIn("evil.example\">x</a>", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;a href=", html)

    def test_program_footer(self):
        self.assertEqual(rd.program_footer("rlq_survey_report", "18.0.1.123.0"),
                         '<p class="text-muted small">rlq_survey_report 18.0.1.123.0</p>')
        self.assertIn("rlq_survey_report ?", rd.program_footer("rlq_survey_report", None))


if __name__ == "__main__":
    unittest.main()
