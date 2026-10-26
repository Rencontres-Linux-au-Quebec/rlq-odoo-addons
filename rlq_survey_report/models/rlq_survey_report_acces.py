# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
rlq_survey_report_acces.py
===========================

Historique d'accès aux rapports de sondage : une entrée créée à chaque
affichage à l'écran ET à chaque téléchargement/export d'un rapport - qui,
quand, quelle action, quel fichier le cas échéant. Objectif : traçabilité
des accès aux renseignements personnels contenus dans ces rapports (bonne
pratique de responsabilisation en matière de protection des renseignements
personnels).

ATTENTION - PORTÉE DE CETTE FONCTIONNALITÉ (à lire avant de s'y fier pour une
obligation légale précise) : la Loi 25 impose explicitement la tenue d'un
REGISTRE DES INCIDENTS DE CONFIDENTIALITÉ (art. 3.5) - un concept différent
d'un journal de CHAQUE accès légitime à un rapport. Cet historique-ci est une
bonne pratique de traçabilité/responsabilisation, utile en cas d'incident
(savoir qui a consulté quoi et quand) et pour démontrer une gouvernance
sérieuse des renseignements personnels, mais ne doit pas être présenté comme
LE registre d'incidents exigé par la loi - celui-ci reste à tenir séparément
(et porte sur les incidents eux-mêmes, pas sur les accès normaux). À
confirmer avec un conseiller juridique si vous voulez vous appuyer dessus
pour une obligation précise.

Cet historique n'est PAS chiffré ni protégé par mot de passe comme les
rapports eux-mêmes - il ne contient pas de renseignements personnels sur les
PARTICIPANTS (seulement sur la personne qui a généré/consulté le rapport, et
le nom du fichier), mais reste à traiter avec la même prudence d'accès que le
reste de ce module (accès restreint au même groupe que le rapport lui-même).

