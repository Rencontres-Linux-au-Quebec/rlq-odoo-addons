# Contexte du projet — rlq_survey_report

Vue d'ensemble pour quiconque (humain ou IA) reprend ce projet sans avoir suivi son
historique. Détail exhaustif de chaque version : `doc/CHANGELOG.md`. Points de vigilance
et hypothèses non vérifiées : `doc/NOTES_VALIDATION.md`.

## En une phrase

Module Odoo 18 CE qui génère, à partir des données natives du module Sondage (`survey`),
un rapport HTML/PDF/Excel des sondages de satisfaction de rencontres communautaires
(développé à l'origine pour Rencontres Linux au Québec), pour aider les bénévoles à
s'améliorer d'une rencontre à l'autre selon l'amélioration continue (Lean Six Sigma).

## Pour qui, et pourquoi

- **Écouter les membres** : agréger plusieurs rencontres pour en dégager des tendances.
- **Passer du diagnostic à l'action** : distinguer un signal réel d'une variation normale
  (limites de contrôle, détection de dérive) et suivre les actions entreprises (champ
  « Actions de suivi », rappelé d'une rencontre à l'autre).
- **Accompagner les présentateurs bénévoles** : section dédiée et filtre par présentateur
  pour leur envoyer un rapport ciblé sur leurs propres rencontres.

Le développement se fait **sans accès direct à une instance Odoo** : développement,
livraison d'une archive, déploiement par l'utilisateur, retour des symptômes observés,
correctif. D'où le nombre d'hypothèses documentées dans `doc/NOTES_VALIDATION.md`.

## Architecture

```
rlq_survey_report/
├── __manifest__.py                    Dépendances : survey, mail, event
├── run-all.sh                         Lance toutes les vérifications (voir scripts/LISEZMOI.md)
├── ruff.toml                          Configuration de ruff (règles qui détectent de vrais bogues)
├── scripts/                           Modèle de configuration et guide de run-all.sh
├── static/src/css/                    Feuille de style de la liste « Historique et fichiers »
├── models/
│   ├── rlq_survey_report_wizard.py    Assistant (TransientModel) : orchestre toute la génération
│   ├── report_builder.py              Fonctions pures de rendu HTML - AUCUNE dépendance à l'ORM,
│   │                                    donc testables sans Odoo
│   ├── survey_survey.py               Champs ajoutés à survey.survey (dates, compteurs,
│   │                                    actions de suivi)
│   ├── event_ticket_survey.py         Sondage différent par type de billet (event.event.ticket)
│   ├── survey_reponses_courriel.py    Courriel des réponses envoyé au participant à la soumission (v1.94)
│   ├── event_inscriptions_alerte.py   Courriels à l'organisateur : N inscriptions atteintes (v1.95), sondage complété (v1.96)
│   ├── event_groupes_inscrits.py      (v1.106 : synchronisation périodique par sondage, tâche aux 5 min) Groupes Odoo des inscrits, un par type de billet (RLQ-JPOL26-Visiteur… depuis v1.104), refus, rattrapage à la création du compte (v1.98), retrait à l'annulation et groupe par réponse de sondage (v1.99)
│   ├── verification_groupes.py        Assistant « Vérifier les groupes et étiquettes » : aperçu puis application après confirmation (v1.104)
│   ├── groupes_etiquettes.py          Étiquettes de contact qui reflètent les groupes d'inscrits, synchronisées à chaque changement + tâche quotidienne (v1.102)
│   ├── event_survey_followup.py       Sondages non complétés : courriels des inscrits à relancer (v1.113), rapport quotidien par courriel (v1.114)
│   ├── followup_report.py             Fonctions pures du suivi des sondages et du rapport quotidien (testées sans Odoo)
│   └── rlq_survey_report_acces.py     Historique d'accès aux rapports (qui, quand, quelle action)
├── controllers/aide.py                Page /rlq_survey_report/aide : sert le guide utilisateur dans Odoo (v1.106)
├── views/                             Formulaire de l'assistant, menus, gabarit PDF, billets
├── data/                              URL d'aide, purge des pièces jointes, mot de passe par défaut, modèle du courriel de réponses
├── security/                          Droits d'accès
├── tests/
│   ├── test_report_builder.py         Tests autonomes (sans Odoo), très rapides
│   └── test_wizard.py                 Tests Odoo (TransactionCase) - exigent une vraie instance
└── doc/                               CONTEXTE.md, CHANGELOG.md, NOTES_VALIDATION.md,
                                         Guide-utilisateur-rlq_survey_report.html, run-all.changelog.txt
```

`report_builder.py` prend des structures Python simples et retourne du HTML : c'est ce qui
permet de tester la présentation (moyennes, seuils de couleur, mise en page) en quelques
millisecondes. Le wizard extrait les données de l'ORM puis appelle `report_builder.py`.

## Concepts clés

- **Rencontre** : un `survey.survey` traité comme un événement daté (date extraite du titre).
- **Note globale** : moyenne composite de trois questions (organisation et logistique,
  satisfaction globale, présentations), comparée à la moyenne mobile des rencontres
  précédentes de la même catégorie, avec limites de contrôle et détection de dérive.
- **Présentateur** : déduit du titre d'une présentation (`Titre [Nom]` ou `Titre (Nom)`) -
  une heuristique texte, pas une relation Odoo. Son nom reste visible dans les titres de
  présentation et l'appréciation des présentateurs même en mode anonymisé, grâce à des
  jetons stables protégés avant l'anonymisation et résolus après.
- **Statistiques en pourcentage** : valeur / échelle maximale × 100, comme les barres ; le
  code couleur reste basé sur la valeur brute (≤2 rouge, 3 jaune, 4 bleu, 5 vert).

## Anonymisation (quand « Anonymiser » est coché)

- Noms remplacés par « Participant N » (regex à limites de mot, accents normalisés).
- Retirés du rendu : courriel (avec son lien ✉ et les champs « Courriels » à copier), téléphone, mobile, ville, pays, étiquettes, et les lignes
  « Sondages remplis » / « Événements inscrits » (listes de dates = empreinte comportementale).
- Liens vers le backend Odoo (configuration du sondage, « Tester sondage », événement) :
  texte simple.
- Filet final : tout texte ayant la forme d'un courriel est masqué, sauf le courriel
  d'attribution d'auteur du pied de page.
- **Limites que le code ne peut pas lever** : le CONTENU d'une réponse libre peut identifier
  son auteur, et un petit nombre de répondants réduit l'anonymat de fait. Une relecture
  humaine reste nécessaire avant toute diffusion publique. Ce n'est pas un avis juridique.

## Mot de passe

| Cas | Mot de passe |
|---|---|
| Écran, rapport anonymisé | jamais |
| Écran, rapport NON anonymisé | requis |
| HTML / PDF anonymisé | jamais (fichier livré en clair) |
| HTML / PDF NON anonymisé | requis (chiffré) |
| Excel | TOUJOURS (non anonymisé, vrais noms) |

Critères : 12 caractères, minuscule, majuscule, chiffre, caractère spécial. Un mot de passe par
défaut est pré-rempli (masqué) depuis le paramètre système `rlq_survey_report.mot_de_passe_defaut` ;
la valeur livrée n'est qu'un marqueur refusé, à remplacer après l'installation (jamais écrasée : ni par une mise à jour, ni par
une réinstallation - créée seulement si elle est absente). Cadre : Loi 25 (Québec), RGPD, PCI DSS v4.0.

