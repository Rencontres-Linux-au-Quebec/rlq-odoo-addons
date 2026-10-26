# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
followup_report.py
==================

Pure functions (NO Odoo import) of the survey follow-up of event registrations (v1.113.0) and of the daily report (v1.114.0, one language since v1.115.0),
testable without Odoo (tests/test_followup_report.py, run by run-all.sh):

  survey_status(states)          -> "done" / "in_progress" / "not_started" from the states of a person's survey.user_input records.
  unique_emails(emails)          -> addresses without duplicates (case ignored), sorted, empty ones dropped.
  completion_rate(done, total)   -> integer percentage, or None when nothing is expected.
  report_lang(code)              -> (« fr » / « en », known) from an Odoo language code; empty -> French (fr_CA) (v1.115.0).
  daily_report_subject(...)      -> subject of the daily report.
  daily_report_html(...)         -> body of the daily report, in ONE language (v1.115.0; bilingual French / English in v1.114.0):
                                    system parameter rlq_survey_report.langue_courriels, fr_CA by default. NO e-mail address of a
                                    registered person (Loi 25): names, tickets and counts only. Everything is escaped.
"""
from html import escape

SURVEY_STATES = ("done", "in_progress", "not_started")


def survey_status(states):
    """Best state among a person's participations: one finished survey is enough; « new » (opened, nothing answered) is not started."""
    states = set(states or ())
    if "done" in states:
        return "done"
    if "in_progress" in states:
        return "in_progress"
    return "not_started"


def unique_emails(emails):
    """['B@x.ca', 'a@x.ca', 'b@X.ca ', ''] -> ['a@x.ca', 'B@x.ca']: first spelling kept, case ignored for duplicates and sorting."""
    seen = {}
    for email in emails or ():
        email = str(email or "").strip()
        if email and email.lower() not in seen:
            seen[email.lower()] = email
    return [seen[k] for k in sorted(seen)]


