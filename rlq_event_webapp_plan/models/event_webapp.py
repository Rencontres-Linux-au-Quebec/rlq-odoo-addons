# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Option of the Rencontres Linux theme on an event day."""

from odoo import fields, models


class EventWebapp(models.Model):
    _inherit = "event.webapp"

    rlq_show_poster = fields.Boolean(
        string="Pause Café Linux card",
        help="Shows the card of the weekly Pause Café Linux, with its "
        "poster, on the home page of the web app.",
    )
