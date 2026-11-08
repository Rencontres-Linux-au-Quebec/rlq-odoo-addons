# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Confirmation page of an event registration that never ends in an error.

Odoo 18 (website_event, WebsiteEventController.event_registration_success):
- without `?registration_ids=` (page reloaded, link copied without its end) -> TypeError, error 500;
- when the visitor cookie is not recognised (other browser or device, sign-in, in-app browser of a mail or chat app,
  page reopened later) -> 404, although the registration exists and its confirmation e-mail was sent.
Seen on 2026-11-07 for the Journée portes ouvertes sur Linux: 1 error 500, 3 errors 404, and 2 people registered twice.

Here:
- registrations of this visitor found -> Odoo's page, unchanged (tickets shown);
- registrations found for this event but not for this visitor -> Odoo's page with a notice instead of the tickets
  (they are in the confirmation e-mail): no personal data of the registration is shown;
- nothing found -> a page that explains how to check the registration, with a link to register.
"""
import logging

from odoo import http
from odoo.http import request

from odoo.addons.website_event.controllers.main import WebsiteEventController

from ..lib.registration_ids import parse_registration_ids

_logger = logging.getLogger(__name__)


class RlqWebsiteEventController(WebsiteEventController):

    @http.route()
    def event_registration_success(self, event, registration_ids=None, **kwargs):
        ids = parse_registration_ids(registration_ids)
        visitor = request.env["website.visitor"]._get_visitor_from_request()
        registrations_sudo = request.env["event.registration"].sudo()
        if ids:
            registrations_sudo = registrations_sudo.search([("id", "in", ids), ("event_id", "=", event.id)])
        attendees_sudo = registrations_sudo.filtered(lambda reg: visitor and reg.visitor_id == visitor)

        values = self._get_registration_confirm_values(event, attendees_sudo)
        if attendees_sudo:
            return request.render("website_event.registration_complete", values)

        if registrations_sudo:
            _logger.info(
                "rlq_website_event_success: event %s, registrations %s shown without tickets (visitor %s not recognised)",
                event.id, registrations_sudo.ids, visitor.id if visitor else None,
            )
            values["rlq_tickets_in_email"] = True
            return request.render("website_event.registration_complete", values)

        _logger.info(
            "rlq_website_event_success: event %s, confirmation page opened without a known registration (parameter %r)",
            event.id, (registration_ids or "")[:100],
        )
        return request.render("rlq_website_event_success.registration_not_found", values)
