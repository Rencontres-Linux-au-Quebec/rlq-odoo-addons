# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
volunteer_expertise.py
======================

« Expertises des bénévoles » (Events / Surveys > Rapports RLQ > Volunteer expertise, v1.137.0): the answers of the
volunteers to the survey questions checked « Show in Volunteer expertise » (survey.question.rlq_volunteer_expertise), for
example « Quelles sont vos expertises ? », « Distributions Linux que vous connaissez ».

The same volunteers as the page « Gestion des bénévoles » (volunteer_coordinator.py, _rlq_volunteer_base()): the registrations
whose ticket name says « bénévole », with the answers of the survey of that ticket only. A choice question gives one column per
choice (1 when chosen: the totals count the volunteers who have this expertise); a text question gives one text column. The
questions of several volunteer surveys with the same title share their columns.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from . import registration_desk_report as rd
from .event_registration_desk import (ANSWERS_URL, CHAT_URL, can_contact, contact_action, guide_action, local_zone,
                                      program_stamp, registration_list_action)
from .volunteer_coordinator import CHOICE_TYPES, download_xlsx, openpyxl


class SurveyQuestionVolunteerExpertise(models.Model):
    _inherit = "survey.question"

    rlq_volunteer_expertise = fields.Boolean(
        string="Show in « Volunteer expertise »", default=False,
        help="If checked, the answer of each volunteer to this question is shown in the page « Volunteer expertise » "
             "(Rapports RLQ): one column per choice, with the number of volunteers who chose it. Useful for questions such as "
             "« What are your areas of expertise? ». Only the survey of the volunteer ticket is read.",
    )


