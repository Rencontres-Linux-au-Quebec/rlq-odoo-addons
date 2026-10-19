# -*- coding: utf-8 -*-
"""
event_groupes_inscrits.py
==========================

Groupes Odoo des personnes inscrites à un événement, un groupe par type de billet (v1.98.0).

Exemple : événement « Journée portes ouvertes sur Linux 2026 », préfixe « JPOL26 » (v1.104.0 : les groupes créés commencent par « RLQ- ») :
    billet Visiteur       -> groupe « RLQ-JPOL26-Visiteur »
    billet Bénévole       -> groupe « RLQ-JPOL26-Bénévole »
    billet Commanditaire  -> groupe « RLQ-JPOL26-Commanditaire »
Les groupes créés avant la v1.104.0 (« JPOL26-Visiteur »…) ne sont PAS renommés.

Le groupe est ensuite associé, dans Discuss, à un canal de discussion (champ « Groupes à abonner
automatiquement » du canal) : les membres du groupe en deviennent membres.

Fonctionnement :
  - `event.event.rlq_groupe_prefixe` : préfixe des groupes. Vide = fonction désactivée pour l'événement.
  - `event.event.ticket.rlq_group_id` : groupe du billet. Rempli automatiquement (groupe existant de
    même nom, sinon CRÉÉ) quand un préfixe est défini ; modifiable à la main (choisir un autre groupe,
    ou en vider un pour ne rien faire pour ce billet).
  - Une inscription confirmée (état `open`) ou présente (`done`) ajoute l'UTILISATEUR de la personne
    (compte portail, créé à sa première connexion) au groupe de son billet.
  - Compte créé APRÈS l'inscription (cas courant : le compte portail naît à la première connexion) :
    la création du compte (`res.users.create`) rattrape les inscriptions de ce contact.
  - `event.registration.rlq_groupe_refus` : case « Ne pas ajouter au groupe » ; cochée, la personne est
    retirée du groupe et n'y est plus jamais ajoutée par ce module (refus, Loi 25).
  - Bouton « Créer / synchroniser les groupes » sur l'événement : traite les inscriptions existantes
    (idempotent : relançable sans créer de doublon). Retirer quelqu'un du groupe À LA MAIN ne suffit
    pas : la prochaine synchronisation le rajouterait ; cochez plutôt la case de refus.
  - Inscription ANNULÉE (v1.99.0) : la personne est retirée du groupe de son billet, sauf si une autre de ses inscriptions
    actives le lui donne encore.
  - Réponses au sondage (v1.99.0) : `survey.question.answer.rlq_group_id` (colonne « Groupe Odoo » des réponses suggérées d'une
    question). Ex. « Serez-vous présent à l'ÉTS ? » = Oui -> « RLQ-JPOL26-Présentiel ». Appliqué quand la personne termine le
    sondage ; retiré avec l'annulation ou le refus de l'inscription liée à ce sondage.
  - Jamais de blocage : toute erreur est journalisée (sans courriel ni nom) et l'inscription continue.

ATTENTION - NON VÉRIFIABLE SANS ACCÈS À UNE INSTANCE (voir NOTES_VALIDATION.md, section -67).

© Services-Linux Conseils Inc — Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com
Licence : AGPL-3
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .report_builder import nom_groupe_billet, nom_groupe_rlq

_logger = logging.getLogger(__name__)

RLQ_SYNCHRO_MINUTES_MIN = 5          # fréquence de la tâche planifiée : un intervalle plus court n'aurait aucun effet

ETATS_INSCRIPTION_ACTIVE = ("open", "done")

RLQ_SYNCHRO_MINUTES_DEFAUT = 15      # intervalle proposé pour un nouveau sondage ou événement (modifiable : paramètre système, voir ci-dessous)
RLQ_PARAM_SYNCHRO_MINUTES = "rlq_survey_report.synchro_minutes_defaut"


def _synchro_minutes_defaut(env):
    """Intervalle (minutes) proposé par défaut : paramètre système `rlq_survey_report.synchro_minutes_defaut` (v1.108.0), 15 s'il est absent
    ou invalide, jamais moins que le minimum (RLQ_SYNCHRO_MINUTES_MIN)."""
    valeur = env["ir.config_parameter"].sudo().get_param(RLQ_PARAM_SYNCHRO_MINUTES)
    try:
        minutes = int(str(valeur).strip()) if valeur else RLQ_SYNCHRO_MINUTES_DEFAUT
    except ValueError:
        minutes = RLQ_SYNCHRO_MINUTES_DEFAUT
    return max(minutes, RLQ_SYNCHRO_MINUTES_MIN)


def _champ_groupes_utilisateur(env):
    """Nom du champ « groupes » de res.users : `group_ids` (Odoo récent) ou `groups_id` (Odoo 18 habituel)."""
    champs = env["res.users"]._fields
    return "group_ids" if "group_ids" in champs and "groups_id" not in champs else "groups_id"


class EventEventGroupes(models.Model):
    _inherit = "event.event"

    rlq_groupe_prefixe = fields.Char(
        string="Préfixe des groupes d'inscrits", copy=False,
        help="Ex. « JPOL26 » : un groupe Odoo « RLQ-JPOL26-<billet> » est créé (s'il n'existe pas) pour chaque type de billet "
             "(RLQ-JPOL26-Visiteur, RLQ-JPOL26-Bénévole, RLQ-JPOL26-Commanditaire ; « RLQ- » est ajouté automatiquement) et les personnes inscrites y sont ajoutées "
             "automatiquement. Vide : aucun groupe pour cet événement. Associez ensuite chaque groupe à un canal de "
             "discussion (Discuss > canal > Groupes à abonner automatiquement).",
    )

    rlq_synchro_active = fields.Boolean(
        string="Synchronisation périodique", copy=False,
        help="Si coché, les groupes des inscrits et leurs étiquettes de contact sont remis à jour automatiquement toutes les N minutes, "
             "jusqu'au lendemain de la fin de l'événement (ensuite la synchronisation s'arrête seule).",
    )
    rlq_synchro_minutes = fields.Integer(string="Toutes les (minutes)", default=lambda self: _synchro_minutes_defaut(self.env), copy=False,
                                         help="Intervalle entre deux mises à jour de cet événement (minimum 5 : fréquence de la tâche planifiée).")
    rlq_synchro_derniere = fields.Datetime(string="Dernière synchronisation", copy=False, readonly=True)
    rlq_synchro_resultat = fields.Char(string="Résultat de la dernière synchronisation", copy=False, readonly=True)

    @api.constrains("rlq_synchro_minutes")
    def _check_rlq_synchro_minutes(self):
        for evenement in self:
            if evenement.rlq_synchro_active and evenement.rlq_synchro_minutes < RLQ_SYNCHRO_MINUTES_MIN:
                raise ValidationError(_("L'intervalle de synchronisation doit être d'au moins %s minutes.", RLQ_SYNCHRO_MINUTES_MIN))

    @api.model_create_multi
    def create(self, vals_list):
        evenements = super().create(vals_list)
        evenements._rlq_assurer_groupes()
        if any(v.get("rlq_synchro_active") for v in vals_list):
            self.env["survey.survey"]._rlq_ajuster_cron()
        return evenements

    def write(self, vals):
        res = super().write(vals)
        if "rlq_groupe_prefixe" in vals:
            self._rlq_assurer_groupes()
        if {"rlq_synchro_active", "active"} & set(vals):
            self.env["survey.survey"]._rlq_ajuster_cron()
        return res

    def unlink(self):
        res = super().unlink()
        self.env["survey.survey"]._rlq_ajuster_cron()
        return res

    def _rlq_assurer_groupes(self):
        """Pour chaque billet sans groupe : trouve ou crée « <préfixe>-<billet> » (idempotent)."""
        for evenement in self.filtered("rlq_groupe_prefixe"):
            try:
                evenement.sudo().event_ticket_ids._rlq_assurer_groupe()
            except Exception:  # noqa: BLE001 - ne jamais bloquer l'enregistrement de l'événement
                _logger.warning("groupes d'inscrits non créés (événement %s)", evenement.id, exc_info=True)

    def action_rlq_synchroniser_groupes(self):
        """Bouton : crée les groupes manquants puis y place les inscrits existants."""
        self.ensure_one()
        self._rlq_assurer_groupes()
        inscriptions = self.env["event.registration"].sudo().search([("event_id", "=", self.id)])
        ajoutes, sans_compte = inscriptions._rlq_synchroniser_groupe()
        try:                                                   # étiquettes de contact des groupes des billets (voir groupes_etiquettes.py)
            self.sudo().event_ticket_ids.rlq_group_id._rlq_assurer_etiquette()
        except Exception:  # noqa: BLE001 - le bouton ne doit jamais échouer à cause des étiquettes
            _logger.warning("étiquettes de groupes non synchronisées (événement %s)", self.id, exc_info=True)
        self.sudo().write({
            "rlq_synchro_derniere": fields.Datetime.now(),
            "rlq_synchro_resultat": _("%(a)s personne(s) dans leur groupe, %(s)s sans compte", a=ajoutes, s=sans_compte),
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Groupes des inscrits"),
                "message": _("%(ajoutes)s personne(s) dans leur groupe ; %(sans)s inscription(s) sans compte portail pour le moment "
                             "(elles seront ajoutées à la création du compte).", ajoutes=ajoutes, sans=sans_compte),
                "type": "success",
                "sticky": False,
            },
        }


    @api.model
    def _cron_rlq_synchroniser_evenements(self):
        """Tâche planifiée (toutes les 5 minutes, v1.107.0) : synchronise les événements dont la synchronisation périodique est active, dont l'intervalle est écoulé
        et qui ne sont pas terminés depuis plus d'un jour. Retourne le nombre d'événements traités."""
        maintenant = fields.Datetime.now()
        n = 0
        for evenement in self.sudo().search([("rlq_synchro_active", "=", True)]):
            if evenement.date_end and evenement.date_end + timedelta(days=1) < maintenant:
                continue                                              # événement terminé depuis plus d'un jour : plus rien à synchroniser
            minutes = max(evenement.rlq_synchro_minutes or 0, RLQ_SYNCHRO_MINUTES_MIN)
            if evenement.rlq_synchro_derniere and evenement.rlq_synchro_derniere + timedelta(minutes=minutes) > maintenant + timedelta(seconds=30):
                continue
            try:
                evenement.action_rlq_synchroniser_groupes()
                n += 1
            except Exception:  # noqa: BLE001 - un événement en erreur n'arrête pas les autres
                _logger.warning("synchronisation périodique de l'événement %s en erreur", evenement.id, exc_info=True)
        return n


class EventEventTicketGroupes(models.Model):
    _inherit = "event.event.ticket"

    rlq_group_id = fields.Many2one(
        "res.groups", string="Groupe des inscrits", copy=False, ondelete="set null",
        help="Groupe Odoo auquel sont ajoutées les personnes inscrites avec CE type de billet. Rempli automatiquement quand "
             "l'événement a un préfixe de groupes ; vous pouvez choisir un autre groupe existant.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        billets = super().create(vals_list)
        try:
            billets.sudo()._rlq_assurer_groupe()
        except Exception:  # noqa: BLE001 - ne jamais bloquer la création d'un billet
            _logger.warning("groupe de billet non créé", exc_info=True)
        return billets

    def _rlq_assurer_groupe(self):
        """Trouve ou crée le groupe « RLQ-<préfixe>-<billet> » des billets qui n'en ont pas (le préfixe est celui de l'événement)."""
        groupes = self.env["res.groups"].sudo()
        for billet in self.filtered(lambda b: not b.rlq_group_id and b.event_id.rlq_groupe_prefixe):
            nom = nom_groupe_billet(billet.event_id.rlq_groupe_prefixe, billet.name)
            if not nom:
                continue
            groupe = groupes.search([("name", "=", nom)], limit=1)
            if not groupe:
                groupe = groupes.create({"name": nom, "comment": "Inscrits (%s) — créé par rlq_survey_report" % billet.event_id.name})
            billet.rlq_group_id = groupe


class EventRegistrationGroupes(models.Model):
    _inherit = "event.registration"

    rlq_groupe_refus = fields.Boolean(
        string="Ne pas ajouter au groupe", copy=False,
        help="Cochée : la personne est retirée du groupe de son billet et n'y sera plus ajoutée (elle ne souhaite pas être "
             "dans le canal de discussion de l'événement).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        inscriptions = super().create(vals_list)
        inscriptions._rlq_synchroniser_groupe_sans_blocage()
        return inscriptions

    def write(self, vals):
        res = super().write(vals)
        if {"state", "event_ticket_id", "partner_id", "rlq_groupe_refus"} & set(vals):
            self._rlq_synchroniser_groupe_sans_blocage()
        return res

    def _rlq_synchroniser_groupe_sans_blocage(self):
        try:
            self.sudo()._rlq_synchroniser_groupe()
        except Exception:  # noqa: BLE001 - une inscription (souvent publique) ne doit jamais échouer à cause des groupes
            _logger.warning("groupes d'inscrits non synchronisés (inscriptions %s)", self.ids, exc_info=True)

    def _rlq_sondages(self):
        """Sondages liés à cette inscription : celui du billet (rlq_survey_id) et, s'il existe, celui de l'événement."""
        self.ensure_one()
        sondages = self.event_ticket_id.rlq_survey_id if self.event_ticket_id else self.env["survey.survey"]
        if "survey_id" in self.event_id._fields and self.event_id.survey_id:
            sondages |= self.event_id.survey_id
        return sondages

    def _rlq_groupes_de_inscription(self):
        """(groupes concernés, groupes voulus) pour CETTE inscription : le groupe de son billet et ceux des réponses de la personne
        aux sondages liés. « Voulus » seulement si l'inscription est active (open / done) et sans refus."""
        self.ensure_one()
        billet = self.event_ticket_id.rlq_group_id if self.event_ticket_id else self.env["res.groups"]
        reponses_toutes, reponses_derniere = self.env["survey.user_input"].sudo()._rlq_groupes_reponses(self.partner_id, self._rlq_sondages())
        actif = self.state in ETATS_INSCRIPTION_ACTIVE and not self.rlq_groupe_refus
        return billet | reponses_toutes, ((billet | reponses_derniere) if actif else self.env["res.groups"])

    def _rlq_synchroniser_groupe(self):
        """Pour chaque personne concernée : ajoute son utilisateur aux groupes voulus (inscriptions actives, sans refus) et le retire des
        groupes que ses inscriptions annulées ou refusées lui donnaient et qu'aucune inscription active ne lui donne.
        Retourne (nombre de personnes ajoutées ou déjà dans leurs groupes, nombre d'inscriptions sans compte)."""
        champ = _champ_groupes_utilisateur(self.env)
        ajoutes = sans_compte = 0
        sans_contact = self.sudo().filtered(lambda r: not r.partner_id)
        sans_compte += len(sans_contact)
        for contact in self.sudo().partner_id:
            toutes = self.env["event.registration"].sudo().search([("partner_id", "=", contact.id)])
            concernes = voulus = self.env["res.groups"]
            for inscription in toutes:
                c, v = inscription._rlq_groupes_de_inscription()
                concernes |= c
                voulus |= v
            utilisateurs = contact.user_ids.filtered("active")
            if not utilisateurs:
                sans_compte += len(self.sudo().filtered(lambda r, c=contact: r.partner_id == c))
                continue
            for groupe in voulus:
                utilisateurs.write({champ: [(4, groupe.id)]})
            for groupe in concernes - voulus:
                utilisateurs.write({champ: [(3, groupe.id)]})
            if voulus:
                ajoutes += len(utilisateurs)
        return ajoutes, sans_compte


