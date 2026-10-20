#!/usr/bin/env bash
# Copyright (C) 2026 Services-Conseils Linux  (Martial@Bigras.ca)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
# =============================================================================
# run-all.sh - Lance TOUTES les vérifications du module rlq_survey_report
# =============================================================================
# Résumé des versions (détail complet : doc/run-all.changelog.txt) :
#   1.2.20261019.202050 - copyright header (AGPL-3 or later); standalone tests: tests.test_followup_report added (module 1.113.0, 1.114.0)
#   1.1.20261016.114848 - standalone tests: tests.test_email_check added (invalid e-mail addresses, module 1.109.0)
#   1.0.20261002.131909 - version initiale : ruff, syntaxe et manifeste, tests autonomes,
#                 base PostgreSQL de test et tests Odoo
#
# Étapes : 1 outils - 2 ruff - 3 syntaxe et manifeste - 4 tests autonomes -
#          5 base PostgreSQL de test + tests Odoo (base supprimée ensuite)
# Configuration : /etc/default/run-all.conf puis ~/.run-all.cfg ; les options de
# la ligne de commande ont priorité. Voir scripts/LISEZMOI.md.
# =============================================================================

VERSION="1.2.20261019.202050"
PROGRAMME="run-all"

set -u
set -o pipefail
# Ne laisser AUCUN fichier de cache dans le module (il sera déployé tel quel) :
# pas de __pycache__ (tests autonomes) ni de .ruff_cache (ruff --no-cache plus bas).
export PYTHONDONTWRITEBYTECODE=1

RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FICHIER_CHANGELOG="$RACINE/doc/$PROGRAMME.changelog.txt"
CONF_SYSTEME="/etc/default/$PROGRAMME.conf"
CONF_UTILISATEUR="${HOME:-/nonexistent}/.$PROGRAMME.cfg"

# --- Valeurs par défaut (écrasées par les fichiers de configuration, puis par la
#     ligne de commande). PG_* vides = valeurs par défaut de libpq (socket local).
BD_NOM="rlq_test"
PG_HOTE=""
PG_PORT=""
PG_UTILISATEUR=""
ODOO_BIN="odoo-bin"
ODOO_ADDONS=""
ODOO_CONF=""
ODOO_TEST_TAGS="/rlq_survey_report"
RUFF_BIN=""
THEME="auto"          # auto | clair | sombre : couleur des numéros de version (--changelog)
GARDER_BD="non"       # oui | non
SANS_ODOO="non"       # oui | non

# --- Options de la ligne de commande (appliquées APRÈS les fichiers de configuration)
CLI_BD=""
CLI_GARDER_BD=""
CLI_SANS_ODOO=""
ACTION="tout"         # tout | changelog | aide | version | supprimer

CONFS_LUES=()
CONFS_ABSENTES=()
BD_CREEE=0
ETAPE_NUM=0
ETAPE_NOM=""
ETAPE_LOG=""
RESULTATS=()
PYTHON="python3"
RUFF_CMD=()
PG_ARGS=()
DOSSIER_JOURNAL=""
# Couleurs vides par défaut : avert()/erreur() servent déjà pendant la lecture des
# options et de la configuration, AVANT init_couleurs() (qui a besoin de THEME, lu
# dans la configuration) - sans ces valeurs, « set -u » ferait planter le script.
GRAS=""; ROUGE=""; VERT=""; JAUNE=""; RESET=""; COULEUR_VERSION=""

# ------------------------------------------------------------------ affichage
init_couleurs() {
    if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
        GRAS=$'\033[1m'; ROUGE=$'\033[31m'; VERT=$'\033[32m'; JAUNE=$'\033[33m'; RESET=$'\033[0m'
        local theme="$THEME"
        if [[ "$theme" == "auto" ]]; then
            # COLORFGBG = « premier-plan;fond » (souvent NON défini : d'où ${...:-}, sans
            # quoi « set -u » fait planter le script sous un vrai terminal). Un fond de 0 à
            # 6 ou 8 est sombre ; non défini = sombre, le cas le plus courant.
            local fond="${COLORFGBG:-}"; fond="${fond##*;}"
            case "$fond" in 0|1|2|3|4|5|6|8|"") theme="sombre" ;; *) theme="clair" ;; esac
        fi
        if [[ "$theme" == "clair" ]]; then COULEUR_VERSION=$'\033[1;34m'; else COULEUR_VERSION=$'\033[1;33m'; fi
    else
        GRAS=""; ROUGE=""; VERT=""; JAUNE=""; RESET=""; COULEUR_VERSION=""
    fi
}

