# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Event Web App Plan",
    "summary": (
        "Mobile web app for an event day at /webapp_event: "
        "announcement, links, events, clickable site plan with one "
        "public chat per room, and the raffle draws of the day."
    ),
    "description": (
        """
Event Web App Plan
==================

A dedicated, installable (PWA) web page at /webapp_event for one event
day, reserved to logged-in users (portal or internal):

* a general announcement and links about the event;
* the events of the day;
* the site plan, on which each room is clickable; a room page embeds its
  Odoo Discuss channel, which the visitor joins automatically; each room
  has its own access group, given to the visitor on entering the room and
  kept afterwards, so the chat stays readable once the day is over and
  stays closed to anonymous visitors and to those who never entered;
* a BigBlueButton conference per room, beside the chat: the room joins
  its meeting through the BigBlueButton API (server URL and shared secret
  in the settings), or shows its conference URL, in the page when the
  server is on the same site as the web app (a display setting can force
  the page or a new tab), else behind a button that opens it in a new
  tab;
* the raffle draws of the day (module event_raffle), refreshed live;
  the raffles of the day are pre-filled from the planned date of each
  raffle, or from the dates of its event, and edited by hand.

The backend application "Event Web App" configures each day: its opening
window (start and end), announcement, links, events, raffles, plan image
and rooms. Rooms are drawn on the plan image with a visual editor.
Outside the opening window, only the Moderator and Administrator groups
of the application can see the page, to test it; they read every room
chat.

The pages aim at WCAG 2.2 AA: skip links, landmarks, one live region
for the announcements, a room list that repeats the plan for screen
readers, and two display options stored on the user, a text-only mode
and an animation mode: follow the device, on or off (see "Accessibility"
in README.md). Decorative cameos come in at the edges of the pages
while the animations run; a theme brings its own actors (see "Theming").

A theme module restyles the pages through the hooks listed in the
"Theming" section of README.md: template slots, CSS custom properties,
DOM events and the page state on the body. A module that adds a block
(the agenda of event_webapp_plan_track, for instance) fills the slots of
the room list and of the room page with the values of
_ewp_page_values().

See doc/CHANGELOG.md for the history of the versions.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
"""
    ),
    "version": "18.0.1.12.0",
    "category": "Marketing/Events",
    "author": (
        "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), "
        "Rencontres Linux au Québec contributors"
    ),
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["event", "event_raffle", "mail", "web"],
    "data": [
        "security/event_webapp_security.xml",
        "security/ir.model.access.csv",
        "views/event_webapp_views.xml",
        "views/event_webapp_bbb_meetings_views.xml",
        "views/res_config_settings_views.xml",
        "views/res_users_views.xml",
        "views/menus.xml",
        "views/webapp_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "event_webapp_plan/static/src/backend/**/*",
        ],
        "event_webapp_plan.assets_webapp": [
            "event_webapp_plan/static/src/webapp/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
