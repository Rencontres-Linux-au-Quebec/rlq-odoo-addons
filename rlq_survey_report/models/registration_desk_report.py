# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
registration_desk_report.py
===========================

Pure functions (NO Odoo import) of the registration desk (v1.121.0), testable without Odoo (tests/test_registration_desk_report.py,
run by run-all.sh):

  question_progress(total, answered)  -> (answered, not answered), clamped: never negative, never more answered than questions.
  progress_text(total, answered)      -> « 8/12 », or « » when the survey has no question.
  answers_text(answers)               -> « Lunch: Yes | On site: No » from [(label, [values])]; questions without answer left out.
  ticket_summary(rows)                -> one line per ticket + the total line (registered, present, surveys, questions).
  weekly_registrations(rows)          -> registrations per ISO week (number, Monday to Sunday) and per ticket, with the cumulative.
  hourly_attendance(rows)             -> (hours, tickets, counts, totals per hour, totals per ticket, total) of the people present.
                                         Hours are LOCAL hours, formatted by the caller (never UTC).
  answers_breakdown(rows)             -> per question shown at the desk, per answer: count per ticket, total, of which present.
  desk_summary_html(rows, lang)       -> the three tables above, in ONE language (French or English), everything escaped.
  sort_key(text)                      -> sort key that ignores case and accents (« Élise » with the « e »).
  find_volunteer_questions(questions) -> the roles, languages and type questions of a volunteer survey, found by their wording.
  person_cell_html(name, chat_url)    -> the name of a participant, link to talk to the person in Odoo, sortable without case or accents.
  reconciliation_html(items, lang)    -> why the « completed » of the survey differs from the one of the event.
  volunteer_column_totals(rows, ...)  -> one total per column of the volunteers' table (header and footer lines).
  volunteer_table_html(rows, ...)     -> the table of the volunteers' coordinator (one column per role), everything escaped.
  volunteer_export_sheets(rows, ...)  -> the three flat sheets of the volunteers' spreadsheet (pivot tables).
  zone_label(abbreviation, lang)      -> « HNE » / « HAE » in French for « EST » / « EDT » (North American zones), unchanged otherwise.
  program_footer(program, version...) -> « rlq_survey_report 18.0.1.124.0 - affiché le <local date and time> » under the screens.

A row describes ONE registration (built by models/event_registration_desk.py):

  {"ticket": "Visitor", "present": True, "hour": "2026-10-10 09",      # hour: local hour of the check-in, None when not present
   "survey_state": "done" / "in_progress" / "not_started" / "none",
   "questions": 12, "answered": 8,
   "answers": [("Lunch", ["Yes"]), ("On site or online", [])]}