def completion_rate(done, total):
    try:
        done, total = int(done or 0), int(total or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return int(round(100.0 * done / total))


def _clean(text):
    return escape(" ".join(str(text or "").split()))


DEFAULT_REPORT_LANG = "fr_CA"
REPORT_LANGS = ("fr", "en")

TEXTS = {
    "fr": {
        "subject": "Rapport quotidien %s : %s",
        "hello": "Bonjour,",
        "intro": "Rapport quotidien de l'événement <strong>%s</strong>%s — %s.",
        "registrations": "<strong>Inscriptions</strong> : %d confirmée(s) — %d nouvelle(s) en 24 h — %d annulée(s) en 24 h.",
        "subscribers": "<strong>Nouveaux abonnés au site web</strong> (24 h) : %d à l'infolettre — %d compte(s) portail.",
        "surveys": "<strong>Sondages</strong> : %d complété(s) sur %d (%s %%) — %d commencé(s) — %d non commencé(s) — %d complété(s) en 24 h.",
        "no_survey": "<strong>Sondages</strong> : aucun sondage associé aux billets.",
        "ticket_heads": ("Billet", "Inscriptions", "Sondage", "Complétés", "Commencés", "Non commencés", "%"),
        "new_title": "Nouvelles inscriptions (24 h)",
        "new_heads": ("Quand", "Personne", "Billet", "Sondage"),
        "more": "… %d de plus.",
        "no_new": "Aucune nouvelle inscription depuis 24 h.",
        "remind": "Liste des courriels à relancer : Événements > Sondages non complétés.",
        "open": "Ouvrir l'événement dans Odoo",
        "no_ticket": "(sans billet)",
        "states": {"done": "Complété", "in_progress": "Commencé", "not_started": "Non commencé"},
    },
    "en": {
        "subject": "Daily report %s: %s",
        "hello": "Hello,",
        "intro": "Daily report of the event <strong>%s</strong>%s — %s.",
        "registrations": "<strong>Registrations</strong>: %d confirmed — %d new in 24 h — %d cancelled in 24 h.",
        "subscribers": "<strong>New website subscribers</strong> (24 h): %d newsletter — %d portal account(s).",
        "surveys": "<strong>Surveys</strong>: %d completed out of %d (%s %%) — %d started — %d not started — %d completed in 24 h.",
        "no_survey": "<strong>Surveys</strong>: no survey assigned to the tickets.",
        "ticket_heads": ("Ticket", "Registrations", "Survey", "Completed", "Started", "Not started", "%"),
        "new_title": "New registrations (24 h)",
        "new_heads": ("When", "Person", "Ticket", "Survey"),
        "more": "… %d more.",
        "no_new": "No new registration in the last 24 hours.",
        "remind": "E-mails to remind: Events > Surveys not completed.",
        "open": "Open the event in Odoo",
        "no_ticket": "(no ticket)",
        "states": {"done": "Completed", "in_progress": "Started", "not_started": "Not started"},
    },
}


def report_lang(code):
    """Language family of the daily report from an Odoo language code (« fr_CA », « fr_FR », « en_US », « fr », « EN-ca »…).

    Empty -> DEFAULT_REPORT_LANG (French). Returns (family, known): family is « fr » or « en »; known is False when the code is
    neither French nor English (« es_ES », « xx ») — the report then falls back to French and the caller logs it.
    """
    code = str(code or "").strip() or DEFAULT_REPORT_LANG
    family = code.replace("-", "_").split("_")[0].lower()
    if family in REPORT_LANGS:
        return family, True
    return "fr", False


def texts(lang=DEFAULT_REPORT_LANG):
    """Labels of the daily report in ONE language (no bilingual text since v1.115.0)."""
    return TEXTS[report_lang(lang)[0]]


def daily_report_subject(event_name, day, lang=DEFAULT_REPORT_LANG):
    """« Rapport quotidien 2026-10-20 : Event » (French) or « Daily report 2026-10-20: Event » (English)."""
    return texts(lang)["subject"] % (day or "", " ".join(str(event_name or "").split()))


def daily_report_html(event_name, begin, generated, totals, tickets, new_registrations, url=None, max_rows=50,
                      lang=DEFAULT_REPORT_LANG):
    """Body of the daily report, in the language `lang` only (French by default).

    totals            : {registered, new, cancelled, expected, done, in_progress, not_started, done_24h}
                        plus optionally subscribers_newsletter / subscribers_portal (new website subscribers
                        of the last 24 hours); the line is left out when subscribers_newsletter is None
                        (module not installed).
    tickets           : [{name, registered, survey, done, in_progress, not_started}] — survey empty: no survey for this ticket.
    new_registrations : [{when, name, ticket, survey_state}] of the last 24 hours (survey_state: done / in_progress / not_started / "").
    """
    t = texts(lang)

    def n(key):
        try:
            return int((totals or {}).get(key) or 0)
        except (TypeError, ValueError):
            return 0
    cell = 'style="padding:2px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top"'
    num = 'style="padding:2px 8px;border-bottom:1px solid #ddd;text-align:right;vertical-align:top"'
    rate = completion_rate(n("done"), n("expected"))
    out = [
        "<p>%s</p>" % t["hello"],
        "<p>%s</p>" % (t["intro"] % (_clean(event_name), (" (" + _clean(begin) + ")") if begin else "", _clean(generated))),
        "<p>%s</p>" % (t["registrations"] % (n("registered"), n("new"), n("cancelled"))),
    ]
    if (totals or {}).get("subscribers_newsletter") is not None:
        out.append("<p>%s</p>" % (t["subscribers"] % (n("subscribers_newsletter"), n("subscribers_portal"))))
    if n("expected"):
        out.append("<p>%s</p>" % (t["surveys"] % (
            n("done"), n("expected"), rate if rate is not None else "-", n("in_progress"), n("not_started"), n("done_24h"))))
    else:
        out.append("<p>%s</p>" % t["no_survey"])
    if tickets:
        out.append('<table style="border-collapse:collapse;font-size:13px"><tr>'
                   + "".join("<th %s>%s</th>" % (cell, h) for h in t["ticket_heads"]) + "</tr>")
        for ticket in tickets:
            has_survey = bool(ticket.get("survey"))
            r = completion_rate(ticket.get("done"), ticket.get("registered")) if has_survey else None
            out.append("<tr><td %s>%s</td><td %s>%d</td><td %s>%s</td>%s</tr>" % (
                cell, _clean(ticket.get("name")), num, int(ticket.get("registered") or 0), cell, _clean(ticket.get("survey")) or "—",
                "".join("<td %s>%s</td>" % (num, v) for v in (
                    (int(ticket.get("done") or 0), int(ticket.get("in_progress") or 0), int(ticket.get("not_started") or 0),
                     r if r is not None else "-")
                    if has_survey else ("—", "—", "—", "—")))))
        out.append("</table>")
    if new_registrations:
        rows = list(new_registrations)
        out.append("<p><strong>%s</strong></p>" % t["new_title"])
        out.append('<table style="border-collapse:collapse;font-size:13px"><tr>'
                   + "".join("<th %s>%s</th>" % (cell, h) for h in t["new_heads"]) + "</tr>")
        for row in rows[:max_rows]:
            out.append("<tr>%s</tr>" % "".join("<td %s>%s</td>" % (cell, v) for v in (
                _clean(row.get("when")), _clean(row.get("name")), _clean(row.get("ticket")),
                t["states"].get(row.get("survey_state"), "—"))))
        out.append("</table>")
        if len(rows) > max_rows:
            out.append("<p>%s</p>" % (t["more"] % (len(rows) - max_rows)))
    else:
        out.append("<p>%s</p>" % t["no_new"])
    if n("not_started") + n("in_progress"):
        out.append("<p>%s</p>" % t["remind"])
    if url:
        out.append('<p><a href="%s">%s</a></p>' % (escape(url, quote=True), t["open"]))
    return "".join(out)
