# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""BigBlueButton server of the event web app, in the general settings.

The URL is an ordinary config parameter. The shared secret is write-only:
the field starts empty on every opening of the settings, a value typed in
it replaces the stored parameter on save and is then wiped from the
transient record, so the secret never travels back to a browser.
`ewp_bbb_secret_set` tells whether one is stored.

The display mode of the conferences is the config parameter
PARAM_BBB_DISPLAY (see event_webapp_room._ewp_bbb_display()); the form
shows "auto" for a parameter unset or holding an unknown value.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from . import bbb_client
from .event_webapp_room import (
    PARAM_BBB_DISPLAY,
    PARAM_BBB_SECRET,
    PARAM_BBB_URL,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ewp_bbb_server_url = fields.Char(
        string="BigBlueButton server",
        config_parameter=PARAM_BBB_URL,
        help="Address of the BigBlueButton server, as printed by "
        '"bbb-conf --secret" on the server.',
    )
    ewp_bbb_secret = fields.Char(
        string="Shared secret",
        help="Shared secret of the BigBlueButton server, as printed by "
        '"bbb-conf --secret" on the server. Never shown again once saved: '
        "type a new one to replace it.",
    )
    ewp_bbb_secret_set = fields.Boolean(
        string="Secret saved", compute="_compute_ewp_bbb_secret_set"
    )
    ewp_bbb_display = fields.Selection(
        [
            (
                "auto",
                "Automatic: embedded only when the server is on the same "
                "site as this web app",
            ),
            ("frame", "Always embedded in the room page"),
            ("tab", "Always in a new tab"),
        ],
        string="Video conference display",
        default="auto",
        required=True,
        config_parameter=PARAM_BBB_DISPLAY,
        help="The video conference server keeps the session of each "
        "participant in a cookie. Browsers refuse that cookie when the "
        "conference is embedded in a page of another site, and Safari "
        "always refuses it: the conference then fails to load in the room "
        "page. The automatic mode embeds it only when the server is on the "
        "same site as this web app, and otherwise shows a button that "
        "opens it in a new tab, the room page and its discussion staying "
        "open.",
    )

    @api.depends("ewp_bbb_secret")
    def _compute_ewp_bbb_secret_set(self):
        stored = bool(
            self.env["ir.config_parameter"].sudo().get_param(PARAM_BBB_SECRET)
        )
        for settings in self:
            settings.ewp_bbb_secret_set = stored

    def get_values(self):
        res = super().get_values()
        res["ewp_bbb_display"] = self.env[
            "event.webapp.room"
        ]._ewp_bbb_display()
        return res

    def set_values(self):
        super().set_values()
        url = (self.ewp_bbb_server_url or "").strip()
        if url and not bbb_client.api_url(url):
            raise UserError(
                _(
                    "The BigBlueButton server must be an http or https "
                    "address."
                )
            )
        secret = (self.ewp_bbb_secret or "").strip()
        if secret:
            self.env["ir.config_parameter"].sudo().set_param(
                PARAM_BBB_SECRET, secret
            )
            self.ewp_bbb_secret = False

    def action_ewp_bbb_forget_secret(self):
        """Delete the stored secret: the rooms stop joining meetings
        through the API and use their conference URL.

        RPC reaches the method on an empty recordset, which no access
        right covers, and the parameter is written with sudo: like
        execute(), the method refuses every caller who is not an
        administrator (env.is_admin())."""
        if not self.env.is_admin():
            raise AccessError(_("Only administrators can change the settings"))
        self.env["ir.config_parameter"].sudo().set_param(
            PARAM_BBB_SECRET, False
        )
        return {"type": "ir.actions.client", "tag": "reload"}
