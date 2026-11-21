/** @odoo-module **/

import {registry} from "@web/core/registry";

// A signed-in winner opens the shop, without the prize link, picks the
// prize, and confirms the free order. The test data names the winner and
// the prize.
registry.category("web_tour.tours").add("event_raffle_prize_claim_checkout", {
    steps: () => [
        {
            content: "The banner greets the winner",
            trigger: ".o_raffle_claim_banner h2:contains(Wendy)",
        },
        {
            content: "The banner gives the deadline",
            trigger: ".o_raffle_claim_countdown time[datetime]",
        },
        {
            content: "Open the prize",
            trigger: ".o_wsale_products_item_title a:contains(Claim Mug)",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The sponsor links to its website",
            trigger: ".o_raffle_prize_sponsor a[href='https://sponsor.example.org']",
        },
        {
            content: "Add the prize to the cart",
            trigger: "#add_to_cart",
            run: "click",
        },
        {
            content: "The notification gives the token cost",
            trigger: ".toast-body:contains(Claim Mug):contains(Group A)",
        },
        {
            content: "The notification shows no amount",
            trigger: ".toast-body",
            run() {
                const text = document.querySelector(".toast-body").textContent;
                if (/\d[.,]\d\d/.test(text)) {
                    throw new Error(`An amount in the notification: ${text}`);
                }
            },
        },
        {
            content: "The cart holds one item",
            trigger: ".my_cart_quantity:contains(1)",
            run() {
                window.location.href = "/shop/cart";
            },
            expectUnloadPage: true,
        },
        {
            content: "The cart shows the prize",
            trigger: "#cart_products:contains(Claim Mug)",
        },
        {
            content: "The banner stays on the cart",
            trigger: ".o_raffle_claim_banner",
        },
        {
            content: "Go to the checkout",
            trigger: 'a[href^="/shop/checkout"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The prize handover is the delivery method",
            trigger: '#o_delivery_methods input[name="o_delivery_radio"]:checked',
        },
        {
            content: "Confirm the address and the delivery",
            trigger: 'a[href^="/shop/confirm_order"]',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Confirm the free order",
            trigger: 'form[name="o_wsale_confirm_order"] button[name="o_payment_submit_button"]:enabled',
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "The prize is reserved",
            trigger: "h1:contains(your prize is reserved)",
        },
    ],
});

// A visitor with no prize link opens a prize for tokens only: the page
// shows the token cost, no add to cart, and its variant scripts run to the
// end (website_sale_stock shows the call-to-action wrapper it finds).
registry.category("web_tour.tours").add("event_raffle_prize_claim_token_only_page", {
    steps: () => [
        {
            content: "The page gives the token cost",
            trigger: ".o_raffle_token_cost:contains(Prize only)",
        },
        {
            content: "The variant scripts reached the empty wrapper",
            // Empty, so never visible: the script swapped d-none for d-flex.
            trigger: "#o_wsale_cta_wrapper.d-flex:not(:has(#add_to_cart)):not(:visible)",
        },
    ],
});
