# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Data of the tests: an open event day whose event has a raffle with
prizes (the data of event_raffle_prize_handover's tests: a pick-up
location, a physical and a virtual prize), and portal users who win or
not. Every name below is invented for the tests."""

from datetime import timedelta

from odoo import Command, fields
from odoo.tests.common import new_test_user

from odoo.addons.event_raffle_prize_handover.tests.common import (
    HandoverDataMixin,
)


class PrizeWebappMixin(HandoverDataMixin):
    @classmethod
    def _webapp_setup(cls, prefix):
        """The day, its raffle and two portal users, ``prefix`` making
        their logins unique per test class."""
        cls._handover_setup()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.env["event.webapp"].search([]).write({"active": False})
        now = fields.Datetime.now()
        cls.day = cls.env["event.webapp"].create(
            {
                "name": "Prize Test Day",
                "date_start": now - timedelta(hours=1),
                "date_end": now + timedelta(hours=8),
                "event_ids": [Command.set(cls.event.ids)],
            }
        )
        cls.home = f"/webapp_event/{cls.day.id}"
        cls.winner_user = cls._portal_user(prefix + "_winner", "Wanda Winner")
        cls.other_user = cls._portal_user(prefix + "_other", "Otto Other")

    @classmethod
    def _portal_user(cls, login, name):
        return new_test_user(
            cls.env,
            login=login,
            password=login,
            groups="base.group_portal",
            name=name,
            email=f"{login}@example.com",
            lang="en_US",
            tz="America/Toronto",
        )

    @classmethod
    def _participant_of(cls, user, attended=True, raffle=None):
        """A participant of ``raffle`` (the test raffle by default) for the
        partner of ``user``, with a registration to its event, checked in
        when ``attended``."""
        raffle = raffle or cls.raffle
        partner = user.partner_id
        registration = cls.env["event.registration"].create(
            {
                "event_id": raffle.event_id.id,
                "partner_id": partner.id,
                "name": partner.name,
                "email": partner.email,
            }
        )
        if attended:
            registration.action_set_done()
        return cls.env["event.raffle.participant"].create(
            {
                "raffle_id": raffle.id,
                "name": partner.name,
                "email": partner.email,
                "partner_id": partner.id,
                "registration_id": registration.id,
                "source": "registration",
            }
        )
