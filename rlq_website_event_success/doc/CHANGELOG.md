# Changelog - rlq_website_event_success

## 18.0.1.1.0 - 2026-11-19 15:10

**Short title:** ticket page `/event/<id>/my_tickets`: 404 instead of error 500 when its parameters are missing.

**Reason for the request:** on 2026-11-19, right after the reminder e-mails "Journée portes ouvertes sur Linux 2026 : dans 2 jours" were sent, app-log-live.py reported 1 error 500 and a traceback on `/event/125/my_tickets?eftvfgebgvba_vef=`. The requests came from the link scanner of an e-mail provider (Microsoft network): it opened the valid ticket link (200), then replayed it with a scrambled parameter name and an empty value.

**Changes:**

- `controllers/my_tickets.py` (new): `RlqEventController.event_my_tickets()` overrides the route of `event` (`@route()`, same URL and options). `registration_ids` and `tickets_hash` become optional and `**kwargs` accepts unknown parameters. Missing or unusable parameters -> `NotFound` (404) with one INFO log line (names of the parameters only, no values); otherwise Odoo's code is called unchanged with the cleaned list of ids.
- `controllers/__init__.py`: imports `my_tickets`.
- `tests/test_my_tickets.py` (new, Odoo HttpCase, 6 tests): no parameter, scrambled parameter name, `registration_ids=abc`, missing hash, wrong hash (all 404), valid link (200, ticket shown).
- `tests/test_registration_ids.py`: 1 new test for the JSON list format `[2094]` of the ticket link.
- `tests/__init__.py`, `__manifest__.py` (version 18.0.1.1.0, description), `README.md`.

**Bugs fixed:**

- Symptom: error 500 `TypeError: EventController.event_my_tickets() missing 2 required positional arguments: 'registration_ids' and 'tickets_hash'`, preceded by the warning `called ignoring args {'eftvfgebgvba_vef'}`. Diagnosis: the route of Odoo 18 has no default value for these 2 parameters; Odoo drops the unknown parameter and calls the method without them, before its own check that would answer 404. Fix: optional parameters and the same 404 as Odoo.
- Symptom: `registration_ids=abc` (or any value that is not a JSON list) would also end in an error 500 (`json.loads`). Fix: `parse_registration_ids()` keeps only the ids, then a clean JSON list is passed to Odoo.

**Safeguards and edge cases:**

- The hash check of Odoo is not touched: without the right `tickets_hash`, no ticket is shown, as before.
- The log line holds only the names of the parameters (cut at 200 characters), never their values (the hash is a secret of the link).
- The `SERIALIZATION_FAILURE` on `website_visitor` seen at the same time is not an error: parallel requests of the scanner created the same visitor; Odoo retried by itself. Nothing to change.

**Checks:**

- `python3 rlq_website_event_success/tests/test_registration_ids.py -v`: 8 tests [OK].
- `ruff check` with the module's `ruff.toml`: passed. `py_compile` of all files: OK.
- The override was written against the source of `event` 18.0 (odoo/odoo, branch 18.0, `addons/event/controllers/main.py`, read on 2026-11-19).
- NOT run: the Odoo tests (`test_my_tickets.py`, `test_registration_success.py`) - no Odoo instance in this environment.

**Action required:**

1. On DEV: update the module (`-u rlq_website_event_success`).
2. Run the Odoo tests on a DISPOSABLE database: `odoo-bin -d TEST_DB -i rlq_website_event_success --test-enable --test-tags rlq_website_event_success --stop-after-init`.
3. Check by hand on DEV: a ticket link from a confirmation e-mail still opens the tickets; the same address without its parameters gives the 404 page.
4. Then update on PROD, when there is less activity on the site.

## 18.0.1.0.0 - 2026-11-07 23:46

**Short title:** new module: registration confirmation page without error 500 or 404.

**Reason for the request:** on 2026-11-07, people who registered for the Journée portes ouvertes sur Linux 2026 got an error on the confirmation page `/event/<event>/registration/success` (1 error 500, 3 errors 404, reported by app-log-live.py), and 2 people registered twice for the same event.

