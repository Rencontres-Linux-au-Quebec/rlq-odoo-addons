# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Event Web App Plan - Rencontres Linux theme",
    "summary": (
        "Look of the Rencontres Linux au Québec event day web app: "
        "lys-blue bars, coffee-break colours, animated Tux mascots."
    ),
    "description": (
        """
Event Web App Plan - Rencontres Linux theme
===========================================

Theme of the event day web app (/webapp_event, module
event_webapp_plan) for Rencontres Linux au Québec, design version 3
"Pause café animée":

* blue bars with a fleur-de-lys motif, a yellow rule and a ribbon of
  words, cream background, Bree Serif headings;
* Tux with a fleur-de-lys and a cup of coffee in the home header and on
  the closed page;
* an animated vector Tux on the room page, in the raffle card and on the
  closed pages, whose pose follows the day: idle, greeting, sipping
  before the opening, celebrating a raffle winner, speaking into a
  microphone while the conference is live, drinking a coffee while it
  waits, waving when it is left, asleep once the day is over;
* Tux cameos a little everywhere on the pages (cameo engine of
  event_webapp_plan): Tux comes in at a corner, a card or the header,
  drinks a coffee, codes on a laptop, waves, peeks or waddles, then goes
  away; he celebrates a raffle winner, speaks into a microphone near a
  live conference and falls asleep after the day;
* an optional "Pause Café Linux" card with its poster on the home page;
* the name, colours and icons of the installable app;
* demo data only: an example event day, "Journée portes ouvertes sur
  Linux 2026", with its event, tickets, five presentation places, 21
  tracks, a raffle of 7 draws, and five rooms on a plan, each following
  a place, so the agenda of event_webapp_plan_track shows in the app.

The agenda comes from event_webapp_plan_track, which pulls
website_event_track (and the website) into the database.

Every animation stops with the animation mode "Off", with the system
setting "reduce motion" under the mode "Follow the device", and in
text-only mode, where no mascot is shown; the mode "On" plays them even
when the device asks for less motion. The
scrolling ribbon has its own pause button and is read once as plain
text by screen readers.

See README.md for the origin of the images and doc/CHANGELOG.md for the
history of the versions.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
"""
    ),
    "version": "18.0.1.3.2",
    "category": "Marketing/Events",
    "author": (
        "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), "
        "Rencontres Linux au Québec contributors"
    ),
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["event_webapp_plan", "event_webapp_plan_track"],
    "data": [
        "views/event_webapp_views.xml",
        "views/webapp_templates.xml",
    ],
    "demo": ["demo/event_webapp_demo.xml"],
    "assets": {
        "event_webapp_plan.assets_webapp": [
            "rlq_event_webapp_plan/static/src/webapp/rlq_theme.scss",
            "rlq_event_webapp_plan/static/src/webapp/rlq_theme.js",
        ],
    },
    "images": ["static/description/banner.jpg"],
    "installable": True,
    "application": False,
}
