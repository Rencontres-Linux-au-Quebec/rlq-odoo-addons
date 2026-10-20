# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests Odoo (TransactionCase) des groupes d'inscrits (v1.98.0).

⚠️ NON EXÉCUTÉS pendant l'écriture (aucune instance Odoo) : voir test_wizard.py pour la marche à suivre
(base JETABLE, jamais la production) :

    odoo-bin -d NOM_BASE_DE_TEST -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRlqGroupesInscrits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evenement = cls.env["event.event"].create({
            "name": "Journée portes ouvertes sur Linux 2026", "date_begin": "2026-10-24 13:00:00", "date_end": "2026-10-24 21:00:00",
            "rlq_groupe_prefixe": "JPOL26",
        })
        cls.billets = {n: cls.env["event.event.ticket"].create({"name": n, "event_id": cls.evenement.id}) for n in ("Visiteur", "Bénévole", "Commanditaire")}
        cls.champ = "group_ids" if "group_ids" in cls.env["res.users"]._fields and "groups_id" not in cls.env["res.users"]._fields else "groups_id"

    def _utilisateur(self, nom):
        return self.env["res.users"].with_context(no_reset_password=True).create({
            "name": nom, "login": "%s@example.com" % nom.lower(), "email": "%s@example.com" % nom.lower(),
            "groups_id" if self.champ == "groups_id" else "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })

    def _inscription(self, partner, billet, **valeurs):
        return self.env["event.registration"].create({
            "event_id": self.evenement.id, "event_ticket_id": self.billets[billet].id, "partner_id": partner.id,
            "name": partner.name, "email": partner.email, "state": "open", **valeurs,
        })

    def _dans_groupe(self, utilisateur, billet):
        return self.billets[billet].rlq_group_id in utilisateur[self.champ]

    def test_groupes_crees_une_seule_fois(self):
        for nom, billet in self.billets.items():
            self.assertEqual(billet.rlq_group_id.name, "RLQ-JPOL26-%s" % nom)
        avant = self.env["res.groups"].search_count([("name", "like", "RLQ-JPOL26-")])
        self.evenement.action_rlq_synchroniser_groupes()
        self.assertEqual(self.env["res.groups"].search_count([("name", "like", "RLQ-JPOL26-")]), avant)

    def test_inscrit_avec_compte_est_ajoute_au_groupe_de_son_billet(self):
        u = self._utilisateur("Alice")
        self._inscription(u.partner_id, "Bénévole")
        self.assertTrue(self._dans_groupe(u, "Bénévole"))
        self.assertFalse(self._dans_groupe(u, "Visiteur"))

    def test_compte_cree_apres_l_inscription(self):
        partner = self.env["res.partner"].create({"name": "Bruno", "email": "bruno@example.com"})
        self._inscription(partner, "Visiteur")
        u = self._utilisateur("Bruno")
        self.assertEqual(u.partner_id.email, "bruno@example.com")
        self.assertTrue(self._dans_groupe(u, "Visiteur"))

    def test_refus_retire_et_ne_rajoute_plus(self):
        u = self._utilisateur("Carole")
        inscription = self._inscription(u.partner_id, "Visiteur")
        self.assertTrue(self._dans_groupe(u, "Visiteur"))
        inscription.rlq_groupe_refus = True
        self.assertFalse(self._dans_groupe(u, "Visiteur"))
        self.evenement.action_rlq_synchroniser_groupes()
        self.assertFalse(self._dans_groupe(u, "Visiteur"))

    def test_brouillon_et_sans_groupe_ne_font_rien(self):
        u = self._utilisateur("Denis")
        self._inscription(u.partner_id, "Visiteur", state="draft")
        self.assertFalse(self._dans_groupe(u, "Visiteur"))
        self.billets["Commanditaire"].rlq_group_id = False
        inscription = self._inscription(u.partner_id, "Commanditaire")           # billet sans groupe : aucune erreur, aucun ajout
        self.assertEqual(inscription.state, "open")
        self.assertFalse(self._dans_groupe(u, "Visiteur"))

    def test_annulation_retire_du_groupe_sauf_autre_inscription_active(self):
        u = self._utilisateur("Eve")
        premiere = self._inscription(u.partner_id, "Visiteur")
        seconde = self._inscription(u.partner_id, "Visiteur")
        premiere.state = "cancel"
        self.assertTrue(self._dans_groupe(u, "Visiteur"))              # la seconde inscription le lui donne encore
        seconde.state = "cancel"
        self.assertFalse(self._dans_groupe(u, "Visiteur"))

    def _sondage_presentiel(self):
        sondage = self.env["survey.survey"].create({"title": "Sondage JPOL26", "access_mode": "public"})
        groupe = self.env["res.groups"].create({"name": "JPOL26-Présentiel"})
        question = self.env["survey.question"].create({
            "survey_id": sondage.id, "title": "Serez-vous présent à l'ÉTS ?", "question_type": "simple_choice",
            "suggested_answer_ids": [(0, 0, {"value": "Oui", "rlq_group_id": groupe.id}), (0, 0, {"value": "Non"})],
        })
        return sondage, groupe, question

    def _repondre(self, sondage, question, partner, reponse):
        participation = self.env["survey.user_input"].create({"survey_id": sondage.id, "partner_id": partner.id, "state": "in_progress"})
        self.env["survey.user_input.line"].create({
            "user_input_id": participation.id, "question_id": question.id, "answer_type": "suggestion", "suggested_answer_id": reponse.id})
        participation._mark_done()
        return participation

    def test_reponse_du_sondage_ajoute_au_groupe_puis_annulation_le_retire(self):
        sondage, groupe, question = self._sondage_presentiel()
        self.billets["Visiteur"].rlq_survey_id = sondage
        u = self._utilisateur("Fred")
        inscription = self._inscription(u.partner_id, "Visiteur")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[0])        # « Oui »
        self.assertIn(groupe, u[self.champ])
        inscription.state = "cancel"
        self.assertNotIn(groupe, u[self.champ])
        self.assertFalse(self._dans_groupe(u, "Visiteur"))

    def test_reponse_non_ne_donne_aucun_groupe(self):
        sondage, groupe, question = self._sondage_presentiel()
        u = self._utilisateur("Gina")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[1])        # « Non »
        self.assertNotIn(groupe, u[self.champ])

    def test_sondage_sans_inscription_liee_ajout_simple(self):
        sondage, groupe, question = self._sondage_presentiel()
        u = self._utilisateur("Hugo")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[0])
        self.assertIn(groupe, u[self.champ])

    def test_oui_puis_non_retire_du_groupe(self):
        """Refaire le sondage : seule la DERNIÈRE réponse compte (avec inscription liée, puis sans)."""
        sondage, groupe, question = self._sondage_presentiel()
        oui, non = question.suggested_answer_ids[0], question.suggested_answer_ids[1]
        u = self._utilisateur("Irene")
        self._repondre(sondage, question, u.partner_id, oui)                    # sans inscription liée
        self.assertIn(groupe, u[self.champ])
        self._repondre(sondage, question, u.partner_id, non)
        self.assertNotIn(groupe, u[self.champ])
        self._repondre(sondage, question, u.partner_id, oui)
        self.assertIn(groupe, u[self.champ])
        self.billets["Visiteur"].rlq_survey_id = sondage                         # avec inscription liée
        self._inscription(u.partner_id, "Visiteur")
        self.assertIn(groupe, u[self.champ])
        self._repondre(sondage, question, u.partner_id, non)
        self.assertNotIn(groupe, u[self.champ])
        self.assertTrue(self._dans_groupe(u, "Visiteur"))                        # le groupe du billet reste

    def test_creation_rapide_d_un_groupe_par_son_nom(self):
        """v1.101.0 : taper un nom dans le champ « Groupe Odoo » puis « Créer » (name_create) ne doit plus insérer un groupe sans nom."""
        identifiant, affichage = self.env["res.groups"].name_create("JPOL26-Test")
        groupe = self.env["res.groups"].browse(identifiant)
        self.assertEqual(groupe.name, "RLQ-JPOL26-Test")                      # v1.104.0 : « RLQ- » ajouté au début
        self.assertIn("RLQ-JPOL26-Test", affichage)
        identifiant, _affichage = self.env["res.groups"].name_create("RLQ-Autre")
        self.assertEqual(self.env["res.groups"].browse(identifiant).name, "RLQ-Autre")      # jamais doublé

    # ---- v1.102.0 : étiquettes de contact qui reflètent les groupes ----
    def _etiquette(self, billet):
        return self.billets[billet].rlq_group_id.rlq_category_id

    def test_etiquette_creee_pour_chaque_groupe_de_billet(self):
        for nom in self.billets:
            self.assertEqual(self._etiquette(nom).name, "RLQ-JPOL26-%s" % nom)
        avant = self.env["res.partner.category"].search_count([("name", "like", "RLQ-JPOL26-")])
        self.evenement.action_rlq_synchroniser_groupes()
        self.assertEqual(self.env["res.partner.category"].search_count([("name", "like", "RLQ-JPOL26-")]), avant)     # idempotent

    def test_etiquette_suit_l_ajout_et_le_retrait_du_groupe(self):
        u = self._utilisateur("Jules")
        self._inscription(u.partner_id, "Bénévole")
        etiquette = self._etiquette("Bénévole")
        self.assertIn(etiquette, u.partner_id.category_id)
        self.assertNotIn(self._etiquette("Visiteur"), u.partner_id.category_id)
        # retrait À LA MAIN dans le formulaire de l'utilisateur : l'étiquette suit
        u.write({self.champ: [(3, self.billets["Bénévole"].rlq_group_id.id)]})
        self.assertNotIn(etiquette, u.partner_id.category_id)
        # ajout à la main
        u.write({self.champ: [(4, self.billets["Visiteur"].rlq_group_id.id)]})
        self.assertIn(self._etiquette("Visiteur"), u.partner_id.category_id)

    def test_etiquette_suit_le_formulaire_du_groupe_et_l_archivage(self):
        u = self._utilisateur("Karine")
        groupe = self.billets["Visiteur"].rlq_group_id
        membres = "user_ids" if "user_ids" in groupe._fields else "users"
        groupe.write({membres: [(4, u.id)]})
        self.assertIn(self._etiquette("Visiteur"), u.partner_id.category_id)
        groupe.write({membres: [(3, u.id)]})
        self.assertNotIn(self._etiquette("Visiteur"), u.partner_id.category_id)
        groupe.write({membres: [(4, u.id)]})
        u.active = False
        self.assertNotIn(self._etiquette("Visiteur"), u.partner_id.category_id)

    def test_etiquette_renommee_avec_le_groupe_et_contact_sans_compte_intact(self):
        sans_compte = self.env["res.partner"].create({"name": "Luc", "email": "luc@example.com", "category_id": [(4, self._etiquette("Visiteur").id)]})
        self.evenement.action_rlq_synchroniser_groupes()
        self.assertIn(self._etiquette("Visiteur"), sans_compte.category_id)             # pas d'utilisateur : étiquette posée à la main conservée
        self.billets["Visiteur"].rlq_group_id.name = "JPOL26-Public"
        self.assertEqual(self._etiquette("Visiteur").name, "JPOL26-Public")

    def test_etiquette_pour_un_groupe_de_reponse_de_sondage(self):
        sondage, groupe, question = self._sondage_presentiel()
        self.assertTrue(groupe.rlq_category_id)
        u = self._utilisateur("Marie")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[0])
        self.assertIn(groupe.rlq_category_id, u.partner_id.category_id)

    def test_parametre_zero_desactive_les_etiquettes(self):
        self.env["ir.config_parameter"].sudo().set_param("rlq_survey_report.etiquettes_groupes", "0")
        groupe = self.env["res.groups"].create({"name": "SANS-ETIQUETTE"})
        self.env["survey.question.answer"].create({"value": "x", "rlq_group_id": groupe.id, "question_id": self._sondage_presentiel()[2].id})
        self.assertFalse(groupe.rlq_category_id)

    def test_cron_resynchronise(self):
        u = self._utilisateur("Nina")
        groupe = self.billets["Visiteur"].rlq_group_id
        self.env.cr.execute("INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s)", (groupe.id, u.id))       # hors ORM
        self.env["res.groups"].invalidate_model()
        self.env["res.groups"]._cron_rlq_synchroniser_etiquettes()
        self.assertIn(self._etiquette("Visiteur"), u.partner_id.category_id)

    def test_appliquer_les_groupes_a_tous_ceux_qui_ont_deja_repondu(self):
        """v1.103.0 : groupe lié APRÈS les réponses -> le bouton du sondage l'applique à tous les participants ayant un compte ; relançable."""
        sondage, groupe, question = self._sondage_presentiel()
        oui, non = question.suggested_answer_ids[0], question.suggested_answer_ids[1]
        oui.rlq_group_id = False
        a, b, c = self._utilisateur("Olga"), self._utilisateur("Paul"), self._utilisateur("Quentin")
        self._repondre(sondage, question, a.partner_id, oui)
        self._repondre(sondage, question, b.partner_id, oui)
        self._repondre(sondage, question, c.partner_id, non)
        sans_compte = self.env["res.partner"].create({"name": "Rita", "email": "rita@example.com"})
        self._repondre(sondage, question, sans_compte, oui)
        self.assertNotIn(groupe, a[self.champ])
        oui.rlq_group_id = groupe                                             # le groupe est ajouté APRÈS les réponses
        self.assertNotIn(groupe, a[self.champ])
        action = sondage.action_rlq_appliquer_groupes_participants()
        self.assertEqual(action["tag"], "display_notification")
        self.assertIn(groupe, a[self.champ])
        self.assertIn(groupe, b[self.champ])
        self.assertNotIn(groupe, c[self.champ])                               # a répondu « Non »
        self.assertIn(groupe.rlq_category_id, a.partner_id.category_id)       # l'étiquette suit
        sondage.action_rlq_appliquer_groupes_participants()                   # idempotent
        self.assertIn(groupe, a[self.champ])

    # ---- v1.104.0 : suppression de groupe, assistant de vérification, préfixe RLQ- ----
    def test_etiquette_supprimee_avec_le_groupe(self):
        groupe = self.billets["Visiteur"].rlq_group_id
        etiquette = groupe.rlq_category_id
        self.assertTrue(etiquette)
        self.billets["Visiteur"].rlq_group_id = False
        groupe.unlink()
        self.assertFalse(etiquette.exists())

    def test_etiquette_partagee_par_un_autre_groupe_est_conservee(self):
        groupe = self.billets["Visiteur"].rlq_group_id
        autre = self.env["res.groups"].create({"name": "RLQ-JPOL26-Autre", "rlq_category_id": groupe.rlq_category_id.id})
        etiquette = groupe.rlq_category_id
        self.billets["Visiteur"].rlq_group_id = False
        groupe.unlink()
        self.assertTrue(etiquette.exists())
        self.assertEqual(autre.rlq_category_id, etiquette)

    def test_assistant_apercu_ne_modifie_rien_puis_applique(self):
        groupe = self.billets["Visiteur"].rlq_group_id
        groupe.rlq_category_id.name = "Ancien nom"                                  # étiquette désynchronisée
        assistant = self.env["rlq.groupes.verification"].create({})
        self.assertEqual(assistant.etat, "apercu")
        self.assertGreaterEqual(assistant.nb_changements, 1)
        self.assertEqual(groupe.rlq_category_id.name, "Ancien nom")                  # l'aperçu n'a rien changé
        assistant.action_appliquer()
        self.assertEqual(groupe.rlq_category_id.name, groupe.name)
        self.assertEqual(assistant.etat, "fait")
        self.assertEqual(assistant.nb_changements, 0)

    # ---- v1.106.0 : synchronisation périodique par sondage (NON EXÉCUTÉ : voir NOTES_VALIDATION.md) ----
    def test_synchro_periodique_respecte_l_intervalle_et_seulement_les_sondages_actifs(self):
        sondage, groupe, question = self._sondage_presentiel()
        autre = self.env["survey.survey"].create({"title": "Autre sondage"})
        u = self._utilisateur("Iris")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[0])
        u.write({self.champ: [(3, groupe.id)]})                                      # retrait fait « hors » du sondage (désynchronisation)
        self.assertEqual(self.env["survey.survey"]._cron_rlq_synchroniser_sondages(), 0)      # synchronisation non cochée : rien
        self.assertNotIn(groupe, u[self.champ])
        sondage.write({"rlq_synchro_active": True, "rlq_synchro_minutes": 15})
        self.assertEqual(self.env["survey.survey"]._cron_rlq_synchroniser_sondages(), 1)      # jamais synchronisé : à faire
        self.assertIn(groupe, u[self.champ])
        self.assertTrue(sondage.rlq_synchro_derniere)
        self.assertFalse(autre.rlq_synchro_derniere)
        u.write({self.champ: [(3, groupe.id)]})
        self.assertEqual(self.env["survey.survey"]._cron_rlq_synchroniser_sondages(), 0)      # intervalle pas écoulé
        sondage.rlq_synchro_derniere = fields.Datetime.now() - timedelta(minutes=16)
        self.assertEqual(self.env["survey.survey"]._cron_rlq_synchroniser_sondages(), 1)      # intervalle écoulé
        self.assertIn(groupe, u[self.champ])

    def test_synchro_intervalle_minimum(self):
        sondage, _groupe, _question = self._sondage_presentiel()
        with self.assertRaises(ValidationError):
            sondage.write({"rlq_synchro_active": True, "rlq_synchro_minutes": 1})

    def test_bouton_met_aussi_a_jour_les_etiquettes(self):
        sondage, groupe, question = self._sondage_presentiel()
        u = self._utilisateur("Jules")
        self._repondre(sondage, question, u.partner_id, question.suggested_answer_ids[0])
        groupe.rlq_category_id.unlink()                                                # étiquette supprimée à la main : à recréer
        sondage.action_rlq_appliquer_groupes_participants()
        self.assertTrue(groupe.rlq_category_id)
        self.assertIn(groupe.rlq_category_id, u.partner_id.category_id)
        self.assertIn("1", sondage.rlq_synchro_resultat)

    # ---- v1.108.0 : tâche planifiée active seulement si une case est cochée ; intervalle par défaut ; sommaire (NON EXÉCUTÉS) ----
    def test_cron_active_seulement_si_une_case_est_cochee(self):
        cron = self.env.ref("rlq_survey_report.ir_cron_synchro_sondages")
        self.env["event.event"].search([("rlq_synchro_active", "=", True)]).write({"rlq_synchro_active": False})
        self.env["survey.survey"].search([("rlq_synchro_active", "=", True)]).write({"rlq_synchro_active": False})
        self.assertFalse(cron.active)
        self.evenement.write({"rlq_synchro_active": True})
        self.assertTrue(cron.active)
        self.evenement.write({"rlq_synchro_active": False})
        self.assertFalse(cron.active)

    def test_intervalle_par_defaut_parametre_systeme(self):
        parametres = self.env["ir.config_parameter"].sudo()
        parametres.set_param("rlq_survey_report.synchro_minutes_defaut", "30")
        self.assertEqual(self.env["survey.survey"].default_get(["rlq_synchro_minutes"])["rlq_synchro_minutes"], 30)
        parametres.set_param("rlq_survey_report.synchro_minutes_defaut", "2")                  # sous le minimum : ramené à 5
        self.assertEqual(self.env["event.event"].default_get(["rlq_synchro_minutes"])["rlq_synchro_minutes"], 5)
        parametres.set_param("rlq_survey_report.synchro_minutes_defaut", "abc")                # invalide : 15
        self.assertEqual(self.env["survey.survey"].default_get(["rlq_synchro_minutes"])["rlq_synchro_minutes"], 15)

    def test_sommaire_dit_si_la_tache_est_desactivee(self):
        self.env["event.event"].search([("rlq_synchro_active", "=", True)]).write({"rlq_synchro_active": False})
        self.env["survey.survey"].search([("rlq_synchro_active", "=", True)]).write({"rlq_synchro_active": False})
        texte = self.env["rlq.synchro.sommaire"].default_get(["resume"])["resume"]
        self.assertIn("DÉSACTIVÉE", str(texte))
        self.evenement.write({"rlq_synchro_active": True})
        texte = self.env["rlq.synchro.sommaire"].default_get(["resume"])["resume"]
        self.assertIn("ACTIVE, toutes les", str(texte))
        self.assertIn(self.evenement.name, str(texte))

    # ---- v1.107.0 : synchronisation périodique des événements (NON EXÉCUTÉ) ----
    def test_synchro_periodique_evenement_intervalle_et_fin(self):
        evenement = self.evenement
        u = self._utilisateur("Karim")
        self._inscription(u.partner_id, "Visiteur")
        u.write({self.champ: [(3, self.billets["Visiteur"].rlq_group_id.id)]})
        modele = self.env["event.event"]
        self.assertEqual(modele._cron_rlq_synchroniser_evenements(), 0)                       # non cochée : rien
        evenement.write({"rlq_synchro_active": True, "rlq_synchro_minutes": 15})
        self.assertEqual(modele._cron_rlq_synchroniser_evenements(), 1)
        self.assertTrue(self._dans_groupe(u, "Visiteur"))
        self.assertEqual(modele._cron_rlq_synchroniser_evenements(), 0)                       # intervalle pas écoulé
        evenement.write({"rlq_synchro_derniere": fields.Datetime.now() - timedelta(minutes=16), "date_end": fields.Datetime.now() - timedelta(days=2)})
        self.assertEqual(modele._cron_rlq_synchroniser_evenements(), 0)                       # terminé depuis plus d'un jour : arrêt automatique
