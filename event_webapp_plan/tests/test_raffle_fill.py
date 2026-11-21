# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests of the pre-fill of the raffles of an event day.

A raffle joins a day when it starts to fit it: the day lists its event and
its planned date falls inside the opening window or, without planned date,
its event lies entirely inside the window. Test raffles never join, and
nothing leaves a day automatically.

The dates are fixed and invented: two consecutive days of a two-day event,
in UTC, as the ORM stores them.
"""

from odoo import Command
from odoo.tests import Form, TransactionCase, tagged

MANAGER = "event_webapp_plan.group_event_webapp_manager"

DAY1 = ("2031-06-10 08:00:00", "2031-06-10 22:00:00")
DAY2 = ("2031-06-11 08:00:00", "2031-06-11 22:00:00")


@tagged("post_install", "-at_install")
class TestRaffleFill(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Event = cls.env["event.event"]
        cls.two_day_event = Event.create(
            {
                "name": "Two-day Fill Event",
                "date_begin": "2031-06-10 13:00:00",
                "date_end": "2031-06-11 20:00:00",
            }
        )
        cls.first_day_event = Event.create(
            {
                "name": "First-day Fill Event",
                "date_begin": "2031-06-10 14:00:00",
                "date_end": "2031-06-10 18:00:00",
            }
        )
        cls.second_day_event = Event.create(
            {
                "name": "Second-day Fill Event",
                "date_begin": "2031-06-11 14:00:00",
                "date_end": "2031-06-11 18:00:00",
            }
        )

    def _day(self, window=DAY1, events=None, **vals):
        return self.env["event.webapp"].create(
            {
                "name": vals.pop("name", "Fill test day"),
                "date_start": window[0],
                "date_end": window[1],
                "event_ids": [
                    Command.set((events or self.env["event.event"]).ids)
                ],
                **vals,
            }
        )

    def _raffle(self, name, event, date_planned=False, **vals):
        return self.env["event.raffle"].create(
            {
                "name": name,
                "event_id": event.id,
                "date_planned": date_planned,
                **vals,
            }
        )

    @staticmethod
    def _listed(form):
        """Ids of the raffles listed in `form`, sorted."""
        return sorted(raffle.id for raffle in form.raffle_ids)

    def test_raffle_joins_the_day_that_holds_its_planned_date(self):
        friday = self._raffle(
            "Friday draw", self.two_day_event, "2031-06-10 17:00:00"
        )
        saturday = self._raffle(
            "Saturday draw", self.two_day_event, "2031-06-11 17:00:00"
        )
        day1 = self._day(DAY1, self.two_day_event)
        day2 = self._day(DAY2, self.two_day_event)
        self.assertEqual(day1.raffle_ids, friday)
        self.assertEqual(day2.raffle_ids, saturday)

    def test_window_bounds_are_included(self):
        opening = self._raffle("At opening", self.two_day_event, DAY1[0])
        closing = self._raffle("At closing", self.two_day_event, DAY1[1])
        day = self._day(DAY1, self.two_day_event)
        self.assertEqual(day.raffle_ids, opening | closing)

    def test_raffle_without_date_joins_when_its_event_fits_the_day(self):
        raffle = self._raffle("Undated", self.first_day_event)
        day = self._day(DAY1, self.first_day_event)
        self.assertEqual(day.raffle_ids, raffle)

    def test_raffle_without_date_of_a_multi_day_event_waits(self):
        self._raffle("Undated two-day", self.two_day_event)
        day1 = self._day(DAY1, self.two_day_event)
        day2 = self._day(DAY2, self.two_day_event)
        self.assertFalse(day1.raffle_ids)
        self.assertFalse(day2.raffle_ids)

    def test_test_raffle_never_joins(self):
        rehearsal = self._raffle(
            "Rehearsal",
            self.first_day_event,
            "2031-06-10 15:00:00",
            is_test=True,
        )
        day = self._day(DAY1, self.first_day_event)
        self.assertFalse(day.raffle_ids)
        # Neither when it is created later, nor when its date moves.
        self._raffle("Late rehearsal", self.first_day_event, is_test=True)
        rehearsal.date_planned = "2031-06-10 16:00:00"
        self.assertFalse(day.raffle_ids)
        # A rehearsal turned real joins.
        rehearsal.is_test = False
        self.assertEqual(day.raffle_ids, rehearsal)

    def test_raffle_of_an_event_off_the_day_does_not_join(self):
        self._raffle("Other event", self.second_day_event)
        self._raffle(
            "Other event, same day",
            self.second_day_event,
            "2031-06-10 15:00:00",
        )
        day = self._day(DAY1, self.first_day_event)
        self.assertFalse(day.raffle_ids)

    def test_raffle_removed_by_hand_stays_off(self):
        first = self._raffle("First", self.first_day_event)
        day = self._day(DAY1, self.first_day_event)
        self.assertEqual(day.raffle_ids, first)
        day.raffle_ids = [Command.unlink(first.id)]
        # An unrelated write of the day leaves the list as it is.
        day.write({"name": "Fill test day, renamed"})
        self.assertFalse(day.raffle_ids)
        # A new event brings its own raffles only.
        friday = self._raffle(
            "Friday draw", self.two_day_event, "2031-06-10 17:00:00"
        )
        self.assertFalse(day.raffle_ids)
        day.event_ids = [Command.link(self.two_day_event.id)]
        self.assertEqual(day.raffle_ids, friday)
        # A write that takes a raffle off while adding an event keeps it
        # off, even when the event is the raffle's own.
        day.write(
            {
                "event_ids": [Command.unlink(self.two_day_event.id)],
            }
        )
        day.write(
            {
                "event_ids": [Command.link(self.two_day_event.id)],
                "raffle_ids": [Command.unlink(friday.id)],
            }
        )
        self.assertFalse(day.raffle_ids)

    def test_raffle_created_later_joins_the_days(self):
        day1 = self._day(DAY1, self.two_day_event)
        day2 = self._day(DAY2, self.two_day_event)
        friday = self._raffle(
            "Friday draw", self.two_day_event, "2031-06-10 17:00:00"
        )
        self.assertEqual(day1.raffle_ids, friday)
        self.assertFalse(day2.raffle_ids)
        # Its planned date moves to the next day: it joins that day, and
        # stays on the first one, which is only ever filled.
        friday.date_planned = "2031-06-11 17:00:00"
        self.assertEqual(day1.raffle_ids, friday)
        self.assertEqual(day2.raffle_ids, friday)
        # Taken off by hand, a later date inside the same day does not
        # bring it back: it fitted that day already.
        day2.raffle_ids = [Command.clear()]
        friday.date_planned = "2031-06-11 18:00:00"
        self.assertFalse(day2.raffle_ids)
        # A raffle moved to the day's event joins.
        undated = self._raffle("Moved", self.second_day_event)
        day3 = self._day(DAY1, self.first_day_event)
        self.assertFalse(day3.raffle_ids)
        undated.event_id = self.first_day_event
        self.assertEqual(day3.raffle_ids, undated)

    def test_window_change_adds_the_raffles_that_start_to_fit(self):
        early = self._raffle(
            "Early", self.two_day_event, "2031-06-10 09:00:00"
        )
        late = self._raffle("Late", self.two_day_event, "2031-06-10 21:00:00")
        day = self._day(
            ("2031-06-10 08:00:00", "2031-06-10 12:00:00"),
            self.two_day_event,
        )
        self.assertEqual(day.raffle_ids, early)
        day.raffle_ids = [Command.clear()]
        day.date_end = "2031-06-10 22:00:00"
        # Late starts to fit; Early fitted before and stays off.
        self.assertEqual(day.raffle_ids, late)

    def test_copy_keeps_the_raffle_list(self):
        first = self._raffle("First", self.first_day_event)
        day = self._day(DAY1, self.first_day_event)
        day.raffle_ids = [Command.unlink(first.id)]
        copy = day.copy()
        self.assertFalse(copy.raffle_ids)
        self.assertFalse(copy.env.context.get("ewp_no_raffle_fill"))

    def test_form_proposes_the_raffles_and_remembers_a_removal(self):
        first = self._raffle("First", self.first_day_event)
        friday = self._raffle(
            "Friday draw", self.two_day_event, "2031-06-10 17:00:00"
        )
        with Form(self.env["event.webapp"]) as form:
            form.name = "Fill form day"
            form.date_start = DAY1[0]
            form.date_end = DAY1[1]
            form.event_ids.add(self.first_day_event)
            self.assertEqual(self._listed(form), first.ids)
            form.raffle_ids.remove(id=first.id)
            form.event_ids.add(self.two_day_event)
            # First is not proposed again in the same edit.
            self.assertEqual(self._listed(form), friday.ids)
        day = form.record
        self.assertEqual(day.raffle_ids, friday)
        # On a saved day, the form proposes the raffles of a new event.
        day.raffle_ids = [Command.clear()]
        with Form(day) as form:
            form.event_ids.add(self.second_day_event)
            form.date_end = DAY2[1]
            self.assertFalse(self._listed(form))
            late = self._raffle(
                "Saturday draw", self.second_day_event, "2031-06-11 12:00:00"
            )
            form.date_start = "2031-06-10 07:00:00"
            self.assertEqual(self._listed(form), late.ids)
        self.assertEqual(day.raffle_ids, late)

    def test_manager_adds_only_the_raffles_it_may_read(self):
        """The candidates are searched as superuser, the write runs as the
        user: a raffle of a company the user is not in stays off."""
        other_company = self.env["res.company"].create(
            {"name": "Fill Other Company"}
        )
        mine = self._raffle("Mine", self.first_day_event)
        theirs = self._raffle(
            "Theirs", self.first_day_event, company_id=other_company.id
        )
        manager = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Fill Manager Tester",
                    "login": "ewp_fill_manager_tester",
                    "groups_id": [Command.set([self.env.ref(MANAGER).id])],
                }
            )
        )
        day = self._day(DAY1).with_user(manager)
        day.event_ids = [Command.link(self.first_day_event.id)]
        self.assertEqual(day.sudo().raffle_ids, mine)
        self.assertNotIn(theirs, day.sudo().raffle_ids)
