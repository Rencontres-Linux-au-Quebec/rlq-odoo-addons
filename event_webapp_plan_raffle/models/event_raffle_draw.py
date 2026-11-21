# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""The self-declared attendance of the winner, shown on the draw.

Both fields are related to the registration of the winning participant
and read only: the draw form shows them beside the attendance mode, which
they never change.
"""

from odoo import fields, models


class EventRaffleDraw(models.Model):
    _inherit = "event.raffle.draw"

    winner_attendance_declared = fields.Boolean(
        string="Declared on site",
        related="winner_participant_id.registration_id.attendance_declared",
        help="The winner said in the event web app that they are on site. "
        "Information only: the attendance comes from the check-in scan.",
    )
    winner_attendance_declared_date = fields.Datetime(
        string="Declared on site at",
        related=(
            "winner_participant_id.registration_id.attendance_declared_date"
        ),
    )