class SurveyQuestionAnswerGroupes(models.Model):
    _inherit = "survey.question.answer"

    rlq_group_id = fields.Many2one(
        "res.groups", string="Groupe Odoo", copy=False, ondelete="set null",
        help="Si la personne choisit cette réponse (ex. « Serez-vous présent à l'ÉTS ? » = Oui), elle est ajoutée à ce groupe "
             "(ex. RLQ-JPOL26-Présentiel) en terminant le sondage. Tapez un nom puis « Créer » pour créer le groupe (« RLQ- » est ajouté au début s'il manque). Laissez vide "
             "pour ne rien faire.",
    )


class SurveyUserInputGroupes(models.Model):
    _inherit = "survey.user_input"

    def _mark_done(self):
        res = super()._mark_done()
        for participation in self:
            try:
                participation.sudo()._rlq_appliquer_groupes_sondage()
            except Exception:  # noqa: BLE001 - jamais bloquer la soumission d'un sondage
                _logger.warning("groupes du sondage non appliqués (participation %s)", participation.id, exc_info=True)
        return res

    @api.model
    def _rlq_groupes_reponses(self, contact, sondages):
        """(groupes de TOUTES les réponses terminées de la personne à ces sondages, groupes de sa DERNIÈRE réponse terminée à chacun).
        Seule la dernière compte : « Oui » puis, en refaisant le sondage, « Non » -> le groupe n'est plus voulu."""
        vide = self.env["res.groups"]
        if not contact or not sondages:
            return vide, vide
        toutes = derniere = vide
        for sondage in sondages:
            participations = self.sudo().search([("partner_id", "=", contact.id), ("survey_id", "=", sondage.id), ("state", "=", "done")], order="id desc")
            for rang, participation in enumerate(participations):
                groupes = participation.user_input_line_ids.suggested_answer_id.rlq_group_id
                toutes |= groupes
                if rang == 0:
                    derniere |= groupes
        return toutes, derniere

    def _rlq_appliquer_groupes_sondage(self):
        """Applique les groupes des réponses de la personne. Si elle a une inscription liée à ce sondage, la synchronisation des
        inscriptions décide (refus, annulation) ; sinon : ajout des groupes de sa dernière réponse, retrait de ceux des réponses
        précédentes qu'elle n'a plus (Oui puis Non)."""
        self.ensure_one()
        contact = self.partner_id
        if not contact or not self.survey_id.question_ids.suggested_answer_ids.rlq_group_id:       # sondage sans réponse liée à un groupe : rien à faire
            return
        inscriptions = self.env["event.registration"].sudo().search([("partner_id", "=", contact.id)]).filtered(lambda r: self.survey_id in r._rlq_sondages())
        if inscriptions:
            inscriptions._rlq_synchroniser_groupe()
            return
        toutes, derniere = self._rlq_groupes_reponses(contact, self.survey_id)
        champ = _champ_groupes_utilisateur(self.env)
        utilisateurs = contact.user_ids.filtered("active")
        for groupe in derniere:
            utilisateurs.write({champ: [(4, groupe.id)]})
        for groupe in toutes - derniere:
            utilisateurs.write({champ: [(3, groupe.id)]})


