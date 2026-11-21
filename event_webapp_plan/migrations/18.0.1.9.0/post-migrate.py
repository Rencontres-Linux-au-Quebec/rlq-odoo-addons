# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""After the models load: the room groups held outside the Moderator role
are recorded as visits (res_users.backfill_room_visits()), so a visitor
who later enters and leaves that role keeps the rooms they entered."""

from odoo.addons.event_webapp_plan.models.res_users import (
    backfill_room_visits,
)


def migrate(cr, version):
    if version:
        backfill_room_visits(cr)
