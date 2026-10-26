# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
event_inscriptions_alerte.py
=============================

Avertissement par courriel quand un événement atteint N inscriptions (v1.95.0).
Activable événement par événement.

Sur le formulaire de l'événement (bloc « Avertissement par courriel ») :
  - `rlq_alerte_active` : la case qui active la fonction pour CET événement ;
  - `rlq_alerte_seuil`  : N, le nombre d'inscriptions à atteindre ;
  - `rlq_alerte_courriel` : adresse(s) à avertir pour cet événement (facultatif).

Destinataire, par ordre de priorité (report_builder.destinataire_alerte_inscriptions) :
  1. le courriel propre à l'événement ;
  2. le paramètre système `rlq_survey_report.courriel_inscriptions` (Réglages > Technique >
     Paramètres système ; créé vide à l'installation ; plusieurs adresses permises,
     séparées par des virgules) ;
  3. le courriel par défaut d'Odoo : celui de la société de l'événement.

Sondage complété (v1.96.0) : la case `rlq_alerte_sondage` envoie en plus un courriel chaque fois qu'une
personne termine un sondage associé à l'événement (sondage d'un type de billet, ou sondage de
l'événement) : nom de la personne, billet, nombre de sondages complétés. Jamais ses réponses ni son
courriel. Même destinataire ; un seul courriel par participation (`rlq_alerte_evenement_envoyee`).

