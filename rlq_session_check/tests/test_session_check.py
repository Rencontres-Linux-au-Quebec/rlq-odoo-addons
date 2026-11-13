# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of lib/session_check.py (pure functions, no database).

Run by Odoo with the module tests, or alone, without Odoo:
    python3 rlq_session_check/tests/test_session_check.py -v
"""
import importlib.util
import os
import unittest

try:
    from odoo.tests.common import BaseCase as _Base
except ImportError:
    _Base = unittest.TestCase

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "session_check.py")
_spec = importlib.util.spec_from_file_location("rlq_session_check_lib", _PATH)
session_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session_check)


class TestParseGroup(_Base):

    def test_no_group(self):
        self.assertIsNone(session_check.parse_group(None))
        self.assertIsNone(session_check.parse_group(""))

    def test_valid_xml_ids(self):
        for value in ("base.group_user", "base.group_portal", "rlq_module.group_volunteers_2026"):
            self.assertEqual(session_check.parse_group(value), value)

    def test_refused(self):
        for value in ("group_user", "Base.group_user", "base.group user", "base..x", ".x", "x.", "base.group_user;drop",
                      "../base.group_user", "a" * 65 + ".x", ["base.group_user"]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    session_check.parse_group(value)


class TestStatus(_Base):

    def test_not_signed_in_always_401(self):
        for in_group in (None, True, False):
            self.assertEqual(session_check.status(True, in_group), 401)

    def test_signed_in(self):
        self.assertEqual(session_check.status(False, None), 204)
        self.assertEqual(session_check.status(False, True), 204)
        self.assertEqual(session_check.status(False, False), 403)


if __name__ == "__main__":
    unittest.main()
