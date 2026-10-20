# Consignes pour Claude — rlq-odoo-addons

## Pull requests

Les créer et donner le lien, ne jamais les fusionner ni les approuver ; l'utilisateur les valide lui-même.

## Tests : le moins de jetons possible

- Pour lancer ou vérifier les tests, déléguer à l'agent **`testeur`** (`.claude/agents/testeur.md` : Claude Haiku 5.5, effort low). Il lance
  `odoo18.0/rlq_survey_report/run-all.sh` et ne rapporte que le verdict, les échecs et les avertissements. Ne jamais relire la sortie complète dans la
  conversation principale.
- Corriger un échec : dans la conversation principale ; un échec simple et bien localisé peut être confié à Claude Sonnet 5.5, effort medium.
- L'utilisateur peut aussi lancer run-all.sh lui-même et ne coller que les lignes d'échec.

## Conventions

Version MAJEUR.MINEUR.AAAAMMJJ.HHMMSS (heure locale) ; module Odoo : version 18.0.MAJEUR.MINEUR.0 ; changelog dans `doc/`, le plus récent en premier ;
archive `rlq_survey_report.18.0.X.Y.0.zip` (sans la date).

## Dépôt public : aucune donnée personnelle

Jamais de vrai nom, courriel, nom d'utilisateur ou adresse IP d'une personne dans le dépôt (code, tests, changelogs, docs) : noms inventés, `exemple.org`,
adresses de documentation (RFC 5737).
