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
        "answered": "Questions répondues (%)",
        "unanswered": "Questions non répondues (%)",
        "total": "Total",
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
        "present": "Present",
        "done": "Surveys completed",
        "in_progress": "Surveys started",
        "not_started": "Surveys not started",
        "answered": "Questions answered (%)",
        "unanswered": "Questions not answered (%)",
        "total": "Total",
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
    chosen value; a person without answer to a question counts under « (no answer) ». Answers that differ only by case or
    accents are one answer (v1.127.0), shown with their most frequent spelling.
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
        result.append({"label": label, "answers": answers})
    return sorted(tickets, key=str.lower), result


_TABLE = '<table class="table table-sm table-bordered" style="width:auto;min-width:50%;">'
_NUM = ' style="text-align:right;"'


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


def _row(cells, tag="td", bold=False):
    out = []
    for index, cell in enumerate(cells):
        numeric = isinstance(cell, (int, Number))
        text = str(cell) if isinstance(cell, int) else escape(cell) if isinstance(cell, Number) else _clean(cell)
        if bold:
            text = "<strong>%s</strong>" % text
        out.append("<%s%s>%s</%s>" % (tag, _NUM if index and numeric else "", text, tag))
    return "<tr>%s</tr>" % "".join(out)


def _ticket_cells(line, keys, lang):
    """Cells of one line of the ticket table: counts, then the questions answered / not answered as percentages."""
    questions = line["answered"] + line["unanswered"]
    return [line[k] for k in keys if k not in ("answered", "unanswered")] + [
        percent_text(line["answered"], questions, lang), percent_text(line["unanswered"], questions, lang)]


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
        html.append(_row([line["name"]] + _ticket_cells(line, keys, lang)))
    html.append(_row([total["name"]] + _ticket_cells(total, keys, lang), bold=True))
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
        html.append('<p class="text-muted small">%s</p>' % _clean(labels["no_answer_note"]))
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
        "on_site": "Présentiel", "online": "Virtuel", "yes": "X", "column_total": "Total",
    },
    "en": {
        "name": "Volunteer", "registered": "Registered on", "survey": "Survey", "type": "Type", "languages": "Languages spoken",
        "arrived": "Arrived at", "departed": "Left at", "title": "Volunteers", "total": "Volunteers listed",
        "no_volunteer": "No volunteer to show for this event.",
        "done": "Completed", "in_progress": "Started", "not_started": "Not started", "none": "No survey",
        "on_site": "On site", "online": "Online", "yes": "X", "column_total": "Total",
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
    for item in items:
        html.append(_row([item.get("survey") or ""] + [_int(item.get(k)) for k in keys]))
    html.append("</tbody></table>")
    html.append('<p class="text-muted small">%s</p>' % _clean(labels["reconcile_note"]))
    return "".join(html)


def volunteer_column_totals(rows, role_groups=(), extra_count=0):
    """v1.131.0: one total per column of the volunteers' table: the number of volunteers in the name column, the number of
    completed surveys in the survey column, and the number of non-empty cells (a role chosen, an hour given...) elsewhere."""
    rows = list(rows or ())
    totals = [len(rows)]
    for key in ("registered", "survey", "type", "languages", "arrived", "departed"):
        if key == "survey":
            totals.append(sum(1 for row in rows if row.get("survey") == "done"))
        else:
            totals.append(sum(1 for row in rows if str(row.get(key) or "").strip()))
    for index in range(extra_count):
        totals.append(sum(1 for row in rows if index < len(row.get("extra") or ()) and str(row["extra"][index] or "").strip()))
    for group_index, group in enumerate(role_groups or ()):
        if not group.get("choices"):
            continue
        counts = [0] * len(group["choices"])
        for row in rows:
            values = list(row.get("roles") or ())
            cells = role_cells(group["choices"], values[group_index] if group_index < len(values) else ())
            for index, cell in enumerate(cells):
                if cell:
                    counts[index] += 1
        totals += counts
    return totals


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
        (« X » or the free text), and the number of roles;
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
             "no_language": "(not specified)" if english else "(non précisé)"}
    groups = [(index, group) for index, group in enumerate(role_groups or ()) if group.get("choices")]
    role_labels = _unique_labels([choice for _i, group in groups for choice in group["choices"]])
    header = _unique_labels([labels["name"], words["email"], words["ticket"], labels["registered"], labels["survey"], labels["type"],
                             labels["languages"], labels["arrived"], labels["departed"]] + list(extra_columns)
                            + role_labels + [words["roles_count"]])
    wide, long_roles, long_languages = [], [], []
    for row in rows or ():
        name = " ".join(str(row.get("name") or "").split())
        survey = labels.get(row.get("survey"), "")
        base = [name, row.get("email") or "", row.get("ticket") or "", row.get("registered_at") or row.get("registered") or "",
                survey, row.get("type") or "", row.get("languages") or "", row.get("arrived") or "", row.get("departed") or ""]
        extra = list(row.get("extra") or ())
        base += [extra[i] if i < len(extra) else "" for i in range(len(extra_columns))]
        role_values = list(row.get("roles") or ())
        cells, count = [], 0
        for index, group in groups:
            values = [v for v in (role_values[index] if index < len(role_values) else ()) if str(v or "").strip()]
            cells += role_cells(group["choices"], values, labels["yes"])
            count += len(values)
            for value in values:
                long_roles.append([name, row.get("email") or "", row.get("type") or "", row.get("languages") or "", survey,
                                   group["title"], value])
        if not count:
            long_roles.append([name, row.get("email") or "", row.get("type") or "", row.get("languages") or "", survey, "",
                               words["no_role"]])
        wide.append(base + cells + [count])
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


