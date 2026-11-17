# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
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

Liens (v1.128.0) : au bas des réponses, « Modifier mes réponses » et « Je ne peux plus venir » (controllers/reponses.py),
chacun seulement s'il s'applique (sondage encore ouvert ; inscription ni annulée, ni présente, événement pas terminé).

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
        # v1.127.0 : les questions « échelle » (scale) étaient omises du courriel de réponses.
        if getattr(ligne, "answer_type", None) == "scale":
            return prefixe + str(getattr(ligne, "value_scale", "") or 0)
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

    @api.depends("user_input_line_ids", "survey_id", "email", "partner_id")
    def _compute_rlq_reponses_html(self):
        for participation in self:
            resume = participation._rlq_resume_inscription_html()
            reponses = rb.html_reponses_courriel(participation._rlq_blocs_reponses())
            participation.rlq_reponses_html = resume + reponses + participation._rlq_liens_html()

    # ------------------------------------------------------------ liens « Modifier mes réponses » / « Je ne peux plus venir »

    def _rlq_peut_modifier(self):
        """La personne peut-elle rouvrir ses réponses ? Sondage actif, pas une certification ni une session en direct, pas
        d'échéance dépassée, pas une entrée de test, participation déjà soumise (v1.128.0)."""
        self.ensure_one()
        sondage = self.survey_id
        if self.test_entry or self.state != "done" or not self.access_token or not sondage.active:
            return False
        if getattr(sondage, "certification", False) or getattr(self, "is_session_answer", False):
            return False
        echeance = getattr(self, "deadline", False)
        return not (echeance and echeance < fields.Datetime.now())

    def _rlq_inscription_annulable(self):
        """L'inscription que la personne peut annuler elle-même : celle de cette participation, ni annulée, ni déjà
        marquée présente, et l'événement pas encore terminé ; sinon None (v1.128.0)."""
        self.ensure_one()
        if self.test_entry or not self.access_token:
            return None
        inscription = self._rlq_inscription_associee()
        if not inscription or inscription.state in ("cancel", "done"):
            return None
        fin = getattr(inscription.event_id, "date_end", False)
        if fin and fin < fields.Datetime.now():
            return None
        return inscription

    def _rlq_liens_html(self):
        """Liens du bas du courriel de réponses ; chaîne vide si aucun ne s'applique ou en cas d'erreur (le courriel ne doit
        jamais en dépendre)."""
        self.ensure_one()
        try:
            base = self.survey_id.get_base_url().rstrip("/")
            racine = "%s/rlq_survey_report/reponses/%s" % (base, self.access_token)
            return rb.html_liens_courriel(
                racine + "/modifier" if self._rlq_peut_modifier() else None,
                racine + "/annuler" if self._rlq_inscription_annulable() else None,
            )
        except Exception:  # noqa: BLE001
            _logger.info("rlq_survey_report : liens du courriel non calculés pour la participation %s", self.id, exc_info=True)
            return ""

    def _rlq_inscription_associee(self):
        """Inscription à l'événement correspondant à cette participation (même courriel,
        et sondage du billet ou de l'événement), la plus récente, ou un recordset vide.
        Ne lève jamais d'erreur : le courriel de réponses ne doit pas en dépendre."""
        self.ensure_one()
        inscriptions = self.env["event.registration"]
        adresse = self._rlq_destinataire()
        if not adresse or not self.survey_id:
            return inscriptions
        # v1.128.0 : event.event.survey_id n'existe que si un module l'ajoute (absent sur l'instance de production :
        # « ValueError: Invalid field event.event.survey_id » à chaque fin de sondage, et le résumé de l'inscription
        # manquait dans le courriel). Le critère n'est ajouté que si le champ existe.
        critere_sondage = [("event_ticket_id.rlq_survey_id", "=", self.survey_id.id)]
        if "survey_id" in self.env["event.event"]._fields:
            critere_sondage = ["|"] + critere_sondage + [("event_id.survey_id", "=", self.survey_id.id)]
        try:
            return inscriptions.sudo().search([
                ("email", "=ilike", adresse),
                ("state", "!=", "cancel"),
            ] + critere_sondage, order="id desc", limit=1)
        except Exception:  # noqa: BLE001 - pas de résumé plutôt qu'une erreur
            _logger.info("rlq_survey_report : inscription non trouvée pour la participation %s", self.id, exc_info=True)
            return inscriptions

    def _rlq_resume_inscription_html(self):
        """HTML « Résumé de votre inscription » (nom, événement, date, lieu, billet, questions
        d'inscription), en tête du courriel de réponses. Chaîne vide si aucune inscription
        ne correspond. Tout est échappé ; chaque champ est lu avec getattr."""
        self.ensure_one()
        inscription = self._rlq_inscription_associee()
        if not inscription:
            return ""
        evenement = inscription.event_id
        lignes = [
            ("Nom", inscription.name),
            ("Courriel", inscription.email),
            ("Événement", getattr(evenement, "name", "")),
        ]
        debut = getattr(evenement, "date_begin", None)
        if debut:
            locale = fields.Datetime.context_timestamp(inscription, debut)
            lignes.append(("Date", locale.strftime("%Y-%m-%d %H:%M")))
        lieu = getattr(evenement, "address_id", None)
        if lieu:
            lignes.append(("Lieu", lieu.display_name))
        billet = getattr(inscription, "event_ticket_id", None)
        if billet:
            lignes.append(("Billet", billet.name))
        for reponse in getattr(inscription, "registration_answer_ids", self.env["event.registration"]):
            question = getattr(reponse, "question_id", None)
            valeur = getattr(reponse, "value_answer_id", None)
            texte = getattr(valeur, "name", False) or getattr(reponse, "value_text_box", False)
            if question and texte:
                lignes.append((question.title, texte))
        return rb.html_resume_inscription(lignes)

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
