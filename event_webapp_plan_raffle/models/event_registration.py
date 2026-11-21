# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Self-declared attendance of a registration.

The attendee says "I am on site" in the event web app. The two fields are
information for the organisers only: the attendance mode of the raffles
(event.raffle.participant.attendance_mode, module event_raffle_prize)
reads the state of the registration, set by the check-in scan, and never
these fields. They are written by _ewp_declare_attendance() only.
"""

from odoo import fields, models


class EventRegistration(models.Model):
    _inherit = "event.registration"

    attendance_declared = fields.Boolean(
        string="Declared on site",
        readonly=True,
        copy=False,
        help="The attendee said in the event web app that they are on "
        "site. Information only: the raffles take the attendance from the "
        "check-in scan.",
    )
    attendance_declared_date = fields.Datetime(
        string="Declared on site at",
        readonly=True,
        copy=False,
    )

    def _ewp_declare_attendance(self, on_site):
        """Write the self-declared attendance of these registrations, as
        superuser: ``on_site`` true sets the flag and the current time,
        false clears both. The caller decides whose registrations they
        are (the web app passes those of the current user only). Returns
        True."""
        self.sudo().write(
            {
                "attendance_declared": bool(on_site),
                "attendance_declared_date": (
                    fields.Datetime.now() if on_site else False
                ),
            }
        )
        return True