def program_footer(program, version, shown_at="", zone="", lang=DEFAULT_LANG):
    """« rlq_survey_report 18.0.1.124.0 - affiché le 2026-11-16 21:15:02 HNE (heure locale, America/Toronto) » under a screen,
    so that a screenshot says which version produced it and when. shown_at is already formatted in LOCAL time, never UTC."""
    text = "%s %s" % (_clean(program), _clean(version or "?"))
    if shown_at:
        english = texts(lang) is TEXTS["en"]
        local = ("local time, %s" if english else "heure locale, %s") % _clean(zone) if zone else ("local time" if english else "heure locale")
        text += " - %s %s (%s)" % ("shown on" if english else "affiché le", _clean(shown_at), local)
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
    fixed = [labels[k] for k in ("name", "registered", "survey", "type", "languages", "arrived", "departed")] + list(extra_columns)
    groups = [(index, group) for index, group in enumerate(role_groups or ()) if group.get("choices")]
    span = ' rowspan="2"' if groups else ""
    head = "".join("<th%s>%s</th>" % (span, _clean(label)) for label in fixed)
    head += "".join('<th colspan="%d" style="text-align:center;">%s</th>' % (len(g["choices"]), _clean(g["title"])) for _i, g in groups)
    html += ["<h4>%s</h4>" % _clean(labels["title"]), _TABLE, "<thead><tr>%s</tr>" % head]
    if groups:
        html.append("<tr>%s</tr>" % "".join("<th>%s</th>" % _clean(choice) for _i, g in groups for choice in g["choices"]))
    # v1.131.0: the totals per column, at the top (last line of the header) and at the bottom (footer) of the table.
    totals = volunteer_column_totals(rows, role_groups, len(extra_columns))
    total_cells = ["%s : %d" % (_clean(labels["column_total"]), totals[0]) if labels is VOLUNTEER_TEXTS["fr"]
                   else "%s: %d" % (_clean(labels["column_total"]), totals[0])] + [str(n) for n in totals[1:]]
    total_line = '<tr class="table-active">%s</tr>' % "".join(
        '<th%s>%s</th>' % ("" if not index else ' style="text-align:center;"', cell) for index, cell in enumerate(total_cells))
    html.append(total_line)
    html.append("</thead><tbody>")
    for row in rows:
        name = _clean(row.get("name"))
        if row.get("chat_url"):
            name = '<a href="%s" target="_blank">%s</a>' % (escape(str(row["chat_url"]), quote=True), name)
        cells = [name] + [_clean(text) for text in (
            row.get("registered"), labels.get(row.get("survey"), ""), row.get("type"), row.get("languages"),
            row.get("arrived"), row.get("departed"))]
        extra = list(row.get("extra") or ())
        cells += [_clean(extra[i] if i < len(extra) else "") for i in range(len(extra_columns))]
        role_values = list(row.get("roles") or ())
        for index, group in groups:
            values = role_values[index] if index < len(role_values) else ()
            cells += ['<span style="display:block;text-align:center;">%s</span>' % _clean(cell) if cell else ""
                      for cell in role_cells(group["choices"], values, labels["yes"])]
        html.append("<tr>%s</tr>" % "".join("<td>%s</td>" % cell for cell in cells))
    html.append("</tbody><tfoot>%s</tfoot></table><p>%s: %d</p>" % (total_line, _clean(labels["total"]), len(rows)))
    return "".join(html)
