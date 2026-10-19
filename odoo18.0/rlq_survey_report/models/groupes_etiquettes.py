# -*- coding: utf-8 -*-
"""
groupes_etiquettes.py
=====================

Étiquettes de contact (res.partner.category) qui REFLÈTENT les groupes d'inscrits (v1.102.0).

Pourquoi : dans Contacts, on voit et on recherche facilement par ÉTIQUETTE, pas par groupe Odoo. Chaque groupe lié à un billet
(`event.event.ticket.rlq_group_id`) ou à une réponse de sondage (`survey.question.answer.rlq_group_id`) reçoit donc une étiquette de MÊME NOM
(« RLQ-JPOL26-Bénévole »), et les contacts des utilisateurs membres du groupe portent cette étiquette : filtre « Étiquettes » de la liste des
contacts, recherche, regroupement.

Fonctionnement :
  - `res.groups.rlq_group_id` -> `res.groups.rlq_category_id` : l'étiquette du groupe (trouvée par son nom, sinon créée). Seuls les groupes
    liés à un billet ou à une réponse reçoivent une étiquette (jamais les groupes du système : « Utilisateur interne », etc.).
  - Les membres sont resynchronisés à CHAQUE changement : ajout ou retrait d'un utilisateur dans un groupe (formulaire utilisateur, formulaire
    du groupe, ce module), archivage ou réactivation d'un utilisateur, renommage du groupe (l'étiquette est renommée), et chaque jour par une
    tâche planifiée (filet de sécurité : modifications faites hors de l'interface).
  - L'étiquette est GÉRÉE par le groupe : le contact d'un UTILISATEUR qui n'est plus dans le groupe perd l'étiquette. Les contacts sans compte
    utilisateur (inscrits qui n'ont pas encore de compte portail) ne sont jamais touchés : une étiquette posée à la main leur reste.
  - Groupe SUPPRIMÉ (v1.104.0) : son étiquette est supprimée aussi (si aucun autre groupe ne l'utilise), donc retirée de tous les contacts.
    Groupe RENOMMÉ : l'étiquette est renommée (voir `write`).
  - Menu Sondages > Rapports détaillés > « Vérifier les groupes et étiquettes » (assistant `rlq.groupes.verification`) : contrôle tous
    les événements, sondages, groupes et étiquettes, montre ce qui changerait et n'applique RIEN sans confirmation.
  - Paramètre système `rlq_survey_report.etiquettes_groupes` (défaut 1) : 0 = aucune étiquette créée ni synchronisée.
  - Jamais de blocage : toute erreur est journalisée et l'opération d'origine continue.

ATTENTION - NON VÉRIFIABLE SANS ACCÈS À UNE INSTANCE (voir NOTES_VALIDATION.md).

© Services-Linux Conseils Inc — Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com
Licence : AGPL-3
"""
import logging

from odoo import api, fields, models

from .event_groupes_inscrits import _champ_groupes_utilisateur

_logger = logging.getLogger(__name__)

PARAMETRE = "rlq_survey_report.etiquettes_groupes"


def _champ_membres(env):
    """Nom du champ « utilisateurs membres » de res.groups : `user_ids` (Odoo récent) ou `users` (Odoo 18 habituel)."""
    return "user_ids" if "user_ids" in env["res.groups"]._fields else "users"


