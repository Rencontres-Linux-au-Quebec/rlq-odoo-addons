# -*- coding: utf-8 -*-
"""
rlq_survey_report_wizard.py
============================

Assistant (wizard) backend générant le rapport HTML directement à partir
des enregistrements natifs du module "survey" (survey.survey,
survey.question, survey.user_input, survey.user_input_line), sans passer
par un export Excel.

ATTENTION - CHAMPS À VALIDER SUR VOTRE INSTANCE
------------------------------------------------
Ce fichier a été écrit sans accès à une instance Odoo pour le tester. Il
suppose la structure standard du module "survey" d'Odoo 18 CE :

  survey.question
    - title, question_type, sequence, survey_id
    - suggested_answer_ids  -> options / colonnes (survey.question.answer)
    - matrix_row_ids        -> lignes d'une question matricielle (idem modèle)

  survey.question.answer
    - value                 -> texte affiché de l'option ou de la ligne

  survey.user_input
    - survey_id, partner_id, email, create_date, state
    - user_input_line_ids

  survey.user_input_line
    - user_input_id, question_id, answer_type
    - value_char_box, value_text_box, value_numerical_box,
      value_date, value_datetime
    - suggested_answer_id   -> option/colonne choisie
    - matrix_row_id         -> ligne choisie (questions matricielles)

Si votre instance (notamment une distribution personnalisée comme
ERPLibre) utilise des noms différents, ajustez les constantes ci-dessous
et les quelques accès directs signalés par un commentaire "# CHAMP".
Voir doc/NOTES_VALIDATION.md pour la procédure de
vérification recommandée avant toute mise en production.

© Services-Linux Conseils Inc — contact@exemple.org, contact@exemple.org
Licence : AGPL-3
"""

from collections import defaultdict
import base64
import hashlib
import io
import secrets

from dateutil.relativedelta import relativedelta
import logging
import re
import time
import unicodedata
from datetime import date as date_cls, datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from markupsafe import Markup

_logger = logging.getLogger(__name__)

# Bibliothèques Python optionnelles, chacune nécessaire seulement à une
# fonctionnalité précise (jamais au fonctionnement de base du module -
# affichage à l'écran, export HTML) : leur absence est donc seulement
# signalée par un avertissement au chargement du module, PAS par une
# dépendance déclarée dans le manifeste (external_dependencies), qui a
# provoqué un incident confirmé en production (v1.51.0) - Odoo refusait
# alors de charger le REGISTRE AU COMPLET dès qu'une seule dépendance
# manquait, bien au-delà du seul blocage de ce module. Un message clair
# apparaît maintenant dans les logs au démarrage - suffisant pour qu'un
# administrateur remarque et installe ce qui manque, sans rien bloquer.
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - selon la version installée sur l'instance
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        PdfReader = PdfWriter = None
        _logger.warning(
            "rlq_survey_report : bibliothèque Python 'pypdf' (ou 'PyPDF2') introuvable - "
            "la protection par mot de passe des exports PDF ne sera pas disponible "
            "tant qu'elle n'est pas installée (pip install pypdf)."
        )

try:
    import pyzipper
except ImportError:  # pragma: no cover - selon la version installée sur l'instance
    pyzipper = None
    _logger.warning(
        "rlq_survey_report : bibliothèque Python 'pyzipper' introuvable - l'export "
        "protégé par mot de passe (Excel) ne sera pas disponible tant qu'elle n'est "
        "pas installée (pip install pyzipper)."
    )

try:
    import openpyxl
except ImportError:  # pragma: no cover - selon la version installée sur l'instance
    openpyxl = None
    _logger.warning(
        "rlq_survey_report : bibliothèque Python 'openpyxl' introuvable - l'export "
        "Excel ne sera pas disponible tant qu'elle n'est pas installée "
        "(pip install openpyxl)."
    )

from . import report_builder as rb  # noqa: E402 - placé après le bloc try/except des bibliothèques optionnelles

MOIS_FR = {
    "janvier": 1, "janv": 1, "jan": 1,
    "février": 2, "fevrier": 2, "févr": 2, "fevr": 2, "fév": 2, "fev": 2,
    "mars": 3, "mar": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "août": 8, "aout": 8, "aoû": 8, "aou": 8,
    "septembre": 9, "sept": 9, "sep": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "dec": 12,
}
# Diminutifs triés du plus long au plus court, pour que l'alternation regex
# privilégie la forme la plus longue (ex. "septembre" avant "sept" avant "sep").
_MOIS_TRIES = sorted(MOIS_FR.keys(), key=len, reverse=True)
_MOTIF_DATE_FR = re.compile(
    r"(\d{1,2})(?:er)?\s+(" + "|".join(re.escape(m) for m in _MOIS_TRIES) + r")\.?(?:\s+(\d{4}))?",
    re.IGNORECASE,
)

# Types de réponse considérés comme "texte libre" pour le dédoublonnage /
# l'attribution d'auteur (section_textes).
TYPES_TEXTE_LIBRE = ("text_box", "char_box")

# Valeur LIVRÉE du paramètre système rlq_survey_report.mot_de_passe_defaut
# (voir data/ir_config_parameter_mot_de_passe.xml) : un simple marqueur, jamais
# accepté comme vrai mot de passe - un administrateur doit la remplacer.
MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER = "!CHANGE-MOI@"

# Où changer ce paramètre - un seul texte, réutilisé par l'avertissement du
# formulaire et par le message d'erreur, pour qu'ils ne divergent jamais. Le
# menu s'appelle « Paramètres » ou « Réglages » selon la version/traduction.
EMPLACEMENT_MOT_DE_PASSE_DEFAUT = (
    "menu Paramètres (ou Réglages) > Technique > Paramètres système, clé "
    "rlq_survey_report.mot_de_passe_defaut (le menu Technique exige le mode développeur)"
)

# Courriel(s) d'attribution d'auteur (pied de page du rapport) : jamais masqués
# par le filet de sécurité générique de _anonymiser_html() - ce n'est pas celui
# d'un participant.
COURRIELS_ATTRIBUTION = ("contact@exemple.org",)

# Clé du paramètre système qui porte le mot de passe par défaut.
CLE_PARAMETRE_MOT_DE_PASSE = "rlq_survey_report.mot_de_passe_defaut"

# Questions d'AUTO-ÉVALUATION (ex. "Débutant" -> 1) à exclure de la
# section "À surveiller" et des graphiques de tendance (recherche par
# mot-clé, insensible à la casse, dans le titre de la question) : une
# note basse à ce type de question ne signale pas un problème à
# corriger, ni une évolution pertinente à suivre, contrairement à une
# note basse/une tendance de satisfaction - ajoutez d'autres mots-clés
# ici au besoin, un par ligne.
MOTS_CLES_QUESTIONS_AUTO_EVALUATION = ("niveau de connaissance",)

# Questions dont les volets sont FIXES et RÉCURRENTS d'une rencontre à
# l'autre (contrairement aux présentations, différentes chaque mois) :
# un tooltip de date sur le nom du volet n'y apporte rien d'utile,
# retiré pour ces questions (recherche par mot-clé, insensible à la
# casse, dans le titre de la question).
MOTS_CLES_VOLETS_FIXES = (
    "satisfaction",
    "organisation et logistique",
    "niveau de connaissance",
    "contenu et expérience linux",
)

# Questions pour lesquelles une tendance PAR ITEM (un graphique séparé
# par volet, en plus du graphique combiné) est utile - typiquement des
# questions à volets fixes/récurrents comportant PLUSIEURS volets
# distincts qu'on veut pouvoir comparer individuellement dans le temps.
MOTS_CLES_TENDANCE_PAR_ITEM = (
    "satisfaction",
    "organisation et logistique",
)

# Les 3 questions combinées pour calculer la "note globale" de chaque
# rencontre - une métrique composite unique permettant de comparer
# facilement toutes les rencontres entre elles, pour l'amélioration
# continue.
MOTS_CLES_NOTE_GLOBALE = (
    "organisation et logistique",
    "satisfaction",
    "présentation",
)


