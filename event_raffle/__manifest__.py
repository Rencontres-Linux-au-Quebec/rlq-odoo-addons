# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle (Tirage)",
    "version": "18.0.1.9.0",
    "summary": "Animated prize draws (3D wheel) for events",
    "description": """
English

Animated prize draws for an event: a 3D wheel of the participants, its
celebration and Tux animations, winners marked absent and drawn again. Each
draw can notify its winner by chat or email and be announced in a Discuss
channel; a test raffle stays out of the default lists. The defaults of new
raffles are in the general settings. Details: README.md of the module.

Français

Tirages de prix animés pour un événement : une roue 3D des participants,
sa célébration et les animations de Tux, des gagnants marqués absents et
tirés de nouveau. Chaque tir peut prévenir son gagnant par clavardage ou
courriel et s'annoncer dans un canal de Discussion ; un tirage de test reste
hors des listes par défaut. Les défauts des nouveaux tirages sont dans les
paramètres généraux. Détails : README.md du module.
""",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event", "mail", "web"],
    "data": [
        "security/ir.model.access.csv",
        "security/event_raffle_security.xml",
        "data/event_raffle_config_data.xml",
        "wizard/event_raffle_start_wizard_views.xml",
        "wizard/event_raffle_draw_notify_wizard_views.xml",
        "views/event_raffle_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/event_raffle_actions.xml",
        "views/event_event_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/event_raffle_menus.xml",
    ],
    "assets": {
        "event_raffle.assets_three": [
            "event_raffle/static/lib/three/three.min.js",
        ],
        "web.assets_backend": [
            "event_raffle/static/src/**/*.js",
            "event_raffle/static/src/**/*.xml",
            "event_raffle/static/src/**/*.scss",
        ],
        "web.assets_unit_tests": [
            "event_raffle/static/tests/**/*.js",
        ],
    },
    "installable": True,
    "application": True,
}
