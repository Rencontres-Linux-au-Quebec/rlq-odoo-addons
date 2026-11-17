# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Static check of the related fields of the module (v1.130.0) - NO DEPENDENCY ON ODOO, run by run-all.sh:

    python3 -m unittest tests.test_related_fields -v

A related field must have the type of the field it points to; otherwise Odoo refuses to load the WHOLE database
(« TypeError: Type of related field ... is inconsistent with ... ») and the site is down. Seen in production with 18.0.1.129.0:
fields.Text(related="question_id.title") while survey.question.title is a Char.

Every related field of models/*.py must have its target in TARGETS (path -> type, checked in the source of Odoo 18.0 or in this
module). A new related field without an entry fails the test: add the entry after checking the type of the target.
"""
import re
import unittest
from pathlib import Path

MODELS = Path(__file__).resolve().parent.parent / "models"

# (file, related path) -> type of the target field
TARGETS = {
    ("survey_answer_edit.py", "user_input_id.survey_id"): "Many2one",       # survey.user_input.survey_id
    ("survey_answer_edit.py", "question_id.question_type"): "Selection",     # survey.question.question_type
    ("survey_answer_edit.py", "question_id.comments_allowed"): "Boolean",    # survey.question.comments_allowed
    ("event_registration_email.py", "registration_id.event_id"): "Many2one",  # event.registration.event_id
    ("event_registration_email.py", "registration_id.name"): "Char",          # event.registration.name
    ("event_registration_email.py", "registration_id.email"): "Char",         # event.registration.email
    ("event_registration_email.py", "registration_id.rlq_email_issue"): "Selection",   # this module
}
FIELD = re.compile(r"=\s*fields\.(\w+)\((.*?)\)\s*$", re.S | re.M)


def related_fields():
    for path in sorted(MODELS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^\s+\w+\s*=\s*fields\.(\w+)\(", source, re.M):
            depth, end = 0, match.end() - 1
            for end in range(match.end() - 1, len(source)):            # the arguments, up to the closing parenthesis
                depth += {"(": 1, ")": -1}.get(source[end], 0)
                if depth == 0:
                    break
            related = re.search(r"""related\s*=\s*["']([\w.]+)["']""", source[match.end():end])
            if related:
                yield path.name, related.group(1), match.group(1), source[:match.start()].count("\n") + 1


class TestRelatedFields(unittest.TestCase):
    def test_every_related_field_has_the_type_of_its_target(self):
        found = list(related_fields())
        self.assertTrue(found)
        problems = []
        for filename, path, kind, line in found:
            expected = TARGETS.get((filename, path))
            if expected is None:
                problems.append("%s:%d related=%r: add its target type to TARGETS" % (filename, line, path))
            elif expected != kind:
                problems.append("%s:%d fields.%s(related=%r): the target is a %s" % (filename, line, kind, path, expected))
        self.assertEqual(problems, [])

    def test_the_check_catches_the_bug_of_1_129(self):
        """The field that made the database fail to load (Text related to a Char) is refused."""
        self.assertNotEqual(TARGETS.get(("survey_answer_edit.py", "question_id.title"), "Char"), "Text")


if __name__ == "__main__":
    unittest.main()
