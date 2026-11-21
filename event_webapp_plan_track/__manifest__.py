# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Event Web App Plan - Agenda",
    "summary": (
        "Agenda of the event day web app from the event tracks: each room "
        "of the plan follows a track location, the home page lists the "
        "sessions, each room shows what happens in it now and next."
    ),
    "description": (
        """
Event Web App Plan - Agenda
===========================

Bridge between the event day web app (/webapp_event, module
event_webapp_plan) and the tracks of the events (module
website_event_track). The agenda is typed once, as event tracks; the web
app reads it:

* each room of the plan follows one track location (one room per
  location and per day);
* the day lists the published tracks of its events that fall in its
  opening window, cancelled ones left out;
* the home page shows an "Agenda" card, sessions grouped by start time,
  with their room (a link to the room page), speaker and tags, the
  sessions in progress marked "Now" and the next ones "Next", and a
  filter by room that works without script;
* the room list of the home page says, under each room, the session in
  progress or the next one;
* a room page lists the sessions of the room, the one in progress
  marked, and announces in the live region the session that starts
  while the visitor is in the room.

Times are shown in the time zone of the event. The states follow the
clock of the page every minute, without reloading it; the program is
asked again from the server every five minutes. The pages keep the
accessibility of the web app: headings, lists, times readable by screen
readers, text-only mode, no animation.

See README.md and doc/CHANGELOG.md.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
"""
    ),
    "version": "18.0.1.2.0",
    "category": "Marketing/Events",
    "author": (
        "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), "
        "Rencontres Linux au Québec contributors"
    ),
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["event_webapp_plan", "website_event_track"],
    "data": [
        "security/ir.model.access.csv",
        "views/event_webapp_views.xml",
        "views/webapp_templates.xml",
    ],
    "assets": {
        "event_webapp_plan.assets_webapp": [
            "event_webapp_plan_track/static/src/webapp/agenda.scss",
            "event_webapp_plan_track/static/src/webapp/agenda.js",
        ],
    },
    "installable": True,
    "application": False,
}
