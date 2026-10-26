# run-all.sh — lancer toutes les vérifications

`run-all.sh` (à la racine du module) enchaîne, en une commande, tout ce qui permet de
valider le module :

| Étape | Ce qui est fait | Exige |
|---|---|---|
| 1. Outils | repère Python et ruff | `python3` |
| 2. ruff | analyse du code (`ruff.toml`) | `ruff` (sinon étape ignorée) |
| 3. Syntaxe et manifeste | tous les `.py` et `.xml` ; fichiers du manifeste ; imports des `__init__.py` | `python3` |
| 4. Tests autonomes | `tests/test_report_builder.py` (sans Odoo) | `python3` |
| 5. Base de test + tests Odoo | crée une base PostgreSQL de test, installe le module, lance `tests/test_wizard.py`, puis supprime la base | PostgreSQL + Odoo |

Une étape dont l'outil est absent est **ignorée** avec la raison (ce n'est pas un échec). Le
code de sortie est 0 si tout est bon, 1 si une étape échoue, 2 si une option est invalide.

## Utilisation rapide

```bash
./run-all.sh                  # tout
./run-all.sh --sans-odoo      # sans PostgreSQL ni Odoo (étapes 1 à 4)
./run-all.sh --garder-bd      # garde la base de test pour l'examiner dans Odoo
./run-all.sh --supprimer-bd   # supprime seulement la base de test
./run-all.sh --bd rlq_test_2  # autre nom de base
./run-all.sh --changelog      # journal des changements
./run-all.sh --help
```

## Préparer PostgreSQL et Odoo (étape 5)

1. L'utilisateur PostgreSQL doit pouvoir créer une base :
   `sudo -u postgres createuser --createdb "$USER"` (ou un rôle équivalent).
2. Le module doit se trouver dans l'`addons_path` d'Odoo, **dans un dossier nommé
   `rlq_survey_report`**. Soit `ODOO_CONF` (un `odoo.conf` qui le contient), soit `ODOO_ADDONS`.
3. Le mot de passe PostgreSQL, s'il en faut un : variable `PGPASSWORD` ou `~/.pgpass`.
   Il n'est jamais lu dans le fichier de configuration du script.

## Configuration

Fichiers lus dans cet ordre (le script dit lesquels il a lus) : `/etc/default/run-all.conf`,
puis `~/.run-all.cfg`. Les options de la ligne de commande ont priorité. Modèle commenté :
`scripts/run-all.conf.exemple`.

## Sécurité de la base de test

- Le nom doit commencer par `test` ou `rlq_test` (lettres, chiffres, `_`) : **tout autre nom est
  refusé**, avant toute commande. Seule cette base est supprimée.
- La base est supprimée même si les tests échouent ou si on interrompt avec Ctrl+C, sauf avec
  `--garder-bd`. Une base du même nom déjà présente est supprimée puis recréée.

## Journaux

Chaque étape écrit son journal complet dans un dossier temporaire (le chemin est affiché à la
fin). En cas d'échec, les 25 dernières lignes sont montrées. Pour l'étape 5, le journal contient
la commande `odoo-bin` exacte, utile pour la relancer à la main.

## À savoir

- `tests/test_wizard.py` **n'a jamais été exécuté sur une vraie instance Odoo** avant ce script :
  la première exécution peut révéler des échecs. Les envoyer (journal de l'étape 5) permet de les
  corriger.
- `ruff.toml` ne retient que les règles qui détectent de vrais bogues ; le style est laissé de côté.
- Installer ruff : `pip install ruff`, ou indiquer un binaire avec `RUFF_BIN`.
