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
  hourly_attendance(rows)             -> (hours, tickets, counts, totals per hour, totals per ticket, total) of the people present.
  answers_breakdown(rows)             -> per question shown at the desk, per answer: count per ticket, total, of which present.
  desk_summary_html(rows, lang)       -> the three tables above, in ONE language (French or English), everything escaped.

A row describes ONE registration (built by models/event_registration_desk.py):

  {"ticket": "Visitor", "present": True, "hour": "2026-10-10 09",      # hour: local hour of the check-in, None when not present
   "survey_state": "done" / "in_progress" / "not_started" / "none",
   "questions": 12, "answered": 8,
   "answers": [("Lunch", ["Yes"]), ("On site or online", [])]}
"""
import unicodedata
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
        "present": "Présents",
        "done": "Sondages complétés",
        "in_progress": "Sondages commencés",
        "not_started": "Sondages non commencés",
        "answered": "Questions répondues",
        "unanswered": "Questions non répondues",
        "total": "Total",
        "hours_title": "Personnes marquées présentes, par heure",
        "hour": "Heure",
        "no_presence": "Personne n'est encore marqué présent.",
        "answers_title": "Réponses aux questions affichées au bureau d'inscription",
        "question": "Question",
        "answer": "Réponse",
        "of_which_present": "dont présents",
        "no_answer": "(sans réponse)",
        "no_desk_question": "Aucune question n'est cochée « Afficher au bureau d'inscription » dans les sondages de cet événement.",
    },
    "en": {
        "no_ticket": "(no ticket)",
        "no_registration": "No registration for this event.",
        "tickets_title": "Registrations and surveys per ticket type",
        "ticket": "Ticket",
        "registered": "Registered",
        "present": "Present",
        "done": "Surveys completed",
        "in_progress": "Surveys started",
        "not_started": "Surveys not started",
        "answered": "Questions answered",
        "unanswered": "Questions not answered",
        "total": "Total",
        "hours_title": "People marked present, per hour",
        "hour": "Hour",
        "no_presence": "Nobody is marked present yet.",
        "answers_title": "Answers to the questions shown at the registration desk",
        "question": "Question",
        "answer": "Answer",
        "of_which_present": "of which present",
        "no_answer": "(no answer)",
        "no_desk_question": "No question is checked « Show at the registration desk » in the surveys of this event.",
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

    Keys: name, registered, present, done, in_progress, not_started, answered, unanswered. The questions are counted only for
    the registrations that have a survey: a person who did not start has all the questions of the survey « not answered ».
    """
    labels = texts(lang)
    keys = ("registered", "present", "done", "in_progress", "not_started", "answered", "unanswered")
    lines = {}
    total = dict.fromkeys(keys, 0)
    total["name"] = labels["total"]
    for row in rows or ():
        name = _ticket_name(row, labels)
        line = lines.setdefault(name, dict(dict.fromkeys(keys, 0), name=name))
        answered, unanswered = question_progress(row.get("questions"), row.get("answered"))
        state = row.get("survey_state")
        for target in (line, total):
            target["registered"] += 1
            target["present"] += 1 if row.get("present") else 0
            if state in SURVEY_STATES:
                target[state] += 1
                target["answered"] += answered
                target["unanswered"] += unanswered
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


def answers_breakdown(rows, lang=DEFAULT_LANG):
    """Counts of the answers to the questions shown at the desk.

    Returns (tickets, questions): tickets is the sorted list of ticket names that have at least one such question; questions is
    [{"label": ..., "answers": [{"value": ..., "by_ticket": {ticket: n}, "total": n, "present": n}]}], in the order the
    questions first appear, the answers sorted by name with « (no answer) » last. A multiple-choice answer counts once per
    chosen value; a person without answer to a question counts under « (no answer) ».
    """
    labels = texts(lang)
    questions, order, tickets = {}, [], set()
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
            values = [" ".join(str(v).split()) for v in (values or ()) if str(v or "").strip()] or [None]
            for value in dict.fromkeys(values):                       # the same value twice counts once
                cell = questions[label].setdefault(value, {"value": value, "by_ticket": {}, "total": 0, "present": 0})
                cell["by_ticket"][ticket] = cell["by_ticket"].get(ticket, 0) + 1
                cell["total"] += 1
                cell["present"] += 1 if row.get("present") else 0
    result = []
    for label in order:
        answers = sorted(questions[label].values(), key=lambda a: (a["value"] is None, str(a["value"] or "").lower()))
        for answer in answers:
            if answer["value"] is None:
                answer["value"] = labels["no_answer"]
        result.append({"label": label, "answers": answers})
    return sorted(tickets, key=str.lower), result


_TABLE = '<table class="table table-sm table-bordered" style="width:auto;min-width:50%;">'
_NUM = ' style="text-align:right;"'


def _row(cells, tag="td", bold=False):
    out = []
    for index, cell in enumerate(cells):
        text = _clean(cell) if not isinstance(cell, int) else str(cell)
        if bold:
            text = "<strong>%s</strong>" % text
        out.append("<%s%s>%s</%s>" % (tag, _NUM if index and isinstance(cell, int) else "", text, tag))
    return "<tr>%s</tr>" % "".join(out)


