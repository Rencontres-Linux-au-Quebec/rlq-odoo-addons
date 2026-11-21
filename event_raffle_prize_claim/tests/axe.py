# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""axe-core audits of the raffle prize pages, in the test browser.

The modules' accessibility tests share three pieces: the copy of
axe-core that EWP_AXE_JS names, the moment a page is ready to audit, and
the audit itself.

A website page reaches `document.readyState === "complete"` before its
JavaScript has run. The lazy loader of the website starts loading
web.assets_frontend_lazy only on the window "load" event, and the public
root starts the page widgets after that bundle. The test assets wait for
modules of that bundle too: a test tour of the website reads the computed
style of the first iframe of the page when it starts. Test code run on
"complete" therefore races the page's own start: it audits markup the
widgets have not set yet, a frame it adds is read by that tour while its
document has no root element, and errors of the widgets arrive after the
test has ended. `FRONTEND_READY` waits for the end of that start instead,
as the tours do when they wait for the lazy JavaScript.
"""

import json
import os

AXE_ENV = "EWP_AXE_JS"

# Resolves to true once the lazy bundles of `win` have run and its public
# root has started every widget of the page. A module of the Odoo loader
# keeps its default export under Symbol.for("default").
_READY_JS = """async function raffleFrontendReady(win) {
    const modules = win.odoo.loader.modules;
    const DEFAULT = Symbol.for("default");
    const lazyloader = modules.get("@web/legacy/js/public/lazyloader");
    await lazyloader[DEFAULT].allScriptsLoaded;
    const root =
        modules.get("@website/js/content/website_root_instance") ||
        modules.get("@web/legacy/js/public/public_root_instance");
    await root[DEFAULT];
    return true;
}"""

# The `ready` code of `browser_js` for a website page: false until the
# document has loaded, then the promise above. `browser_js` evaluates it
# again until it is true, so a page whose start fails ends on the ready
# timeout, with the page's own error.
FRONTEND_READY = f"document.readyState === 'complete' && ({_READY_JS})(window)"

# Defines raffleFrontendReady(win) and raffleAxeAudit(win, include, touch).
# The audit loads axe-core in `win` once, runs the WCAG 2.0, 2.1 and 2.2 A
# and AA rules plus "region" on the elements of `include` found in the
# page, and throws when one fails, when no element of `include` is there,
# when the page scrolls sideways, or when an element of `touch` is less
# than 48 px high.
_AUDIT_JS = _READY_JS + """
async function raffleAxeAudit(win, include, touch = []) {
    if (!win.axe) {
        win.eval(RAFFLE_AXE_SOURCE);
    }
    const doc = win.document;
    const own = include.filter((selector) => doc.querySelector(selector));
    if (!own.length) {
        throw new Error("no element of the module on the page");
    }
    const result = await win.axe.run(
        {include: own.map((selector) => [selector])},
        {
            iframes: false,
            runOnly: {
                type: "tag",
                values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
            },
            rules: {region: {enabled: true}},
        }
    );
    const found = result.violations.map((v) => {
        const nodes = v.nodes.map((n) => n.target.join(" "));
        return `${v.id}: ${nodes.join(", ")}`;
    });
    if (found.length) {
        throw new Error("axe: " + found.join(" | "));
    }
    if (doc.documentElement.scrollWidth > win.innerWidth + 1) {
        throw new Error("horizontal scroll at " + win.innerWidth);
    }
    const small = touch.length
        ? [...doc.querySelectorAll(touch.join(", "))].filter(
              (el) => el.getBoundingClientRect().height < 47.5
          )
        : [];
    if (small.length) {
        throw new Error(
            "touch targets under 48 px: " +
                small.map((el) => el.outerHTML.slice(0, 80)).join(" | ")
        );
    }
}
"""


class AxeMixin:
    """axe-core audits for an HttpCase."""

    def _axe_source(self):
        """The source of axe-core that EWP_AXE_JS names.

        The test skips only when the variable is unset: a run that names a
        file expects it there, and fails when it is missing.
        """
        path = os.environ.get(AXE_ENV)
        if not path:
            self.skipTest(f"{AXE_ENV} is not set: no copy of axe.min.js")
        if not os.path.isfile(path):
            self.fail(f"{AXE_ENV}={path} is not a file")
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def _axe_code(self, body):
        """The test code of `browser_js` for `body`, the statements of an
        async function that calls raffleAxeAudit() and throws on a failure.
        The code logs the success signal once `body` returns, and the
        message of the error it throws otherwise."""
        return (
            "const RAFFLE_AXE_SOURCE = "
            + json.dumps(self._axe_source())
            + ";\n"
            + _AUDIT_JS
            + "\n(async () => {\n"
            + body
            + '\nconsole.log("test successful");\n'
            + "})().catch((error) => console.error(error.message));\n"
        )

    def _axe_browse(self, url, code, **kwargs):
        """Runs `code` on `url` once the page has started; `kwargs` go to
        `browser_js` (login, cookies)."""
        self.browser_js(url, code, ready=FRONTEND_READY, **kwargs)
