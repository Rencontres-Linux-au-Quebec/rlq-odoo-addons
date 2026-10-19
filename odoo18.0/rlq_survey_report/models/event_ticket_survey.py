# -*- coding: utf-8 -*-
"""
event_ticket_survey.py
=======================

Permet d'associer un sondage DIFFÉRENT à chaque type de billet d'un même
événement (ex. bénévoles, visiteurs, commanditaires) - le module Événements
d'Odoo n'expose nativement qu'un seul sondage par ÉVÉNEMENT
(event.event.survey_id), partagé par tous les billets, ce qui ne permettait
pas cette distinction.

Ajoute :
  - `rlq_survey_id` sur event.event.ticket : le sondage propre à CE type de
    billet.
  - `rlq_lien_sondage_billet` sur event.registration : lien calculé vers ce
    sondage, à insérer dans un modèle de courriel (ex. le courriel de
    confirmation d'inscription, onglet "Communication" de l'événement) via
    l'outil "Placeholder dynamique" (tapez "/" dans le corps du courriel,
    cherchez "Lien du sondage") - PAS la syntaxe ${...} (Jinja), retirée des
    gabarits de courriel depuis Odoo 15 ; le corps utilise maintenant QWeb
    (ex. <t t-out="object.rlq_lien_sondage_billet"/>), inséré automatiquement
    par cet outil plutôt que tapé à la main.

`store=True` (v1.81.0, CORRECTIF) : ce champ était calculé à la volée
(non stocké) - signalé comme invisible dans la liste de recherche de
l'outil "Placeholder dynamique" du corps du courriel, contrairement à
`rlq_survey_id` (une vraie colonne). Rendu stocké pour que ce champ se
comporte comme n'importe quel autre champ normal du modèle - recalculé
automatiquement (`@api.depends`) si le billet change ou si le sondage
assigné à ce billet change.

`get_start_url()` plutôt que `/survey/start/{survey.id}` (v1.82.0,
CORRECTIF) : signalé en conditions réelles - le lien généré s'affichait
bien dans le courriel, mais ne menait à aucun sondage. `survey.id` (la
clé interne en base) n'est pas ce qu'attend la route publique
`/survey/start/...` - `get_start_url()`, la méthode NATIVE d'Odoo,
construit la bonne URL en interne (vraisemblablement basée sur
`access_token`, pas `id`). La MÊME erreur (URL de sondage construite à
la main plutôt qu'avec les méthodes natives d'Odoo) avait déjà été
rencontrée et corrigée ailleurs dans ce module (voir
`_lien_test_sondage()` dans rlq_survey_report_wizard.py, après
plusieurs tentatives) - ce fichier-ci avait été écrit sans reprendre
cette leçon déjà apprise.

ATTENTION - NON VÉRIFIABLE SANS ACCÈS À UNE INSTANCE (voir NOTES_VALIDATION.md) :
  - Ce fichier suppose que event.registration porte bien un champ
    `event_ticket_id` (Many2one vers event.event.ticket) - nom standard
    depuis plusieurs versions d'Odoo, mais non vérifié sur cette instance
    précise (ERPLibre).
  - Le lien pointe maintenant vers ce que `get_start_url()` retourne (avec
    repli sur `/survey/start/{access_token}` si cette méthode échoue ou
    n'existe pas) - PAS vers un lien à jeton de réponse personnalisé
    (`answer_token` sur un `survey.user_input` déjà créé), qui exigerait de
    créer cet enregistrement à l'avance plutôt qu'au moment où la personne
    clique. Un lien par jeton de réponse individuel reste possible en
    évolution future si vous voulez suivre qui a répondu précisément via
    ce canal.
  - Le passage à `store=True` (v1.81.0) et la correction de l'URL
    (v1.82.0) n'ont pas pu être testés sur une instance réelle - à
    confirmer que le lien reçu dans un vrai courriel de confirmation mène
    bel et bien au bon sondage après la mise à jour du module.

Ce module devient dépendant du module "event" à partir de cette version
(ajouté à `depends` dans __manifest__.py) - auparavant, `event` n'était
qu'une dépendance OPTIONNELLE, détectée au moment de générer le rapport
(voir `event_dispo` dans rlq_survey_report_wizard.py, qui reste utile pour
le rapport lui-même : le module continue de fonctionner même sur une
instance qui n'aurait pas d'inscriptions à des événements). Cette
extension-ci, elle, cible directement le modèle event.event.ticket : elle
exige donc que le module Événements soit installé.

© Services-Linux Conseils Inc — contact@exemple.org, contact@exemple.org
Licence : AGPL-3
"""

