# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
survey_reponses_courriel.py
============================

Envoi au PARTICIPANT, par courriel, d'une copie de ses propres réponses dès qu'il
termine un sondage (v1.94.0). Activable sondage par sondage.

Fonctionnement :
  - `survey.survey.rlq_envoyer_reponses` (case à cocher, décochée par défaut) active
    la fonction pour CE sondage ; `rlq_modele_courriel_reponses` permet de choisir un
    autre modèle de courriel (par défaut : « Vos réponses au sondage », fourni par
    data/mail_template_reponses.xml, modifiable dans Réglages > Technique > Modèles
    de courriel).
  - `survey.user_input._mark_done()` (appelé par Odoo quand le participant soumet la
    dernière page) est étendu : après le traitement natif, si le sondage a la case
    cochée, le courriel est mis en file d'envoi.
  - `rlq_reponses_html` (calculé, non stocké) est le corps « questions et réponses »
    que le modèle insère avec <t t-out="object.rlq_reponses_html"/>.

Garde-fous : jamais d'erreur remontée au participant (échec journalisé, la soumission
du sondage n'est JAMAIS bloquée) ; jamais pour une entrée de test ; jamais deux fois
pour la même réponse ; rien si aucune adresse de courriel n'est connue (sondage
anonyme ou participant sans courriel) ; le courriel en file est supprimé après envoi
(auto_delete) pour ne pas conserver les réponses dans les courriels sortants (Loi 25).
"""
import logging

from odoo import api, fields, models

from . import report_builder as rb

_logger = logging.getLogger(__name__)


class SurveySurveyReponses(models.Model):
    _inherit = "survey.survey"

    rlq_envoyer_reponses = fields.Boolean(
        string="Envoyer ses réponses au participant",
        default=False,
        help="Si cochée, le participant reçoit par courriel une copie de ses réponses "
             "dès qu'il termine le sondage (seulement s'il a un courriel connu : "
             "invitation par courriel, utilisateur connecté, ou question de courriel).",
    )
    rlq_modele_courriel_reponses = fields.Many2one(
        "mail.template",
        string="Modèle du courriel de réponses",
        domain="[('model', '=', 'survey.user_input')]",
        help="Modèle de courriel utilisé. Vide : le modèle « Vos réponses au sondage » fourni "
             "par ce module.",
    )


class SurveyUserInputReponses(models.Model):
    _inherit = "survey.user_input"

    rlq_courriel_reponses_envoye = fields.Datetime(
        string="Courriel de réponses envoyé le", copy=False, readonly=True,
        help="Date de mise en file du courriel qui rappelle ses réponses au participant "
             "(vide : jamais envoyé).",
    )
    rlq_reponses_html = fields.Html(
        string="Réponses (courriel)", compute="_compute_rlq_reponses_html", sanitize=False,
        help="Questions et réponses de cette participation, en HTML - insérées dans le "
             "courriel envoyé au participant.",
    )

    @staticmethod
    def _rlq_texte_ligne(ligne):
        """Texte d'une ligne de réponse, selon son type (champs vérifiés avec getattr)."""
        prefixe = ""
        rang = getattr(ligne, "matrix_row_id", None)
        if rang:
            prefixe = f"{rang.value} : "
        choix = getattr(ligne, "suggested_answer_id", None)
        if choix:
            return prefixe + (choix.value or "")
        for champ in ("value_text_box", "value_char_box"):
            valeur = getattr(ligne, champ, None)
            if valeur:
                return prefixe + str(valeur)
        numerique = getattr(ligne, "value_numerical_box", None)
        if numerique or numerique == 0:
            if getattr(ligne, "answer_type", None) == "numerical_box":
                return prefixe + f"{numerique:g}"
        for champ in ("value_date", "value_datetime"):
            valeur = getattr(ligne, champ, None)
            if valeur:
                return prefixe + str(valeur)
        return ""

    def _rlq_blocs_reponses(self):
        """[(titre de la question, [textes])] dans l'ordre du sondage."""
        self.ensure_one()
        blocs = []
        for question in self.survey_id.question_ids:
            if getattr(question, "is_page", False):
                continue
            lignes = self.user_input_line_ids.filtered(
                lambda ligne, q=question: ligne.question_id == q and not getattr(ligne, "skipped", False)
            )
            textes = [t for t in (self._rlq_texte_ligne(ligne) for ligne in lignes) if t]
            if textes:
                blocs.append((question.title, textes))
        return blocs

    @api.depends("user_input_line_ids", "survey_id")
    def _compute_rlq_reponses_html(self):
        for participation in self:
            participation.rlq_reponses_html = rb.html_reponses_courriel(participation._rlq_blocs_reponses())

    def _rlq_destinataire(self):
        """Adresse de courriel du participant, ou chaîne vide."""
        self.ensure_one()
        adresse = (self.email or "").strip()
        if not adresse and self.partner_id:
            adresse = (self.partner_id.email or "").strip()
        return adresse

    def _rlq_modele_reponses(self):
        modele = self.survey_id.rlq_modele_courriel_reponses
        if not modele:
            modele = self.env.ref("rlq_survey_report.mail_template_reponses_participant", raise_if_not_found=False)
        return modele

    def rlq_envoyer_reponses_courriel(self, force=False):
        """Met en file le courriel de réponses. Retourne le nombre de courriels mis en file.
        `force=True` : renvoie même si déjà envoyé (relance manuelle). Ne lève jamais d'erreur."""
        envoyes = 0
        for participation in self:
            try:
                if participation.test_entry or participation.state != "done":
                    continue
                if participation.rlq_courriel_reponses_envoye and not force:
                    continue
                destinataire = participation._rlq_destinataire()
                modele = participation._rlq_modele_reponses()
                if not destinataire or not modele or not participation.rlq_reponses_html:
                    continue
                with self.env.cr.savepoint():
                    modele.sudo().send_mail(
                        participation.id, force_send=False,
                        email_values={"email_to": destinataire, "recipient_ids": [(5,)], "auto_delete": True},
                    )
                    participation.sudo().rlq_courriel_reponses_envoye = fields.Datetime.now()
                envoyes += 1
            except Exception:  # noqa: BLE001 - ne JAMAIS bloquer la soumission du sondage
                _logger.exception(
                    "rlq_survey_report : courriel de réponses non envoyé pour survey.user_input %s", participation.id
                )
        return envoyes

    def _mark_done(self):
        """Après le traitement natif, envoie au participant ses réponses (sondages cochés)."""
        a_terminer = self.filtered(lambda p: p.state != "done")
        resultat = super()._mark_done()
        for participation in a_terminer.filtered(lambda p: p.state == "done" and p.survey_id.rlq_envoyer_reponses):
            participation.rlq_envoyer_reponses_courriel()
        return resultat
