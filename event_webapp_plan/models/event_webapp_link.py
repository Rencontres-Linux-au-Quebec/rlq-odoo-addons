# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Link shown as a button on the web app of an event day."""

from odoo import fields, models


class EventWebappLink(models.Model):
    _name = "event.webapp.link"
    _description = "Event Web App Link"
    _order = "sequence, id"

    webapp_id = fields.Many2one(
        "event.webapp",
        string="Event day",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Label", required=True, translate=True)
    url = fields.Char(string="URL", required=True)
    description = fields.Char(translate=True)
