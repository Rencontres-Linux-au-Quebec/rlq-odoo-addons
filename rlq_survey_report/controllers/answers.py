# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
answers.py - « see the answers of this person » link of the registration desk and of the volunteers (v1.135.0, v1.139.0)
=========================================================================================================================

/rlq_survey_report/answers/<survey.user_input id>, for the internal users of the Events application only.

v1.139.0: the page is made here (registration_desk_report.answers_page_html) instead of redirecting to the page « print »
of Odoo, which did not show WHO answered: the name of the person is now in the title of the browser tab and at the top, with
the survey, its state, the date of submission (local time) and every question with its answers, page by page. A link opens the
printable version of Odoo too. Test participations are refused. Every opening is logged.
"""
import logging

from odoo import fields, http
from odoo.http import request

from ..models import registration_desk_report as rd
from ..models.event_registration_desk import local_zone

_logger = logging.getLogger(__name__)

PRINT_URL = "/survey/print/%s?answer_token=%s"


class RlqSurveyReportAnswers(http.Controller):

    @http.route("/rlq_survey_report/answers/<int:user_input_id>", type="http", auth="user", methods=["GET"])
    def answers(self, user_input_id, **kwargs):
        if not request.env.user.has_group("event.group_event_user"):
            return request.not_found()
        user_input = request.env["survey.user_input"].sudo().browse(user_input_id).exists()
        if not user_input or user_input.test_entry or not user_input.access_token or not user_input.survey_id.access_token:
            return request.not_found()
        _logger.info("rlq_survey_report: answers of survey.user_input %s shown to user %s", user_input.id, request.env.uid)
        lang = request.env.lang or rd.DEFAULT_LANG
        name = user_input.partner_id.name or getattr(user_input, "nickname", "") or user_input.email or ""
        submitted = ""
        if user_input.state == "done" and user_input.end_datetime:
            zone = local_zone(request.env)
            moment = fields.Datetime.context_timestamp(user_input.with_context(tz=zone), user_input.end_datetime)
            submitted = rd.local_stamp(moment, "%Y-%m-%d %H:%M", lang)
        html = rd.answers_page_html(name, user_input.survey_id.title or "", user_input.state, submitted,
                                    self._sections(user_input), PRINT_URL % (user_input.survey_id.access_token,
                                                                             user_input.access_token), lang)
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"),
                                                    ("Cache-Control", "no-store"), ("X-Robots-Tag", "noindex")])

    @staticmethod
    def _sections(user_input):
        """The questions of the survey, page by page, with the answers of this participation (same texts as the desk)."""
        questions = request.env["survey.question"].sudo().search([("survey_id", "=", user_input.survey_id.id)],
                                                                 order="sequence, id")
        lines = request.env["survey.user_input.line"].sudo()
        wanted = ["question_id", "skipped", "answer_type", "suggested_answer_id", "matrix_row_id", "value_char_box",
                  "value_text_box", "value_numerical_box", "value_scale", "value_date", "value_datetime"]
        rows = lines.search_read([("user_input_id", "=", user_input.id)], [n for n in wanted if n in lines._fields], order="id")
        answer_ids = {(row.get(name) or [False])[0] for row in rows for name in ("suggested_answer_id", "matrix_row_id")}
        answer_values = {answer.id: answer.value or "" for answer in
                         request.env["survey.question.answer"].sudo().browse(sorted(a for a in answer_ids if a)).exists()}
        registrations = request.env["event.registration"].sudo()
        values = {}
        for row in rows:
            if row.get("skipped") or not row.get("question_id"):
                continue
            text = registrations._rlq_desk_value(row, answer_values)
            if text:
                values.setdefault(row["question_id"][0], []).append(text)
        sections, current = [], {"title": "", "questions": []}
        for question in questions:
            if getattr(question, "is_page", False):
                if current["questions"] or current["title"]:
                    sections.append(current)
                current = {"title": question.title or "", "questions": []}
                continue
            current["questions"].append({"title": question.title or "", "values": values.get(question.id, [])})
        if current["questions"] or current["title"]:
            sections.append(current)
        return sections
