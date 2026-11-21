# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prize Claim (Lien du gagnant)",
    "version": "18.0.1.1.0",
    "summary": "Single-use prize link, winner shop and member sales of prizes",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event_raffle_prize", "website_sale", "website_sale_stock"],
    "data": [
        "data/delivery_carrier_data.xml",
        "data/ir_cron_data.xml",
        "data/mail_layout_data.xml",
        "data/mail_template_prize.xml",
        "views/event_raffle_views.xml",
        "views/event_raffle_config_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/delivery_carrier_views.xml",
        "views/website_templates.xml",
    ],
    "demo": [
        "demo/event_raffle_prize_claim_demo.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "event_raffle_prize_claim/static/src/js/**/*.js",
            "event_raffle_prize_claim/static/src/scss/**/*.scss",
        ],
        "web.assets_tests": [
            "event_raffle_prize_claim/static/tests/tours/**/*.js",
        ],
    },
    "installable": True,
    "application": False,
}
