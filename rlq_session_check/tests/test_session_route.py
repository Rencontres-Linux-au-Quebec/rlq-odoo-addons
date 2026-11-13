# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (HttpCase) of /rlq/session/check.

NOT RUN while writing (no Odoo instance). On a DISPOSABLE database, never production:
    odoo-bin -d TEST_DB -i rlq_session_check --test-enable --test-tags rlq_session_check --stop-after-init
"""
from odoo.tests import HttpCase, new_test_user, tagged

URL = "/rlq/session/check"


@tagged("post_install", "-at_install")
class TestSessionRoute(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = new_test_user(cls.env, login="rlq_check_internal", groups="base.group_user", password="rlq-check-internal-42")
        cls.portal = new_test_user(cls.env, login="rlq_check_portal", groups="base.group_portal", password="rlq-check-portal-42")

    def check(self, query=""):
        return self.url_open(URL + query, allow_redirects=False)

    def test_not_signed_in(self):
        response = self.check()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.text, "")
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertEqual(self.check("?group=base.group_user").status_code, 401)

    def test_signed_in_without_group(self):
        self.authenticate("rlq_check_portal", "rlq-check-portal-42")
        self.assertEqual(self.check().status_code, 204)

    def test_group(self):
        self.authenticate("rlq_check_internal", "rlq-check-internal-42")
        self.assertEqual(self.check("?group=base.group_user").status_code, 204)
        self.authenticate("rlq_check_portal", "rlq-check-portal-42")
        self.assertEqual(self.check("?group=base.group_user").status_code, 403)

    def test_unknown_or_invalid_group_refused(self):
        self.authenticate("rlq_check_internal", "rlq-check-internal-42")
        self.assertEqual(self.check("?group=base.no_such_group").status_code, 403)
        self.assertEqual(self.check("?group=base.model_res_partner").status_code, 403)    # an XML id, but not a group
        self.assertEqual(self.check("?group=not-an-xml-id").status_code, 403)

    def test_post_refused(self):
        response = self.url_open(URL, data={"x": "1"}, allow_redirects=False)
        self.assertNotIn(response.status_code, (200, 204))
