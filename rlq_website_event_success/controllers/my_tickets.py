# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Ticket page of an event (/event/<id>/my_tickets) that answers 404 instead of 500 when its parameters are missing.

Odoo 18 (event, EventController.event_my_tickets): `registration_ids` and `tickets_hash` have no default value, so a
request without them never reaches the code that would answer 404: Odoo raises TypeError -> error 500. A malformed
`registration_ids` ("abc") also ends in a 500 (json.loads fails).
Seen on 2026-11-19: the link scanner of an e-mail provider opened the link of the reminder e-mail, then replayed it with
a scrambled parameter name and an empty value (`?eftvfgebgvba_vef=`) -> 1 error 500 and a traceback in the Odoo log.

Here: missing or unusable parameters -> 404 (what Odoo itself answers for an invalid hash); valid parameters -> Odoo's
code, unchanged (hash check, PDF or responsive HTML).
"""
import json
import logging

from werkzeug.exceptions import NotFound

from odoo.http import request, route

from odoo.addons.event.controllers.main import EventController

from ..lib.registration_ids import parse_registration_ids

_logger = logging.getLogger(__name__)


class RlqEventController(EventController):

    @route()
    def event_my_tickets(self, event_id, registration_ids=None, tickets_hash=None, badge_mode=False,
                         responsive_html=False, **kwargs):
        ids = parse_registration_ids(registration_ids)
        if not ids or not tickets_hash or not isinstance(tickets_hash, str):
            _logger.info(
                "rlq_website_event_success: event %s, ticket page opened without usable parameters (%s) -> 404",
                event_id, ", ".join(sorted(request.params))[:200] or "none",
            )
            raise NotFound()
        return super().event_my_tickets(
            event_id, json.dumps(ids), tickets_hash, badge_mode=badge_mode, responsive_html=responsive_html,
        )
