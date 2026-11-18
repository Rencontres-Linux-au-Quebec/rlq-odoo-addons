# -*- coding: utf-8 -*-
# Copyright (C) 2026 Rencontres Linux au Québec contributors
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
"""
test_release.py - release.py, __manifest__.py and doc/CHANGELOG.md agree (v1.137.0). Standalone: no Odoo needed.

    python3 -m unittest tests.test_release
"""
import ast
import importlib.util
import os
import re
import unittest
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _release():
    spec = importlib.util.spec_from_file_location("rlq_release", os.path.join(HERE, "release.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRelease(unittest.TestCase):

    def test_version_everywhere_the_same(self):
        release = _release()
        with open(os.path.join(HERE, "__manifest__.py"), encoding="utf-8") as handle:
            manifest = ast.literal_eval(handle.read())
        self.assertEqual(release.__version__, manifest["version"])
        with open(os.path.join(HERE, "doc", "CHANGELOG.md"), encoding="utf-8") as handle:
            first = re.search(r"^## (\S+)", handle.read(), re.M).group(1)
        self.assertEqual(first, release.__version__, "the first entry of CHANGELOG.md must be the version of release.py")

    def test_version_datetime(self):
        release = _release()
        moment = datetime.strptime(release.VERSION_DATETIME, "%Y-%m-%d %H:%M:%S")
        self.assertGreaterEqual(moment.year, 2026)
        self.assertEqual(release.VERSION_ZONE, "America/Toronto")

    def test_guide_news_lists_the_current_version(self):
        """« Nouveautés » of the guide names the current version (and the two before): it can no longer go stale."""
        release = _release()
        with open(os.path.join(HERE, "doc", "Guide-utilisateur-rlq_survey_report.html"), encoding="utf-8") as handle:
            guide = handle.read()
        news = guide[guide.index("Nouveautés"):]
        news = news[:news.index("</div>")]
        minor = int(release.__version__.split(".")[3])
        for number in (minor, minor - 1, minor - 2):
            self.assertIn("v1.%d" % number, news)
        self.assertIn(release.__version__, guide[:guide.index("Nouveautés")])          # the header of the guide


if __name__ == "__main__":
    unittest.main()
