# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Event Raffle Survey (Tirage par sondage)",
    "version": "18.0.1.0.0",
    "summary": "Draw a raffle among the respondents of a survey",
    # Rendered as RST on the Apps page: the module is no application (see
    # `application` below) and has no static/description/index.html. A list
    # or an indented line that no blank line sets apart either logs a
    # docutils warning or renders as something else, so the text keeps to
    # plain paragraphs.
    "description": """
English

Adds the "Survey filled only" choice to the Start a Raffle wizard of an
event. Pick a survey: its respondents enter the raffle instead of the
event's registrations. An answer counts when it is completed, is not a
test entry and answers at least one question. Each person enters once,
recognised by contact, then email, then nickname; an answer without a
contact joins the contact whose answers give the same email, unless
several contacts give it.

Optionally, list required questions of the survey: only the respondents
who answered each of them, or at least one, then enter. The wizard counts
the respondents entering, anonymous ones included, before the draw.

Drawing from a survey needs the Surveys: User access right; without it,
the wizard does not offer the survey choice.

Français

Ajoute le choix « Sondage rempli seulement » à l'assistant « Démarrer un
tirage » d'un événement. Choisissez un sondage : ses répondants entrent
dans le tirage à la place des inscrits de l'événement. Une participation
compte si elle est terminée, n'est pas un test et répond à au moins une
question. Chaque personne n'entre qu'une fois, reconnue par son contact,
puis son courriel, puis son pseudo ; une participation sans contact
rejoint le contact dont les participations donnent le même courriel, sauf
si plusieurs contacts le donnent.

En option, listez des questions exigées du sondage : seuls les répondants
qui ont répondu à chacune, ou à au moins une, entrent alors. L'assistant
compte les répondants retenus, anonymes compris, avant le tirage.

Tirer depuis un sondage demande le droit d'accès Sondages : Utilisateur ;
sans lui, l'assistant ne propose pas le choix du sondage.
""",
    "author": "TechnoLibre",
    "website": "https://technolibre.ca",
    "category": "Marketing/Events",
    "license": "AGPL-3",
    "depends": ["event_raffle", "survey"],
    "data": [
        "wizard/event_raffle_start_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
