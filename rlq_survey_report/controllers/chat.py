# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
chat.py - « talk to this person on Odoo » link of the volunteers' table (v1.123.0)
===================================================================================

/rlq_survey_report/chat/<partner id>, for the internal users of the Events application only:
  - the contact has a user account (internal or portal): opens (creating it if needed) the direct chat with that person in the
    Discuss application of Odoo;
  - otherwise (a contact without account cannot receive a chat), or on any error: opens the form of the contact, where the
    chatter (« Send message ») writes to the person by e-mail.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

DISCUSS_URL = "/odoo/action-mail.action_discuss?active_id=%d"
CONTACT_URL = "/mail/view?model=res.partner&res_id=%d"


class RlqSurveyReportChat(http.Controller):

    @http.route("/rlq_survey_report/chat/<int:partner_id>", type="http", auth="user", methods=["GET"])
    def chat(self, partner_id, **kwargs):
        if not request.env.user.has_group("event.group_event_user"):
            return request.not_found()
        partner = request.env["res.partner"].sudo().browse(partner_id).exists()
        if not partner:
            return request.not_found()
        try:
            has_account = bool(partner.user_ids.filtered("active"))
            if has_account and partner != request.env.user.partner_id and "discuss.channel" in request.env:
                channel = request.env["discuss.channel"].channel_get([partner.id])
                return request.redirect(DISCUSS_URL % channel.id)
        except Exception:  # noqa: BLE001 - the contact form is always a valid fallback
            _logger.info("rlq_survey_report: chat with contact %s not opened, contact form instead", partner_id, exc_info=True)
        return request.redirect(CONTACT_URL % partner.id)
