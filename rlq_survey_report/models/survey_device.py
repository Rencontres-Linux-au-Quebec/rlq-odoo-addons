# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
survey_device.py - operating system and browser of each survey participation (v1.140.0)
========================================================================================

Some participants could not go further than the first question with Firefox mobile. To understand such a problem, every
participation (survey.user_input) now keeps the User-Agent of the browser that LAST answered it, from the public pages of the
survey only (/survey/...), with the operating system and the browser read from it (registration_desk_report.parse_user_agent):
« Android 14 », « Firefox 145 ». A participation « started » whose last device is always the same browser shows where a
survey blocks. An administrator who edits the answers in the back-office (survey_answer_edit.py) does not replace the device.

Only technical data, no IP address. Shown in the participations of the Surveys application, on the page « See the answers »
and in « Sondages non complétés ».
"""
import logging

from odoo import api, fields, models

from . import registration_desk_report as rd

try:
    from odoo.http import request
except ImportError:  # pragma: no cover
    request = None

_logger = logging.getLogger(__name__)

UA_MAX = 500                                   # a User-Agent is ~150 characters; longer ones are cut


def current_user_agent():
    """The User-Agent of the current request when it comes from a public page of a survey (/survey/...), otherwise None."""
    try:
        if not request or not request.httprequest:
            return None
        if not (request.httprequest.path or "").startswith("/survey/"):
            return None
        return (request.httprequest.headers.get("User-Agent") or "")[:UA_MAX] or None
    except RuntimeError:                       # no request bound (cron, shell, tests)
        return None


def device_vals(user_agent):
    """The values of the three fields for a User-Agent."""
    os_name, browser = rd.parse_user_agent(user_agent)
    return {"rlq_user_agent": user_agent, "rlq_os": os_name or False, "rlq_browser": browser or False}


class SurveyUserInputDevice(models.Model):
    _inherit = "survey.user_input"

    rlq_user_agent = fields.Char(string="User-Agent", readonly=True, copy=False,
                                 help="User-Agent of the browser that last answered this participation (public survey pages).")
    rlq_os = fields.Char(string="Operating system", readonly=True, copy=False,
                         help="Operating system of the device that last answered this participation, read from its User-Agent.")
    rlq_browser = fields.Char(string="Browser", readonly=True, copy=False,
                              help="Browser that last answered this participation, read from its User-Agent.")

    @api.model_create_multi
    def create(self, vals_list):
        user_agent = current_user_agent()
        if user_agent:
            vals_list = [dict(device_vals(user_agent), **vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        user_agent = current_user_agent()
        if user_agent and "rlq_user_agent" not in vals and any(r.rlq_user_agent != user_agent for r in self):
            vals = dict(vals, **device_vals(user_agent))
        return super().write(vals)


class SurveyUserInputLineDevice(models.Model):
    """Each answered page creates answer lines: the participation is updated with the device that sent them."""
    _inherit = "survey.user_input.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        user_agent = current_user_agent()
        if user_agent:
            inputs = lines.mapped("user_input_id").filtered(lambda i: i.rlq_user_agent != user_agent)
            if inputs:
                inputs.sudo().write(device_vals(user_agent))
        return lines
