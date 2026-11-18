# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Unit tests of models/registration_desk_report.py (v1.121.0) - NO DEPENDENCY ON ODOO (pure functions), run by run-all.sh (standalone tests):

    python3 -m unittest tests.test_registration_desk_report -v
"""
import re
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

    def test_ticket_summary_unique_people_by_email(self):
        """v1.136.0: « Participants uniques (courriel) »: the same address counts once, per ticket and in total."""
        rows = [dict(row("Visitor"), email="A@x.org"), dict(row("Visitor"), email="a@x.org"), dict(row("Volunteer"), email="a@x.org"),
                dict(row("Volunteer"), email=""), dict(row("Volunteer"), email="b@x.org")]
        lines, total = rd.ticket_summary(rows, "fr")
        self.assertEqual([(line["name"], line["registered"], line["unique"]) for line in lines], [("Visitor", 2, 1), ("Volunteer", 3, 3)])
        self.assertEqual((total["registered"], total["unique"]), (5, 3))                     # a@x.org once in the whole event
        self.assertIn("Participants uniques (courriel)", rd.desk_summary_html(rows, "fr"))

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
        # v1.133.0: people concerned by each question, denominators of « % registered » and « % present ».
        self.assertEqual((questions[0]["registered"], questions[0]["present"]), (4, 3))
        self.assertEqual((questions[1]["registered"], questions[1]["present"]), (3, 2))

    def test_answers_breakdown_multiple_choice_counts_each_value_once(self):
        _tickets, questions = rd.answers_breakdown([row("V", answers=[("Meals", ["Lunch", "Dinner", "Lunch"])])], "en")
        self.assertEqual({a["value"]: a["total"] for a in questions[0]["answers"]}, {"Dinner": 1, "Lunch": 1})

    def test_html_french_by_default_and_english(self):
        html = rd.desk_summary_html(ROWS)
        for text in ("Inscriptions et sondages par type de billet", "Sondages complétés (%)", "dont présents", "(sans billet)",
                     "2026-10-10 09 h"):
            self.assertIn(text, html)
        self.assertNotIn("Registered", html)
        html = rd.desk_summary_html(ROWS, "en_CA")
        for text in ("Registered", "Surveys completed (%)", "of which present", "% present", "(no ticket)"):
            self.assertIn(text, html)
        self.assertNotIn("Inscrits", html)

    def test_percent_text(self):
        self.assertEqual(rd.percent_text(431, 1064), "40,5\u00a0%")
        self.assertEqual(rd.percent_text(1, 3, "en_US"), "33.3%")
        self.assertEqual(rd.percent_text(0, 7), "0,0\u00a0%")
        self.assertEqual(rd.percent_text(5, 0), "")
        self.assertIsInstance(rd.percent_text(1, 2), rd.Number)

    def test_survey_completed_percentage_replaces_the_question_columns(self):
        """v1.133.0: « Questions répondues (%) » and « Questions non répondues (%) » are gone; « Sondages complétés (%) »
        counts the completed surveys out of the registrations that have a survey."""
        html = rd.desk_summary_html(ROWS)
        self.assertNotIn("Questions répondues (%)", html)
        self.assertNotIn("Questions non répondues (%)", html)
        self.assertIn("Sondages complétés (%)", html)
        # Visitor: 1 completed of 3 with a survey -> 33,3 %, right-aligned like the counts; total: 2 of 4 (no survey excluded).
        self.assertIn('text-align:right;">33,3\u00a0%</td>', html)
        self.assertIn("<strong>50,0\u00a0%</strong>", html)
        self.assertIn("50.0%", rd.desk_summary_html(ROWS, "en"))
        self.assertIn("(sans réponse) » : personnes inscrites", html)                          # the note explains it

    def test_answers_table_percentages_and_bold_questions(self):
        """v1.133.0: « % inscrits » and « % présents » next to « Total » and « dont présents »; the questions are in bold."""
        html = rd.desk_summary_html(ROWS)
        self.assertIn(">% inscrits</th>", html)
        self.assertIn(">% présents</th>", html)
        self.assertNotIn("<strong></strong>", html)
        # v1.134.0: each question is framed (its own <tbody>), the question in ONE cell over all its answers.
        self.assertEqual(html.count('<tbody style="border:2px solid'), 2)
        self.assertRegex(html, r'<td rowspan="3"[^>]*><strong>Lunch</strong></td>')
        self.assertRegex(html, r'<td rowspan="2"[^>]*><strong>Mode</strong></td>')
        # Lunch « Yes »: 2 of the 4 registered people concerned -> 50,0 %; 2 present of those same 4 -> 50,0 % (v1.134.0:
        # out of all the people concerned, no longer out of the people present only, which gave 100 % too often).
        cells = re.findall(r"<td[^>]*>([^<]*)</td>", html.split("<strong>Lunch</strong>")[1].split("</tr>")[1])
        self.assertEqual(cells, ["Yes", "1", "1", "2", "50,0\u00a0%", "2", "50,0\u00a0%"])

    def test_tables_have_header_colour_and_stripes(self):
        """v1.134.0: dark header with white text, one line out of two in pale grey, a border on every cell."""
        html = rd.desk_summary_html(ROWS)
        self.assertIn("background-color:%s;color:%s" % (rd.HEAD_BG, rd.HEAD_FG), html)
        self.assertIn("background-color:%s" % rd.STRIPE_BG, html)
        self.assertNotRegex(html, r"<t[dh]>")                                                  # every cell is styled
        volunteers = rd.volunteer_table_html([{"name": "A"}, {"name": "B"}], [], "fr")
        self.assertIn("background-color:%s;color:%s" % (rd.HEAD_BG, rd.HEAD_FG), volunteers)
        self.assertIn("background-color:%s" % rd.STRIPE_BG, volunteers)

    def test_weekly_registrations(self):
        """v1.134.0: registrations per ISO week, empty weeks in between listed, cumulative total."""
        rows = [dict(row("Visitor"), registered="2026-11-02 10:00"), dict(row("Visitor"), registered="2026-11-08 23:59"),
                dict(row("Volunteer"), registered="2026-11-17 15:59"), dict(row("Visitor"), registered="")]
        weekly = rd.weekly_registrations(rows, "fr")
        self.assertEqual(weekly["tickets"], ["Visitor", "Volunteer"])
        self.assertEqual([(w["week"], w["total"], w["cumulative"]) for w in weekly["weeks"]], [(45, 2, 2), (46, 0, 2), (47, 1, 3)])
        self.assertEqual(str(weekly["weeks"][0]["monday"]), "2026-11-02")
        self.assertEqual(str(weekly["weeks"][0]["sunday"]), "2026-11-08")
        html = rd.desk_summary_html(rows, "fr")
        self.assertIn("Inscriptions par semaine", html)
        self.assertIn("Semaine 45 : 2026-11-02 au 2026-11-08", html)
        self.assertIn("Week 47: 2026-11-16 to 2026-11-22", rd.desk_summary_html(rows, "en"))
        self.assertEqual(rd.weekly_registrations([row("V")])["weeks"], [])                    # no date: no section

    def test_answers_that_differ_by_case_or_accents_are_grouped(self):
        rows = [row("Visitor", answers=[("Diet", ["Végétarien"])]), row("Visitor", answers=[("Diet", ["végétarien"])]),
                row("Volunteer", True, answers=[("Diet", ["Végétarien "])]), row("Visitor", answers=[("Diet", ["vegetarien"])]),
                row("Visitor", answers=[("Diet", ["végétarienne"])])]
        _tickets, questions = rd.answers_breakdown(rows, "fr")
        answers = {a["value"]: a for a in questions[0]["answers"]}
        self.assertEqual(sorted(answers), ["Végétarien", "végétarienne"])
        self.assertEqual((answers["Végétarien"]["total"], answers["Végétarien"]["present"]), (4, 1))
        self.assertEqual(answers["Végétarien"]["by_ticket"], {"Visitor": 3, "Volunteer": 1})

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
        none = {"arrival": None, "departure": None}
        self.assertEqual(found, dict(none, roles=[4, 3], languages=2, type=5))               # the on-site roles first
        # A roles question that speaks of « virtuel » is never taken for the type question.
        self.assertEqual(rd.find_volunteer_questions(questions[:4]), dict(none, roles=[4, 3], languages=2, type=None))
        # The type question can also be recognized by its title alone.
        by_title = rd.find_volunteer_questions([{"id": 9, "title": "En virtuel ou pas ?", "choices": ["Oui", "Non"], "is_choice": True}])
        self.assertEqual(by_title, dict(none, roles=[], languages=None, type=9))
        self.assertEqual(rd.find_volunteer_questions([]), dict(none, roles=[], languages=None, type=None))

    def test_find_arrival_and_departure_questions(self):
        def question(number, title, choices=()):
            return {"id": number, "title": title, "choices": list(choices), "is_choice": bool(choices)}
        found = rd.find_volunteer_questions([question(1, "Votre département"), question(2, "Heure d'arrivée prévue"),
                                             question(3, "Heure de départ :"), question(4, "Langues parlées", ["Français"])])
        self.assertEqual((found["arrival"], found["departure"], found["languages"]), (2, 3, 4))
        found = rd.find_volunteer_questions([question(1, "À quelle heure arriverez-vous ?", ["8 h", "9 h"]),
                                             question(2, "Quand partirez-vous ?", ["16 h", "17 h"])])
        self.assertEqual((found["arrival"], found["departure"], found["type"]), (1, 2, None))
        found = rd.find_volunteer_questions([question(1, "Votre département"), question(2, "Départements visités")])
        self.assertEqual((found["arrival"], found["departure"]), (None, None))                # « département » is not « départ »

    def test_volunteer_export_sheets(self):
        import datetime
        groups = [{"title": "Rôles (en présentiel)", "choices": ["Accueil", "Autre"]}, {"title": "Rôles (en virtuel)", "choices": ["Modérateur", "Autre"]}]
        rows = [
            {"name": "Zoé Tremblay", "email": "zoe@exemple.org", "ticket": "Bénévole", "registered": "2026-10-01 09:00",
             "registered_at": datetime.datetime(2026, 10, 1, 9, 0), "survey": "done", "type": "Présentiel", "languages": "Français, Anglais",
             "languages_list": ["Français", "Anglais"], "arrived": "8 h", "departed": "16 h",
             "roles": [["Accueil", "Autre", "Photographe"], []], "extra": ["Oui"]},
            {"name": "Éric Roy", "email": "", "ticket": "Bénévole", "registered": "2026-10-02 10:00", "survey": "not_started",
             "type": "", "languages": "", "arrived": "", "departed": "", "roles": [[], []], "extra": []},
        ]
        sheets = rd.volunteer_export_sheets(rows, groups, "fr_CA", extra_columns=["Dîner"])
        self.assertEqual([title for title, _header, _lines in sheets], ["Bénévoles", "Rôles", "Langues"])
        _title, header, lines = sheets[0]
        self.assertEqual(header, ["Bénévole", "Courriel", "Billet", "Inscrit le", "Sondage", "Type", "Présentiel", "Langues parlées", "Heure d'arrivée",
                                  "Heure de départ", "Dîner", "Accueil", "Autre", "Modérateur", "Autre (2)", "Autres rôles (texte)",
                                  "Nombre de rôles"])
        self.assertEqual(len(set(header)), len(header))                                       # unique names: needed by a pivot table
        self.assertEqual(lines[0], ["Zoé Tremblay", "zoe@exemple.org", "Bénévole", datetime.datetime(2026, 10, 1, 9, 0), "Complété",
                                    "Présentiel", 1, "Français, Anglais", "8 h", "16 h", "Oui", 1, 1, None, None, "Photographe", 3])
        self.assertEqual(lines[1][3], "2026-10-02 10:00")                                      # no datetime given: the text
        self.assertEqual(lines[1][-6:], [None, None, None, None, "", 0])                      # v1.135.0: numbers, empty cells
        self.assertEqual(sum(line[11] or 0 for line in lines), 1)                              # the column can be summed
        self.assertEqual([line[6] for line in lines], [1, None])                               # v1.136.0: « Présentiel »
        self.assertTrue(all(len(line) == len(header) for line in lines))
        _title, header, lines = sheets[1]
        self.assertEqual(header, ["Bénévole", "Courriel", "Type", "Langues parlées", "Sondage", "Question", "Rôle"])
        self.assertEqual([line[-2:] for line in lines], [["Rôles (en présentiel)", "Accueil"], ["Rôles (en présentiel)", "Autre"],
                                                         ["Rôles (en présentiel)", "Photographe"], ["", "(aucun rôle)"]])
        _title, header, lines = sheets[2]
        self.assertEqual(lines, [["Zoé Tremblay", "Présentiel", "Complété", "Français"], ["Zoé Tremblay", "Présentiel", "Complété", "Anglais"],
                                 ["Éric Roy", "", "Non commencé", "(non précisé)"]])
        english = rd.volunteer_export_sheets(rows, groups, "en_US")
        self.assertEqual([title for title, _header, _lines in english], ["Volunteers", "Roles", "Languages"])
        self.assertEqual(rd.volunteer_export_sheets([], [], "fr")[0][2], [])

    def test_volunteer_export_opens_in_a_spreadsheet(self):
        """The sheets are written with openpyxl (as the module does) and read back: flat tables, real dates."""
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl is not installed")
        import datetime
        import io
        rows = [{"name": "Zoé", "registered_at": datetime.datetime(2026, 10, 1, 9, 0), "survey": "done", "roles": [["Accueil"]],
                 "languages_list": ["Français"]}]
        workbook = openpyxl.Workbook()
        workbook.remove(workbook.active)
        for title, header, lines in rd.volunteer_export_sheets(rows, [{"title": "Rôles", "choices": ["Accueil"]}], "fr"):
            sheet = workbook.create_sheet(title[:31])
            sheet.append(header)
            for line in lines:
                sheet.append(line)
        buffer = io.BytesIO()
        workbook.save(buffer)
        again = openpyxl.load_workbook(io.BytesIO(buffer.getvalue()))
        self.assertEqual(again.sheetnames, ["Bénévoles", "Rôles", "Langues"])
        self.assertEqual(again["Bénévoles"]["D2"].value, datetime.datetime(2026, 10, 1, 9, 0))
        self.assertEqual(again["Rôles"]["G2"].value, "Accueil")

    def test_role_kind_and_deduced_type(self):
        self.assertEqual(rd.role_kind("Rôles pendant l'événement (en présentiel) ?"), "on_site")
        self.assertEqual(rd.role_kind("Rôles pendant l'événement (en virtuel) ?"), "online")
        self.assertIsNone(rd.role_kind("Rôles"))
        self.assertIsNone(rd.role_kind("Rôles en présentiel ou en virtuel"))
        self.assertEqual(rd.deduced_type(["online", "on_site", "online"]), "Présentiel, Virtuel")
        self.assertEqual(rd.deduced_type(["online"], "en"), "Online")
        self.assertEqual(rd.deduced_type([]), "")

    def test_answers_cell_html(self):
        """v1.135.0: the answers are a link to every answer of the person, sortable without case or accents, escaped."""
        html = rd.answers_cell_html("Dîner: <b>Oui</b>", "/rlq_survey_report/answers/7")
        self.assertIn('href="/rlq_survey_report/answers/7"', html)
        self.assertIn('data-rlq-sort="diner: <b>oui</b>"'.replace("<", "&lt;").replace(">", "&gt;"), html)
        self.assertNotIn("<b>", html)
        self.assertEqual(rd.answers_cell_html("", None), "")
        self.assertIn("href", rd.answers_cell_html("", "/rlq_survey_report/answers/8"))          # answered, nothing shown: link
        self.assertNotIn("href", rd.answers_cell_html("Oui", None))

    def test_volunteer_survey_cell_links_to_the_answers(self):
        html = rd.volunteer_table_html([{"name": "A", "survey": "done", "answers_url": "/rlq_survey_report/answers/3"},
                                        {"name": "B", "survey": "not_started"}], [], "fr")
        self.assertIn('<a href="/rlq_survey_report/answers/3" target="_blank">Complété</a>', html)
        self.assertEqual(html.count("/rlq_survey_report/answers/"), 1)

    def test_role_numbers(self):
        """v1.135.0: 1 instead of « X » in the spreadsheet; the free text of « Autre » counts 1 and is returned apart."""
        self.assertEqual(rd.role_numbers(["Accueil", "Salle 2", "Autre"], ["accueil"]), ([1, None, None], []))
        self.assertEqual(rd.role_numbers(["Accueil", "Autre"], ["Photographe"]), ([None, 1], ["Photographe"]))
        self.assertEqual(rd.role_numbers(["A", "B"], ["libre"]), ([None, 1], ["libre"]))
        self.assertEqual(rd.role_numbers([], ["x"]), ([], ["x"]))

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
                     "Complété", "Commencé", "Non commencé", "Bénévoles listés: 3", "Une &lt;note&gt;", "Présentiel",
                     "Participants uniques (courriel): "):
            self.assertIn(text, html)
        self.assertIn('<a href="/rlq_survey_report/chat/7" target="_blank">Zoé &lt;b&gt;Tremblay&lt;/b&gt;</a>', html)
        self.assertNotIn("<b>Tremblay</b>", html)
        self.assertIn('colspan="2"', html)
        self.assertIn('rowspan="2"', html)
        # v1.136.0: « 1 » instead of « X » (roles: Accueil x2, Salle 2, Modérateur), plus « 1 » in « Présentiel ».
        self.assertNotIn(">X</span>", html)
        self.assertEqual(html.count(">1</span>"), 4 + 1)                                       # 4 roles + Zoé on site
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
        french = rd.program_footer("rlq_survey_report", "18.0.1.124.0", "2026-11-16 21:15:02 EST", "America/Toronto")
        self.assertEqual(french, '<p class="text-muted small">rlq_survey_report 18.0.1.124.0 - affiché le 2026-11-16 21:15:02 EST '
                                 '(heure locale, America/Toronto)</p>')
        english = rd.program_footer("rlq_survey_report", "18.0.1.124.0", "2026-11-16 21:15:02 EST", "", "en_US")
        self.assertIn("shown on 2026-11-16 21:15:02 EST (local time)", english)
        self.assertNotIn("<b>", rd.program_footer("p", "v", "<b>x</b>", "<b>z</b>"))
        # v1.137.0: the time of the last change of the module, not the time of the display.
        self.assertIn("modifié le 2026-11-17 19:30:00 HNE (heure locale, America/Toronto)",
                      rd.program_footer("p", "v", "2026-11-17 19:30:00 HNE", "America/Toronto", "fr", modified=True))
        self.assertIn("modified on", rd.program_footer("p", "v", "x", "", "en", modified=True))

    def test_topics_of_interest(self):
        """v1.138.0: topics counted per question, free answers grouped, ranked by count; only numbers in the page."""
        self.assertTrue(rd.is_visitor_ticket("Visiteurs (gratuit)"))
        self.assertTrue(rd.is_visitor_ticket("VISITOR"))
        self.assertFalse(rd.is_visitor_ticket("Bénévole"))
        questions = [{"title": "Sujets <i>souhaités</i>", "choices": ["Sécurité", "Docker", "Autre"]}, {"title": "Idées", "choices": []}]
        people = [{"ticket": "Visiteur", "questions": {0, 1}, "answers": {0: ["Docker", "securite", "Docker"], 1: ["Rust"]}},
                  {"ticket": "Visiteur", "questions": {0, 1}, "answers": {0: ["docker", " Rust  "]}},
                  {"ticket": "Bénévole", "questions": {0}, "answers": {}},
                  {"ticket": "Bénévole", "questions": set(), "answers": {}}]
        first, second = rd.topics_breakdown(people, questions)
        self.assertEqual((first["concerned"], first["respondents"]), (3, 2))
        self.assertEqual([(t["topic"], t["count"], t["free"]) for t in first["topics"]],
                         [("Docker", 2, False), ("Rust", 1, True), ("Sécurité", 1, False)])
        self.assertEqual(first["topics"][0]["by_ticket"], {"Visiteur": 2})
        self.assertEqual((second["concerned"], second["respondents"]), (2, 1))
        html = rd.topics_html([first, second], ["Bénévole", "Visiteur"], "fr", "visitors")
        for text in ("Sujets d&#x27;intérêt des visiteurs", "Répondants : 2 sur 3", "Rust (texte libre)", ">% des répondants</th>",
                     ">Visiteur</th>", "100,0\u00a0%"):
            self.assertIn(text, html)
        self.assertNotIn("<i>", html)
        self.assertNotIn("@", html)
        self.assertIn("Aucune question", rd.topics_html([], [], "fr"))
        self.assertIn("No registration", rd.topics_html(None, [], "en"))
        self.assertIn("Topics of interest of the audience", rd.topics_html([first], ["V"], "en"))

    def test_ticket_scopes_of_topics(self):
        """v1.139.0: visitors, volunteers and sponsors tickets for « Topics of interest »."""
        self.assertTrue(rd.ticket_in_scope("Bénévoles", "volunteers"))
        self.assertTrue(rd.ticket_in_scope("Commanditaire Or", "sponsors"))
        self.assertTrue(rd.ticket_in_scope("Sponsor", "sponsors"))
        self.assertFalse(rd.ticket_in_scope("Visiteur", "sponsors"))
        self.assertTrue(rd.ticket_in_scope("Visiteur", "visitors"))
        self.assertTrue(rd.ticket_in_scope("Tout", "all"))
        for scope, title in (("volunteers", "Sujets d&#x27;intérêt des bénévoles"), ("sponsors", "commanditaires"),
                             ("tickets", "billets choisis")):
            self.assertIn(title, rd.topics_html([], [], "fr", scope))

    def test_answer_filter_of_the_desk(self):
        """v1.139.0: filter « Answer »: one answer of a desk question, or « (no answer) », accents and case ignored."""
        answers = [("Serez-vous présent à l'ÉTS ?", ["Oui"]), ("Dîner", [])]
        self.assertTrue(rd.answer_matches(answers, rd.sort_key("Serez-vous présent à l'ETS ?"), "oui"))
        self.assertFalse(rd.answer_matches(answers, rd.sort_key("Serez-vous présent à l'ÉTS ?"), "non"))
        self.assertTrue(rd.answer_matches(answers, rd.sort_key("Dîner"), ""))                 # (no answer)
        self.assertFalse(rd.answer_matches(answers, rd.sort_key("Autre question"), ""))       # not in the survey
        self.assertFalse(rd.answer_matches([], "x", ""))

    def test_answers_page_shows_the_name(self):
        """v1.139.0: « See the answers »: the name in the title of the tab and at the top, sections, escaped."""
        html = rd.answers_page_html("Zoé <b>Tremblay</b>", "Sondage visiteurs", "done", "2026-11-17 20:10 HNE",
                                    [{"title": "Page 1", "questions": [{"title": "Dîner ?", "values": ["Oui"]},
                                                                       {"title": "Commentaire", "values": ["ligne 1\nligne 2"]},
                                                                       {"title": "Vide", "values": []}]}],
                                    "/survey/print/a?answer_token=b", "fr")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<title>Réponses de Zoé &lt;b&gt;Tremblay&lt;/b&gt; - Sondage visiteurs</title>", html)
        self.assertIn("<h1>Réponses de Zoé &lt;b&gt;Tremblay&lt;/b&gt;</h1>", html)
        for text in ("Complété", "Soumis le", "2026-11-17 20:10 HNE", "<h2>Page 1</h2>", "<li>Oui</li>", "ligne 1<br/>ligne 2",
                     "(sans réponse)", 'href="/survey/print/a?answer_token=b"', "Renseignements personnels"):
            self.assertIn(text, html)
        self.assertNotIn("<b>Tremblay", html)
        self.assertIn("<title>Answers of A - S</title>", rd.answers_page_html("A", "S", lang="en"))

    def test_expertise_table_and_export(self):
        """v1.137.0: « Expertises des bénévoles »: one column per choice (1), a text column, totals, free text of « Autre »."""
        columns = [{"title": "Expertises", "choices": ["Python", "Réseau", "Autre"]}, {"title": "Commentaire", "choices": []}]
        rows = [{"name": "Zoé", "survey": "done", "email": "z@x.org", "answers_url": "/rlq_survey_report/answers/4",
                 "answers": [["python", "Kubernetes"], ["J'aime <b>Linux</b>"]]},
                {"name": "Éric", "survey": "not_started", "email": "Z@x.org", "answers": [[], []]}]
        self.assertEqual(rd.expertise_totals(rows, columns), [2, 1, 0, 1, 1])
        html = rd.expertise_table_html(rows, columns, "fr")
        for text in ("Expertises des bénévoles", 'colspan="3"', ">Python</th>", ">Commentaire</th>", "Kubernetes",
                     '<a href="/rlq_survey_report/answers/4" target="_blank">Complété</a>', "Participants uniques (courriel): 1"):
            self.assertIn(text, html)
        self.assertNotIn("<b>Linux</b>", html)
        self.assertIn("Aucune question de sondage", rd.expertise_table_html(rows, [], "fr"))
        self.assertIn("No volunteer", rd.expertise_table_html([], columns, "en"))
        title, header, lines = rd.expertise_export_sheet(rows, columns, "fr")
        self.assertEqual(title, "Expertises des bénévoles")
        self.assertEqual(header, ["Bénévole", "Courriel", "Billet", "Sondage", "Expertises - Python", "Expertises - Réseau",
                                  "Expertises - Autre", "Expertises (texte libre)", "Commentaire"])
        self.assertEqual(lines[0][4:], [1, None, 1, "Kubernetes", "J'aime <b>Linux</b>"])
        self.assertEqual(lines[1][4:], [None, None, None, "", ""])

    # ------------------------------------------------------------------ v1.131.0

    def test_zone_label_french_abbreviations(self):
        self.assertEqual(rd.zone_label("EST", "fr_CA"), "HNE")
        self.assertEqual(rd.zone_label("EDT", "fr_CA"), "HAE")
        self.assertEqual(rd.zone_label("PDT", "fr_FR"), "HAP")
        self.assertEqual(rd.zone_label("EST", "en_US"), "EST")
        self.assertEqual(rd.zone_label("UTC", "fr_CA"), "UTC")
        self.assertEqual(rd.zone_label("", "fr_CA"), "")

    def test_local_stamp_follows_the_change_of_time(self):
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
        except ImportError:                                            # Python 3.8: no zoneinfo, dateutil from Odoo
            from dateutil.tz import gettz as ZoneInfo
        zone = ZoneInfo("America/Toronto")
        winter = datetime(2026, 11, 17, 11, 14, tzinfo=zone)
        summer = datetime(2026, 10, 10, 9, 0, tzinfo=zone)
        self.assertEqual(rd.local_stamp(winter, "%Y-%m-%d %H:%M", "fr_CA"), "2026-11-17 11:14 HNE")
        self.assertEqual(rd.local_stamp(summer, "%Y-%m-%d %H:%M", "fr_CA"), "2026-10-10 09:00 HAE")
        self.assertEqual(rd.local_stamp(winter, "%H:%M", "en_US"), "11:14 EST")
        self.assertEqual(rd.local_stamp(datetime(2026, 1, 1, 8, 0), "%H:%M", "fr_CA"), "08:00")
        self.assertEqual(rd.local_stamp(None), "")

    def test_person_cell_sorts_without_case_or_accents(self):
        names = ["Zoé", "éric", "Denis", "Élise", "fanny", "denis"]
        cells = [rd.person_cell_html(name, "/rlq_survey_report/chat/%d" % i) for i, name in enumerate(names)]
        ordered = [names[cells.index(cell)] for cell in sorted(cells)]       # what the web client does: plain string order
        self.assertEqual([rd.sort_key(n) for n in ordered], sorted(rd.sort_key(n) for n in names))
        self.assertIn('href="/rlq_survey_report/chat/0"', cells[0])
        self.assertEqual(rd.person_cell_html("Ann", None), '<span data-rlq-sort="ann">Ann</span>')
        hostile = rd.person_cell_html('"><script>x</script>', "javascript:\"x")
        self.assertNotIn("<script>", hostile)
        self.assertNotIn('"x"', hostile)

    def test_arrival_and_departure_questions_found(self):
        found = rd.find_volunteer_questions([
            {"id": 1, "title": "À quelle heure pensez-vous arriver ?", "choices": [], "is_choice": False},
            {"id": 2, "title": "Heure de départ prévue?", "choices": [], "is_choice": False},
            {"id": 3, "title": "Département", "choices": [], "is_choice": False}])
        self.assertEqual((found["arrival"], found["departure"]), (1, 2))

    def test_volunteer_totals_in_header_and_footer(self):
        rows = self._volunteers()
        groups = [{"title": "Rôles", "choices": ["Accueil", "Technique", "Autre"]}]
        totals = rd.volunteer_column_totals(rows, groups)
        self.assertEqual(totals[0], len(rows))
        self.assertEqual(len(totals), 8 + 3)                                     # v1.136.0: + « Présentiel »
        html = rd.volunteer_table_html(rows, groups, "fr")
        self.assertIn("<tfoot>", html)
        self.assertEqual(html.count("Total : %d" % len(rows)), 2)        # top (header) and bottom (footer)

    def test_on_site_and_unique_people(self):
        """v1.136.0: who will be there in person, and the number of different people by e-mail address."""
        self.assertTrue(rd.is_on_site("Présentiel"))
        self.assertTrue(rd.is_on_site("Présentiel, Virtuel"))
        self.assertTrue(rd.is_on_site("Hybride"))
        self.assertFalse(rd.is_on_site("Virtuel"))
        self.assertFalse(rd.is_on_site(""))
        rows = [{"email": "A@x.org"}, {"email": " a@x.org "}, {"email": "b@x.org"}, {"email": ""}, {}]
        self.assertEqual(rd.unique_people(rows), 4)                          # a@x.org once, two rows without address

    def test_reconciliation(self):
        self.assertEqual(rd.reconciliation_html([]), "")
        html = rd.reconciliation_html([{"survey": "S<1>", "survey_done": 12, "matched_done": 9, "duplicates": 1,
                                        "cancelled_done": 1, "unmatched_done": 1, "tests": 3}], "fr")
        self.assertIn("Pourquoi", html)
        self.assertIn("S&lt;1&gt;", html)
        self.assertIn(">12<", html)


if __name__ == "__main__":
    unittest.main()
