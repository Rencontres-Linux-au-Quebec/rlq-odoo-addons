# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Pure helpers (no Odoo import) for the `data-last-history-steps` attribute.

Odoo's collaborative HTML editor stores, in the attribute `data-last-history-steps` of the edited content, the ids of the
editing steps (comma separated). Only the LAST id is used by the editor to resynchronise collaborators. When the list is
never emptied, every save appends its steps: on 2026-11-07 a wiki page of 528 words weighed 24 MB, 99.9 % of it in this
attribute, and opening it raised MemoryError in the Odoo worker.

This file has no dependency on Odoo so that it can be tested alone (see tests/test_html_steps.py).
"""
import re

ATTRIBUTE = "data-last-history-steps"

# The attribute, its quote and its value. The value never contains its own quote (ids are alphanumeric, separated by commas).
_STEPS_RE = re.compile(r"(\s" + ATTRIBUTE + r"\s*=\s*)([\"'])(.*?)\2", re.IGNORECASE | re.DOTALL)


def trim_history_steps(html, keep=1):
    """Return `html` with each `data-last-history-steps` value reduced to its `keep` last step ids.

    keep >= 1: keep the last ids (the editor only reads the last one).
    keep <= 0: remove the attribute entirely.
    The type of the value is kept (str or markupsafe.Markup); False/None/"" are returned unchanged.
    """
    if not html or not isinstance(html, str) or ATTRIBUTE not in html.lower():
        return html

    def _replace(match):
        if keep <= 0:
            return ""
        ids = [step.strip() for step in match.group(3).split(",") if step.strip()]
        if not ids:
            return ""
        return f"{match.group(1)}{match.group(2)}{','.join(ids[-keep:])}{match.group(2)}"

    result = _STEPS_RE.sub(_replace, html)
    if result == html:
        return html
    # markupsafe.Markup is a str subclass: rebuild the same type without escaping again.
    return type(html)(result) if type(html) is not str else result


def steps_size(html):
    """Number of characters taken by the `data-last-history-steps` values in `html` (0 when absent)."""
    if not html or not isinstance(html, str):
        return 0
    return sum(len(match.group(3)) for match in _STEPS_RE.finditer(html))