from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class EventEventTicket(models.Model):
    _inherit = "event.event.ticket"

    rlq_survey_id = fields.Many2one(
        "survey.survey", string="Sondage pour ce type de billet",
        help="Sondage à proposer aux personnes inscrites avec CE type de billet "
             "précisément (ex. un sondage « Bénévoles » distinct de celui des "
             "visiteurs ou des commanditaires). Laissez vide pour ne pas offrir "
             "de sondage spécifique à ce billet - le sondage général de "
             "l'événement (event.event, champ « Sondage à soumettre » natif "
             "d'Odoo, s'il existe), lui, n'est pas modifié par ce champ et "
             "continue de s'appliquer normalement à tous les billets qui n'ont "
             "pas leur propre sondage ici.\n\n"
             "Pour l'envoyer automatiquement : dans Événements > votre "
             "événement > onglet Communication, ajoutez (ou modifiez) un "
             "modèle de courriel de confirmation d'inscription et insérez-y, "
             "via l'outil Placeholder dynamique (tapez « / » dans le corps), "
             "le champ « Lien du sondage (type de billet) » - ce lien "
             "pointera alors vers LE sondage propre au billet réellement "
             "choisi par chaque personne inscrite.",
    )


class EventRegistration(models.Model):
    _inherit = "event.registration"

    rlq_lien_sondage_billet = fields.Char(
        string="Lien du sondage (type de billet)",
        compute="_compute_rlq_lien_sondage_billet", store=True,
        help="Lien public vers le sondage associé au type de billet choisi par "
             "cette inscription (event_ticket_id.rlq_survey_id) - vide si ce "
             "type de billet n'a pas de sondage spécifique. Construit avec la "
             "méthode native survey.get_start_url() (pas l'identifiant interne "
             "du sondage, qui ne mène nulle part sur la route publique). À "
             "insérer dans un modèle de courriel via l'outil Placeholder "
             "dynamique (tapez « / » dans le corps du courriel, puis cherchez "
             "ce champ par son nom affiché ci-dessus).",
    )

    @api.depends("event_ticket_id", "event_ticket_id.rlq_survey_id")
    def _compute_rlq_lien_sondage_billet(self):
        for registration in self:
            ticket = registration.event_ticket_id if "event_ticket_id" in registration._fields else False
            survey = ticket.rlq_survey_id if ticket else False
            if not survey:
                registration.rlq_lien_sondage_billet = False
                continue
            # CORRECTIF (v1.82.0) : `survey.id` (l'identifiant interne en
            # base) n'est PAS ce qu'attend la route publique
            # /survey/start/<...> - signalé en conditions réelles (lien
            # généré mais qui ne menait à aucun sondage). `get_start_url()`
            # est la méthode NATIVE d'Odoo pour obtenir l'URL publique
            # correcte d'un sondage (construite en interne à partir du bon
            # identifiant, probablement access_token plutôt que id) - déjà
            # utilisée ailleurs dans ce module (voir _lien_test_sondage())
            # après plusieurs tentatives ratées avec une URL construite à
            # la main, exactement la même erreur que celle-ci. Repli sur
            # `access_token` si `get_start_url()` échoue ou n'existe pas,
            # jamais sur `id`.
            try:
                registration.rlq_lien_sondage_billet = survey.get_start_url()
            except Exception:  # noqa: BLE001 - ne doit jamais faire échouer le calcul du champ
                _logger.warning(
                    "get_start_url() a échoué pour le sondage %s - repli sur access_token",
                    survey.id, exc_info=True,
                )
                base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "") or ""
                registration.rlq_lien_sondage_billet = (
                    f"{base_url}/survey/start/{survey.access_token}" if survey.access_token else False
                )
