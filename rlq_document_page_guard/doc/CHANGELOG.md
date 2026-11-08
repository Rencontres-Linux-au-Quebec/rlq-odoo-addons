# Changelog - rlq_document_page_guard

## 18.0.1.0.0 - 2026-11-07 19:33

**Short title:** new module: guard against oversized wiki pages (data-last-history-steps).

**Reason for the request:** on 2026-11-07, wiki page 167 could no longer be opened (MemoryError in the Odoo worker, `web_read` of `document.page`). Its 528 words weighed 24 MB: 99.9 % of the content was the attribute `data-last-history-steps` of Odoo's collaborative editor, which grew at every save, and every version of the history kept a full copy (264 MB for this page, 485 MB for page 149, about 1.1 GB for some thirty pages). The history was cleaned by hand in SQL; this module adds a validation so that the problem does not come back.

**Changes:**

- `lib/html_steps.py` (new, no Odoo import): `trim_history_steps(html, keep=1)` reduces each `data-last-history-steps` value to its last step id(s), or removes the attribute when `keep` is 0; `steps_size(html)` measures the attribute values.
- `models/document_page.py` (new):
  - `document.page.create()` / `write()`: the content is cleaned before the OCA module compares it with the current version, so a save without real change no longer creates a heavy version.
  - `document.page.history.create()` / `write()`: the content is cleaned again (any other path that writes the history), then validated by `_rlq_check_content_size()`.
  - `_rlq_check_content_size()`: refuses (ValidationError, French and English) a version larger than `rlq_document_page_guard.max_content_mb`, unless it is not larger than the current version.
  - `_rlq_trim_existing_history(min_bytes=100000)`: cleans the stored versions one at a time in SQL.
- `hooks.py` (new): `post_init_hook` calls `_rlq_trim_existing_history()` at installation.
- `data/ir_config_parameter.xml` (new, noupdate): `rlq_document_page_guard.keep_history_steps` = 1, `rlq_document_page_guard.max_content_mb` = 5.
- `i18n/fr.po` (new): French translation of the validation message.
- `tests/test_html_steps.py` (new, 12 tests without Odoo) and `tests/test_document_page_guard.py` (new, Odoo TransactionCase, 8 tests).
- `__manifest__.py`, `__init__.py`, `ruff.toml` (copied from rlq_survey_report), `README.md`.

**Bugs fixed:**

- Symptom: a wiki page can no longer be opened, Odoo shows an error and the log has `MemoryError` in `web_read`.
- Diagnosis: the attribute `data-last-history-steps` is never emptied; the page and each of its versions grow by the ids of the editing steps at every save, until reading the page exceeds `limit_memory_hard` (1196 MB per worker on PROD).
- Fix: only the last step id is kept at every save (the only one the editor reads to resynchronise collaborators), and the versions already stored are cleaned at installation.

**Safeguards and edge cases:**

- The text, links and formatting are never modified: only the value of this one attribute. The words "data-last-history-steps" in the visible text are not touched (an attribute needs `=`).
- Double and single quotes, upper or lower case, empty values, `False`/`None` and `markupsafe.Markup` values are handled; the cleaning is idempotent.
- The size limit is checked AFTER cleaning: the ids do not count. A page already above the limit can always be saved if the new version is not larger, so a volunteer can make it lighter. `max_content_mb` = 0 disables the check.
- The size of the current version is read in SQL (`octet_length`), never its content: the check itself cannot run out of memory.
- `_rlq_trim_existing_history()` reads and rewrites one version at a time (24 MB at most in memory), only those above 100 KB that contain the attribute.
- Invalid parameter values fall back to the defaults (1 and 5 MB).

**Checks:**

- `tests/test_html_steps.py` run alone (`python3 rlq_document_page_guard/tests/test_html_steps.py -v`): 12 tests [OK], including a 24 MB attribute around 528 words.
- `ruff check` with the module's `ruff.toml`: passed.
- Python syntax (`py_compile`) of all files: OK. XML of `ir_config_parameter.xml` parsed: OK.
- NOT run: the Odoo tests (`test_document_page_guard.py`), the installation and the post_init_hook - no Odoo instance in this environment. Not verified on a real instance: the exact behaviour of the OCA `document_page` 18.0 module (computed `content` with an inverse that creates the history line), on which the test "save without real change" relies.

**Action required:**

1. On DEV: put the module in the addons path, update the list of apps, install `rlq_document_page_guard` (`-i rlq_document_page_guard`). The log must show "N version(s) of wiki pages cleaned".
2. Run the Odoo tests on a DISPOSABLE database: `odoo-bin -d TEST_DB -i rlq_document_page_guard --test-enable --test-tags rlq_document_page_guard --stop-after-init`.
3. On DEV, edit a wiki page several times and check that `data-last-history-steps` keeps a single id: `SELECT id, octet_length(content) FROM document_page_history ORDER BY id DESC LIMIT 5;`
4. Edit a page at two at the same time (two browsers) to check that the collaborative editing still works.
5. Then install on PROD.