class RlqVolunteerExpertise(models.TransientModel):
    _name = "rlq.volunteer.expertise"
    _inherit = ["rlq.pi.confirmation.mixin", "rlq.last.event.mixin"]
    _description = "Volunteer expertise"

    @api.model
    def _default_event_id(self):
        return self.env["rlq.registration.desk"]._default_event_id()

    event_id = fields.Many2one("event.event", string="Event", required=True, default=_default_event_id,
                               help="By default: the event in progress, otherwise the next one.")
    survey_filter = fields.Selection(
        [("all", "All"), ("done", "Survey completed"), ("in_progress", "Survey started"), ("not_started", "Survey not started")],
        string="Survey", default="all", required=True, help="Lists only the volunteers whose survey is in this state.")
    sort_by = fields.Selection(
        [("name", "Name"), ("registered", "Registration date"), ("survey", "Survey")],
        string="Sort by", default="name", required=True,
        help="Order of the table. Case and accents are ignored; equal values are sorted by name.")
    sort_desc = fields.Boolean(string="Descending", default=False, help="Reverses the order of the table.")
    table_html = fields.Html(string="Volunteer expertise", compute="_compute_table", sanitize=False)

    @api.depends("event_id")
    def _compute_display_name(self):
        for wizard in self:
            wizard.display_name = (_("Volunteer expertise: %(event)s", event=wizard.event_id.name) if wizard.event_id
                                   else _("Volunteer expertise"))

    @api.depends("event_id", "survey_filter", "sort_by", "sort_desc")
    def _compute_table(self):
        for wizard in self:
            rows, columns, notes = wizard._rlq_table_data()
            wizard.table_html = program_stamp(self.env, wizard.event_id) + rd.expertise_table_html(
                rows, columns, self.env.lang or rd.DEFAULT_LANG, notes)

    def _rlq_coordinator(self):
        """A page « Gestion des bénévoles » in memory, for the same volunteers and the same answers."""
        return self.env["rlq.volunteer.coordinator"].new({"event_id": self.event_id.id, "survey_filter": self.survey_filter})

    def _rlq_table_data(self):
        """(rows, columns, notes). columns: [{"title", "choices"}] (choices empty: a text question); each row has "answers",
        one list of answers per column."""
        self.ensure_one()
        if not self.event_id:
            return [], [], []
        registrations, status, values, chosen = self._rlq_coordinator()._rlq_volunteer_base()
        columns, column_index, by_survey, notes = [], {}, {}, []
        questions = self.env["survey.question"].sudo()
        for survey in {status[r.id][0] for r in registrations if status[r.id][0]}:
            domain = [("survey_id", "=", survey.id), ("rlq_volunteer_expertise", "=", True)]
            if "is_page" in questions._fields:
                domain.append(("is_page", "=", False))
            found = by_survey[survey.id] = []
            for question in questions.search(domain, order="sequence, id"):
                title = question.rlq_desk_label or question.title or ""
                choices = [a.value or "" for a in question.suggested_answer_ids if a.value] \
                    if question.question_type in CHOICE_TYPES else []
                key = rd.sort_key(title)
                if key not in column_index:
                    column_index[key] = len(columns)
                    columns.append({"title": title, "choices": []})
                column = columns[column_index[key]]
                known = {rd.sort_key(c) for c in column["choices"]}
                column["choices"] += [c for c in choices if rd.sort_key(c) not in known]
                found.append((question.id, column_index[key]))
            if not found:
                notes.append(_("No question checked « Show in Volunteer expertise » in the survey « %(survey)s ».",
                               survey=survey.title))
        rows = []
        for registration in registrations:
            survey, state, _done = status[registration.id]
            if self.survey_filter and self.survey_filter != "all" and state != self.survey_filter:
                continue
            input_id = chosen.get(registration.id)
            answers = [[] for _c in columns]
            for qid, index in by_survey.get(survey.id, ()) if survey else ():
                if input_id:
                    answers[index] = answers[index] + list(values.get((input_id, qid), []))
            zone = local_zone(self.env, registration.event_id)
            registered_at = fields.Datetime.context_timestamp(registration.with_context(tz=zone), registration.create_date) \
                if registration.create_date else None
            rows.append({
                "name": registration.name or registration.partner_id.name or "",
                "chat_url": CHAT_URL % registration.partner_id.id if registration.partner_id else None,
                "registered": registered_at.strftime("%Y-%m-%d %H:%M") if registered_at else "",
                "email": registration.email or registration.partner_id.email or "",
                "ticket": registration.event_ticket_id.name or "",
                "survey": state, "answers": answers, "registration_id": registration.id,
                "answers_url": ANSWERS_URL % input_id if input_id else None,
            })
        return rd.sort_volunteer_rows(rows, self.sort_by or "name", self.sort_desc), columns, notes

    def action_refresh(self):
        return True

    def action_open_guide(self):
        return guide_action(self.env, "expertises-benevoles")

    def _rlq_listed_registrations(self):
        rows = self._rlq_table_data()[0]
        return self.env["event.registration"].browse([row["registration_id"] for row in rows])

    def action_open_list(self):
        self.ensure_one()
        guard = self._rlq_pi_guard("action_open_list")
        if guard:
            return guard
        return registration_list_action(self.env, _("Volunteer expertise: %(event)s", event=self.event_id.name),
                                        [("id", "in", self._rlq_listed_registrations().ids)], self.event_id.id)

    def action_contact(self):
        self.ensure_one()
        if not can_contact(self.env):                                    # v1.138.0: before the confirmation window
            raise AccessError(_("Only the administrators of the surveys or of the events may contact the participants."))
        guard = self._rlq_pi_guard("action_contact")
        if guard:
            return guard
        return contact_action(self.env, self._rlq_listed_registrations())

    def action_export_excel(self):
        """The table in an .xlsx file: one column per choice with the number 1, so that it can be summed or pivoted."""
        self.ensure_one()
        guard = self._rlq_pi_guard("action_export_excel")
        if guard:
            return guard
        if openpyxl is None:
            raise UserError(_("The spreadsheet export needs the Python library « openpyxl », which is not installed on this server "
                              "(pip install openpyxl)."))
        rows, columns, _notes = self._rlq_table_data()
        if not rows:
            raise UserError(_("No volunteer to export for this event."))
        content = self._rlq_coordinator()._rlq_workbook([rd.expertise_export_sheet(rows, columns, self.env.lang or rd.DEFAULT_LANG)])
        return download_xlsx(self, content, "Expertises-benevoles",
                             _("Volunteer expertise: %(event)s", event=self.event_id.name), len(rows))
