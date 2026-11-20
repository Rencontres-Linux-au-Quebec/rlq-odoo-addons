# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Rebuilds i18n/fr.po: scripts/fr_base.po (the entries of the older screens) + every term of the registration desk and
volunteers screens (models/event_registration_desk.py, models/volunteer_coordinator.py, views/event_registration_desk_views.xml).

Why a script: Odoo attaches a translation to a view, field, menu or action through the « #: » reference of its entry, and loads
the translation of a Python string only when the entry carries the comment « #. odoo-python ». Entries written by hand without
them stay in English on screen (seen in 18.0.1.121.0 and 18.0.1.122.0). The terms are extracted from the sources, so that none
is forgotten; each one must have a French translation in FR below, otherwise the script stops and names it.

Usage, from the module directory, after adding or changing a label of those screens (add its translation to FR first):

    python3 scripts/build_fr_po.py
"""
import ast
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

MODULE = "rlq_survey_report"
root_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_po = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root_dir, "scripts", "fr_base.po")

FR = {
    # survey.question
    "Show at the registration desk": "Afficher au bureau d'inscription",
    "If checked, the answer of each registered person to this question is shown in the RLQ registration desk of the event (Events > RLQ registration desk), and the answers are counted per ticket type. Useful for questions such as « On site or online? » or « Will you be there for lunch? ».":
        "Si coché, la réponse de chaque inscrit à cette question est affichée dans le bureau d'inscription RLQ de l'événement (Événements > Bureau d'inscription RLQ), et les réponses sont comptées par type de billet. Utile pour des questions comme « Sur place ou en ligne ? » ou « Serez-vous présent pour le dîner ? ».",
    "Short label at the registration desk": "Libellé court au bureau d'inscription",
    "Short name of this question in the registration desk (for example « Lunch »). Empty: the title of the question.":
        "Nom court de cette question dans le bureau d'inscription (par exemple « Dîner »). Vide : le titre de la question.",
    # v1.131.0: name with a link to send a message, date of the event
    "Participant name": "Nom du participant",
    "Name of the participant. Click it to send a message to this person in Odoo (Discuss). Sorting by this column ignores case and accents.":
        "Nom du participant. Cliquez dessus pour envoyer un message à cette personne dans Odoo (Discussion). Le tri de cette colonne ignore les majuscules et les accents.",
    "Date of the event": "Date de l'événement",
    "Local date and time of the event (start, and end when it is another day).":
        "Date et heure locales de l'événement (début, et fin si c'est un autre jour).",
    # event.registration
    "Left at": "Heure de départ",
    "Survey submitted on": "Sondage soumis le",                      # v1.133.0: « Sort by » of the desk
    "Time when the person left the event, recorded with the « Left » button of the RLQ registration desk.":
        "Heure à laquelle la personne a quitté l'événement, enregistrée avec le bouton « Départ » du bureau d'inscription RLQ.",
    "Questions answered": "Questions répondues",
    "Questions answered / questions of the survey expected for this registration (pages excluded). Empty: no survey.":
        "Questions répondues / questions du sondage attendu pour cette inscription (pages exclues). Vide : aucun sondage.",
    "Answers": "Réponses",
    "Answers of this person to the survey questions checked « Show at the registration desk ».":
        "Réponses de cette personne aux questions du sondage cochées « Afficher au bureau d'inscription ».",
    # rlq.registration.desk
    "RLQ registration desk": "Bureau d'inscription RLQ",
    "Registration desk: %(event)s": "Bureau d'inscription : %(event)s",
    "Registration desk": "Bureau d'inscription",
    "Event": "Événement",
    "By default: the event in progress, otherwise the next one.": "Par défaut : l'événement en cours, sinon le prochain.",
    "Search": "Recherche",
    "Hide the people already present": "Masquer les personnes déjà présentes",
    "Survey": "Sondage",
    "Lists only the registrations whose survey is in this state.": "Liste seulement les inscriptions dont le sondage est dans cet état.",
    "All": "Tous",
    # v1.145.0: filter « On site or online » of every RLQ page
    "On site": "Présentiel",
    "Online": "Virtuel",
    "Not specified": "Non précisé",
    "On site or online": "Présentiel ou virtuel",
    "On site or online not specified": "Présentiel ou virtuel non précisé",
    "From the answer to the on site or online question of the survey of this person, otherwise from the roles questions « (en présentiel) » / « (en virtuel) » answered, otherwise from the name of the ticket.":
        "D'après la réponse à la question présentiel ou virtuel du sondage de cette personne, sinon d'après les questions de rôles « (en présentiel) » / « (en virtuel) » répondues, sinon d'après le nom du billet.",
    "Lists only the people who will be on site (« Présentiel », « Sur place », « Hybride », or « Oui » to « Serez-vous présent à l'ÉTS ? »), only the people online, or only the people whose answers say neither. Read in this order: the answer to the on site or online question of their survey, the roles questions « (en présentiel) » / « (en virtuel) » they answered, then the name of their ticket.":
        "Liste seulement les personnes qui seront en présentiel (« Présentiel », « Sur place », « Hybride », ou « Oui » à « Serez-vous présent à l'ÉTS ? »), seulement les personnes en virtuel, ou seulement celles dont les réponses ne disent ni l'un ni l'autre. Lu dans cet ordre : la réponse à la question présentiel ou virtuel de leur sondage, les questions de rôles « (en présentiel) » / « (en virtuel) » auxquelles elles ont répondu, puis le nom de leur billet.",
    "Survey completed": "Sondage complété",
    "Survey started": "Sondage commencé",
    "Survey not started": "Sondage non commencé",
    "No survey": "Aucun sondage",
    "Sort by": "Trier par",
    "Order of the list below. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by ticket, then by name.":
        "Ordre de la liste ci-dessous. Les majuscules et les accents sont ignorés (« Élise » est classée avec les « e ») ; à valeur égale, le tri se fait par billet, puis par nom.",
    "Ticket": "Billet",
    "Name": "Nom",
    "Registration date": "Date d'inscription",
    "Status": "Statut",
    "Arrival": "Arrivée",
    "Departure": "Départ",
    "Descending": "Ordre décroissant",
    "Reverses the order of the list.": "Inverse l'ordre de la liste.",
    "Summary": "Sommaire",
    "Registrations": "Inscriptions",
    "Registrations listed": "Inscriptions listées",
    "Refresh": "Actualiser",
    "Open as a list": "Ouvrir en liste",
    "Present": "Présent",
    "Undo": "Annuler la présence",
    "Undo the presence of this person?": "Annuler la présence de cette personne ?",
    "Left": "Départ",
    "Undo the departure": "Annuler le départ",
    "Clear the departure time of this person?": "Effacer l'heure de départ de cette personne ?",
    "Registered on": "Inscrit le",
    "Arrived at": "Heure d'arrivée",
    "« Present » records the hour of arrival. The questions listed under « Answers » are the survey questions checked « Show at the registration desk ». A survey belongs to a registration when it was answered by the same contact or with the same e-mail address.":
        "« Présent » enregistre l'heure d'arrivée. Les questions listées sous « Réponses » sont les questions du sondage cochées « Afficher au bureau d'inscription ». Un sondage est rattaché à une inscription quand il a été rempli par le même contact ou avec la même adresse courriel.",
    "Person": "Personne",
    "Not present yet": "Pas encore présent",
    "Group By": "Regrouper par",
    "User guide": "Guide d'utilisation",
    "Help for this page": "Aide de cette page",                      # v1.134.0: button of the desk and the volunteers
    # v1.141.0: participants blocked by a « live session »
    "Live session mode: the participants wait for a host.": "Mode session en direct : les participants attendent un hôte.",
    "Every person who opens this survey sees « wait for the host to go to the next question » and cannot go further than the first question.":
        "Toute personne qui ouvre ce sondage voit « Veuillez attendre que l'hôte passe à la question suivante » et ne peut pas aller plus loin que la première question.",
    "Do not use « End Live Session » of Odoo: it marks EVERY participation as completed, even the unfinished ones.":
        "N'utilisez pas « Terminer la session en direct » d'Odoo : ce bouton marque TOUTES les participations comme complétées, même celles qui ne sont pas finies.",
    "Participations waiting:": "Participations en attente :",
    "Close the live session (keep the answers)": "Fermer la session en direct (garder les réponses)",
    "Close the live session? The blocked participants will continue after reloading the page; no participation is marked completed.":
        "Fermer la session en direct ? Les participants bloqués pourront continuer en rechargeant la page ; aucune participation n'est marquée complétée.",
    "Participants blocked on the first question": "Participants bloqués à la première question",
    "Survey « %(survey)s »: live session mode, %(count)d participations wait for a host. Open the survey and click « Close the live session (keep the answers) ».":
        "Sondage « %(survey)s » : mode session en direct, %(count)d participations attendent un hôte. Ouvrez le sondage et cliquez « Fermer la session en direct (garder les réponses) ».",
    "Only survey users can manage sessions.": "Seuls les utilisateurs des sondages peuvent gérer les sessions.",
    "Live session closed": "Session en direct fermée",
    "%(count)d participations can continue: the people only need to reload the page of the survey. No participation was marked completed.":
        "%(count)d participations peuvent continuer : les personnes n'ont qu'à recharger la page du sondage. Aucune participation n'a été marquée complétée.",
    "The survey « %(survey)s » is used by event registrations: a live session would make every person who opens it wait for a host, question by question. Duplicate the survey to run a live session.":
        "Le sondage « %(survey)s » sert aux inscriptions d'un événement : une session en direct ferait attendre un hôte, question par question, à toute personne qui l'ouvre. Dupliquez le sondage pour faire une session en direct.",
    "Participations waiting for the host": "Participations en attente de l'hôte",
    "Participations not completed that are in « live session » mode: the person sees « wait for the host » and cannot go to the next question.":
        "Participations non complétées en mode « session en direct » : la personne voit « attendez l'hôte » et ne peut pas passer à la question suivante.",
    "Live session problem": "Problème de session en direct",
    # v1.140.0: device of the participations, survey reminders
    "Send a reminder": "Envoyer un rappel",
    "Send the invitation e-mail of their survey again to every person listed (each one receives their own link)?":
        "Renvoyer le courriel d'invitation de leur sondage à toutes les personnes listées (chacune reçoit son propre lien) ?",
    "Customize the reminder": "Personnaliser le rappel",
    "Device": "Appareil",
    "Operating system": "Système d'exploitation",
    "Operating system of the device that last answered the survey of this person.":
        "Système d'exploitation de l'appareil qui a répondu en dernier au sondage de cette personne.",
    "Browser": "Navigateur",
    "Browser that last answered the survey of this person (for example « Firefox 145 »).":
        "Navigateur qui a répondu en dernier au sondage de cette personne (par exemple « Firefox 145 »).",
    "User-Agent": "User-Agent",
    "User-Agent of the browser that last answered this participation (public survey pages).":
        "User-Agent du navigateur qui a répondu en dernier à cette participation (pages publiques du sondage).",
    "Operating system of the device that last answered this participation, read from its User-Agent.":
        "Système d'exploitation de l'appareil qui a répondu en dernier à cette participation, lu dans son User-Agent.",
    "Browser that last answered this participation, read from its User-Agent.":
        "Navigateur qui a répondu en dernier à cette participation, lu dans son User-Agent.",
    # v1.139.0: more tickets in « Topics of interest », filter « Answer » of the desk, last event displayed
    "(no answer)": "(sans réponse)",
    "Last event displayed": "Dernier événement affiché",
    "Answer": "Réponse",
    "Lists only the registrations that gave this answer (or no answer) to a question checked « Show at the registration desk ». The questions of the same title in several surveys are taken together.":
        "N'affiche que les inscriptions qui ont donné cette réponse (ou aucune réponse) à une question cochée « Afficher au bureau d'inscription ». Les questions de même titre dans plusieurs sondages sont prises ensemble.",
    "Topics of interest of the volunteers": "Sujets d'intérêt des bénévoles",
    "Topics of interest of the sponsors": "Sujets d'intérêt des commanditaires",
    "Which registrations are counted, by the name of their ticket (case and accents ignored): « visiteur » / « visitor », « bénévole », « commanditaire » / « sponsor » / « partenaire », or the tickets chosen below.":
        "Quelles inscriptions sont comptées, selon le nom de leur billet (sans tenir compte des majuscules ni des accents) : « visiteur » / « visitor », « bénévole », « commanditaire » / « sponsor » / « partenaire », ou les billets choisis ci-dessous.",
    "Volunteer tickets": "Billets bénévoles",
    "Sponsor tickets": "Billets commanditaires",
    "Tickets chosen one by one": "Billets choisis un par un",
    "Tickets chosen": "Billets choisis",
    "With « Tickets chosen one by one »: only the registrations to these tickets.":
        "Avec « Billets choisis un par un » : seulement les inscriptions à ces billets.",
    # v1.138.0: « Topics of interest », « Contact the participants » for the administrators only
    "Topics of interest": "Sujets d'intérêt",
    "Topics of interest of the audience": "Sujets d'intérêt de l'audience",
    "Topics of interest of the visitors": "Sujets d'intérêt des visiteurs",
    "Only the administrators of the surveys or of the events may contact the participants.":
        "Seuls les administrateurs des sondages ou des événements peuvent contacter les participants.",
    "(no ticket)": "(sans billet)",
    "No question checked « Show in Topics of interest » in the survey « %(survey)s ».":
        "Aucune question cochée « Afficher dans « Sujets d'intérêt » » dans le sondage « %(survey)s ».",
    "Show in « Topics of interest »": "Afficher dans « Sujets d'intérêt »",
    "If checked, the answers to this question are counted in the page « Topics of interest » (Rapports RLQ): each topic chosen or written, with the number of people and the percentage of the respondents, per ticket. Useful for questions such as « Which topics would you like at a next meeting? ». No name or e-mail address is shown.":
        "Si cochée, les réponses à cette question sont comptées dans la page « Sujets d'intérêt » (Rapports RLQ) : chaque sujet choisi ou écrit, avec le nombre de personnes et le pourcentage des répondants, par billet. Utile pour des questions comme « Quels sujets aimeriez-vous lors d'une prochaine rencontre ? ». Aucun nom ni courriel n'est affiché.",
    "Tickets": "Billets",
    "Every ticket": "Tous les billets",
    "Visitor tickets": "Billets visiteurs",
    # v1.137.0: « Volunteer expertise », menu « Volunteer management », contact by mailing
    "Volunteer management": "Gestion des bénévoles",
    "Volunteer expertise": "Expertises des bénévoles",
    "Volunteer expertise: %(event)s": "Expertises des bénévoles : %(event)s",
    "Event: %(event)s": "Événement : %(event)s",
    "No question checked « Show in Volunteer expertise » in the survey « %(survey)s ».":
        "Aucune question cochée « Afficher dans Expertises des bénévoles » dans le sondage « %(survey)s ».",
    "Show in « Volunteer expertise »": "Afficher dans « Expertises des bénévoles »",
    "If checked, the answer of each volunteer to this question is shown in the page « Volunteer expertise » (Rapports RLQ): one column per choice, with the number of volunteers who chose it. Useful for questions such as « What are your areas of expertise? ». Only the survey of the volunteer ticket is read.":
        "Si cochée, la réponse de chaque bénévole à cette question est affichée dans la page « Expertises des bénévoles » (Rapports RLQ) : une colonne par choix, avec le nombre de bénévoles qui l'ont choisi. Utile pour des questions comme « Quelles sont vos expertises ? ». Seul le sondage du billet bénévole est lu.",
    "Order of the table. Case and accents are ignored; equal values are sorted by name.":
        "Ordre du tableau. Les majuscules et les accents sont ignorés ; à égalité, le tri se fait par nom.",
    # v1.136.0: confirmation about personal information, once per page
    "Confirmation": "Confirmation",
    "This page shows personal information about the participants (names, e-mail addresses, phone numbers). I confirm that I am responsible for its confidentiality and will share it only with authorized people.":
        "Cette page contient des renseignements personnels sur les participants (noms, courriels, téléphones). Je confirme être responsable de leur confidentialité et m'engage à ne les partager qu'avec les personnes autorisées.",
    "Continue": "Continuer",
    "Check the box about personal information to continue.":
        "Cochez la case de confirmation concernant les renseignements personnels pour continuer.",
    "Confirmation about personal information": "Confirmation concernant les renseignements personnels",
    "I am responsible for the personal information shown": "Je suis responsable des renseignements personnels affichés",
    "This page shows personal information about the participants (names, e-mail addresses, phone numbers). By checking this box, you confirm that you are aware of this responsibility and will share it only with authorized people (Loi 25 in Québec, GDPR in Europe).":
        "Cette page contient des renseignements personnels sur les participants (noms, courriels, téléphones). En cochant cette case, vous confirmez être conscient(e) de cette responsabilité et vous engager à ne les partager qu'avec les personnes autorisées (Loi 25 au Québec, RGPD en Europe).",
    # v1.135.0: answers of a person, contact, search in more columns
    "See the answers": "Voir les réponses",
    "Contact the participants": "Contacter les participants",
    "Name, e-mail, company, phone, ticket or answer": "Nom, courriel, entreprise, téléphone, billet ou réponse",
    "No participant of this list has an e-mail address.": "Aucun participant de cette liste n'a d'adresse courriel.",
    "This person has not answered the survey yet.": "Cette personne n'a pas encore répondu au sondage.",
    "Answers (text)": "Réponses (texte)",
    "Answers of this person to the survey questions checked « Show at the registration desk ». Click them to see every answer of the survey filled in by this person.":
        "Réponses de cette personne aux questions du sondage cochées « Afficher au bureau d'inscription ». Cliquez dessus pour voir toutes les réponses du sondage rempli par cette personne.",
    "The participation of this person to the expected survey (the most advanced one, the most recent among equals).":
        "La participation de cette personne au sondage attendu (la plus avancée, la plus récente à égalité).",
    "Can edit the answers": "Peut modifier les réponses",
    "Part of a name, an e-mail address, a company, a phone number, a ticket or an answer: only the matching registrations are listed (case and accents ignored). The summary always counts the whole event.":
        "Une partie d'un nom, d'une adresse courriel, d'une entreprise, d'un numéro de téléphone, d'un billet ou d'une réponse : seules les inscriptions correspondantes sont listées (sans tenir compte des majuscules ni des accents). Le sommaire compte toujours tout l'événement.",
    "Export to a spreadsheet": "Exporter dans un chiffrier",
    "The spreadsheet export needs the Python library « openpyxl », which is not installed on this server (pip install openpyxl).":
        "L'export dans un chiffrier nécessite la bibliothèque Python « openpyxl », qui n'est pas installée sur ce serveur (pip install openpyxl).",
    "No volunteer to export for this event.": "Aucun bénévole à exporter pour cet événement.",
    "The survey « %(survey)s » has no question about the hour of arrival or of departure: the hours shown are those recorded at the registration desk (« Present », « Left »).":
        "Le sondage « %(survey)s » n'a pas de question sur l'heure d'arrivée ou de départ : les heures affichées sont celles enregistrées au bureau d'inscription (« Présent », « Départ »).",
    # rlq.survey.answer.change / rlq.survey.answer.edit (v1.127.0)
    'Answer to edit':
        'Réponse à modifier',
    'This type of question (matrix) cannot be changed here.':
        'Ce type de question (matrice) ne peut pas être modifié ici.',
    'Edit the answers':
        'Modifier les réponses',
    'Example: correction asked by the person on the phone':
        'Exemple : correction demandée par la personne au téléphone',
    'Click a question to change its answer. The questions changed are shown in bold; each one is written in the history (Surveys > RLQ reports > Manual changes of answers).':
        "Cliquez sur une question pour changer sa réponse. Les questions modifiées sont en gras ; chacune est inscrite dans l'historique (Sondages > Rapports RLQ > Modifications manuelles des réponses).",
    'Save the changes':
        'Enregistrer les changements',
    'Cancel':
        'Annuler',
    'Manual changes of answers':
        'Modifications manuelles des réponses',
    'Send the update by e-mail':
        'Envoyer la mise à jour par courriel',
    'Manual change of a survey answer':
        "Modification manuelle d'une réponse de sondage",
    'Not sent yet':
        'Pas encore envoyées',
    'Sent':
        'Envoyées',
    'Date of the change':
        'Date de la modification',
    'Changed by':
        'Modifié par',
    'No manual change yet.':
        "Aucune modification manuelle pour l'instant.",
    'To change an answer: Surveys > RLQ reports > Edit answers, open the participation, then « Edit the answers ».':
        'Pour changer une réponse : Sondages > Rapports RLQ > Modifier des réponses, ouvrez la participation, puis « Modifier les réponses ».',
    'Edit answers':
        'Modifier des réponses',
    'Open a participation, then click « Edit the answers ».':
        'Ouvrez une participation, puis cliquez « Modifier les réponses ».',
    'Manual changes':
        'Modifications manuelles',
    'Update sent to %(count)s person(s).':
        'Mise à jour envoyée à %(count)s personne(s).',
    '%(count)s answer(s) changed; the changes are in the history.':
        "%(count)s réponse(s) modifiée(s) ; les changements sont dans l'historique.",
    'The history of the manual changes cannot be modified.':
        "L'historique des modifications manuelles ne peut pas être modifié.",
    'Only a survey administrator can send the update of the answers.':
        'Seul un administrateur des sondages peut envoyer la mise à jour des réponses.',
    'The selected changes have already been sent.':
        'Les modifications sélectionnées ont déjà été envoyées.',
    'Not sent (no e-mail address): %(names)s.':
        'Non envoyée (aucune adresse courriel) : %(names)s.',
    'Update of the answers':
        'Mise à jour des réponses',
    'Only a survey administrator can change the answers of a participation.':
        "Seul un administrateur des sondages peut modifier les réponses d'une participation.",
    'No answer was changed.':
        "Aucune réponse n'a été modifiée.",
    'Answers saved':
        'Réponses enregistrées',
    'The update was sent to %(email)s.':
        'La mise à jour a été envoyée à %(email)s.',
    'No e-mail sent: the person has no e-mail address.':
        "Aucun courriel envoyé : la personne n'a pas d'adresse courriel.",
    'Changed on':
        'Modifié le',
    'Participation':
        'Participation',
    'Deleting the participation deletes its history too (personal data).':
        'Supprimer la participation supprime aussi son historique (renseignements personnels).',
    'Name (or e-mail address) of the person, at the time of the change.':
        'Nom (ou adresse courriel) de la personne, au moment de la modification.',
    'E-mail address':
        'Adresse courriel',
    'Question':
        'Question',
    'Question title':
        'Titre de la question',
    'Title of the question at the time of the change, kept if the question is deleted.':
        'Titre de la question au moment de la modification, conservé si la question est supprimée.',
    'Answer before':
        'Réponse avant',
    'Answer after':
        'Réponse après',
    'Reason':
        'Motif',
    'Sent to the person on':
        'Envoyé à la personne le',
    'Sent by':
        'Envoyé par',
    'Number of manual changes':
        'Nombre de modifications manuelles',
    'Changes (e-mail)':
        'Changements (courriel)',
    'The manual changes put in the update e-mail sent to the person (question, answer before, answer after).':
        'Les modifications manuelles mises dans le courriel de mise à jour envoyé à la personne (question, réponse avant, réponse après).',
    'Edit the answers of a participation':
        "Modifier les réponses d'une participation",
    'Questions':
        'Questions',
    'Reason of the change':
        'Motif de la modification',
    'Written in the history with each question changed (optional).':
        "Inscrit dans l'historique avec chaque question modifiée (facultatif).",
    'Send the update by e-mail to the person':
        'Envoyer la mise à jour par courriel à la personne',
    'After saving, the person receives the list of the changes, then all their answers as they are now.':
        "Après l'enregistrement, la personne reçoit la liste des changements, puis toutes ses réponses telles qu'elles sont maintenant.",
    'Edit':
        'Modification',
    'Sequence':
        'Séquence',
    'Type of question':
        'Type de question',
    'Comment allowed':
        'Commentaire permis',
    'Can be changed':
        'Modifiable',
    'Current answer':
        'Réponse actuelle',
    'Answer (cannot be changed here)':
        'Réponse (non modifiable ici)',
    'New answer':
        'Nouvelle réponse',
    'New number':
        'Nouveau nombre',
    'New value of the scale':
        "Nouvelle valeur de l'échelle",
    'New date':
        'Nouvelle date',
    'New date and time':
        'Nouvelles date et heure',
    'New choice':
        'Nouveau choix',
    'New choices':
        'Nouveaux choix',
    'Comment or « Other » answer':
        'Commentaire ou réponse « Autre »',
    'No answer':
        'Aucune réponse',
    'Removes the answer to this question: the question becomes « skipped ».':
        'Retire la réponse à cette question : la question devient « sautée ».',
    'New answer (text)':
        'Nouvelle réponse (texte)',
    'Changed':
        'Modifiée',
    # views/event_survey_followup_views.xml (v1.128.0)
    'Surveys not completed':
        'Sondages non complétés',
    'Event date':
        "Date de l'événement",
    'Confirmed registrations whose person has not completed the survey of their ticket (otherwise the survey of the event) yet. A survey belongs to a registration when it was answered by the same contact or with the same e-mail address.':
        "Inscriptions confirmées dont la personne n'a pas encore complété le sondage de son billet (sinon celui de l'événement). Un sondage est rattaché à une inscription quand il a été rempli par le même contact ou avec la même adresse courriel.",
    'Close':
        'Fermer',
    'Survey follow-up and daily report':
        'Suivi des sondages et rapport quotidien',
    'Send the daily report now':
        'Envoyer le rapport quotidien maintenant',
    'Surveys not completed (registrations)':
        'Sondages non complétés (inscriptions)',
    # v1.128.0
    'Marked present by':
        'Marqué présent par',
    'User who marked this person present (button « Present » of the RLQ registration desk, or the registration desk of Odoo). Cleared when the presence is undone.':
        "Utilisateur qui a marqué cette personne présente (bouton « Présent » du bureau d'inscription RLQ, ou bureau d'inscription d'Odoo). Effacé quand la présence est annulée.",
    'Label of the type, as translated by the Surveys application.':
        "Libellé du type, tel que traduit par l'application Sondages.",
    'Answer after the change':
        'Réponse après la modification',
    'The new answer, only for the questions changed; empty when the answer is unchanged.':
        "La nouvelle réponse, seulement pour les questions modifiées ; vide quand la réponse n'a pas changé.",
    # v1.129.0
    "Title of the question, on several lines when it is long.":
        "Titre de la question, sur plusieurs lignes quand il est long.",
    # rlq.volunteer.coordinator
    "Volunteers": "Bénévoles",
    "Volunteers: %(event)s": "Bénévoles : %(event)s",
    "Lists only the volunteers whose survey is in this state.": "Liste seulement les bénévoles dont le sondage est dans cet état.",
    "Order of the table. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by name.":
        "Ordre du tableau. Les majuscules et les accents sont ignorés (« Élise » est classée avec les « e ») ; à valeur égale, le tri se fait par nom.",
    "Type": "Type",
    "Languages spoken": "Langues parlées",
    "Number of roles": "Nombre de rôles",
    "Reverses the order of the table.": "Inverse l'ordre du tableau.",
    "No question about the roles (title containing « rôle ») in the survey « %(survey)s ».":
        "Aucune question sur les rôles (titre contenant « rôle ») dans le sondage « %(survey)s ».",
    "No question about the languages (title containing « langue ») in the survey « %(survey)s ».":
        "Aucune question sur les langues (titre contenant « langue ») dans le sondage « %(survey)s ».",
    "The survey « %(survey)s » has no question about the type (on site or online): the type is deduced from the roles questions that the volunteer answered.":
        "Le sondage « %(survey)s » n'a pas de question sur le type (présentiel ou virtuel) : le type est déduit des questions sur les rôles auxquelles le bénévole a répondu.",
    "No question about the type (on site or online) in the survey « %(survey)s ».":
        "Aucune question sur le type (présentiel ou virtuel) dans le sondage « %(survey)s ».",
    "Some volunteer tickets have no survey: their volunteers are listed without answers.":
        "Certains billets bénévoles n'ont pas de sondage : leurs bénévoles sont listés sans réponses.",
}

terms = OrderedDict()          # msgid -> {"refs": [..], "python": bool}


def add(msgid, ref, python=False):
    msgid = " ".join(msgid.split())
    if not msgid:
        return
    entry = terms.setdefault(msgid, {"refs": [], "python": False})
    if ref not in entry["refs"]:
        entry["refs"].append(ref)
    entry["python"] = entry["python"] or python


# 1. views
VIEW_FILES = ("views/event_registration_desk_views.xml", "views/survey_answer_edit_views.xml", "views/event_survey_followup_views.xml")
MODEL_FILES = ("event_registration_desk.py", "volunteer_coordinator.py", "survey_answer_edit.py", "volunteer_expertise.py", "audience_topics.py", "survey_device.py", "survey_live_session.py")
records = [record for view_file in VIEW_FILES for record in ET.parse("%s/%s" % (root_dir, view_file)).getroot()]
for record in records:
    xmlid = record.get("id")
    if record.tag == "menuitem":
        add(record.get("name"), "model:ir.ui.menu,name:%s.%s" % (MODULE, xmlid))
        continue
    model = record.get("model")
    if model in ("ir.actions.act_window", "ir.actions.act_url"):
        add(record.find("field[@name='name']").text, "model:%s,name:%s.%s" % (model, MODULE, xmlid))
    elif model == "ir.ui.view":
        ref = "model_terms:ir.ui.view,arch_db:%s.%s" % (MODULE, xmlid)
        arch = record.find("field[@name='arch']")
        for node in arch.iter():
            for attribute in ("string", "placeholder", "confirm", "help", "title"):
                if node.get(attribute):
                    add(node.get(attribute), ref)
            if node.tag in ("p", "span", "div", "label", "h1", "h2", "h3") and (node.text or "").strip():
                add(xml_escape(node.text), ref)          # text of a view: Odoo keeps it XML-escaped (see FR_FOR)
        continue
    for field_name in ("help",):
        node = record.find("field[@name='%s']" % field_name)
        if node is not None and model == "ir.actions.act_window":
            for paragraph in node.iter("p"):
                if (paragraph.text or "").strip():
                    add(xml_escape(paragraph.text), "model:ir.actions.act_window,help:%s.%s" % (MODULE, xmlid))


# 2. model fields and 3. _() calls
def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


for filename in MODEL_FILES:
    source = open("%s/models/%s" % (root_dir, filename), encoding="utf-8").read()
    module_ast = ast.parse(source)
    code_ref = "code:addons/%s/models/%s:0" % (MODULE, filename)
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args:
            text = literal(node.args[0])
            if isinstance(text, str):
                add(text, code_ref, python=True)
    for cls in [n for n in module_ast.body if isinstance(n, ast.ClassDef)]:
        attrs = {t.id: literal(s.value) for s in cls.body if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)}
        model = attrs.get("_name") or attrs.get("_inherit")
        if not model:
            continue
        under = model.replace(".", "_")
        if attrs.get("_name") and attrs.get("_description"):
            add(attrs["_description"], "model:ir.model,name:%s.model_%s" % (MODULE, under))
        for stmt in cls.body:
            if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)):
                continue
            func = stmt.value.func
            if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "fields"):
                continue
            field = stmt.targets[0].id
            kwargs = {k.arg: literal(k.value) for k in stmt.value.keywords}
            assert kwargs.get("string"), "field %s.%s has no string" % (model, field)
            add(kwargs["string"], "model:ir.model.fields,field_description:%s.field_%s__%s" % (MODULE, under, field))
            if kwargs.get("help"):
                add(kwargs["help"], "model:ir.model.fields,help:%s.field_%s__%s" % (MODULE, under, field))
            if func.attr == "Selection" and stmt.value.args:
                for value, label in literal(stmt.value.args[0]) or ():
                    add(label, "model:ir.model.fields.selection,name:%s.selection__%s__%s__%s" % (MODULE, under, field, value))



def fr_for(msgid):
    """French translation of a term. v1.129.0: the TEXT of a view (between tags, not an attribute) is stored by Odoo as XML
    (odoo/tools/translate.py, serialize_xml: « > » becomes « &gt; », « & » becomes « &amp; »), so its msgid and its msgstr
    must be escaped the same way, otherwise Odoo never finds the translation (seen: « Click a question... (Surveys >
    RLQ reports > ...) » stayed in English). FR is written with plain characters."""
    if msgid in FR:
        return FR[msgid]
    raw = xml_unescape(msgid)
    return xml_escape(FR[raw]) if raw in FR else None


missing = [t for t in terms if fr_for(t) is None]
assert not missing, "no French translation for: %r" % missing
unused = [t for t in FR if t not in terms and xml_escape(t) not in terms]
assert not unused, "translation without term: %r" % unused

# base file: header + entries; code entries get the « odoo-python » comment that Odoo requires to load them
base = open(base_po, encoding="utf-8").read().rstrip("\n")
header, _sep, body = base.partition("\n\n#. module:")
blocks = ["#. module:" + block for block in body.split("\n\n#. module:")]
out = []
for block in blocks:
    lines = block.split("\n")
    msgid = re.search(r'^msgid "(.*)"$', block, re.M).group(1)
    if any(line.startswith("#: code:") for line in lines) and "#. odoo-python" not in lines:
        lines.insert(1, "#. odoo-python")
    if msgid in terms:                                       # same English text already in the base file: add the references
        extra = terms.pop(msgid)
        assert re.search(r'^msgstr "(.*)"$', block, re.M).group(1) == fr_for(msgid), "different translation for %r" % msgid
        if extra["python"] and "#. odoo-python" not in lines:
            lines.insert(1, "#. odoo-python")
        at = max(i for i, line in enumerate(lines) if line.startswith("#"))
        lines[at + 1:at + 1] = ["#: " + ref for ref in extra["refs"] if "#: " + ref not in lines]
    out.append("\n".join(lines))
for msgid, entry in terms.items():
    lines = ["#. module: %s" % MODULE] + (["#. odoo-python"] if entry["python"] else [])
    lines += ["#: " + ref for ref in entry["refs"]]
    assert '"' not in msgid and '"' not in fr_for(msgid) and "\\" not in msgid
    lines += ['msgid "%s"' % msgid, 'msgstr "%s"' % fr_for(msgid)]
    out.append("\n".join(lines))
open(root_dir + "/i18n/fr.po", "w", encoding="utf-8").write(header + "\n\n" + "\n\n".join(out) + "\n")
ids = re.findall(r'^msgid "(.+)"$', "\n".join(out), re.M)
assert len(ids) == len(set(ids)), "duplicate msgid"
print("entries:", len(out), "- desk/volunteers terms:", len(FR))