"""
import re
import unicodedata
from datetime import date, timedelta
from html import escape

DEFAULT_LANG = "fr_CA"
VOLUNTEER_WORD = "benevol"   # « Bénévole », « Bénévoles » ... once accents and case are ignored
SURVEY_STATES = ("done", "in_progress", "not_started")

TEXTS = {
    "fr": {
        "no_ticket": "(sans billet)",
        "no_registration": "Aucune inscription pour cet événement.",
        "tickets_title": "Inscriptions et sondages par type de billet",
        "ticket": "Billet",
        "registered": "Inscrits",
        "unique": "Participants uniques (courriel)",
        "present": "Présents",
        "done": "Sondages complétés",
        "in_progress": "Sondages commencés",
        "not_started": "Sondages non commencés",
        "answered": "Questions répondues (%)",
        "unanswered": "Questions non répondues (%)",
        "done_pct": "Sondages complétés (%)",
        "registered_pct": "% inscrits",
        "present_pct": "% présents",
        "pct_note": "« Sondages complétés (%) » : sondages complétés sur les inscriptions qui ont un sondage. « % inscrits » : "
                    "personnes inscrites qui ont donné cette réponse, sur toutes les personnes inscrites concernées par la "
                    "question ; « % présents » : personnes présentes qui ont donné cette réponse, sur ce même total. Un choix "
                    "multiple peut dépasser 100 % au total.",
        "total": "Total",
        "weeks_title": "Inscriptions par semaine",
        "week": "Semaine",
        "week_label": "Semaine %(week)d : %(monday)s au %(sunday)s",
        "cumulative": "Cumul",
        "weeks_note": "Semaines ISO (du lundi au dimanche), selon la date d'inscription en heure locale. Les inscriptions "
                      "annulées ne sont pas comptées.",
        "hours_title": "Personnes marquées présentes, par heure",
        "hour": "Heure",
        "no_presence": "Personne n'est encore marqué présent.",
        "answers_title": "Réponses aux questions affichées au bureau d'inscription",
        "question": "Question",
        "answer": "Réponse",
        "of_which_present": "dont présents",
        "no_answer": "(sans réponse)",
        "no_answer_note": "« (sans réponse) » : personnes inscrites qui n'ont pas de réponse à cette question (sondage non "
                          "commencé, question sautée, ou question non affichée parce qu'elle dépend d'une autre réponse). Les "
                          "réponses écrites qui ne diffèrent que par les majuscules ou les accents sont regroupées.",
        "no_desk_question": "Aucune question n'est cochée « Afficher au bureau d'inscription » dans les sondages de cet événement.",
        "reconcile_title": "Pourquoi les nombres du sondage diffèrent de ceux de l'événement",
        "survey": "Sondage",
        "survey_done": "Participations complétées (sondage)",
        "matched_done": "Inscriptions au sondage complété (événement)",
        "duplicates": "Participations en double (même personne)",
        "unmatched_done": "Complétées sans inscription correspondante",
        "cancelled_done": "Complétées par une inscription annulée",
        "tests": "Tests (exclus)",
        "reconcile_note": "Le sondage compte des participations, l'événement compte des inscriptions. Une participation est "
                          "rattachée à une inscription par le même contact ou la même adresse courriel. Une personne qui a "
                          "répondu deux fois, ou avec une autre adresse que celle de son inscription, ou dont l'inscription "
                          "est annulée, explique l'écart, de même qu'un sondage partagé avec un autre événement. Les tests ne sont jamais comptés.",
    },
    "en": {
        "no_ticket": "(no ticket)",
        "no_registration": "No registration for this event.",
        "tickets_title": "Registrations and surveys per ticket type",
        "ticket": "Ticket",
        "registered": "Registered",
        "unique": "Unique participants (e-mail)",
        "present": "Present",
        "done": "Surveys completed",
        "in_progress": "Surveys started",
        "not_started": "Surveys not started",
        "answered": "Questions answered (%)",
        "unanswered": "Questions not answered (%)",
        "done_pct": "Surveys completed (%)",
        "registered_pct": "% registered",
        "present_pct": "% present",
        "pct_note": "« Surveys completed (%) »: surveys completed out of the registrations that have a survey. « % registered »: "
                    "registered people who gave this answer, out of all the registered people concerned by the question; "
                    "« % present »: people present who gave this answer, out of that same total. A multiple choice can exceed "
                    "100% in total.",
        "total": "Total",
        "weeks_title": "Registrations per week",
        "week": "Week",
        "week_label": "Week %(week)d: %(monday)s to %(sunday)s",
        "cumulative": "Cumulative",
        "weeks_note": "ISO weeks (Monday to Sunday), by the date of registration in local time. Cancelled registrations are "
                      "not counted.",
        "hours_title": "People marked present, per hour",
        "hour": "Hour",
        "no_presence": "Nobody is marked present yet.",
        "answers_title": "Answers to the questions shown at the registration desk",
        "question": "Question",
        "answer": "Answer",
        "of_which_present": "of which present",
        "no_answer": "(no answer)",
        "no_answer_note": "« (no answer) »: registered people who have no answer to this question (survey not started, question "
                          "skipped, or question not shown because it depends on another answer). Written answers that differ "
                          "only by capitals or accents are grouped.",
        "no_desk_question": "No question is checked « Show at the registration desk » in the surveys of this event.",
        "reconcile_title": "Why the numbers of the survey differ from those of the event",
        "survey": "Survey",
        "survey_done": "Participations completed (survey)",
        "matched_done": "Registrations with the survey completed (event)",
        "duplicates": "Duplicate participations (same person)",
        "unmatched_done": "Completed without a matching registration",
        "cancelled_done": "Completed by a cancelled registration",
        "tests": "Tests (excluded)",
        "reconcile_note": "The survey counts participations, the event counts registrations. A participation belongs to a "
                          "registration through the same contact or the same e-mail address. A person who answered twice, or "
                          "with another address than the one of the registration, or whose registration is cancelled, "
                          "explains the difference, as does a survey shared with another event. Tests are never counted.",
    },
}


def texts(lang=DEFAULT_LANG):
    """Labels in ONE language: an English code (en_US, en_CA, en) -> English; anything else -> French."""
    family = str(lang or DEFAULT_LANG).replace("-", "_").split("_")[0].lower()
    return TEXTS["en" if family == "en" else "fr"]


def _clean(text):
    return escape(" ".join(str(text or "").split()))


def _int(value):
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def question_progress(total, answered):
    """(answered, not answered) of one survey: (12, 8) -> (8, 4); more answers than questions -> (12, 0); bad values -> 0."""
    total, answered = _int(total), _int(answered)
    answered = min(answered, total)
    return answered, total - answered


def progress_text(total, answered):
    """« 8/12 » (answered / questions of the survey); « » when the survey has no question (or there is no survey)."""
    if _int(total) <= 0:
        return ""
    return "%d/%d" % (question_progress(total, answered)[0], _int(total))


def answers_text(answers, separator=" | "):
    """[("Lunch", ["Yes"]), ("Workshops", ["A", "B"]), ("Empty", [])] -> « Lunch: Yes | Workshops: A, B » (plain text, not escaped)."""
    parts = []
    for label, values in answers or ():
        values = [" ".join(str(v).split()) for v in (values or ()) if str(v or "").strip()]
        if values:
            parts.append("%s: %s" % (" ".join(str(label or "").split()), ", ".join(values)))
    return separator.join(parts)


def _ticket_name(row, labels):
    return " ".join(str(row.get("ticket") or "").split()) or labels["no_ticket"]


def ticket_summary(rows, lang=DEFAULT_LANG):
    """(lines, total): one dict per ticket, sorted by name, and the same dict for the whole event.

    Keys: name, registered, unique, present, done, in_progress, not_started, answered, unanswered. The questions are counted only for
    the registrations that have a survey: a person who did not start has all the questions of the survey « not answered ».
    v1.136.0: « unique » counts the different e-mail addresses (case and spaces ignored): one person who registered several
    times with the same address counts once; a registration without address counts as one person.
    """
    labels = texts(lang)
    keys = ("registered", "present", "done", "in_progress", "not_started", "answered", "unanswered")
    lines, people = {}, {}
    total = dict.fromkeys(keys, 0)
    total["name"] = labels["total"]
    for number, row in enumerate(rows or ()):
        name = _ticket_name(row, labels)
        line = lines.setdefault(name, dict(dict.fromkeys(keys, 0), name=name))
        person = " ".join(str(row.get("email") or "").lower().split()) or ("#", number)
        people.setdefault(name, set()).add(person)
        people.setdefault(None, set()).add(person)
        answered, unanswered = question_progress(row.get("questions"), row.get("answered"))
        state = row.get("survey_state")
        for target in (line, total):
            target["registered"] += 1
            target["present"] += 1 if row.get("present") else 0
            if state in SURVEY_STATES:
                target[state] += 1
                target["answered"] += answered
                target["unanswered"] += unanswered
    for name, line in lines.items():
        line["unique"] = len(people[name])
    total["unique"] = len(people.get(None, ()))
    return sorted(lines.values(), key=lambda t: t["name"].lower()), total


def hourly_attendance(rows, lang=DEFAULT_LANG):
    """People marked present per hour and per ticket.

    Returns {"hours": [...], "tickets": [...], "counts": {(hour, ticket): n}, "by_hour": {hour: n}, "by_ticket": {ticket: n},
    "total": n}. Only the rows with present=True and an hour are counted; hours and tickets are sorted.
    """
    labels = texts(lang)
    counts, by_hour, by_ticket = {}, {}, {}
    for row in rows or ():
        hour = str(row.get("hour") or "").strip()
        if not row.get("present") or not hour:
            continue
        ticket = _ticket_name(row, labels)
        counts[(hour, ticket)] = counts.get((hour, ticket), 0) + 1
        by_hour[hour] = by_hour.get(hour, 0) + 1
        by_ticket[ticket] = by_ticket.get(ticket, 0) + 1
    return {"hours": sorted(by_hour), "tickets": sorted(by_ticket, key=str.lower), "counts": counts,
            "by_hour": by_hour, "by_ticket": by_ticket, "total": sum(by_hour.values())}


def _row_date(row):
    """The local date of registration of a row (« 2026-11-17 15:59 » -> date(2026, 11, 17)); None when missing or invalid."""
    text = str(row.get("registered") or "").strip()[:10]
    try:
        return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except (ValueError, IndexError):
        return None


def weekly_registrations(rows, lang=DEFAULT_LANG):
    """v1.134.0: registrations per ISO week (Monday to Sunday) and per ticket, by the LOCAL date of registration.

    Returns {"tickets": [...], "weeks": [{"year", "week", "monday", "sunday", "by_ticket": {ticket: n}, "total", "cumulative"}]}.
    Weeks without any registration between the first and the last one are listed with 0, so the rhythm is visible. Rows
    without a date are not counted."""
    labels = texts(lang)
    counts, tickets = {}, set()
    for row in rows or ():
        day = _row_date(row)
        if day is None:
            continue
        monday = day - timedelta(days=day.weekday())
        ticket = _ticket_name(row, labels)
        tickets.add(ticket)
        per_week = counts.setdefault(monday, {})
        per_week[ticket] = per_week.get(ticket, 0) + 1
    weeks, cumulative = [], 0
    if counts:
        monday, last = min(counts), max(counts)
        while monday <= last:
            by_ticket = counts.get(monday, {})
            total = sum(by_ticket.values())
            cumulative += total
            year, week, _day = monday.isocalendar()
            weeks.append({"year": year, "week": week, "monday": monday, "sunday": monday + timedelta(days=6),
                          "by_ticket": by_ticket, "total": total, "cumulative": cumulative})
            monday += timedelta(days=7)
    return {"tickets": sorted(tickets, key=str.lower), "weeks": weeks}


def answers_breakdown(rows, lang=DEFAULT_LANG):
    """Counts of the answers to the questions shown at the desk.

    Returns (tickets, questions): tickets is the sorted list of ticket names that have at least one such question; questions is
    [{"label": ..., "registered": n, "present": n, "answers": [{"value": ..., "by_ticket": {ticket: n}, "total": n, "present": n}]}]
    (the question's "registered" / "present": people concerned by the question, denominators of the percentages), in the order the
    questions first appear, the answers sorted by name with « (no answer) » last. A multiple-choice answer counts once per
    chosen value; a person without answer to a question counts under « (no answer) ». Answers that differ only by case or
    accents are one answer (v1.127.0), shown with their most frequent spelling.
    """
    labels = texts(lang)
    questions, order, tickets, people = {}, [], set(), {}
    for row in rows or ():
        ticket = _ticket_name(row, labels)
        for label, values in row.get("answers") or ():
            label = " ".join(str(label or "").split())
            if not label:
                continue
            tickets.add(ticket)
            if label not in questions:
                questions[label] = {}
                order.append(label)
                people[label] = [0, 0]
            people[label][0] += 1                                    # v1.133.0: denominators of « % registered / % present »
            people[label][1] += 1 if row.get("present") else 0
            values = [" ".join(str(v).split()) for v in (values or ()) if str(v or "").strip()] or [None]
            keys = {}
            for value in values:                                      # the same value twice counts once
                keys.setdefault(sort_key(value) if value is not None else None, value)
            for key, value in keys.items():
                # v1.127.0: « Végétarien » and « végétarien » are ONE answer; the spelling shown is the most frequent one.
                cell = questions[label].setdefault(key, {"value": value, "spellings": {}, "by_ticket": {}, "total": 0, "present": 0})
                cell["spellings"][value] = cell["spellings"].get(value, 0) + 1
                cell["by_ticket"][ticket] = cell["by_ticket"].get(ticket, 0) + 1
                cell["total"] += 1
                cell["present"] += 1 if row.get("present") else 0
    result = []
    for label in order:
        answers = list(questions[label].values())
        for answer in answers:
            spellings = answer.pop("spellings")
            answer["value"] = max(spellings, key=lambda s: (spellings[s], s is not None and s[:1].isupper()))
        answers.sort(key=lambda a: (a["value"] is None, sort_key(a["value"])))
        for answer in answers:
            if answer["value"] is None:
                answer["value"] = labels["no_answer"]
        result.append({"label": label, "answers": answers, "registered": people[label][0], "present": people[label][1]})
    return sorted(tickets, key=str.lower), result


# v1.134.0: every table of the desk and volunteers pages has the same look, in INLINE styles (the HTML fields of Odoo do not
# load a style sheet of their own): dark header with white text (contrast 9.9:1, WCAG AAA), one line out of two in pale grey,
# a border on every cell, total lines in a mid grey. Inline styles also survive a copy into an e-mail or a spreadsheet.
HEAD_BG = "#34495e"
HEAD_FG = "#ffffff"
STRIPE_BG = "#f2f2f2"
TOTAL_BG = "#dde3ea"
BORDER = "1px solid #b8c0c8"
GROUP_BORDER = "2px solid #34495e"
_TABLE = ('<table class="table table-sm" style="width:auto;min-width:50%%;border-collapse:collapse;border:%s;">' % BORDER)
_NUM = ' style="text-align:right;"'


def cell_style(tag="td", numeric=False, stripe=False, total=False, extra=""):
    """« style="..." » of one cell: header, pale grey line (stripe), total line, right-aligned number."""
    parts = ["border:%s" % BORDER, "padding:2px 6px"]
    if tag == "th":
        parts += ["background-color:%s" % HEAD_BG, "color:%s" % HEAD_FG]
    elif total:
        parts += ["background-color:%s" % TOTAL_BG, "font-weight:bold"]
    elif stripe:
        parts.append("background-color:%s" % STRIPE_BG)
    if numeric:
        parts.append("text-align:right")
    if extra:
        parts.append(extra)
    return ' style="%s;"' % ";".join(parts)


class Number(str):
    """A number already formatted as text (a percentage): escaped like any text, but right-aligned like a number."""


def percent_text(part, whole, lang=DEFAULT_LANG):
    """« 40,5 % » (French) or « 40.5% » (English) of part / whole, one decimal; « » when whole is 0 (v1.127.0)."""
    part, whole = _int(part), _int(whole)
    if whole <= 0:
        return Number("")
    value = "%.1f" % (100.0 * part / whole)
    if texts(lang) is TEXTS["en"]:
        return Number(value + "%")
    return Number(value.replace(".", ",") + "\u00a0%")


class Strong(str):
    """A text cell shown in bold (v1.133.0: the questions of the answers table)."""


def _row(cells, tag="td", bold=False, stripe=False, first_attrs=""):
    """One line of a table. bold=True: a total line. stripe=True: pale grey background (one line out of two).
    first_attrs: extra attributes of the first cell (v1.134.0: rowspan of the question in the answers table); a first cell
    that is None is left out (covered by the rowspan of a previous line)."""
    out = []
    for index, cell in enumerate(cells):
        if cell is None:
            continue
        numeric = isinstance(cell, (int, Number))
        text = str(cell) if isinstance(cell, int) else escape(cell) if isinstance(cell, Number) else _clean(cell)
        if bold or (isinstance(cell, Strong) and text):
            text = "<strong>%s</strong>" % text
        style = cell_style(tag, numeric=bool(index and numeric), stripe=stripe, total=bold and tag == "td",
                           extra="vertical-align:top;background-color:#ffffff" if index == 0 and first_attrs else "")
        out.append("<%s%s%s>%s</%s>" % (tag, first_attrs if index == 0 else "", style, text, tag))
    return "<tr>%s</tr>" % "".join(out)


def _ticket_cells(line, keys, lang):
    """Cells of one line of the ticket table: counts, then the percentage of surveys completed (v1.133.0, replaces the
    percentages of questions answered / not answered), out of the registrations that have a survey."""
    with_survey = sum(line[state] for state in SURVEY_STATES)
    return [line[k] for k in keys] + [percent_text(line["done"], with_survey, lang)]


def desk_summary_html(rows, lang=DEFAULT_LANG):
    """The summary shown at the top of the registration desk, in the language `lang` only. Everything is escaped."""
    labels = texts(lang)
    rows = list(rows or ())
    if not rows:
        return "<p>%s</p>" % _clean(labels["no_registration"])
    keys = ("registered", "unique", "present", "done", "in_progress", "not_started")
    html = ["<h4>%s</h4>" % _clean(labels["tickets_title"]), _TABLE,
            "<thead>%s</thead><tbody>" % _row([labels["ticket"]] + [labels[k] for k in keys] + [labels["done_pct"]], tag="th")]
    lines, total = ticket_summary(rows, lang)
    for number, line in enumerate(lines):
        html.append(_row([line["name"]] + _ticket_cells(line, keys, lang), stripe=number % 2 == 1))
    html.append(_row([total["name"]] + _ticket_cells(total, keys, lang), bold=True))
    html.append("</tbody></table>")

    weekly = weekly_registrations(rows, lang)
    if weekly["weeks"]:
        html += ["<h4>%s</h4>" % _clean(labels["weeks_title"]), _TABLE, "<thead>%s</thead><tbody>" % _row(
            [labels["week"]] + weekly["tickets"] + [labels["total"], labels["cumulative"]], tag="th")]
        for number, week in enumerate(weekly["weeks"]):
            label = labels["week_label"] % {"week": week["week"], "monday": week["monday"].isoformat(),
                                            "sunday": week["sunday"].isoformat()}
            html.append(_row([label] + [week["by_ticket"].get(t, 0) for t in weekly["tickets"]]
                             + [week["total"], week["cumulative"]], stripe=number % 2 == 1))
        html.append("</tbody></table>")
        html.append('<p class="text-muted small">%s</p>' % _clean(labels["weeks_note"]))

    hourly = hourly_attendance(rows, lang)
    html.append("<h4>%s</h4>" % _clean(labels["hours_title"]))
    if not hourly["total"]:
        html.append("<p>%s</p>" % _clean(labels["no_presence"]))
    else:
        html += [_TABLE, "<thead>%s</thead><tbody>" % _row([labels["hour"]] + hourly["tickets"] + [labels["total"]], tag="th")]
        for number, hour in enumerate(hourly["hours"]):
            html.append(_row(["%s h" % hour] + [hourly["counts"].get((hour, t), 0) for t in hourly["tickets"]]
                             + [hourly["by_hour"][hour]], stripe=number % 2 == 1))
        html.append(_row([labels["total"]] + [hourly["by_ticket"][t] for t in hourly["tickets"]] + [hourly["total"]], bold=True))
        html.append("</tbody></table>")

    tickets, questions = answers_breakdown(rows, lang)
    html.append("<h4>%s</h4>" % _clean(labels["answers_title"]))
    if not questions:
        html.append("<p>%s</p>" % _clean(labels["no_desk_question"]))
    else:
        html += [_TABLE, "<thead>%s" % _row(
            [labels["question"], labels["answer"]] + tickets
            + [labels["total"], labels["registered_pct"], labels["of_which_present"], labels["present_pct"]], tag="th")
            + "</thead>"]
        # v1.134.0: each question is framed (its own <tbody> with a thick border, the question in one cell over all its
        # answers); « % présents » is out of ALL the people concerned by the question, like « % inscrits » (before: out of the
        # people present only, so a question answered by everybody present always showed 100 %).
        for question in questions:
            answers = question["answers"]
            html.append('<tbody style="border:%s;">' % GROUP_BORDER)
            for index, answer in enumerate(answers):
                first = Strong(question["label"]) if not index else None
                html.append(_row([first, answer["value"]]
                                 + [answer["by_ticket"].get(t, 0) for t in tickets]
                                 + [answer["total"], percent_text(answer["total"], question["registered"], lang),
                                    answer["present"], percent_text(answer["present"], question["registered"], lang)],
                                 stripe=index % 2 == 1,
                                 first_attrs=' rowspan="%d"' % len(answers) if not index and len(answers) > 1 else ""))
            html.append("</tbody>")
        html.append("</table>")
        html.append('<p class="text-muted small">%s</p>' % _clean(labels["no_answer_note"]))
        html.append('<p class="text-muted small">%s</p>' % _clean(labels["pct_note"]))
    return "".join(html)


# ----------------------------------------------------------------- volunteers' coordinator (v1.122.0, reworked in v1.123.0)

ROLE_WORDS = ("role",)
LANGUAGE_WORDS = ("langue", "language")
ON_SITE_WORDS = ("presentiel", "sur place", "en personne", "on site", "in person")
ONLINE_WORDS = ("virtuel", "en ligne", "a distance", "online", "remote")
TYPE_WORDS = ON_SITE_WORDS + ONLINE_WORDS + ("hybride", "hybrid")
OTHER_WORDS = ("autre", "other")
# v1.131.0: « arriver » and « partir » added: « À quelle heure pensez-vous arriver ? » was not found (only « arrivée »...).
ARRIVAL_PATTERN = re.compile(r"\b(arrivee|arrival|arriver|arriverez|arriveras|arrives?)\b")
DEPARTURE_PATTERN = re.compile(r"\b(depart|departure|partir|partirez|partiras|quitterez|quitteras|leave|leaving)\b")   # never « departement »
SURVEY_RANK = {"done": 0, "in_progress": 1, "not_started": 2, "none": 3}
VOLUNTEER_SORTS = ("name", "registered", "survey", "type", "languages", "arrived", "departed", "roles")

VOLUNTEER_TEXTS = {
    "fr": {
        "name": "Bénévole", "registered": "Inscrit le", "survey": "Sondage", "type": "Type", "languages": "Langues parlées",
        "arrived": "Heure d'arrivée", "departed": "Heure de départ", "title": "Bénévoles", "total": "Bénévoles listés",
        "no_volunteer": "Aucun bénévole à afficher pour cet événement.",
        "done": "Complété", "in_progress": "Commencé", "not_started": "Non commencé", "none": "Aucun sondage",
        "on_site": "Présentiel", "online": "Virtuel", "yes": "1", "column_total": "Total",
        "unique": "Participants uniques (courriel)",
        "expertise_title": "Expertises des bénévoles",
        "no_expertise_question": "Aucune question de sondage n'est cochée « Afficher dans Expertises des bénévoles » : ouvrez "
                                 "le sondage du billet bénévole, puis la question : la case est en bas de sa fiche.",
        "other_text": "texte libre",
    },
    "en": {
        "name": "Volunteer", "registered": "Registered on", "survey": "Survey", "type": "Type", "languages": "Languages spoken",
        "arrived": "Arrived at", "departed": "Left at", "title": "Volunteers", "total": "Volunteers listed",
        "no_volunteer": "No volunteer to show for this event.",
        "done": "Completed", "in_progress": "Started", "not_started": "Not started", "none": "No survey",
        "on_site": "On site", "online": "Online", "yes": "1", "column_total": "Total",
        "unique": "Unique participants (e-mail)",
        "expertise_title": "Volunteer expertise",
        "no_expertise_question": "No survey question is checked « Show in Volunteer expertise »: open the survey of the "
                                 "volunteer ticket, then the question: the box is at the bottom of its form.",
        "other_text": "free text",
    },
}


def volunteer_texts(lang=DEFAULT_LANG):
    return VOLUNTEER_TEXTS["en" if texts(lang) is TEXTS["en"] else "fr"]


def sort_key(text):
    """Key for sorting that ignores case AND accents: « Élise » sorts with the « e » words, « éric » before « Éva »."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def _has_word(text, words):
    key = sort_key(text)
    return any(word in key for word in words)


VISITOR_WORDS = ("visiteur", "visitor")   # v1.138.0: « Visiteur », « Visiteurs », « Visitor » once accents and case are ignored
SPONSOR_WORDS = ("commandit", "sponsor", "partenaire", "partner")   # v1.139.0: « Commanditaire », « Sponsor », « Partenaire »

TOPICS_TEXTS = {
    "fr": {"all": "Sujets d'intérêt de l'audience", "visitors": "Sujets d'intérêt des visiteurs",
           "volunteers": "Sujets d'intérêt des bénévoles", "sponsors": "Sujets d'intérêt des commanditaires",
           "tickets": "Sujets d'intérêt : billets choisis", "topic": "Sujet",
           "total": "Total", "pct": "% des répondants", "free": "texte libre",
           "respondents": "Répondants : %(respondents)d sur %(concerned)d personnes concernées par la question",
           "no_question": "Aucune question de sondage n'est cochée « Afficher dans « Sujets d'intérêt » » : ouvrez le sondage "
                          "du billet (ou de l'événement), puis la question : la case est en bas de sa fiche.",
           "no_answer": "Personne n'a encore répondu à cette question.",
           "nobody": "Aucune inscription à afficher pour cet événement et ces billets.",
           "note": "Seuls des nombres sont affichés : aucun nom ni courriel. Une personne peut choisir plusieurs sujets. Les "
                   "réponses libres (« Autre », questions texte) sont regroupées quand elles sont identiques, sans tenir "
                   "compte des majuscules ni des accents."},
    "en": {"all": "Topics of interest of the audience", "visitors": "Topics of interest of the visitors",
           "volunteers": "Topics of interest of the volunteers", "sponsors": "Topics of interest of the sponsors",
           "tickets": "Topics of interest: chosen tickets", "topic": "Topic",
           "total": "Total", "pct": "% of respondents", "free": "free text",
           "respondents": "Respondents: %(respondents)d of %(concerned)d people concerned by the question",
           "no_question": "No survey question is checked « Show in « Topics of interest » »: open the survey of the ticket (or "
                          "of the event), then the question: the box is at the bottom of its form.",
           "no_answer": "Nobody has answered this question yet.",
           "nobody": "No registration to show for this event and these tickets.",
           "note": "Only numbers are shown: no name, no e-mail. A person can choose several topics. Free answers (« Other », "
                   "text questions) are grouped when they are identical, case and accents ignored."},
}


def is_visitor_ticket(ticket_name):
    """v1.138.0: True for a ticket whose name says « visiteur » / « visitor » (any case, with or without accents)."""
    key = sort_key(ticket_name)
    return any(word in key for word in VISITOR_WORDS)


def is_sponsor_ticket(ticket_name):
    """v1.139.0: True for a ticket whose name says « commanditaire », « sponsor » or « partenaire » (case and accents ignored)."""
    key = sort_key(ticket_name)
    return any(word in key for word in SPONSOR_WORDS)


def ticket_in_scope(ticket_name, scope):
    """v1.139.0: does a ticket belong to the scope of « Topics of interest »: all, visitors, volunteers, sponsors? (The scope
    « tickets », chosen one by one, is decided by the page.)"""
    if scope == "visitors":
        return is_visitor_ticket(ticket_name)
    if scope == "volunteers":
        return is_volunteer_ticket(ticket_name)
    if scope == "sponsors":
        return is_sponsor_ticket(ticket_name)
    return True


def topics_breakdown(people, questions):
    """v1.138.0: for each question checked « Show in Topics of interest », the topics chosen and how many people chose each.

    people: [{"ticket": name, "questions": {question index, ...} (the questions of their survey), "answers": {question
    index: [texts]}}]; questions: [{"title", "choices"}] (choices empty: a text question).
    Returns [{"title", "concerned", "respondents", "topics": [{"topic", "free", "count", "by_ticket": {ticket: n}}]}]: the
    topics sorted by count (descending), then by name; a free answer (not one of the choices) is a topic of its own, the same
    text written several times (case, accents and spaces ignored) counted together."""
    result = []
    for index, question in enumerate(questions or ()):
        known = {sort_key(choice): choice for choice in question.get("choices") or ()}
        topics, concerned, respondents = {}, 0, 0
        for person in people or ():
            if index not in (person.get("questions") or ()):
                continue
            concerned += 1
            values = [" ".join(str(v).split()) for v in (person.get("answers") or {}).get(index, ()) if str(v or "").strip()]
            if values:
                respondents += 1
            seen = set()
            for value in values:
                key = sort_key(value)
                if key in seen:
                    continue
                seen.add(key)
                topic = topics.setdefault(key, {"topic": known.get(key, value), "free": key not in known, "count": 0,
                                                "by_ticket": {}})
                topic["count"] += 1
                ticket = person.get("ticket") or ""
                topic["by_ticket"][ticket] = topic["by_ticket"].get(ticket, 0) + 1
        ranked = sorted(topics.values(), key=lambda t: (-t["count"], sort_key(t["topic"])))
        result.append({"title": question.get("title") or "", "concerned": concerned, "respondents": respondents,
                       "topics": ranked})
    return result


ANSWERS_PAGE_TEXTS = {
    "fr": {"title": "Réponses de %(name)s", "survey": "Sondage", "state": "État", "submitted": "Soumis le", "device": "Appareil",
           "no_answer": "(sans réponse)", "print": "Version imprimable d'Odoo", "confidential":
           "Renseignements personnels : ne pas partager cette page en dehors des personnes autorisées.",
           "done": "Complété", "in_progress": "Commencé", "new": "Non commencé"},
    "en": {"title": "Answers of %(name)s", "survey": "Survey", "state": "State", "submitted": "Submitted on", "device": "Device",
           "no_answer": "(no answer)", "print": "Printable version of Odoo", "confidential":
           "Personal information: do not share this page outside the authorized people.",
           "done": "Completed", "in_progress": "Started", "new": "Not started"},
}


_UA_OS = (
    (r"Android\s+([\d.]+)", "Android %s"), (r"Android", "Android"),
    (r"(?:iPhone|CPU) OS ([\d_]+)", "iOS %s"), (r"iPad.*OS ([\d_]+)", "iPadOS %s"), (r"iPhone|iPad|iPod", "iOS"),
    (r"CrOS", "ChromeOS"), (r"Windows NT 10", "Windows 10/11"), (r"Windows NT ([\d.]+)", "Windows NT %s"), (r"Windows", "Windows"),
    (r"Mac OS X ([\d_]+)", "macOS %s"), (r"Macintosh", "macOS"), (r"Ubuntu", "Ubuntu"), (r"Fedora", "Fedora"),
    (r"Linux", "Linux"),
)
_UA_BROWSER = (                     # order matters: Edge and Samsung say « Chrome » too, Chrome says « Safari » too
    (r"EdgA?/([\d]+)", "Edge %s"), (r"SamsungBrowser/([\d]+)", "Samsung Internet %s"), (r"OPR/([\d]+)", "Opera %s"),
    (r"FxiOS/([\d]+)", "Firefox iOS %s"), (r"Focus/([\d]+)", "Firefox Focus %s"), (r"Firefox/([\d]+)", "Firefox %s"),
    (r"CriOS/([\d]+)", "Chrome iOS %s"), (r"; wv\)", "Android WebView"), (r"Chrome/([\d]+)", "Chrome %s"),
    (r"Version/([\d]+).*Safari", "Safari %s"), (r"Safari", "Safari"),
)


def parse_user_agent(user_agent):
    """v1.140.0: (« Android 14 », « Firefox 145 ») from the User-Agent of the browser of a participant; (« », « ») when
    unknown. Kept simple on purpose (no library): enough to compare the devices that get stuck in a survey."""
    text = str(user_agent or "")
    found = []
    for patterns in (_UA_OS, _UA_BROWSER):
        value = ""
        for pattern, label in patterns:
            match = re.search(pattern, text)
            if match:
                value = label % match.group(1).replace("_", ".") if "%s" in label else label
                break
        found.append(value)
    return found[0], found[1]


def answer_matches(answers, question_key, answer_key):
    """v1.139.0: filter « Answer » of the desk. answers: [(label, [values])] of one registration (_rlq_desk_map). True when the
    question (key of its label, case and accents ignored) has the answer `answer_key`, or, when answer_key is empty, when the
    question is in the survey of the person but has no answer. A person whose survey has not that question never matches."""
    for label, values in answers or ():
        if sort_key(" ".join(str(label or "").split())) != question_key:
            continue
        keys = {sort_key(" ".join(str(v or "").split())) for v in values or () if str(v or "").strip()}
        if (answer_key and answer_key in keys) or (not answer_key and not keys):
            return True
    return False


def answers_page_html(name, survey_title, state="", submitted="", sections=(), print_url=None, lang=DEFAULT_LANG, device=""):
    """v1.139.0: the page « See the answers » of one participant: the NAME of the person in the title of the browser tab and
    at the top (the page « print » of Odoo does not show it), the survey, its state and date, then every question with its
    answers, section by section. sections: [{"title": page title or "", "questions": [{"title", "values": [texts]}]}].
    A complete HTML document; everything is escaped."""
    labels = ANSWERS_PAGE_TEXTS["en"] if texts(lang) is TEXTS["en"] else ANSWERS_PAGE_TEXTS["fr"]
    title = labels["title"] % {"name": name or "?"}
    html = ['<!DOCTYPE html><html lang="%s"><head><meta charset="utf-8"/>' % ("en" if labels is ANSWERS_PAGE_TEXTS["en"] else "fr"),
            "<title>%s - %s</title>" % (_clean(title), _clean(survey_title)),
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>',
            "<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:60rem;margin:1.5rem auto;"
            "padding:0 1rem;color:#1f2933;line-height:1.45}h1{font-size:1.6rem;margin:0 0 .3rem}"
            "header{border-bottom:3px solid %s;padding-bottom:.6rem;margin-bottom:1rem}"
            ".meta{color:#52606d;margin:.1rem 0}h2{font-size:1.15rem;background:%s;color:%s;padding:.3rem .6rem;"
            "margin:1.4rem 0 .6rem}h3{font-size:1rem;margin:.9rem 0 .2rem}ul{margin:.1rem 0 .4rem 1.2rem;padding:0}"
            ".none{color:#7b8794;font-style:italic}.warn{color:#8a5a00;font-size:.85rem}</style></head><body>"
            % (HEAD_BG, HEAD_BG, HEAD_FG),
            "<header><h1>%s</h1>" % _clean(title),
            '<p class="meta"><strong>%s :</strong> %s</p>' % (_clean(labels["survey"]), _clean(survey_title))]
    if state:
        html.append('<p class="meta"><strong>%s :</strong> %s</p>' % (_clean(labels["state"]), _clean(labels.get(state, state))))
    if submitted:
        html.append('<p class="meta"><strong>%s :</strong> %s</p>' % (_clean(labels["submitted"]), _clean(submitted)))
    if device:                                          # v1.140.0: operating system and browser of the participation
        html.append('<p class="meta"><strong>%s :</strong> %s</p>' % (_clean(labels["device"]), _clean(device)))
    html.append('<p class="warn">%s</p></header>' % _clean(labels["confidential"]))
    for section in sections or ():
        if section.get("title"):
            html.append("<h2>%s</h2>" % _clean(section["title"]))
        for question in section.get("questions") or ():
            html.append("<h3>%s</h3>" % _clean(question.get("title")))
            values = [v for v in question.get("values") or () if str(v or "").strip()]
            if values:
                html.append("<ul>%s</ul>" % "".join("<li>%s</li>" % escape(str(v).strip()).replace("\n", "<br/>") for v in values))
            else:
                html.append('<p class="none">%s</p>' % _clean(labels["no_answer"]))
    if print_url:
        html.append('<p style="margin-top:2rem"><a href="%s">%s</a></p>' % (escape(str(print_url), quote=True), _clean(labels["print"])))
    html.append("</body></html>")
    return "".join(html)


def topics_html(breakdown, tickets=(), lang=DEFAULT_LANG, scope="all", notes=()):
    """v1.138.0: page « Sujets d'intérêt »: one table per question (topic, one column per ticket when there are several,
    total, % of respondents). Only numbers: no personal information. Everything is escaped."""
    labels = TOPICS_TEXTS["en"] if texts(lang) is TEXTS["en"] else TOPICS_TEXTS["fr"]
    tickets = list(tickets or ())
    per_ticket = len(tickets) > 1
    html = ["<h4>%s</h4>" % _clean(labels[scope if scope in ("visitors", "volunteers", "sponsors", "tickets") else "all"])]
    html += ['<p class="text-muted small">%s</p>' % _clean(note) for note in notes or ()]
    if breakdown is None:
        html.append("<p>%s</p>" % _clean(labels["nobody"]))
        return "".join(html)
    if not breakdown:
        html.append("<p>%s</p>" % _clean(labels["no_question"]))
        return "".join(html)
    for question in breakdown:
        html.append('<h5 style="margin-top:1rem;"><strong>%s</strong></h5>' % _clean(question["title"]))
        html.append('<p class="text-muted small">%s</p>' % _clean(labels["respondents"] % {
            "respondents": question["respondents"], "concerned": question["concerned"]}))
        if not question["topics"]:
            html.append("<p>%s</p>" % _clean(labels["no_answer"]))
            continue
        head = [labels["topic"]] + (tickets if per_ticket else []) + [labels["total"], labels["pct"]]
        html += [_TABLE, "<thead>%s</thead><tbody>" % _row(head, tag="th")]
        for number, topic in enumerate(question["topics"]):
            name = topic["topic"] + (" (%s)" % labels["free"] if topic["free"] else "")
            cells = [name] + ([topic["by_ticket"].get(ticket, 0) for ticket in tickets] if per_ticket else []) + [
                topic["count"], percent_text(topic["count"], question["respondents"], lang)]
            html.append(_row(cells, stripe=number % 2 == 1))
        html.append("</tbody></table>")
    html.append('<p class="text-muted small">%s</p>' % _clean(labels["note"]))
    return "".join(html)


def is_volunteer_ticket(ticket_name):
    """True for a ticket whose name says « bénévole » (any case, with or without accents)."""
    return VOLUNTEER_WORD in sort_key(ticket_name)


def role_kind(title):
    """« on_site » / « online » when the title of a roles question says so (« ... (en présentiel) ? »), otherwise None."""
    on_site, online = _has_word(title, ON_SITE_WORDS), _has_word(title, ONLINE_WORDS)
    if on_site == online:
        return None
    return "on_site" if on_site else "online"


def find_volunteer_questions(questions):
    """Finds the questions of the volunteers' table in a survey.

    questions: [{"id": ..., "title": ..., "choices": [labels], "is_choice": bool}] in the order of the survey.
    Returns {"roles": [ids], "languages": id or None, "type": id or None, "arrival": id or None, "departure": id or None}:
      - arrival / departure (v1.126.0): the first other question whose title speaks of the hour of arrival (« arrivée »)
        or of departure (« départ », never « département »): the hours the volunteer PLANS, as answered in the survey;
      - roles: EVERY choice question whose title contains « rôle », the on-site one(s) first, then the order of the survey;
      - languages: the first other question whose title contains « langue »;
      - type: the first other choice question whose title or choices speak of on site / online (« virtuel », « présentiel »,
        « en ligne », « sur place »...). None when the survey has no such question (see deduced_type()).
    """
    roles, languages, type_id, arrival, departure = [], None, None, None, None
    for question in questions or ():
        title = question.get("title")
        if question.get("is_choice") and _has_word(title, ROLE_WORDS):
            roles.append(question)
        elif arrival is None and ARRIVAL_PATTERN.search(sort_key(title)):
            arrival = question["id"]
        elif departure is None and DEPARTURE_PATTERN.search(sort_key(title)):
            departure = question["id"]
        elif languages is None and _has_word(title, LANGUAGE_WORDS):
            languages = question["id"]
        elif type_id is None and question.get("is_choice") and (
                _has_word(title, TYPE_WORDS) or any(_has_word(choice, TYPE_WORDS) for choice in question.get("choices") or ())):
            type_id = question["id"]
    roles.sort(key=lambda q: 0 if role_kind(q.get("title")) == "on_site" else 1)          # stable: keeps the survey order
    return {"roles": [q["id"] for q in roles], "languages": languages, "type": type_id, "arrival": arrival, "departure": departure}


def is_on_site(type_text):
    """v1.136.0: True when the type of a volunteer says they will be there in person (« Présentiel », « Sur place »,
    « Hybride », or « Présentiel, Virtuel »); False for « Virtuel » alone or an empty type."""
    return _has_word(type_text or "", ON_SITE_WORDS + ("hybride", "hybrid"))


def unique_people(rows):
    """v1.136.0: number of different people by e-mail address (case and spaces ignored); a row without address counts 1."""
    return len({" ".join(str(row.get("email") or "").lower().split()) or ("#", index) for index, row in enumerate(rows or ())})


def deduced_type(kinds, lang=DEFAULT_LANG):
    """Type of a volunteer when the survey has no type question: from the roles questions that were answered.

    kinds: the role_kind() of each roles question the volunteer answered. -> « Présentiel », « Virtuel », both, or « ».
    """
    labels = volunteer_texts(lang)
    kinds = set(kinds or ())
    return ", ".join(labels[kind] for kind in ("on_site", "online") if kind in kinds)


def role_cells(choices, values, yes="X"):
    """One cell per choice of a roles question: « X » when chosen. A free-text answer (the comment of an « Autre » choice) is
    shown in the « Autre » column instead of « X »; without such a column it is added to the last column."""
    chosen = {sort_key(value): value for value in values or ()}
    known = {sort_key(choice) for choice in choices}
    free = [value for key, value in chosen.items() if key not in known]
    cells = [yes if sort_key(choice) in chosen else "" for choice in choices]
    if free and cells:
        text = ", ".join(free)
        other = next((i for i, choice in enumerate(choices) if _has_word(choice, OTHER_WORDS)), None)
        if other is None:
            other = len(cells) - 1
            text = ("%s %s" % (cells[other], text)).strip()
        cells[other] = text
    return cells


def role_numbers(choices, values):
    """v1.135.0, for the spreadsheet: one cell per choice of a roles question, the NUMBER 1 when chosen and None (empty cell)
    otherwise, so that a column can be summed. A free-text answer (comment of an « Autre » choice) counts 1 in the « Autre »
    column (or the last column) and its text is returned apart: (cells, [free texts])."""
    chosen = {sort_key(value): value for value in values or ()}
    known = {sort_key(choice) for choice in choices}
    free = [value for key, value in chosen.items() if key not in known]
    cells = [1 if sort_key(choice) in chosen else None for choice in choices]
    if free and cells:
        other = next((i for i, choice in enumerate(choices) if _has_word(choice, OTHER_WORDS)), len(cells) - 1)
        cells[other] = 1
    return cells, free


def person_cell_html(name, chat_url=None):
    """Name of a participant in the list of the registration desk (v1.131.0): a link that opens a conversation with the person
    in Odoo (Discuss) when the registration has a contact, otherwise the plain name. Everything is escaped.

    The value starts with « <span data-rlq-sort="key"> », key = sort_key(name): the web client sorts the column of the list
    by comparing these strings, so the order ignores case and accents (« éric » between « Denis » and « Fanny »)."""
    key = escape(sort_key(" ".join(str(name or "").split())), quote=True)
    text = _clean(name)
    if chat_url:
        text = '<a href="%s" target="_blank" title="Message">%s</a>' % (escape(str(chat_url), quote=True), text)
    return '<span data-rlq-sort="%s">%s</span>' % (key, text)


def answers_cell_html(text, url=None):
    """v1.135.0: the answers of a registration in the lists of the desk, a link to every answer of the survey filled in by the
    person (controllers/answers.py) when there is a participation. Starts with « <span data-rlq-sort> » like
    person_cell_html(), so that the column sorts without case or accents. Everything is escaped; « » when empty."""
    text = " ".join(str(text or "").split())
    if not text and not url:
        return ""
    key = escape(sort_key(text), quote=True)
    shown = _clean(text) or "&#8230;"
    if url:
        shown = '<a href="%s" target="_blank">%s</a>' % (escape(str(url), quote=True), shown)
    return '<span data-rlq-sort="%s">%s</span>' % (key, shown)


def reconciliation_html(items, lang=DEFAULT_LANG):
    """v1.131.0: why « completed » differs between the survey (participations) and the event (registrations).

    items: [{"survey": title, "survey_done", "matched_done", "duplicates", "unmatched_done", "cancelled_done", "tests"}], one
    per survey of the event. « » when there is no survey. Everything is escaped."""
    labels = texts(lang)
    items = list(items or ())
    if not items:
        return ""
    keys = ("survey_done", "matched_done", "duplicates", "cancelled_done", "unmatched_done", "tests")
    html = ["<h4>%s</h4>" % _clean(labels["reconcile_title"]), _TABLE,
            "<thead>%s</thead><tbody>" % _row([labels["survey"]] + [labels[k] for k in keys], tag="th")]
    for number, item in enumerate(items):
        html.append(_row([item.get("survey") or ""] + [_int(item.get(k)) for k in keys], stripe=number % 2 == 1))
    html.append("</tbody></table>")
    html.append('<p class="text-muted small">%s</p>' % _clean(labels["reconcile_note"]))
    return "".join(html)


NEGATIVE_WORDS = ("non", "no", "aucun", "aucune", "none", "jamais", "never", "nope", "faux", "false")
NEGATIVE_VALUES = ("0", "-", "n/a", "na", "s.o.", "so", "sans objet", "pas du tout", "not at all")


def is_negative_answer(value):
    """v1.144.0: True for an answer that means « no » (« Non », « non merci », « Aucune », « No », « 0 », « - », « N/A »...),
    accents and case ignored: such a cell is shown but NOT counted in the totals. The first word decides (« Non, je ne
    pourrai pas »), split on spaces and punctuation but not on the hyphen (« Non-binaire » is not a « no »)."""
    text = " ".join(str(value or "").split())
    if not text:
        return False
    key = sort_key(text)
    if key in NEGATIVE_VALUES:
        return True
    first = re.split(r"[\s,;.:!?()]+", key, maxsplit=1)[0]
    return first in NEGATIVE_WORDS


def _counts(value):
    """A cell counts in a total when it is not empty and does not mean « no »."""
    return bool(str(value or "").strip()) and not is_negative_answer(value)


def volunteer_column_totals(rows, role_groups=(), extra_count=0):
    """v1.131.0: one total per column of the volunteers' table: the number of volunteers in the name column, the number of
    completed surveys in the survey column, and the number of non-empty cells (a role chosen, an hour given...) elsewhere.
    v1.144.0: a cell that means « no » (« Non », « Aucun »..., is_negative_answer()) is not counted."""
    rows = list(rows or ())
    totals = [len(rows)]
    for key in ("registered", "survey", "type", "on_site", "languages", "arrived", "departed"):
        if key == "survey":
            totals.append(sum(1 for row in rows if row.get("survey") == "done"))
        elif key == "on_site":                                    # v1.136.0: the volunteers who will be there in person
            totals.append(sum(1 for row in rows if is_on_site(row.get("type"))))
        elif key in ("registered", "type"):
            totals.append(sum(1 for row in rows if str(row.get(key) or "").strip()))
        else:
            totals.append(sum(1 for row in rows if _counts(row.get(key))))
    for index in range(extra_count):
        totals.append(sum(1 for row in rows if index < len(row.get("extra") or ()) and _counts(row["extra"][index])))
    for group_index, group in enumerate(role_groups or ()):
        if not group.get("choices"):
            continue
        counts = [0] * len(group["choices"])
        for row in rows:
            values = list(row.get("roles") or ())
            cells = role_cells(group["choices"], values[group_index] if group_index < len(values) else ())
            for index, cell in enumerate(cells):
                if _counts(cell):
                    counts[index] += 1
        totals += counts
    return totals


def expertise_cells(column, values, yes="1"):
    """v1.137.0: the cells of one question of « Volunteer expertise » for one volunteer. A choice question (column["choices"]
    not empty): one cell per choice, `yes` when chosen, the free text of « Autre » in the « Autre » (or last) cell, like the
    roles. A text question: one cell, the answers joined."""
    values = [v for v in (values or ()) if str(v or "").strip()]
    if column.get("choices"):
        return role_cells(column["choices"], values, yes)
    return [", ".join(str(v) for v in values)]


def expertise_totals(rows, columns):
    """Number of volunteers per cell column (a choice chosen, a text answered), and the number of volunteers first."""
    rows = list(rows or ())
    totals = [len(rows)]
    for index, column in enumerate(columns or ()):
        counts = None
        for row in rows:
            answers = list(row.get("answers") or ())
            cells = expertise_cells(column, answers[index] if index < len(answers) else ())
            counts = counts or [0] * len(cells)
            for position, cell in enumerate(cells):
                counts[position] += 1 if _counts(cell) else 0                       # v1.144.0: « Non » not counted
        totals += counts or [0] * max(len(column.get("choices") or ()), 1)
    return totals


def expertise_table_html(rows, columns=(), lang=DEFAULT_LANG, notes=()):
    """v1.137.0: table « Volunteer expertise »: one line per volunteer (name: link to Discuss; survey state: link to every
    answer), then, for each question checked « Show in Volunteer expertise », one column per choice (1 when chosen) or one
    text column. Totals at the top and the bottom. Everything is escaped."""
    labels = volunteer_texts(lang)
    rows, columns = list(rows or ()), list(columns or ())
    html = ['<h4>%s</h4>' % _clean(labels["expertise_title"])]
    html += ['<p class="text-muted small">%s</p>' % _clean(note) for note in notes or ()]
    if not columns:
        html.append("<p>%s</p>" % _clean(labels["no_expertise_question"]))
    if not rows:
        html.append("<p>%s</p>" % _clean(labels["no_volunteer"]))
        return "".join(html)
    has_choices = any(column.get("choices") for column in columns)
    span = ' rowspan="2"' if has_choices else ""
    th, th_center = cell_style("th"), cell_style("th", extra="text-align:center")
    head = "".join("<th%s%s>%s</th>" % (span, th, _clean(labels[k])) for k in ("name", "survey"))
    for column in columns:
        if column.get("choices"):
            head += '<th colspan="%d"%s>%s</th>' % (len(column["choices"]), th_center, _clean(column["title"]))
        else:
            head += "<th%s%s>%s</th>" % (span, th, _clean(column["title"]))
    head_lines = ["<tr>%s</tr>" % head]
    if has_choices:
        head_lines.append("<tr>%s</tr>" % "".join("<th%s>%s</th>" % (th_center, _clean(choice))
                                                  for column in columns for choice in column.get("choices") or ()))
    totals = expertise_totals(rows, columns)
    total_cells = ["%s : %d" % (_clean(labels["column_total"]), totals[0]), ""] + [str(n) for n in totals[1:]]
    total_line = "<tr>%s</tr>" % "".join("<th%s>%s</th>" % (cell_style(total=True, extra="text-align:center" if i else ""), c)
                                         for i, c in enumerate(total_cells))
    html += [_TABLE, "<thead>%s%s</thead><tbody>" % ("".join(head_lines), total_line)]
    for number, row in enumerate(rows):
        name = _clean(row.get("name"))
        if row.get("chat_url"):
            name = '<a href="%s" target="_blank">%s</a>' % (escape(str(row["chat_url"]), quote=True), name)
        survey = _clean(labels.get(row.get("survey"), ""))
        if row.get("answers_url") and survey:
            survey = '<a href="%s" target="_blank">%s</a>' % (escape(str(row["answers_url"]), quote=True), survey)
        cells = [name, survey]
        answers = list(row.get("answers") or ())
        for index, column in enumerate(columns):
            for cell in expertise_cells(column, answers[index] if index < len(answers) else (), labels["yes"]):
                text = _clean(cell)
                cells.append('<span style="display:block;text-align:center;">%s</span>' % text
                             if column.get("choices") and text == labels["yes"] else text)
        td = cell_style(stripe=number % 2 == 1)
        html.append("<tr>%s</tr>" % "".join("<td%s>%s</td>" % (td, cell) for cell in cells))
    html.append("</tbody><tfoot>%s</tfoot></table><p>%s: %d - %s: %d</p>" % (
        total_line, _clean(labels["total"]), len(rows), _clean(labels["unique"]), unique_people(rows)))
    return "".join(html)


def expertise_export_sheet(rows, columns=(), lang=DEFAULT_LANG):
    """v1.137.0: (title, header, lines) of « Volunteer expertise » for the spreadsheet: name, e-mail, ticket, survey, then one
    column per choice with the NUMBER 1 (empty otherwise, so that it can be summed) and one « (free text) » column per choice
    question when somebody wrote one, or one text column per text question."""
    labels = volunteer_texts(lang)
    english = texts(lang) is TEXTS["en"]
    words = {"email": "E-mail" if english else "Courriel", "ticket": "Ticket" if english else "Billet"}
    columns = list(columns or ())
    with_free = []
    for index, column in enumerate(columns):
        with_free.append(bool(column.get("choices")) and any(
            role_numbers(column["choices"], (list(row.get("answers") or ())[index:index + 1] or [()])[0])[1] for row in rows or ()))
    header = [labels["name"], words["email"], words["ticket"], labels["survey"]]
    for column, free in zip(columns, with_free):
        if column.get("choices"):
            header += ["%s - %s" % (column["title"], choice) for choice in column["choices"]]
            if free:
                header.append("%s (%s)" % (column["title"], labels["other_text"]))
        else:
            header.append(column["title"])
    lines = []
    for row in rows or ():
        answers = list(row.get("answers") or ())
        line = [row.get("name") or "", row.get("email") or "", row.get("ticket") or "", labels.get(row.get("survey"), "")]
        for index, (column, free) in enumerate(zip(columns, with_free)):
            values = [v for v in (answers[index] if index < len(answers) else ()) if str(v or "").strip()]
            if column.get("choices"):
                numbers, texts_free = role_numbers(column["choices"], values)
                line += numbers + ([", ".join(texts_free)] if free else [])
            else:
                line.append(", ".join(str(v) for v in values))
        lines.append(line)
    return labels["expertise_title"], _unique_labels(header), lines


def volunteer_sort_value(row, sort_by):
    """Sort value of one row of the volunteers' table (case and accents ignored for the texts)."""
    if sort_by == "survey":
        return (SURVEY_RANK.get(row.get("survey"), 9),)
    if sort_by == "roles":
        return (-sum(len(values or ()) for values in (row.get("roles") or ())),)
    if sort_by in ("registered", "arrived", "departed"):
        return (not row.get(sort_by), row.get(sort_by) or "")                              # empty dates last
    if sort_by in ("type", "languages"):
        return (not row.get(sort_by), sort_key(row.get(sort_by)))                           # empty answers last
    return (sort_key(row.get("name")),)


def sort_volunteer_rows(rows, sort_by="name", descending=False):
    """Rows sorted by one column, then by name, then by registration date. Unknown column: by name."""
    sort_by = sort_by if sort_by in VOLUNTEER_SORTS else "name"
    rows = sorted(rows or (), key=lambda row: (sort_key(row.get("name")), row.get("registered") or ""))
    return sorted(rows, key=lambda row: volunteer_sort_value(row, sort_by), reverse=bool(descending))      # stable


def _unique_labels(labels):
    """Column names of a spreadsheet must be unique for a pivot table: « Autre », « Autre » -> « Autre », « Autre (2) »."""
    seen, result = {}, []
    for label in labels:
        label = " ".join(str(label or "").split()) or "?"
        seen[label] = seen.get(label, 0) + 1
        result.append(label if seen[label] == 1 else "%s (%d)" % (label, seen[label]))
    return result


def volunteer_export_sheets(rows, role_groups=(), lang=DEFAULT_LANG, extra_columns=()):
    """Content of the spreadsheet of the volunteers (v1.126.0): [(sheet title, header, [lines])], plain values, no library.

    Three sheets, each one a flat table (one header line, unique column names, no merged cell) so that a pivot table can be
    built on it directly:
      - « Bénévoles »: ONE line per volunteer, the same columns as the screen plus e-mail and ticket, one column per role
        (the number 1 when chosen, v1.135.0, so that it can be summed; the free texts in « Autres rôles (texte) »), and the number
        of roles;
      - « Rôles »: ONE line per volunteer AND per role chosen (« (aucun rôle) » when none): the sheet for a pivot table of
        the roles by type, by language, by survey state;
      - « Langues »: ONE line per volunteer AND per language spoken (« (non précisé) » when none).
    rows: the rows of volunteer_table_html(), with the optional keys « email », « ticket », « registered_at » (a datetime
    in local time, written as a real date so that the spreadsheet can group by day) and « languages_list ».
    """
    labels = volunteer_texts(lang)
    english = labels is VOLUNTEER_TEXTS["en"]
    words = {"email": "E-mail" if english else "Courriel", "ticket": "Ticket" if english else "Billet",
             "roles_count": "Number of roles" if english else "Nombre de rôles", "roles": "Roles" if english else "Rôles",
             "question": "Question", "role": "Role" if english else "Rôle", "no_role": "(no role)" if english else "(aucun rôle)",
             "languages_sheet": "Languages" if english else "Langues", "language": "Language" if english else "Langue",
             "no_language": "(not specified)" if english else "(non précisé)",
             "other_text": "Other roles (text)" if english else "Autres rôles (texte)"}
    groups = [(index, group) for index, group in enumerate(role_groups or ()) if group.get("choices")]
    role_labels = _unique_labels([choice for _i, group in groups for choice in group["choices"]])
    header = _unique_labels([labels["name"], words["email"], words["ticket"], labels["registered"], labels["survey"], labels["type"],
                             labels["on_site"], labels["languages"], labels["arrived"], labels["departed"]] + list(extra_columns)
                            + role_labels + [words["other_text"], words["roles_count"]])
    wide, long_roles, long_languages = [], [], []
    for row in rows or ():
        name = " ".join(str(row.get("name") or "").split())
        survey = labels.get(row.get("survey"), "")
        base = [name, row.get("email") or "", row.get("ticket") or "", row.get("registered_at") or row.get("registered") or "",
                survey, row.get("type") or "", 1 if is_on_site(row.get("type")) else None, row.get("languages") or "", row.get("arrived") or "", row.get("departed") or ""]
        extra = list(row.get("extra") or ())
        base += [extra[i] if i < len(extra) else "" for i in range(len(extra_columns))]
        role_values = list(row.get("roles") or ())
        cells, count, free_texts = [], 0, []
        for index, group in groups:
            values = [v for v in (role_values[index] if index < len(role_values) else ()) if str(v or "").strip()]
            # v1.135.0: 1 instead of « X », so that the columns can be summed; the free text goes to « Autres rôles (texte) ».
            numbers, free = role_numbers(group["choices"], values)
            cells += numbers
            free_texts += free
            count += len(values)
            for value in values:
                long_roles.append([name, row.get("email") or "", row.get("type") or "", row.get("languages") or "", survey,
                                   group["title"], value])
        if not count:
            long_roles.append([name, row.get("email") or "", row.get("type") or "", row.get("languages") or "", survey, "",
                               words["no_role"]])
        wide.append(base + cells + [", ".join(free_texts), count])
        languages = row.get("languages_list")
        if languages is None:
            languages = [part.strip() for part in str(row.get("languages") or "").split(",")]
        languages = [language for language in languages if str(language or "").strip()] or [words["no_language"]]
        for language in languages:
            long_languages.append([name, row.get("type") or "", survey, language])
    return [
        (labels["title"], header, wide),
        (words["roles"], [labels["name"], words["email"], labels["type"], labels["languages"], labels["survey"],
                          words["question"], words["role"]], long_roles),
        (words["languages_sheet"], [labels["name"], labels["type"], labels["survey"], words["language"]], long_languages),
    ]


# French abbreviations of the North American time zones (Office québécois de la langue française): « N » = normale (standard
# time), « A » = avancée (daylight saving time). Python and the system only give the English ones (%Z: EST, EDT...).
FRENCH_ZONE_ABBREVIATIONS = {
    "NST": "HNT", "NDT": "HAT",       # Newfoundland
    "AST": "HNA", "ADT": "HAA",       # Atlantic
    "EST": "HNE", "EDT": "HAE",       # Eastern (Québec, Ontario)
    "CST": "HNC", "CDT": "HAC",       # Central
    "MST": "HNR", "MDT": "HAR",       # Mountain (« Rocheuses »)
    "PST": "HNP", "PDT": "HAP",       # Pacific
}


def zone_label(abbreviation, lang=DEFAULT_LANG):
    """Abbreviation of a time zone for the reader: « HNE » / « HAE » in French for « EST » / « EDT » (the change of time is
    already in the abbreviation given by strftime('%Z'), computed from the date), unchanged in English or for an unknown zone
    (« UTC », « CET »...)."""
    abbreviation = (abbreviation or "").strip()
    if texts(lang) is not TEXTS["en"]:
        return FRENCH_ZONE_ABBREVIATIONS.get(abbreviation.upper(), abbreviation)
    return abbreviation


def local_stamp(moment, pattern="%Y-%m-%d %H:%M", lang=DEFAULT_LANG):
    """« 2026-11-17 11:14 HNE »: a datetime ALREADY in local time (with its tzinfo) and the abbreviation of its zone, in the
    language of the reader. « » when moment is empty; no abbreviation when the datetime has no zone."""
    if not moment:
        return ""
    label = zone_label(moment.strftime("%Z"), lang)
    text = moment.strftime(pattern)
    return "%s %s" % (text, label) if label else text


def program_footer(program, version, shown_at="", zone="", lang=DEFAULT_LANG, modified=False):
    """« rlq_survey_report 18.0.1.124.0 - affiché le 2026-11-16 21:15:02 HNE (heure locale, America/Toronto) » under a screen,
    so that a screenshot says which version produced it and when. shown_at is already formatted in LOCAL time, never UTC.
    v1.137.0: modified=True says « modifié le » / « modified on »: shown_at is then the time of the last change of the module
    (release.VERSION_DATETIME), not the time of the display."""
    text = "%s %s" % (_clean(program), _clean(version or "?"))
    if shown_at:
        english = texts(lang) is TEXTS["en"]
        local = ("local time, %s" if english else "heure locale, %s") % _clean(zone) if zone else ("local time" if english else "heure locale")
        verb = ("modified on" if english else "modifié le") if modified else ("shown on" if english else "affiché le")
        text += " - %s %s (%s)" % (verb, _clean(shown_at), local)
    return '<p class="text-muted small">%s</p>' % text


def volunteer_table_html(rows, role_groups=(), lang=DEFAULT_LANG, extra_columns=(), notes=()):
    """Table of the volunteers for the coordinator, in the language `lang`. Everything is escaped.

    rows: [{"name", "chat_url" (or None), "registered", "survey" (done / in_progress / not_started / none), "type", "languages",
            "arrived", "departed", "roles": [values of group 0, values of group 1...], "extra": [text per extra column]}]
    role_groups: [{"title": title of the roles question, "choices": [labels]}]: one column per choice, under the title.
    extra_columns: labels of the other survey questions checked « Show at the registration desk ».
    notes: sentences shown above the table (question not found, type deduced...).
    """
    labels = volunteer_texts(lang)
    rows = list(rows or ())
    html = ["<p><em>%s</em></p>" % _clean(note) for note in notes or ()]
    if not rows:
        return "".join(html) + "<p>%s</p>" % _clean(labels["no_volunteer"])
    fixed = [labels[k] for k in ("name", "registered", "survey", "type", "on_site", "languages", "arrived", "departed")] + list(extra_columns)
    groups = [(index, group) for index, group in enumerate(role_groups or ()) if group.get("choices")]
    span = ' rowspan="2"' if groups else ""
    th = cell_style("th")
    th_center = cell_style("th", extra="text-align:center")
    head = "".join("<th%s%s>%s</th>" % (span, th, _clean(label)) for label in fixed)
    head += "".join('<th colspan="%d"%s>%s</th>' % (len(g["choices"]), th_center, _clean(g["title"])) for _i, g in groups)
    html += ["<h4>%s</h4>" % _clean(labels["title"]), _TABLE, "<thead><tr>%s</tr>" % head]
    if groups:
        html.append("<tr>%s</tr>" % "".join("<th%s>%s</th>" % (th_center, _clean(choice)) for _i, g in groups for choice in g["choices"]))
    # v1.131.0: the totals per column, at the top (last line of the header) and at the bottom (footer) of the table.
    totals = volunteer_column_totals(rows, role_groups, len(extra_columns))
    total_cells = ["%s : %d" % (_clean(labels["column_total"]), totals[0]) if labels is VOLUNTEER_TEXTS["fr"]
                   else "%s: %d" % (_clean(labels["column_total"]), totals[0])] + [str(n) for n in totals[1:]]
    total_line = '<tr class="table-active">%s</tr>' % "".join(
        '<th%s>%s</th>' % (cell_style(total=True, extra="text-align:center" if index else ""), cell)
        for index, cell in enumerate(total_cells))
    html.append(total_line)
    html.append("</thead><tbody>")
    for number, row in enumerate(rows):
        name = _clean(row.get("name"))
        if row.get("chat_url"):
            name = '<a href="%s" target="_blank">%s</a>' % (escape(str(row["chat_url"]), quote=True), name)
        survey = _clean(labels.get(row.get("survey"), ""))
        if row.get("answers_url") and survey:                     # v1.135.0: every answer of the survey of this person
            survey = '<a href="%s" target="_blank">%s</a>' % (escape(str(row["answers_url"]), quote=True), survey)
        on_site = '<span style="display:block;text-align:center;">1</span>' if is_on_site(row.get("type")) else ""
        cells = [name, _clean(row.get("registered")), survey, _clean(row.get("type")), on_site] + [_clean(text) for text in (
            row.get("languages"), row.get("arrived"), row.get("departed"))]
        extra = list(row.get("extra") or ())
        cells += [_clean(extra[i] if i < len(extra) else "") for i in range(len(extra_columns))]
        role_values = list(row.get("roles") or ())
        for index, group in groups:
            values = role_values[index] if index < len(role_values) else ()
            cells += ['<span style="display:block;text-align:center;">%s</span>' % _clean(cell) if cell else ""
                      for cell in role_cells(group["choices"], values, labels["yes"])]
        td = cell_style(stripe=number % 2 == 1)
        html.append("<tr>%s</tr>" % "".join("<td%s>%s</td>" % (td, cell) for cell in cells))
    html.append("</tbody><tfoot>%s</tfoot></table><p>%s: %d - %s: %d</p>" % (
        total_line, _clean(labels["total"]), len(rows), _clean(labels["unique"]), unique_people(rows)))
    return "".join(html)
