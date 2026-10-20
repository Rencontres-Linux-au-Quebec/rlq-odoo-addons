# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
verification_groupes.py
=======================

Assistant « Vérifier les groupes et étiquettes » (v1.104.0), menu Sondages > Rapports détaillés.

Contrôle d'un coup TOUS les événements, sondages, groupes et étiquettes de contact créés par le module :
  - billets d'événements (avec préfixe de groupes) dont le groupe manque ;
  - groupes sans étiquette, étiquettes dont le nom n'est plus celui du groupe (groupe renommé) ;
  - étiquettes à ajouter ou à retirer sur les contacts des membres des groupes ;
  - sondages dont des réponses sont liées à un groupe : participants dont l'appartenance au groupe ne correspond pas à leur dernière réponse.

Deux temps : l'assistant s'ouvre sur un APERÇU (rien n'est modifié), puis le bouton « Appliquer les changements » (avec une confirmation)
fait les changements. Les mêmes opérations que les boutons existants (« Créer / synchroniser les groupes » d'un événement, « Appliquer les groupes
aux participants » d'un sondage) : idempotent, relançable. L'aperçu des participants est une ESTIMATION (l'inscription liée, le refus et l'annulation
sont tranchés à l'application).

ATTENTION - NON VÉRIFIABLE SANS ACCÈS À UNE INSTANCE (voir NOTES_VALIDATION.md).
"""
import logging

from markupsafe import escape

from odoo import _, api, fields, models

from .event_groupes_inscrits import _champ_groupes_utilisateur
from .groupes_etiquettes import _champ_membres

_logger = logging.getLogger(__name__)


class RlqGroupesVerification(models.TransientModel):
    _name = "rlq.groupes.verification"
    _description = "Vérification des groupes et étiquettes des sondages et événements"

    etat = fields.Selection([("apercu", "Aperçu"), ("fait", "Terminé")], default="apercu", readonly=True)
    nb_changements = fields.Integer(string="Changements à faire", readonly=True)
    resume = fields.Html(string="Résumé", readonly=True, sanitize=False)

    # ---------------------------------------------------------------- analyse (aucune écriture)
    @api.model
    def _analyser(self):
        """Dict de listes de textes (une ligne par constat) ; ne modifie rien."""
        env = self.env
        constats = {"billets": [], "etiquettes": [], "membres": [], "participants": []}
        evenements = env["event.event"].sudo().search([("rlq_groupe_prefixe", "!=", False)])
        for billet in evenements.event_ticket_ids.filtered(lambda b: not b.rlq_group_id):
            constats["billets"].append(_("Événement « %(e)s », billet « %(b)s » : groupe à créer.", e=billet.event_id.name, b=billet.name))
        groupes = (env["event.event.ticket"].sudo().search([("rlq_group_id", "!=", False)]).rlq_group_id
                   | env["survey.question.answer"].sudo().search([("rlq_group_id", "!=", False)]).rlq_group_id
                   | env["res.groups"].sudo().search([("rlq_category_id", "!=", False)]))
        if groupes._rlq_etiquettes_actives():
            champ = _champ_membres(env)
            partenaires = env["res.partner"].sudo().with_context(active_test=False)
            for groupe in groupes:
                if not groupe.rlq_category_id:
                    constats["etiquettes"].append(_("Groupe « %s » : étiquette à créer.", groupe.name))
                    voulus = groupe[champ].partner_id
                    if voulus:
                        constats["membres"].append(_("Groupe « %(g)s » : étiquette à poser sur %(n)s contact(s).", g=groupe.name, n=len(voulus)))
                    continue
                if groupe.rlq_category_id.name != groupe.name:
                    constats["etiquettes"].append(_("Groupe « %(g)s » : étiquette « %(e)s » à renommer.", g=groupe.name, e=groupe.rlq_category_id.name))
                voulus = groupe[champ].partner_id
                porteurs = partenaires.search([("category_id", "=", groupe.rlq_category_id.id)])
                a_ajouter, a_retirer = voulus - porteurs, (porteurs - voulus).filtered("user_ids")
                if a_ajouter or a_retirer:
                    constats["membres"].append(_("Groupe « %(g)s » : étiquette à poser sur %(a)s contact(s), à retirer de %(r)s.",
                                                 g=groupe.name, a=len(a_ajouter), r=len(a_retirer)))
        champ_g = _champ_groupes_utilisateur(env)
        for sondage in self._sondages_avec_groupes():
            manquants = en_trop = 0
            vus = env["res.partner"]
            for participation in env["survey.user_input"].sudo().search([("survey_id", "=", sondage.id), ("state", "=", "done"), ("partner_id", "!=", False)], order="id desc"):
                contact = participation.partner_id
                if contact in vus:
                    continue
                vus |= contact
                utilisateurs = contact.user_ids.filtered("active")
                if not utilisateurs:
                    continue
                toutes, derniere = env["survey.user_input"]._rlq_groupes_reponses(contact, sondage)
                actuels = utilisateurs[0].sudo()[champ_g]
                manquants += 1 if (derniere - actuels) else 0
                en_trop += 1 if ((toutes - derniere) & actuels) else 0
            if manquants or en_trop:
                constats["participants"].append(_("Sondage « %(s)s » : %(m)s participant(s) à ajouter à un groupe, %(t)s à retirer d'un groupe (estimation).",
                                                  s=sondage.title, m=manquants, t=en_trop))
        return constats

    @api.model
    def _sondages_avec_groupes(self):
        return self.env["survey.question.answer"].sudo().search([("rlq_group_id", "!=", False)]).question_id.survey_id

    @api.model
    def _html_constats(self, constats):
        titres = (("billets", _("Groupes de billets manquants")), ("etiquettes", _("Étiquettes de groupes")),
                  ("membres", _("Étiquettes des contacts")), ("participants", _("Participants aux sondages")))
        morceaux = []
        for cle, titre in titres:
            if constats[cle]:
                morceaux.append("<h4>%s (%s)</h4><ul>%s</ul>" % (escape(titre), len(constats[cle]), "".join("<li>%s</li>" % escape(t) for t in constats[cle])))
        return "".join(morceaux) or "<p>%s</p>" % escape(_("Tout est déjà en ordre : aucun changement à faire."))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        constats = self._analyser()
        res.setdefault("nb_changements", sum(len(v) for v in constats.values()))
        res.setdefault("resume", self._html_constats(constats))
        return res

    # ---------------------------------------------------------------- application (après confirmation)
    def action_appliquer(self):
        """Bouton « Appliquer les changements » (confirmation demandée par la vue) : refait les opérations des boutons existants."""
        self.ensure_one()
        env = self.env
        evenements = env["event.event"].sudo().search([("rlq_groupe_prefixe", "!=", False)])
        erreurs = 0
        for evenement in evenements:
            try:
                evenement.action_rlq_synchroniser_groupes()
            except Exception:  # noqa: BLE001 - un événement en erreur n'arrête pas les autres
                erreurs += 1
                _logger.warning("vérification des groupes : événement %s en erreur", evenement.id, exc_info=True)
        for sondage in self._sondages_avec_groupes():
            try:
                sondage.sudo().action_rlq_appliquer_groupes_participants()
            except Exception:  # noqa: BLE001
                erreurs += 1
                _logger.warning("vérification des groupes : sondage %s en erreur", sondage.id, exc_info=True)
        groupes = env["res.groups"].sudo()
        try:
            groupes._cron_rlq_synchroniser_etiquettes()
            groupes.search([("rlq_category_id", "!=", False)])._rlq_renommer_etiquette()
        except Exception:  # noqa: BLE001
            erreurs += 1
            _logger.warning("vérification des groupes : étiquettes en erreur", exc_info=True)
        reste = sum(len(v) for v in self._analyser().values())
        self.write({
            "etat": "fait", "nb_changements": reste,
            "resume": "<p>%s</p>" % escape(_("Terminé : %(n)s constat(s) restant(s) ; %(e)s erreur(s) (voir le journal du serveur).", n=reste, e=erreurs)),
        })
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode": "form", "target": "new"}
