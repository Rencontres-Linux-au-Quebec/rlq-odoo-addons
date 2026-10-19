# -*- coding: utf-8 -*-
"""
survey_survey.py
=================

Extension de survey.survey ajoutant quelques statistiques utiles pour
choisir un sondage dans le wizard de rapport RLQ. Tous les champs ajoutés
sont stockés (store=True) pour permettre le tri par un clic sur l'en-tête
de colonne dans la liste de sélection - aucune donnée existante n'est
modifiée, et aucune vue du module Sondage d'origine n'est touchée (seule
notre propre vue affiche ces champs).

IMPORTANT : `answer_count`/`answer_done_count` (natifs, non stockés dans
le module Sondage d'origine) ne sont PAS redéclarés ici avec store=True -
une tentative en ce sens (v1.26.0) a provoqué un avertissement Odoo
("inconsistent 'store' for computed fields") visible sur l'ensemble de
l'instance, pas seulement ce module. `rlq_answer_count`/
`rlq_answer_done_count` (nos propres champs, calculés indépendamment)
leur servent de copies triables à la place.

Autres champs Odoo natifs réutilisés (vérifiés sur le code source
d'Odoo 18 CE) :
  - create_date : date de création du sondage (toujours présente sur
    tout modèle Odoo) - utilisée à la fois comme colonne "Date de
    création" et comme repli d'année pour la date extraite du titre,
    à la place d'une détection de "date d'envoi" qui s'est avérée
    infructueuse sur cette instance (aucun champ de ce genre trouvé).
  - start_datetime / end_datetime (sur survey.user_input) : bornes
    utilisées pour calculer nous-mêmes la durée moyenne, plutôt que de
    réutiliser le champ natif answer_duration_avg dont le périmètre
    exact (sondages terminés uniquement, ou non) n'a pas pu être
    vérifié avec certitude. Réutilisées aussi (v1.86.0) comme "date de
    réponse" affichée par participant dans le rapport (voir
    rlq_survey_report_wizard.py) - déjà confirmées fiables ici.
  - deadline (sur survey.user_input) : date limite de réponse propre à
    CETTE invitation précise - confirmée par le code source d'Odoo
    (plusieurs versions, dont un correctif dédié à son comportement),
    mais son usage précis DANS CE MODULE (v1.86.0, affichée par
    participant) n'a pas été testé sur une instance réelle.
  - test_entry (sur survey.user_input) : indique une entrée de test
    (créée via le bouton "Tester" plutôt que par un vrai répondant) -
    confirmé par le code source d'Odoo (paramètre de
    `_create_answer()`), mais son affichage dans le rapport (v1.86.0)
    n'a pas été testé sur une instance réelle.

`SurveyUserInput` ci-dessous (v1.86.0) ajoute `rlq_commentaire_staff`,
un champ libre pour qu'un membre de l'équipe (rôle Sondage : Utilisateur
ou plus) commente la réponse d'UNE personne précise - la vue qui
l'expose sur le formulaire de survey.user_input cible l'external ID
`survey.survey_user_input_view_form`, choisi par analogie avec
`survey.survey_survey_view_form` (confirmé fonctionner sur cette
instance pour survey.survey) mais PAS confirmé lui-même - voir
NOTES_VALIDATION.md.

© Services-Linux Conseils Inc — Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com
Licence : AGPL-3
"""

from odoo import api, fields, models

# Durée moyenne plafonnée à cette valeur (secondes) pour l'affichage en
# liste - une valeur aberrante (ex. une session laissée ouverte des jours)
# ne doit pas rendre la colonne illisible.
_DUREE_MAX_AFFICHEE = 999

_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


