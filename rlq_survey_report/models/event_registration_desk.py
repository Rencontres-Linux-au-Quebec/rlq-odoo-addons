# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
event_registration_desk.py
==========================

Registration desk of an event (v1.121.0): ONE screen (Events > RLQ registration desk, or the button of the event form) for the
volunteers who welcome people on the day of the event.

  - Summary at the top (models/registration_desk_report.py, pure functions):
      * per ticket type and in total: registered, present, surveys completed / started / not started, questions answered and
        not answered;
      * people marked present per hour (time zone of the event), per ticket and in total;
      * counts of the answers to the survey questions checked « Show at the registration desk » (online or on site, lunch...).
  - List of the registrations (not cancelled), sorted by ticket then name, with the state of the survey, « 8/12 » questions
    answered, the answers to the checked questions, and the buttons « Present » and « Undo ».

« Present » uses the native state of Odoo (event.registration.state = « done », action_set_done()): the native registration desk,
the badges and the attendance statistics of Odoo see the same thing. The hour of the check-in is the native field `date_closed`.
« Undo » puts the registration back to « open » and clears `date_closed`.

The survey of a registration is the one of models/event_survey_followup.py (survey of the ticket, otherwise of the event); the
participation is found by the same contact or the same e-mail address. When a person has several participations, the most
advanced one is used (completed, then started), the most recent one among equals. Test entries are ignored.

