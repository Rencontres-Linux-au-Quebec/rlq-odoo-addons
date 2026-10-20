# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
followup_report.py
==================

Pure functions (NO Odoo import) of the survey follow-up of event registrations (v1.113.0) and of the daily report (v1.114.0),
testable without Odoo (tests/test_followup_report.py, run by run-all.sh):

  survey_status(states)          -> "done" / "in_progress" / "not_started" from the states of a person's survey.user_input records.
  unique_emails(emails)          -> addresses without duplicates (case ignored), sorted, empty ones dropped.
  completion_rate(done, total)   -> integer percentage, or None when nothing is expected.
  daily_report_subject(...)      -> subject of the daily report.
  daily_report_html(...)         -> body of the daily report. Bilingual (French then English): the recipient is an address, not a
                                    contact, so its language is unknown. NO e-mail address of a registered person (Loi 25): names,
                                    tickets and counts only. Everything is escaped.
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


def daily_report_subject(event_name, day):
    """« Rapport quotidien / Daily report 2026-10-20 : Event »."""
    return "Rapport quotidien / Daily report %s : %s" % (day or "", " ".join(str(event_name or "").split()))


def daily_report_html(event_name, begin, generated, totals, tickets, new_registrations, url=None, max_rows=50):
    """Body of the daily report.

    totals            : {registered, new, cancelled, expected, done, in_progress, not_started, done_24h}
    tickets           : [{name, registered, survey, done, in_progress, not_started}] — survey empty: no survey for this ticket.
    new_registrations : [{when, name, ticket, survey_state}] of the last 24 hours (survey_state: done / in_progress / not_started / "").
    """
    def n(key):
        try:
            return int((totals or {}).get(key) or 0)
        except (TypeError, ValueError):
            return 0
    cell = 'style="padding:2px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top"'
    num = 'style="padding:2px 8px;border-bottom:1px solid #ddd;text-align:right;vertical-align:top"'
    state_label = {"done": "Complété / Completed", "in_progress": "Commencé / Started", "not_started": "Non commencé / Not started"}
    rate = completion_rate(n("done"), n("expected"))
    out = [
        "<p>Bonjour, / Hello,</p>",
        "<p>Rapport quotidien de l'événement / Daily report of the event <strong>%s</strong>%s — %s.</p>" % (
            _clean(event_name), (" (" + _clean(begin) + ")") if begin else "", _clean(generated)),
        "<p><strong>Inscriptions / Registrations</strong> : %d confirmée(s) / confirmed — "
        "%d nouvelle(s) en 24 h / new in 24 h — %d annulée(s) en 24 h / cancelled in 24 h.</p>" % (n("registered"), n("new"), n("cancelled")),
    ]
    if n("expected"):
        out.append(
            "<p><strong>Sondages / Surveys</strong> : %d complété(s) / completed sur / out of %d (%s %%) — %d commencé(s) / started — "
            "%d non commencé(s) / not started — %d complété(s) en 24 h / completed in 24 h.</p>" % (
                n("done"), n("expected"), rate if rate is not None else "-", n("in_progress"), n("not_started"), n("done_24h")))
    else:
        out.append("<p><strong>Sondages / Surveys</strong> : aucun sondage associé aux billets / no survey assigned to the tickets.</p>")
    if tickets:
        heads = ("Billet / Ticket", "Inscriptions / Registrations", "Sondage / Survey", "Complétés / Completed",
                 "Commencés / Started", "Non commencés / Not started", "%")
        out.append('<table style="border-collapse:collapse;font-size:13px"><tr>'
                   + "".join("<th %s>%s</th>" % (cell, h) for h in heads) + "</tr>")
        for t in tickets:
            has_survey = bool(t.get("survey"))
            r = completion_rate(t.get("done"), t.get("registered")) if has_survey else None
            out.append("<tr><td %s>%s</td><td %s>%d</td><td %s>%s</td>%s</tr>" % (
                cell, _clean(t.get("name")), num, int(t.get("registered") or 0), cell, _clean(t.get("survey")) or "—",
                "".join("<td %s>%s</td>" % (num, v) for v in (
                    (int(t.get("done") or 0), int(t.get("in_progress") or 0), int(t.get("not_started") or 0), r if r is not None else "-")
                    if has_survey else ("—", "—", "—", "—")))))
        out.append("</table>")
    if new_registrations:
        rows = list(new_registrations)
        out.append("<p><strong>Nouvelles inscriptions (24 h) / New registrations (24 h)</strong></p>")
        out.append('<table style="border-collapse:collapse;font-size:13px"><tr>'
                   + "".join("<th %s>%s</th>" % (cell, h) for h in ("Quand / When", "Personne / Person", "Billet / Ticket", "Sondage / Survey"))
                   + "</tr>")
        for r in rows[:max_rows]:
            out.append("<tr>%s</tr>" % "".join("<td %s>%s</td>" % (cell, v) for v in (
                _clean(r.get("when")), _clean(r.get("name")), _clean(r.get("ticket")),
                state_label.get(r.get("survey_state"), "—"))))
        out.append("</table>")
        if len(rows) > max_rows:
            out.append("<p>… %d de plus / more.</p>" % (len(rows) - max_rows))
    else:
        out.append("<p>Aucune nouvelle inscription depuis 24 h. / No new registration in the last 24 hours.</p>")
    if n("not_started") + n("in_progress"):
        out.append("<p>Liste des courriels à relancer / E-mails to remind : Événements > Sondages non complétés / "
                   "Events > Surveys not completed.</p>")
    if url:
        out.append('<p><a href="%s">Ouvrir l\'événement dans Odoo / Open the event in Odoo</a></p>' % escape(url, quote=True))
    return "".join(out)
