# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Tests unitaires pour report_builder.py - AUCUNE DÉPENDANCE À ODOO.

Ce fichier teste uniquement les fonctions pures de report_builder.py
(construction de chaînes HTML, calculs statistiques, échappement...),
qui ne touchent jamais à l'ORM (self.env, recordsets, etc.). Il peut
donc s'exécuter n'importe où avec un simple interpréteur Python, sans
avoir besoin d'une instance Odoo :

    cd rlq_survey_report/models && python3 -m unittest discover \\
        -s ../tests -p "test_report_builder.py" -v

Ou plus simplement, depuis la racine du module :

    PYTHONPATH=models python3 -m unittest tests.test_report_builder -v

Ces tests couvrent la logique la plus manipulée au fil des versions de
ce module (tooltips, sauts de page, anonymisation, statistiques) -
exactement les endroits où des régressions se sont déjà produites par
le passé (voir CHANGELOG.md). Ils ne remplacent PAS des tests Odoo
complets (voir test_wizard.py, qui nécessite une instance Odoo réelle
pour s'exécuter) - ils valident seulement que les briques de
construction HTML/statistiques elles-mêmes sont correctes, séparément
de leur intégration avec les données Sondage.
"""
import sys
import unittest
from pathlib import Path

try:
    # Cas d'exécution via Odoo (--test-enable) : le module est déjà
    # importé sous odoo.addons.rlq_survey_report.models.report_builder.
    from odoo.addons.rlq_survey_report.models import report_builder as rb
except ImportError:
    # Cas d'exécution autonome, sans Odoo du tout (voir docstring
    # ci-dessus) : ajoute models/ au chemin de recherche pour importer
    # report_builder.py directement.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "models"))
    import report_builder as rb  # noqa: E402


class TestNomGroupeBillet(unittest.TestCase):
    """v1.98.0 : nom du groupe Odoo des inscrits d'un type de billet."""
    def test_prefixe_et_billet(self):
        self.assertEqual(rb.nom_groupe_billet("JPOL26", "Bénévole"), "RLQ-JPOL26-Bénévole")
        self.assertEqual(rb.nom_groupe_billet("JPOL26", "Visiteur"), "RLQ-JPOL26-Visiteur")
        self.assertEqual(rb.nom_groupe_billet("JPOL26", "Commanditaire"), "RLQ-JPOL26-Commanditaire")

    def test_prefixe_rlq_jamais_double(self):
        self.assertEqual(rb.nom_groupe_billet("RLQ-JPOL26", "Visiteur"), "RLQ-JPOL26-Visiteur")
        self.assertEqual(rb.nom_groupe_billet("rlq jpol26", "Visiteur"), "RLQ-jpol26-Visiteur")
        self.assertEqual(rb.nom_groupe_rlq("JPOL26-Présentiel"), "RLQ-JPOL26-Présentiel")
        self.assertEqual(rb.nom_groupe_rlq("RLQ-JPOL26-Présentiel"), "RLQ-JPOL26-Présentiel")
        self.assertEqual(rb.nom_groupe_rlq("  Mon   groupe "), "RLQ-Mon groupe")
        self.assertEqual(rb.nom_groupe_rlq("RLQ-"), "")
        self.assertEqual(rb.nom_groupe_rlq(None), "")

    def test_espaces_et_tiret_final_nettoyes(self):
        self.assertEqual(rb.nom_groupe_billet("  JPOL26- ", "  Install   Linux "), "RLQ-JPOL26-Install Linux")

    def test_jamais_de_groupe_sans_nom_clair(self):
        self.assertEqual(rb.nom_groupe_billet("", "Visiteur"), "")
        self.assertEqual(rb.nom_groupe_billet("JPOL26", ""), "")
        self.assertEqual(rb.nom_groupe_billet("RLQ", "Visiteur"), "")
        self.assertEqual(rb.nom_groupe_billet(None, None), "")


class TestNormalisationEtSlug(unittest.TestCase):
    def test_normaliser_nom_insensible_accents_et_casse(self):
        self.assertEqual(rb.normaliser_nom("Éric BÉDARD"), rb.normaliser_nom("eric bedard"))

    def test_slug_convertit_accents_et_espaces(self):
        self.assertEqual(rb.slug("Fête de Noël"), "fete-de-noel")

    def test_slug_jamais_vide(self):
        self.assertEqual(rb.slug("!!!"), "section")


class TestJourSemaine(unittest.TestCase):
    def test_jour_semaine_connu(self):
        # Le 4 août 2026 est un mardi.
        self.assertEqual(rb.jour_semaine("2026-08-04"), "mardi")

    def test_jour_semaine_date_invalide_ne_leve_pas(self):
        self.assertIsNone(rb.jour_semaine("pas-une-date"))
        self.assertIsNone(rb.jour_semaine(None))


class TestEchappement(unittest.TestCase):
    def test_echapper_html(self):
        self.assertEqual(rb.echapper("<script>&\"'"), "&lt;script&gt;&amp;\"'")

    def test_echapper_attr_echappe_aussi_les_guillemets(self):
        self.assertIn("&quot;", rb.echapper_attr('Il a dit "bonjour"'))

    def test_echapper_none_ne_leve_pas(self):
        self.assertEqual(rb.echapper(None), "")

    def test_chiffres_gras_convertit_les_chiffres(self):
        resultat = rb.chiffres_gras("Il y a 5 questions")
        self.assertNotIn("5", resultat)
        self.assertIn("𝟓", resultat)


class TestConversionEtStatistiques(unittest.TestCase):
    def test_convertir_numerique_extrait_le_nombre(self):
        self.assertEqual(rb.convertir_numerique("5 =satisfait"), 5)
        self.assertEqual(rb.convertir_numerique("1 =débutant"), 1)

    def test_convertir_numerique_reponse_non_numerique(self):
        self.assertIsNone(rb.convertir_numerique("Je n'étais pas là"))

    def test_moyenne_simple(self):
        self.assertAlmostEqual(rb.moyenne([4, 5, 3]), 4.0)

    def test_moyenne_liste_vide(self):
        self.assertIsNone(rb.moyenne([]))

    def test_stats_description_champs_attendus(self):
        stats = rb.stats_description([1, 2, 3, 4, 5])
        for champ in ("min", "max", "moy", "ecart_type", "p95"):
            self.assertIn(champ, stats)
        self.assertEqual(stats["min"], 1)
        self.assertEqual(stats["max"], 5)

    def test_stats_description_liste_vide(self):
        self.assertIsNone(rb.stats_description([]))


class TestRetirerDivsParPrefixeClasse(unittest.TestCase):
    """Fonction critique pour le retrait des graphiques flex du PDF
    (v1.42.0) - une régression ici referait réapparaître les pages
    presque vides déjà signalées."""

    def test_retire_bloc_simple(self):
        html = "<p>avant</p><div class='evo-section'><div>x</div></div><p>après</p>"
        resultat = rb.retirer_divs_par_prefixe_classe(html, "evo-section")
        self.assertEqual(resultat, "<p>avant</p><p>après</p>")

    def test_gere_imbrication_profonde(self):
        stats = [("2026-08-04", "x1", 15, 12, 2, 300, 5), ("2026-07-01", "x2", 10, 8, 1, 250, 5)]
        evo_html = rb.section_evolution(stats)
        gabarit = f"<h2>Titre</h2>{evo_html}<h3>Suite</h3>"
        resultat = rb.retirer_divs_par_prefixe_classe(gabarit, "evo-section")
        self.assertNotIn("evo-section", resultat)
        self.assertIn("<h2>Titre</h2>", resultat)
        self.assertIn("<h3>Suite</h3>", resultat)

    def test_plusieurs_occurrences_consecutives(self):
        t1 = rb.section_tendance_question("Q1", {"2026-08-04": [4, 5], "2026-07-01": [3, 3]})
        t2 = rb.section_tendance_question("Q2", {"2026-08-04": [2, 2], "2026-07-01": [4, 4]})
        gabarit = f"<p>avant</p>{t1}<p>milieu</p>{t2}<p>après</p>"
        resultat = rb.retirer_divs_par_prefixe_classe(gabarit, "evo-serie")
        self.assertEqual(resultat, "<p>avant</p><p>milieu</p><p>après</p>")

    def test_aucune_occurrence_ne_change_rien(self):
        html = "<p>rien à voir ici</p>"
        self.assertEqual(rb.retirer_divs_par_prefixe_classe(html, "evo-section"), html)


class TestSectionMatriceColorerSeuils(unittest.TestCase):
    """v1.76.0 - la coloration par seuils de qualité (rouge/jaune/bleu/
    vert) de la barre "Note moyenne" peut être désactivée pour les
    questions d'auto-évaluation (ex. "Niveau de connaissance ?"), où
    une note basse ne signale pas un problème comme le ferait une note
    de satisfaction basse."""

    def test_colore_par_defaut(self):
        lignes = [{"item": "X", "valeurs": [2, 2], "detail": []}]
        html = rb.section_matrice("Q", lignes)
        self.assertIn("pct-rouge", html)

    def test_pas_de_coloration_si_desactivee(self):
        lignes = [{"item": "X", "valeurs": [2, 2], "detail": []}]
        html = rb.section_matrice("Niveau de connaissance ?", lignes, colorer_seuils=False)
        self.assertNotIn("pct-rouge", html)
        self.assertNotIn("pct-vert", html)
        self.assertNotIn("pct-bleu", html)
        self.assertNotIn("pct-jaune", html)
        # La barre et le % restent affichés, seule la couleur disparaît.
        self.assertIn("40%", html)


class TestTooltipDateSurItem(unittest.TestCase):
    """section_matrice() - couvre la régression de v1.35.0 à v1.43.0 :
    le tooltip de date doit être sur le NOM de l'item, pas sur la barre
    (qui garde son propre tooltip de moyenne, séparé)."""

    def test_tooltip_date_sur_le_nom_pas_sur_la_barre(self):
        lignes = [{"item": "Introduction à Docker", "valeurs": [4, 5], "detail": []}]
        html = rb.section_matrice(
            "Comment avez-vous aimé les présentations ?", lignes,
            dates_par_item={"Introduction à Docker": "2026-08-04"},
        )
        # Le nom de l'item porte le tooltip de date.
        avant_barre = html.split("<td>", 2)[1]
        self.assertIn("data-rlq-tip=\"Présenté le 2026-08-04", avant_barre)
        self.assertIn("Introduction à Docker", avant_barre)
        # La barre elle-même ne porte plus aucun tooltip (retiré en
        # v1.54.0 - l'information de moyenne est déjà visible via le
        # pourcentage affiché à côté).
        cellule_barre = html.split("barre-cadre")[1]
        self.assertNotIn("data-rlq-tip", cellule_barre.split("</div>")[0])

    def test_pas_de_tooltip_sans_date_connue(self):
        lignes = [{"item": "Sans date", "valeurs": [3, 4], "detail": []}]
        html = rb.section_matrice("Q", lignes)
        cellule_nom = html.split("<td>", 2)[1].split("</td>")[0]
        self.assertNotIn("a-tooltip", cellule_nom)

    def test_tooltip_date_fonctionne_sans_moyenne(self):
        lignes = [{"item": "Aucune valeur", "valeurs": [], "detail": []}]
        html = rb.section_matrice("Q", lignes, dates_par_item={"Aucune valeur": "2026-08-04"})
        self.assertIn("Présenté le", html)

    def test_colonne_detail_absente_sans_ventiler(self):
        lignes = [{"item": "X", "valeurs": [1, 2], "detail": [("1", 1, "Jean", "d")]}]
        html = rb.section_matrice("Q", lignes, ventiler=False)
        self.assertNotIn("detail-oui", html)

    def test_flèche_detail_presente_avec_ventiler(self):
        lignes = [{
            "item": "Salle", "valeurs": [4, 2, 5],
            "detail": [("4", 4, "Jean", "2026-08-04"), ("2", 2, "Marie", "2026-08-04"), ("5", 5, "Paul", "2026-08-04")],
        }]
        html = rb.section_matrice("Organisation et logistique", lignes, ventiler=True)
        self.assertIn("detail-oui", html)
        # Pas la variante "-inline" (position absolute), cause du bogue
        # de fenêtres superposées corrigé en v1.44.0.
        self.assertNotIn("detail-inline", html)

    def test_pas_de_tooltip_si_dates_par_item_absent(self):
        """Régression v1.49.0 : le wizard n'envoie plus dates_par_item du
        tout pour "Satisfaction globale" - section_matrice() elle-même
        n'a pas besoin de connaître ce nom de question, elle affiche
        simplement ce qu'on lui donne (ou pas)."""
        lignes = [{"item": "Note générale de l'événement", "valeurs": [4, 5], "detail": []}]
        html = rb.section_matrice("Satisfaction globale", lignes, dates_par_item=None)
        cellule_nom = html.split("<td>", 2)[1].split("</td>")[0]
        self.assertNotIn("a-tooltip", cellule_nom)


class TestRenduNombreAvecDetailNotes(unittest.TestCase):
    """v1.75.0 : toujours la liste dépliable cliquable, même pour une
    seule personne - avant, en dessous d'un seuil de personnes
    distinctes, un simple tooltip au survol (non cliquable) s'affichait
    à la place, empêchant d'accéder à la fiche de cette personne."""

    def test_sans_detail_retourne_le_nombre_simple(self):
        self.assertEqual(rb.rendu_nombre_avec_detail_notes(5, []), "5")

    def test_une_seule_personne_utilise_quand_meme_une_liste_depliable(self):
        detail = [("4", 4, "Jean", "2026-08-04")]
        resultat = rb.rendu_nombre_avec_detail_notes(1, detail)
        self.assertIn("<details class='detail-oui'>", resultat)
        self.assertNotIn("a-tooltip", resultat)
        self.assertIn("Jean", resultat)

    def test_plusieurs_personnes_utilise_une_liste_depliable(self):
        detail = [
            ("4", 4, "Jean", "2026-08-04"),
            ("2", 2, "Marie", "2026-08-04"),
            ("5", 5, "Paul", "2026-07-01"),
        ]
        resultat = rb.rendu_nombre_avec_detail_notes(3, detail)
        self.assertIn("<details class='detail-oui'>", resultat)
        self.assertNotIn("detail-inline", resultat)
        # Trié par note croissante - Marie (2) doit apparaître en premier.
        self.assertLess(resultat.index("Marie"), resultat.index("Jean"))


class TestSectionASurveiller(unittest.TestCase):
    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_a_surveiller([]), "")

    def test_trie_par_note_croissante_puis_date_decroissante(self):
        alertes = [
            ("2026-08-04", "Q1", "Item1", "Jean", 1, None),
            ("2026-07-01", "Q2", "Item2", "Marie", 2, None),
            ("2026-08-04", "Q3", "Item3", "Paul", 2, None),
        ]
        html = rb.section_a_surveiller(alertes)
        # Jean (note 1) doit apparaître avant Marie et Paul (note 2).
        self.assertLess(html.index("Jean"), html.index("Marie"))
        self.assertLess(html.index("Jean"), html.index("Paul"))
        # Entre Marie et Paul (note égale), le plus récent (Paul, 08-04)
        # doit apparaître avant Marie (07-01).
        self.assertLess(html.index("Paul"), html.index("Marie"))

    def test_nombre_correct_dans_le_badge(self):
        alertes = [("2026-08-04", "Q", "I", "Jean", 1, None), ("2026-08-04", "Q", "I", "Marie", 2, None)]
        html = rb.section_a_surveiller(alertes)
        self.assertIn("2 note(s)", html)

    def test_commentaire_lie_affiche_si_present(self):
        """Nouveau en v1.68.0 : un commentaire libre de la même personne
        dans le même sondage est affiché à côté de la note basse."""
        alertes = [("2026-08-04", "Q", "I", "Jean", 1, "Le local était trop bruyant")]
        html = rb.section_a_surveiller(alertes)
        self.assertIn("Le local était trop bruyant", html)

    def test_tiret_si_aucun_commentaire(self):
        alertes = [("2026-08-04", "Q", "I", "Jean", 1, None)]
        html = rb.section_a_surveiller(alertes)
        self.assertIn("<td class='commentaire-lie'>—</td>", html)