Répétition (v1.105.0) : la case `rlq_alerte_repeter` (« Répéter tous les N inscriptions ») envoie un courriel à
chaque multiple de N atteint (N, 2N, 3N…) au lieu d'un seul ; `rlq_alerte_palier` garde le dernier multiple
avisé (une annulation puis une nouvelle inscription ne renvoie rien tant que le multiple suivant n'est pas atteint).
Modifier N, cocher ou décocher la case, ou réactiver l'avertissement remet le compteur à zéro.

Une « inscription » = une inscription confirmée (état `open`) ou présente (`done`) ; les
brouillons et les annulations ne comptent pas. L'avertissement est vérifié à chaque création
d'inscription et à chaque changement d'état, et envoyé UNE seule fois
(`rlq_alerte_envoyee`) ; modifier le seuil ou réactiver la case le réarme.

Garde-fous : jamais d'erreur remontée à la personne qui s'inscrit (échec journalisé,
l'inscription n'est JAMAIS bloquée) ; verrou de ligne (`FOR UPDATE`) pour que deux inscriptions
simultanées n'envoient pas deux courriels ; le courriel ne contient AUCUNE donnée personnelle
(ni nom ni courriel des inscrits : Loi 25) et est supprimé des courriels sortants après envoi.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from . import report_builder as rb

_logger = logging.getLogger(__name__)

CLE_PARAMETRE_COURRIEL_INSCRIPTIONS = "rlq_survey_report.courriel_inscriptions"
ETATS_COMPTES = ("open", "done")


class EventEventAlerte(models.Model):
    _inherit = "event.event"

    rlq_alerte_active = fields.Boolean(
        string="Avertir par courriel après N inscriptions", default=False, copy=False,
        help="Si cochée, un courriel est envoyé une seule fois quand le nombre d'inscriptions "
             "confirmées atteint le seuil ci-dessous.",
    )
    rlq_alerte_seuil = fields.Integer(
        string="Nombre d'inscriptions (N)", default=50, copy=False,
        help="Le courriel part quand l'événement atteint (ou dépasse) ce nombre d'inscriptions "
             "confirmées. Modifier ce nombre réarme l'avertissement.",
    )
    rlq_alerte_repeter = fields.Boolean(
        string="Répéter tous les N inscriptions", default=False, copy=False,
        help="Si cochée, un courriel est envoyé à CHAQUE multiple du nombre ci-dessus (N, 2N, 3N…) "
             "au lieu d'un seul. Modifier N ou cette case remet le compteur à zéro.",
    )
    rlq_alerte_palier = fields.Integer(
        string="Dernier palier avisé", readonly=True, copy=False,
        help="Dernier multiple de N pour lequel un courriel est parti (répétition seulement).",
    )
    rlq_alerte_sondage = fields.Boolean(
        string="Avertir aussi à chaque sondage complété", default=False, copy=False,
        help="Si cochée, un courriel est envoyé chaque fois qu'une personne termine un sondage associé à "
             "cet événement (le sondage propre à un type de billet, ou le sondage de l'événement). Le courriel "
             "donne le nom de la personne, son billet et le nombre de sondages complétés ; jamais ses réponses ni son courriel. "
             "Même destinataire que l'avertissement d'inscriptions.",
    )
    rlq_alerte_courriel = fields.Char(
        string="Courriel à avertir", copy=False,
        help="Adresse(s) de courriel à avertir pour CET événement (séparées par des virgules). "
             "Vide : le paramètre système « rlq_survey_report.courriel_inscriptions », puis, "
             "à défaut, le courriel de la société (courriel par défaut d'Odoo).",
    )
    rlq_alerte_envoyee = fields.Datetime(
        string="Avertissement envoyé le", readonly=True, copy=False,
        help="Date d'envoi de l'avertissement. Vide : pas encore envoyé.",
    )
    rlq_inscriptions_comptees = fields.Integer(
        string="Inscriptions confirmées", compute="_compute_rlq_inscriptions_comptees",
        help="Inscriptions confirmées ou présentes (les brouillons et annulations ne comptent pas).",
    )

    @api.constrains("rlq_alerte_active", "rlq_alerte_seuil")
    def _check_rlq_alerte_seuil(self):
        for evenement in self:
            if evenement.rlq_alerte_active and evenement.rlq_alerte_seuil < 1:
                raise ValidationError(_("Le nombre d'inscriptions de l'avertissement doit être d'au moins 1."))

    def _compute_rlq_inscriptions_comptees(self):
        for evenement in self:
            evenement.rlq_inscriptions_comptees = evenement._rlq_compter_inscriptions()

    def _rlq_compter_inscriptions(self):
        self.ensure_one()
        return self.env["event.registration"].sudo().search_count([
            ("event_id", "=", self.id), ("state", "in", list(ETATS_COMPTES)),
        ])

    def write(self, vals):
        rearmer = any(c in vals for c in ("rlq_alerte_seuil", "rlq_alerte_active", "rlq_alerte_repeter"))
        if rearmer:
            vals = dict(vals)
            vals.setdefault("rlq_alerte_envoyee", False)       # nouveau seuil, case recochée ou répétition changée : réarmé
            vals.setdefault("rlq_alerte_palier", 0)
        res = super().write(vals)
        if rearmer:
            self._rlq_verifier_alerte()                       # seuil déjà atteint : avertir tout de suite
        return res

    def _rlq_verifier_alerte(self):
        """Envoie l'avertissement pour chaque événement qui a atteint son seuil. Ne lève jamais
        d'exception : l'inscription ou l'enregistrement en cours ne doit pas être bloqué."""
        for evenement in self.sudo().filtered("rlq_alerte_active"):
            try:
                with self.env.cr.savepoint():
                    evenement._rlq_envoyer_alerte_si_atteint()
            except Exception:  # noqa: BLE001 - jamais bloquer une inscription
                _logger.warning("avertissement d'inscriptions non envoyé (événement %s)", evenement.id, exc_info=True)

    def _rlq_envoyer_alerte_si_atteint(self):
        self.ensure_one()
        if self.rlq_alerte_seuil < 1 or (self.rlq_alerte_envoyee and not self.rlq_alerte_repeter):
            return False
        nombre = self._rlq_compter_inscriptions()
        if rb.palier_alerte(nombre, self.rlq_alerte_seuil, self.rlq_alerte_repeter, self.rlq_alerte_palier) is None:
            return False
        # Verrou : deux inscriptions simultanées n'envoient pas deux courriels.
        self.env.cr.execute("SELECT id FROM event_event WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(["rlq_alerte_envoyee", "rlq_alerte_palier"])
        palier = rb.palier_alerte(nombre, self.rlq_alerte_seuil, self.rlq_alerte_repeter, self.rlq_alerte_palier)
        if palier is None or (self.rlq_alerte_envoyee and not self.rlq_alerte_repeter):
            return False
        destinataire, source = self._rlq_destinataire_alerte()
        if not destinataire:
            _logger.warning(
                "événement %s : %d inscriptions atteintes mais aucune adresse valide à avertir "
                "(courriel de l'événement, paramètre %s, courriel de la société)",
                self.id, nombre, CLE_PARAMETRE_COURRIEL_INSCRIPTIONS,
            )
            return False
        debut = self._rlq_debut_texte()
        self._rlq_envoyer_courriel(
            destinataire, rb.sujet_alerte_inscriptions(self.name, nombre),
            rb.html_alerte_inscriptions(self.name, debut, nombre, self.rlq_alerte_seuil, self._rlq_url(), self.rlq_alerte_repeter),
        )
        self.write({"rlq_alerte_envoyee": fields.Datetime.now(), "rlq_alerte_palier": palier})
        try:
            self.message_post(
                body=_("Avertissement envoyé à %(dest)s : %(n)d inscriptions (seuil %(seuil)d).",
                       dest=destinataire, n=nombre, seuil=self.rlq_alerte_seuil),
                subtype_xmlid="mail.mt_note",
            )
        except Exception:  # noqa: BLE001 - la trace dans le fil n'est qu'un confort
            _logger.info("note d'avertissement non ajoutée à l'événement %s", self.id, exc_info=True)
        _logger.info("événement %s : avertissement de %d inscriptions envoyé (source du destinataire : %s)",
                     self.id, nombre, source)
        return True

    def _rlq_destinataire_alerte(self):
        """(adresses, source) : courriel de l'événement, puis paramètre système, puis courriel de la société."""
        self.ensure_one()
        parametres = self.env["ir.config_parameter"].sudo()
        return rb.destinataire_alerte_inscriptions(
            self.rlq_alerte_courriel,
            parametres.get_param(CLE_PARAMETRE_COURRIEL_INSCRIPTIONS, ""),
            (self.company_id or self.env.company).email,
        )

    def _rlq_debut_texte(self):
        self.ensure_one()
        return fields.Datetime.to_string(self.date_begin)[:10] if self.date_begin else None

    def _rlq_url(self):
        """Lien vers l'événement dans Odoo (Odoo 18 : /odoo/<modèle>/<id>) ; None sans web.base.url."""
        self.ensure_one()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
        return "%s/odoo/event.event/%d" % (base.rstrip("/"), self.id) if base else None

    def _rlq_envoyer_courriel(self, destinataire, sujet, corps_html):
        """Met le courriel en file (supprimé après envoi : rien n'est conservé dans les courriels sortants)."""
        self.ensure_one()
        societe = self.company_id or self.env.company
        valeurs = {
            "subject": sujet, "body_html": corps_html, "email_to": destinataire, "auto_delete": True,
            "model": "event.event", "res_id": self.id,
        }
        if societe.email:
            valeurs["email_from"] = societe.email_formatted or societe.email
        self.env["mail.mail"].sudo().create(valeurs).send()

    def _rlq_surveys_associes(self):
        """Sondages associés à CET événement : celui de chaque type de billet, et le sondage de l'événement s'il existe."""
        self.ensure_one()
        sondages = self.env["event.event.ticket"].sudo().search([("event_id", "=", self.id)]).mapped("rlq_survey_id")
        if "survey_id" in self._fields and self.survey_id:
            sondages |= self.survey_id
        return sondages

    def _rlq_dernieres_inscriptions(self, limite=10):
        """Les `limite` dernières inscriptions (30 jours) de l'événement avec leur sondage de confirmation :
        même contenu que la touche « I » de app-log-live.py. Heures dans le fuseau de l'événement."""
        self.ensure_one()
        contexte = self.with_context(tz=self.date_tz or "America/Toronto")

        def local(date):
            return fields.Datetime.context_timestamp(contexte, date).strftime("%Y-%m-%d %H:%M") if date else ""
        depuis = fields.Datetime.now() - timedelta(days=30)
        inscriptions = self.env["event.registration"].sudo().search([
            ("event_id", "=", self.id), ("state", "in", list(ETATS_COMPTES)), ("create_date", ">=", depuis),
        ], order="create_date desc, id desc", limit=limite)
        participations = self.env["survey.user_input"].sudo()
        resultat = []
        for ins in inscriptions:
            ticket = ins.event_ticket_id if "event_ticket_id" in ins._fields else False
            attendu = (ticket.rlq_survey_id if ticket and "rlq_survey_id" in ticket._fields else False) or (
                self.survey_id if "survey_id" in self._fields else False)
            sondage = None
            if attendu:
                domaine = [("survey_id", "=", attendu.id), ("test_entry", "=", False)]
                trouve = participations.browse()
                if ins.partner_id:
                    trouve = participations.search(domaine + [("partner_id", "=", ins.partner_id.id)], order="state desc, create_date desc", limit=1)
                if not trouve and ins.email:
                    trouve = participations.search(domaine + [("email", "=ilike", ins.email)], order="state desc, create_date desc", limit=1)
                if trouve:
                    sondage = {"quand": local(trouve.end_datetime if trouve.state == "done" and "end_datetime" in trouve._fields and trouve.end_datetime else trouve.create_date),
                               "nom": trouve.partner_id.name or ins.name or "", "titre": attendu.title, "etat": trouve.state}
            resultat.append({"quand": local(ins.create_date), "nom": ins.name or "", "billet": ticket.name if ticket else "",
                             "etat": ins.state, "attendu": bool(attendu), "sondage": sondage})
        return resultat

    def _rlq_alerte_sondage_complete(self, participation):
        """Courriel « sondage complété » (case rlq_alerte_sondage) pour une participation terminée. Retourne True si envoyé."""
        self.ensure_one()
        sondages = self._rlq_surveys_associes()
        if not self.rlq_alerte_sondage or participation.survey_id not in sondages:
            return False
        destinataire, _source = self._rlq_destinataire_alerte()
        if not destinataire:
            _logger.warning("événement %s : sondage complété mais aucune adresse valide à avertir", self.id)
            return False
        inscription = self.env["event.registration"].sudo().browse()
        domaine = [("event_id", "=", self.id), ("state", "in", list(ETATS_COMPTES))]
        if participation.partner_id:
            inscription = inscription.search(domaine + [("partner_id", "=", participation.partner_id.id)], limit=1, order="id desc")
        if not inscription and participation.email:
            inscription = inscription.search(domaine + [("email", "=ilike", participation.email)], limit=1, order="id desc")
        billet = inscription.event_ticket_id.name if inscription and "event_ticket_id" in inscription._fields and inscription.event_ticket_id else ""
        personne = (inscription.name if inscription else "") or participation.partner_id.name or ""
        complets = self.env["survey.user_input"].sudo().search_count([
            ("survey_id", "in", sondages.ids), ("state", "=", "done"), ("test_entry", "=", False),
        ])
        self._rlq_envoyer_courriel(
            destinataire, rb.sujet_alerte_sondage(self.name, personne),
            rb.html_alerte_sondage(self.name, self._rlq_debut_texte(), personne, billet, participation.survey_id.title,
                                   complets, self._rlq_compter_inscriptions(), self._rlq_url(), self._rlq_dernieres_inscriptions()),
        )
        return True

    @api.model
    def _creer_parametre_courriel_inscriptions_si_absent(self):
        """Crée le paramètre système (vide) SEULEMENT s'il n'existe pas : une valeur existante
        n'est jamais remplacée (même raison que pour le mot de passe par défaut : un <record> XML
        serait rechargé en mode « init »). Ne doit jamais empêcher le chargement du module."""
        try:
            with self.env.cr.savepoint():
                parametres = self.env["ir.config_parameter"].sudo()
                if not parametres.search([("key", "=", CLE_PARAMETRE_COURRIEL_INSCRIPTIONS)], limit=1):
                    parametres.create({"key": CLE_PARAMETRE_COURRIEL_INSCRIPTIONS, "value": ""})
        except Exception:  # noqa: BLE001
            _logger.warning("paramètre %s non créé", CLE_PARAMETRE_COURRIEL_INSCRIPTIONS, exc_info=True)


class SurveyUserInputAlerte(models.Model):
    _inherit = "survey.user_input"

    rlq_alerte_evenement_envoyee = fields.Datetime(
        string="Avertissement de l'événement envoyé le", readonly=True, copy=False,
        help="Date d'envoi du courriel « sondage complété » à l'organisateur de l'événement (jamais deux fois).",
    )

    def _mark_done(self):
        res = super()._mark_done()
        self._rlq_alerte_sondage_evenement()
        return res

    def _rlq_alerte_sondage_evenement(self):
        """Pour chaque participation terminée (hors essai) d'un sondage associé à un événement dont la case
        « Avertir aussi à chaque sondage complété » est cochée : courriel à l'organisateur. Ne lève jamais
        d'exception : la soumission du sondage n'est JAMAIS bloquée."""
        for participation in self.sudo().filtered(lambda p: p.state == "done" and not p.test_entry and not p.rlq_alerte_evenement_envoyee):
            try:
                with self.env.cr.savepoint():
                    billets = self.env["event.event.ticket"].sudo().search([("rlq_survey_id", "=", participation.survey_id.id)])
                    evenements = billets.mapped("event_id")
                    if "survey_id" in self.env["event.event"]._fields:
                        evenements |= self.env["event.event"].sudo().search([("survey_id", "=", participation.survey_id.id)])
                    envoye = False
                    for evenement in evenements.filtered("rlq_alerte_sondage"):
                        envoye = evenement._rlq_alerte_sondage_complete(participation) or envoye
                    if envoye:
                        participation.rlq_alerte_evenement_envoyee = fields.Datetime.now()
            except Exception:  # noqa: BLE001 - jamais bloquer la soumission d'un sondage
                _logger.warning("avertissement « sondage complété » non envoyé (participation %s)", participation.id, exc_info=True)


class EventRegistrationAlerte(models.Model):
    _inherit = "event.registration"

    @api.model_create_multi
    def create(self, vals_list):
        inscriptions = super().create(vals_list)
        inscriptions._rlq_alerte_inscriptions()
        return inscriptions

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals or "event_id" in vals:
            self._rlq_alerte_inscriptions()
        return res

    def _rlq_alerte_inscriptions(self):
        evenements = self.sudo().event_id.filtered("rlq_alerte_active")
        if evenements:
            evenements._rlq_verifier_alerte()
