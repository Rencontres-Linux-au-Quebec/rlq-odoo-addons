# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
answers.py - « see the answers of this person » link of the registration desk and of the volunteers (v1.135.0)
================================================================================================================

/rlq_survey_report/answers/<survey.user_input id>, for the internal users of the Events application only: redirects to the
page « print » of the Surveys application (/survey/print/<survey token>?answer_token=<answer token>), which shows every
answer of the survey filled in by the person. A volunteer at the desk thus sees the answers without the rights of the Surveys
application and without going through its menus. Test participations are refused.
"""
import logging

from odoo import http
from odoo.http import request

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
        return request.redirect(PRINT_URL % (user_input.survey_id.access_token, user_input.access_token))
