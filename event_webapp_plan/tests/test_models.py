# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Model tests of event_webapp_plan.

Run on a disposable database:

    odoo-bin -d TEST_DB -i event_webapp_plan --test-enable \\
        --test-tags event_webapp_plan --stop-after-init

Every date is relative to the clock, and the event days already in the
database are archived in setUp (rolled back with the test), so the
selection of the default day only sees the records of the test.
"""

from datetime import timedelta

from lxml import etree
from odoo import Command, fields
from odoo.addons.base.models.res_users import name_selection_groups
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval

MODERATOR = "event_webapp_plan.group_event_webapp_moderator"
MANAGER = "event_webapp_plan.group_event_webapp_manager"
ROOM_CATEGORY = "event_webapp_plan.module_category_event_webapp_room"


@tagged("post_install", "-at_install")
class TestEventWebapp(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Webapp = cls.env["event.webapp"]
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.portal_user = Users.create(
            {
                "name": "Portal Tester",
                "login": "ewp_webapp_portal_tester",
                "groups_id": [
                    Command.set([cls.env.ref("base.group_portal").id])
                ],
            }
        )
        cls.internal_user = Users.create(
            {
                "name": "Internal Tester",
                "login": "ewp_webapp_internal_tester",
                "groups_id": [
                    Command.set([cls.env.ref("base.group_user").id])
                ],
            }
        )
        cls.moderator_user = Users.create(
            {
                "name": "Moderator Tester",
                "login": "ewp_webapp_moderator_tester",
                "groups_id": [Command.set([cls.env.ref(MODERATOR).id])],
            }
        )
        cls.manager_user = Users.create(
            {
                "name": "Room Manager Tester",
                "login": "ewp_webapp_room_manager_tester",
                "groups_id": [Command.set([cls.env.ref(MANAGER).id])],
            }
        )

    def setUp(self):
        super().setUp()
        self.Webapp.search([]).write({"active": False})
        self.now = fields.Datetime.now()

    def _webapp(self, start_hours, end_hours, **vals):
        """Event day opening and closing at hours relative to now."""
        return self.Webapp.create(
            {
                "name": vals.pop("name", "Test day"),
                "date_start": self.now + timedelta(hours=start_hours),
                "date_end": self.now + timedelta(hours=end_hours),
                **vals,
            }
        )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    def test_date_end_must_follow_date_start(self):
        with self.assertRaises(ValidationError):
            self._webapp(2, 1)
        with self.assertRaises(ValidationError):
            self._webapp(1, 1)
        webapp = self._webapp(-1, 1)
        with self.assertRaises(ValidationError):
            webapp.date_end = webapp.date_start - timedelta(minutes=1)

    def test_room_area_must_stay_inside_the_plan(self):
        webapp = self._webapp(-1, 1)
        Room = self.env["event.webapp.room"]
        base = {"webapp_id": webapp.id, "name": "Room"}
        room = Room.create(
            {
                **base,
                "pos_x": 66.67,
                "pos_y": 0,
                "pos_width": 33.33,
                "pos_height": 100,
            }
        )
        self.assertAlmostEqual(room.pos_x + room.pos_width, 100, places=2)
        for area in (
            {"pos_x": 80, "pos_width": 30},
            {"pos_y": 50, "pos_height": 50.5},
            {"pos_x": -1, "pos_width": 10},
            {"pos_width": -5},
            {"pos_height": -5},
        ):
            with self.subTest(area=area), self.assertRaises(ValidationError):
                Room.create({**base, **area})

    def test_room_rotation_is_normalised(self):
        webapp = self._webapp(-1, 1)
        Room = self.env["event.webapp.room"]
        room = Room.create(
            {
                "webapp_id": webapp.id,
                "name": "Room",
                "pos_x": 10,
                "pos_y": 10,
                "pos_width": 20,
                "pos_height": 20,
            }
        )
        self.assertEqual(room.pos_rotation, 0)
        for value, expected in (
            (270, -90),
            (-180, 180),
            (180, 180),
            (360, 0),
            (-360, 0),
            (725.5, 5.5),
            (-270, 90),
            (12.345, 12.35),
            (-179.999, 180),
        ):
            with self.subTest(value=value):
                room.pos_rotation = value
                self.assertAlmostEqual(room.pos_rotation, expected, places=2)
                created = Room.create(
                    {
                        "webapp_id": webapp.id,
                        "name": "Created",
                        "pos_rotation": value,
                    }
                )
                self.assertAlmostEqual(
                    created.pos_rotation, expected, places=2
                )
        for value in (float("nan"), float("inf"), float("-inf"), "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    room.write({"pos_rotation": value})
                with self.assertRaises(ValidationError):
                    Room.create(
                        {
                            "webapp_id": webapp.id,
                            "name": "Refused",
                            "pos_rotation": value,
                        }
                    )

    def test_turned_area_constraint_reads_the_unturned_box(self):
        """The corners of a turned area may leave the image: the constraint
        reads the box before it turns, which must stay inside."""
        webapp = self._webapp(-1, 1)
        Room = self.env["event.webapp.room"]
        base = {"webapp_id": webapp.id, "name": "Room", "pos_rotation": 45}
        # A full-size box turned by 45 degrees has its corners far outside
        # the image, and is accepted.
        room = Room.create(
            {
                **base,
                "pos_x": 0,
                "pos_y": 0,
                "pos_width": 100,
                "pos_height": 100,
            }
        )
        self.assertEqual(room.pos_rotation, 45)
        with self.assertRaises(ValidationError):
            Room.create(
                {
                    **base,
                    "pos_x": 80,
                    "pos_y": 0,
                    "pos_width": 30,
                    "pos_height": 10,
                }
            )

    def test_copy_keeps_the_rotation_of_the_areas(self):
        webapp = self._webapp(-1, 1, name="Day")
        webapp.room_ids = [
            Command.create(
                {
                    "name": "Hall",
                    "pos_x": 10,
                    "pos_y": 20,
                    "pos_width": 30,
                    "pos_height": 15,
                    "pos_rotation": -37.5,
                }
            )
        ]
        copy = webapp.copy()
        self.assertEqual(copy.room_ids.pos_rotation, -37.5)
        self.assertEqual(copy.room_ids.pos_width, 30)
        self.assertEqual(webapp.room_ids.copy().pos_rotation, -37.5)

    # ------------------------------------------------------------------
    # Chat channel of a room
    # ------------------------------------------------------------------

    def _channel_readers(self, channel):
        """Logins of the test users who can read ``channel``."""
        users = (
            self.env.ref("base.public_user")
            | self.portal_user
            | self.internal_user
            | self.moderator_user
        )
        return {
            user.login
            for user in users
            if channel.with_user(user).has_access("read")
        }

    def test_room_channel_is_restricted_to_its_room_group(self):
        webapp = self._webapp(-1, 1, name="Day")
        webapp.room_ids = [
            Command.create({"name": "Hall"}),
            Command.create({"name": "Lab"}),
        ]
        hall, lab = webapp.room_ids
        group = hall.access_group_id
        channel = hall.channel_id
        self.assertEqual(len(group), 1)
        self.assertEqual(group.name, "Day - Hall")
        self.assertEqual(group.category_id, self.env.ref(ROOM_CATEGORY))
        self.assertFalse(group.implied_ids)
        self.assertNotEqual(group, lab.access_group_id)
        self.assertIn(group, self.env.ref(MODERATOR).implied_ids)
        self.assertEqual(channel.channel_type, "channel")
        self.assertEqual(channel.group_public_id, group)
        self.assertEqual(channel.name, "Day - Hall")
        # Only the moderators read the chat, through their implied groups,
        # before anybody entered the room.
        self.assertIn(group, self.moderator_user.groups_id)
        self.assertEqual(
            self._channel_readers(channel), {self.moderator_user.login}
        )
        self.portal_user.groups_id = [Command.link(group.id)]
        self.assertTrue(self.portal_user.share)
        self.assertEqual(
            self._channel_readers(channel),
            {self.moderator_user.login, self.portal_user.login},
        )
        self.assertFalse(
            lab.channel_id.with_user(self.portal_user).has_access("read")
        )

        hall.name = "Main hall"
        self.assertEqual(channel.name, "Day - Main hall")
        self.assertEqual(group.name, "Day - Main hall")
        webapp.name = "First day"
        self.assertEqual(channel.name, "First day - Main hall")
        self.assertEqual(group.name, "First day - Main hall")

    def test_moderator_created_later_reads_every_room_chat(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Hall"})]
        moderator = self.env["res.users"].create(
            {
                "name": "Late Moderator Tester",
                "login": "ewp_webapp_late_moderator_tester",
                "groups_id": [Command.set([self.env.ref(MODERATOR).id])],
            }
        )
        self.assertIn(webapp.room_ids.access_group_id, moderator.groups_id)
        self.assertTrue(
            webapp.room_ids.channel_id.with_user(moderator).has_access("read")
        )

    def _room_groups(self, user):
        """Room groups held by `user`, those of the days already in the
        database included."""
        category = self.env.ref(ROOM_CATEGORY)
        return user.groups_id.filtered(lambda g: g.category_id == category)

    def test_former_moderator_keeps_only_the_rooms_entered(self):
        """Res.users keeps an implied group after its implying group goes:
        a user who leaves the Moderator role loses the room groups of the
        role, and keeps those that a room visit gave them."""
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [
            Command.create({"name": "Hall"}),
            Command.create({"name": "Lab"}),
        ]
        hall, lab = webapp.room_ids
        Users = self.env["res.users"].with_context(no_reset_password=True)
        user = Users.create(
            {
                "name": "Promoted Tester",
                "login": "ewp_webapp_promoted_tester",
                "groups_id": [
                    Command.set([self.env.ref("base.group_user").id])
                ],
            }
        )
        self.assertTrue(hall.with_user(user)._ewp_grant_access())
        moderator = self.env.ref(MODERATOR)
        user.groups_id = [Command.link(moderator.id)]
        both = hall.access_group_id | lab.access_group_id
        self.assertEqual(self._room_groups(user) & both, both)
        # A visit as a moderator gives nothing of its own.
        self.assertTrue(lab.with_user(user)._ewp_grant_access())
        user.groups_id = [Command.unlink(moderator.id)]
        self.assertFalse(user.has_group(MODERATOR))
        self.assertEqual(self._room_groups(user), hall.access_group_id)
        self.assertTrue(hall.channel_id.with_user(user).has_access("read"))
        self.assertFalse(lab.channel_id.with_user(user).has_access("read"))

        # Removed from the group form.
        user.groups_id = [Command.link(moderator.id)]
        self.assertIn(lab.access_group_id, user.groups_id)
        moderator.users = [Command.unlink(user.id)]
        self.assertEqual(self._room_groups(user), hall.access_group_id)

        # Role cleared in the user form (selection of the application),
        # for an Administrator, who never entered a room.
        manager = self.env.ref(MANAGER)
        field = name_selection_groups([moderator.id, manager.id])
        self.assertIn(field, self.env["res.users"].fields_get([field]))
        self.assertEqual(self._room_groups(self.manager_user) & both, both)
        self.manager_user.write({field: False})
        self.assertFalse(self.manager_user.has_group(MODERATOR))
        self.assertFalse(self._room_groups(self.manager_user))

        # A moderator still reads every room chat while in the role.
        self.assertTrue(
            lab.channel_id.with_user(self.moderator_user).has_access("read")
        )

    def test_room_visits_are_recorded_for_existing_holders(self):
        """backfill_room_visits() records as a visit every room group held
        by a user outside the Moderator role, the state of a database
        installed before the record of the visits."""
        from odoo.addons.event_webapp_plan.models.res_users import (
            backfill_room_visits,
        )

        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Hall"})]
        group = webapp.room_ids.access_group_id
        self.portal_user.groups_id = [Command.link(group.id)]
        self.assertFalse(self.portal_user.ewp_room_visit_group_ids)
        backfill_room_visits(self.env.cr)
        self.env.invalidate_all()
        self.assertEqual(self.portal_user.ewp_room_visit_group_ids, group)
        self.assertFalse(self.moderator_user.ewp_room_visit_group_ids)
        # Running it again adds nothing.
        backfill_room_visits(self.env.cr)
        self.env.invalidate_all()
        self.assertEqual(self.portal_user.ewp_room_visit_group_ids, group)

    def test_room_channel_must_be_a_channel_of_its_own(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [
            Command.create({"name": "Hall"}),
            Command.create({"name": "Lab"}),
        ]
        hall, lab = webapp.room_ids
        conversation = self.env["discuss.channel"].create(
            {"name": "Private conversation", "channel_type": "group"}
        )
        with self.assertRaises(ValidationError):
            hall.channel_id = conversation
        thread = hall.channel_id._create_sub_channel(name="Thread")
        with self.assertRaises(ValidationError):
            lab.channel_id = thread
        with self.assertRaises(ValidationError):
            lab.channel_id = hall.channel_id

    def test_linked_channel_gets_the_room_group(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Hall"})]
        room = webapp.room_ids
        existing = self.env["discuss.channel"].create(
            {"name": "Existing public channel", "channel_type": "channel"}
        )
        existing.group_public_id = False
        self.assertTrue(
            existing.with_user(self.env.ref("base.public_user")).has_access(
                "read"
            )
        )
        room.channel_id = existing
        self.assertEqual(existing.group_public_id, room.access_group_id)
        self.assertEqual(
            self._channel_readers(existing), {self.moderator_user.login}
        )

    def test_access_group_is_set_by_the_module_only(self):
        """The room page gives the access group to every visitor: an event
        Administrator, who is not a Settings user, cannot choose it."""
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [
            Command.create({"name": "Hall"}),
            Command.create({"name": "Lab"}),
        ]
        hall, lab = webapp.room_ids
        system = self.env.ref("base.group_system")
        Room = self.env["event.webapp.room"].with_user(self.manager_user)
        self.assertFalse(self.manager_user._is_system())
        for group in (
            system,
            self.env.ref("base.group_public"),
            lab.access_group_id,
        ):
            with self.subTest(group=group.name):
                with self.assertRaises(AccessError):
                    Room.create(
                        {
                            "webapp_id": webapp.id,
                            "name": "Elsewhere",
                            "access_group_id": group.id,
                        }
                    )
                with self.assertRaises(AccessError):
                    hall.with_user(self.manager_user).write(
                        {"access_group_id": group.id}
                    )
        # A default fills the field the values leave out: the context of
        # the call, or the group of a deleted room, which stays in the
        # room category.
        webapp.room_ids = [Command.create({"name": "Gone"})]
        gone = webapp.room_ids - hall - lab
        orphan = gone.access_group_id
        gone.unlink()
        for group in (system, orphan):
            with self.subTest(default=group.name):
                with self.assertRaises(AccessError):
                    Room.with_context(default_access_group_id=group.id).create(
                        {"webapp_id": webapp.id, "name": "Default group"}
                    )
                with self.assertRaises(AccessError):
                    webapp.with_user(self.manager_user).with_context(
                        default_access_group_id=group.id
                    ).write(
                        {"room_ids": [Command.create({"name": "Default"})]}
                    )
        self.assertEqual(webapp.room_ids, hall | lab)
        # The Administrator still creates and edits rooms.
        room = Room.create({"webapp_id": webapp.id, "name": "Workshop"})
        room.name = "Main workshop"
        self.assertEqual(
            room.access_group_id.category_id, self.env.ref(ROOM_CATEGORY)
        )

        # A group that is not a room group of its own, set in superuser
        # mode, is never given to a visitor nor put on the channel.
        own_group = hall.access_group_id
        for group in (system, lab.access_group_id):
            with self.subTest(granted=group.name):
                hall.access_group_id = group
                self.assertFalse(hall._ewp_is_room_group())
                self.assertFalse(
                    hall.with_user(self.internal_user)._ewp_grant_access()
                )
                self.assertNotIn(group, self.internal_user.groups_id)
                hall._ewp_ensure_access(create_channel=False)
                self.assertEqual(hall.channel_id.group_public_id, own_group)
        hall.access_group_id = own_group
        self.assertTrue(hall._ewp_is_room_group())
        self.assertTrue(hall.with_user(self.internal_user)._ewp_grant_access())
        self.assertIn(own_group, self.internal_user.groups_id)
        self.assertFalse(self.internal_user._is_system())

    def test_linked_channel_restricted_to_another_group_is_refused(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [
            Command.create({"name": "Hall"}),
            Command.create({"name": "Lab"}),
        ]
        hall, lab = webapp.room_ids
        restricted_group = self.env["res.groups"].create(
            {"name": "Restricted channel test group"}
        )
        restricted = self.env["discuss.channel"].create(
            {
                "name": "Restricted test channel",
                "channel_type": "channel",
                "group_public_id": restricted_group.id,
            }
        )
        employees = self.env["discuss.channel"].create(
            {"name": "Employees test channel", "channel_type": "channel"}
        )
        self.assertEqual(
            employees.group_public_id, self.env.ref("base.group_user")
        )
        orphan = lab.channel_id
        lab.channel_id = False
        for channel in (restricted, employees, orphan):
            with self.subTest(channel=channel.name):
                group = channel.group_public_id
                with self.assertRaises(ValidationError):
                    hall.with_user(self.manager_user).channel_id = channel
                self.assertEqual(channel.group_public_id, group)
        # Its own channel, or a channel open to everybody, can be linked.
        own = hall.channel_id
        hall.with_user(self.manager_user).channel_id = False
        hall.with_user(self.manager_user).channel_id = own
        self.assertEqual(own.group_public_id, hall.access_group_id)
        # The Settings group may take a channel over.
        hall.channel_id = restricted
        self.assertEqual(restricted.group_public_id, hall.access_group_id)

    def test_copy_gives_each_room_its_own_channel_and_group(self):
        webapp = self._webapp(-1, 1, name="Day")
        webapp.room_ids = [Command.create({"name": "Hall"})]
        original = webapp.room_ids.channel_id
        original_group = webapp.room_ids.access_group_id
        self.portal_user.groups_id = [Command.link(original_group.id)]
        copy = webapp.copy()
        self.assertEqual(copy.room_ids.name, "Hall")
        copy_group = copy.room_ids.access_group_id
        self.assertTrue(copy.room_ids.channel_id)
        self.assertNotEqual(copy.room_ids.channel_id, original)
        self.assertTrue(copy_group)
        self.assertNotEqual(copy_group, original_group)
        self.assertEqual(copy.room_ids.channel_id.group_public_id, copy_group)
        self.assertNotIn(copy_group, self.portal_user.groups_id)
        # The copy keeps the name of the day: its group name, unique in its
        # category, carries the id of the room.
        self.assertEqual(copy_group.name, "Day - Hall (%s)" % copy.room_ids.id)
        copy.name = "Next day"
        self.assertEqual(copy.room_ids.channel_id.name, "Next day - Hall")
        self.assertEqual(copy_group.name, "Next day - Hall")
        self.assertEqual(original.name, "Day - Hall")
        self.assertEqual(original_group.name, "Day - Hall")

    def test_create_missing_channels(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Lab"})]
        room = webapp.room_ids
        room.channel_id = False
        webapp.action_create_missing_channels()
        self.assertTrue(room.channel_id)
        self.assertEqual(room.channel_id.group_public_id, room.access_group_id)
        existing = room.channel_id
        group = room.access_group_id
        webapp.action_create_missing_channels()
        self.assertEqual(room.channel_id, existing)
        self.assertEqual(room.access_group_id, group)

    def test_create_missing_channels_needs_the_write_right(self):
        """The action creates channels and groups with sudo: a moderator,
        who only reads the days, cannot run it through RPC."""
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Lab"})]
        room = webapp.room_ids
        room.channel_id = False
        with self.assertRaises(AccessError):
            webapp.with_user(
                self.moderator_user
            ).action_create_missing_channels()
        self.assertFalse(room.channel_id)
        webapp.with_user(self.manager_user).action_create_missing_channels()
        self.assertTrue(room.channel_id)

    def test_room_channel_access_is_locked(self):
        """A room visitor is a member of an internal channel, which
        base.group_user may write: the fields that decide who reads the
        channel stay out of reach of everybody but the Settings group,
        also once the room is deleted."""
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Hall"})]
        room = webapp.room_ids
        channel = room.channel_id
        group = room.access_group_id
        self.assertTrue(room.with_user(self.internal_user)._ewp_grant_access())
        other = self.env["res.groups"].create({"name": "Other test group"})
        changes = (
            {"group_public_id": False},
            {"group_public_id": other.id},
            {"group_ids": [Command.link(self.env.ref("base.group_user").id)]},
            {"active": False},
        )
        for user in (self.internal_user, self.manager_user):
            for vals in changes:
                with self.subTest(user=user.login, vals=vals):
                    with self.assertRaises(AccessError):
                        channel.with_user(user).write(vals)
                    self.assertEqual(channel.group_public_id, group)
                    self.assertFalse(channel.group_ids)
                    self.assertTrue(channel.active)
                # A change that went through would hide the channel from
                # the next caller: the next subtest starts from the room
                # state.
                channel.write(
                    {
                        "group_public_id": group.id,
                        "group_ids": [Command.clear()],
                        "active": True,
                    }
                )
        with self.assertRaises(AccessError):
            channel.with_user(self.internal_user).action_archive()
        # The rest of the channel stays editable by its members.
        channel.with_user(self.internal_user).description = "Hall chat"
        room.unlink()
        with self.assertRaises(AccessError):
            channel.with_user(self.internal_user).group_public_id = False
        # The Settings group still may.
        admin = self.env.ref("base.user_admin")
        channel.with_user(admin).group_public_id = other
        self.assertEqual(channel.group_public_id, other)

    def test_deleted_room_leaves_its_channel_restricted(self):
        webapp = self._webapp(-1, 1)
        webapp.room_ids = [Command.create({"name": "Hall"})]
        room = webapp.room_ids
        group = room.access_group_id
        channel = room.channel_id
        self.portal_user.groups_id = [Command.link(group.id)]
        # A group that authorizes a room chat cannot be deleted.
        with self.assertRaises(UserError):
            group.unlink()
        room.unlink()
        self.assertTrue(group.exists())
        self.assertEqual(channel.group_public_id, group)
        self.assertEqual(
            self._channel_readers(channel),
            {self.moderator_user.login, self.portal_user.login},
        )
        with self.assertRaises(UserError):
            group.unlink()
        # The database cascade of a deleted day does the same.
        webapp.room_ids = [Command.create({"name": "Lab"})]
        lab_channel = webapp.room_ids.channel_id
        webapp.unlink()
        self.assertTrue(lab_channel.group_public_id)
        self.assertFalse(
            lab_channel.with_user(self.env.ref("base.public_user")).has_access(
                "read"
            )
        )

    # ------------------------------------------------------------------
    # Default day of /webapp_event
    # ------------------------------------------------------------------

    def test_find_default_prefers_open_then_upcoming_then_ended(self):
        recent_ended = self._webapp(-5, -2, name="Recent ended")
        self._webapp(-50, -48, name="Old ended")
        soon = self._webapp(3, 5, name="Soon")
        self._webapp(24, 30, name="Later")
        open_first = self._webapp(-3, 2, name="Open first")
        open_second = self._webapp(-1, 4, name="Open second")
        self._webapp(-10, 10, name="Archived open", active=False)

        self.assertEqual(self.Webapp._ewp_find_default(), open_first)

        (open_first | open_second).active = False
        self.assertEqual(self.Webapp._ewp_find_default(), soon)

        self.Webapp.search([("date_start", ">", self.now)]).active = False
        self.assertEqual(self.Webapp._ewp_find_default(), recent_ended)

        self.Webapp.search([]).active = False
        self.assertFalse(self.Webapp._ewp_find_default())

    def test_find_default_works_for_a_portal_user(self):
        open_day = self._webapp(-1, 1)
        found = self.Webapp.with_user(self.portal_user)._ewp_find_default()
        self.assertEqual(found, open_day)

    # ------------------------------------------------------------------
    # Who may see the content
    # ------------------------------------------------------------------

    def test_can_view_portal_user_only_inside_the_window(self):
        open_day = self._webapp(-1, 1)
        future_day = self._webapp(2, 4)
        ended_day = self._webapp(-4, -2)
        for user in (self.portal_user, self.internal_user):
            with self.subTest(user=user.login):
                self.assertTrue(open_day.with_user(user)._ewp_can_view())
                self.assertFalse(future_day.with_user(user)._ewp_can_view())
                self.assertFalse(ended_day.with_user(user)._ewp_can_view())

    def test_can_view_moderator_and_manager_at_any_time(self):
        future_day = self._webapp(2, 4)
        ended_day = self._webapp(-4, -2)
        manager = self.env.ref("base.user_admin")
        self.assertTrue(manager.has_group(MANAGER))
        for user in (self.moderator_user, manager):
            with self.subTest(user=user.login):
                self.assertTrue(future_day.with_user(user)._ewp_can_view())
                self.assertTrue(ended_day.with_user(user)._ewp_can_view())
        self.assertTrue(
            self.Webapp.with_user(self.moderator_user)._ewp_is_moderator()
        )
        self.assertFalse(
            self.Webapp.with_user(self.portal_user)._ewp_is_moderator()
        )

    # ------------------------------------------------------------------
    # Room group: access to the room chats
    # ------------------------------------------------------------------

    def test_grant_access_only_inside_the_window(self):
        future_day = self._webapp(2, 4)
        future_day.room_ids = [Command.create({"name": "Hall"})]
        future_room = future_day.room_ids
        self.assertFalse(
            future_room.with_user(self.portal_user)._ewp_grant_access()
        )
        self.assertNotIn(
            future_room.access_group_id, self.portal_user.groups_id
        )
        open_day = self._webapp(-1, 1)
        open_day.room_ids = [Command.create({"name": "Hall"})]
        room = open_day.room_ids
        public = self.env.ref("base.public_user")
        self.assertFalse(room.with_user(public)._ewp_grant_access())
        self.assertNotIn(room.access_group_id, public.groups_id)
        self.assertTrue(room.with_user(self.portal_user)._ewp_grant_access())
        self.assertIn(room.access_group_id, self.portal_user.groups_id)
        self.assertTrue(self.portal_user.share)
        # A moderator holds the group already and may enter at any time.
        self.assertTrue(
            future_room.with_user(self.moderator_user)._ewp_grant_access()
        )

    def test_room_access_is_kept_once_the_day_is_over(self):
        open_day = self._webapp(-1, 1)
        open_day.room_ids = [Command.create({"name": "Hall"})]
        room = open_day.room_ids
        room.with_user(self.portal_user)._ewp_grant_access()
        open_day.date_end = self.now - timedelta(minutes=1)
        open_day.active = False
        self.assertIn(room.access_group_id, self.portal_user.groups_id)
        self.assertTrue(
            room.channel_id.with_user(self.portal_user).has_access("read")
        )
        # No scheduled action withdraws the group.
        self.assertFalse(
            self.env["ir.cron"].search_count(
                [("model_id.model", "=", "event.webapp")]
            )
        )

    # ------------------------------------------------------------------
    # Form of the day, used with the module's own groups only
    # ------------------------------------------------------------------

    def test_manager_can_list_the_raffles_and_events_to_pick(self):
        """The "Add a line" dialogs of the Raffles and Events tabs list
        records with the view the field context names, else the default
        list. A manager without any Events right must read all its fields,
        on a raffle that has participants and draws."""
        manager = self.env["res.users"].create(
            {
                "name": "Manager Tester",
                "login": "ewp_webapp_manager_tester",
                "groups_id": [Command.set([self.env.ref(MANAGER).id])],
            }
        )
        self.assertFalse(manager.has_group("event.group_event_user"))
        event = self.env["event.event"].create(
            {
                "name": "Pick Test Event",
                "date_begin": self.now,
                "date_end": self.now + timedelta(hours=2),
            }
        )
        self.env["event.raffle"].create(
            {
                "name": "Pick Test Raffle",
                "event_id": event.id,
                "participant_ids": [Command.create({"name": "Ada Tester"})],
                "draw_ids": [Command.create({"sequence": 1, "prize": "Pen"})],
            }
        )
        form = self.Webapp.with_user(manager).get_view(view_type="form")
        arch = etree.fromstring(form["arch"])
        for field_name in ("raffle_ids", "event_ids"):
            with self.subTest(field=field_name):
                node = arch.xpath("//field[@name='%s']" % field_name)[0]
                context = safe_eval(node.get("context") or "{}")
                comodel = self.Webapp._fields[field_name].comodel_name
                Model = (
                    self.env[comodel].with_user(manager).with_context(context)
                )
                view = Model.get_views([(False, "list")])["views"]["list"]
                names = etree.fromstring(view["arch"]).xpath("//field/@name")
                spec = {
                    name: (
                        {"fields": {"display_name": {}}}
                        if Model._fields[name].type == "many2one"
                        else {}
                    )
                    for name in names
                }
                result = Model.web_search_read([], spec)
                self.assertTrue(result["length"])

    def test_is_open_and_url(self):
        open_day = self._webapp(-1, 1)
        self.assertTrue(open_day.is_open)
        self.assertFalse(self._webapp(1, 2).is_open)
        self.assertEqual(open_day.webapp_url, "/webapp_event/%d" % open_day.id)
