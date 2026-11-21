# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Rencontres Linux theme of the /webapp_event pages, controller side.

The class extends the controller of event_webapp_plan: Odoo serves the
routes of the parent through the most derived class, so only the helpers
change. The installed app takes the name, the blue of the bars and the
Tux icons of the theme; every page receives rlq_show_poster, read by the
home lead slot of views/webapp_templates.xml.
"""

from odoo.addons.event_webapp_plan.controllers.main import (
    EventWebappController,
)
from odoo.http import request

ICON_URL = "/rlq_event_webapp_plan/static/src/webapp/img/icon-%s.png"
# Blue of the bars: browser chrome and splash screen of the installed app.
THEME_COLOR = "#1F4E9E"


class RlqEventWebappController(EventWebappController):
    def _ewp_pwa_values(self):
        values = super()._ewp_pwa_values()
        _ = request.env._
        values.update(
            name=_("Rencontres Linux event day"),
            short_name=_("Rencontres Linux"),
            theme_color=THEME_COLOR,
            background_color=THEME_COLOR,
            icon_url=ICON_URL % 192,
            icons=[
                {
                    "src": ICON_URL % size,
                    "sizes": "%sx%s" % (size, size),
                    "type": "image/png",
                    "purpose": "any maskable",
                }
                for size in (192, 512)
            ],
        )
        return values

    def _ewp_base_values(self, webapp=None, tz="UTC"):
        values = super()._ewp_base_values(webapp, tz)
        values["rlq_show_poster"] = bool(webapp and webapp.rlq_show_poster)
        return values