class SurveySurvey(models.Model):
    _inherit = "survey.survey"

    # NE JAMAIS redéclarer answer_count/answer_done_count avec store=True :
    # tenté en v1.26.0 pour les rendre triables, mais Odoo a émis un
    # avertissement "inconsistent 'store' for computed fields" affectant le
    # REGISTRE ENTIER (pas seulement ce module) dès qu'un champ quelconque
    # ailleurs dans Odoo (ex. res.lang) déclenchait leur recalcul - visible
    # même sur des pages n'ayant aucun rapport avec les sondages. Retiré
    # immédiatement. Ces deux colonnes restent donc non triables dans la
    # liste de sélection - un compromis acceptable face à la gravité du
    # problème que leur redéclaration causait.

    rlq_answer_count = fields.Integer(
        string="Inscrit", compute="_compute_rlq_stats", store=True,
        help="Nombre total de réponses (tous statuts) - copie triable de answer_count, "
             "qui n'est pas stocké par le module Sondage d'origine et ne peut donc pas "
             "être trié par un clic sur l'en-tête de colonne.",
    )
    rlq_answer_done_count = fields.Integer(
        string="Terminé", compute="_compute_rlq_stats", store=True,
        help="Nombre de réponses terminées (state='done') - copie triable de "
             "answer_done_count, pour la même raison que ci-dessus.",
    )
    rlq_answer_in_progress_count = fields.Integer(
        string="Débuté sans terminer", compute="_compute_rlq_stats", store=True,
        help="Nombre de réponses en cours (statut 'in_progress') : la personne a "
             "commencé le sondage mais ne l'a pas terminé.",
    )
    rlq_answer_duration_avg_seconds = fields.Integer(
        string="Durée moyenne (secondes)", compute="_compute_rlq_stats", store=True,
        help=f"Durée moyenne pour remplir le sondage, en secondes - calculée "
             f"uniquement sur les réponses au statut 'Terminé' (state='done'), "
             f"plafonnée à {_DUREE_MAX_AFFICHEE} secondes pour l'affichage.",
    )
    rlq_question_count = fields.Integer(
        string="Nombre de questions", compute="_compute_rlq_question_count", store=True,
        help="Nombre de questions dans ce sondage (question_ids), pour avoir une "
             "idée de sa longueur avant de le sélectionner.",
    )
    rlq_date_titre = fields.Date(
        string="Date (titre)", compute="_compute_rlq_date_titre", store=True,
        help="Date extraite du titre du sondage (ex. « 4 août 2026 » ou « 17 avril » "
             "sans année, complétée avec l'année de création du sondage si besoin) - "
             "stockée pour permettre le tri par cette colonne.",
    )
    rlq_jour_semaine = fields.Char(
        string="Jour de la semaine", compute="_compute_rlq_date_titre", store=True,
        help="Jour de la semaine (mardi, vendredi...) correspondant à la date "
             "extraite du titre - vide si aucune date n'a pu en être extraite.",
    )
    rlq_actions_suivi = fields.Text(
        string="Actions de suivi (amélioration continue)",
        help="Notes libres sur les actions entreprises suite aux commentaires ou "
             "signaux de CETTE rencontre (ex. « Projecteur remplacé suite aux "
             "plaintes » ) - PAS calculé, à remplir manuellement ici. Champ "
             "PERSISTANT (contrairement au rapport lui-même, généré à la volée à "
             "chaque fois) : le rapport de rlq_survey_report rappelle ces notes en "
             "tête de la section de cette rencontre, pour fermer la boucle "
             "Plan-Do-Check-Act d'une rencontre à l'autre plutôt que de se limiter "
             "au diagnostic.",
    )

    @api.depends("question_ids")
    def _compute_rlq_question_count(self):
        for survey in self:
            survey.rlq_question_count = len(survey.question_ids)

    @api.depends("title", "create_date")
    def _compute_rlq_date_titre(self):
        """Réutilise la logique déjà écrite et testée dans le wizard
        (extraction de date depuis le titre) plutôt que de la dupliquer ici -
        appelée sur un recordset vide du modèle du wizard, un patron standard
        pour invoquer une méthode utilitaire qui ne dépend pas de `self`
        avoir un id réel.

        L'année de repli (quand le titre omet l'année, ex. « 31 juillet »)
        utilise directement `create_date` - une tentative précédente de
        détecter un champ « date d'envoi » séparé n'a rien trouvé sur cette
        instance ; `create_date`, lui, existe toujours et son horodatage
        (visible dans le fil de discussion du sondage : « Sondage créé »)
        correspond à ce que l'utilisateur souhaite voir ici."""
        assistant = self.env["rlq.survey.report.wizard"]
        for survey in self:
            annee_repli = survey.create_date.year if survey.create_date else None
            date_titre = assistant._extraire_date_titre(survey.title, annee_repli=annee_repli)
            survey.rlq_date_titre = date_titre
            survey.rlq_jour_semaine = _JOURS_FR[date_titre.weekday()] if date_titre else False

    @api.depends("user_input_ids.state", "user_input_ids.start_datetime", "user_input_ids.end_datetime")
    def _compute_rlq_stats(self):
        for survey in self:
            user_inputs = survey.user_input_ids
            survey.rlq_answer_count = len(user_inputs)
            termine = user_inputs.filtered(lambda ui: ui.state == "done")
            survey.rlq_answer_done_count = len(termine)
            survey.rlq_answer_in_progress_count = len(
                user_inputs.filtered(lambda ui: ui.state == "in_progress")
            )
            terminees = termine.filtered(lambda ui: ui.start_datetime and ui.end_datetime)
            durees = [
                (ui.end_datetime - ui.start_datetime).total_seconds()
                for ui in terminees
                if ui.end_datetime > ui.start_datetime
            ]
            moyenne = int(round(sum(durees) / len(durees))) if durees else 0
            survey.rlq_answer_duration_avg_seconds = min(moyenne, _DUREE_MAX_AFFICHEE)


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    rlq_commentaire_staff = fields.Text(
        string="Commentaire (interne)",
        help="Note libre ajoutée par un membre de l'équipe (rôle Sondage : "
             "Utilisateur ou plus) à propos de CETTE réponse précise d'UNE "
             "personne - pas calculé, à remplir manuellement ici. Rappelé dans "
             "le rapport de rlq_survey_report, dans le détail des soumissions "
             "de cette personne, une fois généré - contrairement à \"Actions de "
             "suivi\" (sur survey.survey, à propos de toute la rencontre), ce "
             "commentaire-ci porte sur la réponse d'une SEULE personne.",
    )
