# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
#
# Server-wide module (server_wide_modules = ...,rlq_preload_statics; NOT installed in a database). Odoo loads the server-wide modules in its
# main process, before it forks the prefork workers (odoo.service.server.start). Each worker otherwise builds odoo.http.root.statics (the
# static/ folder of every module of addons_path: a manifest read and an icon looked for in every folder of addons_path, for every module) the
# first time it serves a static file. Built here once, the list is inherited by every worker at its fork, the replaced workers included.
# Not done in the gevent process (odoo.evented: live chat, no static file). A failure is logged and changes nothing: each worker then builds
# the list itself, as before.
import logging
import time

import odoo

_logger = logging.getLogger(__name__)


def preload(root):
    """Builds root.statics (lazy property of odoo.http.Application); returns the number of modules with a static/ folder."""
    return len(root.statics)


def post_load():
    if getattr(odoo, "evented", False):
        return
    start = time.time()
    try:
        from odoo import http                     # never « import odoo.http » here: it would make odoo a local name
        count = preload(http.root)
    except Exception:  # noqa: BLE001 - never stop Odoo for an optimisation
        _logger.exception("rlq_preload_statics: static folders not listed in advance (each worker will list them itself)")
        return
    _logger.info("rlq_preload_statics: static folders of %d modules listed in %.1f s, before the workers start (inherited by every worker)",
                 count, time.time() - start)
