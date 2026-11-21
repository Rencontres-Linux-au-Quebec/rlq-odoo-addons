# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Wizard listing the meetings of the BigBlueButton server (getMeetings).

The event day fills it (`action_open_bbb_meetings`); each line gives its
meetingID to a room of that day, which then joins this meeting through the
API. A Greenlight room shows only its own short code, never this internal
meetingID: this list is where a manager finds it, once the host started
the meeting.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class EventWebappBbbMeetings(models.TransientModel):
    _name = "event.webapp.bbb.meetings"
    _description = "Event Web App BigBlueButton Meetings"

    webapp_id = fields.Many2one(
        "event.webapp",
        string="Event day",
        required=True,
        ondelete="cascade",
    )
    line_ids = fields.One2many(
        "event.webapp.bbb.meeting.line", "wizard_id", string="Meetings"
    )
    meeting_count = fields.Integer(compute="_compute_meeting_count")

    def _compute_meeting_count(self):
        for wizard in self:
            wizard.meeting_count = len(wizard.line_ids)

    def _ewp_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Running BBB meetings"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_refresh(self):
        self.ensure_one()
        return self.webapp_id.action_open_bbb_meetings()


class EventWebappBbbMeetingLine(models.TransientModel):
    _name = "event.webapp.bbb.meeting.line"
    _description = "Event Web App BigBlueButton Meeting"
    _order = "meeting_name, id"

    wizard_id = fields.Many2one(
        "event.webapp.bbb.meetings", required=True, ondelete="cascade"
    )
    webapp_id = fields.Many2one(related="wizard_id.webapp_id")
    meeting_name = fields.Char(string="Meeting", readonly=True)
    meeting_id = fields.Char(string="Meeting ID", readonly=True)
    participant_count = fields.Integer(string="Participants", readonly=True)
    running = fields.Boolean(readonly=True)
    room_id = fields.Many2one(
        "event.webapp.room",
        string="Room",
        domain="[('webapp_id', '=', webapp_id)]",
    )

    def action_assign(self):
        """Give the meeting ID of the line to its room, then show the list
        again. Reserved to the Settings group, like the list itself."""
        self.ensure_one()
        self.env["event.webapp.room"]._ewp_bbb_check_meeting_rights()
        if not self.room_id:
            raise UserError(_("Choose the room that joins this meeting."))
        if self.room_id.webapp_id != self.webapp_id:
            raise UserError(_("The room must belong to this event day."))
        self.room_id.bbb_meeting_id = self.meeting_id
        return self.wizard_id._ewp_action()