def desk_summary_html(rows, lang=DEFAULT_LANG):
    """The summary shown at the top of the registration desk, in the language `lang` only. Everything is escaped."""
    labels = texts(lang)
    rows = list(rows or ())
    if not rows:
        return "<p>%s</p>" % _clean(labels["no_registration"])
    keys = ("registered", "present", "done", "in_progress", "not_started", "answered", "unanswered")
    html = ["<h4>%s</h4>" % _clean(labels["tickets_title"]), _TABLE,
            "<thead>%s</thead><tbody>" % _row([labels["ticket"]] + [labels[k] for k in keys], tag="th")]
    lines, total = ticket_summary(rows, lang)
    for line in lines:
        html.append(_row([line["name"]] + [line[k] for k in keys]))
    html.append(_row([total["name"]] + [total[k] for k in keys], bold=True))
    html.append("</tbody></table>")

    hourly = hourly_attendance(rows, lang)
    html.append("<h4>%s</h4>" % _clean(labels["hours_title"]))
    if not hourly["total"]:
        html.append("<p>%s</p>" % _clean(labels["no_presence"]))
    else:
        html += [_TABLE, "<thead>%s</thead><tbody>" % _row([labels["hour"]] + hourly["tickets"] + [labels["total"]], tag="th")]
        for hour in hourly["hours"]:
            html.append(_row(["%s h" % hour] + [hourly["counts"].get((hour, t), 0) for t in hourly["tickets"]]
                             + [hourly["by_hour"][hour]]))
        html.append(_row([labels["total"]] + [hourly["by_ticket"][t] for t in hourly["tickets"]] + [hourly["total"]], bold=True))
        html.append("</tbody></table>")

    tickets, questions = answers_breakdown(rows, lang)
    html.append("<h4>%s</h4>" % _clean(labels["answers_title"]))
    if not questions:
        html.append("<p>%s</p>" % _clean(labels["no_desk_question"]))
    else:
        html += [_TABLE, "<thead>%s</thead><tbody>" % _row(
            [labels["question"], labels["answer"]] + tickets + [labels["total"], labels["of_which_present"]], tag="th")]
        for question in questions:
            for index, answer in enumerate(question["answers"]):
                html.append(_row([question["label"] if not index else "", answer["value"]]
                                 + [answer["by_ticket"].get(t, 0) for t in tickets] + [answer["total"], answer["present"]]))
        html.append("</tbody></table>")
    return "".join(html)


# ----------------------------------------------------------------- v1.122.0: volunteers' coordinator

def sort_key(text):
    """Key for sorting that ignores case AND accents: « Élise » sorts with the « e » words, « éric » before « Éva »."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def is_volunteer_ticket(ticket_name):
    """True for a ticket whose name says « bénévole » (any case, with or without accents)."""
    return VOLUNTEER_WORD in sort_key(ticket_name)


def _volunteer_texts(lang):
    if texts(lang) is TEXTS["en"]:
        return {"name": "Volunteer", "registered": "Registered on", "type": "Type", "languages": "Languages",
                "arrived": "Arrived at", "departed": "Left at", "no_volunteer": "No volunteer is registered for this event.",
                "title": "Volunteers", "total": "Volunteers listed", "none": "not answered", "yes": "X",
                "no_type": "Type question not found in the survey", "no_roles": "Roles question not found in the survey",
                "no_languages": "Languages question not found in the survey"}
    return {"name": "Bénévole", "registered": "Inscrit le", "type": "Type", "languages": "Langues parlées",
            "arrived": "Heure d'arrivée", "departed": "Heure de départ", "no_volunteer": "Aucun bénévole inscrit à cet événement.",
            "title": "Bénévoles", "total": "Bénévoles listés", "none": "sans réponse", "yes": "X",
            "no_type": "Question sur le type introuvable dans le sondage", "no_roles": "Question sur les rôles introuvable dans le sondage",
            "no_languages": "Question sur les langues introuvable dans le sondage"}


def volunteer_table_html(rows, roles, lang=DEFAULT_LANG, base_url=""):
    """Table of the volunteers for the coordinator. rows: dicts with keys name, partner_id, registered, type, languages, arrived,
    departed, roles (set of role labels). roles: the choices of the roles question, one column each. Everything escaped.

    Name: link to the chat of the volunteer (base_url + /chat/<partner_id>), so the coordinator can talk to them on Odoo.
    """
    labels = _volunteer_texts(lang)
    rows = list(rows or ())
    if not rows:
        return "<p>%s</p>" % escape(labels["no_volunteer"])
    head = [labels["name"], labels["registered"], labels["type"], labels["languages"], labels["arrived"], labels["departed"]]
    html = ["<h4>%s</h4>" % escape(labels["title"]), _TABLE,
            "<thead>%s</thead><tbody>" % _row(head + list(roles or ()), tag="th")]
    for row in rows:
        link = '<a href="%s">%s</a>' % (escape("%s/chat/%d" % (base_url, row["partner_id"]), quote=True),
                                        escape(" ".join(str(row.get("name") or "").split()))) if row.get("partner_id") \
            else escape(row.get("name") or "")
        cells = [link, row.get("registered") or "", row.get("type") or "", row.get("languages") or "",
                 row.get("arrived") or "", row.get("departed") or ""]
        cells += [labels["yes"] if role in (row.get("roles") or ()) else "" for role in (roles or ())]
        html.append("<tr>%s</tr>" % "".join(
            "<td>%s</td>" % (cell if str(cell).startswith("<a ") else _clean(cell)) for cell in cells))
    html.append("</tbody></table>")
    html.append("<p>%s: %d</p>" % (escape(labels["total"]), len(rows)))
    return "".join(html)
