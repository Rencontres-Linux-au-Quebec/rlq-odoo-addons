# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prizes (Prix de tirage)",
    "version": "18.0.1.2.0",
    "summary": "Prize catalogue, stock and assisted prize claims for raffles",
    "description": """
English

A catalogue of sponsored prizes with a real inventory, token categories
Prize Group A to F, and an assisted prize claim for each winner: one token
of the draw's category takes one prize of that category. A claim log keeps
declines and expiries, and a draw, raffle or event holding a prize cannot be
deleted. Details: README.md of the module.

Français

Un catalogue de prix commandités avec un vrai inventaire, des catégories
de jeton Groupe de prix A à F, et une attribution assistée pour chaque
gagnant : un jeton de la catégorie du tir prend un prix de cette catégorie.
Un journal garde refus et expirations, et un tir, tirage ou événement qui
tient un prix ne peut pas être supprimé. Détails : README.md du module.
""",
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
