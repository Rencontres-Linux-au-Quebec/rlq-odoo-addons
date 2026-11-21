# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Event Web App Plan - Raffle Prizes",
    "summary": (
        'Raffle prizes in the event day web app: a "My prize" card for '
        "the logged-in winner, the public name of the winners page, and "
        'a self-declared "I am on site" toggle, for information only.'
    ),
    "description": (
        """
Event Web App Plan - Raffle Prizes
==================================

Bridge between the event day web app (/webapp_event, module
event_webapp_plan) and the raffle prizes (module
event_raffle_prize_handover and the modules it builds on):

* the home page shows a "My prize" card to the logged-in user, for each
  draw of the day that this user won: the button "Choose my prize" with
  its deadline while the prize link is open, then the reserved prize and
  how it reaches the winner (pick-up location, email, shipping with its
  tracking number), then its hand-over; the card stays hidden for a user
  who won nothing, and follows the draws without reloading the page;
* the card sets the public name that the winners page and the raffle
  block of the web app show instead of the full name;
* an "I am on site" toggle lets an attendee say they are at the event;
  the registration and the draw show it, for information only: the
  attendance of the raffles still comes from the check-in scan.

The pages keep the accessibility of the web app: headings, lists, forms
that work without script, one live region, text-only mode.

See README.md and doc/CHANGELOG.md.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
"""
    ),
    "version": "18.0.1.1.0",
    "category": "Marketing/Events",
    "author": (
        "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), "
        "Rencontres Linux au Québec contributors"
    ),
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["event_webapp_plan", "event_raffle_prize_handover"],
    "data": [
        "views/event_registration_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/webapp_templates.xml",
    ],
    "assets": {
        "event_webapp_plan.assets_webapp": [
            "event_webapp_plan_raffle/static/src/webapp/prize.scss",
            "event_webapp_plan_raffle/static/src/webapp/prize.js",
        ],
    },
    "installable": True,
    "application": False,
}
