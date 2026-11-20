# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of rlq_discuss_frontend_fix.

The first class reads the files only (no database) and runs alone, without Odoo:
    python3 rlq_discuss_frontend_fix/tests/test_assets.py -v
The second class runs with the module tests in Odoo: the patch is really in the website bundle and never in the back-office one.
"""
import ast
import os
import re
import unittest

try:
    from odoo.tests.common import BaseCase as _Base, TransactionCase, tagged
except ImportError:
    _Base = unittest.TestCase
    TransactionCase = None

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH = "rlq_discuss_frontend_fix/static/src/thread_model_patch.js"


def manifest():
    with open(os.path.join(MODULE, "__manifest__.py"), encoding="utf-8") as f:
        return ast.literal_eval(f.read().split("\n", 6)[-1])


def patch_js():
    with open(os.path.join(MODULE, "static", "src", "thread_model_patch.js"), encoding="utf-8") as f:
        return f.read()


class TestFiles(_Base):

    def test_patch_in_website_and_public_bundles_only(self):
        assets = manifest()["assets"]
        self.assertIn(PATCH, assets["im_livechat.assets_embed_core"])     # included by web.assets_frontend (website)
        self.assertIn(PATCH, assets["mail.assets_public"])                # public discussion pages
        self.assertNotIn("web.assets_backend", assets)                    # the back-office has Odoo's own function

    def test_depends(self):
        self.assertEqual(set(manifest()["depends"]), {"mail", "im_livechat"})

    def test_patch_defines_close_chat_window(self):
        js = patch_js()
        self.assertTrue(js.startswith("/** @odoo-module **/"))
        self.assertIn('import { Thread } from "@mail/core/common/thread_model";', js)
        self.assertRegex(js, r"patch\(Thread\.prototype, \{\s+closeChatWindow\(\) \{")
        self.assertIn("chatWindow?.close({ notifyState: false });", js)

    def test_odoo_function_kept_when_it_exists(self):
        self.assertIn('if (typeof super.closeChatWindow === "function")', patch_js())

    def test_version(self):
        self.assertTrue(re.fullmatch(r"18\.0\.\d+\.\d+\.\d+", manifest()["version"]))


if TransactionCase is not None:
    @tagged("post_install", "-at_install")
    class TestBundles(TransactionCase):

        def _urls(self, bundle):
            files = self.env["ir.qweb"]._get_asset_bundle(bundle, debug_assets=True).files
            return [f.get("url", "") for f in files]

        def test_in_frontend_bundle(self):
            self.assertTrue(any(u.endswith(PATCH) for u in self._urls("web.assets_frontend")))

        def test_not_in_backend_bundle(self):
            self.assertFalse(any(u.endswith(PATCH) for u in self._urls("web.assets_backend")))


if __name__ == "__main__":
    unittest.main()
