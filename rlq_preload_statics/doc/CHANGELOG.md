# Changelog - rlq_preload_statics

## 18.0.1.0.0 - 2026-11-18 19:27

**Short title:** new server-wide module: the main process of Odoo lists the static folders once, before its workers.

**Reason for the request:** request of the administrator on 2026-11-18, after the profiles of the warm-up (odoo-warmup.py of rlq-admin-tools): 61.6 % of the busy time in get_manifest, get_module_icon and os.path.exists (odoo.http.root.statics), 10.1 s per worker in DEV (135 folders in addons_path, 4480 modules); the module goes into rlq-odoo-addons, the repository of the Odoo modules.

**Changes:**

- `__init__.py`: `post_load()` (hook of the manifest, called by Odoo when it loads the server-wide modules in its main process) and `preload(root)`.
- `__manifest__.py` (`post_load`, depends on `base`, not auto-installed), `README.md`, `ruff.toml`.
- `tests/test_preload.py`: 3 tests that run without Odoo (a fake odoo module).

**Bugs fixed:** the first version (copy in rlq-admin-tools odoo-addons/, nginx-hardening.sh 2.116) did `import odoo.http` inside `post_load()`: Python then treats `odoo` as a local name and the first line (`getattr(odoo, "evented", False)`) raises UnboundLocalError. Found by the tests of this module; fixed with `from odoo import http`.

**Safeguards and edge cases:**

- Not done in the gevent process (`odoo.evented`).
- Any failure is logged (ERROR with the traceback) and changes nothing: Odoo starts as before.
- Never installed in a database: no data, no view, no model.

**Checks performed:** `python3 -m py_compile`; `python3 rlq_preload_statics/tests/test_preload.py -v` (3 tests without Odoo); ruff. Not yet run in a real Odoo.

**Action required:** test in DEV first: `nginx-hardening.sh --update --odoo-preload-statics` (rlq-admin-tools 2.117), then `odoo-update-module.sh --restart-only`; look for the line « rlq_preload_statics: static folders of N modules listed in X s » in the log of Odoo.