avert() { printf '%s⚠ %s%s\n' "$JAUNE" "$*" "$RESET" >&2; }
erreur() { printf '%s✘ %s%s\n' "$ROUGE" "$*" "$RESET" >&2; }

usage() {
    cat << EOF
Usage : run-all.sh [OPTIONS]

Lance toutes les vérifications du module rlq_survey_report : ruff, syntaxe et
manifeste, tests autonomes, puis - si PostgreSQL et Odoo sont disponibles -
création d'une base PostgreSQL de test et exécution des tests Odoo.

Options (ordre alphabétique) :
  --bd NOM        nom de la base de test (défaut : $BD_NOM). Doit commencer par
                  « test » ou « rlq_test » : garde-fou contre un accident.
  --changelog     affiche le journal des changements
  --garder-bd     ne supprime pas la base de test à la fin
  --help          affiche cette aide
  --sans-odoo     saute l'étape PostgreSQL / Odoo
  --supprimer-bd  supprime seulement la base de test, puis quitte
  --version       affiche la version

Configuration : lue dans $CONF_SYSTEME puis $CONF_UTILISATEUR ;
les options de la ligne de commande ont priorité. Modèle : scripts/run-all.conf.exemple
Code de sortie : 0 = tout est bon ; 1 = au moins une étape en échec ; 2 = option invalide.
EOF
}

afficher_changelog() {
    trap 'exit 0' PIPE   # « run-all.sh --changelog | head » ne doit pas faire de bruit
    if [[ ! -r "$FICHIER_CHANGELOG" ]]; then
        erreur "journal introuvable : $FICHIER_CHANGELOG"
        exit 1
    fi
    if [[ -n "$COULEUR_VERSION" ]]; then
        sed -E "s/^(Version [0-9][0-9.]*)/${COULEUR_VERSION}\\1${RESET}/" "$FICHIER_CHANGELOG" 2>/dev/null
    else
        cat "$FICHIER_CHANGELOG" 2>/dev/null
    fi
    exit 0
}

# --------------------------------------------------------------- configuration
charger_conf() {
    local fichier="$1" ligne cle val
    if [[ ! -r "$fichier" ]]; then CONFS_ABSENTES+=("$fichier"); return 0; fi
    CONFS_LUES+=("$fichier")
    while IFS= read -r ligne || [[ -n "$ligne" ]]; do
        ligne="${ligne%%#*}"
        [[ "$ligne" == *=* ]] || continue
        cle="${ligne%%=*}"; val="${ligne#*=}"
        cle="${cle//[[:space:]]/}"
        val="${val#"${val%%[![:space:]]*}"}"; val="${val%"${val##*[![:space:]]}"}"
        val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
        case "$cle" in
            BD_NOM|PG_HOTE|PG_PORT|PG_UTILISATEUR|ODOO_BIN|ODOO_ADDONS|ODOO_CONF|ODOO_TEST_TAGS|RUFF_BIN|THEME|GARDER_BD|SANS_ODOO)
                printf -v "$cle" '%s' "$val" ;;
            *) avert "clé inconnue ignorée dans $fichier : $cle" ;;
        esac
    done < "$fichier"
}

lire_configuration() {
    charger_conf "$CONF_SYSTEME"
    charger_conf "$CONF_UTILISATEUR"
    [[ -n "$CLI_BD" ]] && BD_NOM="$CLI_BD"
    [[ -n "$CLI_GARDER_BD" ]] && GARDER_BD="$CLI_GARDER_BD"
    [[ -n "$CLI_SANS_ODOO" ]] && SANS_ODOO="$CLI_SANS_ODOO"
    PG_ARGS=()
    [[ -n "$PG_HOTE" ]] && PG_ARGS+=(-h "$PG_HOTE")
    [[ -n "$PG_PORT" ]] && PG_ARGS+=(-p "$PG_PORT")
    [[ -n "$PG_UTILISATEUR" ]] && PG_ARGS+=(-U "$PG_UTILISATEUR")
    return 0
}

