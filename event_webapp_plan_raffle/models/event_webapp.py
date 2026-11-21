# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Raffle prizes and registrations of a contact for an event day.

The web app asks the day for the draws a contact won and for the
registrations of that contact; both helpers search as superuser, since
portal users read neither model, and take the contact as an argument:
the controller passes the partner of the current user, never one from the
request.
"""

from odoo import api, models
from odoo.tools import str2bool

from .res_config_settings import PARAM_ONSITE_CARD


class EventWebapp(models.Model):
    _inherit = "event.webapp"

    @api.model
    def _ewp_onsite_card_enabled(self):
        """True when the setting "On-site card" is ticked (config parameter
        PARAM_ONSITE_CARD, read as superuser); False when the parameter is
        missing, which is the default, or holds anything but a true
        value."""
        value = (
            self.env["ir.config_parameter"].sudo().get_param(PARAM_ONSITE_CARD)
        )
        return bool(str2bool(value or "", default=False))

    def _ewp_prize_raffles(self):
        """Raffles of this day, as superuser: those listed on the day and
        those of its events."""
        self.ensure_one()
        day = self.sudo()
        return day.raffle_ids | day.env["event.raffle"].search(
            [("event_id", "in", day.event_ids.ids)]
        )

    def _ewp_prize_draws(self, partner):
        """Draws of this day's raffles won by ``partner``, as superuser,
        newest first.

        A draw belongs to ``partner`` when its winning participant is that
        contact; once the participant is deleted, when the prize order of
        the draw is theirs. Draws marked absent are left out: the winner
        was not there and the draw went to someone else.
        """
        self.ensure_one()
        draws = self.env["event.raffle.draw"].sudo()
        if not partner:
            return draws
        return draws.search(
            [
                ("raffle_id", "in", self._ewp_prize_raffles().ids),
                ("is_absent", "=", False),
                "|",
                ("partner_id", "=", partner.id),
                "&",
                ("partner_id", "=", False),
                ("prize_order_id.partner_id", "=", partner.id),
            ],
            order="date desc, id desc",
        )

    def _ewp_partner_registrations(self, partner):
        """Registrations of ``partner`` to the events of this day that
        are not cancelled, as superuser."""
        self.ensure_one()
        registrations = self.env["event.registration"].sudo()
        if not partner:
            return registrations
        return registrations.search(
            [
                ("event_id", "in", self.sudo().event_ids.ids),
                ("partner_id", "=", partner.id),
                ("state", "!=", "cancel"),
            ]
        )
