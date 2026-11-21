# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Clickable room of the site plan, with its Discuss channel and its group.

The area of a room is a rectangle in PERCENT of the plan image (origin at
the top left corner), so it follows the image whatever its displayed size.
A room without area (width or height 0) is listed but not drawn. The
rectangle turns by `pos_rotation` degrees, clockwise, around its centre;
the constraint on the area applies to the rectangle before it turns, so
the corners of a turned area may leave the image, which the pages clip.

Each room owns an access group (category Event Web App Rooms) that is the
authorized group of its channel: the record rule
`ir_rule_discuss_channel_all` lets only the members of that group read the
channel, through the web app or /discuss/channel/<id>. The room page gives
the group to the logged-in visitor allowed to see the day, and nothing
takes it back: the chat stays readable for them once the day is over. The
Moderator group implies every room group; a user who leaves that role
loses the room groups they did not get from a visit (res_users.py).

Only the module sets the access group of a room, with sudo: create() and
write() refuse `access_group_id` from any other caller, since the room page
gives that group to every visitor. create() checks its values once the
defaults are added (`_prepare_create_values()`), so a default from the
context or from ir.default passes the same checks as a given value. A
group is used only when it is a room group of its own
(`_ewp_is_room_group()`). A channel linked by hand must have no authorized
group or the group of the room already: taking over a channel restricted to
another group is reserved to the Settings group.

Deleting a room keeps its group and its channel, still linked together: the
channel never loses its authorized group, so it never becomes public, and
the people who took part keep its history. A day deleted by the database
cascade leaves its rooms' groups and channels in the same state.

A room may also show a BigBlueButton conference, in this order (see
`_ewp_bbb_target()`): the meeting `bbb_meeting_id` through the server API
when the server URL and its shared secret are set in the settings, else
the page `bbb_room_url`, in an iframe when its headers allow it
(`bbb_frameable`), else behind a button that opens it in a new tab. The
API joins an existing meeting only: it never creates one. Only the
Settings group, which holds the shared secret, lists the meetings of the
server and sets a new meeting ID on a room
(`_ewp_check_bbb_meeting_vals()`).

