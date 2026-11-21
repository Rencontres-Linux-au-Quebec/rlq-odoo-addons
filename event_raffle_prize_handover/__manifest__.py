# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prize Handover (Remise des prix)",
    "version": "18.0.1.0.0",
    "summary": "Prize pick-up, virtual prizes, shipping, hand-over screen "
    "and public winners page",
    "description": """
English

How a reserved prize reaches its winner: picked up on site, sent by email
when it is virtual, or shipped to a virtual winner. A phone screen lets the
event team find a winner and hand the prize over, and a public page lists
the winners of an event hour by hour. Details: README.md of the module.

Français

Comment un prix réservé atteint son gagnant : retiré sur place, envoyé par
courriel s'il est virtuel, ou expédié à un gagnant virtuel. Un écran de
téléphone permet à l'équipe de trouver un gagnant et de lui remettre le
prix, et une page publique liste les gagnants d'un événement heure par
heure. Détails : README.md du module.
""",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event_raffle_prize_claim"],
    "data": [
        "security/ir.model.access.csv",
        "data/mail_template_prize.xml",
        "wizard/event_raffle_prize_ship_wizard_views.xml",
        "wizard/event_raffle_prize_virtual_wizard_views.xml",
        "views/event_event_views.xml",
        "views/event_raffle_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/website_templates.xml",
        "views/handover_templates.xml",
        "views/winners_templates.xml",
        "views/event_raffle_handover_menus.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "event_raffle_prize_handover/static/src/js/**/*.js",
            "event_raffle_prize_handover/static/src/scss/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
