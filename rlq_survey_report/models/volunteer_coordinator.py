# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
volunteer_coordinator.py
========================

« Coordination des bénévoles » (v1.122.0): one table for the volunteers' coordinator of an event.

Only the registrations whose ticket name says « bénévole » are listed, and their answers come ONLY from the survey of that
volunteer ticket. Columns: name (link to the chat with the volunteer), date and time of the registration, type (virtual or on
site, from the question whose title contains « virtuel »), languages spoken (question containing « langue »), arrival (desk),
departure (desk), and one column per choice of the question containing « rôle » (« Rôles pendant l'événement (en présentiel) »).

The three questions are found by their title, ignoring case and accents. A question that is not found leaves its columns empty
and a note is shown above the table.

Sorting by clicking a column header is NOT available here: the columns are generated from the survey (one per role), which an
Odoo list cannot do. Standalone rules are in models/registration_desk_report.py (volunteer_table_html, is_volunteer_ticket).
"""
from html import escape

from odoo import _, api, fields, models

from . import registration_desk_report as rd
from .event_registration_desk import LIST_STATES, local_time

CHAT_PATH = "/chat/%d"


def _answer_text(values, input_id, question):
    """Answers of one question, joined with commas; « » when there is no question or no answer."""
    if not question or not input_id:
        return ""
    return ", ".join(values.get((input_id, question.id), []))


class RlqVolunteerCoordinator(models.TransientModel):
    _name = "rlq.volunteer.coordinator"
    _description = "Volunteers coordinator"

    @api.model
    def _default_event_id(self):
        return self.env["rlq.registration.desk"]._default_event_id()

    event_id = fields.Many2one("event.event", string="Event", required=True, default=_default_event_id,
                               help="By default: the event in progress, otherwise the next one.")
    table_html = fields.Html(string="Volunteers", compute="_compute_table", sanitize=False)

    @api.depends("event_id")
    def _compute_table(self):
        for wizard in self:
            wizard.table_html = wizard._rlq_table_html()

    def action_refresh(self):
        """Button « Refresh »: the table is computed again."""
        return True

    def _rlq_volunteer_registrations(self):
        self.ensure_one()
        if not self.event_id:
            return self.env["event.registration"].sudo()
        registrations = self.env["event.registration"].sudo().search([
            ("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))])
        return registrations.filtered(lambda r: r.event_ticket_id and rd.is_volunteer_ticket(r.event_ticket_id.name))

    def _rlq_questions(self, survey):
        """(type question, languages question, roles question) of a survey, found by title; None when missing."""
        found = {"type": None, "languages": None, "roles": None}
        for question in self.env["survey.question"].sudo().search([("survey_id", "=", survey.id)], order="sequence, id"):
            if getattr(question, "is_page", False):
                continue
            key = rd.sort_key(question.title)
            if found["roles"] is None and "role" in key:
                found["roles"] = question
            elif found["type"] is None and "virtuel" in key:
                found["type"] = question
            elif found["languages"] is None and "langue" in key:
                found["languages"] = question
        return found

    def _rlq_chosen_inputs(self, registrations, survey):
        """{registration id: survey.user_input id}: the most advanced participation of the same contact or e-mail address."""
        inputs = self.env["survey.user_input"].sudo().search([("survey_id", "=", survey.id), ("test_entry", "=", False)])
        rank = {"done": 2, "in_progress": 1}
        by_partner, by_email = {}, {}
        for user_input in inputs:
            item = (rank.get(user_input.state, 0), user_input.id)
            if user_input.partner_id:
                by_partner.setdefault(user_input.partner_id.id, []).append(item)
            if user_input.email:
                by_email.setdefault(user_input.email.strip().lower(), []).append(item)
        chosen = {}
        for registration in registrations:
            items = list(by_partner.get(registration.partner_id.id, [])) if registration.partner_id else []
            if registration.email:
                items += by_email.get(registration.email.strip().lower(), [])
            if items:
                chosen[registration.id] = max(items)[1]
        return chosen

    def _rlq_values(self, input_ids):
        """{(input id, question id): [text, ...]} read from the answer lines (skipped questions left out)."""
        if not input_ids:
            return {}
        lines = self.env["survey.user_input.line"].sudo().search_read(
            [("user_input_id", "in", sorted(input_ids))],
            ["user_input_id", "question_id", "skipped", "answer_type", "suggested_answer_id", "matrix_row_id",
             "value_char_box", "value_text_box", "value_numerical_box", "value_date", "value_datetime"], order="id")
        answer_ids = {(row.get(name) or [False])[0] for row in lines for name in ("suggested_answer_id", "matrix_row_id")}
        answers = {a.id: a.value or "" for a in self.env["survey.question.answer"].sudo().browse(
            sorted(i for i in answer_ids if i)).exists()}
        registration_model = self.env["event.registration"]
        values = {}
        for row in lines:
            if row.get("skipped") or not row.get("question_id"):
                continue
            text = registration_model._rlq_desk_value(row, answers)
            if text:
                values.setdefault((row["user_input_id"][0], row["question_id"][0]), []).append(text)
        return values

    def _rlq_table_html(self):
        self.ensure_one()
        registrations = self._rlq_volunteer_registrations()
        if not registrations:
            return rd.volunteer_table_html([], [], self.env.lang, "")
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or "").rstrip("/")
        roles, rows, notes = [], [], []
        by_survey = {}
        for registration in registrations:
            by_survey.setdefault(registration.event_ticket_id.rlq_survey_id.id or 0, []).append(registration)
        for survey_id, group in by_survey.items():
            if not survey_id:
                notes.append(_("Volunteer tickets without survey: their volunteers are not listed."))
                continue
            survey = self.env["survey.survey"].sudo().browse(survey_id)
            questions = self._rlq_questions(survey)
            for label, key in ((_("Type question not found in the survey"), "type"),
                               (_("Languages question not found in the survey"), "languages"),
                               (_("Roles question not found in the survey"), "roles")):
                if not questions[key]:
                    notes.append(label + " (%s)" % survey.title)
            chosen = self._rlq_chosen_inputs(group, survey)
            values = self._rlq_values(set(chosen.values()))
            if questions["roles"]:
                for answer in questions["roles"].suggested_answer_ids:
                    if answer.value and answer.value not in roles:
                        roles.append(answer.value)
            for registration in group:
                input_id = chosen.get(registration.id)
                rows.append({
                    "name": registration.name or registration.partner_id.name or "",
                    "partner_id": registration.partner_id.id if registration.partner_id else False,
                    "registered": local_time(registration, registration.create_date, "%Y-%m-%d %H:%M"),
                    "type": _answer_text(values, input_id, questions["type"]),
                    "languages": _answer_text(values, input_id, questions["languages"]),
                    "arrived": local_time(registration, registration.date_closed, "%Y-%m-%d %H:%M")
                    if registration.state == "done" else "",
                    "departed": local_time(registration, registration.rlq_departure, "%Y-%m-%d %H:%M"),
                    "roles": set(values.get((input_id, questions["roles"].id), [])) if questions["roles"] and input_id else set(),
                })
        rows.sort(key=lambda row: (rd.sort_key(row["name"]), row["registered"]))
        html = rd.volunteer_table_html(rows, roles, self.env.lang, base_url)
        if notes:
            html = "".join("<p><em>%s</em></p>" % escape(note) for note in notes) + html
        return html
