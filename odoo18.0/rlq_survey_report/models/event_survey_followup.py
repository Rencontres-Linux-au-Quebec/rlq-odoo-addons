# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
event_survey_followup.py
========================

Survey follow-up of event registrations.

Surveys not completed (v1.113.0): for the events whose tickets have a survey (`event.event.ticket.rlq_survey_id`, otherwise the survey of
the event), the list of the confirmed registrations (`open` / `done`) whose person has NOT completed that survey yet, with the list of
their e-mail addresses to copy (Events > Surveys not completed, button on the event form).
  - `event.registration.rlq_survey_state` (computed, not stored): none / not_started / in_progress / done.
  - A participation (`survey.user_input`, test entries excluded) belongs to a registration when it is on the expected survey AND has the
    same contact OR the same e-mail address (case ignored): the same matching as `_rlq_dernieres_inscriptions` (event_inscriptions_alerte.py).
  - Wizard `rlq.survey.pending`: events (default: the current and upcoming events with a ticket survey), « include started surveys »,
    registrations and e-mail addresses (no duplicates, sorted).

Daily report (v1.114.0): the box `rlq_daily_report` of an event sends every day (scheduled action « RLQ … daily report ») to the same
recipient as the registration alert (`_rlq_destinataire_alerte`): registrations (confirmed, new and cancelled in 24 h, the new ones with
their ticket and survey state) and survey statistics per ticket (completed, started, not started, completion rate). No e-mail address of
a registered person (Loi 25). Sent until the day after the end of the event; at most once per 20 hours by the scheduled action (the
« Send the daily report now » button always sends). Never raises: a failure is logged and the next event is processed.

Language of the daily report (v1.115.0): ONE language, no longer bilingual. System parameter `rlq_survey_report.langue_courriels`
(created with « fr_CA » when absent, an existing value is never replaced): a French code (fr_CA, fr_FR…) -> French, an English code
(en_US, en_CA…) -> English; empty -> fr_CA; any other code -> French, with a warning in the log. The labels come from
followup_report.TEXTS (not from Odoo translations), so the chosen language does not need to be installed in Odoo.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import followup_report as fr
from .event_inscriptions_alerte import CLE_PARAMETRE_COURRIEL_INSCRIPTIONS, ETATS_COMPTES

_logger = logging.getLogger(__name__)

SURVEY_STATE_SELECTION = [
    ("none", "No survey"),
    ("not_started", "Not started"),
    ("in_progress", "Started"),
    ("done", "Completed"),
]
DAILY_REPORT_MIN_HOURS = 20
PARAM_REPORT_LANG = "rlq_survey_report.langue_courriels"