The questions counted are the questions of the survey (pages excluded). A conditional question that was never shown to the
person counts as « not answered »: Odoo does not record why a question has no answer.
"""
import logging
from collections import defaultdict
from datetime import datetime

from odoo import _, api, fields, models

from . import registration_desk_report as rd
from .registration_desk_report import sort_key

_logger = logging.getLogger(__name__)

STATE_RANK = {"done": 2, "in_progress": 1}
LIST_STATES = ("draft", "open", "done")


class SurveyQuestionRegistrationDesk(models.Model):
    _inherit = "survey.question"

    rlq_registration_desk = fields.Boolean(
        string="Show at the registration desk", default=False,
        help="If checked, the answer of each registered person to this question is shown in the RLQ registration desk of the "
             "event (Events > RLQ registration desk), and the answers are counted per ticket type. Useful for questions such as "
             "« On site or online? » or « Will you be there for lunch? ».",
    )
    rlq_desk_label = fields.Char(
        string="Short label at the registration desk", translate=True,
        help="Short name of this question in the registration desk (for example « Lunch »). Empty: the title of the question.",
    )


def local_time(registration, value, pattern):
    """Formats a UTC datetime in the time zone of the event (otherwise of the user, otherwise America/Toronto); « » when empty."""
    if not value:
        return ""
    zone = registration.event_id.date_tz or registration.env.user.tz or "America/Toronto"
    return fields.Datetime.context_timestamp(registration.with_context(tz=zone), value).strftime(pattern)


class EventRegistrationDesk(models.Model):
    _inherit = "event.registration"

    rlq_departure = fields.Datetime(
        string="Left at", copy=False, readonly=True,
        help="Time when the person left the event, recorded with the « Left » button of the RLQ registration desk.",
    )
    rlq_desk_progress = fields.Char(
        string="Questions answered", compute="_compute_rlq_desk",
        help="Questions answered / questions of the survey expected for this registration (pages excluded). Empty: no survey.",
    )
    rlq_desk_answers = fields.Char(
        string="Answers", compute="_compute_rlq_desk",
        help="Answers of this person to the survey questions checked « Show at the registration desk ».",
    )

    def _compute_rlq_desk(self):
        data = self._rlq_desk_map()
        for registration in self:
            item = data.get(registration.id) or {}
            registration.rlq_desk_progress = rd.progress_text(item.get("questions"), item.get("answered")) or False
            registration.rlq_desk_answers = rd.answers_text(item.get("answers")) or False

    @api.model
    def _rlq_desk_value(self, row, answer_values):
        """Text of one survey.user_input.line (dict of search_read); « » when the line carries no value."""
        answer_type = row.get("answer_type") or ""
        if answer_type == "suggestion":
            value = answer_values.get((row.get("suggested_answer_id") or [False])[0], "")
            matrix_row = answer_values.get((row.get("matrix_row_id") or [False])[0], "")
            return "%s: %s" % (matrix_row, value) if matrix_row and value else value
        value = row.get("value_%s" % answer_type)
        if value in (None, False, ""):
            return ""
        if isinstance(value, float):
            return ("%f" % value).rstrip("0").rstrip(".")
        return str(value)

    def _rlq_desk_map(self):
        """{registration id: {"survey", "state", "questions", "answered", "answers": [(label, [values])]}} for the whole recordset.

        A fixed number of queries whatever the number of registrations. Read with sudo(): a volunteer of the Events application
        does not always have the rights of the Surveys application. Never raises for a missing optional field.
        """
        registrations = self.sudo().filtered("id")
        status = registrations._rlq_survey_status_map()
        survey_ids = sorted({survey.id for survey, _state, _done in status.values() if survey})
        result = {}
        if not survey_ids:
            for registration in registrations:
                result[registration.id] = {"survey": False, "state": "none", "questions": 0, "answered": 0, "answers": []}
            return result

        # Questions of each survey (pages excluded), and the ones shown at the desk.
        questions = self.env["survey.question"].sudo()
        domain = [("survey_id", "in", survey_ids)]
        if "is_page" in questions._fields:
            domain.append(("is_page", "=", False))
        question_count, desk_questions = defaultdict(int), defaultdict(list)
        for question in questions.search(domain, order="sequence, id"):
            question_count[question.survey_id.id] += 1
            if question.rlq_registration_desk:
                desk_questions[question.survey_id.id].append((question.id, question.rlq_desk_label or question.title or ""))

        # Best participation of each (survey, contact) and (survey, e-mail address).
        by_partner, by_email = defaultdict(list), defaultdict(list)
        inputs = self.env["survey.user_input"].sudo()
        for row in inputs.search_read([("survey_id", "in", survey_ids), ("test_entry", "=", False)],
                                      ["survey_id", "partner_id", "email", "state"]):
            item = (STATE_RANK.get(row["state"], 0), row["id"])
            if row["partner_id"]:
                by_partner[(row["survey_id"][0], row["partner_id"][0])].append(item)
            if row["email"]:
                by_email[(row["survey_id"][0], row["email"].strip().lower())].append(item)
        chosen = {}
        for registration in registrations:
            survey = status[registration.id][0]
            if not survey:
                continue
            items = []
            if registration.partner_id:
                items += by_partner.get((survey.id, registration.partner_id.id), [])
            if registration.email:
                items += by_email.get((survey.id, registration.email.strip().lower()), [])
            if items:
                chosen[registration.id] = max(items)[1]

        # Lines of the chosen participations: questions answered, and the values of the questions shown at the desk.
        lines = self.env["survey.user_input.line"].sudo()
        wanted = ["user_input_id", "question_id", "skipped", "answer_type", "suggested_answer_id", "matrix_row_id",
                  "value_char_box", "value_text_box", "value_numerical_box", "value_date", "value_datetime"]
        read = [name for name in wanted if name in lines._fields]
        rows = lines.search_read([("user_input_id", "in", sorted(set(chosen.values())))], read, order="id") if chosen else []
        answer_ids = {(row.get(name) or [False])[0] for row in rows for name in ("suggested_answer_id", "matrix_row_id")}
        answer_values = {answer.id: answer.value or "" for answer in
                         self.env["survey.question.answer"].sudo().browse(sorted(a for a in answer_ids if a)).exists()}
        answered, values = defaultdict(set), defaultdict(list)
        for row in rows:
            if row.get("skipped") or not row.get("question_id"):
                continue
            input_id, question_id = row["user_input_id"][0], row["question_id"][0]
            answered[input_id].add(question_id)
            text = self._rlq_desk_value(row, answer_values)
            if text:
                values[(input_id, question_id)].append(text)

        for registration in registrations:
            survey, state, _done = status[registration.id]
            if not survey:
                result[registration.id] = {"survey": False, "state": "none", "questions": 0, "answered": 0, "answers": []}
                continue
            input_id = chosen.get(registration.id)
            result[registration.id] = {
                "survey": survey, "state": state, "questions": question_count.get(survey.id, 0),
                "answered": len(answered.get(input_id, ())),
                "answers": [(label, values.get((input_id, question_id), [])) for question_id, label in desk_questions.get(survey.id, [])],
            }
        return result

    def _rlq_desk_rows(self):
        """Rows of registration_desk_report (one per registration); the hour of the check-in is in the time zone of the event."""
        data = self._rlq_desk_map()
        rows = []
        for registration in self.sudo().filtered("id"):
            item = data.get(registration.id) or {}
            present = registration.state == "done"
            closed = registration.date_closed if "date_closed" in registration._fields else False
            hour = local_time(registration, closed, "%Y-%m-%d %H") if present and closed else None
            ticket = registration.event_ticket_id if "event_ticket_id" in registration._fields else False
            rows.append({"ticket": ticket.name if ticket else "", "present": present, "hour": hour,
                         "survey_state": item.get("state", "none"), "questions": item.get("questions", 0),
                         "answered": item.get("answered", 0), "answers": item.get("answers", []),
                         "registered": local_time(registration, registration.create_date, "%Y-%m-%d %H:%M"),
                         "arrived": local_time(registration, closed, "%Y-%m-%d %H:%M") if present else "",
                         "departed": local_time(registration, registration.rlq_departure, "%Y-%m-%d %H:%M"),
                         "event_date": registration.event_id.date_begin or False})
        return rows

    def action_rlq_desk_present(self):
        """Button « Present »: native state « done » (the hour is recorded by Odoo in date_closed). Cancelled: left alone."""
        registrations = self.filtered(lambda r: r.state not in ("done", "cancel"))
        if registrations:
            if hasattr(registrations, "action_set_done"):
                registrations.action_set_done()
            else:
                registrations.write({"state": "done"})
            _logger.info("registration desk: %d registration(s) marked present by user %s", len(registrations), self.env.uid)
        return True

    def action_rlq_desk_depart(self):
        """Button « Left »: records the time of departure (now). Only for people present, and only once."""
        registrations = self.filtered(lambda r: r.state == "done" and not r.rlq_departure)
        if registrations:
            registrations.write({"rlq_departure": fields.Datetime.now()})
            _logger.info("registration desk: %d departure(s) recorded by user %s", len(registrations), self.env.uid)
        return True

    def action_rlq_desk_depart_undo(self):
        """Button « Undo the departure »: clears the time of departure."""
        registrations = self.filtered("rlq_departure")
        if registrations:
            registrations.write({"rlq_departure": False})
        return True

    def action_rlq_desk_undo(self):
        """Button « Undo »: a registration marked present by mistake goes back to « open »; the hour of the check-in is cleared."""
        registrations = self.filtered(lambda r: r.state == "done")
        if registrations:
            vals = {"state": "open"}
            if "date_closed" in registrations._fields:
                vals["date_closed"] = False
            registrations.write(vals)
            _logger.info("registration desk: presence of %d registration(s) undone by user %s", len(registrations), self.env.uid)
        return True


class EventEventRegistrationDesk(models.Model):
    _inherit = "event.event"

    def action_rlq_registration_desk(self):
        """Opens the RLQ registration desk of this event."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("RLQ registration desk"),
            "res_model": "rlq.registration.desk",
            "view_mode": "form",
            "target": "current",
            "context": {"default_event_id": self.id},
        }


