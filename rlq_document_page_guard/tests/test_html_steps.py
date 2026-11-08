# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of lib/html_steps.py (pure functions, no database).

Run by Odoo with the module tests, or alone, without Odoo:
    python3 rlq_document_page_guard/tests/test_html_steps.py -v
"""
import importlib.util
import os
import unittest

try:
    from odoo.tests.common import BaseCase as _Base
except ImportError:
    _Base = unittest.TestCase

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "html_steps.py")
_spec = importlib.util.spec_from_file_location("rlq_html_steps", _PATH)
html_steps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(html_steps)
trim = html_steps.trim_history_steps


class TestHtmlSteps(_Base):

    def test_keeps_last_id(self):
        html = '<p data-oe-version="2.0" data-last-history-steps="111,222,333">Bonjour</p>'
        self.assertEqual(trim(html), '<p data-oe-version="2.0" data-last-history-steps="333">Bonjour</p>')

    def test_keep_two(self):
        html = '<div data-last-history-steps="1,2,3,4">x</div>'
        self.assertEqual(trim(html, keep=2), '<div data-last-history-steps="3,4">x</div>')

    def test_keep_zero_removes_attribute(self):
        html = '<div class="a" data-last-history-steps="1,2,3">x</div>'
        self.assertEqual(trim(html, keep=0), '<div class="a">x</div>')

    def test_single_quotes_and_case(self):
        html = "<div DATA-LAST-HISTORY-STEPS='7,8,9'>x</div>"
        self.assertEqual(trim(html), "<div DATA-LAST-HISTORY-STEPS='9'>x</div>")

    def test_empty_value_removed(self):
        self.assertEqual(trim('<div data-last-history-steps="">x</div>'), "<div>x</div>")

    def test_unchanged_without_attribute(self):
        html = "<p>Texte ordinaire, data-last-history-steps cité dans le texte</p>"
        self.assertIs(trim(html), html)

    def test_text_mention_not_touched(self):
        # The words in the visible text are not an attribute (no '=' after them): kept.
        html = '<p data-last-history-steps="5,6">On parle de data-last-history-steps ici</p>'
        self.assertEqual(trim(html), '<p data-last-history-steps="6">On parle de data-last-history-steps ici</p>')

    def test_falsy_values(self):
        for value in (False, None, ""):
            self.assertIs(trim(value), value)

    def test_huge_value(self):
        # The case of 2026-11-07: 24 MB of ids around 528 words of text.
        ids = ",".join(str(10**9 + i) for i in range(2_000_000))
        html = f'<div data-last-history-steps="{ids}"><p>{"mot " * 528}</p></div>'
        result = trim(html)
        self.assertLess(len(result), 5000)
        self.assertIn(f'data-last-history-steps="{10**9 + 1_999_999}"', result)
        self.assertIn("mot " * 528, result)

    def test_idempotent(self):
        html = '<div data-last-history-steps="1,2,3">x</div>'
        self.assertEqual(trim(trim(html)), trim(html))

    def test_markup_type_kept(self):
        try:
            from markupsafe import Markup
        except ImportError:
            self.skipTest("markupsafe not installed")
        result = trim(Markup('<div data-last-history-steps="1,2">x &amp; y</div>'))
        self.assertIsInstance(result, Markup)
        self.assertEqual(str(result), '<div data-last-history-steps="2">x &amp; y</div>')

    def test_steps_size(self):
        self.assertEqual(html_steps.steps_size('<div data-last-history-steps="12,34">x</div>'), 5)
        self.assertEqual(html_steps.steps_size("<div>x</div>"), 0)
        self.assertEqual(html_steps.steps_size(None), 0)


if __name__ == "__main__":
    unittest.main()