class EventRegistrationSurveyFollowup(models.Model):
    _inherit = "event.registration"

    rlq_survey_state = fields.Selection(
        SURVEY_STATE_SELECTION, string="Survey", compute="_compute_rlq_survey_state",
        help="State of the survey expected for this registration (the survey of its ticket, otherwise the survey of the event): "
             "completed, started, not started, or no survey.",
    )
    rlq_expected_survey_id = fields.Many2one(
        "survey.survey", string="Expected survey", compute="_compute_rlq_survey_state",
        help="The survey of the ticket of this registration, otherwise the survey of the event.",
    )

    def _compute_rlq_survey_state(self):
        status = self._rlq_survey_status_map()
        for registration in self:
            survey, state, _done_at = status.get(registration.id, (False, "none", None))
            registration.rlq_survey_state = state
            registration.rlq_expected_survey_id = survey or False

    def _rlq_survey_status_map(self):
        """{registration id: (expected survey, state, end of the completed participation or None)} in TWO queries for the whole recordset."""
        registrations = self.sudo().filtered("id")
        empty = self.env["survey.survey"].sudo().browse()
        expected = {}
        for registration in registrations:
            ticket = registration.event_ticket_id if "event_ticket_id" in registration._fields else False
            survey = ticket.rlq_survey_id if ticket else empty
            if not survey and "survey_id" in registration.event_id._fields:
                survey = registration.event_id.survey_id
            expected[registration.id] = survey or empty
        survey_ids = sorted({s.id for s in expected.values() if s})
        by_partner, by_email = defaultdict(list), defaultdict(list)
        if survey_ids:
            participations = self.env["survey.user_input"].sudo()
            read = ["survey_id", "partner_id", "email", "state"] + (["end_datetime"] if "end_datetime" in participations._fields else [])
            for row in participations.search_read([("survey_id", "in", survey_ids), ("test_entry", "=", False)], read):
                item = (row["state"], row.get("end_datetime") if row["state"] == "done" else None)
                if row["partner_id"]:
                    by_partner[(row["survey_id"][0], row["partner_id"][0])].append(item)
                if row["email"]:
                    by_email[(row["survey_id"][0], row["email"].strip().lower())].append(item)
        result = {}
        for registration in registrations:
            survey = expected[registration.id]
            if not survey:
                result[registration.id] = (empty, "none", None)
                continue
            items = []
            if registration.partner_id:
                items += by_partner.get((survey.id, registration.partner_id.id), [])
            if registration.email:
                items += by_email.get((survey.id, registration.email.strip().lower()), [])
            done_at = max((d for s, d in items if s == "done" and d), default=None)
            result[registration.id] = (survey, fr.survey_status(s for s, _d in items), done_at)
        return result


