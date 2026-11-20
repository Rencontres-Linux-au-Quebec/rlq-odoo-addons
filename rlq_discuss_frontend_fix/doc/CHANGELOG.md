# Changelog - rlq_discuss_frontend_fix

## 18.0.1.0.0 - 2026-11-20 17:14

**Short title:** new module: no more "thread.closeChatWindow is not a function" on the website.

**Reason for the request:** on 2026-11-20 at 15:44:50 (20:44:50 GMT), the administrator saw on www.rencontres-linux.quebec: "UncaughtClientError > TypeError: thread.closeChatWindow is not a function at Proxy._handleNotificationChannelDelete (web.assets_frontend_lazy.min.js)".

**Changes:**

- `static/src/thread_model_patch.js` (new): patch of `Thread.prototype` with `closeChatWindow()`: calls Odoo's function when one exists, otherwise closes the chat window of the thread (`store.ChatWindow.get({ thread }).close({ notifyState: false })`, same body as Odoo's back-office version).
- `__manifest__.py`: depends on `mail` and `im_livechat`; the file is added to `im_livechat.assets_embed_core` (included in `web.assets_frontend`, so the website, and in the external livechat embed) and to `mail.assets_public`.
- `tests/test_assets.py` (new): 5 tests on the files (run without Odoo) and 2 Odoo tests (file present in `web.assets_frontend`, absent from `web.assets_backend`).
- `README.md`, `ruff.toml`.

**Bugs fixed:**

- Symptom: error dialog "thread.closeChatWindow is not a function" on the website, and the deleted channel stays in the page. Diagnosis: in Odoo 18 (checked on the branch 18.0 of odoo/odoo, 2026-11-20), `_handleNotificationChannelDelete()` of `mail/static/src/discuss/core/common/discuss_core_common_service.js` calls `thread.closeChatWindow()`, defined only in `mail/static/src/core/web/thread_model_patch.js`. That file is in `web.assets_backend` only; `im_livechat.assets_embed_core` and `mail.assets_public` load the handler without it. Every notification "discuss.channel/delete" received by a website page fails. Fix: the missing function in those bundles.

**Safeguards and edge cases:**

- Never loaded in `web.assets_backend`: the back-office keeps Odoo's function.
- If a later Odoo defines `closeChatWindow` in common code, the patch calls it (`super`) instead of its own body.
- No chat window open for the channel (the usual case on the website): nothing happens, the handler goes on and removes the channel from the page.
- `store.ChatWindow` missing: optional chaining, no error.

**Checks:**

- `python3 rlq_discuss_frontend_fix/tests/test_assets.py -v`: 5 tests [OK].
- `ruff check`: [OK]; `node --check` of the JavaScript file: [OK].
- Not verified here: the Odoo tests (TestBundles) and the behaviour in a browser; no Odoo instance in this environment.

**Action required:** after merge, on the Odoo PROD server: copy the module into addons_path (or git pull of rlq-odoo-addons), update the list of applications, install "Discussion : plus d'erreur closeChatWindow sur le site". Check with the test of the DEV first if wanted: `odoo-bin -d BASE -i rlq_discuss_frontend_fix --test-tags /rlq_discuss_frontend_fix --stop-after-init`.
