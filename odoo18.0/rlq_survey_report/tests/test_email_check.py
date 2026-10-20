# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Unit tests of models/email_check.py (v1.109.0) — NO DEPENDENCY ON ODOO (pure functions), run by run-all.sh (standalone tests):

    PYTHONPATH=models python3 -m unittest tests.test_email_check -v
"""
import sys
import unittest
from pathlib import Path

try:
    from odoo.addons.rlq_survey_report.models import email_check as ec
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "models"))
    import email_check as ec  # noqa: E402


class TestEmailCheck(unittest.TestCase):
    def test_apostrophe_instead_of_dot_is_invalid_and_corrected(self):
        """The case reported: « marieb.essai@gmail'com »."""
        c = ec.check("marieb.essai@gmail'com")
        self.assertFalse(c["valid"])
        self.assertIn("'", c["reason"])
        self.assertEqual(c["suggestion"], "marieb.essai@gmail.com")
        self.assertEqual(ec.syntax_fix("marieb.essai@gmail'com"), "marieb.essai@gmail.com")
        self.assertEqual(ec.issue("marieb.essai@gmail'com"), ("invalid", "marieb.essai@gmail.com"))

    def test_valid_addresses_untouched(self):
        for a in ("jean.dupont@videotron.ca", "hugues.thibodeau@videotron.qc.ca", "a+b@sub.example.org", "o'brien@example.com"):
            with self.subTest(a=a):
                self.assertEqual(ec.issue(a), (False, None))
                self.assertIsNone(ec.syntax_fix(a))

    def test_typo_of_a_popular_domain_is_suggested_not_auto_fixed(self):
        self.assertEqual(ec.issue("x@gmial.com"), ("typo", "x@gmail.com"))
        self.assertEqual(ec.issue("x@hotmal.com"), ("typo", "x@hotmail.com"))
        self.assertEqual(ec.issue("x@gmail.con"), ("typo", "x@gmail.com"))
        self.assertIsNone(ec.syntax_fix("x@gmial.com"))                 # a domain name is never changed automatically

    def test_syntax_fix_changes_no_letter(self):
        self.assertEqual(ec.syntax_fix("x @ gmail.com"), "x@gmail.com")
        self.assertEqual(ec.syntax_fix("x@gmail..com"), "x@gmail.com")
        self.assertEqual(ec.syntax_fix("x@gmail,com"), "x@gmail.com")
        self.assertEqual(ec.syntax_fix("x@@gmail.com"), "x@gmail.com")
        self.assertIsNone(ec.syntax_fix("marie claude@gmail.com"))      # a dot or nothing? only the person knows

    def test_unfixable_and_disposable(self):
        self.assertEqual(ec.issue("pas une adresse"), ("invalid", None))
        self.assertEqual(ec.issue("a@b"), ("invalid", None))
        self.assertEqual(ec.issue("bob@yopmail.com"), ("disposable", None))
        self.assertEqual(ec.issue(""), (False, None))
        self.assertEqual(ec.issue(None), (False, None))


if __name__ == "__main__":
    unittest.main()