class TestSectionEvolutionEtTendance(unittest.TestCase):
    def test_evolution_vide_si_moins_de_2_rencontres(self):
        stats = [("2026-08-04", "x1", 15, 12, 2, 300, 5)]
        self.assertEqual(rb.section_evolution(stats), "")

    def test_evolution_avec_2_rencontres(self):
        stats = [
            ("2026-08-04", "x1", 15, 12, 2, 300, 5),
            ("2026-07-01", "x2", 10, 8, 1, 250, 5),
        ]
        html = rb.section_evolution(stats)
        self.assertIn("evo-section", html)
        self.assertEqual(html.count("evo-barre-conteneur"), 6)  # 3 séries x 2 dates

    def test_tendance_vide_si_moins_de_2_dates_avec_valeurs(self):
        self.assertEqual(rb.section_tendance_question("Q", {"2026-08-04": [4]}), "")
        self.assertEqual(rb.section_tendance_question("Q", {}), "")

    def test_tendance_ignore_dates_sans_valeur(self):
        valeurs = {"2026-08-04": [4, 5], "2026-07-01": [], "2026-06-01": [3, 3]}
        html = rb.section_tendance_question("Q", valeurs)
        # Seules 2 dates ont des valeurs -> devrait quand même produire un graphique.
        self.assertNotEqual(html, "")
        self.assertEqual(html.count("evo-barre-conteneur"), 2)

    def test_hauteur_en_pixels_pas_en_pourcentage(self):
        """Régression signalée (v1.55.0) : aucune différence de hauteur
        visible entre 4.0 et 5.0 - un pourcentage sur un enfant flex
        (flex-direction:column) ne se résout pas toujours de façon
        fiable. Passé à une hauteur en pixels, calculée directement."""
        html = rb.section_tendance_question("Q", {"2026-08-04": [5.0], "2026-07-01": [4.0]})
        self.assertIn("height:70px", html)
        self.assertIn("height:52px", html)
        self.assertNotIn("%'></div>", html)

    def test_tooltip_statistiques_completes_par_barre(self):
        """Nouveau en v1.57.0, converti en % en v1.72.0 : chaque barre
        porte un tooltip avec les statistiques complètes en pourcentage
        de l'échelle (Min/Moy/Max/É-T/P95/# réponses), pas seulement la
        moyenne affichée au-dessus - elle aussi en % désormais, pour
        pouvoir comparer visuellement des métriques sur des échelles
        différentes. v1.75.0 : formule corrigée pour être valeur/max*100
        (comme barre()), pas ancrée à echelle_min (qui donnait des %
        incohérents avec le reste du rapport pour la même note)."""
        html = rb.section_tendance_question("Q", {"2026-08-04": [4.8, 5.0], "2026-07-01": [3.5, 3.6]})
        self.assertIn("Min 96% · Moy 98% · Max 100% · É-T 2% · P95 100%", html)
        self.assertIn("2 réponse(s)", html)
        self.assertIn("98%</div>", html)

    def test_limites_controle_detecte_une_valeur_hors_norme(self):
        """Nouveau en v1.68.0 : avec limites_controle=True, une
        rencontre dont la moyenne s'écarte de plus d'un écart-type de
        la moyenne globale est marquée distinctement."""
        valeurs = {
            "2026-01-01": [4, 4], "2026-02-01": [4, 4],
            "2026-03-01": [1, 1], "2026-04-01": [4, 4],
        }
        html = rb.section_tendance_question("Q", valeurs, limites_controle=True)
        self.assertIn("evo-barre-signal", html)
        self.assertIn("écart-type", html)

    def test_limites_controle_desactivees_par_defaut(self):
        valeurs = {"2026-01-01": [4, 4], "2026-02-01": [1, 1]}
        html = rb.section_tendance_question("Q", valeurs)
        self.assertNotIn("evo-barre-signal", html)

    def test_derive_a_la_baisse_detectee(self):
        """Nouveau en v1.71.0 : une tendance soutenue sur 3 rencontres
        consécutives (pas juste un point isolé) est signalée."""
        valeurs = {
            "2026-01-01": [4], "2026-02-01": [3.5], "2026-03-01": [3], "2026-04-01": [2.5],
        }
        html = rb.section_tendance_question("Q", valeurs, detecter_derive=True)
        self.assertIn("BAISSE soutenue", html)

    def test_derive_a_la_hausse_detectee(self):
        valeurs = {
            "2026-01-01": [2.5], "2026-02-01": [3], "2026-03-01": [3.5], "2026-04-01": [4],
        }
        html = rb.section_tendance_question("Q", valeurs, detecter_derive=True)
        self.assertIn("HAUSSE soutenue", html)

    def test_pas_de_derive_si_non_monotone(self):
        valeurs = {
            "2026-01-01": [4], "2026-02-01": [3], "2026-03-01": [4], "2026-04-01": [3],
        }
        html = rb.section_tendance_question("Q", valeurs, detecter_derive=True)
        self.assertNotIn("soutenue", html)

    def test_derive_desactivee_par_defaut(self):
        valeurs = {
            "2026-01-01": [4], "2026-02-01": [3.5], "2026-03-01": [3], "2026-04-01": [2.5],
        }
        html = rb.section_tendance_question("Q", valeurs)
        self.assertNotIn("soutenue", html)