class RlqSurveyReportWizard(models.TransientModel):
    _name = "rlq.survey.report.wizard"
    _description = "Rapport de sondage (synthèse + par participant)"

    survey_ids = fields.Many2many(
        "survey.survey", string="Sondages (rencontres) à inclure", required=True,
        help="Sélectionnez un ou plusieurs sondages mensuels. Chacun est traité "
             "comme une « rencontre » distincte dans le rapport.",
    )
    date_from = fields.Date(
        string="À partir du",
        help="Ne considérer que les réponses soumises à partir de cette date "
             "(inclusivement). Laisser vide pour aucune limite de début.",
    )
    date_to = fields.Date(
        string="Jusqu'au",
        help="Ne considérer que les réponses soumises jusqu'à cette date "
             "(inclusivement). Laisser vide pour aucune limite de fin.",
    )
    filtre_dernieres_heures = fields.Integer(
        string="Limiter aux dernières X heures?", default=0,
        help="0 = aucune limite (défaut). Sinon, ne considère que les réponses "
             "soumises au cours des X dernières heures précédant la génération "
             "de ce rapport - utile pour un suivi à chaud (ex. juste après une "
             "rencontre) sans avoir à ajuster « À partir du »/« Jusqu'au ». "
             "Se combine avec ces deux champs s'ils sont aussi renseignés "
             "(le filtre le plus restrictif des deux s'applique). Reflété dans "
             "le nom du fichier téléchargé (ex. « ...-24h-... »).",
    )
    exclude_partner_ids = fields.Many2many(
        "res.partner", string="Participants à exclure",
        help="Ces personnes et toutes leurs réponses seront exclues du rapport.",
    )
    exclude_tag_ids = fields.Many2many(
        "res.partner.category", string="Exclure par étiquette",
        default=lambda self: self._default_exclude_tag_ids(),
        help="Toute personne portant une de ces étiquettes (sur sa fiche contact) "
             "est exclue du rapport, quel que soit le sondage.",
    )
    exclude_title_keywords = fields.Char(
        string="Exclure les sondages dont le titre contient",
        help="Mots séparés par une virgule. Un sondage sélectionné dont le titre "
             "contient l'un de ces mots (recherche insensible à la casse) est "
             "ignoré - utile pour exclure des sondages de test. Vide par défaut "
             "(retiré en v1.84.0) - un « test » par défaut ici excluait "
             "silencieusement tout sondage contenant ce mot dans son titre, sans "
             "jamais pouvoir le voir dans le rapport, même en le sélectionnant "
             "explicitement.",
    )
    filtre_titre_predefini = fields.Selection([
        ("tous", "Tous les sondages"),
        ("pause_cafe", "Pause café"),
        ("portes_ouvertes", "Portes ouvertes"),
        ("premier_mardi", "Premier mardi du mois"),
        ("autre", "Autre (préciser un mot-clé)"),
    ], string="Filtrer par titre",
       help="Remplace la sélection de sondages ci-dessus par celle correspondant "
            "à la catégorie choisie - un raccourci équivalent aux sous-menus de "
            "sélection rapide, mais utilisable sans quitter ce formulaire. Les "
            "filtres « Sondage terminé » et « Exclure si le titre contient » "
            "ci-dessous s'appliquent en plus, une fois une catégorie choisie.")
    filtre_titre_autre = fields.Char(
        string="Mot-clé personnalisé",
        help="Utilisé seulement si « Autre » est choisi ci-dessus - tout sondage "
             "dont le titre contient ce mot (recherche insensible à la casse) est "
             "sélectionné.",
    )
    filtre_participants_min = fields.Integer(
        string="Minimum ayant débuté ou terminé?", default=1,
        help="N'a d'effet qu'en combinaison avec « Filtrer par titre » "
             "ci-dessus : un sondage de la catégorie choisie ayant reçu moins que ce "
             "nombre de réponses débutées ou terminées (les invitations jamais "
             "ouvertes ne comptent pas) est exclu de la sélection.",
    )
    filtre_exclure_titre_contient = fields.Char(
        string="Exclure si le titre contient",
        help="N'a d'effet qu'en combinaison avec « Filtrer par titre » "
             "ci-dessus : tout sondage de la catégorie choisie dont le titre contient "
             "ce texte (recherche insensible à la casse) est retiré de la sélection.",
    )
    filtre_derniers_mois = fields.Integer(
        string="Sondages des N derniers mois", default=0,
        help="N'a d'effet qu'en combinaison avec « Filtrer par titre » "
             "ci-dessus : ne garde que les sondages dont la date (déduite du titre, "
             "ou de la date de création à défaut) tombe dans les N derniers mois. "
             "0 (par défaut) = aucune limite, tous les sondages de la catégorie sont "
             "gardés peu importe leur ancienneté.",
    )
    filtre_presentateur = fields.Selection(
        selection="_get_presentateurs_disponibles", string="Filtrer par présentateur",
        help="Remplace la sélection de sondages ci-dessus par UNIQUEMENT les "
             "rencontres où ce présentateur a donné au moins une présentation - "
             "utile pour lui envoyer un rapport ciblé (voir « Appréciation des "
             "présentateurs ») sans les autres rencontres. La liste provient de "
             "tous les sondages de la base, pas seulement ceux déjà sélectionnés - "
             "choisir un nom ici sélectionne automatiquement ses rencontres.",
    )

    @api.onchange(
        "filtre_titre_predefini", "filtre_titre_autre", "filtre_participants_min",
        "filtre_exclure_titre_contient", "filtre_derniers_mois",
    )
    def _onchange_filtres_titre(self):
        """Filtre rapide, dans le formulaire : équivalent aux sous-menus de
        sélection rapide (dont il réutilise les méthodes existantes),
        mais utilisable sans rouvrir le formulaire depuis un autre menu.
        Ne fait rien tant qu'aucune catégorie n'est choisie, pour ne pas
        écraser une sélection manuelle de sondages faite par ailleurs."""
        if not self.filtre_titre_predefini:
            return
        if self.filtre_titre_predefini == "tous":
            surveys = self._survey_ids_tous()
        elif self.filtre_titre_predefini == "premier_mardi":
            surveys = self._survey_ids_premier_mardi()
        elif self.filtre_titre_predefini == "pause_cafe":
            surveys = self._survey_ids_pause_cafe()
        elif self.filtre_titre_predefini == "portes_ouvertes":
            surveys = self._survey_ids_portes_ouvertes()
        elif self.filtre_titre_predefini == "autre" and self.filtre_titre_autre:
            surveys = self.env["survey.survey"].search([("title", "ilike", self.filtre_titre_autre)])
        else:
            surveys = self.env["survey.survey"]

        seuil = self.filtre_participants_min if self.filtre_participants_min else 1
        surveys = surveys.filtered(
            lambda s: (s.rlq_answer_done_count + s.rlq_answer_in_progress_count) >= seuil
        )

        mot_exclu = (self.filtre_exclure_titre_contient or "").strip().lower()
        if mot_exclu:
            surveys = surveys.filtered(lambda s: mot_exclu not in (s.title or "").lower())

        if self.filtre_derniers_mois:
            limite = fields.Date.today() - relativedelta(months=self.filtre_derniers_mois)
            surveys = surveys.filtered(lambda s: s.rlq_date_titre and s.rlq_date_titre >= limite)

        self.survey_ids = surveys

    @api.model
    def _get_presentateurs_disponibles(self):
        """Options du champ filtre_presentateur - liste dynamique des
        présentateurs reconnus (voir rb.extraire_presentateur) parmi
        TOUS les sondages de la base (pas seulement ceux actuellement
        sélectionnés dans ce formulaire), pour permettre de choisir un
        nom puis de voir automatiquement toutes ses rencontres, sans
        présélection préalable. Une question matricielle est considérée
        comme une question de présentation si "présentation" apparaît
        dans son titre (même mot-clé que pour la section "Appréciation
        des présentateurs" du rapport, pour rester cohérent)."""
        questions = self.env["survey.question"].search([
            ("question_type", "=", "matrix"), ("title", "ilike", "présentation"),
        ])
        presentateurs = set()
        for question in questions:
            for row in self._get_rows(question):
                _titre, nom = rb.extraire_presentateur(row.value)
                if nom:
                    presentateurs.add(nom)
        return [(nom, nom) for nom in sorted(presentateurs, key=rb.normaliser_nom)]

    @api.onchange("filtre_presentateur")
    def _onchange_filtre_presentateur(self):
        """Quand un présentateur est choisi, remplace la sélection de
        sondages par UNIQUEMENT les rencontres où ce présentateur a
        donné au moins une présentation - cherche parmi TOUS les
        sondages de la base (comme _get_presentateurs_disponibles),
        pas seulement ceux déjà sélectionnés, pour ne pas exiger une
        présélection préalable. Ne fait rien si le champ est vidé, pour
        ne pas écraser une sélection manuelle par un vidage accidentel."""
        if not self.filtre_presentateur:
            return
        questions = self.env["survey.question"].search([
            ("question_type", "=", "matrix"), ("title", "ilike", "présentation"),
        ])
        surveys_du_presentateur = self.env["survey.survey"]
        for question in questions:
            for row in self._get_rows(question):
                _titre, nom = rb.extraire_presentateur(row.value)
                if nom == self.filtre_presentateur:
                    surveys_du_presentateur |= question.survey_id
                    break
        self.survey_ids = surveys_du_presentateur

    include_partial = fields.Boolean(
        string="Inclure les réponses partielles (non terminées)", default=True,
        help="Par défaut, seules les réponses au statut Terminé sont comptées. "
             "Cochez pour inclure aussi celles en cours (commencées mais non "
             "terminées) - les invitations jamais ouvertes ne sont, elles, "
             "jamais comptées comme des réponses.",
    )
    voir_non_repondants = fields.Boolean(
        string="Voir les personnes n'ayant pas répondu", default=False,
        help="Ajoute, pour chaque rencontre, la liste des personnes invitées "
             "au sondage mais n'ayant jamais commencé à y répondre (statut "
             "'Nouveau'). Nécessite que ces invitations existent bien comme "
             "enregistrements dans Odoo (ce qui n'est pas garanti selon la "
             "façon dont les sondages sont envoyés sur cette instance).",
    )
    pdf_tableaux_participants = fields.Boolean(
        string="Tableaux de réponses par participant dans le PDF", default=True,
        help="Décochez pour un très gros rapport (ex. des centaines de participants) "
             "si la génération du PDF échoue ou s'arrête avant la fin - seuls les noms "
             "et coordonnées des participants apparaîtront alors dans le PDF, sans le "
             "tableau détaillé de leurs réponses (le rapport à l'écran, lui, reste "
             "toujours complet quel que soit ce réglage).",
    )
    pdf_saut_page_rencontre = fields.Boolean(
        string="Saut de page forcé par rencontre (PDF)", default=True,
        help="Chaque rencontre commence sur une nouvelle page du PDF. Décochez pour "
             "un document plus compact (les rencontres s'enchaînent alors normalement, "
             "plusieurs par page si leur contenu est court).",
    )
    pdf_saut_page_participant = fields.Boolean(
        string="Saut de page forcé par participant (PDF)", default=True,
        help="Chaque participant commence sur une nouvelle page du PDF. Attention : "
             "pour un très grand nombre de participants (ex. la Journée Portes "
             "Ouvertes), ceci peut produire un document si volumineux que sa "
             "génération échoue ou s'arrête avant la fin - décoché par défaut pour "
             "cette raison, à cocher seulement si vous savez le nombre de "
             "participants raisonnable.",
    )
    mot_de_passe = fields.Char(
        string="Mot de passe du fichier",
        default=lambda self: self._mot_de_passe_par_defaut(),
        help="Pré-rempli avec le mot de passe par défaut (paramètre système "
             "rlq_survey_report.mot_de_passe_defaut), masqué - utilisez « Afficher le mot "
             "de passe » pour le voir. Tant qu'il vaut « !CHANGE-MOI@ » (marqueur livré), "
             "il est refusé : un administrateur doit d'abord le personnaliser. Requis "
             "pour un rapport NON anonymisé (affichage à l'écran, fichier HTML ou PDF) "
             "et TOUJOURS pour l'export Excel (qui contient les vrais noms et courriels, "
             "l'anonymisation ne s'y applique pas) : ces rapports contiennent des "
             "renseignements personnels, à protéger en vertu de la Loi 25 (Québec) et "
             "de réglementations comparables (ex. RGPD en Europe). Jamais requis pour un "
             "rapport anonymisé, affiché à l'écran ou téléchargé en HTML/PDF (livré sans "
             "chiffrement). Demandé deux fois (avec confirmation) pour éviter une erreur "
             "de frappe.",
    )
    mot_de_passe_confirmation = fields.Char(
        string="Confirmer le mot de passe",
        default=lambda self: self._mot_de_passe_par_defaut(),
        help="Pré-rempli comme le mot de passe ci-dessus ; retapez-le exactement si "
             "vous le changez, pour vérifier l'absence d'erreur de frappe.",
    )
    avertissement_mot_de_passe_defaut = fields.Char(
        string="Avertissement mot de passe par défaut",
        compute="_compute_avertissement_mot_de_passe_defaut",
        help="Texte simple (pas de HTML : le widget Html a déjà fait planter "
             "l'interface) affiché en évidence tant que le mot de passe du "
             "formulaire est encore le marqueur livré avec le module.",
    )

    @api.depends("mot_de_passe")
    def _compute_avertissement_mot_de_passe_defaut(self):
        """Non vide seulement tant que le mot de passe du formulaire vaut
        encore le marqueur livré - il disparaît dès qu'on saisit le sien ou
        qu'un administrateur remplace le paramètre système."""
        for wizard in self:
            if wizard.mot_de_passe == MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER:
                wizard.avertissement_mot_de_passe_defaut = _(
                    "⚠ Le mot de passe par défaut n'a pas été changé : « %(valeur)s » est "
                    "un marqueur livré avec le module, il sera refusé. Un administrateur "
                    "doit le définir : %(emplacement)s. Ou saisissez votre propre mot de "
                    "passe dans les champs ci-dessous."
                ) % {
                    "valeur": MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER,
                    "emplacement": EMPLACEMENT_MOT_DE_PASSE_DEFAUT,
                }
            else:
                wizard.avertissement_mot_de_passe_defaut = ""

    def action_ouvrir_parametre_mot_de_passe(self):
        """Ouvre directement la fiche du paramètre système du mot de passe par
        défaut, pour un administrateur - sans avoir à chercher le menu. Réservé
        au groupe Administrateur (la fiche d'un paramètre système ne l'est pas
        pour les autres) : le bouton y est masqué dans la vue, et la méthode
        revérifie, puisqu'un appel direct ne passe pas par la vue."""
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise UserError(
                _("Seul un administrateur peut modifier ce paramètre : %(emplacement)s.")
                % {"emplacement": EMPLACEMENT_MOT_DE_PASSE_DEFAUT}
            )
        param = self.env["ir.config_parameter"].sudo().search(
            [("key", "=", "rlq_survey_report.mot_de_passe_defaut")], limit=1
        )
        if not param:
            raise UserError(
                _(
                    "Le paramètre rlq_survey_report.mot_de_passe_defaut n'existe pas encore : "
                    "mettez le module à jour (-u) pour le créer."
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Mot de passe par défaut du rapport"),
            "res_model": "ir.config_parameter",
            "res_id": param.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
        }

    apercu_ampleur = fields.Char(
        string="Ampleur de la génération", compute="_compute_apercu_ampleur",
        help="Calculé automatiquement selon les sondages sélectionnés - indique "
             "le nombre de sondages et de réponses à traiter, pour savoir à quoi "
             "s'attendre avant de cliquer sur Générer. Affiché en permanence dans "
             "le formulaire plutôt que via une notification transitoire (bus), qui "
             "s'est déjà avérée peu fiable sur cette instance.",
    )

    @api.depends("survey_ids", "include_partial")
    def _compute_apercu_ampleur(self):
        """Champ CALCULÉ plutôt qu'un onchange (tenté en v1.46.0, signalé
        ne s'afficher ni avant ni après le clic sur Générer) : un
        onchange ne se déclenche de façon fiable que sur un changement
        de champ fait INTERACTIVEMENT par l'utilisateur - or ce
        formulaire s'ouvre le plus souvent avec `survey_ids` DÉJÀ REMPLI
        via le contexte (`default_survey_ids`, voir
        _action_ouvrir_wizard_pour), pas par une saisie interactive. Un
        champ calculé, lui, s'évalue chaque fois que le formulaire est
        affiché ou que sa dépendance change, peu importe COMMENT cette
        valeur y est arrivée - un mécanisme different et plus robuste
        pour ce cas précis."""
        for wizard in self:
            if not wizard.survey_ids:
                wizard.apercu_ampleur = ""
                continue
            nb_sondages = len(wizard.survey_ids)
            nb_reponses = wizard.env["survey.user_input"].search_count([
                ("survey_id", "in", wizard.survey_ids.ids),
                ("state", "in", (["done", "in_progress"] if wizard.include_partial else ["done"])),
            ])
            nb_inscrits = sum(wizard.survey_ids.mapped("rlq_answer_count"))
            nb_termines = sum(wizard.survey_ids.mapped("rlq_answer_done_count"))
            nb_debutes = sum(wizard.survey_ids.mapped("rlq_answer_in_progress_count"))
            wizard.apercu_ampleur = _(
                "%(ns)s sondage(s) sélectionné(s), %(np)s participant(s) au total à traiter "
                "(%(ni)s inscrit(s), %(nt)s terminé(s), %(nd)s débuté(s) sans terminer)."
            ) % {
                "ns": nb_sondages, "np": nb_reponses,
                "ni": nb_inscrits, "nt": nb_termines, "nd": nb_debutes,
            }

    apercu_solidite_mot_de_passe = fields.Char(
        string="État du mot de passe", readonly=True,
        help="Mis à jour automatiquement pendant la saisie - indique si le mot de "
             "passe respecte les critères minimaux et si la confirmation correspond, "
             "sans dépendre d'une notification à l'écran qui pourrait ne pas "
             "s'afficher de façon fiable.",
    )

    @api.onchange("mot_de_passe", "mot_de_passe_confirmation")
    def _onchange_mot_de_passe(self):
        """Retour visuel immédiat et permanent sur la solidité du mot de
        passe ET la correspondance de sa confirmation, affiché directement
        dans le formulaire plutôt que seulement via une notification
        transitoire (bus) - qui s'est déjà avérée peu fiable sur certaines
        instances (ex. l'incident avec notify_warning, inexistant sur
        cette installation).

        N'affiche PLUS le mot de passe lui-même, sous aucune forme -
        seulement une confirmation que les deux saisies correspondent et
        respectent les critères. Deux tentatives précédentes pour
        afficher le mot de passe de façon temporaire ont échoué :
        - v1.59.0 : attribut HTML natif title= - signalé ne pas
          fonctionner (ni au survol, ni au clic).
        - v1.60.0 : mécanisme CSS autonome via un champ Html - a
          PLANTÉ Odoo (confirmé par une trace d'erreur complète :
          OwlError dans HtmlViewer.retargetLinks, un bogue du widget
          Html d'Odoo lui-même face à ce contenu, pas seulement une
          fonctionnalité qui ne s'affichait pas).
        Après ce second échec (un vrai plantage, plus grave qu'un
        simple defaut d'affichage), le champ redevient un Char simple,
        SANS tenter un troisième mécanisme de révélation - la
        correspondance exacte des deux saisies masquées est déjà, en
        pratique, une garantie suffisante contre une erreur de frappe."""
        if not self.mot_de_passe and not self.mot_de_passe_confirmation:
            self.apercu_solidite_mot_de_passe = ""
            return
        if not self.mot_de_passe or not self.mot_de_passe_confirmation:
            self.apercu_solidite_mot_de_passe = "Entrez le mot de passe dans les deux champs."
            return
        if self.mot_de_passe != self.mot_de_passe_confirmation:
            self.apercu_solidite_mot_de_passe = "⚠ Les deux mots de passe ne correspondent pas."
            return
        manquants = self._criteres_manquants_mot_de_passe()
        if manquants:
            self.apercu_solidite_mot_de_passe = "⚠ Il manque : " + ", ".join(manquants) + "."
        else:
            self.apercu_solidite_mot_de_passe = "✓ Les deux mots de passe correspondent et sont suffisamment solides."

    ventiler_matrices = fields.Boolean(
        string="Ventiler les notes (liste dépliable détaillée)", default=True,
        help="Ajoute, sous chaque note moyenne, une liste dépliable indiquant qui "
             "a donné quelle note (avec un lien vers sa fiche). Décochez pour un "
             "rapport plus compact, sans ce détail.",
    )
    combiner_reponses_meme_sondage = fields.Boolean(
        string="Combiner les réponses d'un utilisateur à un même sondage", default=False,
        help="Par défaut (décoché) : si une personne a répondu plusieurs fois au "
             "même sondage (ex. en changeant d'idée), le tableau de réponses de "
             "sa fiche affiche chaque soumission dans sa PROPRE colonne, avec la "
             "date ET l'heure de cette soumission précise - permet de voir "
             "chaque tentative séparément. Cochez pour revenir au comportement "
             "précédent : une seule colonne par rencontre, montrant seulement la "
             "DERNIÈRE soumission traitée en cas de réponses multiples (les "
             "précédentes restent visibles dans « Détail des soumissions », mais "
             "plus dans ce tableau).",
    )
    dedupliquer_textes = fields.Boolean(
        string="Dédoublonner les réponses libres avec compteur", default=True,
        help="Pour les questions à réponse libre (ex. suggestions de sujets), "
             "regroupe les réponses identiques avec un compteur (x2, x3...) au "
             "lieu de les répéter une fois par personne.",
    )
    theme = fields.Selection(
        [("blue", "Bleu (défaut)"), ("dark", "Sombre"), ("green", "Vert"), ("purple", "Violet")],
        default="blue", string="Thème",
        help="Palette de couleurs du rapport. Peut aussi être changée directement "
             "dans le rapport déjà généré, via le sélecteur de thème en haut de "
             "celui-ci - sans avoir à régénérer.",
    )
    confirmation_renseignements_personnels = fields.Boolean(
        string="Je confirme être responsable des renseignements personnels de ce rapport",
        default=False,
        help="Ce rapport contient des renseignements personnels sur les participants "
             "(noms, coordonnées). En cochant cette case, vous confirmez être conscient(e) "
             "de cette responsabilité et vous engager à ne le partager qu'avec les "
             "personnes autorisées, conformément aux obligations applicables (ex. Loi 25 "
             "au Québec, RGPD en Europe).",
    )
    anonymiser = fields.Boolean(
        string="Anonymiser les participants", default=True,
        help="Remplace le nom de chaque participant par « Participant 1 », "
             "« Participant 2 »... (le même numéro partout pour une même personne). Un "
             "présentateur reste nommé UNIQUEMENT dans le titre de ses présentations, la "
             "ligne « Présentateur(s) » de chaque rencontre et la section « Appréciation "
             "des présentateurs » (déjà identifié publiquement par sa présentation) ; "
             "partout ailleurs, y compris dans la liste des participants, il est anonymisé "
             "comme les autres. RETIRÉS entièrement (pas seulement masqués) : le courriel, "
             "le téléphone, le mobile, la ville, le pays, les étiquettes, et les lignes "
             "« Sondages remplis » et « Événements inscrits » (une longue suite de dates "
             "peut identifier quelqu'un). Les liens vers le backend d'Odoo (configuration "
             "du sondage, « Tester sondage », événement) deviennent du texte simple, et tout "
             "texte ayant la forme d'un courriel est masqué. Le CONTENU des réponses libres "
             "reste visible tel quel : il peut identifier indirectement son auteur, à "
             "relire avant toute diffusion publique. Aucun mot de passe n'est requis pour un "
             "rapport anonymisé (à l'écran ou en fichier HTML/PDF) ; l'export Excel, lui, "
             "n'est PAS anonymisé.",
    )
    inclure_section_surveiller = fields.Boolean(
        string="Ajouter une section « À surveiller » (notes ≤ 2)", default=True,
        help="Ajoute, à la toute fin du rapport, une liste de toutes les notes de 2 ou "
             "moins données à n'importe quelle question, tous sondages sélectionnés "
             "confondus (avec la date, le volet concerné et le nom du participant) - "
             "pour repérer rapidement les pistes d'amélioration sans avoir à parcourir "
             "le détail de chaque sondage un par un.",
    )
    output_format = fields.Selection(
        [
            ("screen", "À l'écran, dans Odoo"),
            ("html", "Fichier HTML (téléchargement immédiat)"),
            ("pdf", "Fichier PDF (téléchargement immédiat)"),
        ],
        default="screen", required=True, string="Format de sortie",
        help="Choisissez ici ce que le bouton « Générer » doit produire. Une fois "
             "le rapport affiché à l'écran, les boutons de téléchargement HTML et "
             "PDF restent de toute façon disponibles séparément.",
    )
    state = fields.Selection([("draft", "Paramètres"), ("done", "Rapport généré")], default="draft")
    report_html = fields.Html(string="Rapport", sanitize=False, readonly=True)
    menu_origine = fields.Char(string="Sous-menu utilisé", readonly=True)
    debug_info = fields.Char(
        string="Version du module", default=lambda self: self._default_debug_info(),
    )

    @api.model
    def _default_debug_info(self):
        """Valeur par défaut plutôt que champ calculé : un `default` est
        garanti être appliqué dès l'ouverture d'un nouvel enregistrement
        (default_get), alors qu'un champ 'compute' sans dépendances ne
        semblait pas se recalculer de façon fiable avant le premier
        enregistrement (le champ ne s'affichait qu'après avoir généré).

        Retourne du HTML (chiffres en gras) plutôt que du texte brut - le
        champ est de type Html avec sanitize=False pour permettre ce
        formatage, comme report_html."""
        module = self.env["ir.module.module"].sudo().search(
            [("name", "=", "rlq_survey_report")], limit=1
        )
        version = module.installed_version or module.latest_version or "?"
        if module.write_date:
            date_locale = fields.Datetime.context_timestamp(self, module.write_date)
            date_install = f"{date_locale.strftime('%Y-%m-%d %H:%M')} {date_locale.strftime('%Z')}"
        else:
            date_install = "?"
        return f"rlq_survey_report v{version} ({date_install})"

    def _anonymiser_html(self, html, participants_tries):
        """Remplace, dans le HTML déjà construit, le nom et le courriel de
        CHAQUE participant (y compris un présentateur qui aurait aussi
        répondu à un sondage - voir jeton_presentateur() pour comment son
        nom reste malgré tout visible là où il doit l'être, dans
        "Appréciation des présentateurs" et les titres de présentations)
        par un pseudonyme (« Participant N ») et un texte masqué - une
        substitution textuelle globale sur le rendu final plutôt qu'une
        modification de chacun des nombreux endroits où un nom est
        utilisé pendant la construction du rapport (table des matières,
        en-têtes, tableaux, étiquettes...), pour limiter le risque d'en
        manquer un. Les noms sont remplacés du plus long au plus court,
        pour qu'un nom plus court contenu dans un nom plus long (ex.
        « Jean » dans « Jean Dupont ») ne soit jamais remplacé en premier
        et ne corrompe pas ainsi le nom plus long.

        Remplace AUSSI le slug d'ancre dérivé du nom (ex.
        personne-jean-dupont -> personne-3) par un index anonyme - un
        remplacement global, comme pour le nom et le courriel, qui
        corrige donc à la fois l'attribut id= de la section ET tout lien
        y pointant (ex. via lien_personne() dans report_builder.py, qui
        construit toujours ses liens à partir du nom réel - cette
        fonction n'a aucune connaissance de l'anonymisation, c'est donc
        ICI, en aval, que la correspondance est corrigée) - CORRECTIF
        d'une fuite précédemment documentée (l'ancre restait dérivée du
        nom réel, devinable dans le code source de la page même une fois
        le texte visible masqué).

        CORRECTIF (v1.79.0) : le remplacement utilise des LIMITES DE MOT
        (regex \\b...\\b), pas une simple sous-chaîne (str.replace) -
        UNE VERSION PRÉCÉDENTE (v1.56.0) EXCLUAIT ENTIÈREMENT tout nom de
        moins de 3 caractères (ex. une seule lettre "F", si une fiche
        contact est incomplète dans Odoo), pour éviter qu'un remplacement
        de sous-chaîne sans limite ne corrompe un mot sans rapport (ex.
        "Filtre" devenant "[Participant N]iltre"). Ce choix évitait la
        corruption, mais au prix de LAISSER CETTE PERSONNE ENTIÈREMENT
        VISIBLE dans un rapport pourtant censé être anonymisé - signalé
        comme un vrai problème, pas un compromis acceptable. Une limite
        de mot (\\bF\\b) ne matche "F" que lorsqu'il est isolé (espace,
        ponctuation, début/fin de texte de part et d'autre) - jamais à
        l'intérieur d'un autre mot comme "Filtre" - ce qui permet de
        remplacer un nom de N'IMPORTE QUELLE longueur, y compris une
        seule lettre, sans ce risque de corruption. Le garde-fou par
        longueur minimale est donc entièrement retiré.

        CORRECTIF (v1.93.0) : \\b...\\b NE FONCTIONNE PAS pour un nom qui se termine
        (ou commence) par un caractère non alphanumérique : il n'existe pas de
        limite de mot entre « ) » et un espace ou un « < ». Un participant nommé
        « Nom Prénom (organisation.com) » n'était donc JAMAIS remplacé - signalé sur
        un rapport anonymisé où il restait lisible. Le remplacement passe maintenant
        par rb.remplacer_nom_complet() (lookarounds « pas collé à un caractère de mot »),
        testable sans Odoo."""
        remplacements = []
        for i, (_cle, p) in enumerate(participants_tries, 1):
            pseudo = f"Participant {i}"
            nom = p.get("nom") or ""
            if nom:
                remplacements.append((nom, pseudo))
                remplacements.append((f"personne-{rb.slug(nom)}", f"personne-{i}"))
            if p.get("email"):
                remplacements.append((p["email"], "[courriel masqué]"))
        remplacements.sort(key=lambda t: len(t[0]), reverse=True)
        # Normalisation Unicode (forme NFC) du HTML ET de chaque nom avant
        # comparaison - CORRECTIF (v1.57.0) : un nom contenant un accent
        # (ex. "Fabián") peut être représenté en Unicode de deux façons
        # différentes mais visuellement identiques - un seul caractère
        # composé (á), ou "a" suivi d'un accent combinant séparé. Si le
        # titre de la présentation (tapé par un administrateur, peut-être
        # copié-collé d'une source différente) utilise une forme
        # différente de celle de la fiche contact du présentateur, un
        # remplacement de chaîne EXACT échoue à faire correspondre les
        # deux, même si le texte semble identique à l'œil - laissant le
        # nom réel visible dans le rapport anonymisé. Normaliser les deux
        # côtés à la même forme élimine cette divergence.
        html = unicodedata.normalize("NFC", html)
        for original, remplacement in remplacements:
            html = rb.remplacer_nom_complet(html, original, remplacement)
        # FILET DE SÉCURITÉ (v1.91.0) : en plus du remplacement exact ci-dessus
        # (qui ne masque qu'un courriel DÉJÀ CONNU comme appartenant à un
        # participant), une expression régulière masque TOUT texte ayant la
        # forme d'un courriel, n'importe où dans le document - y compris un
        # courriel qui ne provient PAS d'une fiche contact (ex. tapé dans une
        # réponse texte libre), même à l'intérieur d'un attribut href='mailto:'.
        # Seul le courriel d'attribution d'auteur du pied de page est conservé.
        def _masquer_courriel(m):
            if m.group(0).lower() in COURRIELS_ATTRIBUTION:
                return m.group(0)
            return "[courriel masqué]"

        html = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", _masquer_courriel, html)
        return html

    def _resume_parametres(self):
        """Résumé HTML des options/filtres actifs pour cette génération,
        affiché en tête du rapport - pour qu'on sache toujours, en relisant
        un rapport plus tard, avec quels paramètres il a été produit."""
        self.ensure_one()
        lignes = []
        if self.menu_origine:
            lignes.append(f"<li>Sous-menu utilisé : <strong>{rb.echapper(self.menu_origine)}</strong></li>")
        if self.filtre_titre_predefini:
            nom_filtre = dict(self._fields["filtre_titre_predefini"].selection).get(
                self.filtre_titre_predefini, self.filtre_titre_predefini
            )
            details_filtre = [nom_filtre]
            if self.filtre_titre_predefini == "autre" and self.filtre_titre_autre:
                details_filtre.append(f"mot-clé « {self.filtre_titre_autre} »")
            if self.filtre_participants_min and self.filtre_participants_min > 1:
                details_filtre.append(f"{self.filtre_participants_min} participants min.")
            if self.filtre_exclure_titre_contient:
                details_filtre.append(f"exclut « {self.filtre_exclure_titre_contient} »")
            if self.filtre_derniers_mois:
                details_filtre.append(f"{self.filtre_derniers_mois} derniers mois")
            lignes.append(
                f"<li>Filtre rapide utilisé : <strong>{rb.echapper(' · '.join(details_filtre))}</strong></li>"
            )
        if self.filtre_presentateur:
            lignes.append(
                f"<li>Filtré par présentateur : <strong>{rb.echapper(self.filtre_presentateur)}</strong></li>"
            )
        lignes.append(f"<li>Sondages inclus : <strong>{len(self.survey_ids)}</strong></li>")
        if self.date_from:
            lignes.append(f"<li>À partir du : <strong>{self.date_from}</strong></li>")
        if self.date_to:
            lignes.append(f"<li>Jusqu'au : <strong>{self.date_to}</strong></li>")
        if self.filtre_dernieres_heures:
            lignes.append(
                f"<li>Limité aux inscriptions des <strong>{self.filtre_dernieres_heures}</strong> "
                "dernières heures</li>"
            )
        lignes.append(
            f"<li>Réponses partielles incluses : <strong>{'Oui' if self.include_partial else 'Non'}</strong></li>"
        )
        if self.exclude_partner_ids:
            noms = ", ".join(self.exclude_partner_ids.mapped("name"))
            lignes.append(f"<li>Participants exclus : <strong>{rb.echapper(noms)}</strong></li>")
        if self.exclude_tag_ids:
            noms = ", ".join(self.exclude_tag_ids.mapped("name"))
            lignes.append(f"<li>Étiquette(s) exclue(s) : <strong>{rb.echapper(noms)}</strong></li>")
        if self.exclude_title_keywords:
            lignes.append(
                f"<li>Sondages exclus si le titre contient : "
                f"<strong>{rb.echapper(self.exclude_title_keywords)}</strong></li>"
            )
        nom_format = dict(self._fields["output_format"].selection).get(self.output_format, self.output_format)
        lignes.append(
            f"<li>Ventilation des notes : <strong>{'Oui' if self.ventiler_matrices else 'Non'}</strong> · "
            f"Dédoublonnage des textes libres : <strong>{'Oui' if self.dedupliquer_textes else 'Non'}</strong> · "
            f"Anonymisation : <strong>{'Oui' if self.anonymiser else 'Non'}</strong> · "
            f"Personnes n'ayant pas répondu : <strong>{'Oui' if self.voir_non_repondants else 'Non'}</strong> · "
            f"Section « À surveiller » : <strong>{'Oui' if self.inclure_section_surveiller else 'Non'}</strong> · "
            f"Combiner les réponses d'un même sondage : "
            f"<strong>{'Oui' if self.combiner_reponses_meme_sondage else 'Non'}</strong> · "
            f"Format de sortie : <strong>{rb.echapper(nom_format)}</strong></li>"
        )
        return (
            "<details class='detail-oui' open='open'><summary>Paramètres utilisés pour ce rapport</summary>"
            f"<ul class='liste-texte'>{''.join(lignes)}</ul></details>"
        )

    # ------------------------------------------------------------------
    # Extraction ORM -> structures Python simples
    # ------------------------------------------------------------------

    @api.model
    def _default_exclude_tag_ids(self):
        """Étiquette exclue par défaut : « Collaborateurs-2026 », si elle
        existe sur cette instance (recherche exacte, insensible à la casse ;
        ne bloque pas si elle est absente)."""
        tag = self.env["res.partner.category"].search([("name", "=ilike", "Collaborateurs-2026")], limit=1)
        return tag.ids

    def _respondent_nom(self, user_input):
        """sudo() sur l'accès au partenaire : un « Utilisateur » du module
        Sondage peut légitimement générer ce rapport (c'est le but même
        du module) mais ne pas avoir un accès direct, via les règles
        d'enregistrement d'Odoo, à CHAQUE fiche contact individuelle liée
        aux réponses (ex. contacts d'une autre société en environnement
        multi-société) - confirmé par une erreur "Access Denied by record
        rules" observée en production. Le contenu déjà affiché par ce
        rapport (nom, courriel) est de toute façon le but explicite du
        module, protégé par ailleurs (confirmation obligatoire, mot de
        passe pour tout téléchargement) - lire seulement ces deux champs
        en sudo() n'expose rien de plus que ce que le rapport montre déjà
        normalement."""
        if user_input.partner_id:
            return user_input.partner_id.sudo().name
        return user_input.email or _("Anonyme")

    def _respondent_email(self, user_input):
        return (user_input.partner_id.sudo().email or user_input.email or "") or None

    def _extraire_date_titre(self, titre, annee_repli=None):
        """Extrait une date d'un titre de sondage contenant un texte français
        du type '4 août 2026', '1er septembre 2026', ou même '31 juillet'
        sans année - auquel cas `annee_repli` (typiquement l'année de la
        date d'envoi du sondage) est utilisée à sa place. Retourne None si
        aucune date n'est trouvée, si l'année manque sans repli fourni, ou
        si l'année semble aberrante (garde-fou contre un nombre à 4
        chiffres qui ne serait pas une année)."""
        if not titre:
            return None
        titre = unicodedata.normalize("NFC", titre)
        m = _MOTIF_DATE_FR.search(titre)
        if not m:
            return None
        jour = int(m.group(1))
        mois = MOIS_FR.get(m.group(2).lower())
        annee = int(m.group(3)) if m.group(3) else annee_repli
        if annee is None or not (2015 <= annee <= 2035):
            return None
        try:
            return date_cls(annee, mois, jour)
        except (ValueError, TypeError):
            return None

    def _trouver_champ_date(self, record, mots_cles):
        """Cherche, parmi les champs Date/Datetime du modèle de `record`, un
        nom contenant l'un des mots-clés donnés (insensible à la casse).
        Retourne (nom_champ, valeur) ou (None, None) - ne suppose jamais de
        nom de champ précis, donc sans risque même si rien n'est trouvé."""
        for fname, fdef in record._fields.items():
            if fdef.type in ("date", "datetime") and any(mc in fname.lower() for mc in mots_cles):
                valeur = record[fname]
                if valeur:
                    return fname, valeur
        return None, None

    def _dates_envoi_expiration(self, survey):
        """Date de création du sondage (create_date, toujours disponible sur
        tout modèle Odoo - visible dans son fil de discussion, ex. « Sondage
        créé ») et date d'expiration, si un champ correspondant a pu être
        détecté sur ce modèle (recherche dynamique par mots-clés, comme pour
        le lien événement). Une tentative précédente de détecter un champ
        "date d'envoi" séparé (ou de le déduire du fil de discussion) n'a
        rien trouvé sur cette instance - create_date, toujours présent, le
        remplace directement plutôt que de continuer à chercher un champ
        potentiellement inexistant."""
        date_creation = survey.create_date.date() if survey.create_date else None
        _f, date_expiration = self._trouver_champ_date(survey, ["expir", "deadline", "cloture", "closing", "fin_"])
        return date_creation, date_expiration

    def _annee_repli_titre(self, survey):
        """Année à utiliser en repli quand le titre d'un sondage indique une
        date sans année (ex. '31 juillet') : celle de la date de création du
        sondage (create_date), toujours disponible."""
        return survey.create_date.year if survey.create_date else None

    def _rencontre_date(self, survey, user_inputs, date_titre=None):
        """Date de la rencontre associée à un sondage. La date indiquée dans
        le titre du sondage (ex. '4 août 2026') est préférée à la date de
        soumission des réponses, qui peut suivre l'événement de quelques
        jours - même principe que pour les noms de fichiers dans la version
        autonome du programme. Si le titre omet l'année, celle de la date
        d'envoi du sondage sert de repli.

        `date_titre` peut être fournie par l'appelant s'il l'a déjà extraite
        (ex. la boucle principale) pour éviter de la recalculer une seconde
        fois - `_extraire_date_titre()` et `_annee_repli_titre()` ne
        déclenchent pas de nouvelle requête SQL grâce au cache de l'ORM,
        mais recalculer trois fois la même chose par sondage restait un
        gaspillage inutile."""
        d = date_titre if date_titre is not None else self._extraire_date_titre(
            survey.title, annee_repli=self._annee_repli_titre(survey)
        )
        if d:
            return d.isoformat()
        dates = [ui.create_date.date() for ui in user_inputs if ui.create_date]
        return min(dates).isoformat() if dates else False

    def _lien_evenement_par_date(self, date_survey):
        """Repli quand aucune relation directe en base ne relie le sondage à
        un événement (voir _lien_evenement) : cherche un event.event ou
        calendar.event dont la date de début tombe le même jour que la date
        du sondage. Les noms de champ candidats pour "date de début" sont
        vérifiés parmi les champs réels du modèle avant toute utilisation -
        aucun accès à un champ suffisamment incertain pour risquer une
        erreur."""
        if not date_survey:
            return None
        candidats_champ = ("date_begin", "start", "date_start", "start_date", "date")
        debut = datetime.combine(date_survey, datetime.min.time())
        fin = datetime.combine(date_survey, datetime.max.time())
        for modele in ("event.event", "calendar.event"):
            if modele not in self.env:
                continue
            Modele = self.env[modele]
            champ_reel = next(
                (c for c in candidats_champ if c in Modele._fields and Modele._fields[c].type in ("date", "datetime")),
                None,
            )
            if not champ_reel:
                continue
            if Modele._fields[champ_reel].type == "date":
                domaine = [(champ_reel, "=", date_survey)]
            else:
                domaine = [(champ_reel, ">=", debut), (champ_reel, "<=", fin)]
            evenement = Modele.search(domaine, limit=1)
            if evenement:
                return evenement
        return None

    def _lien_evenement(self, survey, date_survey=None):
        """Cherche un lien entre ce sondage et un événement, sans supposer de
        nom de champ ni de sens de relation précis (rien de tel n'existe
        dans le module Sondage d'origine - la liaison est donc forcément
        une particularité de cette instance) :
        1) un champ Many2one sur survey.survey pointant vers event.event
           ou calendar.event ;
        2) le cas inverse : un champ sur event.event/calendar.event
           pointant vers ce survey.survey ;
        3) à défaut de relation directe en base : un événement dont la date
           correspond exactement à `date_survey` (la date extraite du
           titre du sondage).
        Retourne l'ENREGISTREMENT trouvé (pas du HTML) - à l'appelant de
        construire le lien voulu (config, page publique...) - ou None si
        rien n'est trouvé. Ne lève jamais d'erreur."""
        modeles_evenement = [m for m in ("event.event", "calendar.event") if m in self.env]

        # 1) Champ direct sur survey.survey
        for fname, fdef in survey._fields.items():
            if fdef.type == "many2one" and fdef.comodel_name in modeles_evenement:
                evenement = survey[fname]
                if evenement:
                    return evenement

        # 2) Champ inverse : l'événement pointe vers le sondage
        for modele in modeles_evenement:
            Modele = self.env[modele]
            for fname, fdef in Modele._fields.items():
                if fdef.type == "many2one" and fdef.comodel_name == "survey.survey":
                    evenement = Modele.search([(fname, "=", survey.id)], limit=1)
                    if evenement:
                        return evenement

        # 3) Repli par correspondance de date
        return self._lien_evenement_par_date(date_survey)

    def _prefixe_nom_fichier(self, format_fichier="html"):
        """Construit un préfixe pour le nom des fichiers téléchargés
        (HTML/PDF/Excel), placé avant la date/heure de génération -
        indique d'un coup d'œil, sans avoir à ouvrir le fichier, s'il
        est chiffré (« enc- »), s'il est anonymisé, et quelle catégorie
        de sondages (et sous-options) a été utilisée pour la sélection
        (ex. « pause-cafe-5derniersmois- »). Le nom de fichier obtenu
        peut devenir long, mais c'est voulu : il reflète alors fidèlement
        le contenu réel du fichier sans avoir à l'ouvrir."""
        self.ensure_one()
        morceaux = []
        if self._mot_de_passe_effectif(format_fichier):
            morceaux.append("enc")
        # L'export Excel n'est PAS anonymisé (vrais noms et courriels) : ne
        # jamais l'étiqueter « anonyme », au risque qu'on le partage en le
        # croyant anonymisé.
        if self.anonymiser and format_fichier != "excel":
            morceaux.append("anonyme")
        # Quand un seul sondage est sélectionné (ex. un rapport ciblé envoyé à
        # un présentateur précis via « Filtrer par présentateur »), son titre
        # est le repère le plus parlant dans le nom du fichier.
        if len(self.survey_ids) == 1 and self.survey_ids.title:
            morceaux.append(rb.slug(self.survey_ids.title))
        slugs_filtre = {
            "premier_mardi": "1erMardi",
            "pause_cafe": "pause-cafe",
            "portes_ouvertes": "portes-ouvertes",
        }
        if self.filtre_titre_predefini == "autre" and self.filtre_titre_autre:
            morceaux.append(rb.slug(self.filtre_titre_autre))
        elif self.filtre_titre_predefini:
            morceaux.append(slugs_filtre.get(self.filtre_titre_predefini, self.filtre_titre_predefini))
            if self.filtre_participants_min and self.filtre_participants_min > 1:
                morceaux.append(f"{self.filtre_participants_min}pmin")
            if self.filtre_derniers_mois:
                morceaux.append(f"{self.filtre_derniers_mois}derniersmois")
        elif self.menu_origine:
            morceaux.append(rb.slug(self.menu_origine))
        if self.filtre_dernieres_heures:
            morceaux.append(f"{self.filtre_dernieres_heures}h")
        if not morceaux:
            return ""
        return "-".join(morceaux) + "-"

    def _suffixe_plage_dates_nom_fichier(self):
        """Construit un suffixe "AAAAMMJJ__a__AAAAMMJJ" représentant la
        plage de dates couverte par ce rapport - à partir des filtres
        explicites (À partir du/Jusqu'au) s'ils sont renseignés, sinon
        calculée à partir des dates réelles des sondages inclus (déduites
        du titre, voir rlq_date_titre). Chaîne vide si aucune date n'est
        disponible d'une façon ou d'une autre (rien à représenter)."""
        self.ensure_one()
        if self.date_from and self.date_to:
            debut, fin = self.date_from, self.date_to
        else:
            dates = sorted(d for d in self.survey_ids.mapped("rlq_date_titre") if d)
            if not dates:
                return ""
            debut, fin = dates[0], dates[-1]
        return f"{debut.strftime('%Y%m%d')}__a__{fin.strftime('%Y%m%d')}"

    def _url_absolue(self, chemin_relatif):
        """Préfixe un chemin relatif (ex. "/web#model=...") avec l'URL de
        base de cette instance (paramètre système web.base.url) - sans
        ce préfixe, un lien relatif fonctionne correctement à l'écran
        dans Odoo (relatif à la page déjà ouverte), mais pointe vers un
        emplacement local incorrect une fois le rapport exporté en HTML
        ou PDF et ouvert en dehors d'Odoo (signalé par l'utilisateur)."""
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
        return f"{base_url}{chemin_relatif}"

    def _html_lien_evenement(self, evenement):
        lien = self._url_absolue(f"/web#model={evenement._name}&id={evenement.id}&view_type=form")
        return f"<a href='{rb.echapper_attr(lien)}' target='_blank'>{rb.echapper(evenement.display_name)}</a>"

    @api.model
    def _cron_purger_pieces_jointes(self, jours=3):
        """Supprime les pièces jointes (HTML/PDF/Excel/ZIP) créées par ce
        module et vieilles de plus de `jours` jours - chaque téléchargement
        (et, depuis v1.80.0, chaque affichage à l'écran) crée un
        ir.attachment permanent (res_model=rlq.survey.report.wizard), qui
        s'accumule indéfiniment sans purge (contrairement à l'enregistrement
        du wizard lui-même, un TransientModel automatiquement nettoyé par
        Odoo au bout de quelques heures - mais qui n'entraîne PAS la
        suppression des pièces jointes qui le référencent). Le délai de 3
        jours par défaut laisse le temps de télécharger le fichier avant sa
        suppression, tout en évitant une accumulation illimitée dans le
        filestore et la table ir_attachment. Enregistrée comme tâche
        planifiée (ir.cron) - voir data/ir_cron_purge.xml.

        EXCEPTION (v1.80.0, sur demande) : les pièces jointes liées à une
        entrée d'historique ANONYMISÉE (rlq.survey.report.acces.anonymise)
        sont EXCLUES de cette purge - conservées indéfiniment (jusqu'à
        suppression manuelle), pour servir de bibliothèque réutilisable
        sans avoir à régénérer d'une personne à l'autre. Cohérent avec le
        principe de minimisation : une copie anonymisée comporte moins de
        risque à conserver qu'une copie avec des noms réels, qui continue
        d'être purgée après `jours` jours comme avant."""
        limite = fields.Datetime.now() - relativedelta(days=jours)
        attachments_anonymises = self.env["rlq.survey.report.acces"].sudo().search([
            ("anonymise", "=", True), ("attachment_id", "!=", False),
        ]).mapped("attachment_id")
        pieces_jointes = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", self._name),
            ("create_date", "<", limite),
            ("id", "not in", attachments_anonymises.ids),
        ])
        if pieces_jointes:
            _logger.info(
                "Purge de %(n)s pièce(s) jointe(s) de rlq_survey_report (plus de %(j)s jours, "
                "hors copies anonymisées conservées indéfiniment)",
                {"n": len(pieces_jointes), "j": jours},
            )
            pieces_jointes.unlink()

    def _lien_test_sondage(self, survey):
        """Lien pour ouvrir le sondage en mode test. CONFIRMÉ FONCTIONNEL
        (v1.65.0) : appeler `action_test_survey()` directement - la
        même action que le bouton natif "Test" du backend (repérée par
        l'utilisateur en mode debug) - fonctionne, le bandeau "Ceci est
        une entrée d'un sondage test." apparaît bien. Libellé changé de
        "ouvrir" à "Tester sondage" en conséquence.

        Historique (voir NOTES_VALIDATION.md pour le détail complet) :
        mécanisme maison de VRAIE entrée de test abandonné en v1.55.0
        après 3 échecs ; repli sur get_start_url() ensuite confirmé peu
        fiable pour un vrai mode test ; action_test_survey() (v1.64.0)
        est la solution qui fonctionne enfin.

        Repli sur get_start_url() conservé si action_test_survey()
        n'existe pas, échoue, ou ne retourne pas la structure
        attendue - ne doit jamais faire échouer tout le rapport."""
        if hasattr(survey, "action_test_survey"):
            try:
                action = survey.action_test_survey()
                if isinstance(action, dict) and action.get("url"):
                    url = action["url"]
                    if url.startswith("/"):
                        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
                        url = f"{base_url}{url}"
                    return url
            except Exception:  # noqa: BLE001 - ne doit jamais faire échouer tout le rapport
                _logger.warning(
                    "action_test_survey() a échoué pour le sondage %s - repli sur get_start_url()",
                    survey.id, exc_info=True,
                )
        try:
            return survey.get_start_url()
        except Exception:  # noqa: BLE001 - méthode non garantie sur toutes les instances
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
            return f"{base_url}/survey/start/{survey.access_token}" if survey.access_token else ""

    def _lien_evenement_public(self, evenement):
        """Lien vers la page publique (site web) de l'événement, si le
        modèle expose un champ de ce type - le champ `website_url`,
        standard sur event.event depuis longtemps dans Odoo, est
        recherché en premier ; aucune erreur si absent, retourne
        simplement None (pas de lien affiché dans ce cas). Ce champ
        retourne typiquement un chemin RELATIF (ex. "/event/mon-evenement-5")
        dans Odoo - préfixé ici avec l'URL de base si nécessaire, pour un
        lien qui fonctionne aussi une fois le rapport exporté hors
        d'Odoo."""
        for nom_champ in ("website_url",):
            valeur = evenement[nom_champ] if nom_champ in evenement._fields else None
            if valeur:
                return valeur if valeur.startswith("http") else self._url_absolue(valeur)
        return None

    def _html_details_evenement(self, evenement):
        """Détails supplémentaires sur l'événement, un par un, chacun
        cherché dynamiquement parmi les champs réels du modèle (jamais
        d'accès direct à un nom supposé) - n'affiche que ceux qui
        existent ET ont une valeur. Couvre les champs standards du
        module Événements d'Odoo (lieu, horaire, description, places) ;
        des champs propres à votre instance (commanditaires, kiosques,
        tirage au sort...) ne sont PAS couverts ici - trop spécifiques
        pour être devinés sans risque de se tromper de nom. Si vous
        connaissez leurs noms exacts, ajoutez-les à `_CHAMPS_DETAILS_EVT`
        en suivant le même patron."""
        morceaux = []

        # Lieu (adresse) - plusieurs noms de champ possibles selon la version.
        for nom_champ in ("address_id",):
            if nom_champ in evenement._fields and evenement[nom_champ]:
                morceaux.append(f"Lieu : {rb.echapper(evenement[nom_champ].display_name)}")
                break

        # Horaire (début/fin) en heure LOCALE (le fuseau de l'utilisateur
        # courant) plutôt qu'en UTC - les champs Datetime d'Odoo sont
        # stockés/lus en UTC par défaut, fields.Datetime.context_timestamp
        # fait la conversion, comme déjà utilisé ailleurs dans ce module
        # pour la date de génération du rapport. Affiché SANS le jour de
        # la semaine (déjà indiqué ailleurs pour la date principale du
        # sondage).
        for champ_debut, champ_fin in (("date_begin", "date_end"),):
            if champ_debut in evenement._fields and evenement[champ_debut]:
                debut = fields.Datetime.context_timestamp(self, evenement[champ_debut])
                horaire = f"Horaire : {debut.strftime('%Y-%m-%d %H:%M')}"
                if champ_fin in evenement._fields and evenement[champ_fin]:
                    fin = fields.Datetime.context_timestamp(self, evenement[champ_fin])
                    horaire += f" – {fin.strftime('%H:%M')}"
                morceaux.append(horaire)
                break

        # Places (inscriptions/présences) - noms de champs standards
        # d'Odoo Événements, vérifiés dynamiquement. seats_reserved et
        # seats_used représentent normalement deux groupes DISTINCTS
        # (inscriptions au statut "confirmé" vs "présence validée"), pas
        # un sous-ensemble l'un de l'autre - une valeur de "Présents"
        # supérieure à "Inscrits en attente" n'est donc pas une
        # incohérence. Libellés volontairement proches des noms de champs
        # Odoo plutôt qu'une interprétation, par prudence sur le sens
        # exact - à valider vous-même sur un événement dont vous
        # connaissez déjà les chiffres réels.
        candidats_places = (
            ("seats_reserved", "Inscrits (en attente de présence)"),
            ("seats_used", "Présence confirmée"),
            ("seats_max", "Places maximum"),
            ("seats_available", "Places restantes"),
        )
        for nom_champ, libelle in candidats_places:
            if nom_champ in evenement._fields and evenement[nom_champ]:
                morceaux.append(f"{libelle} : <strong>{evenement[nom_champ]}</strong>")

        # Photo - affichée en miniature si un champ image standard existe.
        for nom_champ in ("image_1920", "image_1024", "image_512"):
            if nom_champ in evenement._fields and evenement[nom_champ]:
                morceaux.append(
                    f"<img src='data:image/png;base64,{evenement[nom_champ].decode('ascii') if isinstance(evenement[nom_champ], bytes) else evenement[nom_champ]}' "
                    "style='max-width:200px;max-height:150px;border-radius:6px;display:block;margin-top:.3rem;' alt='Photo de l’événement'/>"
                )
                break

        if not morceaux:
            return ""
        return "<p class='titre-sondage'>" + " · ".join(m for m in morceaux if not m.startswith("<img")) + (
            "".join(m for m in morceaux if m.startswith("<img"))
        ) + "</p>"

    def _repartition_presence_evenement(self, evenement, noms_participants_survey):
        """Répartit les répondants d'UN sondage (`noms_participants_survey`,
        noms tels qu'apparaissant dans les réponses) en 3 groupes selon
        leur statut dans les inscriptions de l'événement lié
        (event.registration, recherché dynamiquement - modèle absent ou
        sans lien clair : retourne trois listes vides sans erreur) :
        Présent, Inscrit (mais pas encore marqué présent), Non-inscrit
        (a répondu au sondage sans figurer dans les inscriptions). Le
        rapprochement se fait par courriel, la donnée la plus fiable
        commune aux deux côtés."""
        presents, inscrits, non_inscrits = [], [], []
        if "event.registration" not in self.env or not evenement or evenement._name != "event.event":
            return presents, inscrits, [nom for nom, _courriel in noms_participants_survey]

        inscriptions = self.env["event.registration"].sudo().search([("event_id", "=", evenement.id)])
        champ_email = next((c for c in ("email",) if c in inscriptions._fields), None)
        champ_etat = next((c for c in ("state",) if c in inscriptions._fields), None)
        emails_par_statut = {}
        for insc in inscriptions:
            courriel = (insc[champ_email] or "").strip().lower() if champ_email else ""
            if not courriel:
                continue
            statut = insc[champ_etat] if champ_etat else None
            emails_par_statut[courriel] = statut

        for nom, courriel_participant in noms_participants_survey:
            cle = (courriel_participant or "").strip().lower()
            if cle and cle in emails_par_statut:
                statut = emails_par_statut[cle]
                if statut == "done":
                    presents.append(nom)
                else:
                    inscrits.append(nom)
            else:
                non_inscrits.append(nom)
        return presents, inscrits, non_inscrits

    def _get_columns(self, question):
        """Options / colonnes d'une question à choix ou matricielle."""
        champ = getattr(question, "suggested_answer_ids", None)
        if champ is None:
            raise UserError(_(
                "Le champ 'suggested_answer_ids' n'existe pas sur survey.question sur "
                "cette instance. Champs disponibles : %s"
            ) % ", ".join(sorted(question._fields.keys())))
        return champ.sorted("sequence")

    def _get_rows(self, question):
        """Lignes (volets) d'une question matricielle."""
        # CHAMP : selon la version, il peut s'agir de question.matrix_row_ids
        # ou d'un sous-ensemble filtré de suggested_answer_ids.
        rows = getattr(question, "matrix_row_ids", False)
        return rows.sorted("sequence") if rows else question.env[self._answer_model_name()]

    def _user_inputs(self, survey):
        domain = [("survey_id", "=", survey.id)]
        if self.include_partial:
            # "Réponses partielles" = commencées mais non terminées
            # (state='in_progress') - jamais les invitations jamais ouvertes
            # (state='new'), qui ne sont pas des réponses du tout.
            domain.append(("state", "in", ("done", "in_progress")))
        else:
            domain.append(("state", "=", "done"))
        if self.date_from:
            domain.append(("create_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("create_date", "<=", self.date_to))
        if self.filtre_dernieres_heures:
            limite = fields.Datetime.now() - relativedelta(hours=self.filtre_dernieres_heures)
            domain.append(("create_date", ">=", limite))
        if self.exclude_partner_ids:
            domain.append(("partner_id", "not in", self.exclude_partner_ids.ids))
        if self.exclude_tag_ids:
            domain.append(("partner_id.category_id", "not in", self.exclude_tag_ids.ids))
        return self.env["survey.user_input"].search(domain)

    def _detecter_champ_et_modele_lignes(self):
        """Détecte dynamiquement le champ One2many de survey.user_input vers
        les réponses individuelles (ligne par ligne), plutôt que de supposer
        que le modèle cible s'appelle 'survey.user_input_line' : ce nom
        s'est avéré incorrect sur au moins une instance (ERPLibre).

        Retourne (nom_du_champ, nom_du_modele). Recalculé à chaque appel :
        les enregistrements Odoo (recordsets) n'autorisent pas d'y stocker
        un attribut arbitraire pour le mettre en cache (contrairement à un
        objet Python ordinaire) - le coût de recalcul est de toute façon
        négligeable (une simple lecture des champs déjà chargés en mémoire)."""
        ui_model = self.env["survey.user_input"]
        candidats = [
            (fname, fdef.comodel_name)
            for fname, fdef in ui_model._fields.items()
            if fdef.type == "one2many" and "line" in fname.lower()
        ]
        if not candidats:
            # Repli : n'importe quel One2many pointant vers un modèle "survey.*"
            candidats = [
                (fname, fdef.comodel_name)
                for fname, fdef in ui_model._fields.items()
                if fdef.type == "one2many" and fdef.comodel_name
                and fdef.comodel_name.startswith("survey.")
                and fdef.comodel_name != "survey.user_input"
            ]
        if not candidats:
            raise UserError(_(
                "Impossible de trouver, sur survey.user_input, le champ One2many menant "
                "aux réponses individuelles. Champs One2many disponibles : %s\n\n"
                "Indiquez-moi le bon nom de champ pour que je corrige le module."
            ) % ", ".join(
                f"{f} -> {d.comodel_name}"
                for f, d in ui_model._fields.items() if d.type == "one2many"
            ))
        return candidats[0]

    def _lines_field_name(self):
        return self._detecter_champ_et_modele_lignes()[0]

    def _answer_model_name(self):
        return self._detecter_champ_et_modele_lignes()[1]

    # ------------------------------------------------------------------
    # Construction du rapport
    # ------------------------------------------------------------------

    def _action_demander_mot_de_passe(self, action_suivante="action_generate"):
        """Retourne l'action ouvrant la petite vue dédiée demandant le mot
        de passe (voir le commentaire sur cette vue dans le fichier XML) -
        utilisée aux trois endroits où l'absence de mot de passe est
        détectée (action_generate, action_download_html,
        action_download_pdf). `action_suivante` est transmise via le
        contexte pour que le bouton "Continuer" de cette fenêtre relance
        la BONNE action d'origine (voir action_continuer_apres_mot_de_passe
        ci-dessous) - le bouton "Télécharger en HTML/PDF" n'a pas le même
        effet que "Générer" et ne doit pas être confondu avec lui."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[self.env.ref("rlq_survey_report.view_rlq_survey_report_wizard_form_password").id, "form"]],
            "target": "new",
            "context": {"rlq_action_apres_mot_de_passe": action_suivante},
        }

    def action_continuer_apres_mot_de_passe(self):
        """Bouton "Continuer" de la fenêtre de demande de mot de passe :
        relance l'action qui avait initialement mené à cette demande
        (Générer, Télécharger en HTML, ou Télécharger en PDF), transmise
        via le contexte au moment de l'ouverture de cette fenêtre."""
        self.ensure_one()
        nom_methode = self.env.context.get("rlq_action_apres_mot_de_passe", "action_generate")
        actions_permises = (
            "action_generate", "action_download_html", "action_download_pdf",
            "action_export_excel",
        )
        if nom_methode not in actions_permises:
            nom_methode = "action_generate"  # repli sûr si le contexte contient autre chose d'inattendu
        return getattr(self, nom_methode)()

    def action_annuler_mot_de_passe(self):
        """Bouton "Annuler" de la fenêtre de demande de mot de passe :
        revient explicitement au formulaire principal, plutôt que de se
        fier au bouton spécial "cancel" d'Odoo - qui semblait renvoyer à
        l'application Sondage plutôt qu'au formulaire (la fenêtre de
        demande ayant remplacé, plutôt qu'empilé sur, celle du formulaire
        principal)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[self.env.ref("rlq_survey_report.view_rlq_survey_report_wizard_form").id, "form"]],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def action_ouvrir_options_pdf(self):
        """Ouvre la petite fenêtre dédiée aux options spécifiques au PDF -
        retirées du formulaire principal (v1.35.0) pour l'alléger,
        puisqu'utilisées moins souvent que le reste des paramètres."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[self.env.ref("rlq_survey_report.view_rlq_survey_report_wizard_form_options_pdf").id, "form"]],
            "target": "new",
        }

    def action_fermer_options_pdf(self):
        """Bouton "OK" de la fenêtre d'options PDF : les cases cochées y
        sont déjà enregistrées sur l'enregistrement (tout bouton de type
        "object" enregistre les champs modifiés avant d'exécuter sa
        méthode) - il ne reste qu'à revenir à la vue principale."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[self.env.ref("rlq_survey_report.view_rlq_survey_report_wizard_form").id, "form"]],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    CLE_PARAM_URL_AIDE = "rlq_survey_report.url_aide"
    URL_AIDE_DEFAUT = "https://www.rencontres-linux.quebec/odoo/action-908/50/action-909/117"

    def action_ouvrir_aide(self):
        """Ouvre la page d'aide de ce module dans un nouvel onglet - son
        URL est un paramètre système (rlq_survey_report.url_aide),
        modifiable sans toucher au code : Réglages > Technique >
        Paramètres système, en mode développeur. Une valeur par défaut
        (URL_AIDE_DEFAUT) est fournie via data/ir_config_parameter.xml
        si ce paramètre n'a jamais été défini."""
        url = self.env["ir.config_parameter"].sudo().get_param(self.CLE_PARAM_URL_AIDE, self.URL_AIDE_DEFAUT)
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def action_generate(self):
        self.ensure_one()
        if not self.survey_ids:
            raise UserError(_("Sélectionnez au moins un sondage."))
        if not self.confirmation_renseignements_personnels:
            raise UserError(
                _(
                    "Cochez la case de confirmation concernant les renseignements "
                    "personnels avant de générer ce rapport."
                )
            )
        if self.output_format != "screen" or not self.anonymiser:
            # Plutôt qu'un simple message d'erreur, on rouvre le même
            # enregistrement avec une petite vue dédiée demandant
            # directement le mot de passe, à ce moment précis - aucun
            # autre paramètre déjà choisi n'est perdu, puisque c'est le
            # même enregistrement qui est simplement réaffiché autrement.
            # `not self.anonymiser` (v1.77.0) : un rapport affichant les
            # vrais noms des participants exige un mot de passe même pour
            # un simple affichage à l'écran, pas seulement pour un
            # téléchargement - sur demande, pour que la protection ne
            # dépende jamais du format choisi quand l'anonymisation est
            # désactivée.
            resultat = self._verifier_mot_de_passe_ou_demander("action_generate")
            if resultat:
                return resultat

        try:
            diagnostics = self._compute_report()
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001 - on veut un message clair, pas une trace brute
            _logger.exception("Échec de la génération du rapport")
            raise UserError(
                _(
                    "La génération du rapport a échoué : %(erreur)s\n\n"
                    "Ceci indique généralement qu'un nom de champ suppose par ce module "
                    "(voir NOTES_VALIDATION.md) ne correspond pas à votre instance. "
                    "Le détail complet est dans le journal serveur (logs) Odoo."
                ) % {"erreur": str(exc)}
            ) from exc

        # Le retour à l'écran (format "screen") s'appuie sur Odoo pour
        # recharger automatiquement la fiche déjà ouverte après un bouton de
        # type "object" - ce comportement s'est avéré peu fiable sur cette
        # instance (rien ne s'affichait malgré une génération réussie côté
        # serveur). On force donc explicitement le rechargement en
        # retournant une action ir.actions.act_window pointant sur ce même
        # enregistrement, plutôt que de se fier au rechargement implicite.
        action_reload = {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

        # Pour l'écran : retour direct d'une action "display_notification"
        # (chaînée vers le rechargement via "next"), PLUTÔT QUE la
        # notification par bus (_envoyer_notification) utilisée pour les
        # cas HTML/PDF ci-dessous (qui, eux, retournent une action
        # incompatible avec ce chaînage). Ce mécanisme direct est
        # confirmé fonctionner de façon fiable sur cette instance
        # (signalé fonctionnel par le passé, contrairement au bus/
        # websocket - voir NOTES_VALIDATION.md) puisqu'il ne dépend
        # d'aucune infrastructure de notification temps réel : la
        # réponse au clic contient directement le message à afficher.
        if diagnostics:
            motif_balises = re.compile(r"<[^>]+>")
            # U+2028 (LINE SEPARATOR) plutôt que "\n" : un simple retour à la
            # ligne ASCII est traité comme un espace collapsible par la
            # plupart des moteurs de rendu HTML (white-space:normal, le
            # comportement par défaut) - U+2028 est un VRAI caractère de
            # saut de ligne selon la spec Unicode/CSS, respecté même hors
            # d'un contexte HTML interprété (voir chiffres_gras() ci-dessus
            # pour le même genre de contournement, déjà nécessaire pour le
            # gras dans ce contexte précis).
            SAUT_LIGNE = "\u2028"
            apercu = SAUT_LIGNE.join(
                f"• {rb.chiffres_gras(motif_balises.sub('', d))}" for d in diagnostics[:8]
            )
            if len(diagnostics) > 8:
                apercu += _("%(sep)s… et %(n)s autre(s) - voir le détail complet en haut du rapport.") % {
                    "sep": SAUT_LIGNE, "n": len(diagnostics) - 8
                }
            titre_notif = _("Rapport généré avec %(n)s avertissement(s)") % {"n": len(diagnostics)}
            type_notif = "warning"
        else:
            apercu = _("Le rapport a été généré avec succès.")
            titre_notif = _("Rapport généré")
            type_notif = "success"

        if self.output_format == "html":
            resultat = self.action_download_html()
            self._envoyer_notification(_("Rapport généré"), _("Le fichier HTML est prêt."), "success")
            return resultat
        if self.output_format == "pdf":
            resultat = self.action_download_pdf()
            self._envoyer_notification(_("Rapport généré"), _("Le fichier PDF est prêt."), "success")
            return resultat

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": titre_notif,
                "message": apercu,
                "sticky": False,
                "type": type_notif,
                "next": action_reload,
            },
        }

    def _traiter_question(
        self, question, titre, lignes, date_rencontre, emails, participants,
        synth_matrice, synth_matrice_detail, synth_ouinon,
        synth_choix, synth_choix_detail, synth_textes, synth_item_date, synth_question_date,
        synth_choix_precisions, alertes_notes_basses, synth_item_par_date,
        colonne_par_ui=None,
    ):
        """Construit le HTML d'une question pour une rencontre donnée, et
        alimente au passage les accumulateurs de synthèse (dicts partagés,
        modifiés en place). Isolée dans sa propre méthode pour qu'un champ
        manquant sur UN type de question n'empêche pas le reste du rapport
        de se générer (voir l'appel dans _compute_report, enveloppé d'un
        try/except par question).

        `colonne_par_ui` (v1.87.0) : dict {user_input_id: colonne_id} - la
        colonne du tableau de réponses D'UN PARTICIPANT où ranger CETTE
        réponse précise (voir combiner_reponses_meme_sondage) - PAS la même
        chose que `date_rencontre`, qui reste la clé utilisée pour toute la
        logique de SYNTHÈSE (agrégée sur toute la rencontre, jamais par
        soumission individuelle). `None` ou absent : repli sur
        `date_rencontre` (comportement historique, avant v1.87.0)."""
        colonne_par_ui = colonne_par_ui or {}
        if question.question_type == "matrix":
            rows = self._get_rows(question)
            valeurs_par_item = defaultdict(list)
            detail_par_item = defaultdict(list)
            oui_non_par_item = defaultdict(lambda: {"oui": [], "non": 0})
            est_oui_non = set(self._get_columns(question).mapped("value")) <= {"Oui", "Non"}
            for ligne in lignes:
                if not ligne.matrix_row_id or not ligne.suggested_answer_id:
                    continue
                item = ligne.matrix_row_id.value
                val_txt = ligne.suggested_answer_id.value
                nom = self._respondent_nom(ligne.user_input_id)
                if est_oui_non:
                    if val_txt == "Oui":
                        oui_non_par_item[item]["oui"].append((nom, date_rencontre))
                        synth_ouinon[titre][item]["oui"].append((nom, date_rencontre))
                    elif val_txt == "Non":
                        oui_non_par_item[item]["non"] += 1
                        synth_ouinon[titre][item]["non"] += 1
                else:
                    num = rb.convertir_numerique(val_txt)
                    if num is not None:
                        valeurs_par_item[item].append(num)
                        synth_matrice[titre][item].append(num)
                        synth_question_date[titre][date_rencontre].append(num)
                        synth_item_par_date[titre][item][date_rencontre].append(num)
                        # La ventilation "Détail des notes" n'a de sens que pour
                        # une vraie note (1 à 5) - une réponse non numérique
                        # (ex. "Je n'étais pas là") n'y apporte rien et alourdit
                        # inutilement la liste ; elle reste par contre visible
                        # dans le tableau propre au participant concerné.
                        detail_par_item[item].append((val_txt, num, nom, date_rencontre))
                        synth_matrice_detail[titre][item].append((val_txt, num, nom, date_rencontre))
                        if item not in synth_item_date[titre]:
                            synth_item_date[titre][item] = date_rencontre
                        if num <= 2 and not any(
                            mot in (titre or "").lower() for mot in MOTS_CLES_QUESTIONS_AUTO_EVALUATION
                        ):
                            commentaire = self._commentaire_libre_pour(ligne.user_input_id)
                            alertes_notes_basses.append((date_rencontre, titre, item, nom, num, commentaire))
                cle = rb.normaliser_nom(nom)
                # v1.87.0 : la colonne du tableau (pas forcément
                # date_rencontre, voir colonne_par_ui) - date_rencontre
                # reste inchangé pour tout ce qui précède (synth_matrice,
                # synth_question_date, etc., à l'échelle de la rencontre).
                colonne = colonne_par_ui.get(ligne.user_input_id.id, date_rencontre)
                participants[cle]["reponses"].setdefault((colonne, titre), {})[item] = val_txt
            if est_oui_non:
                lignes_data = [
                    {"item": r.value, "oui": oui_non_par_item[r.value]["oui"], "non": oui_non_par_item[r.value]["non"]}
                    for r in rows
                ]
                return rb.section_oui_non(titre, lignes_data, emails, afficher_uniques=False)
            lignes_data = [
                {
                    # v1.78.0 : protège le nom du présentateur (s'il y en a
                    # un dans ce titre, voir rb.proteger_nom_dans_titre) -
                    # SEULEMENT le libellé affiché change, `valeurs_par_item`
                    # et `detail_par_item` ci-dessous restent indexés par le
                    # texte BRUT r.value (inchangé), donc aucun risque de
                    # rater une entrée par une clé qui ne correspondrait
                    # plus.
                    "item": rb.proteger_nom_dans_titre(r.value),
                    "valeurs": valeurs_par_item[r.value], "detail": detail_par_item[r.value],
                }
                for r in rows
            ]
            # Même date pour tous les items ici (celle de cette rencontre) -
            # redondant avec la date déjà visible dans l'en-tête de section,
            # mais garde le tooltip disponible même quand la Synthèse est
            # omise (une seule rencontre incluse dans le rapport).
            # Exclu pour les questions à volets fixes/récurrents (ex.
            # "Satisfaction globale", "Organisation et logistique") : un
            # tooltip de date n'y apporte rien d'utile, contrairement aux
            # présentations, différentes à chaque rencontre.
            est_volets_fixes = any(mot in (titre or "").lower() for mot in MOTS_CLES_VOLETS_FIXES)
            if date_rencontre and not est_volets_fixes:
                # v1.78.0 : mêmes clés que "item" dans lignes_data ci-dessus
                # (rb.proteger_nom_dans_titre(r.value), pas r.value brut) -
                # sinon ce dict ne correspondrait plus à rien pour une
                # question de type Présentations (la seule où ces deux
                # textes diffèrent), et le tooltip de date disparaîtrait
                # silencieusement pour ces lignes précises.
                dates_par_item_rencontre = {rb.proteger_nom_dans_titre(r.value): date_rencontre for r in rows}
            else:
                dates_par_item_rencontre = None
            return rb.section_matrice(
                titre, lignes_data, ventiler=self.ventiler_matrices, dates_par_item=dates_par_item_rencontre,
                colorer_seuils=not any(
                    mot in (titre or "").lower() for mot in MOTS_CLES_QUESTIONS_AUTO_EVALUATION
                ),
            )

        if question.question_type in ("simple_choice", "multiple_choice"):
            compteur, details = defaultdict(int), defaultdict(list)
            precisions_locales = []
            for ligne in lignes:
                nom = self._respondent_nom(ligne.user_input_id)
                if not ligne.suggested_answer_id:
                    # Pas un choix sélectionné : c'est potentiellement la
                    # ligne de commentaire "Autre, précisez" - enregistrée
                    # par Odoo comme une ligne SÉPARÉE (sans
                    # suggested_answer_id), pas sur la même ligne que le
                    # choix (confirmé par la documentation et le code
                    # source d'Odoo) - la précédente version de ce code
                    # cherchait à tort value_char_box sur la ligne DU
                    # CHOIX lui-même, qui ne l'a jamais, d'où l'échec.
                    precision = getattr(ligne, "value_char_box", None) or getattr(
                        ligne, "value_text_box", None
                    )
                    if precision:
                        precisions_locales.append((nom, precision))
                        synth_choix_precisions[titre].append((nom, precision))
                    continue
                val = ligne.suggested_answer_id.value
                compteur[val] += 1
                details[val].append((nom, date_rencontre))
                synth_choix[titre][val] += 1
                synth_choix_detail[titre][val].append((nom, date_rencontre))
                cle = rb.normaliser_nom(nom)
                # Une LISTE, pas une chaîne concaténée par des virgules -
                # une réponse à choix multiples s'affiche donc une par
                # ligne, triée (v1.86.0, voir tableau_reponses_personne()).
                # v1.87.0 : la colonne du tableau (pas forcément
                # date_rencontre, voir colonne_par_ui ci-dessus).
                colonne = colonne_par_ui.get(ligne.user_input_id.id, date_rencontre)
                participants[cle]["reponses"].setdefault((colonne, titre), []).append(val)
            return rb.section_choix(titre, compteur, details, emails, precisions=precisions_locales)

        if question.question_type in TYPES_TEXTE_LIBRE:
            entries = []
            for ligne in lignes:
                texte = ligne.value_text_box or ligne.value_char_box
                if not texte:
                    continue
                nom = self._respondent_nom(ligne.user_input_id)
                entries.append((texte, nom, date_rencontre))
                synth_textes[titre].append((texte, nom, date_rencontre))
                cle = rb.normaliser_nom(nom)
                # v1.87.0 : la colonne du tableau (pas forcément
                # date_rencontre, voir colonne_par_ui plus haut).
                colonne = colonne_par_ui.get(ligne.user_input_id.id, date_rencontre)
                participants[cle]["reponses"][(colonne, titre)] = texte
            return rb.section_textes(
                titre, entries, dedupliquer=self.dedupliquer_textes, emails=emails, attribuer_auteur=True,
            )

        # Types 'numerical_box', 'date', 'datetime' non couverts par souci de
        # temps - à ajouter au besoin en suivant le même patron ci-dessus.
        return ""

    def _envoyer_notification(self, titre, message, type_notif="info", sticky=False):
        """Notification envoyée via le bus temps réel d'Odoo, indépendamment
        de toute action retournée par le bouton en cours - fonctionne donc
        aussi bien pour un rechargement d'écran que pour un téléchargement
        HTML/PDF. Un commit immédiat suit l'envoi pour la rendre visible
        pendant que la transaction est encore en cours (sans risque de
        laisser un état incohérent : voir _envoyer_progression ci-dessous
        pour le contexte).

        Protégé par un try/except : après l'incident avec `notify_warning`
        (méthode qui n'existait pas sur cette instance, provoquant un
        plantage), toute nouvelle tentative d'utiliser une API de
        notification non testée en conditions réelles doit rester sans
        risque pour la génération elle-même si elle échoue."""
        try:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {"type": type_notif, "title": titre, "message": message, "sticky": sticky},
            )
            self.env.cr.commit()
        except Exception:  # noqa: BLE001
            _logger.warning("Impossible d'envoyer une notification (%s)", titre, exc_info=True)

    def _envoyer_progression(self, message):
        """Notification de progression pendant une génération longue (ex.
        « Tous les sondages ») - aucune donnée persistante n'est encore
        écrite à ce stade de la génération (seule l'affectation finale de
        report_html, tout à la fin, écrit réellement quelque chose), donc
        le commit immédiat de _envoyer_notification() ne risque pas de
        laisser un état incohérent en base."""
        self._envoyer_notification(_("Génération en cours…"), message, "info")

    def _compute_report(self):
        self.ensure_one()

        emails = {}  # nom normalisé -> courriel
        # Accumulateurs pour la synthèse (fusion par titre de question / de ligne)
        synth_matrice = defaultdict(lambda: defaultdict(list))       # titre -> item -> [valeurs]
        synth_matrice_detail = defaultdict(lambda: defaultdict(list))  # titre -> item -> [(texte,num,nom,date)]
        synth_item_date = defaultdict(dict)  # titre -> item -> date_rencontre (première occurrence)
        synth_choix_precisions = defaultdict(list)  # titre -> [(nom, texte précision "Autre"), ...]
        alertes_notes_basses = []  # [(date_rencontre, titre, item, nom, num, commentaire), ...] pour la section "À surveiller"
        synth_question_date = defaultdict(lambda: defaultdict(list))  # titre -> date -> [valeurs numériques, tous items confondus]
        synth_item_par_date = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # titre -> item -> date -> [valeurs]
        synth_ouinon = defaultdict(lambda: defaultdict(lambda: {"oui": [], "non": 0}))
        synth_choix = defaultdict(lambda: defaultdict(int))
        synth_choix_detail = defaultdict(lambda: defaultdict(list))
        synth_textes = defaultdict(list)  # titre -> [(texte,nom,date)]
        synth_types = {}  # titre -> question_type (pour savoir comment rendre la synthèse)

        # Registre des participants, toutes rencontres confondues
        participants = {}  # cle -> {"nom":..., "email":..., "dates": set(), "reponses": {(date,titre): valeur_txt}}

        corps_rencontres = []
        toc_rencontres = []
        stats_rencontres = []
        dates_rencontres = []
        evenements_rencontres = []
        survey_ids_rencontres = []
        nb_reponses_trouvees = 0
        diagnostics = []

        mots_exclus = [
            m.strip().lower() for m in (self.exclude_title_keywords or "").split(",") if m.strip()
        ]
        surveys_a_traiter = self.survey_ids
        if mots_exclus:
            # Signalé (v1.67.0) : exclure un sondage par mot-clé est un
            # comportement VOULU par l'utilisateur (ce filtre est déjà
            # visible dans le résumé des paramètres en haut du rapport,
            # voir _resume_parametres() plus bas) - PAS une erreur ou un
            # problème technique. Ne plus l'ajouter aux diagnostics (qui
            # alimentent le bandeau "N problème(s) rencontré(s)") -
            # contrairement à un sondage à 0 réponse ou une erreur de
            # traitement, une exclusion volontaire ne mérite pas d'être
            # signalée comme un problème.
            surveys_exclus = surveys_a_traiter.filtered(
                lambda s: any(mot in (s.title or "").lower() for mot in mots_exclus)
            )
            surveys_a_traiter -= surveys_exclus

        nb_total_a_traiter = len(surveys_a_traiter)
        heure_dernier_avis = time.time()
        for i, survey in enumerate(surveys_a_traiter.sorted(lambda s: s.id), 1):
            if nb_total_a_traiter > 1 and time.time() - heure_dernier_avis >= 3:
                self._envoyer_progression(
                    _("%(i)s / %(total)s sondages traités…") % {"i": i - 1, "total": nb_total_a_traiter}
                )
                heure_dernier_avis = time.time()
            user_inputs = self._user_inputs(survey)
            if not user_inputs:
                # Signalé (v1.66.0) : si un seuil minimum de participants est
                # actif (>= 1), un sondage à 0 réponse "retenue" ici (après
                # les filtres additionnels de _user_inputs - date_from/
                # date_to, exclusions - voir NOTES_VALIDATION.md section -32)
                # n'est pas surprenant, c'est une conséquence normale des
                # filtres choisis - ne pas l'indiquer comme un problème du
                # tout dans ce cas. Affiché seulement si AUCUN seuil minimum
                # n'est en vigueur (0), où un sondage à 0 réponse est alors
                # plus surprenant et mérite d'être signalé.
                if self.filtre_participants_min < 1:
                    total_survey = self.env["survey.user_input"].search_count([("survey_id", "=", survey.id)])
                    # Message volontairement court : l'explication générale (à
                    # quoi vérifier) n'est affichée qu'une seule fois, dans le
                    # bandeau d'ensemble - la répéter pour chaque sondage à 0
                    # réponse rendait le bandeau illisible dès qu'il y en avait
                    # plusieurs à la fois (ex. 10 sondages "Pause café" à 0).
                    diagnostics.append(
                        f"« {rb.echapper(survey.title)} » : <strong>0/{total_survey}</strong> réponse(s) retenue(s)"
                    )
                continue
            nb_reponses_trouvees += len(user_inputs)
            date_envoi, date_expiration = self._dates_envoi_expiration(survey)
            annee_repli = self._annee_repli_titre(survey)
            date_titre_extraite = self._extraire_date_titre(survey.title, annee_repli=annee_repli)
            date_rencontre = self._rencontre_date(survey, user_inputs, date_titre=date_titre_extraite)
            if not date_titre_extraite and date_rencontre:
                # La date affichée n'est PAS celle du titre - repli sur la
                # date de soumission (la plus ancienne réponse) faute d'avoir
                # pu en reconnaître une dans le titre. Signalé explicitement
                # plutôt qu'en silence, pour pouvoir corriger la
                # reconnaissance si le titre contient bel et bien une date
                # dans un format non prévu.
                diagnostics.append(
                    f"« {rb.echapper(survey.title)} » : aucune date reconnue dans le titre - date de "
                    f"soumission utilisée en repli ({date_rencontre}). Si ce titre contient "
                    "bien une date, signalez son format exact pour corriger la reconnaissance."
                )
            anchor = rb.slug(date_rencontre or survey.title)

            # Liste des participants de cette rencontre (pour l'affichage
            # sous l'en-tête, comme dans la version autonome).
            noms_participants = []
            noms_participants_avec_email = []
            # v1.87.0 : une "colonne" du tableau de réponses d'un participant
            # correspond soit à la RENCONTRE (mode combiné - comportement
            # historique), soit à CETTE soumission précise (mode par défaut,
            # décoché) - ce dict associe chaque user_input de cette rencontre
            # à la colonne où ses réponses doivent être rangées, utilisé plus
            # bas par _traiter_question() sans jamais toucher à `date_rencontre`
            # lui-même (qui reste, lui, à l'échelle de la RENCONTRE pour toute
            # la logique de synthèse par ailleurs inchangée).
            colonne_par_ui = {}
            for ui in user_inputs:
                nom = self._respondent_nom(ui)
                courriel = self._respondent_email(ui)
                cle = rb.normaliser_nom(nom)
                # v1.93.0 : en mode anonymisé, AUCUN courriel n'alimente les listes - ni lien
                # ✉ (qui devenait « mailto:[courriel masqué] »), ni suffixe « - courriel », ni
                # champ « Courriels (N) » à copier. Les retirer ICI, à la source, plutôt que de
                # les masquer après coup. Le courriel reste dans p["email"] : il sert encore
                # à masquer toute occurrence exacte dans une réponse libre.
                if courriel and not self.anonymiser:
                    emails[cle] = courriel
                noms_participants.append(nom)
                noms_participants_avec_email.append((nom, courriel))
                p = participants.setdefault(
                    cle, {
                        "nom": nom, "email": courriel, "dates": set(), "reponses": {}, "partner": None,
                        "soumissions": [], "colonnes": {},
                    }
                )
                p["dates"].add(date_rencontre)
                if courriel and not p.get("email"):
                    p["email"] = courriel
                if ui.partner_id and not p.get("partner"):
                    p["partner"] = ui.partner_id
                # v1.86.0 : détail de CETTE soumission précise (date/heure de
                # réponse, date limite, entrée test?) - pas seulement la date
                # de la rencontre déjà ajoutée ci-dessus. Une même personne
                # peut avoir plusieurs survey.user_input pour LE MÊME sondage
                # si elle a répondu plus d'une fois (ex. en changeant d'idée)
                # - chacune listée séparément ici plutôt que fusionnée, pour
                # qu'on puisse voir toutes ses soumissions distinctement.
                #
                # "Date de réponse" = end_datetime (déjà un champ VÉRIFIÉ sur
                # survey.user_input dans ce module, voir
                # _compute_rlq_stats() dans survey_survey.py, qui l'utilise
                # pour calculer la durée moyenne) - repli sur start_datetime
                # (quand la personne a OUVERT le sondage) si end_datetime est
                # vide, ex. une réponse partielle jamais terminée.
                date_reponse_brute = ui.end_datetime or ui.start_datetime
                date_reponse_locale = (
                    fields.Datetime.context_timestamp(self, date_reponse_brute) if date_reponse_brute else None
                )
                date_limite_locale = (
                    fields.Datetime.context_timestamp(self, ui.deadline) if ui.deadline else None
                )
                # v1.90.0 : temps de réponse (end_datetime - start_datetime),
                # affiché sur les colonnes du tableau de réponses (voir
                # p["colonnes"] plus bas) - None si l'un des deux horodatages
                # manque, ou si end_datetime précède start_datetime (données
                # incohérentes, ne devrait normalement pas arriver).
                duree_reponse_texte = None
                if ui.start_datetime and ui.end_datetime and ui.end_datetime > ui.start_datetime:
                    duree_reponse_texte = rb.duree_humaine((ui.end_datetime - ui.start_datetime).total_seconds())
                p["soumissions"].append({
                    "date_rencontre": date_rencontre,
                    "date_reponse": date_reponse_locale.strftime("%Y-%m-%d %H:%M") if date_reponse_locale else None,
                    "date_limite": date_limite_locale.strftime("%Y-%m-%d %H:%M") if date_limite_locale else None,
                    "test": bool(ui.test_entry),
                    # v1.86.0 : commentaire libre d'un membre de l'équipe sur
                    # CETTE soumission précise (voir rlq_commentaire_staff
                    # sur survey.user_input, dans survey_survey.py) - vide
                    # si personne n'en a laissé.
                    "commentaire": ui.rlq_commentaire_staff or None,
                })

                # v1.87.0 : colonne du tableau de réponses pour CETTE
                # soumission - voir le champ combiner_reponses_meme_sondage.
                # v1.90.0 : "ligne1"/"ligne2" plutôt qu'un "libelle" unique -
                # signalé comme trompeur (l'heure de réponse était affichée
                # à côté de la date DU SONDAGE plutôt que de la date RÉELLE
                # de réponse, quand les deux diffèrent - ex. un sondage
                # rempli plusieurs jours après la rencontre). "ligne1" =
                # date du sondage (titre, INCHANGÉE) ; "ligne2" = date ET
                # heure réelles de réponse (voir tableau_reponses_personne()
                # pour le rendu exact, deux lignes avec <br/>).
                if self.combiner_reponses_meme_sondage:
                    # Comportement historique : une seule colonne par
                    # rencontre - identique pour toutes les soumissions
                    # d'une même personne à ce même sondage (la dernière
                    # traitée "gagne" dans le tableau, comme avant v1.86.0).
                    colonne_id = date_rencontre
                    p["colonnes"][colonne_id] = {
                        "ligne1": str(date_rencontre) if date_rencontre else (survey.title or ""),
                        "ligne2": date_reponse_locale.strftime("%Y-%m-%d %H:%M") if date_reponse_locale else None,
                        "duree": duree_reponse_texte,
                        "ancre": rb.slug(date_rencontre) if date_rencontre else None,
                        "tri": str(date_rencontre) if date_rencontre else "",
                        "test": bool(ui.test_entry),
                    }
                else:
                    # Par défaut : une colonne PROPRE à cette soumission.
                    colonne_id = (date_rencontre, ui.id)
                    p["colonnes"][colonne_id] = {
                        "ligne1": str(date_rencontre) if date_rencontre else (survey.title or ""),
                        "ligne2": date_reponse_locale.strftime("%Y-%m-%d %H:%M") if date_reponse_locale else None,
                        "duree": duree_reponse_texte,
                        # L'ancre reste basée sur la RENCONTRE (pas la
                        # soumission) - c'est la section de la rencontre qui
                        # existe dans le rapport, pas une section par
                        # soumission individuelle.
                        "ancre": rb.slug(date_rencontre) if date_rencontre else None,
                        "tri": (
                            date_reponse_locale.strftime("%Y-%m-%d %H:%M:%S")
                            if date_reponse_locale else (str(date_rencontre) if date_rencontre else "")
                        ),
                        # v1.88.0 : affiché directement dans l'en-tête de
                        # colonne (voir tableau_reponses_personne()) -
                        # "Détail des soumissions" ne le répète plus dans ce
                        # mode, devenu redondant avec cet en-tête.
                        "test": bool(ui.test_entry),
                    }
                colonne_par_ui[ui.id] = colonne_id

            jour = rb.jour_semaine(date_rencontre) if date_rencontre else None
            suffixe_jour_html = f" <span class='jour-semaine'>({jour})</span>" if jour else ""
            contenu = [
                f"<section class='rencontre' id='{anchor}'><h2>{rb.echapper(date_rencontre or survey.title)}"
                f"{suffixe_jour_html}"
                f" <span class='badge'>{len(user_inputs)} réponse(s)</span></h2>"
            ]
            contenu.append(
                f"<p class='titre-sondage'>Inscrit : <strong>{survey.rlq_answer_count}</strong> · "
                f"Terminé : <strong>{survey.rlq_answer_done_count}</strong> · "
                f"Débuté sans terminer : <strong>{survey.rlq_answer_in_progress_count}</strong></p>"
            )
            if date_rencontre and survey.title:
                # Les liens vers la configuration du sondage et le mode test
                # pointent vers le BACKEND Odoo (/web#model=...) : utiles pour
                # un·e organisateur·rice qui consulte le rapport dans Odoo,
                # mais inappropriés (et une fuite d'URL interne) si le rapport
                # est partagé publiquement, ce que l'anonymisation signale
                # comme une intention possible. Titre en texte simple et lien
                # « Tester sondage » entièrement retiré dans ce cas.
                if self.anonymiser:
                    lien_config_sondage = rb.echapper(survey.title)
                    lien_test_html = ""
                else:
                    lien_config_url = self._url_absolue(f"/web#model=survey.survey&id={survey.id}&view_type=form")
                    lien_config_sondage = (
                        f"<a href='{rb.echapper_attr(lien_config_url)}' "
                        f"target='_blank'>{rb.echapper(survey.title)}</a>"
                    )
                    url_test = self._lien_test_sondage(survey)
                    lien_test_html = (
                        f" (<em><a href='{rb.echapper_attr(url_test)}' target='_blank'>Tester sondage</a></em>)"
                        if url_test else ""
                    )
                contenu.append(f"<p class='titre-sondage'>{lien_config_sondage}{lien_test_html}</p>")
            evenement_trouve = self._lien_evenement(survey, date_survey=date_titre_extraite)
            evenements_rencontres.append(evenement_trouve.id if evenement_trouve else None)
            if evenement_trouve:
                morceaux_evt = [
                    f"Événement : {rb.echapper(evenement_trouve.display_name)}" if self.anonymiser
                    else f"Événement : {self._html_lien_evenement(evenement_trouve)}"
                ]
                lien_public = self._lien_evenement_public(evenement_trouve)
                if lien_public:
                    lien_public_html = (
                        f"<a href='{rb.echapper_attr(lien_public)}' target='_blank'>page publique</a>"
                    )
                    morceaux_evt.append(f"(<em>{lien_public_html}</em>)")
                contenu.append(f"<p class='titre-sondage'>{' '.join(morceaux_evt)}</p>")
                details_evt_html = self._html_details_evenement(evenement_trouve)
                if details_evt_html:
                    contenu.append(details_evt_html)
                presents, inscrits, non_inscrits = self._repartition_presence_evenement(
                    evenement_trouve, noms_participants_avec_email
                )
                if presents or inscrits or non_inscrits:
                    for libelle_groupe, noms_groupe in (
                        ("Répondants présents à l'événement (validés)", presents),
                        ("Répondants inscrits (présence non validée)", inscrits),
                        ("Répondants non inscrits à l'événement", non_inscrits),
                    ):
                        if not noms_groupe:
                            continue
                        puces = "".join(f"<li>{rb.lien_personne(n)}</li>" for n in sorted(set(noms_groupe), key=rb.normaliser_nom))
                        contenu.append(
                            f"<details class='detail-oui'><summary>{rb.echapper(libelle_groupe)} "
                            f"({len(set(noms_groupe))})</summary><ul class='liste-texte'>{puces}</ul></details>"
                        )
            if date_envoi or date_expiration:
                morceaux = []
                if date_envoi:
                    morceaux.append(f"Créé le {date_envoi.date() if hasattr(date_envoi, 'date') else date_envoi}")
                if date_expiration:
                    morceaux.append(
                        f"Expire le {date_expiration.date() if hasattr(date_expiration, 'date') else date_expiration}"
                    )
                contenu.append(f"<p class='titre-sondage' style='margin-top:.6rem;'>{' · '.join(morceaux)}</p>")
            if noms_participants:
                liens = ", ".join(rb.lien_personne(n) for n in sorted(set(noms_participants), key=rb.normaliser_nom))
                contenu.append(f"<p class='liste-participants'><strong>Participants :</strong> {liens}</p>")

            # Présentateurs de CETTE rencontre précise (déduits du titre des
            # présentations, voir rb.extraire_presentateur) - liens vers leur
            # propre ligne dans "Appréciation des présentateurs" (ancre
            # ajoutée à chaque ligne de ce tableau, voir plus bas).
            presentateurs_ici = set()
            for question_p in survey.question_and_page_ids.filtered(
                lambda q: q.question_type == "matrix" and "présentation" in (q.title or "").lower()
            ):
                for row in self._get_rows(question_p):
                    _titre_p, nom_p = rb.extraire_presentateur(row.value)
                    if nom_p:
                        presentateurs_ici.add(nom_p)
            if presentateurs_ici:
                liens_presentateurs = ", ".join(
                    # v1.78.0 : jeton plutôt que le nom réel directement pour
                    # le texte AFFICHÉ (voir rb.jeton_presentateur - résolu
                    # vers le nom réel tout à la fin, anonymisé ou non) -
                    # SEUL l'ancre (href) reste basée sur le nom réel, pour
                    # continuer à pointer vers la bonne ligne de
                    # "Appréciation des présentateurs" (qui utilise, elle
                    # aussi, le nom réel comme base d'ancre - voir
                    # section_appreciation_presentateurs()).
                    rb.lien_ancre(f"presentateur-{rb.slug(nom_p)}", rb.echapper(rb.jeton_presentateur(nom_p)))
                    for nom_p in sorted(presentateurs_ici, key=rb.normaliser_nom)
                )
                contenu.append(
                    f"<p class='liste-participants'><strong>Présentateur(s) :</strong> {liens_presentateurs}</p>"
                )

            if self.voir_non_repondants:
                non_repondants = self.env["survey.user_input"].search([
                    ("survey_id", "=", survey.id), ("state", "=", "new"),
                ])
                if non_repondants:
                    noms_nr = sorted(
                        {self._respondent_nom(ui) for ui in non_repondants}, key=rb.normaliser_nom
                    )
                    puces_nr = "".join(f"<li>{rb.echapper(n)}</li>" for n in noms_nr)
                    contenu.append(
                        f"<p class='liste-participants'><strong>N'ont pas répondu ({len(noms_nr)}) :"
                        f"</strong></p><ul class='liste-texte'>{puces_nr}</ul>"
                    )

            # Chargement des lignes de réponse UNE SEULE FOIS par rencontre
            # (plutôt qu'une fois par question) et regroupement par question :
            # avec >100 réponses, refaire un .filtered() sur l'ensemble des
            # lignes à chaque question (comme avant) devenait très lent, voire
            # semblait ne plus répondre du tout.
            toutes_lignes = user_inputs.mapped(self._lines_field_name())
            lignes_par_question = defaultdict(lambda: self.env[self._answer_model_name()])
            for ligne in toutes_lignes:
                lignes_par_question[ligne.question_id.id] |= ligne

            for question in survey.question_ids.sorted("sequence"):
                titre = question.title
                synth_types.setdefault(titre, question.question_type)
                try:
                    lignes = lignes_par_question.get(question.id, self.env[self._answer_model_name()])
                    if not lignes:
                        continue
                    contenu.append(
                        self._traiter_question(
                            question, titre, lignes, date_rencontre, emails, participants,
                            synth_matrice, synth_matrice_detail, synth_ouinon,
                            synth_choix, synth_choix_detail, synth_textes, synth_item_date, synth_question_date,
                            synth_choix_precisions, alertes_notes_basses, synth_item_par_date,
                            colonne_par_ui,
                        )
                    )
                except UserError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    _logger.exception(
                        "Question '%s' (type %s) ignorée suite à une erreur", titre, question.question_type
                    )
                    diagnostics.append(
                        f"Question « {rb.echapper(titre)} » (type {question.question_type}) ignorée : "
                        f"{rb.echapper(exc.__class__.__name__)}: {rb.echapper(str(exc))}"
                    )
                    contenu.append(
                        f"<p class='vide'>⚠ Question « {rb.echapper(titre)} » ignorée (erreur - voir le "
                        "message d'avertissement en haut du rapport et les logs serveur).</p>"
                    )

            contenu.append("</section>")
            corps_rencontres.append("".join(contenu))
            libelle_toc = f"{date_rencontre} ({jour})" if (date_rencontre and jour) else (date_rencontre or survey.title)
            toc_rencontres.append((libelle_toc, anchor))
            dates_rencontres.append(date_rencontre)
            survey_ids_rencontres.append(survey.id)
            stats_rencontres.append((
                libelle_toc, anchor, survey.rlq_answer_count, survey.rlq_answer_done_count,
                survey.rlq_answer_in_progress_count, survey.rlq_answer_duration_avg_seconds,
                survey.rlq_question_count,
            ))

        # Ordre chronologique inversé (la rencontre la plus récente en
        # premier) - les libellés sont au format AAAA-MM-JJ quand une date a
        # été trouvée, donc un tri lexicographique équivaut à un tri
        # chronologique. Les deux listes sont réordonnées ensemble pour que
        # le corps du rapport suive le même ordre que la table des matières.
        if toc_rencontres:
            paires = sorted(
                zip(toc_rencontres, corps_rencontres, dates_rencontres, evenements_rencontres, survey_ids_rencontres),
                key=lambda t: t[0][0], reverse=True,
            )
            toc_rencontres = [p[0] for p in paires]
            corps_rencontres = [p[1] for p in paires]
            dates_rencontres = [p[2] for p in paires]
            evenements_rencontres = [p[3] for p in paires]
            survey_ids_rencontres = [p[4] for p in paires]
            stats_rencontres.sort(key=lambda s: s[0], reverse=True)

        # "Note globale" de chaque rencontre : moyenne composite des 3
        # questions listées dans MOTS_CLES_NOTE_GLOBALE, insérée en tête
        # de chaque section de rencontre (juste après son titre) pour
        # une comparaison rapide entre rencontres - LE métrique
        # d'amélioration continue le plus important selon l'utilisateur.
        # Utilise synth_matrice_detail (déjà peuplé pour TOUTES les
        # rencontres à ce stade), filtré par date pour isoler les
        # valeurs propres à CHAQUE rencontre individuellement.
        valeurs_note_globale_par_date = defaultdict(list)
        for titre_q, items in synth_matrice_detail.items():
            if not any(mot in (titre_q or "").lower() for mot in MOTS_CLES_NOTE_GLOBALE):
                continue
            for _item, entrees in items.items():
                for _texte, num, _nom, date_entree in entrees:
                    if num is not None and date_entree:
                        valeurs_note_globale_par_date[date_entree].append(num)
        # dates_rencontres est trié du plus récent au plus ancien (voir le tri
        # chronologique plus haut) - les "N rencontres précédentes" d'une
        # rencontre à l'index i sont donc celles aux index SUIVANTS (i+1,
        # i+2, ...), pas aux index précédents.
        NB_RENCONTRES_REFERENCE = 6
        # Catégorise chaque rencontre incluse (Premier mardi/Pause café/
        # Portes ouvertes/Autre) - la moyenne de référence pour une
        # rencontre donnée n'utilise QUE les rencontres précédentes de LA
        # MÊME catégorie, une Pause café et des Portes ouvertes n'ayant pas
        # forcément la même dynamique de base ; les comparer sans distinction
        # pourrait être trompeur.
        ids_premier_mardi = set(self._survey_ids_premier_mardi().ids)
        ids_pause_cafe = set(self._survey_ids_pause_cafe().ids)
        ids_portes_ouvertes = set(self._survey_ids_portes_ouvertes().ids)

        def _categorie_pour(survey_id):
            if survey_id in ids_premier_mardi:
                return "premier_mardi"
            if survey_id in ids_pause_cafe:
                return "pause_cafe"
            if survey_id in ids_portes_ouvertes:
                return "portes_ouvertes"
            return "autre"

        categories_par_index = [_categorie_pour(sid) for sid in survey_ids_rencontres]

        # Recueilli EN MÊME TEMPS que actions_suivi_html ci-dessous (une
        # seule lecture par sondage, pas une deuxième boucle) - alimente
        # la liste consolidée de la Synthèse (section_actions_suivi_
        # consolidee), qui coexiste avec la note affichée sur chaque
        # rencontre individuellement (voir demande [2]).
        entrees_actions_suivi_toutes = []

        for i, date_rencontre_i in enumerate(dates_rencontres):
            valeurs_ici = valeurs_note_globale_par_date.get(date_rencontre_i, [])
            categorie_ici = categories_par_index[i]
            indices_precedents = [
                j for j in range(i + 1, len(dates_rencontres))
                if categories_par_index[j] == categorie_ici
            ][:NB_RENCONTRES_REFERENCE]
            valeurs_precedentes = [
                v for j in indices_precedents
                for v in valeurs_note_globale_par_date.get(dates_rencontres[j], [])
            ]
            moyenne_reference = rb.moyenne(valeurs_precedentes) if valeurs_precedentes else None
            note_globale_html = rb.section_note_globale(
                valeurs_ici, moyenne_reference=moyenne_reference, nb_reference=len(indices_precedents)
            )
            survey_id_ici = survey_ids_rencontres[i]
            texte_actions_ici = (
                self.env["survey.survey"].browse(survey_id_ici).rlq_actions_suivi
                if survey_id_ici else False
            )
            actions_suivi_html = rb.section_actions_suivi(texte_actions_ici)
            if texte_actions_ici and texte_actions_ici.strip():
                entrees_actions_suivi_toutes.append((date_rencontre_i, texte_actions_ici))
            if note_globale_html or actions_suivi_html:
                corps_rencontres[i] = corps_rencontres[i].replace(
                    "</h2>", "</h2>" + note_globale_html + actions_suivi_html, 1
                )
        graphique_tendance_note_globale = rb.section_tendance_question(
            "Note globale de la rencontre", valeurs_note_globale_par_date,
            limites_controle=True, detecter_derive=True
        )

        # "Ce qui a le plus bougé" : pour chaque question ayant au moins 2
        # rencontres avec des valeurs, compare la moyenne des deux dernières
        # rencontres chronologiquement - calculé ici, avant la boucle
        # principale de la Synthèse, pour être inséré en tête.
        mouvements = []
        for titre, dates_valeurs in synth_question_date.items():
            if any(mot in (titre or "").lower() for mot in MOTS_CLES_QUESTIONS_AUTO_EVALUATION):
                continue
            dates_avec_valeurs = sorted(d for d, v in dates_valeurs.items() if d and v)
            if len(dates_avec_valeurs) >= 2:
                avant = rb.moyenne(dates_valeurs[dates_avec_valeurs[-2]])
                apres = rb.moyenne(dates_valeurs[dates_avec_valeurs[-1]])
                if avant is not None and apres is not None:
                    mouvements.append((titre, avant, apres))
        section_top_mouvements_html = rb.section_top_mouvements(mouvements)
        section_actions_suivi_consolidee_html = rb.section_actions_suivi_consolidee(
            entrees_actions_suivi_toutes
        )

        # ------------------------------------------------------------
        # Synthèse (fusion par titre de question à travers les rencontres)
        # ------------------------------------------------------------
        contenu_synthese = [
            "<section class='rencontre' id='synthese'><h2>Synthèse - toutes rencontres confondues</h2>"
            + graphique_tendance_note_globale + section_top_mouvements_html
            + section_actions_suivi_consolidee_html
        ]
        for titre, qtype in synth_types.items():
            if qtype == "matrix":
                if titre in synth_ouinon:
                    items = list(synth_ouinon[titre].keys())
                    lignes_data = [
                        {"item": it, "oui": synth_ouinon[titre][it]["oui"], "non": synth_ouinon[titre][it]["non"]}
                        for it in items
                    ]
                    contenu_synthese.append(rb.section_oui_non(titre, lignes_data, emails, afficher_uniques=True))
                elif titre in synth_matrice:
                    items = list(synth_matrice[titre].keys())
                    lignes_data = [
                        {
                            # v1.78.0 : protège le nom du présentateur, comme
                            # pour le détail par rencontre (voir
                            # _traiter_question()) - même raisonnement.
                            "item": rb.proteger_nom_dans_titre(it),
                            "valeurs": synth_matrice[titre][it], "detail": synth_matrice_detail[titre][it],
                        }
                        for it in items
                    ]
                    est_tendance_par_item = any(
                        mot in (titre or "").lower() for mot in MOTS_CLES_TENDANCE_PAR_ITEM
                    )
                    est_volets_fixes = any(mot in (titre or "").lower() for mot in MOTS_CLES_VOLETS_FIXES)
                    est_auto_evaluation = any(
                        mot in (titre or "").lower() for mot in MOTS_CLES_QUESTIONS_AUTO_EVALUATION
                    )
                    # Mêmes clés PROTÉGÉES que "item" ci-dessus, sinon ce
                    # dict ne correspondrait plus à rien pour les questions
                    # de type Présentations (voir la même correction faite
                    # sur dates_par_item_rencontre dans _traiter_question()).
                    dates_item_titre = synth_item_date.get(titre)
                    dates_item_proteges = (
                        {rb.proteger_nom_dans_titre(it): d for it, d in dates_item_titre.items()}
                        if dates_item_titre else None
                    )
                    contenu_synthese.append(
                        rb.section_matrice(
                            titre, lignes_data, ventiler=self.ventiler_matrices,
                            dates_par_item=None if est_volets_fixes else dates_item_proteges,
                            colorer_seuils=not est_auto_evaluation,
                        )
                    )
                    if not est_auto_evaluation:
                        contenu_synthese.append(
                            rb.section_tendance_question(titre, synth_question_date.get(titre, {}))
                        )
                    # Tendance détaillée PAR ITEM (plutôt qu'une seule
                    # moyenne combinée) pour les questions listées dans
                    # MOTS_CLES_TENDANCE_PAR_ITEM - identifiées par un
                    # mot-clé dans leur titre plutôt qu'une correspondance
                    # exacte, pour rester robuste si le titre exact
                    # diffère légèrement d'une instance à l'autre.
                    if est_tendance_par_item:
                        for it in items:
                            contenu_synthese.append(
                                rb.section_tendance_question(it, synth_item_par_date[titre].get(it, {}))
                            )
            elif qtype in ("simple_choice", "multiple_choice") and titre in synth_choix:
                contenu_synthese.append(
                    rb.section_choix(
                        titre, synth_choix[titre], synth_choix_detail[titre], emails,
                        precisions=synth_choix_precisions.get(titre, []),
                    )
                )
            elif qtype in TYPES_TEXTE_LIBRE and titre in synth_textes:
                contenu_synthese.append(
                    rb.section_textes(
                        titre, synth_textes[titre],
                        dedupliquer=self.dedupliquer_textes, emails=emails, attribuer_auteur=True,
                    )
                )
        contenu_synthese.append("</section>")

        # ------------------------------------------------------------
        # Participants
        # ------------------------------------------------------------
        contenu_participants = ["<h2>Participants</h2>"]
        toc_participants = []
        event_dispo = "event.registration" in self.env

        # Noms (normalisés) ayant réellement une fiche dans CE rapport -
        # pour distinguer, dans les listes de membres d'étiquette, ceux sur
        # qui un clic mène quelque part de ceux qui n'ont pas répondu à un
        # sondage inclus dans ce rapport précis.
        noms_avec_fiche = set(participants.keys())

        # Cache pour éviter de refaire la même requête si plusieurs
        # participants du rapport partagent la même étiquette : liste tous
        # les membres RÉELS de chaque étiquette (pas seulement ceux ayant
        # répondu à un sondage inclus dans ce rapport), comme demandé.
        membres_etiquette_cache = {}

        # Décompte des sondages remplis (total) et des événements inscrits,
        # par lot pour tous les participants ayant une fiche contact - une
        # seule requête groupée chacun, plutôt qu'une requête par personne
        # (qui devenait coûteuse avec un grand nombre de participants).
        partner_ids = [p["partner"].id for p in participants.values() if p.get("partner")]
        sondages_par_partenaire = {}
        evenements_par_partenaire = {}
        dates_sondages_par_partenaire = defaultdict(list)
        dates_evenements_par_partenaire = defaultdict(list)
        if partner_ids:
            for partner, compte in self.env["survey.user_input"]._read_group(
                [("partner_id", "in", partner_ids), ("state", "=", "done")],
                ["partner_id"], ["__count"],
            ):
                sondages_par_partenaire[partner.id] = compte
            # Liste des dates (une requête groupée, pas une par personne) :
            # tous les sondages remplis, tous temps confondus, avec la date
            # de chacun - réutilise rlq_date_titre (déjà disponible sur
            # N'IMPORTE QUEL sondage, pas seulement ceux inclus dans ce
            # rapport, puisque c'est un champ calculé du modèle lui-même),
            # avec repli sur la date de création si le titre n'a pas pu
            # être daté.
            tous_user_inputs = self.env["survey.user_input"].sudo().search([
                ("partner_id", "in", partner_ids), ("state", "=", "done"),
            ])
            for ui in tous_user_inputs:
                survey_lie = ui.survey_id
                d = survey_lie.rlq_date_titre or (survey_lie.create_date.date() if survey_lie.create_date else None)
                if d and ui.partner_id:
                    dates_sondages_par_partenaire[ui.partner_id.id].append((d, survey_lie.id))
            if event_dispo:
                for partner, compte in self.env["event.registration"]._read_group(
                    [("partner_id", "in", partner_ids)],
                    ["partner_id"], ["__count"],
                ):
                    evenements_par_partenaire[partner.id] = compte
                toutes_inscriptions = self.env["event.registration"].sudo().search([
                    ("partner_id", "in", partner_ids),
                ])
                for insc in toutes_inscriptions:
                    evenement_lie = insc.event_id
                    if not insc.partner_id:
                        continue
                    d = evenement_lie.date_begin.date() if getattr(evenement_lie, "date_begin", None) else None
                    if d:
                        url_evenement = self._url_absolue(
                            f"/web#model={evenement_lie._name}&id={evenement_lie.id}&view_type=form"
                        )
                        dates_evenements_par_partenaire[insc.partner_id.id].append(
                            (d, url_evenement, evenement_lie.id)
                        )
                    else:
                        # Date introuvable EN BASE LOCALE (date_begin vide sur
                        # l'événement) - signalé explicitement plutôt qu'omis
                        # en silence comme avant (le total "Événements
                        # inscrits" ci-dessous, lui, comptait déjà cette
                        # inscription, d'où un décompte qui ne correspondait
                        # plus aux dates affichées). Aucune tentative de
                        # trouver la date ailleurs (site web, calendrier
                        # externe...) : ce texte de repli reste local, sans
                        # lien externe - donc rien qui "sorte sur Internet"
                        # depuis un rapport HTML/PDF déjà exporté hors
                        # d'Odoo.
                        texte_repli = (
                            "date non disponible dans ce rapport "
                            f"({evenement_lie.display_name})"
                        )
                        dates_evenements_par_partenaire[insc.partner_id.id].append(
                            (texte_repli, None, evenement_lie.id)
                        )

        participants_tries = sorted(participants.items(), key=lambda kv: rb.normaliser_nom(kv[1]["nom"]))

        # Événements liés aux rencontres INCLUSES dans ce rapport précis
        # (pas "tous temps") - utilisé pour savoir si un événement inscrit
        # d'un participant (une donnée "tous temps", potentiellement hors
        # de ce rapport) correspond à une rencontre présente ICI, auquel
        # cas son lien doit pointer DANS le rapport plutôt que vers la
        # fiche externe de l'événement dans le backend Odoo. Comparé par
        # IDENTIFIANT D'ÉVÉNEMENT (pas par date : une comparaison de
        # dates s'est avérée peu fiable en pratique, l'événement pouvant
        # avoir une date légèrement différente de celle extraite du
        # titre du sondage) - réutilise le même essai de correspondance
        # que _lien_evenement(), déjà fait une fois par rencontre plus
        # haut, plutôt que de le refaire.
        evenements_rencontres_par_id = {
            eid: date for eid, date in zip(evenements_rencontres, dates_rencontres) if eid
        }
        # Repli par DATE en plus de l'ID d'événement - _lien_evenement() peut
        # ne trouver aucun événement lié pour certaines rencontres (aucune
        # relation directe en base ET aucun événement à une date
        # correspondante trouvé par sa propre recherche) alors qu'un
        # event.registration existe bel et bien à cette même date - la
        # correspondance par ID seule s'est avérée insuffisante en
        # pratique (signalé : les liens restaient tous externes).
        dates_rencontres_incluses = {str(d) for d in dates_rencontres if d}
        dates_rencontres_par_survey_id = dict(zip(survey_ids_rencontres, dates_rencontres))

        for _cle, p in participants_tries:
            dates_triees = sorted((d for d in p["dates"] if d), reverse=True)
            anchor = "personne-" + rb.slug(p["nom"])
            toc_participants.append((f"{p['nom']} ({len(dates_triees)})", anchor))

        for _cle, p in participants_tries:
            dates_triees = sorted((d for d in p["dates"] if d), reverse=True)
            anchor = "personne-" + rb.slug(p["nom"])
            contenu_participants.append(
                f"<section class='personne' id='{anchor}'><h2>{rb.echapper(p['nom'])}"
                f" <span class='badge'>{len(dates_triees)} participation(s)</span></h2>"
            )
            if p.get("email") and not self.anonymiser:
                contenu_participants.append(
                    f"<p class='courriel'>Courriel : <a href='mailto:{rb.echapper_attr(p['email'])}'>"
                    f"{rb.echapper(p['email'])}</a></p>"
                )

            # Informations complémentaires tirées de la fiche contact
            # (res.partner), quand le répondant y est lié. sudo() ici pour
            # la même raison que _respondent_nom/_respondent_email : un
            # « Utilisateur » du module Sondage peut légitimement générer
            # ce rapport sans avoir un accès direct, via les règles
            # d'enregistrement d'Odoo, à CHAQUE fiche contact individuelle
            # (confirmé par une erreur "Access Denied by record rules" en
            # production) - montrer ces coordonnées est le but même de ce
            # rapport, déjà protégé par ailleurs (confirmation
            # obligatoire, mot de passe pour tout téléchargement).
            partner = p.get("partner")
            if partner:
                partner = partner.sudo()
            details = []
            # v1.77.0 : coordonnées et étiquettes RETIRÉES (pas seulement
            # masquées) en mode anonymisé - une anonymisation renforcée sur
            # demande, suite à une lecture des exigences de la Loi 25 :
            # contrairement à un simple masquage textuel en aval (comme
            # pour le nom, voir _anonymiser_html()), une donnée qui n'est
            # jamais rendue dans le HTML ne peut pas fuiter par un
            # remplacement manqué.
            # v1.91.0 : les lignes « Sondages remplis (total, tous temps) » et
            # « Événements inscrits » (avec leurs listes de dates précises) sont
            # AUSSI retirées en mode anonymisé, sur demande : une longue suite
            # de dates agit comme une empreinte comportementale qui peut
            # identifier quelqu'un même sans son nom (ex. 24 dates d'événements).
            if partner and not self.anonymiser:
                # v1.90.0 : téléphone/mobile/ville/pays sur UNE SEULE ligne,
                # séparés par une virgule et au moins 4 espaces INSÉCABLES
                # (\xa0 - un espace normal serait réduit à un seul par le
                # rendu HTML) - plutôt qu'une ligne par coordonnée comme
                # avant, sur demande. Étiquettes reste sur sa propre ligne
                # (peut être longue, avec la liste des autres membres).
                coordonnees = []
                if partner.phone:
                    coordonnees.append(f"Téléphone : {rb.echapper(partner.phone)}")
                if partner.mobile:
                    coordonnees.append(f"Mobile : {rb.echapper(partner.mobile)}")
                if partner.city:
                    coordonnees.append(f"Ville : {rb.echapper(partner.city)}")
                if partner.country_id:
                    coordonnees.append(f"Pays : {rb.echapper(partner.country_id.name)}")
                if coordonnees:
                    details.append(",\xa0\xa0\xa0\xa0".join(coordonnees))
                if partner.category_id:
                    puces_etiquettes = []
                    for etiquette in partner.category_id:
                        if etiquette.id not in membres_etiquette_cache:
                            membres_etiquette_cache[etiquette.id] = self.env["res.partner"].sudo().search(
                                [("category_id", "=", etiquette.id)]
                            ).mapped("name")
                        membres = membres_etiquette_cache[etiquette.id]
                        puces_etiquettes.append(
                            f"{rb.echapper(etiquette.name)} "
                            f"{rb.liste_personnes_simple(membres, noms_avec_fiche=noms_avec_fiche)}"
                        )
                    details.append("Étiquettes : " + ", ".join(puces_etiquettes))
            if partner and not self.anonymiser:
                nb_sondages_total = sondages_par_partenaire.get(partner.id, 0)
                paires_sondages = dates_sondages_par_partenaire.get(partner.id, [])
                paires_sondages_liees = [
                    (
                        d,
                        f"#{rb.slug(dates_rencontres_par_survey_id[sid])}"
                        if dates_rencontres_par_survey_id.get(sid)
                        else self._url_absolue(f"/web#model=survey.survey&id={sid}&view_type=form"),
                    )
                    for d, sid in paires_sondages
                ]
                liste_dates_sondages = rb.liste_dates_avec_liens(paires_sondages_liees)
                details.append(
                    f"Sondages remplis (total, tous temps) : {nb_sondages_total}"
                    + (f" — {liste_dates_sondages}" if liste_dates_sondages else "")
                )
                if event_dispo:
                    nb_evenements = evenements_par_partenaire.get(partner.id, 0)
                    paires_evenements = dates_evenements_par_partenaire.get(partner.id, [])
                    def _lien_ou_ancre_evenement(d, url, eid):
                        if eid in evenements_rencontres_par_id:
                            return f"#{rb.slug(evenements_rencontres_par_id[eid])}"
                        if str(d) in dates_rencontres_incluses:
                            return f"#{rb.slug(str(d))}"
                        return url

                    paires_evenements_liees = [
                        (d, _lien_ou_ancre_evenement(d, url, eid))
                        for d, url, eid in paires_evenements
                    ]
                    liste_dates_evenements = rb.liste_dates_avec_liens(paires_evenements_liees)
                    details.append(
                        f"Événements inscrits : {nb_evenements}"
                        + (f" — {liste_dates_evenements}" if liste_dates_evenements else "")
                    )
            if details:
                lignes_info = "".join(f"<div>{d}</div>" for d in details)
                contenu_participants.append(f"<div class='infos-participant'>{lignes_info}</div>")

            # v1.88.0 : "Détail des soumissions" n'est plus affiché en mode
            # PAR SOUMISSION (comportement par défaut) - devenu redondant
            # avec les colonnes du tableau ci-dessous, qui montrent
            # maintenant chacune sa propre date/heure (et son statut
            # "Entrée test", voir plus bas) directement en en-tête. Gardé
            # SEULEMENT en mode combiné, où le tableau n'a qu'une colonne
            # par rencontre et ne peut donc plus distinguer les soumissions
            # individuelles - "Détail des soumissions" reste alors le seul
            # endroit où les voir.
            if self.combiner_reponses_meme_sondage:
                contenu_participants.append(rb.section_soumissions_participant(p.get("soumissions", [])))
            # v1.87.0 : liste triée des colonnes du tableau de réponses -
            # PAS dates_triees (qui reste la liste des rencontres, utilisée
            # pour le compteur "X participation(s)" et la table des
            # matières) - voir p["colonnes"], alimenté plus haut selon
            # combiner_reponses_meme_sondage. La plus récente en premier,
            # cohérent avec le reste du rapport (clé "tri" = date+heure ou
            # date seule selon le mode, toujours une chaîne comparable).
            colonnes_tableau = [
                {
                    "id": colonne_id, "ligne1": info["ligne1"], "ligne2": info.get("ligne2"),
                    "duree": info.get("duree"), "ancre": info["ancre"], "test": info.get("test", False),
                }
                for colonne_id, info in sorted(
                    p.get("colonnes", {}).items(), key=lambda kv: kv[1]["tri"], reverse=True
                )
            ]
            contenu_participants.append(rb.tableau_reponses_personne(p["reponses"], colonnes_tableau, synth_types))
            contenu_participants.append("</section>")


        # ------------------------------------------------------------
        # Assemblage final
        # ------------------------------------------------------------
        bloc_diagnostic = ""
        if diagnostics:
            puces_diag = "".join(f"<li>{d}</li>" for d in diagnostics)
            explication_zero = ""
            if any("réponse(s) retenue(s)" in d for d in diagnostics):
                explication_zero = (
                    "<p>Pour les sondages à 0 réponse retenue ci-dessus : vérifiez le statut "
                    "des réponses (cochez « Inclure les réponses partielles » si elles ne sont "
                    "pas encore toutes terminées), la plage de dates, et les exclusions actives "
                    "(participant, étiquette, mot-clé du titre).</p>"
                )
            # Signalé (v1.60.0) : présenter les sondages à 0 réponse
            # retenue avec la même sévérité qu'une vraie erreur technique
            # est trompeur si l'utilisateur a lui-même choisi des filtres
            # (plage de dates, exclusions) qui EXPLIQUENT ce 0 - ce n'est
            # pas nécessairement un problème, juste une conséquence
            # attendue de ces filtres. Un bandeau neutre (bleu) est utilisé
            # à la place du rouge d'alarme lorsque TOUS les diagnostics
            # sont de ce type (aucune AUTRE catégorie d'erreur mélangée).
            tout_est_zero_reponse = all("réponse(s) retenue(s)" in d for d in diagnostics)
            if tout_est_zero_reponse:
                couleur_fond, couleur_bordure, couleur_texte = "#e7f1fb", "#5b9bd5", "#1c3d5a"
                titre_bandeau = f"ℹ {len(diagnostics)} sondage(s) sans réponse retenue avec ces filtres :"
            else:
                couleur_fond, couleur_bordure, couleur_texte = "#fdecea", "#d93025", "#5c2b27"
                titre_bandeau = f"⚠ {len(diagnostics)} problème(s) rencontré(s) pendant la génération de ce rapport :"
            bloc_diagnostic = (
                f"<div style='background:{couleur_fond};border:2px solid {couleur_bordure};"
                f"color:{couleur_texte};padding:.8rem 1.2rem;border-radius:6px;margin-bottom:1.2rem;'>"
                f"<strong style='color:{couleur_bordure};'>{titre_bandeau}</strong><ul>{puces_diag}</ul>"
                f"{explication_zero}"
                "<em>Le détail complet (trace technique) se trouve dans les logs serveur Odoo.</em></div>"
            )
        if nb_reponses_trouvees == 0:
            self.report_html = (
                f"<div class='rlq-rapport'><style>{rb.CSS}</style>{bloc_diagnostic}{self._resume_parametres()}"
                "<p class='vide'>Aucune réponse trouvée pour l'ensemble des sondages sélectionnés "
                "avec les critères actuels (statut, plage de dates, exclusions). Voir le détail "
                "ci-dessus.</p></div>"
            )
            self.state = "done"
            return diagnostics

        toc_participants_html = "".join(
            f"<li>{rb.lien_ancre(a, rb.echapper(lbl))}</li>"
            for lbl, a in sorted(toc_participants, key=lambda t: rb.normaliser_nom(t[0]))
        )
        resume_parametres = self._resume_parametres()

        # Une seule rencontre incluse : la Synthèse serait identique au détail
        # de cette unique rencontre - on l'omet.
        une_seule_rencontre = len(stats_rencontres) <= 1

        # Tableau récapitulatif Inscrit/Terminé/Débuté par rencontre, en tête
        # du rapport global - la Synthèse y figure aussi comme une ligne de
        # plus (sans ces trois chiffres, qui n'ont pas de sens pour elle).
        # Cette information rendant redondante l'ancienne colonne "Rapport
        # global" (qui ne faisait que lister les mêmes dates), celle-ci est
        # retirée : la liste des participants dispose ainsi de toute la
        # largeur, répartie sur plusieurs colonnes.
        lignes_stats = ""
        if not une_seule_rencontre:
            lignes_stats += (
                f"<tr><td>{rb.lien_ancre('synthese', 'Synthèse')}</td>"
                "<td class='centre'>—</td><td class='centre'>—</td><td class='centre'>—</td>"
                "<td class='centre'>—</td><td class='centre'>—</td></tr>"
            )
        lignes_stats += "".join(
            f"<tr><td>{rb.lien_ancre(a, rb.echapper(lbl))}</td><td class='centre'>{insc}</td>"
            f"<td class='centre'>{term}</td><td class='centre'>{debute}</td>"
            f"<td class='centre'>{duree}</td><td class='centre'>{nb_q}</td></tr>"
            for lbl, a, insc, term, debute, duree, nb_q in stats_rencontres
        )
        tableau_stats = (
            "<table class='tableau'><thead><tr><th>Rencontre</th><th>Inscrit</th>"
            "<th>Terminé</th><th>Débuté sans terminer</th><th>Durée moyenne (s)</th>"
            f"<th>Nb. questions</th></tr></thead><tbody>{lignes_stats}</tbody></table>"
        ) if stats_rencontres else ""
        graphique_evolution = rb.section_evolution(stats_rencontres) + rb.section_taux_reponse(stats_rencontres)

        contenu_synthese_html = "" if une_seule_rencontre else "".join(contenu_synthese)

        # Calculé ici (plutôt que plus loin, à son unique autre usage) pour
        # savoir dès la construction de la table des matières si la section
        # "Appréciation des présentateurs" aura du contenu ou non - un lien
        # vers une section qui ne serait pas générée serait un lien mort.
        donnees_presentateurs = defaultdict(lambda: {"valeurs": [], "detail": [], "presentations": {}})
        for titre_question, items in synth_matrice.items():
            if "présentation" not in titre_question.lower():
                continue
            for item, valeurs in items.items():
                titre_sans_nom, presentateur = rb.extraire_presentateur(item)
                if presentateur:
                    donnees_presentateurs[presentateur]["valeurs"].extend(valeurs)
                    donnees_presentateurs[presentateur]["detail"].extend(
                        synth_matrice_detail[titre_question][item]
                    )
                    date_presentation = synth_item_date.get(titre_question, {}).get(item)
                    donnees_presentateurs[presentateur]["presentations"][item] = (
                        titre_sans_nom, date_presentation, valeurs
                    )

        # Navigation vers les sections principales, en tête du rapport -
        # les sections conditionnelles (À surveiller, Appréciation des
        # présentateurs) ne sont incluses que si elles auront effectivement
        # du contenu, pour ne jamais pointer vers une ancre inexistante.
        liens_sections = [f'<li>{rb.lien_ancre("toc-participants", "Liste des participants")}</li>']
        if self.inclure_section_surveiller and alertes_notes_basses:
            liens_sections.append(f'<li>{rb.lien_ancre("a-surveiller", "À surveiller")}</li>')
        if donnees_presentateurs:
            liens_sections.append(
                f'<li>{rb.lien_ancre("appreciation-presentateurs", "Appréciation des présentateurs")}</li>'
            )
        nav_sections = f"<ul class='nav-sections'>{''.join(liens_sections)}</ul>"

        table_matieres = f"""
<nav class='table-matieres'>
  <h2>Table des matières</h2>
  {nav_sections}
  {resume_parametres}
  {tableau_stats}
  {graphique_evolution}
  <h3 id="toc-participants">Participants ({len(toc_participants)})</h3>
  <ul class='liste-individus liste-individus-large'>{toc_participants_html}</ul>
</nav>"""
        selecteur_theme = """
<div class='selecteur-theme'>
  <strong>Thème :</strong>
  <button type="button" onclick="document.getElementById('rlq-rapport-root').setAttribute('data-theme','blue')">Bleu</button>
  <button type="button" onclick="document.getElementById('rlq-rapport-root').setAttribute('data-theme','dark')">Sombre</button>
  <button type="button" onclick="document.getElementById('rlq-rapport-root').setAttribute('data-theme','green')">Vert</button>
  <button type="button" onclick="document.getElementById('rlq-rapport-root').setAttribute('data-theme','purple')">Violet</button>
</div>"""
        date_generation_locale = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        # v1.79.0 : libellé différent selon self.anonymiser - sur demande,
        # pour ne pas affirmer que le rapport "contient" des
        # renseignements personnels quand l'anonymisation est active
        # (elle retire déjà l'essentiel), tout en restant honnête sur le
        # fait qu'aucune anonymisation automatique ne peut garantir un
        # résultat parfait à 100% (ex. un nom mentionné dans le texte
        # libre d'une réponse, que ce mécanisme ne détecte pas).
        if self.anonymiser:
            texte_avis = (
                "⚠ Ce rapport PEUT contenir des renseignements personnels sur les "
                "participants qui n'auraient pas été bien anonymisés."
            )
        else:
            texte_avis = (
                "⚠ Ce rapport contient des renseignements personnels sur les participants "
                "(noms, courriels, coordonnées)."
            )
        # Titre du sondage en évidence : pertinent surtout quand un seul sondage
        # est sélectionné (ex. un rapport ciblé pour un présentateur) ; avec
        # plusieurs sondages, un titre unique n'aurait pas de sens.
        titre_sondage_evidence = ""
        if len(self.survey_ids) == 1 and self.survey_ids.title:
            titre_sondage_evidence = (
                "<h2 style='text-align:center;margin:.3rem 0 1rem 0;'>"
                f"{rb.echapper(self.survey_ids.title)}</h2>"
            )
        avis_renseignements_personnels = (
            "<p style='background:#fff3cd;border:1px solid #ffcc00;color:#5c4813;"
            "padding:.6rem 1rem;border-radius:6px;margin-bottom:1rem;'>"
            f"{texte_avis}</p>"
        )
        bandeau_generation = (
            f"<p class='titre-sondage' style='text-align:right;'>Rapport généré le "
            f"<strong>{date_generation_locale.strftime('%Y-%m-%d %H:%M')}</strong> "
            f"{date_generation_locale.strftime('%Z')} (heure locale)</p>"
        )
        pied_de_page = (
            "<p style='text-align:center;color:var(--texte-attenue);font-size:.8rem;"
            f"margin-top:2rem;'>Généré par le module {self._default_debug_info()}"
            "<br>© Services-Linux Conseils Inc — contact@exemple.org, contact@exemple.org"
            "<br>rlq_survey_report est distribué sous licence "
            "<a href='https://www.gnu.org/licenses/why-affero-gpl.fr.html' target='_blank' "
            "style='color:inherit;'>AGPL-3</a>.</p>"
        )
        section_surveiller = (
            rb.section_a_surveiller(alertes_notes_basses) if self.inclure_section_surveiller else ""
        )
        # "Appréciation des présentateurs" : donnees_presentateurs a déjà
        # été calculé plus haut (avant table_matieres, pour savoir si un
        # lien vers cette section doit y figurer) - reste ici seulement à
        # produire le rendu HTML final.
        section_presentateurs = rb.section_appreciation_presentateurs([
            {
                "presentateur": nom, "presentateur_affichage": rb.jeton_presentateur(nom),
                "valeurs": d["valeurs"], "detail": d["detail"],
                "presentations": [
                    (titre_sans_nom, date, valeurs_presentation)
                    for titre_sans_nom, date, valeurs_presentation in sorted(
                        d["presentations"].values(), key=lambda t: t[0]
                    )
                ],
            }
            for nom, d in donnees_presentateurs.items()
        ])
        html = f"""
<div id="rlq-rapport-root" class="rlq-rapport" data-theme="{self.theme}" tabindex="0" style="outline:none;">
<style>{rb.CSS}</style>
{selecteur_theme}
{titre_sondage_evidence}
{avis_renseignements_personnels}
{bandeau_generation}
{bloc_diagnostic}
{table_matieres}
{contenu_synthese_html}
{''.join(corps_rencontres)}
{''.join(contenu_participants)}
{section_surveiller}
{section_presentateurs}
{pied_de_page}
</div>
"""
        if self.anonymiser:
            html = self._anonymiser_html(html, participants_tries)
        # v1.78.0 : résout les jetons de présentateurs (voir
        # rb.jeton_presentateur) vers leur nom réel - TOUJOURS, que le
        # rapport soit anonymisé ou non, puisque ce mécanisme protège
        # seulement CES occurrences précises contre le remplacement par
        # pseudonyme ci-dessus ; il ne doit jamais laisser un jeton
        # visible tel quel dans le rapport livré.
        html = self._resoudre_jetons_presentateurs(html, donnees_presentateurs.keys())
        self.report_html = html
        self.state = "done"
        attachment_ecran = self._sauvegarder_copie_ecran(html)
        self._journaliser_acces("ecran", attachment_ecran.name if attachment_ecran else None, attachment_ecran)
        return diagnostics

    def _sauvegarder_copie_ecran(self, html):
        """Sauvegarde une copie persistante du rapport affiché à l'écran,
        comme pièce jointe (ir.attachment) - sur demande, pour alimenter
        le menu "Fichiers déjà générés" (une bibliothèque réutilisable
        sans avoir à régénérer d'une personne à l'autre) même pour un
        simple affichage, pas seulement un téléchargement explicite.

        Protégée par mot de passe SI un mot de passe est déjà renseigné
        (self.mot_de_passe) - obligatoire pour un rapport NON anonymisé
        depuis v1.77.0, donc cette copie l'est alors aussi ; optionnel
        pour un rapport anonymisé, donc cette copie reste alors non
        chiffrée si aucun mot de passe n'a été saisi, cohérent avec ce
        qui se passe déjà pour un téléchargement HTML dans ce cas.

        Ne lève jamais d'erreur : un problème de sauvegarde de la copie
        ne doit jamais empêcher l'affichage du rapport lui-même - retourne
        None dans ce cas (log de l'erreur, _journaliser_acces gère déjà
        une pièce jointe absente)."""
        try:
            document = (
                "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
                f"<title>Rapport de sondage</title></head><body>{html}</body></html>"
            )
            # Chiffrée seulement si un mot de passe est réellement requis : une
            # copie d'un rapport anonymisé reste en clair même si un mot de
            # passe par défaut est pré-rempli dans le formulaire.
            mdp_copie = self._mot_de_passe_effectif("screen")
            if mdp_copie:
                document = self._html_protege_par_mot_de_passe(document, mdp_copie)
            plage_dates = self._suffixe_plage_dates_nom_fichier()
            horodatage_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            nom_fichier = (
                f"RapportSondage-{self._prefixe_nom_fichier('screen')}"
                f"{plage_dates + '-' if plage_dates else ''}"
                f"{horodatage_local.strftime('%Y%m%d.%H%M%S')}.html"
            )
            return self.env["ir.attachment"].sudo().create({
                "name": nom_fichier,
                "type": "binary",
                "datas": base64.b64encode(document.encode("utf-8")),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "text/html",
            })
        except Exception:  # noqa: BLE001 - ne doit jamais empêcher l'affichage du rapport
            _logger.exception("Échec de la sauvegarde de la copie persistante du rapport affiché à l'écran")
            return None

    def _resoudre_jetons_presentateurs(self, html, noms_presentateurs):
        """Remplace chaque jeton produit par rb.jeton_presentateur(nom) par
        le nom réel (échappé) correspondant - dernière étape de la
        construction du rapport, après l'anonymisation éventuelle (voir
        action_generate ci-dessus). `noms_presentateurs` : les noms
        RÉELS de tous les présentateurs de ce rapport (ex.
        donnees_presentateurs.keys()) - le jeton étant un hachage à sens
        unique du nom, il n'existe pas d'autre façon de retrouver le nom
        réel à partir du jeton seul."""
        for nom in noms_presentateurs:
            html = html.replace(rb.jeton_presentateur(nom), rb.echapper(nom))
        return html

    def _journaliser_acces(self, action, nom_fichier=None, attachment=None):
        """Ajoute une entrée à l'historique d'accès (rlq.survey.report.acces)
        - qui, quand, quelle action, quel fichier le cas échéant - à appeler
        SEULEMENT après le succès réel de l'action (jamais avant, ni en cas
        d'erreur) : voir NOTES_VALIDATION.md pour la portée exacte de cet
        historique (bonne pratique de traçabilité, PAS le registre
        d'incidents de confidentialité exigé par la Loi 25, un concept
        différent).

        `attachment` (v1.80.0) : la pièce jointe ir.attachment déjà créée
        pour cette génération - gardée comme référence (`attachment_id`),
        et son CONTENU copié dans `fichier_telecharger` (v1.83.0, CORRECTIF
        CRITIQUE - voir le docstring du modèle rlq.survey.report.acces
        pour le détail complet : la version précédente exposait le
        téléchargement via un champ lié directement à cette pièce jointe,
        combiné à une règle d'accès qui a cassé l'accès aux pièces jointes
        de tout Odoo pour le groupe Sondage - jamais plus de règle d'accès
        sur ir.attachment dans ce module). `None` seulement si la création
        de la pièce jointe elle-même a échoué (ne doit jamais bloquer la
        journalisation de l'accès pour autant).

        sudo() : la création de cette entrée ne doit jamais échouer à cause
        d'un droit d'accès sur res.users ou sur ce modèle lui-même - un
        historique d'accès qui pourrait silencieusement ne pas s'écrire
        selon les droits de la personne qui consulte le rapport perdrait
        justement l'utilité qu'on lui cherche.

        `resume_sondages` liste TOUTES les DATES (rlq_date_titre, déjà
        stockée sur survey.survey), PAS les titres complets - sur
        demande, les titres rendaient cette colonne beaucoup trop longue
        à lire pour un rapport couvrant de nombreuses rencontres. Sur
        deux lignes plutôt que tronquée si la liste est longue (plus de
        10 dates) - pour ne jamais en omettre, seulement présenter plus
        compactement."""
        dates = sorted(d for d in self.survey_ids.mapped("rlq_date_titre") if d)
        textes_dates = [str(d) for d in dates]
        if len(textes_dates) > 10:
            milieu = (len(textes_dates) + 1) // 2
            resume = ", ".join(textes_dates[:milieu]) + "\n" + ", ".join(textes_dates[milieu:])
        else:
            resume = ", ".join(textes_dates)
        self.env["rlq.survey.report.acces"].sudo().create({
            "user_id": self.env.user.id,
            "action": action,
            "nom_fichier": nom_fichier,
            "attachment_id": attachment.id if attachment else False,
            # sudo() ICI aussi : la personne qui vient de générer le
            # rapport a forcément accès à SA PROPRE pièce jointe fraîchement
            # créée, mais sudo() élimine tout risque de coincidence de
            # droits pour autant - cette copie doit toujours réussir.
            "fichier_telecharger": attachment.sudo().datas if attachment else False,
            "anonymise": self.anonymiser,
            "nb_sondages": len(self.survey_ids),
            "resume_sondages": resume[:250],
        })

    def action_back(self):
        self.ensure_one()
        self.state = "draft"
        # Même correctif que pour action_generate : retourner True ne
        # rechargeait pas la fiche de façon fiable sur cette instance
        # ("ne fait rien et sort").
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

    def _criteres_manquants_mot_de_passe(self):
        """Retourne la liste des critères manquants (niveau PCI DSS v4.0
        8.3.6, en vigueur depuis le 31 mars 2025) pour le mot de passe
        actuel, ou une liste vide s'il est suffisamment solide. La norme
        PCI DSS elle-même n'exige littéralement que des caractères
        alphabétiques ET numériques ; la règle appliquée ici va plus loin
        en exigeant les 4 types de caractères (minuscule, majuscule,
        chiffre, spécial), pour une résistance réellement supérieure aux
        attaques hors ligne - voir l'aide du champ mot_de_passe pour le
        détail communiqué à l'utilisateur."""
        mdp = self.mot_de_passe or ""
        manquants = []
        if len(mdp) < 12:
            manquants.append(_("au moins 12 caractères"))
        if not re.search(r"[a-z]", mdp):
            manquants.append(_("au moins une lettre minuscule"))
        if not re.search(r"[A-Z]", mdp):
            manquants.append(_("au moins une lettre majuscule"))
        if not re.search(r"[0-9]", mdp):
            manquants.append(_("au moins un chiffre"))
        if not re.search(r"[^a-zA-Z0-9]", mdp):
            manquants.append(_("au moins un caractère spécial (ex. ! @ # $ %)"))
        return manquants

    def _valider_solidite_mot_de_passe(self):
        """Lève une erreur si le mot de passe ne respecte pas les critères
        minimaux - utilisée là où un arrêt net est approprié. Voir aussi
        _verifier_mot_de_passe_ou_demander(), qui gère à la fois
        l'absence ET la faiblesse d'un mot de passe en rouvrant la
        fenêtre de demande plutôt qu'en s'arrêtant sur une erreur sans
        possibilité de corriger immédiatement."""
        manquants = self._criteres_manquants_mot_de_passe()
        if manquants:
            raise UserError(
                _(
                    "Le mot de passe ne respecte pas les critères minimaux (niveau PCI "
                    "DSS) : il lui manque %(criteres)s."
                ) % {"criteres": ", ".join(manquants)}
            )

    @api.model
    def _mot_de_passe_par_defaut(self):
        """Mot de passe pré-rempli dans le formulaire, lu depuis le paramètre
        système `rlq_survey_report.mot_de_passe_defaut` (créé SEULEMENT s'il est absent
        par _creer_parametre_mot_de_passe_si_absent(), modifiable ensuite par un
        administrateur sans toucher au code). Retourne False si le paramètre est vide
        ou absent - aucun mot de passe n'est alors pré-rempli."""
        return self.env["ir.config_parameter"].sudo().get_param(
            "rlq_survey_report.mot_de_passe_defaut", ""
        ) or False

    @api.model
    def _creer_parametre_mot_de_passe_si_absent(self):
        """Crée le paramètre système du mot de passe par défaut, avec le marqueur livré,
        SEULEMENT s'il n'existe pas déjà : une valeur existante - même vide, qui désactive
        le pré-remplissage - n'est JAMAIS remplacée.

        Appelée par data/ir_config_parameter_mot_de_passe.xml (balise <function>, hors
        noupdate : exécutée à chaque installation ET mise à jour). POURQUOI PAS un
        <record> XML : noupdate="1" ne protège que contre une mise à jour (-u). En mode
        « init » (module installé avec -i, ou désinstallé puis réinstallé), Odoo recharge
        les données en IGNORANT noupdate - le mot de passe défini par l'administrateur
        était alors remplacé par le marqueur (signalé en production, v1.92.0).

        Détache aussi l'ancien identifiant XML (créé par les versions 1.75 à 1.92) : un
        enregistrement lié à un module est supprimé avec lui à la désinstallation. Ne doit
        JAMAIS empêcher le chargement du module : toute erreur est journalisée, pas levée.
        """
        try:
            with self.env.cr.savepoint():
                params = self.env["ir.config_parameter"].sudo()
                if not params.search([("key", "=", CLE_PARAMETRE_MOT_DE_PASSE)], limit=1):
                    params.create({
                        "key": CLE_PARAMETRE_MOT_DE_PASSE,
                        "value": MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER,
                    })
                anciens = self.env["ir.model.data"].sudo().search([
                    ("module", "=", "rlq_survey_report"),
                    ("name", "=", "ir_config_parameter_mot_de_passe_defaut"),
                ])
                if anciens:
                    anciens.unlink()
        except Exception:
            _logger.exception("Impossible de créer le paramètre %s", CLE_PARAMETRE_MOT_DE_PASSE)
            return False
        return True

    def _mot_de_passe_requis(self, format_fichier):
        """Un mot de passe est-il requis pour ce format ?
        - "screen" (affichage à l'écran), "html" et "pdf" : seulement si le
          rapport n'est PAS anonymisé. (La règle « écran » est celle de la
          v1.77.0 : un rapport montrant les vrais noms exige un mot de passe
          même à l'écran ; un rapport anonymisé n'en exige jamais, ni à
          l'écran ni en fichier HTML/PDF.)
        - "excel" : TOUJOURS - cet export n'applique pas l'anonymisation, il
          contient les vrais noms et courriels des participants."""
        if format_fichier in ("screen", "html", "pdf") and self.anonymiser:
            return False
        return True

    def _mot_de_passe_effectif(self, format_fichier):
        """Le mot de passe à appliquer au fichier de ce format, ou False s'il
        ne doit PAS être chiffré - un fichier anonymisé est livré en clair
        même si un mot de passe est pré-rempli dans le formulaire."""
        if not self._mot_de_passe_requis(format_fichier):
            return False
        return self.mot_de_passe or False

    def action_afficher_mot_de_passe(self):
        """Affiche le mot de passe actuellement saisi (masqué dans le champ)
        dans une notification à l'écran, à la demande - retournée directement
        comme action client (le mécanisme fiable déjà utilisé ailleurs dans ce
        module), sans HTML ni JavaScript : les deux approches essayées
        auparavant pour ce besoin (attribut title=, champ Html) ont échoué,
        dont une en faisant planter l'interface."""
        self.ensure_one()
        if not self.mot_de_passe:
            raise UserError(_("Aucun mot de passe n'est saisi pour le moment."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Mot de passe du fichier"),
                "message": self.mot_de_passe,
                "type": "info",
                "sticky": True,
            },
        }

    def _verifier_mot_de_passe_ou_demander(self, action_suivante):
        """Vérifie que le mot de passe est présent (dans les deux champs,
        entré deux fois), que les deux saisies correspondent, et que le
        mot de passe est suffisamment solide.

        Si l'un OU l'autre champ est vide, rouvre simplement la fenêtre
        de demande de mot de passe (rien à signaler comme erreur -
        l'utilisateur n'a encore rien soumis). Si les deux champs sont
        remplis mais qu'il y a un problème (ne correspondent pas, ou
        trop faible), lève une UserError - une fenêtre native d'Odoo,
        fiable et bien visible, plutôt qu'une notification bus (qui
        s'est déjà avérée peu fiable sur cette instance). Cette erreur
        s'affiche par-dessus la fenêtre de demande de mot de passe (déjà
        ouverte à ce stade), qui reste donc affichée pour une correction
        immédiate une fois l'erreur fermée.

        Retourne l'action à retourner par l'appelant si le mot de passe
        manque encore, ou None si tout est en ordre (l'appelant peut
        alors poursuivre normalement) - ne retourne jamais en cas
        d'erreur de correspondance/solidité, puisque l'exception
        interrompt déjà l'exécution à cet endroit."""
        format_fichier = {
            "action_download_html": "html",
            "action_download_pdf": "pdf",
            "action_export_excel": "excel",
        }.get(action_suivante, self.output_format)
        if not self._mot_de_passe_requis(format_fichier):
            return None
        if not self.mot_de_passe or not self.mot_de_passe_confirmation:
            return self._action_demander_mot_de_passe(action_suivante)
        if self.mot_de_passe != self.mot_de_passe_confirmation:
            raise UserError(
                _(
                    "Les deux mots de passe entrés ne correspondent pas. "
                    "Veuillez les saisir de nouveau."
                )
            )
        if self.mot_de_passe == MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER:
            raise UserError(
                _(
                    "Le mot de passe par défaut n'a pas encore été personnalisé : "
                    "« %(valeur)s » n'est qu'un marqueur livré avec le module. Un "
                    "administrateur doit le remplacer : %(emplacement)s. Ou saisissez "
                    "ici votre propre mot de passe dans les deux champs."
                ) % {
                    "valeur": MOT_DE_PASSE_PAR_DEFAUT_A_CHANGER,
                    "emplacement": EMPLACEMENT_MOT_DE_PASSE_DEFAUT,
                }
            )
        manquants = self._criteres_manquants_mot_de_passe()
        if manquants:
            raise UserError(
                _(
                    "Le mot de passe ne respecte pas les critères minimaux (niveau "
                    "PCI DSS) : il manque %(criteres)s."
                ) % {"criteres": ", ".join(manquants)}
            )
        return None

    def action_download_html(self):
        """Télécharge le rapport sous forme de fichier .html autonome. Si
        « Protéger le fichier par un mot de passe » est coché, le contenu
        est chiffré (AES-GCM, clé dérivée du mot de passe via PBKDF2) et le
        fichier livré contient à la place une page d'invite qui déchiffre
        le contenu dans le navigateur au moment de l'ouverture, via
        l'API Web Crypto native (aucune bibliothèque JavaScript externe)."""
        self.ensure_one()
        if not self.report_html:
            raise UserError(_("Générez d'abord le rapport à l'écran."))
        document = (
            "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>"
            f"<title>Rapport de sondage</title></head><body>{self.report_html}</body></html>"
        )
        resultat = self._verifier_mot_de_passe_ou_demander("action_download_html")
        if resultat:
            return resultat
        mdp_html = self._mot_de_passe_effectif("html")
        if mdp_html:
            document = self._html_protege_par_mot_de_passe(document, mdp_html)
        plage_dates = self._suffixe_plage_dates_nom_fichier()
        horodatage_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        nom_fichier = (
            f"RapportSondage-{self._prefixe_nom_fichier()}"
            f"{plage_dates + '-' if plage_dates else ''}"
            f"{horodatage_local.strftime('%Y%m%d.%H%M%S')}.html"
        )
        attachment = self.env["ir.attachment"].create({
            "name": nom_fichier,
            "type": "binary",
            "datas": base64.b64encode(document.encode("utf-8")),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "text/html",
        })
        self._envoyer_notification(
            _("Fichier prêt"),
            _(
                "Le fichier HTML a été généré et son téléchargement est en cours. "
                "Note : cette fenêtre ne se ferme pas automatiquement (limite connue "
                "d'Odoo pour un téléchargement protégé) - vous pouvez la fermer "
                "avec le bouton Annuler."
            ),
            "success",
            sticky=True,
        )
        self._journaliser_acces("html", nom_fichier, attachment)
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true&filename={nom_fichier}",
            "target": "self",
        }

    def _html_protege_par_mot_de_passe(self, document, mot_de_passe):
        """Chiffre `document` (AES-256-GCM, clé dérivée du mot de passe via
        PBKDF2-SHA256, 210 000 itérations - recommandation OWASP actuelle)
        et retourne une page HTML autonome contenant : le contenu chiffré
        (en base64), le sel et le vecteur d'initialisation nécessaires à la
        dérivation/déchiffrement, et un script qui effectue ce
        déchiffrement dans le navigateur via l'API Web Crypto native (
        aucune bibliothèque tierce, aucune donnée envoyée à un serveur -
        tout se passe localement une fois le fichier téléchargé).

        AVERTISSEMENT : ce mécanisme n'a pas pu être testé en conditions
        réelles (aucun navigateur disponible pour valider le
        déchiffrement). Le chiffrement lui-même utilise des primitives
        standards et éprouvées (bibliothèque `cryptography`, API Web
        Crypto), mais TESTEZ personnellement qu'un fichier généré s'ouvre
        et se déchiffre correctement avec le bon mot de passe (et échoue
        proprement avec un mauvais) avant de vous y fier pour une
        obligation légale de protection des renseignements personnels."""
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as exc:
            raise UserError(
                _(
                    "La protection par mot de passe du HTML nécessite la bibliothèque "
                    "Python 'cryptography', introuvable sur cette instance. "
                    "Installez-la (pip install cryptography) ou décochez l'option de "
                    "protection - ou choisissez le format PDF, dont la protection par "
                    "mot de passe utilise une bibliothèque différente (pypdf)."
                )
            ) from exc

        iterations = 210_000
        sel = secrets.token_bytes(16)
        cle = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, iterations, dklen=32)
        nonce = secrets.token_bytes(12)
        contenu_chiffre = AESGCM(cle).encrypt(nonce, document.encode("utf-8"), None)

        sel_b64 = base64.b64encode(sel).decode("ascii")
        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        chiffre_b64 = base64.b64encode(contenu_chiffre).decode("ascii")

        return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Rapport de sondage (protégé)</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 420px; margin: 15vh auto; text-align: center; }}
  input {{ font-size: 1rem; padding: .5rem; width: 100%; box-sizing: border-box; margin: .5rem 0; }}
  button {{ font-size: 1rem; padding: .5rem 1.5rem; cursor: pointer; }}
  #erreur {{ color: #b3261e; min-height: 1.2em; }}