class SurveySurveyGroupes(models.Model):
    _inherit = "survey.survey"

    rlq_synchro_active = fields.Boolean(
        string="Synchronisation périodique", copy=False,
        help="Si coché, les groupes des réponses et les étiquettes de contact de ce sondage sont remis à jour automatiquement toutes les N minutes "
             "(utile tant que des gens répondent ou changent d'avis). Une tâche planifiée vérifie toutes les 5 minutes quels sondages sont à faire.",
    )
    rlq_synchro_minutes = fields.Integer(
        string="Toutes les (minutes)", default=lambda self: _synchro_minutes_defaut(self.env), copy=False,
        help="Intervalle entre deux mises à jour de ce sondage (minimum 5 : c'est la fréquence de la tâche planifiée).",
    )
    rlq_synchro_derniere = fields.Datetime(string="Dernière synchronisation", copy=False, readonly=True)
    rlq_synchro_resultat = fields.Char(string="Résultat de la dernière synchronisation", copy=False, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        sondages = super().create(vals_list)
        if any(v.get("rlq_synchro_active") for v in vals_list):
            self._rlq_ajuster_cron()
        return sondages

    def write(self, vals):
        res = super().write(vals)
        if {"rlq_synchro_active", "active"} & set(vals):
            self._rlq_ajuster_cron()
        return res

    def unlink(self):
        res = super().unlink()
        self._rlq_ajuster_cron()
        return res

    @api.model
    def _rlq_ajuster_cron(self):
        """v1.108.0 : la tâche planifiée « RLQ Sondages et événements : synchronisation périodique… » n'est ACTIVE que si au moins un sondage ou un événement
        a la case « Synchronisation périodique » cochée. Sinon elle est désactivée : plus de ligne « Job ... starting » toutes les 5 minutes dans le journal d'Odoo.
        Les synchronisations immédiates (inscription, sondage terminé, création de compte) ne dépendent pas de cette tâche. Appelée aussi à chaque mise à jour du module."""
        cron = self.env.ref("rlq_survey_report.ir_cron_synchro_sondages", raise_if_not_found=False)
        if not cron:
            return False
        voulu = bool(self.env["survey.survey"].sudo().search_count([("rlq_synchro_active", "=", True)])
                     or self.env["event.event"].sudo().search_count([("rlq_synchro_active", "=", True)]))
        if cron.sudo().active != voulu:
            cron.sudo().write({"active": voulu})
        return voulu

    @api.constrains("rlq_synchro_minutes")
    def _check_rlq_synchro_minutes(self):
        for sondage in self:
            if sondage.rlq_synchro_active and sondage.rlq_synchro_minutes < RLQ_SYNCHRO_MINUTES_MIN:
                raise ValidationError(_("L'intervalle de synchronisation doit être d'au moins %s minutes.", RLQ_SYNCHRO_MINUTES_MIN))

    def _rlq_synchroniser_groupes_et_etiquettes(self):
        """Applique les groupes des réponses à TOUS les participants de ce sondage, puis met à jour les étiquettes de contact des groupes liés à ses réponses.
        Idempotent. Retourne (traitées, sans_compte, erreurs) ; mémorise l'heure et le résultat. Une personne en erreur n'arrête pas les autres."""
        self.ensure_one()
        participations = self.env["survey.user_input"].sudo().search([("survey_id", "=", self.id), ("state", "=", "done"), ("partner_id", "!=", False)], order="id desc")
        vues = self.env["res.partner"]
        traitees = sans_compte = erreurs = 0
        for participation in participations:
            if participation.partner_id in vues:                    # la plus récente de chaque personne suffit : _rlq_appliquer_groupes_sondage lit toutes ses réponses
                continue
            vues |= participation.partner_id
            if not participation.partner_id.user_ids.filtered("active"):
                sans_compte += 1
                continue
            try:
                participation._rlq_appliquer_groupes_sondage()
                traitees += 1
            except Exception:  # noqa: BLE001 - une personne en erreur ne doit pas arrêter les autres
                erreurs += 1
                _logger.warning("groupes du sondage non appliqués (participation %s)", participation.id, exc_info=True)
        try:
            self.sudo().question_ids.suggested_answer_ids.rlq_group_id._rlq_assurer_etiquette()
        except Exception:  # noqa: BLE001 - les étiquettes seront refaites au prochain passage
            erreurs += 1
            _logger.warning("étiquettes du sondage %s non mises à jour", self.id, exc_info=True)
        self.sudo().write({
            "rlq_synchro_derniere": fields.Datetime.now(),
            "rlq_synchro_resultat": _("%(n)s participant(s) mis à jour, %(s)s sans compte, %(e)s erreur(s)", n=traitees, s=sans_compte, e=erreurs),
        })
        return traitees, sans_compte, erreurs

    def action_rlq_appliquer_groupes_participants(self):
        """Bouton « Appliquer les groupes aux participants » (v1.103.0) : après avoir lié un groupe à une réponse, applique les groupes des réponses
        à TOUTES les personnes qui ont déjà terminé ce sondage (leur dernière réponse compte ; inscription liée, refus et annulation respectés),
        puis met à jour les étiquettes (v1.106.0). Idempotent : relançable sans doublon. Les personnes sans compte seront ajoutées à la création de leur compte."""
        self.ensure_one()
        traitees, sans_compte, erreurs = self._rlq_synchroniser_groupes_et_etiquettes()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Groupes des participants"),
                "message": _("%(n)s participant(s) mis à jour ; %(s)s sans compte portail pour le moment (ajoutés à la création du compte) ; %(e)s erreur(s).",
                             n=traitees, s=sans_compte, e=erreurs),
                "type": "warning" if erreurs else "success",
                "sticky": bool(erreurs),
            },
        }

    @api.model
    def _cron_rlq_synchroniser_sondages(self):
        """Tâche planifiée (toutes les 5 minutes, v1.106.0) : synchronise les sondages dont la synchronisation périodique est active et dont l'intervalle
        (rlq_synchro_minutes) est écoulé depuis la dernière fois. Retourne le nombre de sondages traités."""
        maintenant = fields.Datetime.now()
        n = 0
        for sondage in self.sudo().search([("rlq_synchro_active", "=", True)]):
            minutes = max(sondage.rlq_synchro_minutes or 0, RLQ_SYNCHRO_MINUTES_MIN)
            if sondage.rlq_synchro_derniere and sondage.rlq_synchro_derniere + timedelta(minutes=minutes) > maintenant + timedelta(seconds=30):
                continue                                              # pas encore l'heure (marge de 30 s : la tâche ne tombe jamais pile)
            try:
                sondage._rlq_synchroniser_groupes_et_etiquettes()
                n += 1
            except Exception:  # noqa: BLE001 - un sondage en erreur n'arrête pas les autres
                _logger.warning("synchronisation périodique du sondage %s en erreur", sondage.id, exc_info=True)
        return n


