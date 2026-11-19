# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of post_load (no database, no Odoo needed: a fake odoo module is used when Odoo is absent).

Run alone, without Odoo:
    python3 rlq_preload_statics/tests/test_preload.py -v
"""
import importlib.util
import logging
import os
import sys
import types
import unittest

try:
    from odoo.tests.common import BaseCase as _Base
except ImportError:
    _Base = unittest.TestCase

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "__init__.py")


def _load(fake_odoo):
    """The module loaded with `fake_odoo` as odoo (and odoo.http), whatever is installed."""
    saved = {k: sys.modules.get(k) for k in ("odoo", "odoo.http")}
    sys.modules["odoo"], sys.modules["odoo.http"] = fake_odoo, fake_odoo.http
    try:
        spec = importlib.util.spec_from_file_location("rlq_preload_statics_under_test", _PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


class _Root:
    def __init__(self, fail=False):
        self.calls, self.fail = 0, fail

    @property
    def statics(self):
        self.calls += 1
        if self.fail:
            raise OSError("addons_path unreadable")
        return {"web": "/x/web/static", "base": "/x/base/static"}


def _fake(evented=False, fail=False):
    odoo = types.ModuleType("odoo")
    odoo.evented = evented
    odoo.http = types.ModuleType("odoo.http")
    odoo.http.root = _Root(fail)
    return odoo


class TestPostLoad(_Base):

    def test_lists_the_static_folders_in_the_main_process(self):
        odoo = _fake()
        module = _load(odoo)
        with self.assertLogs(module._logger.name, logging.INFO) as logs:
            _run(module, odoo)
        self.assertEqual(odoo.http.root.calls, 1)
        self.assertIn("static folders of 2 modules", logs.output[0])

    def test_nothing_in_the_gevent_process(self):
        odoo = _fake(evented=True)
        module = _load(odoo)
        _run(module, odoo)
        self.assertEqual(odoo.http.root.calls, 0)

    def test_a_failure_never_stops_odoo(self):
        odoo = _fake(fail=True)
        module = _load(odoo)
        with self.assertLogs(module._logger.name, logging.ERROR):
            _run(module, odoo)                                     # no exception


def _run(module, odoo):
    saved = {k: sys.modules.get(k) for k in ("odoo", "odoo.http")}
    sys.modules["odoo"], sys.modules["odoo.http"] = odoo, odoo.http
    try:
        module.odoo = odoo
        module.post_load()
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


if __name__ == "__main__":
    unittest.main()
