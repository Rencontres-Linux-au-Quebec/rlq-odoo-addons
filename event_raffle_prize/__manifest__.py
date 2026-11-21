# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prizes (Prix de tirage)",
    "version": "18.0.1.2.0",
    "summary": "Prize catalogue, stock and assisted prize claims for raffles",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event_raffle", "sale_stock"],
    "data": [
        "security/ir.model.access.csv",
        "data/event_raffle_prize_band_data.xml",
        "wizard/event_raffle_prize_choose_wizard_views.xml",
        "wizard/event_raffle_prize_decline_wizard_views.xml",
        "views/event_raffle_prize_band_views.xml",
        "views/product_template_views.xml",
        "views/product_product_views.xml",
        "views/event_raffle_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/sale_order_views.xml",
        "views/event_raffle_prize_claim_log_views.xml",
        "views/event_raffle_prize_menus.xml",
    ],
    "demo": [
        "demo/event_raffle_prize_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "event_raffle_prize/static/src/**/*.js",
            "event_raffle_prize/static/src/**/*.xml",
            "event_raffle_prize/static/src/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
