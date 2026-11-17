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
      * people marked present per hour (LOCAL time, see local_zone()), per ticket and in total;
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

Sorting (v1.123.0):
  - the list of the desk is sorted by the wizard (« Sort by », « Descending »): Python, case and accents ignored, every column;
  - the full list (« Open as a list ») is sorted by clicking a column header. The action carries the context key
    `rlq_desk_event_id`; with it, _order_field_to_sql() orders the text columns and the computed columns (survey, questions
    answered, answers) by the position of the record in a list of ids sorted in Python with the same keys. Without the key,
    nothing changes for the other screens of Odoo;
  - events are listed most recent first in the selectors of this module (context key `rlq_recent_first`, search_fetch()).
"""
import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

from . import registration_desk_report as rd
from .registration_desk_report import sort_key

_logger = logging.getLogger(__name__)

STATE_RANK = {"done": 2, "in_progress": 1}
LIST_STATES = ("draft", "open", "done")
PROGRAM = "rlq_survey_report"
COMPUTED_SORTS = ("rlq_survey_state", "rlq_desk_progress", "rlq_desk_answers", "rlq_desk_person", "rlq_survey_done_date",
                  "rlq_desk_answers_html")
MAP_SORTS = ("rlq_survey_state", "rlq_desk_progress", "rlq_desk_answers", "rlq_desk_answers_html")   # sorts that need _rlq_desk_map()
SURVEY_MANAGER_GROUP = "survey.group_survey_manager"                             # may change the answers (survey_answer_edit.py)
TEXT_OPERATORS = ("ilike", "not ilike", "=", "!=")
CHAT_URL = "/rlq_survey_report/chat/%d"
GUIDE_URL = "/rlq_survey_report/aide#%s"
ANSWERS_URL = "/rlq_survey_report/answers/%d"                                    # controllers/reponses.py: the answers of a person                                         # controllers/aide.py, section of the guide                                          # controllers/: opens Discuss with the contact
STATE_ORDER = {"draft": 0, "open": 1, "done": 2, "cancel": 3}
RECENT_EVENTS_FIRST = "date_begin desc, id desc"
DEFAULT_ZONE = "America/Toronto"


def program_version(env):
    """« 18.0.1.123.0 »: the installed version of this module (read from Odoo, never a hard-coded string)."""
    module = env["ir.module.module"].sudo().search([("name", "=", PROGRAM)], limit=1)
    return module.installed_version or module.latest_version or "?"


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


def local_zone(env, event=None):
    """Name of the LOCAL time zone used by the desk and the volunteers' table (v1.124.0): the time zone of the user (the one of
    the browser, sent by the web client in the context, otherwise the one of the user's preferences), otherwise the time zone
    of the event, otherwise America/Toronto. Never UTC by default: the database stores UTC, people read local time."""
    return env.context.get("tz") or env.user.tz or (event.date_tz if event else False) or DEFAULT_ZONE


def local_time(registration, value, pattern):
    """Formats a UTC datetime of the database in local time (see local_zone()); « » when empty."""
    if not value:
        return ""
    zone = local_zone(registration.env, registration.event_id)
    return fields.Datetime.context_timestamp(registration.with_context(tz=zone), value).strftime(pattern)


def guide_action(env, anchor):
    """Opens the user guide (controllers/aide.py) in a new tab, at the section `anchor` (v1.134.0)."""
    return {"type": "ir.actions.act_url", "url": GUIDE_URL % anchor, "target": "new", "name": _("User guide")}


def contact_action(env, registrations):
    """v1.135.0: the e-mail window of Odoo, one e-mail per registration that has an address (mass mailing on
    event.registration: each person receives their own e-mail, the addresses are never shown to the others)."""
    with_email = registrations.filtered(lambda r: (r.email or "").strip())
    if not with_email:
        raise UserError(_("No participant of this list has an e-mail address."))
    return {
        "type": "ir.actions.act_window", "name": _("Contact the participants"), "res_model": "mail.compose.message",
        "view_mode": "form", "target": "new",
        "context": {"default_model": "event.registration", "default_res_ids": with_email.ids,
                    "default_composition_mode": "mass_mail", "active_model": "event.registration", "active_ids": with_email.ids},
    }


def registration_list_action(env, name, domain, event_id):
    """« Open as a list »: the registrations in the full list of the desk (search, filters, grouping, export, same buttons)."""
    return {
        "type": "ir.actions.act_window", "name": name, "res_model": "event.registration", "view_mode": "list,form",
        "views": [(env.ref("rlq_survey_report.view_rlq_registration_desk_registration_list").id, "list"), (False, "form")],
        "search_view_id": [env.ref("rlq_survey_report.view_rlq_registration_desk_registration_search").id, "search"],
        "domain": domain, "context": {"create": False, "rlq_desk_event_id": event_id},
    }


def program_stamp(env, event=None):
    """Footer of the screens: program name, installed version, local date and time of the display, with the time zone."""
    zone = local_zone(env, event)
    now = fields.Datetime.context_timestamp(env["res.users"].with_context(tz=zone), fields.Datetime.now())
    lang = env.lang or rd.DEFAULT_LANG
    return rd.program_footer(PROGRAM, program_version(env), rd.local_stamp(now, "%Y-%m-%d %H:%M:%S", lang), zone, lang)


class EventRegistrationDesk(models.Model):
    _inherit = "event.registration"

    rlq_present_by = fields.Many2one(
        "res.users", string="Marked present by", copy=False, readonly=True, ondelete="set null",
        help="User who marked this person present (button « Present » of the RLQ registration desk, or the registration "
             "desk of Odoo). Cleared when the presence is undone.",
    )
    rlq_departure = fields.Datetime(
        string="Left at", copy=False, readonly=True,
        help="Time when the person left the event, recorded with the « Left » button of the RLQ registration desk.",
    )
    rlq_desk_progress = fields.Char(
        string="Questions answered", compute="_compute_rlq_desk",
        help="Questions answered / questions of the survey expected for this registration (pages excluded). Empty: no survey.",
    )
    rlq_desk_answers = fields.Char(
        string="Answers (text)", compute="_compute_rlq_desk", search="_search_rlq_desk_answers",
        help="Answers of this person to the survey questions checked « Show at the registration desk ».",
    )
    rlq_desk_answers_html = fields.Html(
        string="Answers", compute="_compute_rlq_desk", sanitize=False,
        help="Answers of this person to the survey questions checked « Show at the registration desk ». Click them to see "
             "every answer of the survey filled in by this person.",
    )
    # An Integer, not a Many2one: a volunteer of the Events application without the rights of the Surveys application must
    # be able to read the list (a Many2one would read the name of the participation, refused by the access rights).
    rlq_desk_user_input_id = fields.Integer(
        string="Participation", compute="_compute_rlq_desk",
        help="The participation of this person to the expected survey (the most advanced one, the most recent among equals).",
    )
    rlq_desk_can_edit_answers = fields.Boolean(string="Can edit the answers", compute="_compute_rlq_desk")
    rlq_desk_person = fields.Html(
        string="Participant name", compute="_compute_rlq_desk_person", sanitize=False,
        help="Name of the participant. Click it to send a message to this person in Odoo (Discuss). Sorting by this column "
             "ignores case and accents.",
    )

    @api.depends("name", "partner_id")
    def _compute_rlq_desk_person(self):
        """v1.131.0: the name, a link to talk to the contact in Odoo (same link as the volunteers' table)."""
        for registration in self:
            partner = registration.partner_id
            registration.rlq_desk_person = rd.person_cell_html(
                registration.name or partner.name or "", CHAT_URL % partner.id if partner else None)

    def _compute_rlq_desk(self):
        data = self._origin._rlq_desk_map()                     # v1.133.0: _origin, see _compute_rlq_survey_state()
        can_edit = self.env.user.has_group(SURVEY_MANAGER_GROUP)
        for registration in self:
            item = data.get(registration._origin.id) or {}
            text = rd.answers_text(item.get("answers"))
            registration.rlq_desk_progress = rd.progress_text(item.get("questions"), item.get("answered")) or False
            registration.rlq_desk_answers = text or False
            input_id = item.get("input")
            registration.rlq_desk_user_input_id = input_id or 0
            # v1.135.0: the answers are a link to the survey filled in by the person (see action_rlq_desk_view_answers).
            registration.rlq_desk_answers_html = rd.answers_cell_html(text, ANSWERS_URL % input_id if input_id else None)
            registration.rlq_desk_can_edit_answers = bool(can_edit and input_id)

    @api.model
    def _search_rlq_desk_answers(self, operator, value):
        """v1.135.0: « Answers » usable in the search bar of « Open as a list » (« contains Végé » finds « Végétarien »): the
        text is computed, so the matching registrations (of the event of the desk when the context names one) are found in
        Python, case and accents ignored."""
        if operator not in TEXT_OPERATORS:
            raise ValueError("rlq_desk_answers: unsupported search operator %r" % (operator,))
        domain = [("state", "!=", "cancel")]
        if self.env.context.get("rlq_desk_event_id"):
            domain.append(("event_id", "=", self.env.context["rlq_desk_event_id"]))
        registrations = self.sudo().with_context(rlq_desk_event_id=False).search(domain)
        data = registrations._rlq_desk_map()
        needle = sort_key(" ".join(str(value or "").split()))
        ids = []
        for registration in registrations:
            text = sort_key(rd.answers_text((data.get(registration.id) or {}).get("answers")))
            found = needle in text if operator in ("ilike", "not ilike") else needle == text
            if found:
                ids.append(registration.id)
        return [("id", "in" if operator in ("ilike", "=") else "not in", ids)]

    def action_rlq_desk_view_answers(self):
        """v1.135.0: button « See the answers »: every answer of the survey filled in by this person, in a new tab (the page
        « print » of Odoo), without going through the Surveys application."""
        self.ensure_one()
        user_input = self._rlq_desk_user_input()
        if not user_input:
            raise UserError(_("This person has not answered the survey yet."))
        return {"type": "ir.actions.act_url", "url": ANSWERS_URL % user_input.id, "target": "new"}

    def action_rlq_desk_edit_answers(self):
        """v1.135.0: button « Edit the answers » (survey administrators only): the window of survey_answer_edit.py."""
        self.ensure_one()
        user_input = self._rlq_desk_user_input()
        if not user_input:
            raise UserError(_("This person has not answered the survey yet."))
        return user_input.action_rlq_edit_answers()

    def _rlq_desk_user_input(self):
        input_id = (self._origin._rlq_desk_map().get(self._origin.id) or {}).get("input")
        return self.env["survey.user_input"].browse(input_id) if input_id else self.env["survey.user_input"]
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

    def _rlq_desk_participations(self, status):
        """The survey answers of the registrations. status: the result of _rlq_survey_status_map().

        Returns (inputs, answered, values, chosen):
          chosen   {registration id: survey.user_input id}: the most advanced participation (completed, then started) of the same
                   contact or e-mail address for the expected survey, the most recent one among equals;
          inputs   the set of those participation ids;
          answered {participation id: {question ids answered}} (skipped questions left out);
          values   {(participation id, question id): [texts]}.
        """
        registrations = self.sudo().filtered("id")
        survey_ids = sorted({survey.id for survey, _state, _done in status.values() if survey})
        by_partner, by_email = defaultdict(list), defaultdict(list)
        if survey_ids:
            for row in self.env["survey.user_input"].sudo().search_read(
                    [("survey_id", "in", survey_ids), ("test_entry", "=", False)], ["survey_id", "partner_id", "email", "state"]):
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

        lines = self.env["survey.user_input.line"].sudo()
        wanted = ["user_input_id", "question_id", "skipped", "answer_type", "suggested_answer_id", "matrix_row_id",
                  "value_char_box", "value_text_box", "value_numerical_box", "value_scale", "value_date", "value_datetime"]
        read = [name for name in wanted if name in lines._fields]
        inputs = set(chosen.values())
        rows = lines.search_read([("user_input_id", "in", sorted(inputs))], read, order="id") if inputs else []
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
        return inputs, answered, values, chosen

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
                result[registration.id] = {"survey": False, "state": "none", "questions": 0, "answered": 0, "answers": [],
                                           "input": False}
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

        _inputs, answered, values, chosen = registrations._rlq_desk_participations(status)

        for registration in registrations:
            survey, state, _done = status[registration.id]
            if not survey:
                result[registration.id] = {"survey": False, "state": "none", "questions": 0, "answered": 0, "answers": [],
                                           "input": False}
                continue
            input_id = chosen.get(registration.id)
            result[registration.id] = {
                "survey": survey, "state": state, "questions": question_count.get(survey.id, 0),
                "answered": len(answered.get(input_id, ())), "input": input_id or False,
                "answers": [(label, values.get((input_id, question_id), [])) for question_id, label in desk_questions.get(survey.id, [])],
            }
        return result

    def _rlq_desk_rows(self):
        """Rows of registration_desk_report (one per registration); every date and hour is in LOCAL time (local_zone()), never UTC."""
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

    def _rlq_desk_sort_keys(self, field_name):
        """{registration id: sort key} for one column of the desk. Texts: case and accents ignored, empty values last."""
        data = self._rlq_desk_map() if field_name in MAP_SORTS else {}
        keys = {}
        for registration in self.sudo().filtered("id"):
            item = data.get(registration.id) or {}
            if field_name == "rlq_survey_state":
                key = (rd.SURVEY_RANK.get(item.get("state", "none"), 9),)
            elif field_name == "rlq_desk_progress":
                key = (not item.get("questions"), item.get("answered", 0), item.get("questions", 0))
            elif field_name in ("rlq_desk_answers", "rlq_desk_answers_html"):
                text = rd.answers_text(item.get("answers"))
                key = (not text, sort_key(text))
            elif field_name == "rlq_desk_person":
                name = registration.name or registration.partner_id.name or ""
                key = (not name, sort_key(name))
            elif field_name == "state":
                key = (STATE_ORDER.get(registration.state, 9),)
            else:
                field = registration._fields.get(field_name)
                value = registration[field_name] if field else False
                if field is not None and field.type == "many2one":
                    value = value.display_name if value else ""
                if field is not None and field.type in ("datetime", "date", "integer", "float"):
                    key = (not value, value or 0)
                else:
                    key = (not value, sort_key(value))
            keys[registration.id] = key
        return keys

    def _rlq_desk_sorted(self, field_name, descending=False):
        """The recordset sorted by one column of the desk; equal values keep the order ticket, name (stable sort)."""
        has_ticket = "event_ticket_id" in self._fields
        base = self.sorted(lambda r: (sort_key(r.event_ticket_id.name if has_ticket else ""), sort_key(r.name), r.id))
        if field_name == "name":
            field_name = "rlq_desk_person"                                     # same order, the name of the contact as fallback
        if not field_name or field_name == "event_ticket_id":
            return base.sorted(lambda r: sort_key(r.event_ticket_id.name if has_ticket else ""), reverse=bool(descending))
        keys = base._rlq_desk_sort_keys(field_name)
        return base.sorted(lambda r: keys.get(r.id, (True,)), reverse=bool(descending))

    @api.model
    def _rlq_desk_sorted_ids(self, event_id, field_name):
        """Ids of the registrations of one event, in ascending order of one column (see _order_field_to_sql)."""
        registrations = self.sudo().with_context(rlq_desk_event_id=False).search([("event_id", "=", event_id)], order="id")
        return registrations._rlq_desk_sorted(field_name).ids

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        """In the full list of the RLQ registration desk only (context key `rlq_desk_event_id`): the text columns are sorted
        without case or accents, and the computed columns (survey, questions answered, answers) become sortable.

        PostgreSQL cannot do it alone: the database of Odoo sorts « É » after « z », and a computed column is not in the table.
        The order is computed in Python for the registrations of the event, and PostgreSQL sorts by the position of each id.
        Everything else (other screens, dates, many2one columns, grouped queries) goes to the standard code.
        """
        event_id = self.env.context.get("rlq_desk_event_id")
        field = self._fields.get(field_name)
        if event_id and field is not None:
            computed = field_name in COMPUTED_SORTS
            if computed and query.groupby:
                return SQL()                                                    # a computed column cannot order groups
            if not query.groupby and (computed or (field.store and field.type in ("char", "text"))):
                ids = self._rlq_desk_sorted_ids(event_id, field_name)
                return SQL("array_position(%s::integer[], %s) %s %s", ids, SQL.identifier(alias, "id"), direction, nulls)
        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    @api.model_create_multi
    def create(self, vals_list):
        """A registration created already present (« done ») records who created it as the person who marked it present."""
        for vals in vals_list:
            if vals.get("state") == "done" and not vals.get("rlq_present_by"):
                vals["rlq_present_by"] = self.env.user.id
        return super().create(vals_list)

    def write(self, vals):
        """v1.128.0: whatever the screen (RLQ desk, desk of Odoo, form), passing to « done » records who did it, and leaving
        « done » clears it. Done here rather than in the button, so that every way of marking present is covered.

        v1.133.0: the hour of arrival (date_closed) follows the presence the same way. Odoo computes date_closed from the state
        but never clears it, and only sets it when it is empty: after « Undo », the old hour stayed on screen, and marking the
        person present again kept the FIRST hour. Now: passing to « done » records the current hour, leaving « done » clears the
        hour of arrival and the hour of departure. A value given in vals is always kept."""
        if "state" not in vals:
            return super().write(vals)
        has_closed = "date_closed" in self._fields
        if vals["state"] == "done":
            to_mark = self.filtered(lambda r: r.state != "done")
            others = self - to_mark
            mark = dict(vals)
            mark.setdefault("rlq_present_by", self.env.user.id)
            if has_closed:
                mark.setdefault("date_closed", fields.Datetime.now())
            result = super(EventRegistrationDesk, to_mark).write(mark) if to_mark else True
            if others:
                result = super(EventRegistrationDesk, others).write(vals) and result
            return result
        leaving = self.filtered(lambda r: r.state == "done")
        vals = dict(vals)
        vals.setdefault("rlq_present_by", False)
        result = super().write(vals)
        clear = {}
        if has_closed and "date_closed" not in vals:
            clear["date_closed"] = False
        if "rlq_departure" not in vals:
            clear["rlq_departure"] = False
        if leaving and clear:
            # Written AFTER the state, so that no recomputation of date_closed triggered by the state can bring the hour back.
            result = super(EventRegistrationDesk, leaving).write(clear) and result
        return result

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
        """Button « Undo »: a registration marked present by mistake goes back to « open »; the hours of arrival and departure
        are cleared by write() (v1.133.0)."""
        registrations = self.filtered(lambda r: r.state == "done")
        if registrations:
            registrations.write({"state": "open"})
            _logger.info("registration desk: presence of %d registration(s) undone by user %s", len(registrations), self.env.uid)
        return True


class EventEventRegistrationDesk(models.Model):
    _inherit = "event.event"

    @api.model
    @api.readonly
    @api.returns("self")
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        """Selectors of this module (context key `rlq_recent_first`): the most recent event first, instead of the oldest.

        Only when the caller gives no order: the drop-down list of a many2one (name_search) and its « Search more » window.
        """
        if not order and self.env.context.get("rlq_recent_first"):
            order = RECENT_EVENTS_FIRST
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

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
                              help="Part of a name, an e-mail address, a company, a phone number, a ticket or an answer: only "
                                   "the matching registrations are listed (case and accents ignored). The summary always counts "
                                   "the whole event.")
    hide_present = fields.Boolean(string="Hide the people already present", default=False)
    survey_filter = fields.Selection(
        [("all", "All"), ("done", "Survey completed"), ("in_progress", "Survey started"),
         ("not_started", "Survey not started"), ("none", "No survey")],
        string="Survey", default="all", required=True, help="Lists only the registrations whose survey is in this state.")
    sort_by = fields.Selection(
        [("event_ticket_id", "Ticket"), ("name", "Name"), ("create_date", "Registration date"), ("state", "Status"),
         ("date_closed", "Arrival"), ("rlq_departure", "Departure"), ("rlq_survey_state", "Survey"),
         ("rlq_desk_progress", "Questions answered"), ("rlq_desk_answers", "Answers"),
         ("rlq_survey_done_date", "Survey submitted on")],
        string="Sort by", default="name", required=True,                       # v1.134.0: by name by default
        help="Order of the list below. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by "
             "ticket, then by name.")
    sort_desc = fields.Boolean(string="Descending", default=False, help="Reverses the order of the list.")
    event_date_text = fields.Char(string="Date of the event", compute="_compute_event_date_text",
                                  help="Local date and time of the event (start, and end when it is another day).")
    summary_html = fields.Html(string="Summary", compute="_compute_desk", sanitize=False)
    registration_ids = fields.Many2many("event.registration", string="Registrations", compute="_compute_desk")
    registration_count = fields.Integer(string="Registrations listed", compute="_compute_desk")

    @api.depends("event_id")
    def _compute_event_date_text(self):
        """v1.131.0: « 2026-11-21 09:00 - 16:00 HNE » in local time, next to the event and in the title of the desk."""
        lang = self.env.lang or rd.DEFAULT_LANG
        for wizard in self:
            event = wizard.event_id
            if not event or not event.date_begin:
                wizard.event_date_text = False
                continue
            zone = local_zone(self.env, event)
            begin = fields.Datetime.context_timestamp(event.with_context(tz=zone), event.date_begin)
            end = fields.Datetime.context_timestamp(event.with_context(tz=zone), event.date_end) if event.date_end else None
            if end and end.date() == begin.date():
                text = "%s - %s" % (begin.strftime("%Y-%m-%d %H:%M"), rd.local_stamp(end, "%H:%M", lang))
            elif end:
                text = "%s - %s" % (begin.strftime("%Y-%m-%d %H:%M"), rd.local_stamp(end, "%Y-%m-%d %H:%M", lang))
            else:
                text = rd.local_stamp(begin, "%Y-%m-%d %H:%M", lang)
            wizard.event_date_text = text

    @api.depends("event_id")
    def _compute_display_name(self):
        for wizard in self:
            if wizard.event_id:
                name = _("Registration desk: %(event)s", event=wizard.event_id.name)
                if wizard.event_date_text:
                    name = "%s (%s)" % (name, wizard.event_date_text)
                wizard.display_name = name
            else:
                wizard.display_name = _("RLQ registration desk")

    def _rlq_all_registrations(self):
        self.ensure_one()
        if not self.event_id:
            return self.env["event.registration"]
        return self.env["event.registration"].search([("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))])

    @staticmethod
    def _rlq_haystack(registration, answers=""):
        """v1.135.0: the search of the desk also looks in the phone number, the ticket and the answers."""
        parts = [registration.name, registration.email, answers]
        for name in ("company_name", "phone", "mobile"):
            if name in registration._fields:
                parts.append(registration[name])
        if "event_ticket_id" in registration._fields:
            parts.append(registration.event_ticket_id.name)
        return " ".join(" ".join(str(p or "").lower().split()) for p in parts)

    def _rlq_listed(self, registrations):
        """The registrations of the list: filters « hide present », « survey » and « search », sorted by the chosen column."""
        self.ensure_one()
        listed = registrations
        if self.hide_present:
            listed = listed.filtered(lambda r: r.state != "done")
        if self.survey_filter and self.survey_filter != "all":
            status = listed._rlq_survey_status_map()
            listed = listed.filtered(lambda r: status.get(r.id, (None, "none"))[1] == self.survey_filter)
        needle = sort_key(" ".join((self.search_text or "").split()))
        if needle:
            data = listed._rlq_desk_map()
            listed = listed.filtered(lambda r: needle in sort_key(self._rlq_haystack(
                r, rd.answers_text((data.get(r.id) or {}).get("answers")))))
        return listed._rlq_desk_sorted(self.sort_by or "event_ticket_id", self.sort_desc)

    @api.depends("event_id", "search_text", "hide_present", "survey_filter", "sort_by", "sort_desc")
    def _compute_desk(self):
        for wizard in self:
            registrations = wizard._rlq_all_registrations()
            # v1.126.0: the program name, version, local date and time come FIRST, above the summary.
            lang = self.env.lang or rd.DEFAULT_LANG
            wizard.summary_html = (program_stamp(self.env, wizard.event_id)
                                   + rd.desk_summary_html(registrations._rlq_desk_rows(), lang)
                                   + rd.reconciliation_html(wizard._rlq_reconciliation_items(), lang))
            listed = wizard._rlq_listed(registrations)
            wizard.registration_ids = listed
            wizard.registration_count = len(listed)

    def _rlq_reconciliation_items(self):
        """v1.131.0: per survey of the event, the numbers that explain why « completed » differs between the survey (it counts
        participations) and the event (it counts registrations). See registration_desk_report.reconciliation_html()."""
        self.ensure_one()
        if not self.event_id:
            return []
        every = self.env["event.registration"].sudo().search([("event_id", "=", self.event_id.id)])
        status = every._rlq_survey_status_map()
        items = []
        for survey in sorted({s for s, _st, _d in status.values() if s}, key=lambda s: sort_key(s.title)):
            active = every.filtered(lambda r, survey=survey: status[r.id][0] == survey and r.state in LIST_STATES)
            cancelled = every.filtered(lambda r, survey=survey: status[r.id][0] == survey and r.state not in LIST_STATES)

            def keys(registrations):
                partners = set(registrations.partner_id.ids)
                emails = {(r.email or "").strip().lower() for r in registrations if r.email}
                return partners, emails

            active_keys, cancelled_keys = keys(active), keys(cancelled)

            def matches(row, found):
                partners, emails = found
                return bool((row["partner_id"] and row["partner_id"][0] in partners)
                            or (row["email"] and row["email"].strip().lower() in emails))

            rows = self.env["survey.user_input"].sudo().search_read(
                [("survey_id", "=", survey.id)], ["partner_id", "email", "state", "test_entry"])
            done = [row for row in rows if row["state"] == "done" and not row["test_entry"]]
            matched = [row for row in done if matches(row, active_keys)]
            cancelled_done = [row for row in done if row not in matched and matches(row, cancelled_keys)]
            matched_done = sum(1 for r in active if status[r.id][1] == "done")
            items.append({
                "survey": survey.title, "survey_done": len(done), "matched_done": matched_done,
                "duplicates": max(len(matched) - matched_done, 0), "cancelled_done": len(cancelled_done),
                "unmatched_done": len(done) - len(matched) - len(cancelled_done),
                "tests": sum(1 for row in rows if row["test_entry"]),
            })
        return items

    def action_refresh(self):
        """Button « Refresh »: the form is read again, so the summary and the list are computed again."""
        return True

    def action_open_guide(self):
        """v1.134.0: button « Help for this page »: the user guide, opened at the section of the registration desk."""
        return guide_action(self.env, "bureau-inscription")

    def action_contact(self):
        """v1.135.0: button « Contact the participants »: an e-mail to the registrations LISTED (same filters and search)."""
        self.ensure_one()
        return contact_action(self.env, self._rlq_listed(self._rlq_all_registrations()))

    def action_open_list(self):
        """The registrations of the event in a full list (native search, filters, grouping by ticket, export), same buttons."""
        self.ensure_one()
        return registration_list_action(self.env, _("Registration desk: %(event)s", event=self.event_id.name),
                                        [("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))], self.event_id.id)