**Changes:**

- `controllers/main.py` (new): `RlqWebsiteEventController.event_registration_success()` overrides the route of `website_event` (`@http.route()`, same URL and options). `registration_ids` becomes optional. Three cases: registrations of this visitor -> Odoo's page unchanged; registrations of this event but visitor not recognised -> Odoo's page with a notice instead of the tickets; nothing found -> new page `registration_not_found`. One log line (INFO) for the last two cases.
- `lib/registration_ids.py` (new, no Odoo import): `parse_registration_ids()` keeps only positive integers below the PostgreSQL limit, without duplicates, 50 at most.
- `views/registration_templates.xml` (new): `registration_complete_tickets_in_email` (inherits `website_event.registration_complete`, notice after the tickets block) and `registration_not_found` (explanation, button to register, organiser's e-mail when there is one).
- `i18n/fr.po` (new): French translation of the 7 texts.
- `tests/test_registration_ids.py` (new, 7 tests without Odoo), `tests/test_registration_success.py` (new, Odoo HttpCase, 4 tests).
- `__manifest__.py`, `__init__.py`, `controllers/__init__.py`, `lib/__init__.py`, `tests/__init__.py`, `ruff.toml` (copied from rlq_survey_report), `README.md`.

**Bugs fixed:**

- Symptom: error 500 `TypeError: WebsiteEventController.event_registration_success() missing 1 required positional argument: 'registration_ids'`. Diagnosis: the route has no default value for the parameter; a reload or a link without its end calls it without. Fix: optional parameter.
- Symptom: error 404 right after a registration that was recorded and confirmed by e-mail. Diagnosis: Odoo raises NotFound when `website.visitor` is not found in the request (cookie replaced or absent: sign-in, other browser or device, in-app browser of a mail or chat app, page reopened later). Fix: page saying that the registration is recorded and the tickets are in the e-mail, so the person does not register a second time.
- Symptom: `registration_ids=abc` or a too large number would also end in an error (cast in the SQL query). Fix: `parse_registration_ids()`.

**Safeguards and edge cases:**

- No personal data of a registration (name, e-mail, ticket, QR code) is shown to a visitor who is not recognised: only the public data of the event, as on its own page. The tickets stay reserved to the recognised visitor, as in Odoo.
- A registration of ANOTHER event is never found (filter on `event_id`), as in Odoo.
- The search is done in sudo only to know whether the registrations exist; it is limited to 50 ids.
- The other modules that inherit `WebsiteEventController` keep working: the route keeps its URL and options, only the signature gets a default value and `**kwargs`.

**Checks:**

- `tests/test_registration_ids.py` run alone (`python3 rlq_website_event_success/tests/test_registration_ids.py -v`): 7 tests [OK].
- `ruff check` with the module's `ruff.toml`: passed. `py_compile` of all files: OK. XML parsed: OK.
- The override was written against the source of `website_event` 18.0 (odoo/odoo, branch 18.0, `controllers/main.py` and `views/event_templates_page_registration.xml`, read on 2026-11-07).
- NOT run: the Odoo tests (`test_registration_success.py`), the installation and the rendering of the pages - no Odoo instance in this environment.

**Action required:**

1. On DEV: install `rlq_website_event_success` (`-i rlq_website_event_success`), with the French language loaded or updated.
2. Run the Odoo tests on a DISPOSABLE database: `odoo-bin -d TEST_DB -i rlq_website_event_success --test-enable --test-tags rlq_website_event_success --stop-after-init`.
3. Check by hand on DEV, in a private window: register for an event (tickets shown), then open the same address in another browser (notice "votre inscription est enregistrée"), then the address without `?registration_ids=` (page "Nous ne pouvons pas afficher d'inscription").
4. Then install on PROD, and remove the duplicate registrations of the 2 people seen on 2026-11-07 (Events > Registrations).
