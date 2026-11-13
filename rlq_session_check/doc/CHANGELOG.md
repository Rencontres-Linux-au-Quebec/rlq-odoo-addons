# Changelog - rlq_session_check

## 18.0.1.1.0 - 2026-11-13 16:44

**Short title:** route /rlq/session/me: first name to greet and profile of the signed-in person, for the link pages.

**Reason for the request:** request of the administrator on 2026-11-13: when someone is signed in to Odoo, the link pages show "Bonjour Prénom" and a button at the bottom right with more information on the person (name, address, groups), the button only for the members of a given group.

**Changes:**

- `controllers/main.py`: new route `/rlq/session/me` (type http, auth public, GET, no CSRF, not in the sitemap, save_session=False) and `_json()` (Content-Type application/json, `Cache-Control: private, no-store`, `Vary: Cookie`, `X-Content-Type-Options: nosniff`, no CORS header).
- `lib/session_check.py`: `first_name()` (field firstname when a module gives it, otherwise the first word of the name; 60 characters at most), `address_lines()`, `profile_answer()` (only the known fields; 50 groups at most), constants `PROFILE_GROUP_PARAM` and `PROFILE_GROUP_DEFAULT`.
- System parameter `rlq_session_check.profile_group` (XML id; default `base.group_user`): the members of that group get `details` (name, address, e-mail, phone, groups without the technical ones: category hidden).
- `tests/test_session_check.py`: 4 tests; `tests/test_session_route.py`: class TestSessionMe, 4 tests; `__manifest__.py`, `README.md`.

**Bugs fixed:** none.

**Safeguards and edge cases:**

- Not signed in: `{"signed_in": false}`, nothing else.
- Only the data of the person who asks, never anyone else; same site only (no CORS header), so another site cannot read it.
- Parameter not valid or group unknown: no details for anyone (one WARNING line).
- The technical groups (hidden category) are not listed.

**Checks performed:** `python3 -m py_compile`; `python3 rlq_session_check/tests/test_session_check.py -v` (9 tests without Odoo); ruff. The HttpCase tests were NOT run (no Odoo instance while writing).

**Action required:** update the module (`-u rlq_session_check`); if needed, set the system parameter `rlq_session_check.profile_group` to the XML id of the group that sees its profile.

## 18.0.1.0.0 - 2026-11-13 14:44

**Short title:** new module: route /rlq/session/check for nginx (auth_request).

**Reason for the request:** request of the administrator on 2026-11-13: the link pages of nginx-link-page.sh (rlq-admin-tools) should show more links to the people signed in to Odoo, in a secure way. nginx needs a light route that answers 2xx or 401 for the session of the browser: the routes of Odoo do not fit (/web/session/get_session_info is JSON-RPC by POST, auth_request sends a GET without a body; /web and /my render a whole page and answer by a redirection).

**Changes:**

- `controllers/main.py` (new): `RlqSessionCheck.rlq_session_check()`, route `/rlq/session/check` (type http, auth public, GET and HEAD, no CSRF, not in the sitemap, save_session=False); optional parameter `group` (XML id of a res.groups); empty answer with `Cache-Control: private, no-store` and `Vary: Cookie`; one log line (WARNING) for a group not valid or not found.
- `lib/session_check.py` (new, no Odoo import): `parse_group()` (XML id module.name, lower-case letters, digits and _) and `status()` (204, 401 or 403).
- `tests/test_session_check.py` (new, 5 tests without Odoo), `tests/test_session_route.py` (new, Odoo HttpCase, 5 tests).
- `__manifest__.py`, `__init__.py`, `controllers/__init__.py`, `lib/__init__.py`, `tests/__init__.py`, `ruff.toml` (copied from rlq_website_event_success), `README.md`.

**Bugs fixed:** none (new module).

**Safeguards and edge cases:**

- Never open by mistake: a group not valid, unknown, or an XML id that is not a group -> 403; any other answer of Odoo (stopped, module not installed) makes nginx refuse.
- Nothing about the user in the answer (no name, no e-mail, no group list): the route only says something about the session of the browser that asks.
- No new session for a visitor who is not signed in (save_session=False), so the check does not fill the session store.
- Portal users count as signed in; use `odoo:base.group_user` in nginx-link-page for the internal users only.

**Checks performed:** `python3 -m py_compile` of every file; `python3 rlq_session_check/tests/test_session_check.py -v` (5 tests without Odoo); ruff with the configuration of the module. The HttpCase tests were NOT run (no Odoo instance while writing).

**Action required:** install the module (Apps, or `odoo-bin -d DB -i rlq_session_check`), then `curl -i https://SITE/rlq/session/check` must answer 401. On a disposable database: `odoo-bin -d TEST_DB -i rlq_session_check --test-enable --test-tags rlq_session_check --stop-after-init`.
