# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prize Claim (Lien du gagnant)",
    "version": "18.0.1.2.0",
    "summary": "Single-use prize link, winner shop and member sales of prizes",
    "description": """
English

A single-use prize link for each winner, opened by the winner's own
account, and a website shop that shows the prizes of their token category
and checks out with the token alone. Members may buy sponsored prizes while
the sponsored shop is open. Details: README.md of the module.

Français

Un lien de prix à usage unique pour chaque gagnant, ouvert par son propre
compte, et une boutique du site qui montre les prix de sa catégorie de jeton
et se règle par le jeton seul. Les membres peuvent acheter les prix
commandités tant que la boutique commanditée est ouverte. Détails :
README.md du module.
""",
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
        "views/event_raffle_draw_views.xml",
        "views/delivery_carrier_views.xml",
        "views/res_config_settings_views.xml",
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
