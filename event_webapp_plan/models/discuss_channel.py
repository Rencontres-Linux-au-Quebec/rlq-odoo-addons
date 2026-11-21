# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Room channels of the event web app in discuss.channel.

base.group_user may write any channel it reads, and a room visitor reads
the channel of the room. write() therefore refuses, on a room channel,
the fields that decide who reads it (ROOM_CHANNEL_LOCKED_FIELDS), outside
superuser mode and the Settings group: without that, a visitor empties
the authorized group (the channel is then readable by anonymous visitors
at /discuss/channel/<id>), sets another group or archives the channel
(everybody else loses it), or subscribes whole groups to it. Odoo already
refuses a change of channel_type or parent_channel_id to everybody.

A room channel is a channel linked to a room, or restricted to a room
group: the channel of a deleted room keeps that group (see res.groups),
and stays locked.
"""

from odoo import _, models
from odoo.exceptions import AccessError

ROOM_CATEGORY = "event_webapp_plan.module_category_event_webapp_room"
ROOM_CHANNEL_LOCKED_FIELDS = frozenset(
    ("group_public_id", "group_ids", "active")
)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _ewp_room_channels(self):
        """Channels of `self` linked to a room or restricted to a room
        group, read with sudo."""
        channels = self.sudo().with_context(active_test=False)
        category = self.env.ref(ROOM_CATEGORY, raise_if_not_found=False)
        linked = (
            self.env["event.webapp.room"]
            .sudo()
            .search([("channel_id", "in", self.ids)])
            .channel_id
        )
        return channels.filtered(
            lambda c: c in linked
            or (category and c.group_public_id.category_id == category)
        )

    def write(self, vals):
        if (
            ROOM_CHANNEL_LOCKED_FIELDS.intersection(vals)
            and not self.env.is_system()
            and self._ewp_room_channels()
        ):
            raise AccessError(
                _(
                    "The access to the chat of an event web app room is "
                    "managed by the room: only the Settings group may "
                    "change its authorized group, its auto-subscribed "
                    "groups or archive it."
                )
            )
        return super().write(vals)