class ResGroupsEtiquette(models.Model):
    _inherit = "res.groups"

    rlq_category_id = fields.Many2one(
        "res.partner.category", string="Étiquette de contact", copy=False, ondelete="set null",
        help="Étiquette de même nom, posée sur le contact de chaque utilisateur membre du groupe (créée par rlq_survey_report pour les groupes "
             "d'inscrits ; mise à jour à chaque changement du groupe). Gérée automatiquement : ne pas l'ajouter à la main aux utilisateurs.",
    )

    def _rlq_etiquettes_actives(self):
        valeur = (self.env["ir.config_parameter"].sudo().get_param(PARAMETRE, "1") or "1").strip().lower()
        return valeur not in ("0", "false", "non", "no", "off")

    def _rlq_assurer_etiquette(self):
        """Trouve ou crée l'étiquette de chaque groupe (idempotent) puis synchronise ses membres."""
        if not self._rlq_etiquettes_actives():
            return
        categories = self.env["res.partner.category"].sudo()
        for groupe in self.sudo().filtered(lambda g: not g.rlq_category_id and g.name):
            categorie = categories.search([("name", "=", groupe.name)], limit=1) or categories.create({"name": groupe.name})
            groupe.rlq_category_id = categorie
        self._rlq_synchroniser_etiquette()

    def _rlq_synchroniser_etiquette(self):
        """Contacts des utilisateurs du groupe = contacts qui ont l'étiquette ; retire l'étiquette aux contacts d'utilisateurs qui ne sont plus membres."""
        if not self._rlq_etiquettes_actives():
            return
        champ = _champ_membres(self.env)
        partenaires = self.env["res.partner"].sudo().with_context(active_test=False)
        for groupe in self.sudo().filtered("rlq_category_id"):
            categorie = groupe.rlq_category_id
            voulus = groupe[champ].partner_id
            porteurs = partenaires.search([("category_id", "=", categorie.id)])
            a_ajouter = voulus - porteurs
            a_retirer = (porteurs - voulus).filtered("user_ids")
            if a_ajouter:
                a_ajouter.write({"category_id": [(4, categorie.id)]})
            if a_retirer:
                a_retirer.write({"category_id": [(3, categorie.id)]})

    def _rlq_renommer_etiquette(self):
        """L'étiquette porte exactement le nom du groupe ; renvoie le nombre d'étiquettes renommées."""
        n = 0
        for groupe in self.sudo().filtered("rlq_category_id"):
            if groupe.name and groupe.rlq_category_id.name != groupe.name:
                groupe.rlq_category_id.name = groupe.name
                n += 1
        return n

    def unlink(self):
        """Groupe supprimé -> son étiquette aussi (v1.104.0), sauf si un autre groupe s'en sert encore."""
        categories = self.sudo().rlq_category_id
        ids_groupes = self.ids
        res = super().unlink()
        try:
            if categories:
                encore = self.sudo().search([("rlq_category_id", "in", categories.ids), ("id", "not in", ids_groupes)]).rlq_category_id
                (categories - encore).exists().unlink()
        except Exception:  # noqa: BLE001 - la suppression du groupe a réussi : une étiquette restante ne doit pas faire échouer l'opération
            _logger.warning("étiquettes de groupes supprimés non supprimées (étiquettes %s)", categories.ids, exc_info=True)
        return res

    def write(self, vals):
        res = super().write(vals)
        try:
            if self._rlq_etiquettes_actives():
                if "name" in vals:
                    for groupe in self.sudo().filtered("rlq_category_id"):
                        if groupe.rlq_category_id.name != groupe.name:
                            groupe.rlq_category_id.name = groupe.name
                if _champ_membres(self.env) in vals:
                    self._rlq_synchroniser_etiquette()
        except Exception:  # noqa: BLE001 - ne jamais bloquer la modification d'un groupe
            _logger.warning("étiquettes de groupes non synchronisées (groupes %s)", self.ids, exc_info=True)
        return res

    @api.model
    def _cron_rlq_synchroniser_etiquettes(self):
        """Tâche planifiée : étiquette + membres de tous les groupes liés à un billet ou à une réponse de sondage (et de ceux qui en ont déjà une)."""
        groupes = (self.env["event.event.ticket"].sudo().search([("rlq_group_id", "!=", False)]).rlq_group_id
                   | self.env["survey.question.answer"].sudo().search([("rlq_group_id", "!=", False)]).rlq_group_id
                   | self.sudo().search([("rlq_category_id", "!=", False)]))
        groupes._rlq_assurer_etiquette()
        return len(groupes)


class ResUsersEtiquettes(models.Model):
    _inherit = "res.users"

    def _rlq_touche_aux_groupes(self, vals):
        champ = _champ_groupes_utilisateur(self.env)
        return any(k in ("active", "partner_id", champ) or k.startswith(("in_group_", "sel_groups_")) for k in vals)

    @api.model_create_multi
    def create(self, vals_list):
        utilisateurs = super().create(vals_list)
        try:
            champ = _champ_groupes_utilisateur(self.env)
            utilisateurs.sudo()[champ].filtered("rlq_category_id")._rlq_synchroniser_etiquette()
        except Exception:  # noqa: BLE001 - la création d'un compte ne doit jamais échouer ici
            _logger.warning("étiquettes de groupes non synchronisées (nouveaux comptes)", exc_info=True)
        return utilisateurs

    def write(self, vals):
        suivre = self._rlq_touche_aux_groupes(vals)
        champ = _champ_groupes_utilisateur(self.env)
        avant = self.sudo()[champ].filtered("rlq_category_id") if suivre else self.env["res.groups"]
        res = super().write(vals)
        if suivre:
            try:
                (avant | self.sudo()[champ].filtered("rlq_category_id"))._rlq_synchroniser_etiquette()
            except Exception:  # noqa: BLE001 - jamais bloquer la modification d'un compte
                _logger.warning("étiquettes de groupes non synchronisées (utilisateurs %s)", self.ids, exc_info=True)
        return res


class EventTicketEtiquette(models.Model):
    _inherit = "event.event.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        billets = super().create(vals_list)
        billets._rlq_etiquettes_des_groupes()
        return billets

    def write(self, vals):
        res = super().write(vals)
        if "rlq_group_id" in vals:
            self._rlq_etiquettes_des_groupes()
        return res

    def _rlq_etiquettes_des_groupes(self):
        try:
            self.sudo().rlq_group_id._rlq_assurer_etiquette()
        except Exception:  # noqa: BLE001 - jamais bloquer l'enregistrement d'un billet
            _logger.warning("étiquettes de groupes de billets non créées", exc_info=True)


class SurveyQuestionAnswerEtiquette(models.Model):
    _inherit = "survey.question.answer"

    @api.model_create_multi
    def create(self, vals_list):
        reponses = super().create(vals_list)
        reponses._rlq_etiquettes_des_groupes()
        return reponses

    def write(self, vals):
        res = super().write(vals)
        if "rlq_group_id" in vals:
            self._rlq_etiquettes_des_groupes()
        return res

    def _rlq_etiquettes_des_groupes(self):
        try:
            self.sudo().rlq_group_id._rlq_assurer_etiquette()
        except Exception:  # noqa: BLE001 - jamais bloquer l'enregistrement d'une réponse de sondage
            _logger.warning("étiquettes de groupes de réponses non créées", exc_info=True)