</style></head>
<body>
<h2>Rapport de sondage</h2>
<p>Ce fichier est protégé par un mot de passe.</p>
<input type="password" id="mdp" placeholder="Mot de passe" autofocus>
<button type="button" onclick="dechiffrer()">Ouvrir</button>
<p id="erreur"></p>
<script>
const SEL = "{sel_b64}";
const NONCE = "{nonce_b64}";
const CHIFFRE = "{chiffre_b64}";
const ITERATIONS = {iterations};

function b64ToBytes(b64) {{
  return Uint8Array.from(atob(b64), c => c.charCodeAt(0));
}}

async function derivateKey(motDePasse) {{
  const enc = new TextEncoder();
  const materiel = await crypto.subtle.importKey(
    "raw", enc.encode(motDePasse), {{name: "PBKDF2"}}, false, ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {{name: "PBKDF2", salt: b64ToBytes(SEL), iterations: ITERATIONS, hash: "SHA-256"}},
    materiel,
    {{name: "AES-GCM", length: 256}},
    false,
    ["decrypt"]
  );
}}

async function dechiffrer() {{
  const mdp = document.getElementById("mdp").value;
  const erreur = document.getElementById("erreur");
  erreur.textContent = "";
  try {{
    const cle = await derivateKey(mdp);
    const clair = await crypto.subtle.decrypt(
      {{name: "AES-GCM", iv: b64ToBytes(NONCE)}}, cle, b64ToBytes(CHIFFRE)
    );
    const html = new TextDecoder().decode(clair);
    document.open();
    document.write(html);
    document.close();
  }} catch (e) {{
    erreur.textContent = "Mot de passe incorrect.";
  }}
}}

