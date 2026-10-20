# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
synchro_sommaire.py
===================

Sommaire « Synchronisation : sommaire » (v1.108.0), menu Sondages > Rapports détaillés.

Répond à la question « est-ce que la synchronisation automatique est active, et pour quoi ? » sans fouiller les sondages et les événements un par un :
  - état de la tâche planifiée (active ou non, fréquence, dernier et prochain passage) ;
  - les synchronisations IMMÉDIATES (toujours actives : inscription créée ou modifiée, sondage terminé, création d'un compte) ;
  - l'intervalle proposé par défaut (paramètre système `rlq_survey_report.synchro_minutes_defaut`, 15 minutes s'il est absent) ;
  - la liste des sondages et des événements dont la case « Synchronisation périodique » est cochée (intervalle, dernier passage, résultat).
Lecture seule : rien n'est modifié.
"""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from .event_groupes_inscrits import RLQ_PARAM_SYNCHRO_MINUTES, _synchro_minutes_defaut


class RlqSynchroSommaire(models.TransientModel):
    _name = "rlq.synchro.sommaire"
    _description = "Sommaire de la synchronisation des groupes et étiquettes"

    resume = fields.Html(string="Sommaire", readonly=True, sanitize=False)

    @api.model
    def _heure_locale(self, valeur):
        """Date et heure d'un champ Datetime dans le fuseau de l'utilisateur, « jamais » si vide."""
        if not valeur:
            return _("jamais")
        return fields.Datetime.context_timestamp(self, valeur).strftime("%Y-%m-%d %H:%M")

    @api.model
    def _lignes(self):
        """Liste de (titre, [lignes]) du sommaire ; ne modifie rien."""
        env = self.env
        cron = env.ref("rlq_survey_report.ir_cron_synchro_sondages", raise_if_not_found=False)
        sondages = env["survey.survey"].sudo().search([("rlq_synchro_active", "=", True)])
        evenements = env["event.event"].sudo().search([("rlq_synchro_active", "=", True)])
        maintenant = fields.Datetime.now()
        blocs = []

        etat = []
        if not cron:
            etat.append(_("Tâche planifiée introuvable : mettez le module à jour."))
        elif cron.sudo().active:
            etat.append(_("ACTIVE, toutes les %(n)s %(t)s.", n=cron.interval_number, t=cron.interval_type))
            etat.append(_("Dernier passage : %(d)s ; prochain passage : %(p)s.", d=self._heure_locale(cron.lastcall), p=self._heure_locale(cron.nextcall)))
        else:
            etat.append(_("DÉSACTIVÉE : aucun sondage ni événement n'a la case « Synchronisation périodique » cochée. Elle ne s'exécute pas "
                          "et n'écrit rien dans le journal. Elle se réactive seule dès qu'une case est cochée."))
        blocs.append((_("Tâche planifiée « synchronisation périodique »"), etat))

        blocs.append((_("Synchronisations immédiates (toujours actives)"), [
            _("Une inscription est créée ou modifiée (état, billet, personne, refus) : le groupe de son billet est mis à jour tout de suite."),
            _("Un sondage est terminé : les groupes liés à ses réponses sont appliqués tout de suite."),
            _("Un compte portail est créé : les groupes de ses inscriptions et de ses réponses sont appliqués tout de suite."),
            _("La synchronisation périodique ne sert donc qu'à rattraper un changement fait hors de ces cas (groupe renommé, membre retiré à la main, étiquette modifiée)."),
        ]))

        blocs.append((_("Intervalle par défaut"), [
            _("%(n)s minute(s) pour un nouveau sondage ou événement (minimum 5). Pour le changer : Paramètres > Technique > Paramètres système, clé « %(k)s ».",
              n=_synchro_minutes_defaut(env), k=RLQ_PARAM_SYNCHRO_MINUTES)]))

        lignes = [_("« %(t)s » : toutes les %(n)s minute(s) ; dernier passage : %(d)s ; %(r)s", t=s.title, n=s.rlq_synchro_minutes,
                    d=self._heure_locale(s.rlq_synchro_derniere), r=s.rlq_synchro_resultat or "-") for s in sondages]
        blocs.append((_("Sondages avec synchronisation périodique (%s)", len(sondages)), lignes or [_("Aucun.")]))

        lignes = []
        for e in evenements:
            termine = bool(e.date_end and e.date_end + timedelta(days=1) < maintenant)
            lignes.append(_("« %(t)s » : toutes les %(n)s minute(s) ; dernier passage : %(d)s ; %(r)s%(f)s", t=e.name, n=e.rlq_synchro_minutes,
                            d=self._heure_locale(e.rlq_synchro_derniere), r=e.rlq_synchro_resultat or "-",
                            f=_(" ; événement terminé depuis plus d'un jour : ignoré (décochez la case)") if termine else ""))
        blocs.append((_("Événements avec synchronisation périodique (%s)", len(evenements)), lignes or [_("Aucun.")]))
        return blocs

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        morceaux = [Markup("<h4>%s</h4><ul>%s</ul>") % (escape(titre), Markup("").join(Markup("<li>%s</li>") % escape(ligne) for ligne in lignes))
                    for titre, lignes in self._lignes()]
        res.setdefault("resume", Markup("").join(morceaux))
        return res
