# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Rapport de sondage mensuel",
    "summary": "Rapport HTML (synthèse + par participant) pour les sondages "
               "mensuels Rencontres Linux au Québec, directement à partir "
               "des données natives du module Sondages (survey).",
    "description": """
Rapport de sondage - Rencontres Linux au Québec
================================================

Génère, depuis le backend Odoo, un rapport HTML combinant :

* Une synthèse toutes rencontres confondues et le détail par rencontre
  (moyennes, statistiques descriptives, ventilation des notes, graphique
  d'évolution dans le temps).
* Une fiche par participant, regroupant ses réponses à travers toutes
  les rencontres auxquelles il a répondu.
* Le repérage des adresses courriel invalides des inscriptions aux
  événements (correction suggérée, menu « Courriels invalides » pour
  corriger l'inscription et le contact puis renvoyer les courriels).
* La liste des courriels des inscrits qui n'ont pas encore rempli le
  sondage de leur billet (Événements > Sondages non complétés) et un
  rapport quotidien par courriel (inscriptions, statistiques des
  sondages), activable événement par événement.
* Des exports HTML, PDF et Excel protégés par mot de passe (Loi 25,
  RGPD), une section "À surveiller" pour repérer rapidement les pistes
  d'amélioration, et une anonymisation optionnelle des participants.

Ce module lit directement les enregistrements survey.user_input et
survey.user_input_line : les libellés de questions, les courriels des
participants et les dates sont donc exacts et à jour automatiquement,
sans ressaisie ni ré-import.

Voir doc/CONTEXTE.md pour une vue d'ensemble du projet, doc/CHANGELOG.md
pour l'historique complet des versions, et doc/NOTES_VALIDATION.md pour
les points à vérifier avant une mise en production (le module a été écrit sans accès direct à une
instance Odoo pour le tester).

Copyright (C) 2026 Services-Conseils Linux Inc. (contact@exemple.org)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.114.0",
    "category": "Marketing/Surveys",
    "author": "Services-Conseils Linux Inc. (contact@exemple.org), Rencontres Linux au Québec contributors",
    "maintainer": "Étienne Bérubé <contact@exemple.org>, <contact@exemple.org>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["survey", "mail", "event"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_purge.xml",
        "data/ir_cron_etiquettes_groupes.xml",
        "data/ir_cron_synchro_sondages.xml",
        "data/ir_cron_daily_report.xml",
        "data/ir_config_parameter_aide.xml",
        "data/ir_config_parameter_mot_de_passe.xml",
        "data/mail_template_reponses.xml",
        "data/ir_config_parameter_courriel_inscriptions.xml",
        "data/ir_config_parameter_registration_email.xml",
        "views/report_templates.xml",
        "views/rlq_survey_report_views.xml",
        "views/event_ticket_survey_views.xml",
        "views/event_inscriptions_alerte_views.xml",
        "views/event_groupes_inscrits_views.xml",
        "views/event_registration_email_views.xml",
        "views/event_survey_followup_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "rlq_survey_report/static/src/css/historique_fichiers.css",
        ],
    },
    "installable": True,
    "application": False,
}