document.getElementById("mdp").addEventListener("keydown", function(e) {{
  if (e.key === "Enter") {{ dechiffrer(); }}
}});
</script>
</body></html>"""

    _MOTIF_DETAIL_NOTES_PDF = re.compile(
        r"<details class='detail-oui'><summary>Détail des notes</summary>.*?</details>", re.DOTALL
    )
    _MOTIF_DETAILS_PDF = re.compile(r"<details class='detail-oui'><summary>(.*?)</summary>", re.DOTALL)
    _MOTIF_SELECTEUR_THEME_PDF = re.compile(r"<div class='selecteur-theme'>.*?</div>", re.DOTALL)
    _MOTIF_TABLEAU_PERSONNE_PDF = re.compile(
        r"<div class='tableau-scroll'><table class='tableau tableau-personne'>.*?</table></div>", re.DOTALL
    )
    _MOTIF_SECTION_RENCONTRE_OUVRANTE = re.compile(r"<section class='rencontre' id='[^']*'>")
    _MOTIF_SECTION_PERSONNE_OUVRANTE = re.compile(r"<section class='personne' id='[^']*'>")
    _MOTIF_BARRE_PDF = re.compile(
        r'<div class="barre-cadre[^"]*"[^>]*><div class="barre-remplie" style="width:(\d+)%"></div></div>'
    )

    @classmethod
    def _remplacer_barres_par_tableaux_pdf(cls, html):
        """Remplace la structure des histogrammes (deux <div> imbriqués avec
        flex/largeur en pourcentage - voir barre() dans report_builder.py)
        par un <table> à deux cellules pour le PDF : la largeur d'une
        cellule de tableau, en pourcentage, est prise en charge de façon
        fiable par pratiquement n'importe quel moteur de rendu HTML depuis
        les tout débuts du web, contrairement à flexbox (déjà source de
        bogues connus avec wkhtmltopdf - voir plus haut) et, semble-t-il,
        même aux largeurs figées en CSS sur des <div> imbriqués (tentées
        sans succès confirmé en v1.29.0)."""
        def _remplacement(match):
            pourcentage = max(0, min(100, int(match.group(1))))
            reste = 100 - pourcentage
            return (
                '<table style="width:140px;height:1rem;border-collapse:collapse;" '
                'cellspacing="0" cellpadding="0"><tr>'
                f'<td style="background:#bfe2ec;width:{pourcentage}%;"></td>'
                f'<td style="background:#e6ecef;width:{reste}%;"></td>'
                "</tr></table>"
            )
        return cls._MOTIF_BARRE_PDF.sub(_remplacement, html)

    @staticmethod
    def _inserer_sauts_de_page_sauf_premier(motif, html):
        """Applique `motif` sur `html`, ajoutant un style de saut de page en
        ligne sur chaque occurrence SAUF LA PREMIÈRE (évite une page blanche
        en tête de document). Le compteur est une variable locale capturée
        par la fermeture `_inserer` - PAS un attribut d'instance
        (self._quelque_chose = ...) : une tentative en ce sens a provoqué un
        plantage confirmé en production (AttributeError), les enregistrements
        Odoo n'acceptant pas l'affectation d'attributs arbitraires en dehors
        de leurs champs déclarés."""
        compteur = [0]

        def _inserer(match):
            compteur[0] += 1
            if compteur[0] == 1:
                return match.group(0)
            return match.group(0)[:-1] + " style=\"page-break-before:always;page-break-inside:avoid;\">"

        return motif.sub(_inserer, html)

    def _html_pour_pdf(self):
        """Variante du rapport pour l'impression PDF :
        1) le sélecteur de thème (boutons JavaScript, sans effet sur un PDF
           statique) est retiré ;
        2) les listes « Détail des notes » (ventilation des notes
           individuelles par question matricielle) sont retirées
           entièrement - trop nombreuses et trop denses pour être
           pertinentes à l'impression, sur demande explicite ;
        3) si « Tableaux de réponses par participant dans le PDF » est
           décoché, le tableau détaillé de chaque participant est retiré
           (ses coordonnées restent) - option de secours pour les très gros
           rapports (ex. la Journée Portes Ouvertes, ~190 participants) dont
           la génération PDF s'arrêtait prématurément (observé : tronqué à
           86 pages), wkhtmltopdf semblant atteindre une limite de temps ou
           de mémoire sur un document de cette taille ;
        4) les sauts de page forcés par rencontre et/ou par participant sont
           ajoutés selon les deux options correspondantes du wizard (CSS
           généré dynamiquement ici, plutôt que fixé dans le gabarit QWeb,
           puisqu'il dépend de ces choix) ;
        5) le résultat est enveloppé dans Markup() : le gabarit QWeb utilise
           `t-out` (t-raw est déprécié) qui échappe le HTML par défaut sauf
           si la valeur est explicitement marquée comme sûre - ce contenu
           l'est bel et bien, puisqu'il provient de self.report_html,
           lui-même déjà construit avec échappement ciblé des données
           utilisateur (voir report_builder.py)."""
        self.ensure_one()
        html = self.report_html or ""
        html = self._MOTIF_SELECTEUR_THEME_PDF.sub("", html)
        # Les graphiques d'évolution/tendance utilisent une mise en page
        # flex, déjà source de bogues connus avec wkhtmltopdf pour les
        # histogrammes (corrigé en les remplaçant par des tableaux) et
        # vraisemblablement responsable de pages presque vides observées
        # dans un PDF généré - retirés du PDF plutôt que reconstruits en
        # tableaux (moins prioritaire visuellement qu'un histogramme de
        # note), le rapport à l'écran/HTML restant de toute façon complet.
        html = rb.retirer_divs_par_prefixe_classe(html, "evo-section")
        html = rb.retirer_divs_par_prefixe_classe(html, "evo-serie")
        html = self._remplacer_barres_par_tableaux_pdf(html)
        html = self._MOTIF_DETAIL_NOTES_PDF.sub("", html)
        if not self.pdf_tableaux_participants:
            html = self._MOTIF_TABLEAU_PERSONNE_PDF.sub(
                "<p class='vide'>(tableau de réponses omis du PDF)</p>", html
            )
        html = self._MOTIF_DETAILS_PDF.sub(r"<div class='detail-oui-pdf'><div class='detail-oui-pdf-titre'>\1</div>", html)
        html = html.replace("</details>", "</div>")

        regles_saut_page = []
        if self.pdf_saut_page_rencontre:
            regles_saut_page.append(
                ".rlq-rapport section.rencontre { page-break-inside: avoid; page-break-before: always; }"
                ".rlq-rapport section.rencontre:first-of-type { page-break-before: avoid; }"
            )
            # Renfort en style En ligne : certains moteurs PDF (wkhtmltopdf,
            # notamment d'anciennes versions) appliquent moins fiablement les
            # sauts de page définis par sélecteur de classe dans un <style>
            # que par un attribut style="" directement sur la balise - une
            # ceinture-et-bretelles peu coûteuse. Le tout premier "rencontre"
            # (la Synthèse ou la première rencontre) est sauté pour éviter
            # une page blanche en tête de document.
            html = self._inserer_sauts_de_page_sauf_premier(self._MOTIF_SECTION_RENCONTRE_OUVRANTE, html)
        if self.pdf_saut_page_participant:
            regles_saut_page.append(
                ".rlq-rapport section.personne { page-break-inside: avoid; page-break-before: always; }"
                ".rlq-rapport section.personne:first-of-type { page-break-before: avoid; }"
            )
            html = self._inserer_sauts_de_page_sauf_premier(self._MOTIF_SECTION_PERSONNE_OUVRANTE, html)
        if regles_saut_page:
            supplement = "".join(regles_saut_page)
            if "</style>" in html:
                html = html.replace("</style>", supplement + "</style>", 1)
            else:
                html = f"<style>{supplement}</style>" + html

        return Markup(html)

    def action_download_pdf(self):
        """Télécharge le rapport en PDF (via le moteur QWeb/wkhtmltopdf
        d'Odoo), toujours protégé par mot de passe : le PDF est généré
        nous-mêmes en octets bruts (plutôt que de laisser Odoo le servir
        directement) pour pouvoir le chiffrer via pypdf avant de le
        proposer au téléchargement - un chiffrement standard, identique à
        celui de n'importe quel PDF protégé par mot de passe dans un
        lecteur usuel. Le format HTML/PDF contenant des renseignements
        personnels, cette protection n'est plus optionnelle (Loi 25,
        RGPD) - seul l'affichage à l'écran, déjà protégé par les droits
        d'accès Odoo, ne l'exige pas."""
        self.ensure_one()
        if not self.report_html:
            raise UserError(_("Générez d'abord le rapport à l'écran."))

        resultat = self._verifier_mot_de_passe_ou_demander("action_download_pdf")
        if resultat:
            return resultat
        mdp_pdf = self._mot_de_passe_effectif("pdf")
        if mdp_pdf and PdfWriter is None:
            raise UserError(
                _(
                    "La protection par mot de passe du PDF nécessite la bibliothèque "
                    "Python 'pypdf' (ou 'PyPDF2'), introuvable sur cette instance. "
                    "Installez-la (pip install pypdf)."
                )
            )

        rapport = self.env.ref("rlq_survey_report.action_report_rlq_survey")
        pdf_content, _content_type = self.env["ir.actions.report"]._render_qweb_pdf(rapport, self.ids)

        if mdp_pdf:
            lecteur = PdfReader(io.BytesIO(pdf_content))
            redacteur = PdfWriter()
            for page in lecteur.pages:
                redacteur.add_page(page)
            try:
                # algorithm="AES-256" est OBLIGATOIRE ici : sans ce paramètre
                # explicite, pypdf chiffre par défaut avec RC4, un algorithme non
                # sécurisé (cassable en quelques secondes avec les outils
                # actuels) conservé seulement pour la compatibilité avec de très
                # vieux lecteurs PDF. Le chiffrement AES de pypdf nécessite lui-
                # même une dépendance supplémentaire (`cryptography` ou
                # `pycryptodome`), déjà requise par ailleurs pour la protection
                # du HTML - message d'erreur clair si elle manquait malgré tout.
                redacteur.encrypt(mdp_pdf, algorithm="AES-256")
            except ImportError as exc:
                raise UserError(
                    _(
                        "Le chiffrement AES du PDF nécessite la bibliothèque Python "
                        "'cryptography' (ou 'pycryptodome'), introuvable sur cette "
                        "instance. Installez-la (pip install cryptography) ou décochez "
                        "l'option de protection."
                    )
                ) from exc
            tampon = io.BytesIO()
            redacteur.write(tampon)
            pdf_chiffre = tampon.getvalue()
        else:
            # Rapport anonymisé : PDF livré tel quel, sans chiffrement.
            pdf_chiffre = pdf_content

        plage_dates = self._suffixe_plage_dates_nom_fichier()
        horodatage_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        nom_fichier = (
            f"RapportSondage-{self._prefixe_nom_fichier('pdf')}"
            f"{plage_dates + '-' if plage_dates else ''}"
            f"{horodatage_local.strftime('%Y%m%d.%H%M%S')}.pdf"
        )
        attachment = self.env["ir.attachment"].create({
            "name": nom_fichier,
            "type": "binary",
            "datas": base64.b64encode(pdf_chiffre),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/pdf",
        })
        self._envoyer_notification(
            _("Fichier prêt"),
            _(
                "Le fichier PDF a été généré et son téléchargement est en cours. "
                "Note : cette fenêtre ne se ferme pas automatiquement (limite connue "
                "d'Odoo pour un téléchargement protégé) - vous pouvez la fermer "
                "avec le bouton Annuler."
            ),
            "success",
            sticky=True,
        )
        self._journaliser_acces("pdf", nom_fichier, attachment)
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true&filename={nom_fichier}",
            "target": "self",
        }

    def _zipper_avec_mot_de_passe(self, nom_fichier_interne, contenu_bytes):
        """Compresse `contenu_bytes` dans une archive ZIP protégée par
        `self.mot_de_passe`, chiffrée en AES (via pyzipper - le module
        `zipfile` standard de Python ne sait pas ÉCRIRE d'archive chiffrée,
        seulement en lire). Lève une UserError claire si pyzipper n'est
        pas installé, plutôt qu'une exception brute."""
        if pyzipper is None:
            raise UserError(
                _(
                    "L'export protégé par mot de passe nécessite la bibliothèque Python "
                    "'pyzipper', introuvable sur cette instance. Installez-la "
                    "(pip install pyzipper) ou décochez l'option de protection."
                )
            )
        tampon = io.BytesIO()
        with pyzipper.AESZipFile(
            tampon, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as archive:
            archive.setpassword(self.mot_de_passe.encode("utf-8"))
            archive.writestr(nom_fichier_interne, contenu_bytes)
        return tampon.getvalue()

    def _creer_attachment_zip(self, nom_fichier_zip, contenu_zip):
        """Crée la pièce jointe et retourne (attachment, action_telechargement)
        - le tuple, plutôt qu'un seul de ces deux éléments, permet à
        l'appelant de journaliser l'accès (_journaliser_acces) AVEC la
        pièce jointe déjà créée, sans avoir à la re-rechercher."""
        attachment = self.env["ir.attachment"].create({
            "name": nom_fichier_zip,
            "type": "binary",
            "datas": base64.b64encode(contenu_zip),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/zip",
        })
        action_telechargement = {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true&filename={nom_fichier_zip}",
            "target": "self",
        }
        return attachment, action_telechargement

    def _commentaire_libre_pour(self, user_input):
        """Cherche une réponse texte libre (TYPES_TEXTE_LIBRE) parmi les
        lignes de CE user_input précis - utilisé pour relier une note
        basse à un commentaire explicatif possible de la MÊME personne,
        dans le MÊME sondage (voir section "À surveiller" - accélère le
        passage du symptôme, la note, à la cause, le commentaire, sans
        chercher manuellement). Retourne la PREMIÈRE réponse libre non
        vide trouvée (une personne laisse rarement plus d'un commentaire
        libre par sondage), ou None si aucune - ne lève jamais d'erreur,
        un commentaire manquant ne doit jamais faire échouer le rapport."""
        try:
            champ_lignes = self._lines_field_name()
            lignes = user_input[champ_lignes].filtered(
                lambda ligne_: ligne_.question_id.question_type in TYPES_TEXTE_LIBRE
            )
            for ligne in lignes:
                valeur = self._valeur_ligne_texte(ligne)
                if valeur:
                    return valeur
        except Exception:  # noqa: BLE001
            _logger.warning(
                "Impossible de chercher un commentaire libre pour user_input %s",
                user_input.id, exc_info=True,
            )
        return None

    def _valeur_ligne_texte(self, ligne):
        """Convertit une ligne de réponse (survey.user_input.line) en texte
        lisible, peu importe son type de question - vérifie chaque champ
        de valeur possible dans l'ordre, retourne le premier renseigné.
        Pour une question matricielle, préfixe avec le nom de la ligne
        (matrix_row_id). Champs vérifiés avec getattr(..., None) : une
        instance sans tel ou tel type de question (donc sans le champ
        correspondant) ne doit jamais faire échouer l'export."""
        prefixe = f"{ligne.matrix_row_id.value} : " if getattr(ligne, "matrix_row_id", None) else ""
        if getattr(ligne, "suggested_answer_id", None):
            return prefixe + (ligne.suggested_answer_id.value or "")
        if getattr(ligne, "value_text_box", None):
            return prefixe + ligne.value_text_box
        if getattr(ligne, "value_char_box", None):
            return prefixe + ligne.value_char_box
        if getattr(ligne, "value_numerical_box", None) is not None and ligne.value_numerical_box:
            return prefixe + str(ligne.value_numerical_box)
        if getattr(ligne, "value_date", None):
            return prefixe + str(ligne.value_date)
        if getattr(ligne, "value_datetime", None):
            return prefixe + str(ligne.value_datetime)
        return ""

    def action_export_excel(self):
        """Exporte un classeur Excel (.xlsx) à plusieurs feuilles - un
        format unique plutôt que plusieurs fichiers CSV séparés, pour
        permettre de construire des tableaux croisés dynamiques
        directement dans Excel à partir de la feuille "Réponses" (une
        ligne par réponse individuelle, structure plate adaptée à un
        tableau croisé) :
        - "Participations" : une ligne par personne par sondage, avec
          ses renseignements de base et son statut ;
        - "Réponses" : le détail de CHAQUE réponse individuelle, toutes
          questions confondues (texte, choix, numérique, matricielle...) ;
        - "Réponses libres" : uniquement les questions à texte libre, pour
          une lecture rapide sans le reste ;
        - "Note globale" : la moyenne composite (Organisation et
          logistique/Satisfaction globale/présentations, voir
          MOTS_CLES_NOTE_GLOBALE) par rencontre - LA métrique de suivi
          proposée pour l'amélioration continue, absente jusqu'ici de
          l'export Excel (déjà présente dans le rapport HTML/PDF).
        Protégé par le même mot de passe que le HTML/PDF (Loi 25, RGPD),
        dans une archive ZIP chiffrée."""
        self.ensure_one()
        resultat = self._verifier_mot_de_passe_ou_demander("action_export_excel")
        if resultat:
            return resultat
        if openpyxl is None:
            raise UserError(
                _(
                    "L'export Excel nécessite la bibliothèque Python 'openpyxl', "
                    "introuvable sur cette instance. Installez-la "
                    "(pip install openpyxl)."
                )
            )

        classeur = openpyxl.Workbook()
        feuille_participations = classeur.active
        feuille_participations.title = "Participations"
        feuille_participations.append([
            "Date", "Sondage", "Participant", "Courriel", "Statut",
            "Date de début", "Date de fin",
        ])
        feuille_reponses = classeur.create_sheet("Réponses")
        feuille_reponses.append(["Date", "Sondage", "Participant", "Question", "Type", "Réponse"])
        feuille_libres = classeur.create_sheet("Réponses libres")
        feuille_libres.append(["Date", "Sondage", "Question", "Participant", "Réponse"])

        champ_lignes = self._lines_field_name()
        # Valeurs de la "Note globale" (moyenne composite de Organisation et
        # logistique/Satisfaction globale/présentations, voir
        # MOTS_CLES_NOTE_GLOBALE) accumulées PAR SONDAGE pendant la même
        # boucle que "Réponses" ci-dessous, pour une feuille dédiée -
        # réutilise convertir_numerique() (déjà utilisé pour le rapport
        # HTML/PDF) plutôt que dupliquer toute la logique d'extraction des
        # questions matricielles.
        valeurs_note_globale_par_survey = defaultdict(list)
        dates_par_survey = {}
        for survey in self.survey_ids.sorted(lambda s: s.id):
            user_inputs = self._user_inputs(survey)
            if not user_inputs:
                continue
            date_rencontre = self._rencontre_date(survey, user_inputs)
            dates_par_survey[survey.id] = date_rencontre

            for ui in user_inputs:
                feuille_participations.append([
                    date_rencontre or "",
                    survey.title or "",
                    self._respondent_nom(ui),
                    self._respondent_email(ui) or "",
                    ui.state or "",
                    str(ui.start_datetime) if ui.start_datetime else "",
                    str(ui.end_datetime) if ui.end_datetime else "",
                ])

            toutes_lignes = user_inputs.mapped(champ_lignes)
            for question in survey.question_and_page_ids.filtered(lambda q: q.question_type):
                lignes_question = toutes_lignes.filtered(lambda ligne_: ligne_.question_id == question)  # noqa: B023 - exécutée immédiatement par filtered(), dans la même itération
                est_note_globale = any(
                    mot in (question.title or "").lower() for mot in MOTS_CLES_NOTE_GLOBALE
                )
                for ligne in lignes_question:
                    valeur = self._valeur_ligne_texte(ligne)
                    if not valeur:
                        continue
                    if est_note_globale:
                        num = rb.convertir_numerique(valeur)
                        if num is not None:
                            valeurs_note_globale_par_survey[survey.id].append(num)
                    feuille_reponses.append([
                        date_rencontre or "",
                        survey.title or "",
                        self._respondent_nom(ligne.user_input_id),
                        question.title or "",
                        question.question_type or "",
                        valeur,
                    ])
                    if question.question_type in TYPES_TEXTE_LIBRE:
                        feuille_libres.append([
                            date_rencontre or "",
                            survey.title or "",
                            question.title or "",
                            self._respondent_nom(ligne.user_input_id),
                            valeur,
                        ])

        feuille_note_globale = classeur.create_sheet("Note globale")
        feuille_note_globale.append(["Date", "Sondage", "Moyenne", "Min", "Max", "Écart-type", "Nb réponses"])
        for survey_id, valeurs in valeurs_note_globale_par_survey.items():
            if not valeurs:
                continue
            stats = rb.stats_description(valeurs)
            survey = self.env["survey.survey"].browse(survey_id)
            feuille_note_globale.append([
                dates_par_survey.get(survey_id) or "",
                survey.title or "",
                round(stats["moy"], 2),
                stats["min"],
                stats["max"],
                round(stats["ecart_type"], 2),
                len(valeurs),
            ])

        tampon = io.BytesIO()
        classeur.save(tampon)
        contenu_xlsx = tampon.getvalue()

        plage_dates = self._suffixe_plage_dates_nom_fichier()
        horodatage_local = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        nom_xlsx = (
            f"RapportSondage-Export-{self._prefixe_nom_fichier('excel')}"
            f"{plage_dates + '-' if plage_dates else ''}"
            f"{horodatage_local.strftime('%Y%m%d.%H%M%S')}.xlsx"
        )
        contenu_zip = self._zipper_avec_mot_de_passe(nom_xlsx, contenu_xlsx)
        nom_zip = nom_xlsx.replace(".xlsx", ".zip")
        attachment, action_telechargement = self._creer_attachment_zip(nom_zip, contenu_zip)
        self._journaliser_acces("excel", nom_zip, attachment)
        return action_telechargement

    # ------------------------------------------------------------------
    # Classement automatique des sondages, pour les sous-menus de sélection
    # rapide. Les critères ci-dessous sont des hypothèses raisonnables, à
    # ajuster si le classement obtenu ne correspond pas à vos attentes -
    # voir NOTES_VALIDATION.md.
    # ------------------------------------------------------------------

    @api.model
    def _survey_ids_premier_mardi(self):
        """Le titre du sondage ne contient pas les mots « premier mardi » :
        on se base plutôt sur la date qu'il contient (ex. « 4 août 2026 »)
        et on retient les sondages tombant un mardi, dans les 7 premiers
        jours du mois (donc nécessairement le premier mardi de ce mois).
        Uniquement la date du TITRE - pas de repli sur la date de
        soumission des réponses (contrairement à _date_survey()), pour
        éviter qu'un sondage sans date de titre reconnaissable ne soit
        classé à tort d'après une date de soumission sans rapport (ex. un
        sondage mentionnant « 31 juillet » sans année, dont les réponses
        soumises coïncideraient par hasard avec un mardi)."""
        resultat = self.env["survey.survey"]
        for survey in self.env["survey.survey"].search([]):
            d = self._extraire_date_titre(survey.title, annee_repli=self._annee_repli_titre(survey))
            if d and d.weekday() == 1 and d.day <= 7:  # 1 = mardi
                resultat |= survey
        return resultat

    @api.model
    def _survey_ids_pause_cafe(self):
        """Recherche « pause café » ou « pause-café » dans le titre (accents
        et casse ignorés par ILIKE)."""
        return self.env["survey.survey"].search([
            "|", "|", "|",
            ("title", "ilike", "pause café"),
            ("title", "ilike", "pause-café"),
            ("title", "ilike", "pause cafe"),
            ("title", "ilike", "pause-cafe"),
        ])

    @api.model
    def _survey_ids_annuel(self, seuil=100):
        """Tout sondage ayant reçu plus de `seuil` réponses au total, sans
        égard au mois. Une contrainte "doit tomber en septembre" avait été
        ajoutée tôt dans la conception de ce module, sur une hypothèse
        d'alors qui s'est avérée être la cause du problème : le sondage
        annuel visé (190 inscriptions) restait introuvable via ce critère,
        vraisemblablement parce que l'événement n'a pas lieu en septembre.
        Retirée : il ne reste que le seuil de réponses, plus simple et plus
        robuste. Le sous-menu « Portes ouvertes » (recherche par mot-clé du
        titre) reste de toute façon la méthode la plus fiable pour ce
        sondage précis, indépendamment de ce critère."""
        resultat = self.env["survey.survey"]
        for survey in self.env["survey.survey"].search([]):
            nb_reponses = self.env["survey.user_input"].search_count([("survey_id", "=", survey.id)])
            if nb_reponses > seuil:
                resultat |= survey
        return resultat

    @api.model
    def _survey_ids_portes_ouvertes(self):
        """Recherche « portes ouvertes » dans le titre (insensible à la
        casse) - alternative fiable au critère par date pour un sondage
        comme la Journée Portes Ouvertes Linux, dont le titre ne contient
        souvent qu'une année sans jour ni mois exploitable."""
        return self.env["survey.survey"].search([("title", "ilike", "portes ouvertes")])

    @api.model
    def _survey_ids_autres(self):
        """Tout sondage ne correspondant à aucune des catégories
        précédentes."""
        deja_classes = (
            self._survey_ids_premier_mardi()
            | self._survey_ids_pause_cafe()
            | self._survey_ids_annuel()
            | self._survey_ids_portes_ouvertes()
        )
        return self.env["survey.survey"].search([("id", "not in", deja_classes.ids)])

    @api.model
    def _survey_ids_tous(self):
        """Tous les sondages ayant reçu au moins une réponse (terminée ou en
        cours) - pour le raccourci « Tous les sondages (terminé et
        commencé) ». Un sondage sans aucune des deux (ex. jamais envoyé, ou
        seulement des invitations jamais ouvertes) n'a pas sa place dans une
        sélection par défaut destinée à produire un rapport."""
        tous = self.env["survey.survey"].search([])
        return tous.filtered(lambda s: s.rlq_answer_done_count > 0 or s.rlq_answer_in_progress_count > 0)

    def _action_ouvrir_wizard_pour(self, surveys, nom_menu=None, contexte_extra=None):
        contexte = {"default_survey_ids": [(6, 0, surveys.ids)], "dialog_size": "extra-large"}
        if nom_menu:
            contexte["default_menu_origine"] = nom_menu
        if contexte_extra:
            contexte.update(contexte_extra)
        return {
            "type": "ir.actions.act_window",
            "res_model": "rlq.survey.report.wizard",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": contexte,
        }

    @api.model
    def action_menu_premier_mardi(self):
        return self._action_ouvrir_wizard_pour(self._survey_ids_premier_mardi(), "Premier mardi du mois")

    @api.model
    def action_menu_pause_cafe(self):
        return self._action_ouvrir_wizard_pour(self._survey_ids_pause_cafe(), "Pause café")

    @api.model
    def action_menu_annuel(self):
        return self._action_ouvrir_wizard_pour(self._survey_ids_annuel(), "Sondage annuel (>100 inscriptions)")

    @api.model
    def action_menu_portes_ouvertes(self):
        return self._action_ouvrir_wizard_pour(self._survey_ids_portes_ouvertes(), "Portes ouvertes")

    @api.model
    def action_menu_autres(self):
        return self._action_ouvrir_wizard_pour(self._survey_ids_autres(), "Tous les autres sondages")
