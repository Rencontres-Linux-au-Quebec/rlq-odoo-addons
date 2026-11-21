# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Prize Sponsors (Commanditaires des prix)",
    "version": "18.0.1.3.0",
    "summary": "Sponsors submit their raffle prizes in the portal, the "
    "organization approves them",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event_raffle_prize_handover", "portal"],
    "data": [
        "security/event_raffle_prize_sponsor_security.xml",
        "security/ir.model.access.csv",
        "data/mail_template_sponsor_thanks.xml",
        "data/product_public_category_data.xml",
        "wizard/event_raffle_prize_refuse_wizard_views.xml",
        "wizard/event_raffle_sponsor_thank_wizard_views.xml",
        "report/event_raffle_sponsor_report_views.xml",
        "views/event_event_views.xml",
        "views/event_registration_views.xml",
        "views/product_template_views.xml",
        "views/event_raffle_sponsor_menus.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "event_raffle_prize_sponsor/static/src/js/**/*.js",
            "event_raffle_prize_sponsor/static/src/scss/**/*.scss",
        ],
    },
    "installable": True,
    "application": False,
}
