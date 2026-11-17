# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
volunteer_coordinator.py
========================

« Bénévoles » (Events > Volunteers, v1.122.0, reworked in v1.123.0): one table for the volunteers' coordinator of an event.

Only the registrations whose ticket name says « bénévole » are listed, and their answers come ONLY from the survey of that
volunteer ticket. Columns: name (link to talk to the volunteer on Odoo), date and time of the registration, state of the
survey, type (on site or online), languages spoken, arrival and departure (registration desk), the other questions checked
« Show at the registration desk », then one column per choice of EVERY roles question (« Rôles pendant l'événement (en
présentiel) ? » first, then the others), under the title of the question.

The questions are found by their wording (registration_desk_report.find_volunteer_questions), case and accents ignored:
roles = title containing « rôle »; languages = title containing « langue »; type = another choice question whose title or
choices speak of on site / online. Without a type question, the type is deduced from the roles questions the volunteer
answered (« (en présentiel) » / « (en virtuel) » in their titles). A note above the table says what was not found.

The table is HTML (the role columns depend on the survey, which an Odoo list cannot do): it is sorted and filtered with the
fields above it (« Sort by », « Descending », « Survey »), not by clicking the column headers.
"""
import base64
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import registration_desk_report as rd
from . import report_builder as rb
from .event_registration_desk import (ANSWERS_URL, LIST_STATES, contact_action, guide_action, local_time, local_zone,
                                      program_stamp, registration_list_action)

try:
    import openpyxl
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover - reported to the user when the export is asked
    openpyxl = None

_logger = logging.getLogger(__name__)

CHAT_URL = "/rlq_survey_report/chat/%d"
CHOICE_TYPES = ("simple_choice", "multiple_choice")


class RlqVolunteerCoordinator(models.TransientModel):
    _name = "rlq.volunteer.coordinator"
    _inherit = ["rlq.pi.confirmation.mixin"]                              # v1.136.0: confirmation once per page
    _description = "Volunteers"

    @api.model
    def _default_event_id(self):
        return self.env["rlq.registration.desk"]._default_event_id()

    event_id = fields.Many2one("event.event", string="Event", required=True, default=_default_event_id,
                               help="By default: the event in progress, otherwise the next one.")
    survey_filter = fields.Selection(
        [("all", "All"), ("done", "Survey completed"), ("in_progress", "Survey started"), ("not_started", "Survey not started")],
        string="Survey", default="all", required=True, help="Lists only the volunteers whose survey is in this state.")
    sort_by = fields.Selection(
        [("name", "Name"), ("registered", "Registration date"), ("survey", "Survey"), ("type", "Type"),
         ("languages", "Languages spoken"), ("arrived", "Arrival"), ("departed", "Departure"), ("roles", "Number of roles")],
        string="Sort by", default="name", required=True,
        help="Order of the table. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by name.")
    sort_desc = fields.Boolean(string="Descending", default=False, help="Reverses the order of the table.")
    table_html = fields.Html(string="Volunteers", compute="_compute_table", sanitize=False)

    @api.depends("event_id")
    def _compute_display_name(self):
        for wizard in self:
            wizard.display_name = _("Volunteers: %(event)s", event=wizard.event_id.name) if wizard.event_id else _("Volunteers")

    @api.depends("event_id", "survey_filter", "sort_by", "sort_desc")
    def _compute_table(self):
        for wizard in self:
            # v1.126.0: the program name, version, local date and time come FIRST, above the table.
            wizard.table_html = program_stamp(self.env, wizard.event_id) + wizard._rlq_table_html()

    def action_refresh(self):
        """Button « Refresh »: the form is read again, so the table is computed again."""
        return True

    def action_open_guide(self):
        """v1.134.0: button « Help for this page »: the user guide, opened at the section of the volunteers."""
        return guide_action(self.env, "benevoles")

    def _rlq_listed_registrations(self):
        """The registrations of the volunteers shown in the table (same « Survey » filter)."""
        rows = self._rlq_table_data()[0]
        return self.env["event.registration"].browse([row["registration_id"] for row in rows])

    def action_open_list(self):
        """v1.135.0: button « Open as a list », as at the registration desk: the volunteers of the table in the full list
        (search on every column, filters, grouping, export, buttons « Present », « See the answers »...)."""
        self.ensure_one()
        guard = self._rlq_pi_guard("action_open_list")
        if guard:
            return guard
        registrations = self._rlq_listed_registrations()
        return registration_list_action(self.env, _("Volunteers: %(event)s", event=self.event_id.name),
                                        [("id", "in", registrations.ids)], self.event_id.id)

    def action_contact(self):
        """v1.135.0: button « Contact the participants »: an e-mail to each volunteer of the table."""
        self.ensure_one()
        guard = self._rlq_pi_guard("action_contact")
        if guard:
            return guard
        return contact_action(self.env, self._rlq_listed_registrations())

    def _rlq_volunteer_registrations(self):
        """Registrations (not cancelled) of the event whose ticket is a volunteer ticket."""
        self.ensure_one()
        registrations = self.env["event.registration"].sudo()
        if not self.event_id or "event_ticket_id" not in registrations._fields:
            return registrations
        registrations = registrations.search([("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))])
        return registrations.filtered(lambda r: r.event_ticket_id and rd.is_volunteer_ticket(r.event_ticket_id.name))

    def _rlq_survey_layout(self, survey):
        """The questions of one volunteer survey used by the table.

        Returns {"roles": [(question id, title, [choices])], "languages": id or None, "type": id or None,
                 "arrival": id or None, "departure": id or None, "extra": [(question id, label)]}
        (extra: the other questions checked « Show at the registration desk »).
        """
        domain = [("survey_id", "=", survey.id)]
        questions = self.env["survey.question"].sudo()
        if "is_page" in questions._fields:
            domain.append(("is_page", "=", False))
        questions = questions.search(domain, order="sequence, id")
        described = [{"id": q.id, "title": q.title or "", "is_choice": q.question_type in CHOICE_TYPES,
                      "choices": [a.value or "" for a in q.suggested_answer_ids]} for q in questions]
        found = rd.find_volunteer_questions(described)
        by_id = {q["id"]: q for q in described}
        used = set(found["roles"]) | {found["languages"], found["type"], found["arrival"], found["departure"]}
        return {
            "roles": [(qid, by_id[qid]["title"], [c for c in by_id[qid]["choices"] if c]) for qid in found["roles"]],
            "languages": found["languages"], "type": found["type"],
            "arrival": found["arrival"], "departure": found["departure"],
            "extra": [(q.id, q.rlq_desk_label or q.title or "") for q in questions if q.rlq_registration_desk and q.id not in used],
        }

    def _rlq_table_html(self):
        self.ensure_one()
        rows, groups, extra_labels, notes = self._rlq_table_data()
        return rd.volunteer_table_html(rows, groups, self.env.lang or rd.DEFAULT_LANG, extra_columns=extra_labels, notes=notes)

    def _rlq_table_data(self):
        """(rows, role groups, labels of the extra columns, notes) of the table: shared by the screen and the spreadsheet."""
        self.ensure_one()
        lang = self.env.lang or rd.DEFAULT_LANG
        registrations = self._rlq_volunteer_registrations()
        if not registrations:
            return [], [], [], []
        # The survey of the volunteer TICKET only (never the survey of the event).
        empty = self.env["survey.survey"].sudo().browse()
        status = registrations._rlq_survey_status_map()
        for registration in registrations:
            survey = registration.event_ticket_id.rlq_survey_id
            if not survey:
                status[registration.id] = (empty, "none", None)
            elif status[registration.id][0] != survey:                      # defensive: the map already prefers the ticket
                status[registration.id] = (survey, status[registration.id][1], None)
        _inputs, _answered, values, chosen = registrations._rlq_desk_participations(status)

        layouts, notes = {}, []
        groups, group_index = [], {}                                         # role columns, shared by every volunteer survey
        extra_labels, extra_index = [], {}
        for survey in {status[r.id][0] for r in registrations if status[r.id][0]}:
            layout = layouts[survey.id] = self._rlq_survey_layout(survey)
            for _qid, title, choices in layout["roles"]:
                key = rd.sort_key(title)
                if key not in group_index:
                    group_index[key] = len(groups)
                    groups.append({"title": title, "choices": []})
                group = groups[group_index[key]]
                group["choices"] += [c for c in choices if rd.sort_key(c) not in {rd.sort_key(x) for x in group["choices"]}]
            for _qid, label in layout["extra"]:
                if rd.sort_key(label) not in extra_index:
                    extra_index[rd.sort_key(label)] = len(extra_labels)
                    extra_labels.append(label)
            if not layout["roles"]:
                notes.append(_("No question about the roles (title containing « rôle ») in the survey « %(survey)s ».", survey=survey.title))
            if not layout["languages"]:
                notes.append(_("No question about the languages (title containing « langue ») in the survey « %(survey)s ».",
                               survey=survey.title))
            if not layout["type"]:
                if any(rd.role_kind(title) for _qid, title, _choices in layout["roles"]):
                    notes.append(_("The survey « %(survey)s » has no question about the type (on site or online): the type is deduced "
                                   "from the roles questions that the volunteer answered.", survey=survey.title))
                else:
                    notes.append(_("No question about the type (on site or online) in the survey « %(survey)s ».", survey=survey.title))
            if not layout["arrival"] or not layout["departure"]:
                notes.append(_("The survey « %(survey)s » has no question about the hour of arrival or of departure: the hours shown "
                               "are those recorded at the registration desk (« Present », « Left »).", survey=survey.title))
        if any(not status[r.id][0] for r in registrations):
            notes.append(_("Some volunteer tickets have no survey: their volunteers are listed without answers."))

        rows = []
        for registration in registrations:
            survey, state, _done = status[registration.id]
            layout = layouts.get(survey.id) if survey else None
            input_id = chosen.get(registration.id)
            roles, extra, kinds, type_text, languages_list = [[] for _g in groups], [""] * len(extra_labels), [], "", []
            # Hours: the ones the volunteer PLANS, answered in the survey (v1.126.0); without such a question in the survey,
            # the hours recorded at the registration desk.
            present = registration.state == "done"
            arrived = local_time(registration, registration.date_closed, "%Y-%m-%d %H:%M") if present else ""
            departed = local_time(registration, registration.rlq_departure, "%Y-%m-%d %H:%M")
            if layout and layout["arrival"]:
                arrived = ", ".join(values.get((input_id, layout["arrival"]), [])) if input_id else ""
            if layout and layout["departure"]:
                departed = ", ".join(values.get((input_id, layout["departure"]), [])) if input_id else ""
            if layout and input_id:
                for qid, title, _choices in layout["roles"]:
                    answers = values.get((input_id, qid), [])
                    roles[group_index[rd.sort_key(title)]] = answers
                    if answers and rd.role_kind(title):
                        kinds.append(rd.role_kind(title))
                for qid, label in layout["extra"]:
                    extra[extra_index[rd.sort_key(label)]] = ", ".join(values.get((input_id, qid), []))
                languages_list = list(values.get((input_id, layout["languages"]), [])) if layout["languages"] else []
                type_text = ", ".join(values.get((input_id, layout["type"]), [])) if layout["type"] else rd.deduced_type(kinds, lang)
            if self.survey_filter and self.survey_filter != "all" and state != self.survey_filter:
                continue
            zone = local_zone(self.env, registration.event_id)
            registered_at = fields.Datetime.context_timestamp(registration.with_context(tz=zone), registration.create_date) \
                if registration.create_date else None
            rows.append({
                "name": registration.name or registration.partner_id.name or "",
                "chat_url": CHAT_URL % registration.partner_id.id if registration.partner_id else None,
                "registered": registered_at.strftime("%Y-%m-%d %H:%M") if registered_at else "",
                "registered_at": registered_at.replace(tzinfo=None, second=0, microsecond=0) if registered_at else None,
                "email": registration.email or registration.partner_id.email or "",
                "ticket": registration.event_ticket_id.name or "",
                "survey": state, "type": type_text, "languages": ", ".join(languages_list), "languages_list": languages_list,
                "arrived": arrived, "departed": departed, "roles": roles, "extra": extra,
                # v1.135.0: the survey cell is a link to every answer of the person; the id serves « Contact » and the list.
                "answers_url": ANSWERS_URL % input_id if input_id else None, "registration_id": registration.id,
            })
        rows = rd.sort_volunteer_rows(rows, self.sort_by or "name", self.sort_desc)
        return rows, groups, extra_labels, notes

    # ------------------------------------------------------------------ spreadsheet export (v1.126.0)

    def _rlq_workbook(self, sheets):
        """The .xlsx file (bytes) of [(title, header, lines)]: bold header, frozen first line, filter on every column."""
        workbook = openpyxl.Workbook()
        workbook.remove(workbook.active)
        for title, header, lines in sheets:
            sheet = workbook.create_sheet(title[:31])
            sheet.append(header)
            for line in lines:
                sheet.append(line)
            for cell in sheet[1]:
                cell.font = Font(bold=True)
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for index, label in enumerate(header, 1):
                longest = max([len(str(label))] + [len(str(line[index - 1] if line[index - 1] is not None else ""))
                                                   for line in lines if index <= len(line)])
                sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 60)
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    def action_export_excel(self):
        """Button « Export to a spreadsheet »: the volunteers of the screen (same filter, same order) in an .xlsx file with
        three flat sheets ready for pivot tables, downloaded directly (v1.128.0: no ZIP archive any more, on request).

        The file contains names and e-mail addresses: every export is written in the access history of the reports."""
        self.ensure_one()
        guard = self._rlq_pi_guard("action_export_excel")                # v1.136.0: names and e-mail addresses in the file
        if guard:
            return guard
        if openpyxl is None:
            raise UserError(_("The spreadsheet export needs the Python library « openpyxl », which is not installed on this server "
                              "(pip install openpyxl)."))
        rows, groups, extra_labels, _notes = self._rlq_table_data()
        if not rows:
            raise UserError(_("No volunteer to export for this event."))
        lang = self.env.lang or rd.DEFAULT_LANG
        content = self._rlq_workbook(rd.volunteer_export_sheets(rows, groups, lang, extra_columns=extra_labels))
        zone = local_zone(self.env, self.event_id)
        stamp = fields.Datetime.context_timestamp(self.with_context(tz=zone), fields.Datetime.now()).strftime("%Y%m%d.%H%M%S")
        name = "Benevoles-%s-%s.xlsx" % (rb.slug(self.event_id.name)[:60], stamp)
        attachment = self.env["ir.attachment"].create({
            "name": name, "type": "binary", "datas": base64.b64encode(content), "res_model": self._name, "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        try:                                                    # traceability, like the survey reports; never blocks the export
            self.env["rlq.survey.report.acces"].sudo().create({
                "user_id": self.env.user.id, "action": "excel", "nom_fichier": name, "attachment_id": attachment.id,
                "fichier_telecharger": attachment.sudo().datas, "anonymise": False, "nb_sondages": 0,
                "resume_sondages": (_("Volunteers: %(event)s", event=self.event_id.name) or "")[:250],
            })
        except Exception:  # noqa: BLE001
            _logger.warning("rlq_survey_report: access log entry not written for %s", name, exc_info=True)
        _logger.info("rlq_survey_report: volunteers spreadsheet %s exported by user %s (%d volunteers)", name, self.env.uid, len(rows))
        return {"type": "ir.actions.act_url", "url": "/web/content/%d?download=true&filename=%s" % (attachment.id, name),
                "target": "self"}
