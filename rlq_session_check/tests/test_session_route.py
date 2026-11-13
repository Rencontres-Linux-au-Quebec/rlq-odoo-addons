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


@tagged("post_install", "-at_install")
class TestSessionMe(HttpCase):
    """18.0.1.1.0: /rlq/session/me."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = new_test_user(cls.env, login="rlq_me_internal", name="Marie Tremblay", groups="base.group_user",
                                     password="rlq-me-internal-42")
        cls.internal.partner_id.write({"city": "Québec", "street": "1 rue Principale"})
        cls.portal = new_test_user(cls.env, login="rlq_me_portal", name="Paul Gagnon", groups="base.group_portal", password="rlq-me-portal-42")

    def me(self):
        response = self.url_open("/rlq/session/me", allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        return response.json()

    def test_not_signed_in(self):
        self.assertEqual(self.me(), {"signed_in": False})

    def test_portal_greeting_without_details(self):
        self.authenticate("rlq_me_portal", "rlq-me-portal-42")
        self.assertEqual(self.me(), {"signed_in": True, "first_name": "Paul"})

    def test_internal_details(self):
        self.authenticate("rlq_me_internal", "rlq-me-internal-42")
        data = self.me()
        self.assertEqual(data["first_name"], "Marie")
        self.assertEqual(data["details"]["name"], "Marie Tremblay")
        self.assertIn("1 rue Principale", data["details"]["address"])

    def test_profile_group_parameter(self):
        self.env["ir.config_parameter"].sudo().set_param("rlq_session_check.profile_group", "base.group_system")
        self.authenticate("rlq_me_internal", "rlq-me-internal-42")
        self.assertNotIn("details", self.me())
        self.env["ir.config_parameter"].sudo().set_param("rlq_session_check.profile_group", "not valid")
        self.assertNotIn("details", self.me())
