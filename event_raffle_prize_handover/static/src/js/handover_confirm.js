/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Pending state of the hand-over form.
 *
 * Once the form is sent, the form gets aria-busy, its button
 * aria-disabled and the label of `data-label-sending`, said in the polite
 * status region of the form; any later submit is cancelled, so a second
 * tap during a slow upload sends nothing. The button keeps the focus. A
 * page shown again from the back-forward cache gets its form back.
 */
publicWidget.registry.RafflePrizeHandoverConfirm = publicWidget.Widget.extend({
    selector: ".o_raffle_handover_form",
    events: {
        submit: "_onSubmit",
    },

    start() {
        this.button = this.el.querySelector(".o_raffle_handover_confirm");
        this.status = this.el.querySelector(".o_raffle_handover_pending");
        this.label = this.button ? this.button.textContent : "";
        this.onPageShow = (ev) => {
            if (ev.persisted) {
                this._setBusy(false);
            }
        };
        window.addEventListener("pageshow", this.onPageShow);
        // Tells a script, such as a test, that the submit is watched.
        this.el.dataset.handoverReady = "1";
        return this._super(...arguments);
    },

    destroy() {
        window.removeEventListener("pageshow", this.onPageShow);
        this._super(...arguments);
    },

    _onSubmit(ev) {
        if (this.el.getAttribute("aria-busy") === "true") {
            ev.preventDefault();
            return;
        }
        this._setBusy(true);
    },

    _setBusy(busy) {
        const sending = this.el.dataset.labelSending || "";
        if (busy) {
            this.el.setAttribute("aria-busy", "true");
        } else {
            this.el.removeAttribute("aria-busy");
        }
        if (this.button) {
            if (busy) {
                this.button.setAttribute("aria-disabled", "true");
            } else {
                this.button.removeAttribute("aria-disabled");
            }
            this.button.textContent = busy && sending ? sending : this.label;
        }
        if (this.status) {
            this.status.textContent = busy ? sending : "";
        }
    },
});

export default publicWidget.registry.RafflePrizeHandoverConfirm;
