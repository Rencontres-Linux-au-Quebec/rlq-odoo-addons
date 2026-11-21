# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Raffle side of the pre-fill of the event days.

A raffle created, or whose planned date, event or test flag changes, joins
the days on which it starts to fit (see `raffle_fits_day()` in
event_webapp.py). It joins them as superuser: the user who saves a raffle
seldom may write the event days, and the link only puts this raffle on days
that already list its event. It never leaves a day automatically.
"""

from collections import defaultdict

from odoo import Command, api, models

from .event_webapp import raffle_fits_day

# Fields of a raffle that decide which days it fits.
DAY_FIT_FIELDS = frozenset(("date_planned", "event_id", "is_test"))


class EventRaffle(models.Model):
    _inherit = "event.raffle"

    @api.model_create_multi
    def create(self, vals_list):
        raffles = super().create(vals_list)
        raffles._ewp_join_fitting_days({})
        return raffles

    def write(self, vals):
        if not DAY_FIT_FIELDS & vals.keys():
            return super().write(vals)
        old_days = self._ewp_fitting_day_ids()
        result = super().write(vals)
        self._ewp_join_fitting_days(old_days)
        return result

    def _ewp_fitting_day_ids(self):
        """Return {raffle id: set of ids of the days it fits}, over the
        active and the archived days, read as superuser."""
        raffles = self.sudo()
        days = self.env["event.webapp"]
        if raffles.event_id:
            days = (
                days.sudo()
                .with_context(active_test=False)
                .search([("event_ids", "in", raffles.event_id.ids)])
            )
        states = days._ewp_raffle_state()
        return {
            raffle.id: {
                day_id
                for day_id, state in states.items()
                if raffle_fits_day(raffle, *state)
            }
            for raffle in raffles
        }

    def _ewp_join_fitting_days(self, old_day_ids):
        """Link each raffle to the days it fits now and did not fit in
        `old_day_ids` (a value of `_ewp_fitting_day_ids()`; a missing
        raffle is a new one)."""
        raffle_ids_by_day = defaultdict(list)
        for raffle_id, day_ids in self._ewp_fitting_day_ids().items():
            for day_id in day_ids - old_day_ids.get(raffle_id, set()):
                raffle_ids_by_day[day_id].append(raffle_id)
        days = self.env["event.webapp"].sudo()
        for day_id, raffle_ids in raffle_ids_by_day.items():
            days.browse(day_id).write(
                {"raffle_ids": [Command.link(rid) for rid in raffle_ids]}
            )