class ResGroupsCreationRapide(models.Model):
    """Création rapide d'un groupe (champ « Groupe Odoo » d'une réponse de sondage, groupe d'un billet : saisir un nom puis « Créer »).
    Sans cela, Odoo 18 insère un groupe SANS nom (le nom affiché de res.groups est calculé) et la base refuse : « null value in column "name" ».
    Depuis la v1.104.0, le nom des groupes créés ainsi commence toujours par « RLQ- » (ajouté s'il manque, jamais doublé)."""
    _inherit = "res.groups"

    @api.model
    def name_create(self, name):
        groupe = self.create({"name": nom_groupe_rlq(name) or name})
        return groupe.id, groupe.display_name


class ResUsersGroupesInscrits(models.Model):
    _inherit = "res.users"

    @api.model_create_multi
    def create(self, vals_list):
        utilisateurs = super().create(vals_list)
        try:
            contacts = utilisateurs.partner_id
            inscriptions = self.env["event.registration"].sudo().search([("partner_id", "in", contacts.ids)])
            if inscriptions:
                inscriptions._rlq_synchroniser_groupe()
            participations = self.env["survey.user_input"].sudo().search([
                ("partner_id", "in", contacts.ids), ("state", "=", "done"), ("user_input_line_ids.suggested_answer_id.rlq_group_id", "!=", False)])
            for participation in participations:
                participation._rlq_appliquer_groupes_sondage()
        except Exception:  # noqa: BLE001 - la création d'un compte (inscription au portail) ne doit jamais échouer ici
            _logger.warning("groupes d'inscrits non synchronisés pour de nouveaux comptes", exc_info=True)
        return utilisateurs