DEPUIS v1.80.0 - DOUBLE COMME BIBLIOTHÈQUE DE FICHIERS RÉUTILISABLES : chaque
entrée (y compris pour un simple affichage à l'écran, désormais aussi
sauvegardé en fichier - sur demande) porte sa PROPRE COPIE du contenu du
fichier (`fichier_telecharger`), téléchargeable directement depuis la
liste. Les copies ANONYMISÉES ne sont plus purgées automatiquement (sur
demande explicite - conservées jusqu'à suppression manuelle) ; les copies
NON anonymisées, elles, restent purgées après quelques jours comme avant
(voir `_cron_purger_pieces_jointes` dans le wizard) - cohérent avec le
principe de minimisation : les copies dépersonnalisées comportent moins de
risque à conserver, les copies avec noms réels, non.

CORRECTIF CRITIQUE (v1.83.0) : la version précédente (v1.80.0) exposait ce
téléchargement via un champ RELATED pointant vers `attachment_id.datas`
(la pièce jointe elle-même), accompagné d'une règle d'accès (ir.rule) sur
`ir.attachment` pour permettre à d'autres utilisateurs du groupe Sondage de
le télécharger. CETTE RÈGLE A CAUSÉ UNE RÉGRESSION GRAVE EN PRODUCTION :
une règle ir.rule liée à un groupe ne fait jamais qu'AJOUTER une
permission - elle RESTREINT l'accès du groupe visé à ce que sa condition
autorise, POUR TOUT LE MODÈLE, PAS SEULEMENT POUR CE CAS D'USAGE. Résultat
concret signalé : plus aucune personne du groupe Sondage ne pouvait voir
ses propres images déjà téléversées ailleurs dans Odoo (ex. pour un site
web), avec un message d'erreur nommant explicitement cette règle. Retiré
IMMÉDIATEMENT (voir NOTES_VALIDATION.md pour le détail complet) et
remplacé par la copie directe du contenu (`fichier_telecharger`, un champ
Binary normal, PAS related) sur CETTE entrée d'historique elle-même -
gouvernée uniquement par les droits d'accès de ce modèle (déjà corrects),
sans jamais toucher aux droits de `ir.attachment` en général. Coût : le
contenu du fichier est désormais dupliqué (une fois dans la pièce jointe
`attachment_id`, une fois ici) - un compromis de stockage jugé nettement
préférable à un risque de régression sur l'accès aux pièces jointes de
tout Odoo.

ATTENTION - CROISSANCE NON BORNÉE : sans purge automatique pour les copies
anonymisées, chaque génération à l'écran (y compris un essai de filtre
abandonné) laisse désormais un fichier permanent sur le serveur (en double,
voir ci-dessus). Si le volume devient un problème, le nettoyage se fait en
supprimant l'entrée d'historique correspondante (ce qui libère aussi
`fichier_telecharger`) via un accès administrateur.
"""

from odoo import fields, models


class RlqSurveyReportAcces(models.Model):
    _name = "rlq.survey.report.acces"
    _description = "Historique d'accès aux rapports de sondage"
    _order = "date_acces desc"
    _log_access = False  # pas besoin de create_uid/write_uid/write_date - date_acces et user_id jouent déjà ce rôle, sans le doublonner

    user_id = fields.Many2one(
        "res.users", string="Utilisateur", required=True, readonly=True, ondelete="restrict",
        help="Qui a généré/téléchargé ce rapport - JAMAIS modifiable après coup, "
             "pour que cet historique reste digne de confiance en cas de besoin.",
    )
    date_acces = fields.Datetime(
        string="Date et heure", required=True, readonly=True, default=fields.Datetime.now,
    )
    action = fields.Selection(
        [
            ("ecran", "Affiché à l'écran"),
            ("html", "Téléchargé (HTML)"),
            ("pdf", "Téléchargé (PDF)"),
            ("excel", "Exporté (Excel)"),
        ],
        string="Action", required=True, readonly=True,
    )
    nom_fichier = fields.Char(
        string="Nom du fichier", readonly=True,
        help="Nom du fichier - voir aussi le champ Télécharger pour récupérer le "
             "fichier lui-même s'il existe toujours (fichier_telecharger).",
    )
    attachment_id = fields.Many2one(
        "ir.attachment", string="Pièce jointe (référence)", readonly=True, ondelete="set null",
        help="Pièce jointe créée pour ce téléchargement/affichage, à titre de "
             "référence/traçabilité seulement - le téléchargement depuis cette "
             "liste utilise le champ « Télécharger » ci-dessous (une copie "
             "indépendante conservée sur CETTE entrée), pas cette pièce jointe "
             "directement, pour ne jamais dépendre des droits d'accès génériques "
             "de ir.attachment (voir l'avertissement en tête de ce fichier).",
    )
    fichier_telecharger = fields.Binary(
        string="Télécharger", readonly=True, attachment=False,
        help="Copie indépendante du fichier généré, gouvernée uniquement par les "
             "droits d'accès de CETTE liste (pas ceux de ir.attachment en "
             "général) - voir l'avertissement en tête de ce fichier pour "
             "pourquoi ce choix de conception précis.",
    )
    anonymise = fields.Boolean(string="Anonymisé", readonly=True)
    nb_sondages = fields.Integer(string="Nombre de sondages inclus", readonly=True)
    resume_sondages = fields.Text(
        string="Dates des sondages inclus", readonly=True,
        help="TOUTES les dates des rencontres/sondages inclus dans ce rapport "
             "(pas les titres, délibérément - trop long à lire pour un rapport "
             "couvrant de nombreuses rencontres) - réparties sur deux lignes si la "
             "liste est longue, plutôt que tronquées, pour ne rien omettre.",
    )

    def name_get(self):
        resultat = []
        for rec in self:
            libelle_action = dict(rec._fields["action"].selection).get(rec.action, rec.action)
            resultat.append((rec.id, f"{rec.date_acces} — {rec.user_id.name} — {libelle_action}"))
        return resultat