## Contraintes et conventions

- Licence AGPL-3. Interface minimaliste ; options PDF dans une fenêtre séparée.
- **Aucun JavaScript personnalisé ni champ `Html` contenant du CSS** : un tel champ a déjà fait
  planter l'interface (`OwlError`). Texte simple (`Char`) et notifications `display_notification`.
  Une feuille de style statique (`static/src/css/`, déclarée dans `assets` du manifeste) reste
  acceptable : elle ne casse rien si ses sélecteurs ne correspondent pas.
- **Pas d'attribut de vue dont la validité n'a pas été vérifiée** (ex. `width` sur une colonne de
  liste) : une vue invalide empêche le module entier de se charger (précédent : `<tree>`, v1.74.0).
- Version `18.0.1.XX.0`, incrémentée à chaque livraison, avec une entrée dans `doc/CHANGELOG.md`.
- **Archives livrées avec leur version dans le nom** (`rlq_survey_report.18.0.1.XX.0.zip`) pour
  pouvoir revenir en arrière ; le dossier interne reste `rlq_survey_report/`.
- Après chaque changement : `./run-all.sh --sans-odoo` (ruff, syntaxe et manifeste, tests autonomes),
  puis `./run-all.sh` complet sur une machine avec PostgreSQL et Odoo (base de test créée puis
  supprimée), et recherche de toute affectation `self.xxx = ...` sur un recordset (interdite par Odoo).
