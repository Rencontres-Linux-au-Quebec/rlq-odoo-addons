# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Display preferences of the event web app, stored on the user.

Both fields are restricted to the Settings group (groups=), so nobody
else reads them or searches on them on another user's record: a text-only
preference says something about the sight of the person. They also belong
to SELF_READABLE_FIELDS and SELF_WRITEABLE_FIELDS, which switch to sudo on
the user's own record: a user, portal users included, reads and writes
them there, and only there. The preferences thereby follow the user from
one device to another.

The fields have a prefetch group of their own: reading one of them on
one's own record then fetches that field alone, which the sudo switch
covers, and never the other fields of the user that it does not cover.

ewp_motion takes one of MOTION_MODES: "auto" follows the setting of the
device (prefers-reduced-motion), "on" shows the animations even when the
device asks for less motion (an explicit choice of the user), "off" stops
them all. An empty value reads as "auto". migrate_reduce_motion() turns
the boolean ewp_reduce_motion of the versions before 18.0.1.4.0 into it.

Room groups of the role. The Moderator group implies every room group,
and Odoo never takes an implied group back from a user who leaves the
implying group. write() of res.users and of res.groups (see res_groups.py)
therefore call `_ewp_drop_role_room_groups()` for every user who leaves
the Moderator role: it removes the room groups they hold, except those
recorded in `ewp_room_visit_group_ids`, the room groups that a visit gave
them while outside the role (event.webapp.room._ewp_grant_access()).
backfill_room_visits() records the visits of a database installed before
that field.
"""

from odoo import Command, fields, models

from odoo.addons.base.models.res_users import is_reified_group

from .event_webapp_room import MODERATOR_GROUP, ROOM_CATEGORY

EWP_PREFERENCE_FIELDS = ["ewp_text_only", "ewp_motion"]
# Group allowed to read the preferences of other users.
EWP_PREFERENCE_GROUPS = "base.group_system"
MOTION_MODES = ("auto", "on", "off")
MOTION_DEFAULT = "auto"


def migrate_reduce_motion(cr):
    """Copy the boolean column ewp_reduce_motion of res_users into the
    column ewp_motion, created when missing: true gives "off", false or
    empty gives "auto". Rows that already have an ewp_motion keep it.
    Does nothing without the old column. Returns the number of rows
    written."""
    cr.execute(
        "SELECT 1 FROM information_schema.columns"
        " WHERE table_name = 'res_users'"
        " AND column_name = 'ewp_reduce_motion'"
    )
    if not cr.fetchone():
        return 0
    cr.execute(
        "ALTER TABLE res_users ADD COLUMN IF NOT EXISTS ewp_motion varchar"
    )
    cr.execute(
        "UPDATE res_users SET ewp_motion = CASE WHEN ewp_reduce_motion"
        " THEN 'off' ELSE 'auto' END WHERE ewp_motion IS NULL"
    )
    return cr.rowcount


def backfill_room_visits(cr):
    """Record as visited, for each user outside the Moderator group, every
    room group they hold: outside the role, a room group comes from a
    visit. Rows already recorded stay. Returns the number of rows
    added."""
    cr.execute(
        "SELECT res_id FROM ir_model_data"
        " WHERE module = 'event_webapp_plan'"
        " AND name = 'group_event_webapp_moderator'"
    )
    row = cr.fetchone()
    if not row:
        return 0
    cr.execute(
        """
        INSERT INTO res_users_ewp_room_visit_rel (user_id, group_id)
        SELECT DISTINCT gu.uid, gu.gid
          FROM event_webapp_room room
          JOIN res_groups_users_rel gu ON gu.gid = room.access_group_id
         WHERE NOT EXISTS (
                SELECT 1 FROM res_groups_users_rel moderator
                 WHERE moderator.uid = gu.uid AND moderator.gid = %s
               )
        ON CONFLICT DO NOTHING
        """,
        (row[0],),
    )
    return cr.rowcount


class ResUsers(models.Model):
    _inherit = "res.users"

    ewp_text_only = fields.Boolean(
        string="Event web app: text-only mode",
        groups=EWP_PREFERENCE_GROUPS,
        prefetch="ewp_preferences",
        help="The event web app shows its content as linear text: no site "
        "plan image, no animation and no decorative image. The rooms stay "
        "a list of links and the video conference opens on demand.",
    )
    ewp_motion = fields.Selection(
        [
            ("auto", "Follow the device"),
            ("on", "On"),
            ("off", "Off"),
        ],
        string="Event web app: animations",
        default=MOTION_DEFAULT,
        groups=EWP_PREFERENCE_GROUPS,
        prefetch="ewp_preferences",
        help="Follow the device: the event web app shows its animations "
        "unless the device asks for less motion. On: it shows them even "
        "then. Off: it stops every animation and no longer replaces the "
        "raffle results on its own.",
    )

    ewp_room_visit_group_ids = fields.Many2many(
        "res.groups",
        "res_users_ewp_room_visit_rel",
        "user_id",
        "group_id",
        string="Event web app: rooms entered",
        groups="base.group_system",
        readonly=True,
        copy=False,
        help="Room groups given by a visit of the room page outside the "
        "Moderator role. They stay when the user leaves that role; the "
        "other room groups go.",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + EWP_PREFERENCE_FIELDS

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + EWP_PREFERENCE_FIELDS

    def _ewp_motion_mode(self):
        """Animation mode of the user (one of MOTION_MODES), "auto" when
        the field is empty. Read on one's own record, or as superuser."""
        self.ensure_one()
        mode = self.ewp_motion
        return mode if mode in MOTION_MODES else MOTION_DEFAULT

    def write(self, vals):
        if not any(
            key == "groups_id" or is_reified_group(key) for key in vals
        ):
            return super().write(vals)
        moderators = self._ewp_moderators()
        result = super().write(vals)
        (moderators - self._ewp_moderators())._ewp_drop_role_room_groups()
        return result

    def _ewp_moderators(self):
        """Users of `self` in the Moderator group, read with sudo; empty
        while the group does not exist (module installation)."""
        group = self.env.ref(MODERATOR_GROUP, raise_if_not_found=False)
        if not group:
            return self.browse()
        return self.sudo().filtered(lambda user: group in user.groups_id)

    def _ewp_drop_role_room_groups(self):
        """Remove from each user of `self` the room groups they hold, except
        the visits recorded in `ewp_room_visit_group_ids`. Called for users
        who left the Moderator role: their other room groups came from the
        implication of that role. A room group that another group of the
        user implies comes back with it (res.users adds the implied groups
        after each write)."""
        category = self.env.ref(ROOM_CATEGORY, raise_if_not_found=False)
        if not category:
            return
        for user in self.sudo():
            groups = user.groups_id.filtered(
                lambda group: group.category_id == category
            )
            groups -= user.ewp_room_visit_group_ids
            if groups:
                user.write(
                    {"groups_id": [Command.unlink(g.id) for g in groups]}
                )
