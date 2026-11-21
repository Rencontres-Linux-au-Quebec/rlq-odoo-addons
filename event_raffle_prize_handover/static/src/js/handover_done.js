/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Focus on the success message of the hand-over screen.
 *
 * After a hand-over the list page opens with the message in a polite live
 * region; a live region present at load is not always announced, so the
 * message also takes the focus (it has tabindex="-1"), which a screen
 * reader reads, and the next Tab reaches the search field.
 */
publicWidget.registry.RafflePrizeHandoverDone = publicWidget.Widget.extend({
    selector: ".o_raffle_handover_done",

    start() {
        this.el.focus();
        return this._super(...arguments);
    },
});

export default publicWidget.registry.RafflePrizeHandoverDone;
