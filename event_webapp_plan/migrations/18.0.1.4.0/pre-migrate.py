# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Before the models load: the boolean "pause animations" of each user
becomes the animation mode ewp_motion ("off" when it was on, else
"auto"). The column has to exist before the ORM creates it, or the ORM
fills it with the default and the choice of the user is lost; the old
column goes with its field at the end of the update."""

from odoo.addons.event_webapp_plan.models.res_users import (
    migrate_reduce_motion,
)


def migrate(cr, version):
    if version:
        migrate_reduce_motion(cr)