resume_configuration() {
    local lus="aucun" absents="aucun"
    (( ${#CONFS_LUES[@]} )) && lus="${CONFS_LUES[*]}"
    (( ${#CONFS_ABSENTES[@]} )) && absents="${CONFS_ABSENTES[*]}"
    printf 'Configuration lue : %s (absents : %s)\n' "$lus" "$absents"
    printf 'Options : base=%s ; PostgreSQL=%s ; odoo-bin=%s ; garder-bd=%s ; sans-odoo=%s\n' \
        "$BD_NOM" "${PG_HOTE:-socket local}${PG_PORT:+:$PG_PORT}${PG_UTILISATEUR:+ (utilisateur $PG_UTILISATEUR)}" \
        "$ODOO_BIN" "$GARDER_BD" "$SANS_ODOO"
}

# ---------------------------------------------------------------------- étapes
etape() {
    ETAPE_NUM=$((ETAPE_NUM + 1))
    ETAPE_NOM="$1"
    local slug
    slug="$(printf '%s' "$1" | tr 'A-Z ' 'a-z-' | tr -cd 'a-z0-9-')"
    ETAPE_LOG="$DOSSIER_JOURNAL/$(printf '%02d' "$ETAPE_NUM")-$slug.log"
    : > "$ETAPE_LOG"
    printf '\n%s== Étape %d : %s ==%s\n' "$GRAS" "$ETAPE_NUM" "$ETAPE_NOM" "$RESET"
}

fin_etape() {   # fin_etape OK|ECHEC|IGNORE "détail"
    local etat="$1" detail="${2:-}" couleur="$VERT" etiquette="OK"
    case "$etat" in
        ECHEC)  couleur="$ROUGE"; etiquette="ÉCHEC" ;;
        IGNORE) couleur="$JAUNE"; etiquette="IGNORÉ" ;;
    esac
    RESULTATS+=("$etat|$ETAPE_NOM|$detail")
    printf '%s[%s]%s %s\n' "$couleur" "$etiquette" "$RESET" "$detail"
    if [[ "$etat" == "ECHEC" && -s "$ETAPE_LOG" ]]; then
        printf '%s--- fin du journal (%s) ---%s\n' "$JAUNE" "$ETAPE_LOG" "$RESET"
        tail -n 25 "$ETAPE_LOG"
    fi
}

etape_outils() {
    etape "Outils"
    if ! command -v "$PYTHON" > /dev/null 2>&1; then
        fin_etape ECHEC "python3 introuvable"; return 1
    fi
    local detail
    detail="$("$PYTHON" --version 2>&1)"
    RUFF_CMD=()
    if [[ -n "$RUFF_BIN" ]]; then
        if [[ -x "$RUFF_BIN" ]]; then RUFF_CMD=("$RUFF_BIN")
        else fin_etape ECHEC "RUFF_BIN n'est pas exécutable : $RUFF_BIN"; return 1; fi
    elif command -v ruff > /dev/null 2>&1; then RUFF_CMD=(ruff)
    elif "$PYTHON" -m ruff --version > /dev/null 2>&1; then RUFF_CMD=("$PYTHON" -m ruff)
    fi
    if (( ${#RUFF_CMD[@]} )); then detail="$detail ; $("${RUFF_CMD[@]}" --version 2>&1)"
    else detail="$detail ; ruff introuvable (pip install ruff, ou RUFF_BIN)"; fi
    if [[ "$(basename "$RACINE")" != "rlq_survey_report" ]]; then
        avert "le dossier du module s'appelle « $(basename "$RACINE") » : Odoo exige « rlq_survey_report »"
    fi
    fin_etape OK "$detail"
}

etape_ruff() {
    etape "ruff"
    if (( ! ${#RUFF_CMD[@]} )); then fin_etape IGNORE "ruff introuvable (pip install ruff, ou RUFF_BIN)"; return 0; fi
    if (cd "$RACINE" && "${RUFF_CMD[@]}" check --no-cache .) >> "$ETAPE_LOG" 2>&1; then
        fin_etape OK "$(tail -n 1 "$ETAPE_LOG")"
    else
        fin_etape ECHEC "ruff a signalé des problèmes"; return 1
    fi
}

etape_syntaxe() {
    etape "Syntaxe et manifeste"
    "$PYTHON" - "$RACINE" >> "$ETAPE_LOG" 2>&1 << 'PYEOF'
import ast, pathlib, re, sys
from xml.dom import minidom

racine = pathlib.Path(sys.argv[1])
problemes = []

fichiers_py = sorted(p for p in racine.rglob("*.py") if "__pycache__" not in p.parts)
for p in fichiers_py:
    try:
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except SyntaxError as exc:
        problemes.append(f"syntaxe Python : {p.relative_to(racine)} ligne {exc.lineno} : {exc.msg}")

fichiers_xml = sorted(p for p in racine.rglob("*.xml") if "__pycache__" not in p.parts)
for p in fichiers_xml:
    try:
        minidom.parse(str(p))
    except Exception as exc:
        problemes.append(f"XML mal formé : {p.relative_to(racine)} : {exc}")

manifeste = {}
try:
    manifeste = ast.literal_eval((racine / "__manifest__.py").read_text(encoding="utf-8"))
except Exception as exc:
    problemes.append(f"manifeste illisible : {exc}")

if manifeste:
    version = str(manifeste.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+\.\d+", version):
        problemes.append(f"version du manifeste invalide : {version!r}")
    for rel in manifeste.get("data", []):
        if not (racine / rel).exists():
            problemes.append(f"fichier du manifeste (data) introuvable : {rel}")
    for lot in manifeste.get("assets", {}).values():
        for ref in lot:
            rel = ref.split("/", 1)[1] if "/" in ref else ref
            if not (racine / rel).exists():
                problemes.append(f"fichier du manifeste (assets) introuvable : {ref}")

for init in (racine / "__init__.py", racine / "models" / "__init__.py"):
    if init.exists():
        for m in re.finditer(r"^\s*from\s+\.(\w*)\s+import\s+(\w+)", init.read_text(encoding="utf-8"), re.M):
            base = init.parent / m.group(1) if m.group(1) else init.parent
            if not ((base / f"{m.group(2)}.py").exists() or (base / m.group(2)).is_dir()):
                problemes.append(f"{init.relative_to(racine)} importe « {m.group(2)} », introuvable")

print(f"{len(fichiers_py)} fichiers Python, {len(fichiers_xml)} fichiers XML, "
      f"manifeste version {manifeste.get('version', '?')}")
for pb in problemes:
    print("PROBLÈME :", pb)
sys.exit(1 if problemes else 0)
PYEOF
    if (( $? == 0 )); then fin_etape OK "$(head -n 1 "$ETAPE_LOG")"
    else fin_etape ECHEC "voir le journal"; return 1; fi
}

etape_tests_autonomes() {
    etape "Tests autonomes"
    if (cd "$RACINE" && "$PYTHON" -m unittest tests.test_report_builder tests.test_email_check tests.test_followup_report) >> "$ETAPE_LOG" 2>&1; then
        fin_etape OK "$(grep -E '^Ran [0-9]+ tests?' "$ETAPE_LOG" | tail -n 1) - OK"
    else
        fin_etape ECHEC "des tests autonomes échouent"; return 1
    fi
}

# ------------------------------------------------------------- base de test
nom_bd_valide() { [[ "$BD_NOM" =~ ^(test|rlq_test)[A-Za-z0-9_]*$ ]]; }

pg() { psql ${PG_ARGS[@]+"${PG_ARGS[@]}"} "$@"; }

supprimer_bd() {
    dropdb ${PG_ARGS[@]+"${PG_ARGS[@]}"} --if-exists "$BD_NOM" >> "${ETAPE_LOG:-/dev/null}" 2>&1
}

nettoyer() {   # appelée à la sortie, même après une interruption
    if (( BD_CREEE )) && [[ "$GARDER_BD" != "oui" ]]; then
        if supprimer_bd; then printf 'Base de test « %s » supprimée.\n' "$BD_NOM"
        else avert "impossible de supprimer la base « $BD_NOM » : à faire à la main (dropdb $BD_NOM)"; fi
    elif (( BD_CREEE )); then
        printf 'Base de test « %s » conservée (--garder-bd) : à supprimer avec run-all.sh --supprimer-bd --bd %s\n' "$BD_NOM" "$BD_NOM"
    fi
}

etape_odoo() {
    etape "Base PostgreSQL de test et tests Odoo"
    if [[ "$SANS_ODOO" == "oui" ]]; then fin_etape IGNORE "demandé (--sans-odoo)"; return 0; fi
    local manquants=() outil
    for outil in psql createdb dropdb; do command -v "$outil" > /dev/null 2>&1 || manquants+=("$outil"); done
    command -v "$ODOO_BIN" > /dev/null 2>&1 || [[ -x "$ODOO_BIN" ]] || manquants+=("$ODOO_BIN")
    if (( ${#manquants[@]} )); then
        fin_etape IGNORE "outils absents : ${manquants[*]} (voir scripts/LISEZMOI.md)"; return 0
    fi
    if ! nom_bd_valide; then
        fin_etape ECHEC "refus : le nom de base « $BD_NOM » doit commencer par « test » ou « rlq_test » (lettres, chiffres, _)"
        return 1
    fi
    if ! pg -d postgres -tAc "select 1" >> "$ETAPE_LOG" 2>&1; then
        fin_etape ECHEC "connexion à PostgreSQL impossible (PG_HOTE/PG_PORT/PG_UTILISATEUR, PGPASSWORD ou ~/.pgpass ?)"
        return 1
    fi
    local existe
    existe="$(pg -d postgres -tAc "select 1 from pg_database where datname='$BD_NOM'" 2>> "$ETAPE_LOG")"
    if [[ "$existe" == "1" ]]; then
        printf 'La base « %s » existe déjà : elle est supprimée puis recréée.\n' "$BD_NOM"
        supprimer_bd || { fin_etape ECHEC "impossible de supprimer l'ancienne base « $BD_NOM »"; return 1; }
    fi
    if ! createdb ${PG_ARGS[@]+"${PG_ARGS[@]}"} -E UTF8 -T template0 "$BD_NOM" >> "$ETAPE_LOG" 2>&1; then
        fin_etape ECHEC "création de la base « $BD_NOM » impossible (l'utilisateur PostgreSQL a-t-il le droit CREATEDB ?)"
        return 1
    fi
    BD_CREEE=1
    printf 'Base de test « %s » créée. Installation du module et tests Odoo (peut prendre plusieurs minutes)...\n' "$BD_NOM"

    local cmd=("$ODOO_BIN")
    [[ -n "$ODOO_CONF" ]] && cmd+=(-c "$ODOO_CONF")
    [[ -n "$ODOO_ADDONS" ]] && cmd+=("--addons-path=$ODOO_ADDONS")
    [[ -n "$PG_HOTE" ]] && cmd+=("--db_host=$PG_HOTE")
    [[ -n "$PG_PORT" ]] && cmd+=("--db_port=$PG_PORT")
    [[ -n "$PG_UTILISATEUR" ]] && cmd+=("--db_user=$PG_UTILISATEUR")
    cmd+=(-d "$BD_NOM" -i rlq_survey_report --test-enable "--test-tags=$ODOO_TEST_TAGS" --stop-after-init --without-demo=all --log-level=test)
    printf 'Commande : %s\n' "${cmd[*]}" >> "$ETAPE_LOG"
    "${cmd[@]}" >> "$ETAPE_LOG" 2>&1
    local rc=$?

    # Résumé des tests lu dans le journal d'Odoo : « N failed, M error(s) of T tests ».
    local ligne echecs erreurs total resume="résumé introuvable dans le journal d'Odoo"
    ligne="$(sed -nE 's/.* ([0-9]+) failed, ([0-9]+) error\(s\) of ([0-9]+) tests.*/\1 \2 \3/p' "$ETAPE_LOG" | tail -n 1)"
    if [[ -n "$ligne" ]]; then
        read -r echecs erreurs total <<< "$ligne"
        resume="$total tests Odoo : $echecs échec(s), $erreurs erreur(s)"
        if (( total == 0 )); then
            fin_etape ECHEC "aucun test Odoo exécuté : vérifiez que le module est dans l'addons_path (ODOO_ADDONS / ODOO_CONF) et ODOO_TEST_TAGS ($ODOO_TEST_TAGS)"
            return 1
        fi
    fi
    if (( rc == 0 )); then fin_etape OK "$resume"
    else fin_etape ECHEC "odoo-bin a retourné le code $rc ; $resume"; return 1; fi
}

resume_final() {
    local ligne etat nom detail couleur etiquette echec=0
    printf '\n%s== Résumé ==%s\n' "$GRAS" "$RESET"
    for ligne in "${RESULTATS[@]}"; do
        etat="${ligne%%|*}"; ligne="${ligne#*|}"; nom="${ligne%%|*}"; detail="${ligne#*|}"
        case "$etat" in
            OK)     couleur="$VERT";  etiquette="OK    " ;;
            ECHEC)  couleur="$ROUGE"; etiquette="ÉCHEC "; echec=1 ;;
            *)      couleur="$JAUNE"; etiquette="IGNORÉ" ;;
        esac
        printf '  %s%s%s  %s : %s\n' "$couleur" "$etiquette" "$RESET" "$nom" "$detail"
    done
    printf 'Journaux : %s\n' "$DOSSIER_JOURNAL"
    return "$echec"
}

# ------------------------------------------------------------------- principal
while (( $# )); do
    case "$1" in
        --bd)           [[ $# -ge 2 ]] || { erreur "--bd exige un nom de base"; exit 2; }
                        CLI_BD="$2"; shift ;;
        --bd=*)         CLI_BD="${1#--bd=}" ;;
        --changelog)    ACTION="changelog" ;;
        --garder-bd)    CLI_GARDER_BD="oui" ;;
        --help|-h)      ACTION="aide" ;;
        --sans-odoo)    CLI_SANS_ODOO="oui" ;;
        --supprimer-bd) ACTION="supprimer" ;;
        --version)      ACTION="version" ;;
        *)              erreur "option inconnue : $1 (voir --help)"; exit 2 ;;
    esac
    shift
done

lire_configuration
init_couleurs

case "$ACTION" in
    version)   printf '%s %s\n' "$PROGRAMME" "$VERSION"; exit 0 ;;
    aide)      usage; exit 0 ;;
    changelog) afficher_changelog ;;
esac

printf '%s %s\n' "$PROGRAMME" "$VERSION"
resume_configuration

DOSSIER_JOURNAL="${TMPDIR:-/tmp}/run-all-$(date +%Y%m%d.%H%M%S)-$$"
mkdir -p "$DOSSIER_JOURNAL" || { erreur "impossible de créer $DOSSIER_JOURNAL"; exit 1; }
trap nettoyer EXIT
trap 'exit 130' INT TERM

if [[ "$ACTION" == "supprimer" ]]; then
    etape "Suppression de la base de test"
    if ! nom_bd_valide; then
        fin_etape ECHEC "refus : le nom de base « $BD_NOM » doit commencer par « test » ou « rlq_test »"
    elif ! command -v dropdb > /dev/null 2>&1; then
        fin_etape ECHEC "dropdb introuvable (client PostgreSQL non installé)"
    elif supprimer_bd; then
        fin_etape OK "base « $BD_NOM » supprimée (ou déjà absente)"
    else
        fin_etape ECHEC "suppression impossible"
    fi
    resume_final; exit $?
fi

etape_outils || true
etape_ruff || true
etape_syntaxe || true
etape_tests_autonomes || true
etape_odoo || true
resume_final
exit $?