class EventEventSurveyFollowup(models.Model):
    _inherit = "event.event"

    rlq_daily_report = fields.Boolean(
        string="Daily report by e-mail", default=False, copy=False,
        help="If checked, a report is sent every morning until the day after the event: registrations (confirmed, new and cancelled "
             "in the last 24 hours) and survey statistics per ticket. Same recipient as the registration alert.",
    )
    rlq_daily_report_sent = fields.Datetime(
        string="Last daily report", readonly=True, copy=False,
        help="Date of the last daily report sent for this event.",
    )
    rlq_survey_pending_count = fields.Integer(
        string="Surveys not completed", compute="_compute_rlq_survey_pending_count",
        help="Confirmed registrations whose survey (survey of the ticket, otherwise of the event) is not completed yet.",
    )

    def _compute_rlq_survey_pending_count(self):
        for event in self:
            registrations = event._rlq_counted_registrations()
            status = registrations._rlq_survey_status_map()
            event.rlq_survey_pending_count = sum(1 for _s, state, _d in status.values() if state in ("not_started", "in_progress"))

    def _rlq_counted_registrations(self):
        return self.env["event.registration"].sudo().search([("event_id", "in", self.ids), ("state", "in", list(ETATS_COMPTES))])

    def action_rlq_survey_pending(self):
        """Opens « Surveys not completed » for these events."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Surveys not completed"),
            "res_model": "rlq.survey.pending",
            "view_mode": "form",
            "target": "new",
            "context": {"default_event_ids": [(6, 0, self.ids)]},
        }

    def action_rlq_send_daily_report(self):
        """Button « Send the daily report now »: always sends (no 20-hour guard)."""
        sent = []
        for event in self:
            recipient = event._rlq_send_daily_report()
            if not recipient:
                raise UserError(_(
                    "No valid address to send the daily report of « %(event)s » to: e-mail of the event, system parameter "
                    "%(param)s, then e-mail of the company.", event=event.name, param=CLE_PARAMETRE_COURRIEL_INSCRIPTIONS))
            sent.append(recipient)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Daily report"), "message": _("Daily report sent to %(dest)s.", dest=", ".join(sent)),
                       "type": "success", "sticky": False},
        }

    @api.model
    def _rlq_daily_report_lang(self):
        """Language code of the daily report: system parameter PARAM_REPORT_LANG, fr_CA when empty or absent."""
        code = (self.env["ir.config_parameter"].sudo().get_param(PARAM_REPORT_LANG, "") or "").strip() or fr.DEFAULT_REPORT_LANG
        if not fr.report_lang(code)[1]:
            _logger.warning("system parameter %s = %r: neither French nor English, the daily report is sent in French",
                            PARAM_REPORT_LANG, code)
        return code

    @api.model
    def _rlq_create_report_lang_param_if_missing(self):
        """Creates the system parameter with fr_CA ONLY when it does not exist: an existing value is never replaced (an XML
        <record> would be reloaded in « init » mode). Must never prevent the module from loading."""
        try:
            with self.env.cr.savepoint():
                params = self.env["ir.config_parameter"].sudo()
                if not params.search([("key", "=", PARAM_REPORT_LANG)], limit=1):
                    params.create({"key": PARAM_REPORT_LANG, "value": fr.DEFAULT_REPORT_LANG})
        except Exception:  # noqa: BLE001
            _logger.warning("system parameter %s not created", PARAM_REPORT_LANG, exc_info=True)

    def _rlq_daily_report_data(self, since, lang=fr.DEFAULT_REPORT_LANG):
        """(totals, tickets, new registrations) of the daily report; times in the time zone of the event."""
        self.ensure_one()
        context = self.with_context(tz=self.date_tz or "America/Toronto")

        def local(date):
            return fields.Datetime.context_timestamp(context, date).strftime("%Y-%m-%d %H:%M") if date else ""
        registrations = self._rlq_counted_registrations()
        status = registrations._rlq_survey_status_map()
        cancelled = self.env["event.registration"].sudo().search_count([
            ("event_id", "=", self.id), ("state", "=", "cancel"), ("write_date", ">=", since)])
        totals = {"registered": len(registrations), "cancelled": cancelled, "new": 0, "expected": 0,
                  "done": 0, "in_progress": 0, "not_started": 0, "done_24h": 0}
        tickets = {}
        new_registrations = []
        for registration in registrations.sorted(lambda r: (r.create_date or fields.Datetime.now(), r.id), reverse=True):
            survey, state, done_at = status.get(registration.id, (False, "none", None))
            ticket = registration.event_ticket_id if "event_ticket_id" in registration._fields else False
            ticket_name = ticket.name if ticket else fr.texts(lang)["no_ticket"]
            line = tickets.setdefault((ticket_name, survey.title if survey else ""), {
                "name": ticket_name, "survey": survey.title if survey else "", "registered": 0,
                "done": 0, "in_progress": 0, "not_started": 0})
            line["registered"] += 1
            if survey:
                totals["expected"] += 1
                totals[state] += 1
                line[state] += 1
                if state == "done" and done_at and done_at >= since:
                    totals["done_24h"] += 1
            if registration.create_date and registration.create_date >= since:
                totals["new"] += 1
                new_registrations.append({"when": local(registration.create_date), "name": registration.name or "",
                                          "ticket": ticket.name if ticket else "", "survey_state": state if survey else ""})
        return totals, sorted(tickets.values(), key=lambda t: (t["name"].lower(), t["survey"].lower())), new_registrations

    def _rlq_send_daily_report(self):
        """Sends the daily report of this event; returns the recipient, or False when there is no valid address."""
        self.ensure_one()
        event = self.sudo()
        recipient, _source = event._rlq_destinataire_alerte()
        if not recipient:
            _logger.warning("event %s: daily report not sent, no valid address (event e-mail, parameter %s, company e-mail)",
                            event.id, CLE_PARAMETRE_COURRIEL_INSCRIPTIONS)
            return False
        now = fields.Datetime.now()
        lang = event._rlq_daily_report_lang()
        totals, tickets, new_registrations = event._rlq_daily_report_data(now - timedelta(hours=24), lang)
        generated = fields.Datetime.context_timestamp(event.with_context(tz=event.date_tz or "America/Toronto"), now)
        event._rlq_envoyer_courriel(
            recipient, fr.daily_report_subject(event.name, generated.strftime("%Y-%m-%d"), lang),
            fr.daily_report_html(event.name, event._rlq_debut_texte(), generated.strftime("%Y-%m-%d %H:%M %Z"),
                                 totals, tickets, new_registrations, event._rlq_url(), lang=lang),
        )
        event.rlq_daily_report_sent = now
        _logger.info("event %s: daily report sent (%d registrations, %d new)", event.id, totals["registered"], totals["new"])
        return recipient

    @api.model
    def _cron_rlq_daily_report(self):
        """Scheduled action: daily report of every event with the box checked, until the day after its end. Never raises."""
        now = fields.Datetime.now()
        events = self.sudo().search([
            ("rlq_daily_report", "=", True), "|", ("date_end", "=", False), ("date_end", ">=", now - timedelta(days=1)),
        ])
        for event in events:
            if event.rlq_daily_report_sent and event.rlq_daily_report_sent > now - timedelta(hours=DAILY_REPORT_MIN_HOURS):
                continue                                              # scheduled action run twice the same day
            try:
                with self.env.cr.savepoint():
                    event._rlq_send_daily_report()
            except Exception:  # noqa: BLE001 - one event must not stop the others
                _logger.warning("daily report not sent (event %s)", event.id, exc_info=True)


class RlqSurveyPending(models.TransientModel):
    _name = "rlq.survey.pending"
    _description = "Surveys not completed"

    @api.model
    def _default_event_ids(self):
        if self.env.context.get("active_model") == "event.event" and self.env.context.get("active_ids"):
            return [(6, 0, self.env.context["active_ids"])]
        tickets = self.env["event.event.ticket"].sudo().search([("rlq_survey_id", "!=", False)])
        events = tickets.mapped("event_id").filtered(lambda e: not e.date_end or e.date_end >= fields.Datetime.now())
        return [(6, 0, events.ids)]

    event_ids = fields.Many2many("event.event", string="Events", default=_default_event_ids,
                                 help="Events to check. By default: the current and upcoming events whose tickets have a survey.")
    include_started = fields.Boolean(
        string="Include started surveys", default=True,
        help="Also list the people who started the survey without finishing it (their registration is not confirmed either).",
    )
    registration_ids = fields.Many2many("event.registration", string="Registrations", compute="_compute_pending")
    emails = fields.Char(string="E-mail addresses", compute="_compute_pending",
                         help="Addresses of the people to remind, without duplicates, separated by « ; » (to copy into the « To » or "
                              "« Bcc » field of an e-mail).")
    email_count = fields.Integer(string="Addresses", compute="_compute_pending")
    missing_email_count = fields.Integer(string="Without e-mail address", compute="_compute_pending")

    @api.depends("event_ids", "include_started")
    def _compute_pending(self):
        for wizard in self:
            states = ("not_started", "in_progress") if wizard.include_started else ("not_started",)
            registrations = self.env["event.registration"].sudo().search([
                ("event_id", "in", wizard.event_ids.ids), ("state", "in", list(ETATS_COMPTES))])
            status = registrations._rlq_survey_status_map()
            pending = registrations.browse([rid for rid, (_s, state, _d) in status.items() if state in states])
            emails = fr.unique_emails(pending.mapped("email"))
            wizard.registration_ids = pending.sorted(lambda r: (r.event_id.name or "", (r.name or "").lower()))
            wizard.emails = "; ".join(emails)
            wizard.email_count = len(emails)
            wizard.missing_email_count = len(pending.filtered(lambda r: not (r.email or "").strip()))

    def action_open_list(self):
        """The same registrations in a list (filters, grouping, export)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Surveys not completed"),
            "res_model": "event.registration",
            "view_mode": "list,form",
            "views": [(self.env.ref("rlq_survey_report.view_rlq_survey_pending_registration_list").id, "list"), (False, "form")],
            "domain": [("id", "in", self.registration_ids.ids)],
            "context": {"group_by": "event_id"},
        }