class RlqRegistrationDesk(models.TransientModel):
    _name = "rlq.registration.desk"
    _description = "RLQ registration desk"

    @api.model
    def _default_event_id(self):
        """The event of the context, otherwise the event in progress or the next one, otherwise the most recent one."""
        if self.env.context.get("active_model") == "event.event" and self.env.context.get("active_id"):
            return self.env.context["active_id"]
        events = self.env["event.event"]
        event = events.search([("date_end", ">=", fields.Datetime.now())], order="date_begin, id", limit=1)
        return (event or events.search([], order="date_begin desc, id desc", limit=1)).id or False

    event_id = fields.Many2one("event.event", string="Event", required=True, default=_default_event_id,
                               help="By default: the event in progress, otherwise the next one.")
    search_text = fields.Char(string="Search",
                              help="Part of a name, an e-mail address or a company: only the matching registrations are listed. "
                                   "The summary always counts the whole event.")
    hide_present = fields.Boolean(string="Hide the people already present", default=False)
    summary_html = fields.Html(string="Summary", compute="_compute_desk", sanitize=False)
    registration_ids = fields.Many2many("event.registration", string="Registrations", compute="_compute_desk")
    registration_count = fields.Integer(string="Registrations listed", compute="_compute_desk")

    @api.depends("event_id")
    def _compute_display_name(self):
        for wizard in self:
            wizard.display_name = _("Registration desk: %(event)s", event=wizard.event_id.name) if wizard.event_id \
                else _("RLQ registration desk")

    def _rlq_all_registrations(self):
        self.ensure_one()
        if not self.event_id:
            return self.env["event.registration"]
        return self.env["event.registration"].search([("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))])

    @staticmethod
    def _rlq_haystack(registration):
        parts = [registration.name, registration.email]
        if "company_name" in registration._fields:
            parts.append(registration.company_name)
        return " ".join(" ".join(str(p or "").lower().split()) for p in parts)

    def _rlq_listed(self, registrations):
        """The registrations of the list: filters « hide present » and « search », sorted by ticket then name."""
        self.ensure_one()
        listed = registrations
        if self.hide_present:
            listed = listed.filtered(lambda r: r.state != "done")
        needle = " ".join((self.search_text or "").lower().split())
        if needle:
            listed = listed.filtered(lambda r: needle in self._rlq_haystack(r))
        has_ticket = "event_ticket_id" in listed._fields
        # Two passes: ticket then name (accent-insensitive), then the most recent event first (Python's sort is stable).
        listed = listed.sorted(lambda r: (sort_key(r.event_ticket_id.name if has_ticket else ""), sort_key(r.name), r.id))
        return listed.sorted(lambda r: r.event_id.date_begin or datetime.min, reverse=True)

    @api.depends("event_id", "search_text", "hide_present")
    def _compute_desk(self):
        for wizard in self:
            registrations = wizard._rlq_all_registrations()
            wizard.summary_html = rd.desk_summary_html(registrations._rlq_desk_rows(), self.env.lang or rd.DEFAULT_LANG)
            listed = wizard._rlq_listed(registrations)
            wizard.registration_ids = listed
            wizard.registration_count = len(listed)

    def action_refresh(self):
        """Button « Refresh »: the form is read again, so the summary and the list are computed again."""
        return True

    def action_open_list(self):
        """The registrations of the event in a full list (native search, filters, grouping by ticket, export), same buttons."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Registration desk: %(event)s", event=self.event_id.name),
            "res_model": "event.registration",
            "view_mode": "list,form",
            "views": [(self.env.ref("rlq_survey_report.view_rlq_registration_desk_registration_list").id, "list"), (False, "form")],
            "domain": [("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))],
            "context": {"group_by": "event_ticket_id", "create": False},
        }
