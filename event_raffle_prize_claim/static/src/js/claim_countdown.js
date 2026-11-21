/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Minutes left on the prize link, in the claim banner.
 *
 * The server renders the deadline time and the minutes left, so the banner
 * reads right without JavaScript. This widget only refreshes the minutes:
 * the text changes once a minute at most, which bounds what the polite
 * live region announces. The labels come translated in data attributes.
 */
publicWidget.registry.RafflePrizeClaimCountdown = publicWidget.Widget.extend({
    selector: ".o_raffle_claim_countdown",

    start() {
        this.deadline = Date.parse(this.el.dataset.deadline);
        this.output = this.el.querySelector(".o_raffle_claim_left");
        this.minutesLeft = null;
        if (this.output && !Number.isNaN(this.deadline)) {
            this.refresh();
            this.timer = setInterval(() => this.refresh(), 10000);
        }
        return this._super(...arguments);
    },

    destroy() {
        clearInterval(this.timer);
        this._super(...arguments);
    },

    refresh() {
        const left = Math.max(0, Math.ceil((this.deadline - Date.now()) / 60000));
        if (left === this.minutesLeft) {
            return;
        }
        this.minutesLeft = left;
        const labels = this.el.dataset;
        let text = labels.labelExpired;
        if (left === 1) {
            text = `(${labels.labelOne})`;
        } else if (left > 1) {
            text = `(${labels.labelMany.replace("%s", left)})`;
        } else {
            clearInterval(this.timer);
        }
        this.output.textContent = text;
    },
});

export default publicWidget.registry.RafflePrizeClaimCountdown;
