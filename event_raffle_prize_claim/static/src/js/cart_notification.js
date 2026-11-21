/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import {AddToCartNotification} from "@website_sale/js/notification/add_to_cart_notification/add_to_cart_notification";
import {CartNotification} from "@website_sale/js/notification/cart_notification/cart_notification";
import {patch} from "@web/core/utils/patch";

/**
 * Token cost of a claim line in the add-to-cart notification.
 *
 * The server sets `raffle_token_label` on a claim line of the notification
 * (WebsiteSale._get_additional_notification_information); the notification
 * shows it where it shows the line's amount, which is 0 after the claim's
 * full discount. Both components declare the shape of a line, so both
 * accept the key.
 */
patch(AddToCartNotification.prototype, {
    getFormattedPrice(line) {
        if (line.raffle_token_label) {
            return line.raffle_token_label;
        }
        return super.getFormattedPrice(...arguments);
    },
});

function withTokenLabel(Component) {
    const lines = Component.props.lines;
    Component.props = {
        ...Component.props,
        lines: {
            ...lines,
            element: {
                ...lines.element,
                shape: {
                    ...lines.element.shape,
                    raffle_token_label: {type: String, optional: true},
                },
            },
        },
    };
}

withTokenLabel(AddToCartNotification);
withTokenLabel(CartNotification);
