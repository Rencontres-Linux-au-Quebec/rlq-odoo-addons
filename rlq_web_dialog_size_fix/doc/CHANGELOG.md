# Changelog - rlq_web_dialog_size_fix

## 18.0.1.0.0 - 2026-11-20 18:24

**Short title:** new module: no loop of "Session expired" dialogs caused by web_dialog_size.

**Reason for the request:** app-log-live.py output of 2026-11-20 sent by the administrator: at 17:38:53, a browser of the team (EricU+EricB) on /odoo/discuss sent several hundred POST /web/dataset/call_kw/ir.config_parameter/get_web_dialog_size_config within one second, each answered with "Session expired" by Odoo, until nginx answered 429 (zone odoo_general, about 235 refusals). The health score of the dashboard went down from 90 % to 66 %.

**Changes:**

- `static/src/expand_button_patch.esm.js` (new): patch of `ExpandButton.prototype.setup` of web_dialog_size: after Odoo's setup, a handler is attached at once to `this.config` (the promise of the RPC); `onMounted()` keeps using it as before.
- `__manifest__.py`: depends on `web_dialog_size`, `auto_install`, file in `web.assets_backend`.
- `tests/test_files.py` (new, 4 tests): manifest, content of the patch, and two node tests (with the patch, the rejected promise of an expired session is never "unhandled" and the later catch still runs; without it, the rejection is unhandled, which is what triggers the loop).
- `README.md`, `ruff.toml`.

**Bugs fixed:**

- Symptom: hundreds of RPC get_web_dialog_size_config per second from one browser after its session expired, then 429 from nginx. Diagnosis (OCA/web 18.0, commit 77f56ce of 2026-11-13, web_dialog_size 18.0.1.0.4): `ExpandButton.setup()` calls `orm.call("ir.config_parameter", "get_web_dialog_size_config")` and attaches `.catch()` only inside `onMounted()`. With an expired session the RPC fails before the dialog is mounted; the browser reports an unhandled rejection; `rpcErrorHandler` of Odoo opens `SessionExpiredDialog` (exception odoo.http.SessionExpiredException); its header holds an ExpandButton, which sends the RPC again: endless loop. Fix: the rejection is handled in the same tick.

**Safeguards and edge cases:**

- The original setup of web_dialog_size runs unchanged (`super.setup`); nothing is done if `this.config` is not a promise (another version of web_dialog_size).
- The first error (of another RPC) still opens one "Session expired" dialog, as in Odoo without web_dialog_size; its Close button still reloads the page.
- A valid session is not affected: the configuration (default maximize) is applied in `onMounted()` as before.

**Checks:**

- `python3 rlq_web_dialog_size_fix/tests/test_files.py -v`: 4 tests [OK] (node 22). `ruff check`: [OK].
- Not verified here: the module in a running Odoo (no instance in this environment); check on the DEV that web_dialog_size of ERPLibre has `this.config = this.orm.call(` in `ExpandButton.setup()`.

**Action required:** after merge: update the list of applications and install the module on the DEV, then the PROD (it also installs itself on a database where web_dialog_size is installed later). Optional: report the bug to OCA/web (web_dialog_size, branch 18.0).
