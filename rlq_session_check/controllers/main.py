# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""/rlq/session/check: tells nginx (auth_request) whether the browser is signed in to Odoo.

Used by nginx-link-page.sh (rlq-admin-tools, LINK_n_ACCESS=odoo or odoo:GROUP): the links reserved to the members are
on a page that nginx serves only when this route answers 204.

- 204: signed in (any user, portal users included), and member of ?group=XMLID when it is given;
- 401: not signed in (nginx then sends to /web/login?redirect=...);
- 403: signed in but not in the group, or group not valid or unknown (refused: never open by mistake).

The answer is empty: no name, no e-mail, nothing about the user. It only says something about the session of the browser
that asks, so it reveals nothing to anyone else. save_session=False: a visitor who is not signed in gets no new session.
"""
import logging

from odoo import http
from odoo.http import request

from ..lib import session_check

_logger = logging.getLogger(__name__)


class RlqSessionCheck(http.Controller):

    @http.route("/rlq/session/check", type="http", auth="public", methods=["GET", "HEAD"], csrf=False, sitemap=False,
                save_session=False)
    def rlq_session_check(self, group=None, **kwargs):
        user = request.env.user
        is_public = user._is_public()
        in_group = None
        try:
            xmlid = session_check.parse_group(group)
        except ValueError:
            _logger.warning("rlq_session_check: group parameter not valid: %r", (group or "")[:100])
            return self._answer(session_check.FORBIDDEN)
        if xmlid and not is_public:
            record = request.env.ref(xmlid, raise_if_not_found=False)
            if record is None or record._name != "res.groups":
                _logger.warning("rlq_session_check: group %s not found (check LINK_n_ACCESS in nginx-link-page)", xmlid)
                return self._answer(session_check.FORBIDDEN)
            in_group = user.has_group(xmlid)
        return self._answer(session_check.status(is_public, in_group))

    def _answer(self, code):
        return request.make_response("", headers=[("Cache-Control", "private, no-store"), ("Vary", "Cookie")], status=code)
