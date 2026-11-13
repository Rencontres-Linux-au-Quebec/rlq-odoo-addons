# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Pure functions of the session check (no Odoo import): read the ?group= parameter and choose the HTTP status.

The answer is read by nginx (auth_request): 2xx lets the request go, 401 and 403 refuse it, any other status is an error
(nginx answers 500): the access is then refused too, never open by default.
"""
import re

# XML id of a group: module.name (lower-case letters, digits and _), as base.group_user or rlq_module.group_volunteers
GROUP_RE = re.compile(r"^[a-z0-9_]{1,64}\.[a-z0-9_]{1,128}$")

ALLOWED = 204        # signed in (and in the group): no content
NOT_SIGNED_IN = 401  # nginx sends to /web/login
FORBIDDEN = 403      # signed in, but not in the group (or the group is not valid: refused, never open)


def parse_group(value):
    """Return the XML id of the group asked, None when no group is asked; raise ValueError when it is not valid."""
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not GROUP_RE.match(value):
        raise ValueError("group must be an XML id like base.group_user")
    return value


def status(is_public, in_group):
    """HTTP status for nginx. is_public: the request has no signed-in user. in_group: True, False, or None (no group asked)."""
    if is_public:
        return NOT_SIGNED_IN
    if in_group is False:
        return FORBIDDEN
    return ALLOWED


# 18.0.1.1.0: /rlq/session/me (greeting "Bonjour Prénom" and profile of the signed-in person, read by the script of the link pages)
PROFILE_GROUP_PARAM = "rlq_session_check.profile_group"   # ir.config_parameter: XML id of the group that sees its profile
PROFILE_GROUP_DEFAULT = "base.group_user"
MAX_GROUPS = 50


def first_name(name, firstname=None):
    """First name to greet: the field firstname when a module gives it (partner_firstname), otherwise the first word of the name."""
    if isinstance(firstname, str) and firstname.strip():
        return firstname.strip()[:60]
    if isinstance(name, str) and name.strip():
        return name.strip().split()[0][:60]
    return ""


def address_lines(street="", street2="", zip_code="", city="", state="", country=""):
    """Lines of a postal address, without the empty parts."""
    ville = " ".join(p for p in (zip_code, city) if p)
    lignes = [street, street2, ", ".join(p for p in (ville, state) if p), country]
    return [ligne.strip() for ligne in lignes if ligne and ligne.strip()]


def profile_answer(signed_in, first="", details=None):
    """JSON answer of /rlq/session/me: never anything when the browser is not signed in; details only for the profile group."""
    if not signed_in:
        return {"signed_in": False}
    answer = {"signed_in": True, "first_name": first}
    if details is not None:
        answer["details"] = {
            "name": details.get("name", ""),
            "address": list(details.get("address", [])),
            "email": details.get("email", ""),
            "phone": details.get("phone", ""),
            "groups": sorted(set(details.get("groups", [])))[:MAX_GROUPS],
        }
    return answer