class TestSectionChoixEtPrecisions(unittest.TestCase):
    """Couvre la régression corrigée en v1.42.0 : la précision "Autre"
    doit être listée séparément, sans fragmenter le comptage."""

    def test_precisions_naffectent_pas_le_comptage(self):
        compteur = {"Facebook": 5, "Autre": 2}
        precisions = [("Marie", "Un ami me l'a mentionné"), ("Paul", "Meetup.com")]
        html = rb.section_choix("Où avez-vous vu l'annonce ?", compteur, precisions=precisions)
        self.assertIn(">2<", html.split("Autre")[1].split("</tr>")[0])
        self.assertIn("Meetup.com", html)
        self.assertIn("Précisions données pour", html)

    def test_sans_precisions_pas_de_bloc_supplementaire(self):
        html = rb.section_choix("Q", {"Oui": 3, "Non": 1})
        self.assertNotIn("Précisions données pour", html)


class TestListeDatesSimple(unittest.TestCase):
    """Nouvelle en v1.50.0 : liste des dates de participation à vie
    (sondages remplis, événements inscrits) sous chaque participant."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.liste_dates_simple([]), "")

    def test_sous_le_seuil_affiche_en_texte(self):
        resultat = rb.liste_dates_simple(["2026-08-04", "2026-07-01"])
        self.assertEqual(resultat, "2026-08-04, 2026-07-01")
        self.assertNotIn("<details", resultat)

    def test_au_dessus_du_seuil_utilise_une_liste_depliable(self):
        dates = ["2026-08-04", "2026-07-01", "2026-06-03", "2026-05-01", "2026-04-01"]
        resultat = rb.liste_dates_simple(dates)
        self.assertIn("<details", resultat)
        self.assertIn("(5 dates)", resultat)

    def test_trie_du_plus_recent_au_plus_ancien(self):
        resultat = rb.liste_dates_simple(["2026-01-01", "2026-08-04"])
        self.assertLess(resultat.index("2026-08-04"), resultat.index("2026-01-01"))

    def test_deduplique(self):
        resultat = rb.liste_dates_simple(["2026-08-04", "2026-08-04"])
        self.assertEqual(resultat, "2026-08-04")


class TestListeDatesAvecLiens(unittest.TestCase):
    """Nouvelle en v1.55.0 : dates cliquables pour "Événements inscrits"
    (chaque date pointe vers la fiche de configuration de l'événement)."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.liste_dates_avec_liens([]), "")

    def test_date_avec_url_devient_un_lien(self):
        resultat = rb.liste_dates_avec_liens([("2026-08-04", "https://exemple.com/event/1")])
        self.assertIn("<a href='https://exemple.com/event/1'", resultat)
        self.assertIn("2026-08-04", resultat)

    def test_date_sans_url_reste_en_texte_simple(self):
        resultat = rb.liste_dates_avec_liens([("2026-08-04", None)])
        self.assertNotIn("<a href", resultat)
        self.assertIn("2026-08-04", resultat)

    def test_url_prefixe_diese_devient_un_lien_interne(self):
        """Nouveau en v1.60.0 : un url commençant par "#" est traité
        comme une ancre interne au rapport (via lien_ancre(), pour un
        défilement correct dans le widget Html d'Odoo), pas comme un
        lien externe classique - régression signalée où les liens
        "Événements inscrits" pointaient hors du rapport."""
        resultat = rb.liste_dates_avec_liens([("2026-08-04", "#2026-08-04")])
        self.assertIn("onclick", resultat)
        self.assertNotIn("target='_blank'", resultat)

    def test_au_dessus_du_seuil_utilise_une_liste_depliable(self):
        paires = [(f"2026-0{i}-01", f"https://exemple.com/{i}") for i in range(1, 6)]
        resultat = rb.liste_dates_avec_liens(paires)
        self.assertIn("<details", resultat)
        self.assertIn("(5 dates)", resultat)


class TestAppreciationPresentateurs(unittest.TestCase):
    """Nouveau en v1.54.0 - extraction HEURISTIQUE d'un nom de
    présentateur depuis le titre d'une présentation (format supposé :
    "Titre - Nom Prénom")."""

    def test_extrait_nom_plausible(self):
        """Format confirmé par l'utilisateur (v1.55.0) : le nom entre
        crochets, à la fin du titre - pas un tiret comme d'abord
        supposé en v1.54.0."""
        titre, nom = rb.extraire_presentateur(
            "Organisation de la Journée Portes-Ouvertes sur Linux 2026 [Étienne Bérubé]"
        )
        self.assertEqual(titre, "Organisation de la Journée Portes-Ouvertes sur Linux 2026")
        self.assertEqual(nom, "Étienne Bérubé")

    def test_extrait_nom_avec_trait_union(self):
        _titre, nom = rb.extraire_presentateur("Sécurité web [Marie-Ève St-Laurent]")
        self.assertEqual(nom, "Marie-Ève St-Laurent")

    def test_extrait_nom_entre_parentheses(self):
        """Nouveau en v1.66.0 : le nom peut aussi être entre parenthèses,
        pas seulement entre crochets - les deux formats sont utilisés."""
        titre, nom = rb.extraire_presentateur("Introduction à Docker (Jean Dupont)")
        self.assertEqual(titre, "Introduction à Docker")
        self.assertEqual(nom, "Jean Dupont")

    def test_crochets_ailleurs_dans_le_titre_ignores(self):
        """Seuls des crochets en TOUTE FIN de titre comptent - des
        crochets ailleurs dans le titre ne doivent pas être confondus."""
        titre, nom = rb.extraire_presentateur(
            "Un titre avec [des crochets] au milieu et à la fin [Jean Dupont]"
        )
        self.assertEqual(nom, "Jean Dupont")
        self.assertEqual(titre, "Un titre avec [des crochets] au milieu et à la fin")

    def test_sans_crochets_pas_de_nom_extrait(self):
        titre, nom = rb.extraire_presentateur("Titre sans aucun crochet")
        self.assertIsNone(nom)
        self.assertEqual(titre, "Titre sans aucun crochet")

    def test_section_vide_si_aucune_donnee(self):
        self.assertEqual(rb.section_appreciation_presentateurs([]), "")

    def test_section_contient_les_presentateurs(self):
        donnees = [
            {
                "presentateur": "Jean Dupont", "valeurs": [4, 5, 4], "detail": [],
                "presentations": [("Introduction à Docker", "2026-08-04", [4, 5, 4])],
            },
            {
                "presentateur": "Marie Martin", "valeurs": [3, 3], "detail": [],
                "presentations": [("Sécurité web", None, [3, 3])],
            },
        ]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("Jean Dupont", html)
        self.assertIn("Marie Martin", html)
        self.assertIn("Appréciation des présentateurs", html)

    def test_tooltip_de_date_sur_le_titre_de_presentation(self):
        """Nouveau en v1.56.0 : le titre de chaque présentation porte un
        tooltip indiquant sa date, comme pour un volet de matrice."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [4], "detail": [],
            "presentations": [("Introduction à Docker", "2026-08-04", [4])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("data-rlq-tip=\"Présenté le 2026-08-04", html)

    def test_detail_des_votants_disponible(self):
        """Nouveau en v1.56.0 : le chiffre "# réponses" porte une flèche
        cliquable vers le détail de qui a voté quoi."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [4, 5, 3],
            "detail": [("4", 4, "Marie", "2026-08-04"), ("5", 5, "Paul", "2026-08-04"), ("3", 3, "Alice", "2026-07-01")],
            "presentations": [("Introduction à Docker", "2026-08-04", [4, 5, 3])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("detail-oui", html)
        self.assertIn("Marie", html)
        self.assertIn("Paul", html)
        self.assertIn("Alice", html)

    def test_statistiques_en_pourcentage_avec_p95(self):
        """Nouveau en v1.72.0 : les statistiques de la ligne principale
        d'un présentateur sont exprimées en % (comme la tendance), avec
        P95 qui manquait auparavant à cet endroit précis. v1.75.0 :
        formule corrigée pour être valeur/max*100 (comme barre()), pas
        ancrée à echelle_min - une note de 2/5 affichait 25% avant ce
        correctif, au lieu des 40% attendus."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [2, 3, 4, 5], "detail": [],
            "presentations": [("Intro", "2026-01-01", [2, 3, 4, 5])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("P95", html)
        self.assertIn("40%", html)  # Min (valeur 2 sur échelle 1-5)

    def test_stats_individuelles_si_plusieurs_presentations(self):
        """Nouveau en v1.62.0 : si un présentateur a fait plusieurs
        présentations, chacune affiche sa propre moyenne et son nombre
        de réponses. Pas de résumé "Moyenne combinée" séparé (retiré en
        v1.63.0, redondant avec la colonne "Note moyenne" déjà affichée
        sur la ligne principale du présentateur)."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [4, 5, 4, 3], "detail": [],
            "presentations": [
                ("Introduction à Docker", "2026-08-04", [4, 5]),
                ("Sécurité web", "2026-07-01", [4, 3]),
            ],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("Moy <span class='val-bleu'>4.50</span>, 2 réponse(s)", html)
        self.assertIn("Moy <span class='val-neutre'>3.50</span>, 2 réponse(s)", html)
        self.assertNotIn("Moyenne combinée de 2 présentations", html)

    def test_pas_de_stats_individuelles_si_une_seule_presentation(self):
        """Une seule présentation : pas de détail par présentation
        (redondant avec la ligne principale)."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [4, 5], "detail": [],
            "presentations": [("Introduction à Docker", "2026-08-04", [4, 5])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertNotIn("Moyenne combinée de 1 présentation", html)
        self.assertNotIn("réponse(s)</li>", html)


class TestJetonPresentateur(unittest.TestCase):
    """v1.78.0 - jeton stable et déterministe substitué au nom réel d'un
    présentateur là où il doit rester visible, immunisant ce texte
    précis contre le remplacement global par pseudonyme (voir
    _anonymiser_html() dans le wizard)."""

    def test_deterministe_pour_le_meme_nom(self):
        self.assertEqual(rb.jeton_presentateur("Jean Dupont"), rb.jeton_presentateur("Jean Dupont"))

    def test_different_pour_des_noms_differents(self):
        self.assertNotEqual(rb.jeton_presentateur("Jean Dupont"), rb.jeton_presentateur("Marie Tremblay"))

    def test_insensible_a_echapper(self):
        # Aucun caractère &<>" dans le jeton - echapper()/echapper_attr()
        # doivent le laisser parfaitement intact.
        jeton = rb.jeton_presentateur("O'Brien & Associés")
        self.assertEqual(rb.echapper(jeton), jeton)
        self.assertEqual(rb.echapper_attr(jeton), jeton)


class TestProtegerNomDansTitre(unittest.TestCase):
    """v1.78.0 - protège le nom d'un présentateur dans un titre de
    présentation (format reconnu par extraire_presentateur), pour qu'il
    survive à _anonymiser_html() là où il doit rester visible."""

    def test_remplace_le_nom_entre_crochets(self):
        resultat = rb.proteger_nom_dans_titre("Introduction à Docker [Jean Dupont]")
        self.assertNotIn("Jean Dupont", resultat)
        self.assertIn("Introduction à Docker", resultat)
        self.assertIn(rb.jeton_presentateur("Jean Dupont"), resultat)

    def test_preserve_les_crochets_dorigine(self):
        resultat = rb.proteger_nom_dans_titre("Introduction à Docker [Jean Dupont]")
        self.assertIn("[", resultat)
        self.assertIn("]", resultat)

    def test_preserve_les_parentheses_dorigine(self):
        resultat = rb.proteger_nom_dans_titre("Introduction à Docker (Jean Dupont)")
        self.assertIn("(", resultat)
        self.assertIn(")", resultat)
        self.assertNotIn("Jean Dupont", resultat)

    def test_inchange_si_aucun_nom_reconnu(self):
        self.assertEqual(rb.proteger_nom_dans_titre("Titre sans nom"), "Titre sans nom")



class TestTopMouvements(unittest.TestCase):
    """Nouveau en v1.68.0 - résumé des questions ayant le plus changé
    entre les deux dernières rencontres, en tête de la Synthèse.
    v1.73.0 : affiché en % de l'échelle plutôt qu'en points bruts."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_top_mouvements([]), "")

    def test_trie_par_ampleur_du_changement(self):
        mouvements = [("Q1", 3.0, 4.5), ("Q2", 4.0, 3.9), ("Q3", 4.0, 4.0), ("Q4", 4.5, 3.0)]
        html = rb.section_top_mouvements(mouvements)
        # Q3 (aucun changement) ne devrait pas apparaître, Q1/Q4 (plus gros
        # changements) devraient apparaître avant Q2.
        self.assertNotIn("Q3", html)
        self.assertLess(html.index("Q1"), html.index("Q2"))
        self.assertIn("▲", html)
        self.assertIn("▼", html)

    def test_respecte_la_limite(self):
        mouvements = [(f"Q{i}", 3.0, 3.0 + i) for i in range(1, 6)]
        html = rb.section_top_mouvements(mouvements, limite=2)
        self.assertEqual(html.count("<li>"), 2)

    def test_valeurs_affichees_en_pourcentage(self):
        # v1.75.0 : valeur/échelle_max*100 (comme barre()), pas ancré à
        # echelle_min - 1/5 -> 20%, 5/5 -> 100% (PAS 0%/100%, qui supposait
        # à tort une échelle ancrée à echelle_min=1).
        html = rb.section_top_mouvements([("Q1", 1.0, 5.0)])
        self.assertNotIn("point de %", html)
        self.assertIn("(20% → 100%)", html)
        self.assertNotIn("1.00", html)
        self.assertNotIn("5.00", html)

    def test_respecte_echelle_personnalisee(self):
        html = rb.section_top_mouvements([("Q1", 0.0, 10.0)], echelle_min=0, echelle_max=10)
        self.assertIn("(0% → 100%)", html)


class TestTauxReponse(unittest.TestCase):
    """Nouveau en v1.68.0 - taux de réponse (terminé/inscrit) comme
    tendance distincte de la satisfaction, une métrique d'engagement."""

    def test_vide_si_moins_de_deux_rencontres(self):
        stats = [("4 août", "a1", 20, 15, 3, 100, 5)]
        self.assertEqual(rb.section_taux_reponse(stats), "")

    def test_calcule_le_pourcentage_correctement(self):
        stats = [
            ("4 août", "a1", 20, 15, 3, 100, 5),
            ("1 juillet", "a2", 30, 10, 5, 100, 5),
        ]
        html = rb.section_taux_reponse(stats)
        self.assertIn("75%", html)
        self.assertIn("33%", html)

    def test_ignore_les_rencontres_sans_inscrit(self):
        """Évite une division par zéro si une rencontre n'a aucun inscrit."""
        stats = [
            ("4 août", "a1", 0, 0, 0, 100, 5),
            ("1 juillet", "a2", 10, 5, 2, 100, 5),
            ("1 juin", "a3", 10, 8, 1, 100, 5),
        ]
        html = rb.section_taux_reponse(stats)
        self.assertIn("50%", html)
        self.assertIn("80%", html)


class TestTendancePresentateur(unittest.TestCase):
    """Nouveau en v1.68.0 - indicateur de tendance (▲▼▬) pour un
    présentateur ayant plusieurs présentations datées."""

    def test_tendance_a_la_hausse(self):
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [3, 5], "detail": [],
            "presentations": [("Intro", "2026-01-01", [3]), ("Suite", "2026-08-01", [5])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("En hausse", html)
        self.assertIn("▲", html)

    def test_tendance_a_la_baisse(self):
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [5, 3], "detail": [],
            "presentations": [("Intro", "2026-01-01", [5]), ("Suite", "2026-08-01", [3])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertIn("En baisse", html)
        self.assertIn("▼", html)

    def test_pas_de_tendance_sans_dates(self):
        """Sans date connue sur au moins 2 présentations, aucune
        tendance ne peut être calculée - pas d'indicateur affiché."""
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [3, 5], "detail": [],
            "presentations": [("Intro", None, [3]), ("Suite", None, [5])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertNotIn("En hausse", html)
        self.assertNotIn("En baisse", html)

    def test_pas_de_tendance_avec_une_seule_presentation(self):
        donnees = [{
            "presentateur": "Jean Dupont", "valeurs": [4], "detail": [],
            "presentations": [("Intro", "2026-01-01", [4])],
        }]
        html = rb.section_appreciation_presentateurs(donnees)
        self.assertNotIn("En hausse", html)
        self.assertNotIn("En baisse", html)


class TestActionsSuivi(unittest.TestCase):
    """Nouveau en v1.71.0 - notes d'actions de suivi persistantes
    (champ rlq_actions_suivi sur survey.survey), pour fermer la boucle
    Plan-Do-Check-Act d'une rencontre à l'autre."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_actions_suivi(""), "")
        self.assertEqual(rb.section_actions_suivi(None), "")
        self.assertEqual(rb.section_actions_suivi("   "), "")

    def test_affiche_le_texte_avec_sauts_de_ligne(self):
        html = rb.section_actions_suivi("Projecteur remplacé.\nÀ vérifier la prochaine fois.")
        self.assertIn("Actions de suivi", html)
        self.assertIn("Projecteur remplacé.<br/>À vérifier la prochaine fois.", html)

    def test_echappe_le_html(self):
        html = rb.section_actions_suivi("<script>alert(1)</script>")
        self.assertNotIn("<script>", html)


class TestActionsSuiviConsolidee(unittest.TestCase):
    """Nouveau en v1.73.0 - liste, dans la Synthèse, de toutes les
    notes d'actions de suivi des rencontres incluses dans le rapport
    (coexiste avec section_actions_suivi(), qui reste affichée sur
    chaque rencontre individuellement)."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_actions_suivi_consolidee([]), "")

    def test_liste_toutes_les_entrees_triees_par_date_desc(self):
        entrees = [("1 juillet 2026", "Note A"), ("4 août 2026", "Note B")]
        html = rb.section_actions_suivi_consolidee(entrees)
        self.assertIn("Note A", html)
        self.assertIn("Note B", html)
        # La plus récente (4 août) doit apparaître avant la plus ancienne.
        self.assertLess(html.index("Note B"), html.index("Note A"))
        self.assertEqual(html.count("<li>"), 2)

    def test_echappe_le_html_et_preserve_les_sauts_de_ligne(self):
        html = rb.section_actions_suivi_consolidee([("4 août 2026", "<script>x</script>\nSuite")])
        self.assertNotIn("<script>", html)
        self.assertIn("<br/>", html)


class TestNoteGlobale(unittest.TestCase):
    """Nouveau en v1.56.0 - métrique composite combinant Organisation
    et logistique, Satisfaction globale et les présentations, affichée
    en tête de chaque rencontre pour comparaison entre rencontres."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_note_globale([]), "")

    def test_contient_la_moyenne_et_les_stats(self):
        html = rb.section_note_globale([4, 5, 4.5, 3.8])
        self.assertIn("Note globale", html)
        self.assertIn("4 réponse(s)", html)
        self.assertIn("barre-cadre", html)

    def test_comparaison_a_la_moyenne_historique(self):
        """Nouveau en v1.68.0 : compare la note de cette rencontre à une
        moyenne de référence (calculée par l'appelant, ex. moyenne
        mobile des N dernières rencontres)."""
        html = rb.section_note_globale([4.5, 4.8], moyenne_reference=4.2, nb_reference=6)
        self.assertIn("au-dessus de la moyenne des 6 rencontre(s) précédente(s)", html)
        html_sous = rb.section_note_globale([3.0], moyenne_reference=4.2, nb_reference=3)
        self.assertIn("sous la moyenne des 3 rencontre(s) précédente(s)", html_sous)

    def test_pas_de_comparaison_sans_reference(self):
        html = rb.section_note_globale([4.5, 4.8])
        self.assertNotIn("rencontre(s) précédente(s)", html)

    def test_libelle_pourcentage_simplifie_et_formule_corrigee(self):
        """v1.75.0 : "3% sous la moyenne" plutôt que "3 point de % sous
        la moyenne" (simplifié sur demande), ET formule de l'écart
        corrigée pour être basée sur valeur/max*100 (comme barre()), pas
        ancrée à 1 - une note de 4/5 (80%) comparée à une référence de
        3/5 (60%) donne un écart de 20%, pas la valeur erronée que
        donnait l'ancien ancrage."""
        html = rb.section_note_globale([4, 4], moyenne_reference=3, nb_reference=5)
        self.assertNotIn("point de %", html)
        self.assertIn("20%", html)
        self.assertIn("(60%)", html)


class TestBarre(unittest.TestCase):
    def test_barre_sans_tooltip(self):
        html = rb.barre(3, 5)
        self.assertNotIn("a-tooltip", html)

    def test_barre_avec_tooltip(self):
        html = rb.barre(3, 5, info_bulle="3.0 / 5")
        self.assertIn("a-tooltip", html)
        self.assertIn("data-rlq-tip=\"3.0 / 5\"", html)

    def test_barre_valeur_none(self):
        # Ne doit jamais lever d'exception, même sans valeur.
        html = rb.barre(None, 5)
        self.assertIsInstance(html, str)

    def test_seuils_couleur_alignes_avec_colorer_par_valeur(self):
        """Régression signalée : _classe_pourcentage() utilisait des
        seuils différents (90/70/60%) de colorer_par_valeur() (2/4/5 sur
        échelle 1-5) - incohérent pour des valeurs affichées côte à
        côte. Alignés : sur une échelle 1-5 (maximum=5), 2->40%,
        3->60%, 4->80%, 5->100%."""
        self.assertIn("pct-rouge", rb.barre(2, 5, style_pourcentage=True, colorer_seuils=True))
        self.assertIn("pct-jaune", rb.barre(3, 5, style_pourcentage=True, colorer_seuils=True))
        self.assertIn("pct-bleu", rb.barre(4, 5, style_pourcentage=True, colorer_seuils=True))
        self.assertIn("pct-vert", rb.barre(5, 5, style_pourcentage=True, colorer_seuils=True))

    def test_barre_remplie_coloree_aussi(self):
        """Nouveau en v1.72.0 : la barre de remplissage elle-même change
        de couleur, pas seulement le texte du pourcentage à sa droite."""
        self.assertIn("barre-remplie-rouge", rb.barre(2, 5, style_pourcentage=True, colorer_seuils=True))
        self.assertIn("barre-remplie-vert", rb.barre(5, 5, style_pourcentage=True, colorer_seuils=True))


class TestCouleurHistogrammesVerticaux(unittest.TestCase):
    """Nouveau en v1.70.0 - les histogrammes verticaux (tendances)
    utilisent la même palette de couleurs que les chiffres et les
    barres horizontales (<=2 rouge, 3 jaune, 4 bleu, 5 vert)."""

    def test_couleurs_par_valeur(self):
        html = rb.section_tendance_question("Q", {
            "2026-01-01": [2], "2026-02-01": [3], "2026-03-01": [4], "2026-04-01": [5],
        })
        self.assertIn("evo-barre-rouge", html)
        self.assertIn("evo-barre-jaune", html)
        self.assertIn("evo-barre-bleu", html)
        self.assertIn("evo-barre-vert", html)


class TestDureeHumaine(unittest.TestCase):
    """v1.90.0 - formate une durée en secondes en texte lisible, pour le
    temps de réponse d'une soumission."""

    def test_secondes_seules(self):
        self.assertEqual(rb.duree_humaine(45), "45 s")

    def test_minutes_et_secondes(self):
        self.assertEqual(rb.duree_humaine(192), "3 min 12 s")

    def test_heures_et_minutes(self):
        self.assertEqual(rb.duree_humaine(3900), "1 h 05 min")

    def test_zero_ou_negatif_retourne_none(self):
        self.assertIsNone(rb.duree_humaine(0))
        self.assertIsNone(rb.duree_humaine(-5))
        self.assertIsNone(rb.duree_humaine(None))


class TestTableauReponsesPersonneChoixMultiples(unittest.TestCase):
    """v1.86.0 - une question à choix multiples affiche une réponse par
    ligne (triée), pas toutes jointes par des virgules sur une seule
    ligne. v1.87.0 - le deuxième paramètre ("colonnes") est maintenant
    une liste de dicts, pas de simples dates. v1.90.0 - "libelle" devient
    "ligne1"/"ligne2" (date du sondage vs date réelle de réponse,
    affichées séparément plutôt que combinées de façon trompeuse)."""

    def test_liste_de_reponses_une_par_ligne(self):
        reponses = {("2026-08-04", "Q"): ["Python", "Bash", "Ansible"]}
        colonnes = [{"id": "2026-08-04", "ligne1": "2026-08-04", "ancre": "2026-08-04"}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "multiple_choice"})
        self.assertIn("<br/>", html)
        self.assertNotIn("Python, Bash", html)
        # Triées alphabétiquement.
        self.assertLess(html.index("Ansible"), html.index("Bash"))
        self.assertLess(html.index("Bash"), html.index("Python"))

    def test_chaine_simple_inchangee(self):
        reponses = {("2026-08-04", "Q"): "Une seule réponse"}
        colonnes = [{"id": "2026-08-04", "ligne1": "2026-08-04", "ancre": "2026-08-04"}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        self.assertIn("Une seule réponse", html)
        self.assertNotIn("<br/>", html)

    def test_colonnes_par_soumission_avec_heure(self):
        """v1.87.0 - deux colonnes distinctes pour deux soumissions au
        même sondage (identifiants différents), avec heure de réponse
        sur une deuxième ligne distincte de la date du sondage."""
        reponses = {
            (("2026-08-04", 1), "Q"): "Première réponse",
            (("2026-08-04", 2), "Q"): "Deuxième réponse",
        }
        colonnes = [
            {"id": ("2026-08-04", 2), "ligne1": "2026-08-04", "ligne2": "2026-08-04 14:30", "ancre": "2026-08-04"},
            {"id": ("2026-08-04", 1), "ligne1": "2026-08-04", "ligne2": "2026-08-04 10:00", "ancre": "2026-08-04"},
        ]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        self.assertIn("2026-08-04 10:00", html)
        self.assertIn("2026-08-04 14:30", html)
        self.assertIn("Première réponse", html)
        self.assertIn("Deuxième réponse", html)
        self.assertEqual(html.count("<th>"), 2)

    def test_ligne2_differente_de_ligne1_si_reponse_tardive(self):
        """v1.90.0 - si la personne répond après la date du sondage, les
        deux dates doivent apparaître séparément (pas fusionnées en une
        seule qui mélangerait la date du sondage et l'heure réelle)."""
        reponses = {("x", "Q"): "Réponse"}
        colonnes = [{"id": "x", "ligne1": "2026-08-04", "ligne2": "2026-08-07 21:37", "ancre": "2026-08-04"}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        entete = html.split("<thead>")[1].split("</thead>")[0]
        self.assertIn("2026-08-04", entete)
        self.assertIn("2026-08-07 21:37", entete)
        self.assertIn("<br/>", entete)

    def test_duree_affichee(self):
        reponses = {("x", "Q"): "Réponse"}
        colonnes = [{"id": "x", "ligne1": "2026-08-04", "ligne2": "2026-08-04 10:05", "duree": "5 min 12 s", "ancre": "2026-08-04"}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        self.assertIn("duree-reponse", html)
        self.assertIn("5 min 12 s", html)

    def test_colonne_sans_ancre_pas_de_lien(self):
        reponses = {("x", "Q"): "Réponse"}
        colonnes = [{"id": "x", "ligne1": "Date inconnue", "ancre": None}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        self.assertIn("Date inconnue", html)
        self.assertNotIn("<a ", html.split("<thead>")[1].split("</thead>")[0])

    def test_badge_entree_test_dans_entete_colonne(self):
        """v1.88.0 - le statut "Entrée test" s'affiche directement dans
        l'en-tête de la colonne (mode par soumission), plutôt que
        seulement dans "Détail des soumissions"."""
        reponses = {("x", "Q"): "Réponse"}
        colonnes = [{"id": "x", "ligne1": "2026-08-04", "ligne2": "2026-08-04 10:00", "ancre": "2026-08-04", "test": True}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        entete = html.split("<thead>")[1].split("</thead>")[0]
        self.assertIn("badge-test", entete)
        self.assertIn("Entrée test", entete)

    def test_pas_de_badge_si_test_absent_ou_faux(self):
        reponses = {("x", "Q"): "Réponse"}
        colonnes = [{"id": "x", "ligne1": "2026-08-04", "ligne2": "2026-08-04 10:00", "ancre": "2026-08-04", "test": False}]
        html = rb.tableau_reponses_personne(reponses, colonnes, {"Q": "simple_choice"})
        self.assertNotIn("badge-test", html)


class TestSectionSoumissionsParticipant(unittest.TestCase):
    """v1.86.0 - détail des soumissions individuelles d'un participant
    (date de réponse, date limite, entrée test, commentaire du personnel) -
    une entrée par SOUMISSION réelle, pas par rencontre (une même
    rencontre peut apparaître plusieurs fois si la personne a répondu plus
    d'une fois)."""

    def test_vide_retourne_chaine_vide(self):
        self.assertEqual(rb.section_soumissions_participant([]), "")

    def test_deux_soumissions_meme_rencontre(self):
        soumissions = [
            {"date_rencontre": "2026-08-04", "date_reponse": "2026-08-01 10:00", "date_limite": None, "test": False},
            {"date_rencontre": "2026-08-04", "date_reponse": "2026-08-02 14:00", "date_limite": None, "test": False},
        ]
        html = rb.section_soumissions_participant(soumissions)
        self.assertEqual(html.count("<li>"), 2)
        # La plus récente (2 août) doit apparaître avant la plus ancienne.
        self.assertLess(html.index("2026-08-02"), html.index("2026-08-01"))

    def test_badge_entree_test(self):
        soumissions = [{"date_rencontre": "2026-08-04", "date_reponse": "2026-08-04 10:00", "date_limite": None, "test": True}]
        html = rb.section_soumissions_participant(soumissions)
        self.assertIn("badge-test", html)
        self.assertIn("Entrée test", html)

    def test_date_limite_affichee(self):
        soumissions = [{"date_rencontre": "2026-08-04", "date_reponse": "2026-08-04 10:00", "date_limite": "2026-08-10 23:59", "test": False}]
        html = rb.section_soumissions_participant(soumissions)
        self.assertIn("2026-08-10 23:59", html)

    def test_commentaire_staff_affiche_et_echappe(self):
        soumissions = [{
            "date_rencontre": "2026-08-04", "date_reponse": "2026-08-04 10:00", "date_limite": None,
            "test": False, "commentaire": "<script>alert(1)</script>",
        }]
        html = rb.section_soumissions_participant(soumissions)
        self.assertIn("commentaire-staff", html)
        self.assertNotIn("<script>", html)


class TestRemplacerNomComplet(unittest.TestCase):
    """v1.93.0 - signalé : un participant dont le nom se terminait par une parenthèse
    (« Gilles Paradis (exemple.com) ») restait visible dans un rapport anonymisé,
    alors que tous les autres étaient masqués. Cause : \\b...\\b ne matche pas après « ) »."""

    @staticmethod
    def _anon(html, nom, pseudo="Participant 1"):
        import unicodedata
        return rb.remplacer_nom_complet(unicodedata.normalize("NFC", html), nom, pseudo)

    NOM = "Gilles Paradis (exemple.com)"

    def test_nom_se_terminant_par_une_parenthese(self):
        """Le cas EXACT signalé."""
        html = f"<li>{self.NOM} (3)</li><p>{self.NOM}</p>"
        sortie = self._anon(html, self.NOM)
        self.assertEqual(sortie, "<li>Participant 1 (3)</li><p>Participant 1</p>")
        self.assertNotIn("Paradis", sortie)
        self.assertNotIn("exemple", sortie)

    def test_nom_suivi_directement_d_une_balise_ou_d_une_virgule(self):
        sortie = self._anon(f"<b>{self.NOM}</b>, {self.NOM}.", self.NOM)
        self.assertEqual(sortie, "<b>Participant 1</b>, Participant 1.")

    def test_nom_en_debut_et_en_fin_de_texte(self):
        self.assertEqual(self._anon(self.NOM, self.NOM), "Participant 1")

    def test_nom_finissant_par_un_point(self):
        self.assertEqual(self._anon("<td>Jean Dupont Jr.</td>", "Jean Dupont Jr."), "<td>Participant 1</td>")

    def test_nom_commencant_par_une_parenthese(self):
        self.assertEqual(self._anon("<td>(CEO) Marie Tremblay</td>", "(CEO) Marie Tremblay"), "<td>Participant 1</td>")

    def test_ne_corrompt_jamais_un_mot_plus_long(self):
        """Le comportement de \\b...\\b est conservé pour les noms ordinaires."""
        self.assertEqual(self._anon("<td>Filtre</td> et F", "F"), "<td>Filtre</td> et Participant 1")
        self.assertEqual(self._anon("Jeanne et Jean", "Jean"), "Jeanne et Participant 1")
        self.assertEqual(self._anon("Anna", "Ann"), "Anna")

    def test_formes_echappees_texte_et_attribut(self):
        """Un nom avec apostrophe, esperluette ou guillemets apparaît échappé dans le HTML."""
        for nom in ("Patrick O'Brien", "Martin & Fils (Québec)", 'Jean "Jeannot" Roy'):
            html = f"<td>{rb.echapper(nom)}</td><span data-rlq-tip=\"{rb.echapper_attr(nom)}\">x</span>"
            sortie = self._anon(html, nom)
            self.assertNotIn(nom.split()[0] + " ", sortie.replace("Participant 1", ""), nom)
            self.assertEqual(sortie.count("Participant 1"), 2, nom)

    def test_accent_nfd_et_nfc(self):
        nom_nfd = "Fabia\u0301n Garcia (acme)"
        self.assertEqual(self._anon("<td>Fabián Garcia (acme)</td>", nom_nfd), "<td>Participant 1</td>")

    def test_remplacement_litteral(self):
        """Aucun caractère du remplacement n'est interprété (ex. une barre oblique inverse)."""
        self.assertEqual(self._anon("<td>Jean</td>", "Jean", pseudo="P\\1\\g<0>"), "<td>P\\1\\g<0></td>")

    def test_ancre_derivee_du_nom_et_courriel(self):
        slug = f"personne-{rb.slug(self.NOM)}"
        html = f"<section id='{slug}'><a href='#{slug}'>x</a><a href='mailto:gilles@exemple.com'>m</a></section>"
        html = self._anon(html, slug, "personne-1")
        html = self._anon(html, "gilles@exemple.com", "[courriel masqué]")
        self.assertNotIn("paradis", html)
        self.assertIn("id='personne-1'", html)
        self.assertIn("href='#personne-1'", html)
        self.assertIn("mailto:[courriel masqué]", html)


class TestHtmlReponsesCourriel(unittest.TestCase):
    """v1.94.0 : corps du courriel qui rappelle ses réponses au participant."""

    def test_questions_et_reponses_dans_l_ordre(self):
        html = rb.html_reponses_courriel([("Q1", ["Oui"]), ("Q2", ["A", "B"])])
        self.assertLess(html.index("Q1"), html.index("Q2"))
        self.assertIn("A<br/>B", html)

    def test_reponse_libre_echappee_et_retours_a_la_ligne_conserves(self):
        html = rb.html_reponses_courriel([("Q", ["<script>x</script>\nligne 2"])])
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;x&lt;/script&gt;<br/>ligne 2", html)

    def test_question_sans_reponse_omise_et_vide_si_rien(self):
        self.assertEqual(rb.html_reponses_courriel([("Q", []), ("R", ["  ", None])]), "")
        self.assertNotIn("Vide", rb.html_reponses_courriel([("Vide", []), ("Ok", ["x"])]))

    def test_titre_echappe(self):
        self.assertIn("&lt;i&gt;", rb.html_reponses_courriel([("<i>T</i>", ["x"])]))


class TestListesSansCourriel(unittest.TestCase):
    """v1.93.0 - en mode anonymisé, le wizard ne fournit AUCUN courriel aux listes : ni
    lien ✉ (qui devenait mailto:[courriel masqué]), ni champ « Courriels » à copier."""

    ENTREES = [("Jean", "2026-01-01"), ("Marie", "2026-01-01")]

    def test_sans_courriels_aucun_lien_ni_champ(self):
        html = rb.construire_detail_personnes(self.ENTREES, "2")
        self.assertNotIn("&#9993;", html)
        self.assertNotIn("mailto:", html)
        self.assertNotIn("champ-courriels", html)

    def test_avec_courriels_le_lien_existe_toujours_hors_anonymisation(self):
        emails = {rb.normaliser_nom("Jean"): "jean@exemple.com"}
        html = rb.construire_detail_personnes(self.ENTREES, "2", emails)
        self.assertIn("&#9993;", html)
        self.assertIn("mailto:jean@exemple.com", html)

    def test_infobulle_sans_courriel_pour_une_seule_personne(self):
        html = rb.rendu_avec_noms("1", [("Jean", "2026-01-01")], emails=None)
        self.assertNotIn("@", html)


class TestAlerteInscriptions(unittest.TestCase):
    """v1.95.0 - avertissement par courriel quand un événement atteint N inscriptions."""

    def test_destinataire_par_ordre_de_priorite(self):
        self.assertEqual(rb.destinataire_alerte_inscriptions("a@x.org", "b@x.org", "c@x.org"), ("a@x.org", "evenement"))
        self.assertEqual(rb.destinataire_alerte_inscriptions("", "b@x.org", "c@x.org"), ("b@x.org", "parametre"))
        self.assertEqual(rb.destinataire_alerte_inscriptions(None, False, "c@x.org"), ("c@x.org", "societe"))
        self.assertEqual(rb.destinataire_alerte_inscriptions("", "", ""), (None, None))

    def test_adresses_invalides_ignorees_et_plusieurs_adresses_permises(self):
        self.assertEqual(rb.destinataire_alerte_inscriptions("pas une adresse", "b@x.org; c@x.org,b@X.org", ""), ("b@x.org, c@x.org", "parametre"))
        self.assertEqual(rb.courriels_valides("a@x, <b@x.org>, c@x.org"), ["c@x.org"])

    def test_sujet_singulier_et_pluriel(self):
        self.assertEqual(rb.sujet_alerte_inscriptions("Rencontre  de   mars", 1), "1 inscription : Rencontre de mars")
        self.assertEqual(rb.sujet_alerte_inscriptions("Rencontre", 50), "50 inscriptions : Rencontre")

    def test_palier_sans_repetition(self):
        self.assertIsNone(rb.palier_alerte(49, 50))
        self.assertEqual(rb.palier_alerte(50, 50), 50)
        self.assertEqual(rb.palier_alerte(120, 50), 50)
        self.assertIsNone(rb.palier_alerte(120, 50, False, 50))

    def test_palier_avec_repetition_a_chaque_multiple(self):
        self.assertEqual(rb.palier_alerte(10, 10, True, 0), 10)
        self.assertIsNone(rb.palier_alerte(19, 10, True, 10))
        self.assertEqual(rb.palier_alerte(20, 10, True, 10), 20)
        self.assertEqual(rb.palier_alerte(35, 10, True, 10), 30)         # plusieurs multiples d'un coup : un seul courriel, le plus récent
        self.assertIsNone(rb.palier_alerte(9, 10, True, 30))              # annulations puis retour : rien avant le multiple suivant
        self.assertIsNone(rb.palier_alerte(25, 10, True, 30))

    def test_palier_valeurs_invalides(self):
        self.assertIsNone(rb.palier_alerte(5, 0, True))
        self.assertIsNone(rb.palier_alerte(5, -3))
        self.assertIsNone(rb.palier_alerte(None, "x"))
        self.assertIsNone(rb.palier_alerte(0, 1))

    def test_corps_repetition(self):
        html = rb.html_alerte_inscriptions("E", None, 20, 10, None, True)
        self.assertIn("chaque multiple de 10 inscriptions", html)
        self.assertNotIn("n'est envoyé qu'une fois", html)

    def test_corps_echappe_sans_donnee_personnelle(self):
        html = rb.html_alerte_inscriptions("Fête <b>x</b>", "2026-11-05", 50, 50, "https://exemple.org/odoo/event.event/7?a=1&b=2")
        self.assertIn("Fête &lt;b&gt;x&lt;/b&gt;", html)
        self.assertIn("50 inscriptions", html)
        self.assertIn("(seuil demandé : 50)", html)
        self.assertIn("a=1&amp;b=2", html)
        self.assertNotIn("<b>x", html)
        self.assertNotIn("<a", rb.html_alerte_inscriptions("E", None, 1, 1))


class TestAlerteSondage(unittest.TestCase):
    """v1.96.0 - courriel quand un sondage associé à un événement est complété."""

    def test_sujet(self):
        self.assertEqual(rb.sujet_alerte_sondage("Journée  portes ouvertes", " Issam "), "Sondage complété par Issam : Journée portes ouvertes")
        self.assertEqual(rb.sujet_alerte_sondage("E", ""), "Sondage complété par une personne : E")

    def test_corps_avancement_billet_echappement_sans_reponses(self):
        html = rb.html_alerte_sondage("JPOL 2026", "2026-10-24", "Issam <i>", "Bénévole", "Portes ouvertes (Bénévole)", 3, 12, "https://exemple.org/odoo/event.event/7")
        self.assertIn("Issam &lt;i&gt;", html)
        self.assertIn("billet « Bénévole »", html)
        self.assertIn("« Portes ouvertes (Bénévole) »", html)
        self.assertIn("<strong>3</strong> pour <strong>12</strong> inscriptions confirmées", html)
        self.assertIn("href=\"https://exemple.org/odoo/event.event/7\"", html)
        self.assertNotIn("<i>", html)
        un = rb.html_alerte_sondage("E", None, "", "", "S", 1, 1)
        self.assertIn("Une personne", un)
        self.assertIn("<strong>1</strong> inscription confirmée.", un)
        self.assertNotIn("<a", un)

    def test_tableau_dernieres_inscriptions_format_de_la_touche_i(self):
        """v1.97.0 : le courriel reprend le rapport « I » : sondage complété (date, nom, titre, état), NON terminé, AUCUN, ou « — » sans sondage attendu."""
        lignes = [
            {"quand": "2026-10-13 11:42", "nom": "R <b>", "billet": "Bénévole", "etat": "open", "attendu": True, "sondage": None},
            {"quand": "2026-10-12 19:57", "nom": "Issam", "billet": "Bénévole", "etat": "open", "attendu": True,
             "sondage": {"quand": "2026-10-12 20:10", "nom": "Issam", "titre": "Portes ouvertes (Bénévole)", "etat": "done"}},
            {"quand": "2026-10-12 18:39", "nom": "M", "billet": "Visiteur", "etat": "open", "attendu": True,
             "sondage": {"quand": "2026-10-12 18:50", "nom": "M", "titre": "S", "etat": "in_progress"}},
            {"quand": "2026-10-12 13:05", "nom": "J", "billet": "", "etat": "open", "attendu": False, "sondage": None},
        ]
        t = rb.tableau_inscriptions_html(lignes)
        self.assertIn("Dernières inscriptions (30 jours)", t)
        self.assertIn("<strong>AUCUN</strong> — inscription non confirmée", t)
        self.assertIn("<strong>complété</strong></span> : 2026-10-12 20:10 Issam Portes ouvertes (Bénévole) (done)", t)
        self.assertIn("<strong>NON terminé</strong>", t)
        self.assertIn("R &lt;b&gt;", t)
        self.assertNotIn("<b>", t)
        self.assertEqual(rb.tableau_inscriptions_html([]), "")
        html = rb.html_alerte_sondage("E", None, "Issam", "", "S", 1, 1, None, lignes)
        self.assertIn("Dernières inscriptions", html)
        self.assertNotIn("Dernières inscriptions", rb.html_alerte_sondage("E", None, "Issam", "", "S", 1, 1))


if __name__ == "__main__":
    unittest.main()
