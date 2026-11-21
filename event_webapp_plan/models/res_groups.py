# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Room groups of the event web app in res.groups.

The access groups of the rooms live in the category Event Web App Rooms:
the user form shows that category in debug mode only, like the technical
groups, and a room group that still authorizes a channel cannot be deleted,
since Odoo then empties the authorized group of the channel and the record
rule `ir_rule_discuss_channel_all` lets everybody read it.

write() on the `users` of a group takes the room groups of the Moderator
role back from the users it removes from that role (see res_users.py).
"""

from odoo import _, api, models
from odoo.exceptions import UserError

from .event_webapp_room import MODERATOR_GROUP, ROOM_CATEGORY


class ResGroups(models.Model):
    _inherit = "res.groups"

    def write(self, vals):
        if "users" not in vals:
            return super().write(vals)
        group = self.env.ref(MODERATOR_GROUP, raise_if_not_found=False)
        if not group:
            return super().write(vals)
        group = group.sudo().with_context(active_test=False)
        moderators = group.users
        result = super().write(vals)
        group.invalidate_recordset(["users"])
        (moderators - group.users)._ewp_drop_role_room_groups()
        return result

    def _get_hidden_extra_categories(self):
        return super()._get_hidden_extra_categories() + [ROOM_CATEGORY]

    @api.ondelete(at_uninstall=False)
    def _unlink_except_ewp_room_access(self):
        category = self.env.ref(ROOM_CATEGORY, raise_if_not_found=False)
        groups = self.filtered(
            lambda g: category and g.category_id == category
        )
        if not groups:
            return
        rooms = (
            self.env["event.webapp.room"]
            .sudo()
            .search([("access_group_id", "in", groups.ids)])
        )
        # Archived channels count too: unarchived later, they would be
        # public.
        channels = (
            self.env["discuss.channel"]
            .sudo()
            .with_context(active_test=False)
            .search([("group_public_id", "in", groups.ids)])
        )
        used = rooms.access_group_id | channels.group_public_id
        if used:
            raise UserError(
                _(
                    "The group %(groups)s gives access to the chat of an "
                    "event web app room. Deleting it would open that chat "
                    "to everybody, anonymous visitors included.",
                    groups=", ".join(used.mapped("name")),
                )
            )
