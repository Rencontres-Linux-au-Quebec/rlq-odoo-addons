# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of lib/registration_ids.py (pure function, no database).

Run by Odoo with the module tests, or alone, without Odoo:
    python3 rlq_website_event_success/tests/test_registration_ids.py -v
"""
import importlib.util
import os
import unittest

try:
    from odoo.tests.common import BaseCase as _Base
except ImportError:
    _Base = unittest.TestCase

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "registration_ids.py")
_spec = importlib.util.spec_from_file_location("rlq_registration_ids", _PATH)
registration_ids = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(registration_ids)
parse = registration_ids.parse_registration_ids


class TestParseRegistrationIds(_Base):

    def test_odoo_format(self):
        self.assertEqual(parse("2073,2074"), [2073, 2074])

    def test_missing(self):
        for value in (None, "", False, []):
            self.assertEqual(parse(value), [])

    def test_garbage_ignored(self):
        self.assertEqual(parse("abc"), [])
        self.assertEqual(parse("12, 13,,x14,"), [12, 13, 14])

    def test_duplicates_and_zero(self):
        self.assertEqual(parse("5,5,0,6"), [5, 6])

    def test_too_large_for_postgresql(self):
        self.assertEqual(parse("99999999999,7"), [7])

    def test_list(self):
        self.assertEqual(parse(["1", "2"]), [1, 2])

    def test_limit(self):
        self.assertEqual(len(parse(",".join(str(i) for i in range(1, 500)))), registration_ids.MAX_IDS)


if __name__ == "__main__":
    unittest.main()
