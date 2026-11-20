# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of rlq_web_dialog_size_fix (files only, no database). Run by Odoo with the module tests, or alone:
    python3 rlq_web_dialog_size_fix/tests/test_files.py -v
The behaviour itself (a rejected promise handled in the same tick) is checked with node when it is installed.
"""
import ast
import os
import shutil
import subprocess
import tempfile
import unittest

try:
    from odoo.tests.common import BaseCase as _Base
except ImportError:
    _Base = unittest.TestCase

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(MODULE, "static", "src", "expand_button_patch.esm.js")


def manifest():
    with open(os.path.join(MODULE, "__manifest__.py"), encoding="utf-8") as f:
        return ast.literal_eval(f.read().split("\n", 6)[-1])


def patch_js():
    with open(JS, encoding="utf-8") as f:
        return f.read()


class TestFiles(_Base):

    def test_manifest(self):
        m = manifest()
        self.assertEqual(m["depends"], ["web_dialog_size"])
        self.assertTrue(m["auto_install"])                      # installed with web_dialog_size, nothing to remember
        self.assertEqual(m["assets"], {"web.assets_backend": ["rlq_web_dialog_size_fix/static/src/expand_button_patch.esm.js"]})

    def test_patch(self):
        js = patch_js()
        self.assertIn('import {ExpandButton} from "@web_dialog_size/js/web_dialog_size.esm";', js)
        self.assertIn("super.setup(...arguments);", js)
        self.assertIn("this.config.catch(() => {});", js)
        self.assertLess(js.index("super.setup(...arguments);"), js.index("this.config.catch"))

    @unittest.skipIf(shutil.which("node") is None, "node absent")
    def test_rejet_pris_en_charge_dans_le_meme_tour(self):
        # Same logic as the patch, with the RPC of an expired session: no unhandledRejection, and onMounted() still sees it.
        prog = r"""
        let unhandled = 0;
        process.on("unhandledRejection", () => { unhandled++; });
        class ExpandButton { setup() { this.config = Promise.reject(new Error("Session expired")); } }
        const orig = ExpandButton.prototype.setup;
        ExpandButton.prototype.setup = function () {
            orig.apply(this, arguments);
            if (this.config && typeof this.config.catch === "function") { this.config.catch(() => {}); }
        };
        const b = new ExpandButton(); b.setup();
        setTimeout(() => {                                   // onMounted(), later: its own .catch() still runs
            b.config.then(() => {}).catch(() => { console.log("mounted-catch"); });
            setTimeout(() => { console.log("unhandled=" + unhandled); }, 20);
        }, 30);
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(prog)
        try:
            out = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=30).stdout
        finally:
            os.unlink(f.name)
        self.assertIn("mounted-catch", out)
        self.assertIn("unhandled=0", out)

    @unittest.skipIf(shutil.which("node") is None, "node absent")
    def test_sans_le_correctif_le_rejet_est_orphelin(self):
        prog = r"""
        let unhandled = 0;
        process.on("unhandledRejection", () => { unhandled++; });
        const config = Promise.reject(new Error("Session expired"));
        setTimeout(() => { config.catch(() => {}); setTimeout(() => console.log("unhandled=" + unhandled), 20); }, 30);
        """
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(prog)
        try:
            out = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=30).stdout
        finally:
            os.unlink(f.name)
        self.assertIn("unhandled=1", out)                    # what the browser reports to Odoo's error service today


if __name__ == "__main__":
    unittest.main()
