# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""The "On site" card of the web app, in the general settings.

The checkbox is the config parameter PARAM_ONSITE_CARD, for every day of
the web app. Odoo stores "True" when it is ticked and deletes the
parameter when it is cleared; the module ships no value, so the card is
off on a new database and on an updated one until an administrator ticks
it. event.webapp._ewp_onsite_card_enabled() reads it.
"""

from odoo import fields, models

PARAM_ONSITE_CARD = "event_webapp_plan_raffle.onsite_card"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ewp_onsite_card = fields.Boolean(
        string="On-site card",
        config_parameter=PARAM_ONSITE_CARD,
        help='Shows the "On site" card on the home page of the web app: '
        "an attendee tells the organizers that they are at the event. For "
        "information only: the attendance of the raffles comes from the "
        "check-in scan. Turned off, the card and its route are gone and "
        "the declared attendance already saved is kept.",
    )
