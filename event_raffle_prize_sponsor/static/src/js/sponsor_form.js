/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Error summary of the prize form of the sponsor portal.
 *
 * A form sent back with errors starts with the summary: it takes the focus
 * on load, so a screen reader reads it first. Each link of the summary
 * moves the focus to its field, which a jump to the anchor alone does not
 * do in every browser.
 */
publicWidget.registry.RafflePrizeSponsorErrors = publicWidget.Widget.extend({
    selector: ".o_raffle_sponsor_errors",
    events: {
        "click a[href^='#']": "_onLinkClick",
    },

    start() {
        this.el.focus();
        return this._super(...arguments);
    },

    _onLinkClick(ev) {
        const target = document.getElementById(
            ev.currentTarget.getAttribute("href").slice(1)
        );
        if (target) {
            ev.preventDefault();
            target.focus();
            target.scrollIntoView({block: "center"});
        }
    },
});

export default publicWidget.registry.RafflePrizeSponsorErrors;
