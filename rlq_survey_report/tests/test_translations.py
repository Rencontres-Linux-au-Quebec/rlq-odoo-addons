# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Checks of i18n/fr.po (v1.129.0) - NO DEPENDENCY ON ODOO, run by run-all.sh (standalone tests):

    python3 -m unittest tests.test_translations -v

Odoo finds the translation of a view TEXT (between tags) only if the msgid is written as Odoo stores the view: XML-escaped
(« > » as « &gt; », « & » as « &amp; »). An entry written with the raw character is silently ignored and the text stays in
English (seen in 18.0.1.127.0: « Click a question to change its answer... (Surveys > Detailed reports > ...) »).
"""
import re
import unittest
from pathlib import Path

PO = Path(__file__).resolve().parent.parent / "i18n" / "fr.po"
RAW = re.compile(r"[<>]|&(?!(amp|lt|gt|quot|apos|#\d+);)")


def entries():
    text = PO.read_text(encoding="utf-8")
    for block in text.split("\n\n"):
        msgid = re.search(r'^msgid "(.*)"$', block, re.M)
        msgstr = re.search(r'^msgstr "(.*)"$', block, re.M)
        if msgid and msgid.group(1):
            yield block, msgid.group(1), msgstr.group(1) if msgstr else ""


class TestFrenchTranslations(unittest.TestCase):
    def test_view_texts_are_xml_escaped(self):
        bad = []
        for block, msgid, msgstr in entries():
            refs = [line for line in block.splitlines() if line.startswith("#: ")]
            view_text = any("model_terms:" in ref or "act_window,help" in ref for ref in refs)
            only_view = all("model_terms:" in ref or "act_window,help" in ref for ref in refs)
            if view_text and only_view and (RAW.search(msgid) or RAW.search(msgstr)):
                bad.append(msgid)
        self.assertEqual(bad, [], "view texts with a raw <, > or & are never found by Odoo")

    def test_every_entry_is_translated_once(self):
        ids = [msgid for _block, msgid, _msgstr in entries()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate msgid")
        self.assertEqual([msgid for _block, msgid, msgstr in entries() if not msgstr], [], "msgid without translation")

    def test_code_entries_are_marked_for_odoo(self):
        """A string of the Python code is loaded by Odoo only with the comment « #. odoo-python »."""
        missing = [msgid for block, msgid, _msgstr in entries()
                   if any(line.startswith("#: code:") and line.endswith(".py:0") for line in block.splitlines())
                   and "#. odoo-python" not in block]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
