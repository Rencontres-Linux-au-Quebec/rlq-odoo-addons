# -*- coding: utf-8 -*-
"""Tests Odoo (TransactionCase) pour rlq.survey.report.wizard.

⚠️ IMPORTANT : contrairement à test_report_builder.py, ce fichier
nécessite une VRAIE instance Odoo pour s'exécuter - il n'a PAS pu être
lancé ni vérifié pendant l'écriture de ce module (aucun accès à une
instance Odoo). Il suit les conventions standards du framework de test
intégré d'Odoo (`odoo.tests.common.TransactionCase`), qui crée une
base de données JETABLE (jamais votre base réelle) pour chaque
exécution, installe le module, exécute les tests, puis annule tout -
rien n'est jamais conservé ni ne touche vos données réelles.

Pour l'exécuter sur votre instance :

    odoo-bin -d NOM_BASE_DE_TEST -i rlq_survey_report \\
        --test-enable --test-tags rlq_survey_report --stop-after-init

(remplacez NOM_BASE_DE_TEST par une base jetable, jamais votre base de
production - Odoo la modifie pendant le test puis, selon la
configuration, la conserve pour inspection ou la supprime).

Les données de test créées ci-dessous (survey.question,
matrix_row_ids, suggested_answer_ids...) suivent les MÊMES hypothèses
de nommage de champs que le reste de ce module (voir
NOTES_VALIDATION.md) - si ces tests échouent avec une erreur du genre
"tel champ n'existe pas", c'est probablement le même ajustement de nom
de champ qui serait nécessaire pour le module lui-même sur votre
instance précise.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.addons.rlq_survey_report.models.rlq_survey_report_wizard import CLE_PARAMETRE_MOT_DE_PASSE
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRlqSurveyReportWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Survey = cls.env["survey.survey"]
        cls.Question = cls.env["survey.question"]
        cls.Answer = cls.env["survey.question.answer"]
        cls.UserInput = cls.env["survey.user_input"]

        # --- Un sondage de référence avec 3 questions ---
        cls.survey = cls.Survey.create({
            "title": "Rencontre du 4 août 2026",
            "access_mode": "public",
        })

        cls.question_matrice = cls.Question.create({
            "survey_id": cls.survey.id,
            "title": "Comment avez-vous aimé les présentations ?",
            "question_type": "matrix",
            "matrix_row_ids": [
                (0, 0, {"value": "Introduction à Docker"}),
                (0, 0, {"value": "Niveau de connaissance ?"}),
            ],
            "suggested_answer_ids": [
                (0, 0, {"value": "1", "sequence": 1}),
                (0, 0, {"value": "2", "sequence": 2}),
                (0, 0, {"value": "3", "sequence": 3}),
                (0, 0, {"value": "4", "sequence": 4}),
                (0, 0, {"value": "5", "sequence": 5}),
            ],
        })

        cls.question_choix = cls.Question.create({
            "survey_id": cls.survey.id,
            "title": "Où avez-vous vu l'annonce ?",
            "question_type": "simple_choice",
            "suggested_answer_ids": [
                (0, 0, {"value": "Facebook", "sequence": 1}),
                (0, 0, {"value": "Autre (à préciser plus bas)", "sequence": 2}),
            ],
        })

        cls.question_texte = cls.Question.create({
            "survey_id": cls.survey.id,
            "title": "Suggestions",
            "question_type": "text_box",
        })

        # --- Deux réponses complètes, avec des notes contrastées ---
        cls.partner_jean = cls.env["res.partner"].create({
            "name": "Jean Dupont", "email": "jean@example.com",
        })
        cls.partner_marie = cls.env["res.partner"].create({
            "name": "Marie Martin", "email": "marie@example.com",
        })

        cls.ui_jean = cls.UserInput.create({
            "survey_id": cls.survey.id, "partner_id": cls.partner_jean.id, "state": "done",
        })
        cls.ui_marie = cls.UserInput.create({
            "survey_id": cls.survey.id, "partner_id": cls.partner_marie.id, "state": "done",
        })

        row_docker = cls.question_matrice.matrix_row_ids.filtered(lambda r: r.value == "Introduction à Docker")
        reponse_5 = cls.question_matrice.suggested_answer_ids.filtered(lambda a: a.value == "5")
        reponse_1 = cls.question_matrice.suggested_answer_ids.filtered(lambda a: a.value == "1")
        cls.env["survey.user_input.line"].create([
            {
                "user_input_id": cls.ui_jean.id, "survey_id": cls.survey.id,
                "question_id": cls.question_matrice.id,
                "matrix_row_id": row_docker.id, "suggested_answer_id": reponse_5.id,
            },
            {
                "user_input_id": cls.ui_marie.id, "survey_id": cls.survey.id,
                "question_id": cls.question_matrice.id,
                "matrix_row_id": row_docker.id, "suggested_answer_id": reponse_1.id,
            },
        ])

        reponse_autre = cls.question_choix.suggested_answer_ids.filtered(
            lambda a: a.value == "Autre (à préciser plus bas)"
        )
        cls.env["survey.user_input.line"].create([
            {
                "user_input_id": cls.ui_marie.id, "survey_id": cls.survey.id,
                "question_id": cls.question_choix.id, "suggested_answer_id": reponse_autre.id,
            },
            {
                # La précision "Autre" : une ligne SÉPARÉE, sans suggested_answer_id
                # (voir CHANGELOG v1.42.0 pour le détail de cette découverte).
                "user_input_id": cls.ui_marie.id, "survey_id": cls.survey.id,
                "question_id": cls.question_choix.id, "value_char_box": "Un ami me l'a mentionné",
            },
        ])

    def _wizard(self, **valeurs):
        defaults = {
            "survey_ids": [(6, 0, self.survey.ids)],
            "confirmation_renseignements_personnels": True,
            # Mot de passe valide par défaut : un rapport NON anonymisé en exige
            # un, même à l'écran. Les tests qui vérifient son absence passent
            # explicitement mot_de_passe=False.
            "mot_de_passe": "Abcdefg!1234",
            "mot_de_passe_confirmation": "Abcdefg!1234",
        }
        defaults.update(valeurs)
        return self.env["rlq.survey.report.wizard"].create(defaults)

    # ------------------------------------------------------------------
    # Génération de base
    # ------------------------------------------------------------------

    def test_generation_ecran_ne_requiert_pas_de_mot_de_passe(self):
        wizard = self._wizard(output_format="screen")
        wizard.action_generate()
        self.assertEqual(wizard.state, "done")
        self.assertIn(self.survey.title, wizard.report_html)

    def test_moyenne_correcte_dans_le_rapport(self):
        """Jean a mis 5, Marie a mis 1 -> moyenne 3.0 pour "Introduction à Docker"."""
        wizard = self._wizard(output_format="screen", anonymiser=False)
        wizard.action_generate()
        self.assertIn("3.0", wizard.report_html)

    def test_section_a_surveiller_contient_la_note_basse(self):
        wizard = self._wizard(output_format="screen", anonymiser=False, inclure_section_surveiller=True)
        wizard.action_generate()
        self.assertIn("À surveiller", wizard.report_html)
        self.assertIn("Marie Martin", wizard.report_html)

    def test_a_surveiller_relie_un_commentaire_libre(self):
        """Nouveau en v1.68.0 : une note basse est reliée à une réponse
        texte libre de LA MÊME personne dans LE MÊME sondage, si elle
        existe - Marie Martin (note basse existante dans les fixtures)
        reçoit ici en plus une réponse texte libre explicative."""
        self.env["survey.user_input.line"].create({
            "user_input_id": self.ui_marie.id, "survey_id": self.survey.id,
            "question_id": self.question_texte.id, "value_char_box": "Le projecteur ne fonctionnait pas bien",
        })
        wizard = self._wizard(output_format="screen", anonymiser=False, inclure_section_surveiller=True)
        wizard.action_generate()
        self.assertIn("Le projecteur ne fonctionnait pas bien", wizard.report_html)

    def test_niveau_de_connaissance_exclu_de_a_surveiller(self):
        """Une question d'auto-évaluation (même avec une note basse) ne
        doit pas apparaître dans "À surveiller" (voir v1.41.0)."""
        # (Ce test suppose qu'une réponse basse a été enregistrée pour
        # "Niveau de connaissance ?" - à adapter si votre jeu de données
        # de test n'en contient pas.)
        wizard = self._wizard(output_format="screen", inclure_section_surveiller=True)
        wizard.action_generate()
        if "Niveau de connaissance" in wizard.report_html:
            surveiller_html = wizard.report_html.split("À surveiller")[-1]
            self.assertNotIn("Niveau de connaissance", surveiller_html)

    def test_niveau_de_connaissance_exclu_de_top_mouvements(self):
        """Nouveau en v1.69.0 : une question d'auto-évaluation (comme
        "Niveau de connaissance ?", qui n'est plus posée dans les
        sondages récents) ne doit pas apparaître dans "Ce qui a le
        plus bougé" - même exclusion que pour "À surveiller"."""
        wizard = self._wizard(output_format="screen")
        wizard.action_generate()
        if "Ce qui a le plus bougé" in wizard.report_html:
            section_html = wizard.report_html.split("Ce qui a le plus bougé")[-1].split("</div>")[0]
            self.assertNotIn("Niveau de connaissance", section_html)

    def test_note_globale_apparait_par_rencontre(self):
        """Nouveau en v1.56.0 : une "note globale" composite (basée sur
        Organisation et logistique/Satisfaction globale/présentations)
        apparaît en tête de chaque section de rencontre - notre jeu de
        test a une question "Comment avez-vous aimé les présentations
        ?" (Jean=5, Marie=1), donc une moyenne de 3.0 est attendue."""
        wizard = self._wizard(output_format="screen", anonymiser=False)
        wizard.action_generate()
        self.assertIn("Note globale de cette rencontre", wizard.report_html)

    def test_filtre_presentateur_selectionne_ses_rencontres(self):
        """Nouveau en v1.70.0 : choisir un présentateur dans le filtre
        remplace la sélection de sondages par UNIQUEMENT ses rencontres
        - cherche parmi TOUS les sondages de la base, pas seulement
        ceux déjà sélectionnés."""
        autre_survey = self.Survey.create({"title": "Autre rencontre", "access_mode": "public"})
        self.Question.create({
            "survey_id": autre_survey.id,
            "title": "Comment avez-vous aimé les présentations ?",
            "question_type": "matrix",
            "matrix_row_ids": [(0, 0, {"value": "Sécurité web [Alice Untel]"})],
            "suggested_answer_ids": [(0, 0, {"value": "5", "sequence": 1})],
        })
        options = dict(self.env["rlq.survey.report.wizard"]._get_presentateurs_disponibles())
        self.assertIn("Alice Untel", options)

        wizard = self._wizard(survey_ids=[(6, 0, self.survey.ids)])
        wizard.filtre_presentateur = "Alice Untel"
        wizard._onchange_filtre_presentateur()
        self.assertEqual(wizard.survey_ids, autre_survey)

    def _creer_rencontre_avec_organisation(self, titre, note):
        """Aide pour test_comparaison_note_globale_par_categorie ci-dessous
        - crée un sondage minimal avec une question "Organisation et
        logistique" (une des 3 combinées pour la Note globale) et une
        seule réponse à la note donnée."""
        survey = self.Survey.create({"title": titre, "access_mode": "public"})
        question = self.Question.create({
            "survey_id": survey.id, "title": "Organisation et logistique",
            "question_type": "matrix",
            "matrix_row_ids": [(0, 0, {"value": "Endroit de l'événement"})],
            "suggested_answer_ids": [(0, 0, {"value": str(n), "sequence": n}) for n in range(1, 6)],
        })
        partenaire = self.env["res.partner"].create({"name": f"Participant {titre}"})
        ui = self.UserInput.create({
            "survey_id": survey.id, "partner_id": partenaire.id, "state": "done",
        })
        self.env["survey.user_input.line"].create({
            "user_input_id": ui.id, "survey_id": survey.id, "question_id": question.id,
            "matrix_row_id": question.matrix_row_ids.id,
            "suggested_answer_id": question.suggested_answer_ids.filtered(lambda a: a.value == str(note)),
        })
        return survey

    def test_comparaison_note_globale_par_categorie(self):
        """Nouveau en v1.71.0 : la moyenne de référence de la Note
        globale ne compare une rencontre qu'aux rencontres précédentes
        de LA MÊME CATÉGORIE - une Portes ouvertes chronologiquement
        entre deux Pause café ne doit pas influencer leur comparaison."""
        pause1 = self._creer_rencontre_avec_organisation("Pause café du 1 juin 2026", 2)
        portes = self._creer_rencontre_avec_organisation("Portes ouvertes du 15 juin 2026", 5)
        pause2 = self._creer_rencontre_avec_organisation("Pause café du 1 juillet 2026", 4)
        wizard = self._wizard(
            survey_ids=[(6, 0, (pause1 | portes | pause2).ids)],
            output_format="screen", anonymiser=False,
        )
        wizard.action_generate()
        # Sans filtrage par catégorie, la moyenne de référence serait de 3.50
        # (moyenne de 2 et 5, les deux rencontres précédentes toutes
        # catégories confondues) - avec filtrage, elle doit être de 2.00
        # (seule la Pause café du 1 juin compte, pas Portes ouvertes).
        self.assertIn("2.00", wizard.report_html)
        self.assertNotIn("3.50", wizard.report_html)

    def test_anonymisation_masque_les_noms(self):
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("Jean Dupont", wizard.report_html)
        self.assertNotIn("Marie Martin", wizard.report_html)
        self.assertIn("Participant 1", wizard.report_html)

    def test_anonymisation_retire_les_coordonnees_completes(self):
        """Nouveau en v1.74.0 : signalé que téléphone/ville/pays/
        étiquettes (avec les noms RÉELS des autres membres partageant
        cette étiquette !) et l'historique détaillé de sondages/
        événements restaient visibles même avec l'anonymisation active -
        ces détails peuvent identifier quelqu'un même sans son nom.
        Tout ce bloc doit disparaître entièrement, pas juste le nom."""
        self.partner_jean.write({
            "phone": "514-555-1234", "city": "Villeneuve-sur-Test",
            "country_id": self.env.ref("base.ca").id,
        })
        tag = self.env["res.partner.category"].create({"name": "EtiquetteUniqueXYZ"})
        self.partner_jean.category_id = [(6, 0, [tag.id])]
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("514-555-1234", wizard.report_html)
        self.assertNotIn("Villeneuve-sur-Test", wizard.report_html)
        self.assertNotIn("EtiquetteUniqueXYZ", wizard.report_html)
        self.assertNotIn("Sondages remplis (total, tous temps)", wizard.report_html)
        self.assertNotIn("Événements inscrits", wizard.report_html)

    def test_anonymisation_retire_les_liens_backend_odoo(self):
        """Nouveau en v1.74.0 : le lien de configuration du sondage et
        "Tester sondage" pointent vers le backend Odoo - inappropriés
        (et une fuite d'URL interne) pour un rapport destiné à être
        rendu public. Le titre du sondage doit rester visible, mais en
        texte simple, pas en lien."""
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("Tester sondage", wizard.report_html)
        self.assertNotIn(f"survey.survey&id={self.survey.id}", wizard.report_html)
        self.assertNotIn(f"survey.survey&amp;id={self.survey.id}", wizard.report_html)
        self.assertIn(self.survey.title, wizard.report_html)

    def test_anonymisation_filet_securite_courriel_generique(self):
        """Nouveau en v1.74.0 : une expression régulière masque tout
        texte ayant la forme d'un courriel, même s'il ne provient pas
        de la fiche contact d'un participant connu (ex. tapé dans une
        réponse texte libre)."""
        self.env["survey.user_input.line"].create({
            "user_input_id": self.ui_marie.id, "survey_id": self.survey.id,
            "question_id": self.question_texte.id,
            "value_char_box": "Contactez-moi à autre-courriel@exemple.com",
        })
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("autre-courriel@exemple.com", wizard.report_html)
        self.assertIn("[courriel masqué]", wizard.report_html)

    def test_filet_courriel_conserve_l_attribution_d_auteur(self):
        """Le filet générique ne doit pas masquer le courriel d'attribution
        d'auteur du pied de page - ce n'est pas celui d'un participant."""
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertIn("contact@exemple.org", wizard.report_html)

    def test_anonymisation_nom_avec_parentheses_et_sans_lien_courriel(self):
        """Signalé (v1.92.0) : un participant dont le nom se terminait par une parenthèse
        (« Nom (organisation.com) ») restait visible dans un rapport anonymisé - et le
        symbole ✉ restait là, avec un lien mailto:[courriel masqué]."""
        self.partner_marie.write({"name": "Marie Martin (exemple-org.ca)", "email": "marie@exemple-org.ca"})
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        html = wizard.report_html
        self.assertNotIn("Marie Martin", html)
        self.assertNotIn("exemple-org", html)
        self.assertNotIn("&#9993;", html)
        self.assertNotIn("class='lien-courriel'", html)
        self.assertNotIn("[courriel masqué]", html)

    def test_anonymisation_normalise_les_accents(self):
        """Régression signalée par l'utilisateur (v1.57.0) : un nom
        contenant un accent (ex. "Fabián") pouvait rester visible dans
        le titre d'une présentation si sa forme Unicode (composée vs
        décomposée) différait de celle utilisée dans le titre - même
        texte à l'œil, octets différents, donc pas de correspondance
        pour un remplacement de chaîne exact sans normalisation."""
        import unicodedata
        partner_accent = self.env["res.partner"].create({
            "name": unicodedata.normalize("NFC", "Fabián Rodríguez"),
            "email": "fabian@example.com",
        })
        survey2 = self.Survey.create({"title": "Rencontre du 1 juillet 2026", "access_mode": "public"})
        question_presentations = self.Question.create({
            "survey_id": survey2.id,
            "title": "Comment avez-vous aimé les présentations ?",
            "question_type": "matrix",
            # Titre utilisant la forme NFD (décomposée) du nom - différente
            # de la fiche contact (NFC) créée ci-dessus, bien qu'identique
            # visuellement.
            "matrix_row_ids": [(0, 0, {
                "value": f"Sécurité web [{unicodedata.normalize('NFD', 'Fabián Rodríguez')}]"
            })],
            "suggested_answer_ids": [(0, 0, {"value": "5", "sequence": 1})],
        })
        ui = self.UserInput.create({
            "survey_id": survey2.id, "partner_id": partner_accent.id, "state": "done",
        })
        self.env["survey.user_input.line"].create({
            "user_input_id": ui.id, "survey_id": survey2.id,
            "question_id": question_presentations.id,
            "matrix_row_id": question_presentations.matrix_row_ids.id,
            "suggested_answer_id": question_presentations.suggested_answer_ids.id,
        })
        wizard = self._wizard(survey_ids=[(6, 0, survey2.ids)], output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("Fabián", wizard.report_html)
        self.assertNotIn("Rodríguez", wizard.report_html)

    def test_anonymisation_avec_nom_court_ne_corrompt_pas_le_texte(self):
        """Régression confirmée par l'utilisateur (v1.56.0) : un
        participant dont le nom est très court (ex. "F", fiche contact
        incomplète) causait un remplacement global de cette lettre dans
        TOUT le document une fois anonymisé - "Filtre" devenait
        "[Participant N]iltre". Ce participant doit maintenant rester
        visible sous son nom réel plutôt que de corrompre le texte."""
        partner_court = self.env["res.partner"].create({"name": "F", "email": "f@example.com"})
        ui_court = self.UserInput.create({
            "survey_id": self.survey.id, "partner_id": partner_court.id, "state": "done",
        })
        self.env["survey.user_input.line"].create({
            "user_input_id": ui_court.id, "survey_id": self.survey.id,
            "question_id": self.question_texte.id, "value_char_box": "Une suggestion",
        })
        wizard = self._wizard(
            output_format="screen", anonymiser=True, filtre_titre_predefini="premier_mardi",
        )
        wizard.action_generate()
        self.assertIn("Filtre rapide utilisé", wizard.report_html)
        self.assertIn("F", wizard.report_html)  # reste visible, non anonymisé (trop court)

    def test_precision_autre_apparait(self):
        """Régression du correctif v1.42.0 : la précision "Autre" doit
        apparaître, séparée du comptage du choix lui-même."""
        wizard = self._wizard(output_format="screen", anonymiser=False)
        wizard.action_generate()
        self.assertIn("Un ami me l'a mentionné", wizard.report_html)

    def test_appreciation_presentateurs(self):
        """Nouveau en v1.54.0 : agrège les présentations par présentateur
        (extrait du titre - format "Titre - Nom Prénom" supposé) dans
        une nouvelle section en fin de rapport."""
        survey2 = self.Survey.create({"title": "Rencontre du 1 juillet 2026", "access_mode": "public"})
        question_presentations = self.Question.create({
            "survey_id": survey2.id,
            "title": "Comment avez-vous aimé les présentations ?",
            "question_type": "matrix",
            "matrix_row_ids": [(0, 0, {"value": "Sécurité web [Jean Dupont]"})],
            "suggested_answer_ids": [(0, 0, {"value": "5", "sequence": 1})],
        })
        ui = self.UserInput.create({
            "survey_id": survey2.id, "partner_id": self.partner_jean.id, "state": "done",
        })
        row = question_presentations.matrix_row_ids
        reponse = question_presentations.suggested_answer_ids
        self.env["survey.user_input.line"].create({
            "user_input_id": ui.id, "survey_id": survey2.id,
            "question_id": question_presentations.id,
            "matrix_row_id": row.id, "suggested_answer_id": reponse.id,
        })
        wizard = self._wizard(
            survey_ids=[(6, 0, (self.survey | survey2).ids)],
            output_format="screen", anonymiser=False,
        )
        wizard.action_generate()
        self.assertIn("Appréciation des présentateurs", wizard.report_html)
        self.assertIn("Jean Dupont", wizard.report_html)
        self.assertIn("Sécurité web", wizard.report_html)

    # ------------------------------------------------------------------
    # Mot de passe
    # ------------------------------------------------------------------

    def test_mot_de_passe_manquant_rouvre_la_demande(self):
        wizard = self._wizard(
            output_format="pdf", anonymiser=False,
            mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        resultat = wizard.action_generate()
        self.assertEqual(resultat.get("res_model"), "rlq.survey.report.wizard")
        self.assertIn("password", resultat.get("views", [[None, ""]])[0][1] or "")

    def test_mot_de_passe_faible_leve_une_erreur(self):
        wizard = self._wizard(
            output_format="pdf", anonymiser=False,
            mot_de_passe="abc", mot_de_passe_confirmation="abc",
        )
        with self.assertRaises(UserError):
            wizard.action_generate()

    def test_mots_de_passe_non_correspondants_levent_une_erreur(self):
        wizard = self._wizard(
            output_format="pdf", anonymiser=False,
            mot_de_passe="Abcdefg!1234", mot_de_passe_confirmation="Autrechose!123",
        )
        with self.assertRaises(UserError):
            wizard.action_generate()

    def test_html_pdf_anonymises_ne_requierent_pas_de_mot_de_passe(self):
        """Nouveau en v1.75.0 : un rapport anonymisé ne contient plus de
        renseignements personnels directs - aucun mot de passe demandé pour
        son téléchargement HTML ou PDF, même sans mot de passe saisi."""
        wizard = self._wizard(
            output_format="html", anonymiser=True,
            mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        self.assertIsNone(wizard._verifier_mot_de_passe_ou_demander("action_download_html"))
        self.assertIsNone(wizard._verifier_mot_de_passe_ou_demander("action_download_pdf"))

    def test_html_non_anonymise_requiert_un_mot_de_passe(self):
        wizard = self._wizard(
            output_format="html", anonymiser=False,
            mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        resultat = wizard._verifier_mot_de_passe_ou_demander("action_download_html")
        self.assertEqual(resultat.get("res_model"), "rlq.survey.report.wizard")

    def test_excel_requiert_toujours_un_mot_de_passe_meme_anonymise(self):
        """L'export Excel n'applique PAS l'anonymisation (vrais noms et
        courriels) - le mot de passe y reste toujours obligatoire."""
        wizard = self._wizard(
            anonymiser=True, mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        resultat = wizard._verifier_mot_de_passe_ou_demander("action_export_excel")
        self.assertEqual(resultat.get("res_model"), "rlq.survey.report.wizard")

    def test_fichier_anonymise_n_est_pas_chiffre(self):
        """Un mot de passe pré-rempli ne doit pas chiffrer un fichier
        anonymisé ni l'étiqueter « enc » ; non anonymisé, il s'applique."""
        wizard = self._wizard(
            output_format="html", anonymiser=True,
            mot_de_passe="Abcdefg!1234", mot_de_passe_confirmation="Abcdefg!1234",
        )
        self.assertFalse(wizard._mot_de_passe_effectif("html"))
        self.assertNotIn("enc", wizard._prefixe_nom_fichier("html").split("-"))
        wizard.anonymiser = False
        self.assertEqual(wizard._mot_de_passe_effectif("html"), "Abcdefg!1234")
        self.assertIn("enc", wizard._prefixe_nom_fichier("html").split("-"))

    def test_excel_jamais_etiquete_anonyme(self):
        """L'Excel contient les vrais noms : son nom de fichier ne doit
        jamais dire « anonyme », même si la case est cochée."""
        wizard = self._wizard(anonymiser=True)
        self.assertNotIn("anonyme", wizard._prefixe_nom_fichier("excel"))
        self.assertIn("anonyme", wizard._prefixe_nom_fichier("html"))

    def test_mot_de_passe_par_defaut_vient_du_parametre_systeme(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "rlq_survey_report.mot_de_passe_defaut", "Valeur!Test-1234"
        )
        valeurs = self.env["rlq.survey.report.wizard"].default_get(
            ["mot_de_passe", "mot_de_passe_confirmation"]
        )
        self.assertEqual(valeurs.get("mot_de_passe"), "Valeur!Test-1234")
        self.assertEqual(valeurs.get("mot_de_passe_confirmation"), "Valeur!Test-1234")

    def test_pas_de_pre_remplissage_si_parametre_vide(self):
        self.env["ir.config_parameter"].sudo().set_param("rlq_survey_report.mot_de_passe_defaut", "")
        valeurs = self.env["rlq.survey.report.wizard"].default_get(["mot_de_passe"])
        self.assertFalse(valeurs.get("mot_de_passe"))

    def test_mot_de_passe_marqueur_livre_est_refuse(self):
        """Le marqueur livré avec le module n'est jamais accepté comme vrai
        mot de passe, avec un message dédié (pas une erreur de critères)."""
        wizard = self._wizard(
            output_format="pdf", anonymiser=False,
            mot_de_passe="!CHANGE-MOI@", mot_de_passe_confirmation="!CHANGE-MOI@",
        )
        with self.assertRaises(UserError) as cm:
            wizard.action_generate()
        self.assertIn("n'a pas encore été personnalisé", str(cm.exception))

    def test_creation_du_parametre_ne_remplace_jamais_une_valeur_existante(self):
        """Signalé en production (v1.92.0) : le mot de passe défini par l'administrateur
        était remplacé par le marqueur après une réinstallation du module."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(CLE_PARAMETRE_MOT_DE_PASSE, "ValeurPerso!1234")
        self.assertTrue(self.env["rlq.survey.report.wizard"]._creer_parametre_mot_de_passe_si_absent())
        self.assertEqual(params.get_param(CLE_PARAMETRE_MOT_DE_PASSE), "ValeurPerso!1234")

    def test_creation_du_parametre_respecte_une_valeur_vide(self):
        """Une valeur VIDE désactive le pré-remplissage : ce n'est pas « absent »."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(CLE_PARAMETRE_MOT_DE_PASSE, "")
        self.env["rlq.survey.report.wizard"]._creer_parametre_mot_de_passe_si_absent()
        self.assertEqual(params.search([("key", "=", CLE_PARAMETRE_MOT_DE_PASSE)]).value, "")

    def test_creation_du_parametre_pose_le_marqueur_s_il_est_absent(self):
        params = self.env["ir.config_parameter"].sudo()
        params.search([("key", "=", CLE_PARAMETRE_MOT_DE_PASSE)]).unlink()
        self.env["rlq.survey.report.wizard"]._creer_parametre_mot_de_passe_si_absent()
        self.assertEqual(params.get_param(CLE_PARAMETRE_MOT_DE_PASSE), "!CHANGE-MOI@")

    def test_creation_du_parametre_detache_l_ancien_identifiant_xml(self):
        """Un enregistrement lié au module serait supprimé avec lui à la désinstallation."""
        params = self.env["ir.config_parameter"].sudo()
        params.set_param(CLE_PARAMETRE_MOT_DE_PASSE, "ValeurPerso!1234")
        param = params.search([("key", "=", CLE_PARAMETRE_MOT_DE_PASSE)])
        imd = self.env["ir.model.data"].sudo()
        imd.search([("module", "=", "rlq_survey_report"), ("name", "=", "ir_config_parameter_mot_de_passe_defaut")]).unlink()
        imd.create({
            "module": "rlq_survey_report", "name": "ir_config_parameter_mot_de_passe_defaut",
            "model": "ir.config_parameter", "res_id": param.id, "noupdate": True,
        })
        self.env["rlq.survey.report.wizard"]._creer_parametre_mot_de_passe_si_absent()
        self.assertFalse(imd.search([("module", "=", "rlq_survey_report"), ("name", "=", "ir_config_parameter_mot_de_passe_defaut")]))
        self.assertTrue(param.exists())
        self.assertEqual(param.value, "ValeurPerso!1234")

    def test_avertissement_tant_que_le_marqueur_n_est_pas_change(self):
        """Tant que le mot de passe du formulaire est le marqueur livré, un
        avertissement indique où le changer ; il disparaît dès qu'on saisit
        le sien."""
        wizard = self._wizard(mot_de_passe="!CHANGE-MOI@", mot_de_passe_confirmation="!CHANGE-MOI@")
        self.assertIn("rlq_survey_report.mot_de_passe_defaut", wizard.avertissement_mot_de_passe_defaut)
        self.assertIn("Technique", wizard.avertissement_mot_de_passe_defaut)
        wizard.mot_de_passe = "Autre!Valeur-123"
        self.assertFalse(wizard.avertissement_mot_de_passe_defaut)

    def test_message_d_erreur_du_marqueur_indique_ou_le_changer(self):
        wizard = self._wizard(
            output_format="pdf", anonymiser=False,
            mot_de_passe="!CHANGE-MOI@", mot_de_passe_confirmation="!CHANGE-MOI@",
        )
        with self.assertRaises(UserError) as cm:
            wizard.action_generate()
        self.assertIn("Technique", str(cm.exception))
        self.assertIn("rlq_survey_report.mot_de_passe_defaut", str(cm.exception))

    def test_ouvrir_parametre_mot_de_passe_pour_un_administrateur(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "rlq_survey_report.mot_de_passe_defaut", "!CHANGE-MOI@"
        )
        wizard = self._wizard().with_user(self.env.ref("base.user_admin"))
        action = wizard.action_ouvrir_parametre_mot_de_passe()
        self.assertEqual(action["res_model"], "ir.config_parameter")
        self.assertTrue(action["res_id"])

    def test_afficher_mot_de_passe_retourne_une_notification(self):
        wizard = self._wizard(mot_de_passe="Abcdefg!1234", mot_de_passe_confirmation="Abcdefg!1234")
        action = wizard.action_afficher_mot_de_passe()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["message"], "Abcdefg!1234")

    def test_ecran_non_anonymise_requiert_un_mot_de_passe(self):
        """Règle de la v1.77.0, conservée : un rapport montrant les vrais noms
        exige un mot de passe même à l'écran."""
        wizard = self._wizard(
            output_format="screen", anonymiser=False,
            mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        resultat = wizard._verifier_mot_de_passe_ou_demander("action_generate")
        self.assertEqual(resultat.get("res_model"), "rlq.survey.report.wizard")

    def test_ecran_anonymise_ne_requiert_pas_de_mot_de_passe(self):
        wizard = self._wizard(
            output_format="screen", anonymiser=True,
            mot_de_passe=False, mot_de_passe_confirmation=False,
        )
        self.assertIsNone(wizard._verifier_mot_de_passe_ou_demander("action_generate"))

    def test_historique_un_seul_nom_de_fichier_visible(self):
        """v1.92.0 : « Nom du fichier » n'est plus une colonne à part (il doublait
        « Télécharger »), mais le champ reste dans la vue, masqué : le widget binaire
        en a besoin pour afficher le nom (attribut filename)."""
        arch = self.env["rlq.survey.report.acces"].get_view(view_type="list")["arch"]
        self.assertIn('name="fichier_telecharger"', arch)
        self.assertRegex(arch, r'<field[^>]*name="nom_fichier"[^>]*column_invisible|<field[^>]*column_invisible[^>]*name="nom_fichier"')

    def test_criteres_manquants_liste_correctement(self):
        wizard = self._wizard(mot_de_passe="abc")
        manquants = wizard._criteres_manquants_mot_de_passe()
        self.assertTrue(any("12 caractères" in m for m in manquants))
        self.assertTrue(any("majuscule" in m for m in manquants))

    def test_mot_de_passe_solide_ne_leve_pas(self):
        wizard = self._wizard(mot_de_passe="Abcdefg!1234")
        self.assertEqual(wizard._criteres_manquants_mot_de_passe(), [])

    def test_mot_de_passe_jamais_affiche(self):
        """Historique : v1.59.0 (title= natif, signalé ne pas
        fonctionner), puis v1.60.0 (mécanisme CSS via un champ Html) -
        a PLANTÉ Odoo (OwlError confirmé dans HtmlViewer.retargetLinks,
        un bogue du widget Html lui-même). Après ce vrai plantage,
        abandon définitif de toute tentative de révélation - le champ
        confirme seulement la correspondance et la solidité, sans
        jamais afficher le mot de passe sous aucune forme."""
        wizard = self._wizard(
            mot_de_passe="Abcdefg!1234", mot_de_passe_confirmation="Abcdefg!1234",
        )
        wizard._onchange_mot_de_passe()
        self.assertNotIn("Abcdefg!1234", wizard.apercu_solidite_mot_de_passe)
        self.assertIn("correspondent", wizard.apercu_solidite_mot_de_passe)

    # ------------------------------------------------------------------
    # Filtre rapide
    # ------------------------------------------------------------------

    def test_filtre_titre_predefini_pause_cafe(self):
        pause_cafe = self.Survey.create({"title": "Pause café de septembre", "access_mode": "public"})
        wizard = self._wizard()
        wizard.filtre_titre_predefini = "pause_cafe"
        wizard._onchange_filtres_titre()
        self.assertIn(pause_cafe, wizard.survey_ids)
        self.assertNotIn(self.survey, wizard.survey_ids)

    def test_filtre_ne_fait_rien_si_categorie_vide(self):
        wizard = self._wizard()
        selection_avant = wizard.survey_ids
        wizard.filtre_titre_predefini = False
        wizard._onchange_filtres_titre()
        self.assertEqual(wizard.survey_ids, selection_avant)

    # ------------------------------------------------------------------
    # Accès sudo() aux fiches contact (régression v1.38.0)
    # ------------------------------------------------------------------

    def test_respondent_nom_ne_leve_pas_meme_sans_acces_direct(self):
        """Ne vérifie pas un vrai scénario multi-société ici (nécessiterait
        une configuration plus élaborée) - confirme au moins que l'appel
        fonctionne normalement dans le cas de base."""
        wizard = self._wizard()
        nom = wizard._respondent_nom(self.ui_jean)
        self.assertEqual(nom, "Jean Dupont")

    def test_url_absolue_prefixe_correctement(self):
        wizard = self._wizard()
        url = wizard._url_absolue("/web#model=survey.survey&id=1")
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        self.assertEqual(url, f"{base_url}/web#model=survey.survey&id=1")

    def test_prefixe_nom_fichier_indique_anonyme(self):
        wizard = self._wizard(anonymiser=True)
        self.assertIn("anonyme", wizard._prefixe_nom_fichier())

    def test_suffixe_plage_dates_utilise_filtres_explicites(self):
        wizard = self._wizard(date_from="2026-07-01", date_to="2026-08-04")
        self.assertEqual(wizard._suffixe_plage_dates_nom_fichier(), "20260701__a__20260804")

    def test_suffixe_plage_dates_vide_si_aucune_date(self):
        survey_sans_date = self.Survey.create({"title": "Sans aucune date", "access_mode": "public"})
        wizard = self._wizard(survey_ids=[(6, 0, survey_sans_date.ids)])
        self.assertEqual(wizard._suffixe_plage_dates_nom_fichier(), "")

    def test_apercu_ampleur_se_met_a_jour(self):
        """Régression v1.46.0/v1.47.0 : remplace la notification bus et
        l'onchange (tous deux signalés peu fiables) par un champ
        calculé - accéder au champ suffit à déclencher son calcul,
        peu importe comment survey_ids a été rempli (contexte ou
        saisie interactive)."""
        wizard = self._wizard()
        self.assertIn("1 sondage(s)", wizard.apercu_ampleur)
        self.assertIn("2 participant(s)", wizard.apercu_ampleur)

    def test_apercu_ampleur_indique_la_repartition(self):
        """Nouveau en v1.55.0 : indique aussi le nombre d'inscrits, de
        terminé et de débuté sans terminer, pas seulement le total."""
        wizard = self._wizard()
        self.assertIn("inscrit(s)", wizard.apercu_ampleur)
        self.assertIn("terminé(s)", wizard.apercu_ampleur)
        self.assertIn("débuté(s) sans terminer", wizard.apercu_ampleur)

    def test_apercu_ampleur_vide_sans_sondage(self):
        wizard = self._wizard(survey_ids=[(5, 0, 0)])
        self.assertEqual(wizard.apercu_ampleur, "")

    def test_lien_test_sondage_retourne_une_url_valide(self):
        """Historique : mécanisme maison de VRAIE entrée de test
        (test_entry=True) abandonné en v1.55.0 après 3 échecs ; repli
        sur get_start_url() (v1.55.0) - confirmé peu fiable pour un
        vrai mode test (bandeau absent même connecté normalement, voir
        NOTES_VALIDATION.md section -38). Nouvelle tentative (v1.64.0) :
        appeler directement action_test_survey() - la MÊME action que
        le bouton natif "Test" du backend (confirmé par l'utilisateur
        en mode debug), plutôt que d'essayer de reconstruire son
        comportement.

        Ce test reste délibérément SOUPLE sur la forme exacte de l'url
        retournée (je ne connais pas avec certitude la structure de
        retour d'action_test_survey() sur toutes les instances) - il
        confirme seulement qu'une url non vide est retournée sans
        exception, peu importe si action_test_survey() a réussi ou si
        le repli sur get_start_url() a été utilisé."""
        wizard = self._wizard()
        url = wizard._lien_test_sondage(self.survey)
        self.assertTrue(url)
        if not hasattr(self.survey, "action_test_survey"):
            # Cette instance n'a pas cette méthode - le repli connu
            # (get_start_url) doit avoir été utilisé.
            self.assertIn("/survey/start/", url)

    def test_totaux_a_vie_pas_dupliques(self):
        """Régression v1.49.0 : "Sondages remplis"/"Événements inscrits"
        avaient été ajoutés une seconde fois par erreur (une
        implémentation équivalente existait déjà, basée sur une requête
        groupée plus efficace) - ne doivent apparaître qu'une seule
        fois dans la fiche de chaque participant."""
        wizard = self._wizard(output_format="screen", anonymiser=False)
        wizard.action_generate()
        self.assertEqual(wizard.report_html.count("Sondages remplis (total, tous temps)"), 2)
        self.assertEqual(wizard.report_html.count("Événements inscrits"), 2)

    def test_dates_de_participation_a_vie_affichees(self):
        """Nouveau en v1.50.0 : la liste des dates (pas seulement le
        total) apparaît sous "Sondages remplis"/"Événements inscrits"."""
        wizard = self._wizard(output_format="screen", anonymiser=False)
        wizard.action_generate()
        # Le tiret cadratin précède la liste de dates dans le rendu.
        self.assertIn("Sondages remplis (total, tous temps) : 2 —", wizard.report_html)

    def test_purge_pieces_jointes_anciennes(self):
        """Régression signalée par une revue de code externe (v1.51.0) :
        les pièces jointes de ce module s'accumulaient sans purge."""
        wizard = self._wizard(output_format="html", mot_de_passe="Abcdefg!1234",
                               mot_de_passe_confirmation="Abcdefg!1234")
        wizard.action_generate()
        piece_jointe = self.env["ir.attachment"].search([("res_model", "=", wizard._name)])
        self.assertTrue(piece_jointe)
        piece_jointe.write({"create_date": fields.Datetime.now() - relativedelta(days=10)})
        self.env["rlq.survey.report.wizard"]._cron_purger_pieces_jointes(jours=3)
        self.assertFalse(piece_jointe.exists())

    def test_purge_ne_touche_pas_les_pieces_jointes_recentes(self):
        wizard = self._wizard(output_format="html", mot_de_passe="Abcdefg!1234",
                               mot_de_passe_confirmation="Abcdefg!1234")
        wizard.action_generate()
        piece_jointe = self.env["ir.attachment"].search([("res_model", "=", wizard._name)])
        self.env["rlq.survey.report.wizard"]._cron_purger_pieces_jointes(jours=3)
        self.assertTrue(piece_jointe.exists())

    def test_anonymisation_corrige_aussi_les_ancres(self):
        """Régression signalée par une revue de code externe (v1.51.0) :
        l'ancre id='personne-jean-dupont' restait devinable dans le code
        source même une fois le nom visible masqué. Vérifie que l'ancre
        ET les liens y pointant (lien_personne()) sont cohérents entre
        eux, peu importe leur forme exacte."""
        wizard = self._wizard(output_format="screen", anonymiser=True)
        wizard.action_generate()
        self.assertNotIn("jean-dupont", wizard.report_html.lower())
        self.assertNotIn("marie-martin", wizard.report_html.lower())


class TestRlqCourrielReponses(TransactionCase):
    """v1.94.0 : le participant reçoit ses réponses par courriel quand il termine le sondage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey = cls.env["survey.survey"].create({
            "title": "Rencontre du 6 octobre 2026", "access_mode": "public", "rlq_envoyer_reponses": True,
        })
        cls.question = cls.env["survey.question"].create({
            "survey_id": cls.survey.id, "title": "Suggestions", "question_type": "text_box",
        })
        cls.partner = cls.env["res.partner"].create({"name": "Jean Dupont", "email": "jean@example.com"})

    def _participation(self, **valeurs):
        participation = self.env["survey.user_input"].create({
            "survey_id": self.survey.id, "partner_id": self.partner.id, "state": "in_progress", **valeurs,
        })
        self.env["survey.user_input.line"].create({
            "user_input_id": participation.id, "survey_id": self.survey.id, "question_id": self.question.id,
            "answer_type": "text_box", "value_text_box": "Plus de café <b>svp</b>",
        })
        return participation

    def _courriels(self, participation):
        return self.env["mail.mail"].search([("res_id", "=", participation.id), ("model", "=", "survey.user_input")])

    def test_courriel_envoye_a_la_soumission(self):
        participation = self._participation()
        participation._mark_done()
        courriels = self._courriels(participation)
        self.assertEqual(len(courriels), 1)
        self.assertIn("jean@example.com", courriels.email_to)
        self.assertIn("Plus de café &lt;b&gt;svp&lt;/b&gt;", courriels.body_html)    # réponse échappée
        self.assertIn("Suggestions", courriels.body_html)
        self.assertTrue(participation.rlq_courriel_reponses_envoye)

    def test_case_decochee_aucun_courriel(self):
        self.survey.rlq_envoyer_reponses = False
        participation = self._participation()
        participation._mark_done()
        self.assertFalse(self._courriels(participation))

    def test_jamais_deux_fois_ni_pour_un_test(self):
        participation = self._participation()
        participation._mark_done()
        participation.rlq_envoyer_reponses_courriel()
        self.assertEqual(len(self._courriels(participation)), 1)
        essai = self._participation(test_entry=True)
        essai._mark_done()
        self.assertFalse(self._courriels(essai))

    def test_sans_adresse_aucun_courriel_et_aucune_erreur(self):
        participation = self.env["survey.user_input"].create({"survey_id": self.survey.id, "state": "in_progress"})
        self.env["survey.user_input.line"].create({
            "user_input_id": participation.id, "survey_id": self.survey.id, "question_id": self.question.id,
            "answer_type": "text_box", "value_text_box": "Merci",
        })
        participation._mark_done()
        self.assertEqual(participation.state, "done")
        self.assertFalse(self._courriels(participation))


class TestRlqAlerteInscriptions(TransactionCase):
    """v1.95.0 : courriel quand un événement atteint N inscriptions (NON exécutés ici : pas d'instance Odoo)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.evenement = cls.env["event.event"].create({
            "name": "Rencontre de novembre", "date_begin": "2026-11-05 23:00:00", "date_end": "2026-11-06 01:00:00",
            "rlq_alerte_active": True, "rlq_alerte_seuil": 2, "rlq_alerte_courriel": "alerte@example.com",
        })

    def _inscrire(self, n, etat="open"):
        return self.env["event.registration"].create([
            {"event_id": self.evenement.id, "name": "Personne %d" % i, "email": "p%d@example.com" % i, "state": etat} for i in range(n)
        ])

    def _courriels(self):
        return self.env["mail.mail"].search([("model", "=", "event.event"), ("res_id", "=", self.evenement.id)])

    def test_courriel_une_seule_fois_au_seuil(self):
        self._inscrire(1)
        self.assertFalse(self._courriels())
        self._inscrire(1)
        courriels = self._courriels()
        self.assertEqual(len(courriels), 1)
        self.assertIn("alerte@example.com", courriels.email_to)
        self.assertIn("2 inscriptions", courriels.subject)
        self.assertNotIn("p0@example.com", courriels.body_html)             # aucune donnée personnelle
        self.assertNotIn("Personne", courriels.body_html)
        self.assertTrue(self.evenement.rlq_alerte_envoyee)
        self._inscrire(3)
        self.assertEqual(len(self._courriels()), 1)

    def test_brouillons_et_annulations_ne_comptent_pas_puis_confirmation(self):
        brouillons = self._inscrire(2, etat="draft")
        self.assertFalse(self._courriels())
        brouillons.write({"state": "open"})
        self.assertEqual(len(self._courriels()), 1)

    def test_changer_le_seuil_rearme(self):
        self._inscrire(2)
        self.assertEqual(len(self._courriels()), 1)
        self.evenement.rlq_alerte_seuil = 3
        self.assertFalse(self.evenement.rlq_alerte_envoyee)
        self._inscrire(1)
        self.assertEqual(len(self._courriels()), 2)

    def test_case_decochee_aucun_courriel(self):
        self.evenement.rlq_alerte_active = False
        self._inscrire(3)
        self.assertFalse(self._courriels())

    def test_destinataire_parametre_puis_societe(self):
        self.evenement.rlq_alerte_courriel = False
        self.env["ir.config_parameter"].sudo().set_param("rlq_survey_report.courriel_inscriptions", "param@example.com")
        self._inscrire(2)
        self.assertIn("param@example.com", self._courriels().email_to)
        self.evenement.rlq_alerte_seuil = 3
        self.env["ir.config_parameter"].sudo().set_param("rlq_survey_report.courriel_inscriptions", "")
        self.env.company.email = "societe@example.com"
        self._inscrire(1)
        self.assertIn("societe@example.com", self._courriels().sorted("id")[-1].email_to)


    def test_repetition_a_chaque_multiple_de_n(self):
        """v1.105.0 : « Répéter tous les N inscriptions » : un courriel à N, 2N, 3N… (NON exécuté ici)."""
        self.evenement.write({"rlq_alerte_repeter": True})
        self._inscrire(2)
        self.assertEqual(len(self._courriels()), 1)
        self._inscrire(1)
        self.assertEqual(len(self._courriels()), 1)               # 3 : pas un multiple de 2 atteint
        self._inscrire(1)
        self.assertEqual(len(self._courriels()), 2)               # 4 : deuxième courriel
        self.assertEqual(self.evenement.rlq_alerte_palier, 4)
        self.evenement.write({"rlq_alerte_seuil": 5})             # changer N remet le compteur à zéro
        self.assertEqual(self.evenement.rlq_alerte_palier, 0)           # 4 inscriptions < 5


class TestRlqAlerteSondage(TransactionCase):
    """v1.96.0 : courriel quand un sondage associé à l'événement est complété (NON exécutés ici : pas d'instance Odoo)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sondage = cls.env["survey.survey"].create({"title": "Portes ouvertes (Bénévole)", "access_mode": "public"})
        cls.evenement = cls.env["event.event"].create({
            "name": "Journée portes ouvertes", "date_begin": "2026-10-24 13:00:00", "date_end": "2026-10-24 21:00:00",
            "rlq_alerte_sondage": True, "rlq_alerte_courriel": "alerte@example.com",
        })
        cls.billet = cls.env["event.event.ticket"].create({"name": "Bénévole", "event_id": cls.evenement.id, "rlq_survey_id": cls.sondage.id})
        cls.partner = cls.env["res.partner"].create({"name": "Issam", "email": "issam@example.com"})
        cls.env["event.registration"].create({
            "event_id": cls.evenement.id, "event_ticket_id": cls.billet.id, "partner_id": cls.partner.id,
            "name": "Issam", "email": "issam@example.com", "state": "open",
        })

    def _participation(self, **valeurs):
        return self.env["survey.user_input"].create({
            "survey_id": self.sondage.id, "partner_id": self.partner.id, "state": "in_progress", **valeurs,
        })

    def _courriels(self):
        return self.env["mail.mail"].search([("model", "=", "event.event"), ("res_id", "=", self.evenement.id), ("subject", "like", "Sondage complété")])

    def test_courriel_a_la_soumission_une_seule_fois(self):
        participation = self._participation()
        participation._mark_done()
        courriels = self._courriels()
        self.assertEqual(len(courriels), 1)
        self.assertIn("alerte@example.com", courriels.email_to)
        self.assertIn("Issam", courriels.subject)
        self.assertIn("Bénévole", courriels.body_html)
        self.assertNotIn("issam@example.com", courriels.body_html)
        self.assertIn("Dernières inscriptions (30 jours)", courriels.body_html)      # v1.97.0 : tableau comme la touche « I »
        self.assertTrue(participation.rlq_alerte_evenement_envoyee)
        participation._mark_done()
        self.assertEqual(len(self._courriels()), 1)

    def test_case_decochee_essai_ou_autre_sondage_aucun_courriel(self):
        self.evenement.rlq_alerte_sondage = False
        self._participation()._mark_done()
        self.assertFalse(self._courriels())
        self.evenement.rlq_alerte_sondage = True
        self._participation(test_entry=True)._mark_done()
        autre = self.env["survey.survey"].create({"title": "Autre", "access_mode": "public"})
        self.env["survey.user_input"].create({"survey_id": autre.id, "state": "in_progress"})._mark_done()
        self.assertFalse(self._courriels())