The display mode of the settings (`_ewp_bbb_display()`) decides between
the iframe and the button: "auto" embeds the conference only when its
server is on the same site as the room page (bbb_client.same_site()),
since a browser refuses the session cookie of the client in a frame from
another site; "frame" always embeds it, "tab" never does.
"""

import logging
import math

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare

from . import bbb_client

_logger = logging.getLogger(__name__)

DEFAULT_COLOR = "#2A9D8F"
MODERATOR_GROUP = "event_webapp_plan.group_event_webapp_moderator"
ROOM_CATEGORY = "event_webapp_plan.module_category_event_webapp_room"
PARAM_BBB_URL = "event_webapp_plan.bbb_server_url"
PARAM_BBB_SECRET = "event_webapp_plan.bbb_secret"
PARAM_BBB_DISPLAY = "event_webapp_plan.bbb_display"
BBB_DISPLAY_MODES = ("auto", "frame", "tab")


class EventWebappRoom(models.Model):
    _name = "event.webapp.room"
    _description = "Event Web App Room"
    _order = "sequence, id"

    webapp_id = fields.Many2one(
        "event.webapp",
        string="Event day",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    color = fields.Char(
        default=DEFAULT_COLOR,
        help="Colour of the room area on the plan, as #RRGGBB.",
    )
    pos_x = fields.Float(
        string="Left (%)", digits=(6, 2), help="Percent of the image width."
    )
    pos_y = fields.Float(
        string="Top (%)", digits=(6, 2), help="Percent of the image height."
    )
    pos_width = fields.Float(
        string="Width (%)", digits=(6, 2), help="Percent of the image width."
    )
    pos_height = fields.Float(
        string="Height (%)",
        digits=(6, 2),
        help="Percent of the image height.",
    )
    pos_rotation = fields.Float(
        string="Rotation (deg)",
        digits=(6, 2),
        default=0.0,
        help="Angle of the area in degrees, clockwise around its centre, "
        "from -180 (excluded) to 180.",
    )
    channel_id = fields.Many2one(
        "discuss.channel",
        string="Chat channel",
        ondelete="set null",
        # A duplicated room gets a channel of its own from create(), never
        # the conversation and the members of the original.
        copy=False,
        help="Discuss channel embedded in the room page, open to the "
        "members of the access group of the room. Created automatically "
        "with the room.",
    )
    access_group_id = fields.Many2one(
        "res.groups",
        string="Access group",
        # A duplicated room gets a group of its own from create(): the
        # visitors of the original do not enter the copy.
        copy=False,
        readonly=True,
        ondelete="restrict",
        help="Authorized group of the chat channel. The room page gives it "
        "to every logged-in visitor of the room, and it is never taken "
        "back. Created automatically with the room.",
    )
    bbb_meeting_id = fields.Char(
        string="BBB meeting ID",
        help="Internal meetingID of the BigBlueButton meeting of the room, "
        "for instance the meeting of a Greenlight room (button Running BBB "
        "meetings of the event day). Used when the BigBlueButton server "
        "and its shared secret are set in the settings. The meeting must "
        "be started by its host: the web app never creates it. Only the "
        "Settings group chooses it; an event administrator may clear it.",
    )
    bbb_room_url = fields.Char(
        string="Conference URL",
        help="Web address of the conference (http or https), used when no "
        "meeting ID can be joined through the server. Shown in the page "
        "when its headers allow it, else opened in a new tab.",
    )
    bbb_frameable = fields.Boolean(
        string="Shown in the page",
        readonly=True,
        copy=False,
        help="The headers of the conference URL let the web app show it in "
        "the page (X-Frame-Options and Content-Security-Policy "
        "frame-ancestors). Checked when the URL changes and by the button "
        "Re-check.",
    )
    bbb_frame_checked = fields.Datetime(
        string="Checked on", readonly=True, copy=False
    )

    @api.constrains("bbb_room_url")
    def _check_bbb_room_url(self):
        for room in self:
            if room.bbb_room_url and not bbb_client.is_web_url(
                room.bbb_room_url
            ):
                raise ValidationError(
                    _(
                        "The conference URL of the room %(name)s must be an "
                        "http or https web address.",
                        name=room.name,
                    )
                )

    @api.constrains("channel_id")
    def _check_channel_type(self):
        # The room page adds every visitor to this channel with sudo: only a
        # top-level channel of type "channel" may be linked, never a private
        # group conversation, a direct chat or a sub-channel, whose access
        # follows its parent. The room then makes its group the authorized
        # group of the channel, with sudo: a channel restricted to another
        # group would move its whole history to the room visitors, so only
        # the Settings group may link one. The constraint runs before that
        # write, on the group the channel had. Read with sudo, since the
        # writer may not be a member of the channel.
        may_take_over = self.env.su or self.env.user._is_system()
        for room in self.sudo():
            channel = room.channel_id
            if not channel:
                continue
            if (
                channel.group_public_id
                and channel.group_public_id != room.access_group_id
                and not may_take_over
            ):
                raise ValidationError(
                    _(
                        "The channel %(channel)s is restricted to the group "
                        "%(group)s. Only a channel open to everybody, or "
                        "already restricted to the group of the room "
                        "%(name)s, can be linked to it.",
                        channel=channel.name,
                        group=channel.group_public_id.name,
                        name=room.name,
                    )
                )
            if channel.channel_type != "channel" or channel.parent_channel_id:
                raise ValidationError(
                    _(
                        "The chat of the room %(name)s must be a Discuss "
                        "channel, not a private conversation or a thread.",
                        name=room.name,
                    )
                )
            if self.search_count(
                [("channel_id", "=", channel.id), ("id", "!=", room.id)],
                limit=1,
            ):
                raise ValidationError(
                    _(
                        "The channel %(channel)s already serves another "
                        "room: each room needs a chat of its own.",
                        channel=channel.name,
                    )
                )

    @api.constrains("pos_x", "pos_y", "pos_width", "pos_height")
    def _check_area(self):
        # Two decimals: the precision of the stored values, so a rectangle
        # touching the right or bottom edge passes despite float rounding.
        for room in self:
            values = (room.pos_x, room.pos_y, room.pos_width, room.pos_height)
            if any(
                float_compare(v, 0.0, precision_digits=2) < 0 for v in values
            ):
                raise ValidationError(
                    _(
                        "The area of the room %(name)s cannot have a "
                        "negative position or size.",
                        name=room.name,
                    )
                )
            if (
                float_compare(
                    room.pos_x + room.pos_width, 100.0, precision_digits=2
                )
                > 0
                or float_compare(
                    room.pos_y + room.pos_height, 100.0, precision_digits=2
                )
                > 0
            ):
                raise ValidationError(
                    _(
                        "The area of the room %(name)s goes beyond the plan "
                        "image (position plus size above 100%%).",
                        name=room.name,
                    )
                )

    @api.model
    def _ewp_normalize_rotation(self, value):
        """Angle `value` in degrees brought into (-180, 180], rounded to
        two decimals: 270 gives -90, -180 gives 180, 360 gives 0. Raises
        ValidationError for a value that is not a finite number."""
        try:
            angle = float(value or 0.0)
        except (TypeError, ValueError):
            angle = math.nan
        if not math.isfinite(angle):
            raise ValidationError(
                _("The rotation of a room area must be a finite number.")
            )
        # Rounded first: a value just above -180 rounds to -180, which
        # the range below turns into 180.
        angle = round(math.fmod(angle, 360.0), 2)
        if angle <= -180.0:
            angle += 360.0
        elif angle > 180.0:
            angle -= 360.0
        # + 0.0 turns -0.0 into 0.0.
        return round(angle, 2) + 0.0

    @api.model
    def _ewp_clean_area_vals(self, vals):
        """Normalise the rotation of `vals` in place, see
        `_ewp_normalize_rotation()`."""
        if "pos_rotation" in vals:
            vals["pos_rotation"] = self._ewp_normalize_rotation(
                vals["pos_rotation"]
            )
        return vals

    @api.model
    def _ewp_clean_bbb_vals(self, vals):
        """Strip the blanks around the URL and the meeting ID."""
        for key in ("bbb_room_url", "bbb_meeting_id"):
            if isinstance(vals.get(key), str):
                vals[key] = vals[key].strip() or False
        return vals

    def _ewp_check_access_group_vals(self, vals):
        """Refuse `access_group_id` in `vals` outside superuser mode: the
        field is filled by the module, with sudo, and the room page gives
        its group to every visitor. readonly only protects the form, not
        an RPC call or an import."""
        if "access_group_id" in vals and not self.env.su:
            raise AccessError(
                _(
                    "The access group of a room is created and managed by the "
                    "room itself; it cannot be set by hand."
                )
            )

    @api.model
    def _ewp_bbb_check_meeting_rights(self):
        """Raise AccessError unless the caller belongs to the Settings
        group or runs in superuser mode. The shared secret signs any call
        on any meeting of the server, and a room meeting is joined with the
        role MODERATOR by the web app moderators: choosing the meeting of
        a room belongs to the group that holds the secret."""
        if not self.env.is_system():
            raise AccessError(
                _(
                    "Only the Settings group lists the meetings of the "
                    "BigBlueButton server and chooses the meeting of a room."
                )
            )

    @api.model
    def _ewp_check_bbb_meeting_vals(self, vals):
        """Refuse a new `bbb_meeting_id` in the cleaned `vals` outside the
        Settings group (`_ewp_bbb_check_meeting_rights()`). Emptying it is
        free, and so is a meeting ID that a room already carries, which a
        Settings user chose: a copied room or day keeps its meetings."""
        meeting_id = vals.get("bbb_meeting_id")
        if not meeting_id or self.env.is_system():
            return
        if not self.sudo().search_count(
            [("bbb_meeting_id", "=", meeting_id)], limit=1
        ):
            self._ewp_bbb_check_meeting_rights()

    @api.model
    def _prepare_create_values(self, vals_list):
        """Clean and check the values of create() once the ORM has added
        the defaults: a field left out of the values takes the context key
        `default_<field>` or an ir.default, which base.group_user records
        for itself, and is stored like a value of the caller. The checks
        of `access_group_id` and `bbb_meeting_id` therefore see every
        stored value, whatever its source."""
        result = []
        for vals in super()._prepare_create_values(vals_list):
            vals = self._ewp_clean_area_vals(
                self._ewp_clean_bbb_vals(dict(vals))
            )
            self._ewp_check_access_group_vals(vals)
            self._ewp_check_bbb_meeting_vals(vals)
            result.append(vals)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        rooms = super().create(vals_list)
        rooms._ewp_ensure_access()
        rooms.filtered("bbb_room_url")._ewp_bbb_check_frame()
        return rooms

    def write(self, vals):
        self._ewp_check_access_group_vals(vals)
        vals = self._ewp_clean_area_vals(self._ewp_clean_bbb_vals(dict(vals)))
        self._ewp_check_bbb_meeting_vals(vals)
        result = super().write(vals)
        if vals.get("channel_id"):
            self._ewp_ensure_access(create_channel=False)
        if "name" in vals:
            self._ewp_sync_names()
        if "bbb_room_url" in vals:
            self._ewp_bbb_check_frame()
        return result

    def _ewp_channel_name(self):
        """Name of the channel and of the access group: "<day> - <room>"."""
        self.ensure_one()
        return "%s - %s" % (self.webapp_id.name, self.name)

    def _ewp_group_model(self):
        """res.groups as sudo, in English. The group names are written in
        en_US only, the key that the unique index (category, name) of
        res.groups and the search below both compare."""
        return self.env["res.groups"].sudo().with_context(lang="en_US")

    def _ewp_group_name(self):
        """Name for the access group of the room. res.groups refuses two
        groups of the same name in a category, which two days of the same
        name produce, so a clash adds the id of the room to the name."""
        self.ensure_one()
        name = self._ewp_channel_name()
        category = self.env.ref(ROOM_CATEGORY)
        clash = self._ewp_group_model().search_count(
            [
                ("category_id", "=", category.id),
                ("name", "=", name),
                ("id", "!=", self.access_group_id.id),
            ],
            limit=1,
        )
        return "%s (%s)" % (name, self.id) if clash else name

    def _ewp_create_access_group(self):
        """Create the access group of each room of `self`, in the category
        of the room groups, implying nothing, so portal users can hold it.
        The Moderator group then implies it: res.groups adds an implied
        group to every current member of the implying group, so moderators
        and administrators read the chat without entering the room."""
        Groups = self._ewp_group_model()
        category = self.env.ref(ROOM_CATEGORY)
        groups = Groups
        for room in self.sudo():
            room.access_group_id = Groups.create(
                {
                    "name": room._ewp_group_name(),
                    "category_id": category.id,
                }
            )
            groups |= room.access_group_id
        if groups:
            self.env.ref(MODERATOR_GROUP).sudo().write(
                {"implied_ids": [Command.link(g.id) for g in groups]}
            )

    def _ewp_create_channel(self):
        """Create the Discuss channel of each room of `self`, restricted to
        the access group of the room. The record rule
        `ir_rule_discuss_channel_all` lets anyone read a channel of type
        "channel" without authorized group, anonymous visitors included.
        Odoo also adds the creating user as first member of the channel."""
        Channel = self.env["discuss.channel"].sudo()
        for room in self:
            room.channel_id = Channel.create(
                {
                    "name": room._ewp_channel_name(),
                    "channel_type": "channel",
                    "group_public_id": room.access_group_id.id,
                    "description": room.description or False,
                }
            )

    def _ewp_is_room_group(self):
        """True when the access group of this room is a room group of its
        own: in the category of the room groups, implying nothing, and the
        group of no other room. Any other group is never given to a visitor
        nor made the authorized group of a channel."""
        self.ensure_one()
        room = self.sudo()
        group = room.access_group_id
        if not group or group.category_id != self.env.ref(ROOM_CATEGORY):
            return False
        if group.implied_ids:
            return False
        return not room.search_count(
            [("access_group_id", "=", group.id), ("id", "!=", room.id)],
            limit=1,
        )

    def _ewp_ensure_access(self, create_channel=True):
        """Give each room of `self` its access group, and its channel when
        `create_channel` is set, then make the group the authorized group
        of the channel, also for a channel linked by hand. A room whose
        group is not a room group of its own leaves its channel as is."""
        self.filtered(
            lambda room: not room.access_group_id
        )._ewp_create_access_group()
        if create_channel:
            self.filtered(
                lambda room: not room.channel_id
            )._ewp_create_channel()
        for room in self.sudo().filtered("channel_id"):
            if room.channel_id.group_public_id == room.access_group_id:
                continue
            if not room._ewp_is_room_group():
                _logger.warning(
                    "Room %s: its access group is not a room group of its "
                    "own, its channel is left unchanged",
                    room.id,
                )
                continue
            room.channel_id.group_public_id = room.access_group_id

    def _ewp_sync_names(self):
        """Rename the channels and the access groups after their day or
        room."""
        for room in self:
            name = room._ewp_channel_name()
            channel = room.channel_id.sudo()
            if channel and channel.name != name:
                channel.name = name
            group = room.access_group_id
            if group:
                group_name = room._ewp_group_name()
                group = room._ewp_group_model().browse(group.id)
                if group.name != group_name:
                    group.name = group_name

    def _ewp_grant_access(self):
        """Give the current user the access group of this room and return
        True, when the day lets them see it (`_ewp_can_view()`) and the
        group is a room group of its own (`_ewp_is_room_group()`); never to
        the public user. The group is never withdrawn afterwards.

        Outside the Moderator role, the visit is also recorded on the user
        (`ewp_room_visit_group_ids`), so the group stays if the user later
        enters and leaves that role (see res_users.py). A moderator holds
        the group through the role, and their visit records nothing.

        Writing the groups of a user clears the server caches, so the write
        happens only for a user who does not hold the group yet.
        """
        self.ensure_one()
        user = self.env.user
        room = self.sudo()
        if user._is_public() or not room.webapp_id._ewp_can_view():
            return False
        if not room.access_group_id:
            room._ewp_ensure_access(create_channel=False)
        if not room._ewp_is_room_group():
            return False
        group = room.access_group_id
        user_sudo = user.sudo()
        vals = {}
        if group not in user_sudo.groups_id:
            vals["groups_id"] = [Command.link(group.id)]
        if (
            not user.has_group(MODERATOR_GROUP)
            and group not in user_sudo.ewp_room_visit_group_ids
        ):
            vals["ewp_room_visit_group_ids"] = [Command.link(group.id)]
        if vals:
            user_sudo.write(vals)
        return True

    # ------------------------------------------------------------------
    # BigBlueButton
    # ------------------------------------------------------------------

    def _ewp_bbb_check_frame(self):
        """Fetch the conference URL of each room and store whether its
        headers let the web app frame it, with the moment of the check. A
        room without URL is marked not frameable and not checked."""
        now = fields.Datetime.now()
        for room in self:
            if room.bbb_room_url:
                vals = {
                    "bbb_frameable": bbb_client.frame_check(
                        room.bbb_room_url, room.get_base_url()
                    ),
                    "bbb_frame_checked": now,
                }
            else:
                vals = {"bbb_frameable": False, "bbb_frame_checked": False}
            room.write(vals)

    def action_bbb_recheck(self):
        # Before the outbound request: a user who cannot store the result
        # never makes the server fetch the URL.
        self.check_access("write")
        self._ewp_bbb_check_frame()
        return True

    @api.model
    def _ewp_bbb_server(self):
        """(API URL, secret) of the BigBlueButton server, or (False,
        False) when either setting is missing. Read with sudo: the
        parameters are reserved to the Settings group."""
        params = self.env["ir.config_parameter"].sudo()
        api = bbb_client.api_url(params.get_param(PARAM_BBB_URL))
        secret = (params.get_param(PARAM_BBB_SECRET) or "").strip()
        if api and secret:
            return api, secret
        return False, False

    @api.model
    def _ewp_bbb_error_message(self, error):
        """Message for the managers about a failed API call."""
        if error.kind == "network":
            return _(
                "The BigBlueButton server cannot be reached. Check its URL "
                "in the settings."
            )
        if error.kind == "http":
            return _(
                "The BigBlueButton server answered with the HTTP status "
                "%(status)s. Check its URL in the settings.",
                status=error.status,
            )
        if error.kind == "parse":
            return _(
                "The answer of the server is not a BigBlueButton answer. "
                "Check its URL in the settings."
            )
        if error.key == "checksumError":
            return _(
                "The BigBlueButton server refused the shared secret. Check "
                "the secret in the settings."
            )
        return _(
            "The BigBlueButton server refused the request: %(key)s %(message)s",
            key=error.key,
            message=error.message,
        )

    @api.model
    def _ewp_bbb_get_meetings(self):
        """Meetings known by the server (bbb_client.meetings_from_xml).
        Raises UserError when the server is not set or fails."""
        api, secret = self._ewp_bbb_server()
        if not api:
            raise UserError(
                _(
                    "Set the BigBlueButton server and its shared secret in "
                    "the settings first."
                )
            )
        try:
            return bbb_client.get_meetings(api, secret)
        except bbb_client.BbbError as error:
            # from None: no chained cause in the traceback that Odoo sends
            # back with a JSON-RPC error (see bbb_client).
            raise UserError(self._ewp_bbb_error_message(error)) from None

    def _ewp_bbb_join_url(self, create_time=None, logout_url=None):
        """Fresh join URL of the room meeting for the current user: their
        name, the role MODERATOR for the Moderator group (implied by
        Administrator) and VIEWER for everyone else, a userID made of the
        Odoo user id only, and `create_time`, the createTime of the
        running session, so the URL works in that session only.
        `logout_url`, an absolute URL, is where the client of this user
        goes once they leave (see bbb_client.join_url())."""
        self.ensure_one()
        api, secret = self._ewp_bbb_server()
        user = self.env.user
        role = "MODERATOR" if user.has_group(MODERATOR_GROUP) else "VIEWER"
        return bbb_client.join_url(
            api,
            secret,
            self.sudo().bbb_meeting_id,
            user.name,
            role,
            "odoo-%s" % user.id,
            create_time=create_time,
            logout_url=logout_url,
        )

    def _ewp_bbb_meeting(self, max_age=None):
        """State of the room meeting, as bbb_client.meeting_info() returns
        it (`running`, `create_time`), through the cache of bbb_client, no
        older than `max_age` seconds when given; None when the room has no
        meeting ID, the server is not set, or the call fails (logged
        without URL, once per real call)."""
        self.ensure_one()
        room = self.sudo()
        api, secret = room._ewp_bbb_server()
        if not (api and room.bbb_meeting_id):
            return None
        try:
            return bbb_client.cached_meeting_info(
                api, secret, room.bbb_meeting_id, max_age=max_age
            )
        except bbb_client.BbbError as error:
            if not error.cached:
                _logger.warning(
                    "Room %s: BigBlueButton getMeetingInfo failed (%s)",
                    room.id,
                    error,
                )
            return None

    def _ewp_bbb_running(self, max_age=None):
        """True or False when the room meeting can be asked to the server,
        None otherwise (see `_ewp_bbb_meeting()`)."""
        info = self._ewp_bbb_meeting(max_age=max_age)
        return None if info is None else info["running"]

    @api.model
    def _ewp_bbb_display(self):
        """Display mode of the conferences: "auto", "frame" or "tab", from
        the parameter PARAM_BBB_DISPLAY; "auto" when it is unset or holds
        another value. Read with sudo, as the other BBB parameters."""
        mode = (
            self.env["ir.config_parameter"].sudo().get_param(PARAM_BBB_DISPLAY)
        )
        return mode if mode in BBB_DISPLAY_MODES else "auto"

    @api.model
    def _ewp_bbb_embed(self, url, page_url):
        """True when a conference served at `url` is shown in the frame of
        a room page served at `page_url`: always in mode "frame", never in
        mode "tab", and in mode "auto" when both URLs are on the same site
        (bbb_client.same_site())."""
        mode = self._ewp_bbb_display()
        if mode == "auto":
            return bbb_client.same_site(url, page_url)
        return mode == "frame"

    def _ewp_bbb_target(self, logout_url=None, page_url=None, max_age=None):
        """What the room page shows for the conference, as a dict:

        - `state`: "frame" (iframe of `url`), "waiting" (meeting not
          started), "button" (`url` opened in a new tab), "unavailable"
          (server call failed and no conference URL) or False (nothing);
        - `url`: join URL or conference URL, for "frame" and "button";
        - `error`: True when the server call failed;
        - `live`: True only when the server says the meeting runs; a
          conference URL tells nothing about a running session.

        The meeting ID is tried first when the server is set; a failed
        call falls back to the conference URL. A running meeting, or a
        conference URL whose headers allow a frame (`bbb_frameable`), is
        shown in the frame when `_ewp_bbb_embed()` accepts its server for
        the page at `page_url` (the origin of the request; web.base.url
        when not given), else behind the button. `logout_url` goes into
        the join URL only (see `_ewp_bbb_join_url()`); `max_age` bounds
        the age of the meeting state (see `_ewp_bbb_meeting()`).
        """
        self.ensure_one()
        room = self.sudo()
        page_url = page_url or room.get_base_url()
        error = False
        api, _secret = room._ewp_bbb_server()
        if api and room.bbb_meeting_id:
            info = self._ewp_bbb_meeting(max_age=max_age)
            if info and info["running"]:
                embed = room._ewp_bbb_embed(api, page_url)
                return {
                    "state": "frame" if embed else "button",
                    "url": self._ewp_bbb_join_url(
                        info["create_time"], logout_url=logout_url
                    ),
                    "error": False,
                    "live": True,
                }
            if info is not None:
                return {
                    "state": "waiting",
                    "url": False,
                    "error": False,
                    "live": False,
                }
            error = True
        if room.bbb_room_url:
            embed = room.bbb_frameable and room._ewp_bbb_embed(
                room.bbb_room_url, page_url
            )
            return {
                "state": "frame" if embed else "button",
                "url": room.bbb_room_url,
                "error": error,
                "live": False,
            }
        return {
            "state": "unavailable" if error else False,
            "url": False,
            "error": error,
            "live": False,
        }
