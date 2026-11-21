# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle (Tirage)",
    "version": "18.0.1.2.0",
    "summary": "Animated prize draws (3D wheel) for events",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event", "mail", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/event_raffle_config_data.xml",
        "wizard/event_raffle_start_wizard_views.xml",
        "views/event_raffle_views.xml",
        "views/event_raffle_draw_views.xml",
        "views/event_raffle_actions.xml",
        "views/event_raffle_config_views.xml",
        "views/event_event_views.xml",
        "views/res_partner_views.xml",
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
