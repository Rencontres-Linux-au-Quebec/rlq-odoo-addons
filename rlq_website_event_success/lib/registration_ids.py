# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Pure helper (no Odoo import): reads the `registration_ids` parameter of the confirmation page.

Odoo builds it as "12,13,14". Anything typed by hand, cut by a mail client or a chat app ("12,13,", "12%2C13", "abc") must
not raise an error: only the positive integers are kept, without duplicates, at most MAX_IDS of them.
"""
import re

MAX_IDS = 50
_NUMBER_RE = re.compile(r"\d+")


def parse_registration_ids(value):
    """Return the list of registration ids found in `value` (str, list or None), in their order, without duplicates."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        value = ",".join(str(item) for item in value)
    ids = []
    for number in _NUMBER_RE.findall(str(value)):
        registration_id = int(number)
        # PostgreSQL integer limit: a longer number cannot be a registration and would make the query fail.
        if 0 < registration_id < 2**31 and registration_id not in ids:
            ids.append(registration_id)
        if len(ids) >= MAX_IDS:
            break
    return ids
