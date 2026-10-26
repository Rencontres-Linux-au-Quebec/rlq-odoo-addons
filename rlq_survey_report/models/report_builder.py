# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
report_builder.py
==================

Fonctions de mise en forme HTML, volontairement indépendantes de l'ORM
Odoo : elles ne reçoivent que des structures Python simples (listes,
dictionnaires) déjà extraites des enregistrements survey.* par
rlq_survey_report_wizard.py.

Ce découpage permet de tester et d'ajuster la présentation du rapport
sans toucher au code d'extraction ORM (le plus susceptible de nécessiter
des ajustements selon la version exacte du module "survey" installé).

Reprend la logique déjà validée du programme autonome
"rapport_sondage-1_10.py" (statistiques descriptives, ventilation
dépliable, tooltips CSS rapides, thèmes) - voir ce fichier pour
l'historique des choix de conception.
"""

import hashlib
import math
import re
import statistics
import unicodedata
from collections import defaultdict


# ---------------------------------------------------------------------------
# Utilitaires de texte
# ---------------------------------------------------------------------------

def normaliser_nom(texte):
    texte = str(texte or "").strip()
    nfkd = unicodedata.normalize("NFKD", texte)
    sans_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sans_accents.lower()


def slug(texte):
    s = normaliser_nom(texte)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


_JETON_PRESENTATEUR_DEBUT = "\u27e6RLQ-PRESENTATEUR:"
_JETON_PRESENTATEUR_FIN = "\u27e7"


def duree_humaine(secondes):
    """Formate un nombre de secondes en texte lisible (ex. "45 s",
    "3 min 12 s", "1 h 05 min") - utilisé pour le temps de réponse d'UNE
    soumission (voir colonne_par_ui/p["colonnes"] dans le wizard).
    Retourne None si `secondes` est vide/nul/négatif (durée inconnue ou
    incohérente - ex. horodatages de fin antérieurs à ceux de début)."""
    if not secondes or secondes < 0:
        return None
    secondes = int(round(secondes))
    heures, reste = divmod(secondes, 3600)
    minutes, sec = divmod(reste, 60)
    if heures:
        return f"{heures} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min {sec:02d} s"
    return f"{sec} s"


def jeton_presentateur(nom):
    """Jeton stable et déterministe (dérivé du nom par hachage - aucun état
    partagé nécessaire entre les différents endroits du rapport qui
    l'utilisent) substitué à la place du nom réel d'un présentateur,
    partout où ce nom doit rester visible malgré une anonymisation active
    (le wizard décide où - voir _anonymiser_html() et
    _resoudre_jetons_presentateurs() dans rlq_survey_report_wizard.py).

    Pourquoi : le remplacement global par pseudonyme (_anonymiser_html())
    ne connaît que le TEXTE du nom, pas le CONTEXTE où il apparaît - il ne
    peut donc pas, par lui-même, épargner un nom dans un endroit précis
    (ex. "Appréciation des présentateurs") tout en l'anonymisant ailleurs
    (ex. "Liste des participants") si la même personne est à la fois
    présentateur et répondante. Remplacer le nom par ce jeton AVANT ce
    remplacement global rend l'occurrence protégée structurellement
    immunisée (elle ne contient plus le texte recherché) ; le jeton est
    ensuite résolu vers le nom réel, à la toute fin, que le rapport soit
    anonymisé ou non.

    Caractères Unicode rares (⟦⟧) plutôt que des caractères de contrôle :
    plus faciles à repérer si un jeton restait par erreur dans un rapport
    livré (visible et reconnaissable, plutôt qu'invisible), et sans risque
    d'être altérés par echapper()/echapper_attr() (aucun caractère
    &<>" à échapper dans ⟦, ⟧, ou l'empreinte hexadécimale)."""
    empreinte = hashlib.md5(nom.encode("utf-8")).hexdigest()[:12]
    return f"{_JETON_PRESENTATEUR_DEBUT}{empreinte}{_JETON_PRESENTATEUR_FIN}"


_JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def jour_semaine(date_iso):
    """Retourne le jour de la semaine en français (ex. 'mardi') pour une date
    au format AAAA-MM-JJ, ou None si le texte n'est pas une date valide."""
    if not date_iso:
        return None
    try:
        from datetime import date as _date
        annee, mois, jour = (int(p) for p in str(date_iso).split("-"))
        return _JOURS_FR[_date(annee, mois, jour).weekday()]
    except (ValueError, TypeError, IndexError):
        return None


def retirer_divs_par_prefixe_classe(html, prefixe_classe):
    """Retire, dans `html`, chaque <div class='PREFIXE...'> avec gestion
    CORRECTE de l'imbrication - contrairement à une expression régulière
    non gourmande (`<div...>.*?</div>`), qui s'arrêterait au tout premier
    </div> rencontré, même s'il appartient à un <div> imbriqué à
    l'intérieur plutôt qu'à celui qu'on cherche à retirer (exactement le
    cas ici : .evo-section/.evo-serie contiennent plusieurs niveaux de
    <div> imbriqués pour les barres du graphique). Utilisé pour retirer
    du PDF les graphiques en barres CSS à mise en page flex, celle-ci
    étant source de bogues connus avec wkhtmltopdf (déjà rencontrés pour
    les histogrammes) et vraisemblablement responsable de pages presque
    vides observées dans un PDF généré."""
    motif_ouverture = re.compile(rf"<div class='{re.escape(prefixe_classe)}[^']*'>")
    morceaux = []
    i = 0
    while True:
        m = motif_ouverture.search(html, i)
        if not m:
            morceaux.append(html[i:])
            break
        morceaux.append(html[i:m.start()])
        profondeur = 1
        pos = m.end()
        while profondeur > 0:
            prochain_ouvrant = html.find("<div", pos)
            prochain_fermant = html.find("</div>", pos)
            if prochain_fermant == -1:
                pos = len(html)  # structure inattendue : on s'arrête prudemment
                break
            if prochain_ouvrant != -1 and prochain_ouvrant < prochain_fermant:
                profondeur += 1
                pos = prochain_ouvrant + 4
            else:
                profondeur -= 1
                pos = prochain_fermant + 6
        i = pos
    return "".join(morceaux)


def texte_brut_depuis_html(html_source):
    """Retire grossièrement les balises HTML d'un champ Html (ex. la
    description d'un événement) pour un affichage en texte brut - un
    retrait par expression régulière plutôt qu'un analyseur HTML complet
    (suffisant ici : le résultat est immédiatement échappé de nouveau par
    l'appelant avant insertion dans le rapport, donc aucun risque même si
    le retrait est imparfait sur un HTML très particulier)."""
    if not html_source:
        return ""
    sans_balises = re.sub(r"<[^>]+>", " ", str(html_source))
    return re.sub(r"\s+", " ", sans_balises).strip()


def echapper(texte):
    return (
        str(texte if texte is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_TABLE_CHIFFRES_GRAS = str.maketrans("0123456789", "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗")


def chiffres_gras(texte):
    """Convertit les chiffres ASCII d'un texte en leur équivalent Unicode
    "gras" (mathematical bold digits, U+1D7CE-U+1D7D7) - un vrai caractère,
    pas une balise HTML - pour simuler visuellement du gras dans un contexte
    où le HTML n'est pas interprété (ex. le message d'une notification
    Odoo, qui s'est avéré afficher du texte brut échappé malgré une
    tentative précédente d'y laisser des balises <strong>)."""
    return str(texte if texte is not None else "").translate(_TABLE_CHIFFRES_GRAS)


def echapper_attr(texte):
    return echapper(texte).replace('"', "&quot;")


def html_reponses_courriel(blocs):
    """HTML du corps d'un courriel qui rappelle à un participant ses propres réponses
    (v1.94.0). `blocs` = [(titre de la question, [réponses en texte])] dans l'ordre du
    sondage ; une question sans réponse est omise. Tout est échappé (une réponse libre
    peut contenir du HTML), les retours à la ligne d'une réponse longue sont conservés.
    Retourne une chaîne vide s'il n'y a rien à montrer."""
    morceaux = []
    for titre, reponses in blocs:
        reponses = [str(r) for r in (reponses or []) if r is not None and str(r).strip()]
        if not reponses:
            continue
        corps = "<br/>".join(echapper(r.strip()).replace("\n", "<br/>") for r in reponses)
        morceaux.append(
            '<p style="margin:0 0 4px 0;"><strong>' + echapper(re.sub(r"\s+", " ", str(titre or "")).strip())
            + '</strong></p><p style="margin:0 0 14px 12px;">' + corps + "</p>"
        )
    return "".join(morceaux)


_COURRIEL_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")


def courriels_valides(texte):
    """Adresses de courriel valides d'un texte (séparées par des virgules, points-virgules ou
    espaces), dans l'ordre, sans doublon ; les morceaux invalides sont ignorés (v1.95.0)."""
    vus = []
    for morceau in re.split(r"[,;\s]+", str(texte or "")):
        morceau = morceau.strip()
        if morceau and _COURRIEL_RE.match(morceau) and morceau.lower() not in [v.lower() for v in vus]:
            vus.append(morceau)
    return vus


def destinataire_alerte_inscriptions(courriel_evenement, courriel_parametre, courriel_societe):
    """Destinataire de l'avertissement « N inscriptions atteintes » (v1.95.0), par ordre de
    priorité : le courriel propre à l'événement, sinon le paramètre système
    rlq_survey_report.courriel_inscriptions, sinon le courriel par défaut d'Odoo (celui de la
    société). Retourne (adresses séparées par une virgule, source) avec source = "evenement",
    "parametre" ou "societe" ; (None, None) si aucune adresse valide."""
    for source, valeur in (("evenement", courriel_evenement), ("parametre", courriel_parametre),
                           ("societe", courriel_societe)):
        adresses = courriels_valides(valeur)
        if adresses:
            return ", ".join(adresses), source
    return None, None


def sujet_alerte_inscriptions(nom_evenement, nombre):
    """Sujet du courriel d'avertissement (v1.95.0)."""
    nom = re.sub(r"\s+", " ", str(nom_evenement or "")).strip()
    return "%d inscription%s : %s" % (nombre, "s" if nombre > 1 else "", nom)


def palier_alerte(nombre, seuil, repeter=False, dernier=0):
    """Palier à avertir (v1.105.0) ou None. Sans répétition : le seuil lui-même, une fois atteint. Avec répétition : le plus grand
    multiple de `seuil` (seuil, 2×seuil…) atteint, s'il dépasse le `dernier` palier déjà avisé. Seuil invalide (< 1) : None."""
    try:
        nombre, seuil, dernier = int(nombre or 0), int(seuil or 0), int(dernier or 0)
    except (TypeError, ValueError):
        return None
    if seuil < 1 or nombre < seuil:
        return None
    palier = (nombre // seuil) * seuil if repeter else seuil
    return palier if palier > dernier else None


def html_alerte_inscriptions(nom_evenement, debut, nombre, seuil, url=None, repeter=False):
    """Corps HTML du courriel d'avertissement (v1.95.0). AUCUNE donnée personnelle : seulement
    le nom de l'événement, sa date, le nombre d'inscriptions et le seuil (Loi 25). Tout est
    échappé ; `url` (lien vers l'événement dans Odoo) est facultatif."""
    nom = echapper(re.sub(r"\s+", " ", str(nom_evenement or "")).strip())
    lignes = [
        "<p>Bonjour,</p>",
        '<p>L\'événement <strong>%s</strong>%s a atteint <strong>%d inscription%s</strong> '
        "(seuil demandé : %d).</p>" % (nom, (" (" + echapper(str(debut)) + ")") if debut else "", nombre,
                                       "s" if nombre > 1 else "", seuil),
        ("<p>Un nouveau courriel partira à chaque multiple de %d inscriptions ; il se réarme si vous modifiez ce nombre.</p>" % seuil) if repeter
        else "<p>Ce courriel n'est envoyé qu'une fois ; il se réarme si vous modifiez le seuil de l'événement.</p>",
    ]
    if url:
        lignes.append('<p><a href="%s">Ouvrir l\'événement dans Odoo</a></p>' % echapper_attr(url))
    return "".join(lignes)


def sujet_alerte_sondage(nom_evenement, personne):
    """Sujet du courriel « sondage complété » (v1.96.0)."""
    nom = re.sub(r"\s+", " ", str(nom_evenement or "")).strip()
    qui = re.sub(r"\s+", " ", str(personne or "")).strip() or "une personne"
    return "Sondage complété par %s : %s" % (qui, nom)


PREFIXE_GROUPES = "RLQ-"


def nom_groupe_rlq(nom):
    """Nom d'un groupe créé par le module (v1.104.0) : commence toujours par « RLQ- » (Rencontres Linux au Québec).
    « JPOL26-Présentiel » -> « RLQ-JPOL26-Présentiel » ; « rlq-jpol26 » -> « RLQ-jpol26 » (casse du préfixe corrigée, jamais doublé) ;
    espaces superflus retirés ; vide si rien ne suit « RLQ- » (aucun groupe sans nom clair)."""
    n = re.sub(r"\s+", " ", str(nom or "")).strip()
    n = re.sub(r"^rlq[-\s]*", "", n, flags=re.IGNORECASE).strip(" -")
    return PREFIXE_GROUPES + n if n else ""


def nom_groupe_billet(prefixe, nom_billet):
    """Nom du groupe Odoo des inscrits d'un type de billet : « JPOL26 » + « Bénévole » -> « RLQ-JPOL26-Bénévole » (depuis v1.104.0 le nom commence
    par « RLQ- » ; avant : « JPOL26-Bénévole »). Espaces superflus retirés ; vide si le préfixe ou le nom du billet est vide."""
    p = re.sub(r"\s+", " ", str(prefixe or "")).strip(" -")
    b = re.sub(r"\s+", " ", str(nom_billet or "")).strip()
    return nom_groupe_rlq("%s-%s" % (p, b)) if nom_groupe_rlq(p) and b else ""


def tableau_inscriptions_html(inscriptions):
    """Tableau « Dernières inscriptions » du courriel « sondage complété » (v1.97.0), le même contenu que la
    touche « I » de app-log-live.py : date, personne, billet, état, puis le sondage de confirmation
    (complété avec sa date, « NON terminé », ou « AUCUN — inscription non confirmée »). `inscriptions` :
    liste de dicts {quand, nom, billet, etat, attendu, sondage} avec sondage = None ou
    {quand, nom, titre, etat}. AUCUNE réponse ni adresse de courriel. Tout est échappé. Vide : ''."""
    def propre(t):
        return echapper(re.sub(r"\s+", " ", str(t or "")).strip())
    if not inscriptions:
        return ""
    cellule = 'style="padding:2px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top"'
    lignes = ['<p><strong>Dernières inscriptions (30 jours)</strong></p>',
              '<table style="border-collapse:collapse;font-size:13px"><tr>'
              + "".join("<th %s>%s</th>" % (cellule, t) for t in ("Inscription", "Personne", "Billet", "État", "Sondage")) + "</tr>"]
    for i in inscriptions:
        sv = i.get("sondage")
        if not i.get("attendu"):
            fin = "—"
        elif not sv:
            fin = '<span style="color:#c60"><strong>AUCUN</strong> — inscription non confirmée</span>'
        else:
            fini = sv.get("etat") == "done"
            fin = ('<span style="color:%s"><strong>%s</strong></span> : %s %s %s (%s)' % (
                "#080" if fini else "#c60", "complété" if fini else "NON terminé", propre(sv.get("quand")),
                propre(sv.get("nom") or i.get("nom")), propre(sv.get("titre")), propre(sv.get("etat"))))
        lignes.append("<tr>" + "".join("<td %s>%s</td>" % (cellule, c) for c in (
            propre(i.get("quand")), propre(i.get("nom")), propre(i.get("billet")), propre(i.get("etat")), fin)) + "</tr>")
    lignes.append("</table>")
    return "".join(lignes)


def html_alerte_sondage(nom_evenement, debut, personne, billet, titre_sondage, complets, inscrits, url=None, dernieres=None):
    """Corps HTML du courriel « sondage complété » (v1.96.0) : événement, personne, billet, sondage et
    avancement (sondages complétés sur inscriptions). AUCUNE réponse ni adresse de courriel. Tout est échappé."""
    def propre(t):
        return echapper(re.sub(r"\s+", " ", str(t or "")).strip())
    qui = propre(personne) or "Une personne"
    billet_txt = " (billet « %s »)" % propre(billet) if billet else ""
    lignes = [
        "<p>Bonjour,</p>",
        "<p><strong>%s</strong>%s a terminé le sondage « %s » de l'événement <strong>%s</strong>%s.</p>" % (
            qui, billet_txt, propre(titre_sondage), propre(nom_evenement), (" (" + echapper(str(debut)) + ")") if debut else ""),
        "<p>Sondages complétés : <strong>%d</strong> pour <strong>%d</strong> inscription%s confirmée%s.</p>" % (
            complets, inscrits, "s" if inscrits > 1 else "", "s" if inscrits > 1 else ""),
    ]
    lignes.append(tableau_inscriptions_html(dernieres))
    if url:
        lignes.append('<p><a href="%s">Ouvrir l\'événement dans Odoo</a></p>' % echapper_attr(url))
    return "".join(lignes)


def convertir_numerique(valeur_texte):
    """Extrait un nombre en tête d'une réponse type '5 =satisfait' ou
    '1 =débutant'. Retourne None si aucun nombre n'est trouvé (ex. réponse
    'Je n'étais pas là')."""
    if valeur_texte is None:
        return None
    m = re.match(r"^\s*(-?\d+(?:[.,]\d+)?)", str(valeur_texte))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def moyenne(valeurs):
    return sum(valeurs) / len(valeurs) if valeurs else None


def percentile95(valeurs):
    if not valeurs:
        return None
    s = sorted(valeurs)
    k = max(0, math.ceil(0.95 * len(s)) - 1)
    return s[k]


def stats_pourcentage_html(valeurs, echelle_min=1, echelle_max=5, inclure_nb_reponses=True, texte_brut=False):
    """Comme stats_description(), mais Min/Moy/Max/P95 exprimés en % de
    l'échelle - valeur/échelle_max*100 (0% à 0, 100% au maximum), la
    MÊME formule que barre() (le rendu graphique des barres ailleurs
    dans ce module) et que _classe_pourcentage() (dont les seuils
    100/80/40% supposent déjà cette formule). PAS ancrée à `echelle_min`
    comme une version précédente de cette fonction - signalé : une note
    de 2/5 affichait 25% ici (ancré à 1 : (2-1)/(5-1)) au lieu des 40%
    attendus (2/5) et affichés par la barre juste à côté, un vrai calcul
    incohérent entre deux éléments du même rapport, pas seulement une
    différence de présentation. `echelle_min` n'intervient donc plus
    dans ce calcul - conservé dans la signature uniquement pour ne pas
    casser les appels existants. Le code couleur (colorer_par_valeur)
    reste basé sur la valeur BRUTE, pas le pourcentage affiché - la
    signification d'une note de 4/5 ne change pas selon la façon dont on
    choisit de l'afficher.

    `texte_brut=True` : retourne du texte SANS balises HTML (pas de
    <span> de couleur) - nécessaire pour un tooltip via l'attribut
    data-rlq-tip, affiché en CSS (content: attr(...)) qui n'interprète
    jamais le HTML qu'il contiendrait, contrairement à une cellule de
    tableau normale.

    Retourne "s.o." si valeurs est vide."""
    stats = stats_description(valeurs)
    if not stats:
        return "s.o."
    def _pct(v):
        return v / echelle_max * 100 if echelle_max else 0
    txt_min = f"{_pct(stats['min']):.0f}%"
    txt_moy = f"{_pct(stats['moy']):.0f}%"
    txt_max = f"{_pct(stats['max']):.0f}%"
    txt_p95 = f"{_pct(stats['p95']):.0f}%"
    pct_ecart_type = stats["ecart_type"] / echelle_max * 100 if echelle_max else 0
    if texte_brut:
        resultat = f"Min {txt_min} · Moy {txt_moy} · Max {txt_max} · É-T {pct_ecart_type:.0f}% · P95 {txt_p95}"
    else:
        resultat = (
            f"Min {colorer_par_valeur(txt_min, num=stats['min'])} · "
            f"Moy {colorer_par_valeur(txt_moy, num=stats['moy'])} · "
            f"Max {colorer_par_valeur(txt_max, num=stats['max'])} · "
            f"É-T {pct_ecart_type:.0f}% · "
            f"P95 {colorer_par_valeur(txt_p95, num=stats['p95'])}"
        )
    if inclure_nb_reponses:
        resultat += f" · {len(valeurs)} réponse(s)"
    return resultat


def stats_description(valeurs):
    if not valeurs:
        return None
    return {
        "min": min(valeurs),
        "moy": moyenne(valeurs),
        "ecart_type": statistics.pstdev(valeurs) if len(valeurs) > 1 else 0.0,
        "max": max(valeurs),
        "p95": percentile95(valeurs),
    }


# ---------------------------------------------------------------------------
# Rendu HTML : éléments de base
# ---------------------------------------------------------------------------

def lien_ancre(anchor_id, texte_html):
    """Construit un lien vers une ancre interne du rapport. Dans le widget
    Html d'Odoo (affichage à l'écran), un simple href='#id' est intercepté
    par le routeur de l'application (qui essaie d'en faire un changement de
    page/URL) plutôt que de faire défiler jusqu'à l'ancre - d'où le clic sur
    le nom d'un participant qui semblait « ne rien faire » ou changer d'URL
    sans effet. Le gestionnaire onclick fait défiler manuellement jusqu'à
    l'élément visé et empêche le comportement par défaut du navigateur/du
    routeur. Le href='#id' est conservé comme repli (ex. si le rapport est
    ouvert hors d'Odoo, dans le fichier HTML téléchargé).

    Sécurité : anchor_id est toujours produit par slug() (lettres, chiffres
    et tirets uniquement) dans tous les appels de ce module, mais on
    l'assainit quand même ici par prudence avant de l'insérer dans un
    attribut HTML et dans une chaîne JavaScript - au cas où une valeur non
    passée par slug() lui serait un jour transmise par erreur."""
    anchor_id_sur = re.sub(r"[^a-zA-Z0-9_-]", "", str(anchor_id))
    onclick = (
        "event.preventDefault();"
        f"var e=document.getElementById('{anchor_id_sur}');"
        "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});}"
    )
    return f"<a href='#{anchor_id_sur}' onclick=\"{onclick}\">{texte_html}</a>"


def lien_date(date_str):
    """Lien vers la section de la rencontre correspondante - l'ancre
    utilisée (slug direct de la date, sans aucun préfixe) correspond à
    celle posée sur la section de la rencontre elle-même dans
    l'assemblage du rapport (rb.slug(date_rencontre))."""
    if not date_str:
        return ""
    return lien_ancre(slug(date_str), echapper(date_str))


def lien_personne(nom):
    return lien_ancre(f"personne-{slug(nom)}", echapper(nom))


def colorer_par_valeur(texte, num=None):
    """Code couleur uniforme pour toute note affichée dans le rapport (échelle
    1-5) : rouge si <= 2, jaune si > 2 et < 4, bleu si >= 4, vert si >= 5
    (donc en pratique : 1-2 rouge, 3 jaune, 4 bleu, 5 vert). 'Oui' est
    toujours vert. Si `num` n'est pas fourni, il est déduit du texte
    (ex. "5 =satisfait" -> 5), pour un rendu cohérent partout où une note
    individuelle est affichée (ventilation, tableau par participant)."""
    if texte is None or texte == "":
        return ""
    if str(texte) == "Oui":
        return f"<span class='val-positive'>{echapper(texte)}</span>"
    if num is None:
        num = convertir_numerique(texte)
    if num is not None:
        if num >= 5:
            return f"<span class='val-positive'>{echapper(texte)}</span>"
        if num >= 4:
            return f"<span class='val-bleu'>{echapper(texte)}</span>"
        if num <= 2:
            return f"<span class='val-negative'>{echapper(texte)}</span>"
        return f"<span class='val-neutre'>{echapper(texte)}</span>"
    return echapper(texte)


def _classe_couleur_1a5(valeur):
    """Retourne "vert"/"bleu"/"jaune"/"rouge" selon les mêmes seuils que
    colorer_par_valeur()/_classe_pourcentage() (échelle 1-5) - pour les
    histogrammes VERTICAUX (barres pleines, sans texte à l'intérieur),
    qui ont besoin d'une classe de COULEUR DE FOND plutôt que de
    couleur de TEXTE. Ne s'applique qu'aux questions sur une vraie
    échelle 1-5 (pas aux comptes ou pourcentages d'engagement comme le
    taux de réponse, qui n'ont pas de "bonne" ou "mauvaise" valeur au
    même sens)."""
    if valeur >= 5:
        return "vert"
    if valeur >= 4:
        return "bleu"
    if valeur <= 2:
        return "rouge"
    return "jaune"


def _classe_pourcentage(pct):
    """Seuils identiques à colorer_par_valeur() (échelle 1-5, ce
    pourcentage étant valeur/maximum*100 avec maximum=5 dans les
    usages courants - Note globale, Appréciation des présentateurs) :
    100% (5) vert, >=80% (4) bleu, <=40% (<=2) rouge, sinon (3) jaune -
    signalé : ces deux mécanismes de coloration utilisaient des seuils
    différents (90/70/60% ici, contre 2/4/5 là-bas), incohérent pour
    des valeurs affichées côte à côte dans le même rapport."""
    if pct >= 100:
        return "pct-vert"
    if pct >= 80:
        return "pct-bleu"
    if pct <= 40:
        return "pct-rouge"
    return "pct-jaune"


def barre(valeur, maximum=5, style_pourcentage=False, info_bulle=None, colorer_seuils=False):
    pourcentage = max(0, min(100, round(100 * valeur / maximum))) if valeur is not None else 0
    if valeur is None:
        libelle = "s.o."
    elif style_pourcentage:
        libelle = f"{pourcentage}%"
    else:
        libelle = f"{valeur:.1f} / {maximum}"
    classe = "barre-cadre a-tooltip" if info_bulle else "barre-cadre"
    attr = f' data-rlq-tip="{echapper_attr(info_bulle)}"' if info_bulle else ""
    classe_valeur = "barre-valeur"
    classe_remplie = "barre-remplie"
    if colorer_seuils and style_pourcentage and valeur is not None:
        classe_pct = _classe_pourcentage(pourcentage)
        classe_valeur += " " + classe_pct
        classe_remplie += " barre-remplie-" + classe_pct.replace("pct-", "")
    return (
        '<div class="barre-ligne">'
        f'<div class="{classe}"{attr}><div class="{classe_remplie}" style="width:{pourcentage}%"></div></div>'
        f'<span class="{classe_valeur}">{libelle}</span>'
        "</div>"
    )


def motif_nom_complet(texte):
    """Regex qui trouve `texte` seulement quand il n'est PAS collé à une lettre, un
    chiffre ou « _ » de part et d'autre. À la différence de \\b...\\b, elle fonctionne
    aussi quand `texte` commence ou finit par un caractère non alphanumérique : une
    limite de mot (\\b) n'existe pas entre « ) » et un espace ou un « < », donc
    \\bAndré Untel (acme.com)\\b ne correspondait JAMAIS (v1.93.0 : un participant dont
    le nom se terminait par une parenthèse restait visible dans un rapport pourtant
    anonymisé). Même chose pour un nom finissant par un point (« Jr. ») ou commençant
    par une parenthèse. Pour un texte qui commence et finit par un caractère de mot
    (le cas courant), le comportement est identique à \\b...\\b : « F » n'est jamais
    trouvé à l'intérieur de « Filtre »."""
    return re.compile(r"(?<!\w)" + re.escape(texte) + r"(?!\w)")


def remplacer_nom_complet(html, original, remplacement):
    """Remplace `original` (nom, courriel, ancre...) par `remplacement` dans `html`, sous
    ses trois formes possibles dans le HTML (échappée pour un attribut, échappée pour du
    texte, brute), uniquement quand il n'est pas collé à un caractère de mot (voir
    motif_nom_complet). `original` est normalisé en NFC ; le HTML doit déjà l'être (fait
    une seule fois par l'appelant : le HTML d'un rapport est volumineux). Le
    remplacement est littéral - aucun caractère spécial n'y est interprété."""
    original_nfc = unicodedata.normalize("NFC", original)
    for variante in (echapper_attr(original_nfc), echapper(original_nfc), original_nfc):
        html = motif_nom_complet(variante).sub(lambda _m: remplacement, html)
    return html


def construire_detail_personnes(entries, resume_html, emails=None):
    """entries : liste de (nom_affiche, date_str). Regroupe par personne
    (une ligne par personne, toutes ses dates réunies), avec lien mailto et
    champ de courriels copiable si des adresses sont connues (dict emails :
    nom-normalisé -> courriel)."""
    emails = emails or {}
    dates_par_personne = defaultdict(list)
    for nom, date_str in entries:
        dates_par_personne[nom].append(date_str)

    puces, courriels = [], []
    for nom in sorted(dates_par_personne, key=normaliser_nom):
        cle = normaliser_nom(nom)
        dates_liees = ", ".join(lien_date(d) for d in sorted(dates_par_personne[nom]) if d)
        lien_courriel = ""
        if emails.get(cle):
            courriels.append(emails[cle])
            lien_courriel = (
                f" <a class='lien-courriel' href='mailto:{echapper_attr(emails[cle])}' "
                f"title='{echapper_attr(emails[cle])}'>&#9993;</a>"
            )
        puces.append(f"<li>{lien_personne(nom)} <span class='date-oui'>({dates_liees})</span>{lien_courriel}</li>")

    champ = ""
    if courriels:
        uniques = sorted(set(courriels))
        champ = (
            f"<div class='champ-courriels'><label>Courriels ({len(uniques)}) — "
            f"cliquez pour tout sélectionner :</label>"
            f"<input type='text' readonly value=\"{echapper_attr(', '.join(uniques))}\" "
            f"onclick='this.select()'></div>"
        )
    return (
        f"<details class='detail-oui'><summary>{resume_html}</summary>"
        f"{champ}<ul class='liste-texte'>{''.join(puces)}</ul></details>"
    )


def rendu_avec_noms(nombre_html, entries, emails=None, seuil=2):
    """entries : liste de (nom_affiche, date_str)."""
    emails = emails or {}
    if not entries:
        return nombre_html
    dates_par_personne = defaultdict(list)
    for nom, date_str in entries:
        dates_par_personne[nom].append(date_str)
    if len(dates_par_personne) < seuil:
        lignes = []
        for nom in sorted(dates_par_personne, key=normaliser_nom):
            dates_txt = ", ".join(sorted(d for d in dates_par_personne[nom] if d))
            cle = normaliser_nom(nom)
            suffixe = f" - {emails[cle]}" if emails.get(cle) else ""
            lignes.append(f"{nom} ({dates_txt}){suffixe}")
        return f"<span class='a-tooltip' data-rlq-tip=\"{echapper_attr(chr(10).join(lignes))}\">{nombre_html}</span>"
    return construire_detail_personnes(entries, nombre_html, emails)


def liste_dates_simple(dates, seuil=4):
    """Comme liste_personnes_simple, mais pour une liste de dates (ex.
    l'historique de participation à vie d'un participant) - triées de
    la plus récente à la plus ancienne plutôt qu'alphabétiquement, sans
    lien cliquable (une date n'a pas de fiche à ouvrir). Le seuil est
    plus élevé que pour une liste de personnes : un historique de
    plusieurs années peut légitimement compter plus que 2 entrées avant
    qu'une liste dépliable devienne préférable à un simple texte."""
    dates_str = sorted({str(d) for d in dates}, reverse=True)
    if not dates_str:
        return ""
    if len(dates_str) < seuil:
        return ", ".join(dates_str)
    puces = "".join(f"<li>{d}</li>" for d in dates_str)
    return (
        f"<details class='detail-oui detail-inline'><summary>({len(dates_str)} dates)</summary>"
        f"<ul class='liste-texte'>{puces}</ul></details>"
    )


def liste_dates_avec_liens(paires_date_url, seuil=4):
    """Comme liste_dates_simple, mais chaque date est un lien hypertexte
    (ex. vers la fiche de configuration de l'événement correspondant,
    ou vers la section de la rencontre correspondante DANS ce rapport
    si sa date y correspond). `paires_date_url` : liste de (date, url) -
    une date sans URL connue (url vide/None) s'affiche en texte simple,
    sans lien. Un url commençant par "#" est traité comme une ANCRE
    INTERNE au rapport (rendu via lien_ancre(), pour un défilement
    correct dans le widget Html d'Odoo plutôt qu'un lien externe classique
    ouvrant un nouvel onglet) - tout autre url est un lien externe normal
    (ouvert dans un nouvel onglet). Dédoublonne sur la COMBINAISON
    (date, url), pas sur la date seule - deux événements différents à
    la même date resteraient donc deux entrées distinctes."""
    paires_uniques = sorted({(str(d), u or "") for d, u in paires_date_url}, key=lambda t: t[0], reverse=True)
    if not paires_uniques:
        return ""
    rendus = []
    for d, u in paires_uniques:
        if u.startswith("#"):
            rendus.append(lien_ancre(u[1:], echapper(d)))
        elif u:
            rendus.append(f"<a href='{echapper_attr(u)}' target='_blank'>{echapper(d)}</a>")
        else:
            rendus.append(echapper(d))
    if len(rendus) < seuil:
        return ", ".join(rendus)
    puces = "".join(f"<li>{r}</li>" for r in rendus)
    return (
        f"<details class='detail-oui detail-inline'><summary>({len(rendus)} dates)</summary>"
        f"<ul class='liste-texte'>{puces}</ul></details>"
    )


def liste_personnes_simple(noms, seuil=2, noms_avec_fiche=None):
    """Comme rendu_avec_noms, mais pour une simple liste de noms sans date
    associée (ex. les personnes partageant une même étiquette). Le nombre
    de personnes sert d'étiquette cliquable/dépliable.

    `noms_avec_fiche` : ensemble optionnel de noms normalisés (voir
    normaliser_nom) ayant réellement une fiche dans CE rapport - un nom
    absent de cet ensemble (ex. une personne de l'étiquette n'ayant pas
    répondu à un sondage inclus dans ce rapport précis) est affiché en
    texte simple plutôt qu'en lien, pour ne pas laisser croire qu'un clic
    y mènerait quelque part. Si non fourni, tous les noms sont rendus
    comme des liens (comportement historique)."""
    noms_uniques = sorted(set(noms), key=normaliser_nom)
    if not noms_uniques:
        return ""

    def rendu_nom(n):
        if noms_avec_fiche is None or normaliser_nom(n) in noms_avec_fiche:
            return lien_personne(n)
        return f"<span style='color:#000;'>{echapper(n)}</span>"

    if len(noms_uniques) < seuil:
        texte_tooltip = "\n".join(noms_uniques)
        return f"<span class='a-tooltip' data-rlq-tip=\"{echapper_attr(texte_tooltip)}\">({len(noms_uniques)})</span>"
    puces = "".join(f"<li>{rendu_nom(n)}</li>" for n in noms_uniques)
    return (
        f"<details class='detail-oui detail-inline'><summary>({len(noms_uniques)})</summary>"
        f"<ul class='liste-texte'>{puces}</ul></details>"
    )


def rendu_nombre_avec_detail_notes(nombre, detail_entries):
    """Affiche `nombre` (le compte de réponses d'un volet de matrice) avec
    une petite flèche cliquable directement dessus pour voir le détail
    des notes individuelles - même patron que liste_personnes_simple(),
    plutôt qu'une colonne "Détail" séparée avec le texte "Détail des
    notes". `detail_entries` : liste de (texte, num, nom, date).

    TOUJOURS la liste dépliable, peu importe le nombre de personnes
    distinctes (même une seule) - une version précédente affichait un
    simple tooltip au survol sous un certain seuil, ce qui empêchait de
    cliquer sur le nom pour aller à sa fiche dans ce cas précis,
    incohérent avec le comportement au-dessus du seuil (signalé)."""
    if not detail_entries:
        return str(nombre)
    entree = sorted(
        detail_entries,
        key=lambda e: (e[1] if e[1] is not None else 99, normaliser_nom(e[2])),
    )
    puces = "".join(
        f"<li>{colorer_par_valeur(txt, num=num)} — {lien_personne(nom)} "
        f"<span class='date-oui'>({lien_date(date)})</span></li>"
        for txt, num, nom, date in entree
    )
    return (
        f"<details class='detail-oui'><summary>{nombre}</summary>"
        f"<ul class='liste-texte'>{puces}</ul></details>"
    )


# ---------------------------------------------------------------------------
# Sections de tableau
# ---------------------------------------------------------------------------

def section_evolution(stats_rencontres):
    """Petit graphique d'évolution (barres CSS, sans JavaScript ni SVG -
    compatible avec un fichier HTML autonome sans connexion internet) des
    trois métriques de participation (Inscrit, Terminé, Débuté sans
    terminer) à travers les rencontres incluses, en ordre CHRONOLOGIQUE
    (du plus ancien au plus récent - contrairement au reste du rapport,
    en ordre inverse) pour visualiser une tendance dans le temps plutôt
    qu'un simple instantané. `stats_rencontres` : liste de tuples
    (libellé, ancre, inscrit, terminé, débuté, durée, nb_questions), déjà
    utilisée pour le tableau récapitulatif - même donnée, présentation
    différente. Retourne une chaîne vide s'il y a moins de 2 rencontres
    (une évolution n'a pas de sens sur un seul point)."""
    if len(stats_rencontres) < 2:
        return ""
    chronologique = list(reversed(stats_rencontres))

    def _graphique_serie(libelle, index_valeur):
        valeurs = [s[index_valeur] for s in chronologique]
        maximum = max(valeurs) if max(valeurs) else 1
        hauteur_max_px = 70
        barres = []
        for (lbl, anchor, *_reste), valeur in zip(chronologique, valeurs):
            hauteur_px = max(round((valeur / maximum) * hauteur_max_px), 2) if valeur else 2
            libelle_date = lbl.split(" ")[0] if lbl else ""
            barres.append(
                "<div class='evo-barre-conteneur'>"
                f"<div class='evo-barre-valeur'>{valeur}</div>"
                f"<div class='evo-barre' style='height:{hauteur_px}px'></div>"
                f"<div class='evo-barre-date'>{lien_ancre(anchor, echapper(libelle_date))}</div>"
                "</div>"
            )
        return (
            f"<div class='evo-serie'><h4>{echapper(libelle)}</h4>"
            f"<div class='evo-graphique'>{''.join(barres)}</div></div>"
        )

    return (
        "<div class='evo-section'>"
        "<h3>Évolution dans le temps</h3>"
        + _graphique_serie("Inscrit", 2)
        + _graphique_serie("Terminé", 3)
        + _graphique_serie("Débuté sans terminer", 4)
        + "</div>"
    )


def section_taux_reponse(stats_rencontres):
    """Tendance du TAUX DE RÉPONSE (terminé / inscrit, en %) à travers
    les rencontres incluses - une métrique d'ENGAGEMENT distincte de la
    satisfaction (Note globale) : une baisse de la note ET une baisse
    du taux de réponse ensemble n'ont pas la même signification qu'une
    baisse de la note SEULE - la première peut indiquer un désintérêt
    plus large, la seconde peut n'être qu'une question de contenu d'une
    rencontre précise. Échelle fixe 0-100%, ancrée à 0 (contrairement
    aux notes de satisfaction, un taux de réponse peut légitimement
    être bas). `stats_rencontres` : même structure que section_evolution
    (libellé, ancre, inscrit, terminé, débuté, durée, nb_questions).
    Retourne une chaîne vide s'il y a moins de 2 rencontres, ou si
    aucune n'a d'inscrit (division par zéro évitée)."""
    if len(stats_rencontres) < 2:
        return ""
    chronologique = list(reversed(stats_rencontres))
    hauteur_max_px = 70
    barres = []
    for lbl, anchor, inscrit, termine, _debute, *_reste in chronologique:
        if not inscrit:
            continue
        taux = round((termine / inscrit) * 100)
        hauteur_px = max(round((taux / 100) * hauteur_max_px), 2)
        libelle_date = lbl.split(" ")[0] if lbl else ""
        barres.append(
            "<div class='evo-barre-conteneur'>"
            f"<div class='evo-barre-valeur'>{taux}%</div>"
            f"<div class='evo-barre' style='height:{hauteur_px}px'></div>"
            f"<div class='evo-barre-date'>{lien_ancre(anchor, echapper(libelle_date))}</div>"
            "</div>"
        )
    if len(barres) < 2:
        return ""
    return (
        "<div class='evo-serie evo-tendance-question'>"
        "<h4>Taux de réponse (terminé / inscrit)</h4>"
        f"<div class='evo-graphique'>{''.join(barres)}</div>"
        "<p class='titre-sondage'>Une métrique d'engagement, distincte de la satisfaction - "
        "une baisse ici avec une baisse de la Note globale peut indiquer un désintérêt plus "
        "large qu'un simple mécontentement ponctuel.</p>"
        "</div>"
    )


_MOTIF_PRESENTATEUR_CROCHETS = re.compile(r"^(.*?)\s*[\[\(]([^\[\]\(\)]+)[\]\)]\s*$")


def titre_avec_tooltip_date(titre, date):
    """Affiche un titre (ex. de présentation) avec un tooltip indiquant
    sa date, s'il y en a une connue - même patron que le tooltip de
    date déjà utilisé sur le nom d'un volet dans section_matrice()."""
    titre_html = echapper(titre)
    if not date:
        return titre_html
    jour = jour_semaine(date)
    texte_date = f"Présenté le {date}" + (f" ({jour})" if jour else "")
    return f"<span class='a-tooltip' data-rlq-tip=\"{echapper_attr(texte_date)}\">{titre_html}</span>"


def extraire_presentateur(titre_presentation):
    """Extrait un nom de présentateur du titre d'une présentation - le
    nom est attendu entre crochets OU entre parenthèses, à la fin du
    titre (ex. "Titre de la présentation [Nom Prénom]" ou "Titre de la
    présentation (Nom Prénom)") - les deux formats sont utilisés selon
    l'utilisateur. Retourne (titre_sans_crochets_ni_parentheses, nom) si
    le motif est reconnu, ou (titre_complet, None) sinon (aucune
    présentation notée avec ce format n'est alors incluse dans la
    section, plutôt que de risquer une fausse attribution)."""
    correspondance = _MOTIF_PRESENTATEUR_CROCHETS.match(titre_presentation)
    if correspondance:
        titre, nom = correspondance.groups()
        return titre.strip(), nom.strip()
    return titre_presentation, None


def proteger_nom_dans_titre(item_texte):
    """Si `item_texte` est un titre de présentation au format reconnu par
    extraire_presentateur() (nom entre crochets/parenthèses), remplace
    UNIQUEMENT le nom par son jeton (voir jeton_presentateur()) - le reste
    du titre, y compris les crochets/parenthèses d'origine tels que
    saisis, n'est pas touché. Retourne `item_texte` inchangé si aucun nom
    n'y est reconnu (cas normal pour toute question qui n'est pas une
    liste de présentations - _MOTIF_PRESENTATEUR_CROCHETS ne matchera
    simplement pas, sans erreur).

    Utilisé pour que le nom d'un présentateur reste visible dans le
    "Volet" d'une question matricielle de type Présentations (voir
    section_matrice()) même si cette même personne est anonymisée
    ailleurs dans le rapport en tant que simple répondante - le jeton
    est résolu vers le nom réel tout à la fin, anonymisé ou non (voir
    _resoudre_jetons_presentateurs() dans rlq_survey_report_wizard.py)."""
    _titre_sans_nom, nom = extraire_presentateur(item_texte)
    if not nom:
        return item_texte
    return item_texte.replace(nom, jeton_presentateur(nom), 1)


def section_appreciation_presentateurs(donnees_presentateurs):
    """donnees_presentateurs : liste de dicts {"presentateur": str,
    "valeurs": [float,...], "detail": [(texte, num, nom, date),...],
    "presentations": [(titre, date, valeurs),...]} - une entrée par
    présentateur reconnu (voir extraire_presentateur), agrégeant toutes
    ses présentations à travers toutes les rencontres incluses. Retourne
    une chaîne vide si la liste est vide (aucun nom de présentateur
    n'a pu être extrait des titres, ou aucune présentation notée).

    Clé optionnelle "presentateur_affichage" : texte à AFFICHER à la
    place de "presentateur" (ex. un jeton, voir jeton_presentateur()) -
    "presentateur" reste dans tous les cas la base de l'ancre (id=) et du
    tri, pour que la navigation interne (liens "Présentateur(s) :" des
    rencontres) continue de fonctionner peu importe le texte affiché.

    Si un présentateur a fait PLUSIEURS présentations, chacune affiche
    ses propres statistiques (moyenne, nombre de réponses) en plus de
    la moyenne combinée de toutes ses présentations - pour une seule
    présentation, ce détail par présentation serait redondant avec la
    ligne principale et n'est donc pas affiché."""
    if not donnees_presentateurs:
        return ""
    lignes = []
    for d in sorted(donnees_presentateurs, key=lambda d: normaliser_nom(d["presentateur"])):
        m = moyenne(d["valeurs"])
        pct = f"{(m / 5) * 100:.0f}%" if m is not None else "s.o."
        cellule_stats = stats_pourcentage_html(d["valeurs"], echelle_min=1, echelle_max=5, inclure_nb_reponses=False)
        plusieurs_presentations = len(d["presentations"]) > 1
        indicateur_tendance = ""
        presentations_datees = sorted(
            (p for p in d["presentations"] if p[1]), key=lambda p: p[1]
        )
        if len(presentations_datees) >= 2:
            m_premiere = moyenne(presentations_datees[0][2])
            m_derniere = moyenne(presentations_datees[-1][2])
            if m_premiere is not None and m_derniere is not None:
                delta = m_derniere - m_premiere
                if abs(delta) < 0.15:
                    texte_tendance = "Stable depuis sa première présentation"
                    classe_tendance, fleche = "val-neutre", "▬"
                elif delta > 0:
                    texte_tendance = f"En hausse depuis sa première présentation ({m_premiere:.2f} → {m_derniere:.2f})"
                    classe_tendance, fleche = "val-positive", "▲"
                else:
                    texte_tendance = f"En baisse depuis sa première présentation ({m_premiere:.2f} → {m_derniere:.2f})"
                    classe_tendance, fleche = "val-negative", "▼"
                indicateur_tendance = (
                    f" <span class='{classe_tendance} a-tooltip' "
                    f"data-rlq-tip=\"{echapper_attr(texte_tendance)}\">{fleche}</span>"
                )
        items_presentations = []
        for titre, date, valeurs_presentation in d["presentations"]:
            titre_html = titre_avec_tooltip_date(titre, date)
            if plusieurs_presentations:
                m_presentation = moyenne(valeurs_presentation)
                txt_moy = f"{m_presentation:.2f}" if m_presentation is not None else "s.o."
                items_presentations.append(
                    f"<li>{titre_html} — Moy "
                    f"{colorer_par_valeur(txt_moy, num=m_presentation)}, "
                    f"{len(valeurs_presentation)} réponse(s)</li>"
                )
            else:
                items_presentations.append(f"<li>{titre_html}</li>")
        titres_html = "".join(items_presentations)
        cellule_nombre = rendu_nombre_avec_detail_notes(len(d["valeurs"]), d.get("detail", []))
        lignes.append(
            f"<tr id='presentateur-{slug(d['presentateur'])}'>"
            f"<td>{echapper(d.get('presentateur_affichage', d['presentateur']))}{indicateur_tendance}"
            f"<details class='detail-oui'><summary>{len(d['presentations'])} présentation(s)</summary>"
            f"<ul class='liste-texte'>{titres_html}</ul></details></td>"
            f"<td>{barre(m, 5, style_pourcentage=True, colorer_seuils=True)}</td>"
            f"<td class='centre'>{pct}</td>"
            f"<td class='centre'>{cellule_nombre}</td>"
            f"<td class='stats-desc'>{cellule_stats}</td>"
            "</tr>"
        )
    return (
        "<section class='rencontre' id='appreciation-presentateurs'>"
        "<h2>Appréciation des présentateurs</h2>"
        "<p class='titre-sondage'>Moyenne combinée de toutes les présentations données par chaque "
        "présentateur, à travers toutes les rencontres incluses dans ce rapport - basé sur les noms "
        "détectés dans les titres de présentation (voir note technique si un nom attendu manque ici).</p>"
        "<table class='tableau'><thead><tr>"
        "<th>Présentateur</th><th>Note moyenne</th><th>%</th><th># réponses</th><th>Statistiques</th>"
        "</tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
        "</section>"
    )


def section_a_surveiller(alertes):
    """Liste toutes les réponses ayant reçu une note de 2 ou moins,
    qu'importe la question ou la rencontre - pour repérer rapidement les
    pistes d'amélioration sans parcourir le détail de chaque sondage un
    par un. `alertes` : liste de (date_rencontre, titre_question, item,
    nom, note, commentaire) - `commentaire` est une réponse texte libre
    de LA MÊME personne dans LE MÊME sondage (voir
    _commentaire_libre_pour dans le wizard), s'il y en a une - relie le
    symptôme (la note) à une cause possible sans avoir à chercher
    manuellement dans le détail du sondage. Triée par note croissante
    (les pires en premier), puis par date décroissante à note égale
    (tri stable en deux passes : les chaînes de dates ISO se comparent
    correctement telles quelles). Retourne une chaîne vide si la liste
    est vide."""
    if not alertes:
        return ""
    etape1 = sorted(alertes, key=lambda a: a[0] or "", reverse=True)
    etape2 = sorted(etape1, key=lambda a: a[4])
    lignes = []
    for date_rencontre, titre_question, item, nom, note, commentaire in etape2:
        jour = jour_semaine(date_rencontre) if date_rencontre else None
        date_txt = f"{date_rencontre} ({jour})" if jour else (date_rencontre or "")
        date_html = lien_ancre(slug(date_rencontre), echapper(date_txt)) if date_rencontre else ""
        cellule_commentaire = f"« {echapper(commentaire)} »" if commentaire else "—"
        lignes.append(
            "<tr>"
            f"<td>{date_html}</td>"
            f"<td>{echapper(titre_question)}</td>"
            f"<td>{echapper(item)}</td>"
            f"<td>{lien_personne(nom)}</td>"
            f"<td class='centre'><strong class='val-negative'>{note:g}</strong></td>"
            f"<td class='commentaire-lie'>{cellule_commentaire}</td>"
            "</tr>"
        )
    return (
        "<section class='rencontre' id='a-surveiller'>"
        f"<h2>À surveiller <span class='badge'>{len(alertes)} note(s) ≤ 2</span></h2>"
        "<p class='titre-sondage'>Toutes les notes de 2 ou moins données à n'importe quelle "
        "question, tous sondages sélectionnés confondus - pour repérer rapidement les "
        "pistes d'amélioration. La colonne Commentaire, si renseignée, provient d'une "
        "réponse texte libre de la MÊME personne dans le MÊME sondage - une piste de "
        "cause possible, pas une certitude.</p>"
        "<table class='tableau'><thead><tr>"
        "<th>Date</th><th>Question</th><th>Volet</th><th>Participant</th><th>Note</th><th>Commentaire</th>"
        "</tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
        "</section>"
    )


def section_tendance_question(
    titre, valeurs_par_date, echelle_max=5, echelle_min=1, limites_controle=False, detecter_derive=False
):
    """Petit graphique de tendance (même technique en barres CSS que
    section_evolution) montrant l'évolution de la note MOYENNE d'une
    question matricielle à travers les rencontres où elle a été posée
    (tous les volets/items de la question combinés en une seule
    moyenne), en ordre chronologique. `valeurs_par_date` : dict
    {date_rencontre: [valeurs numériques]}. Retourne une chaîne vide
    s'il y a moins de 2 dates distinctes avec au moins une valeur - une
    tendance n'a pas de sens sur un seul point, et une date sans aucune
    valeur numérique (ex. tout le monde a répondu "Je n'étais pas là")
    ne doit pas produire une barre vide trompeuse.

    La hauteur de chaque barre est calculée sur l'ÉCHELLE RÉELLE DE LA
    QUESTION (1 à 5 par défaut), ancrée à `echelle_min` plutôt qu'à 0 -
    puisqu'une note ne descend jamais sous 1, ancrer à 0 (comme le
    faisait une version précédente, relative en plus au maximum DE LA
    SÉRIE plutôt qu'à l'échelle fixe) compresse artificiellement les
    écarts visuels entre des valeurs qui se ressemblent.

    La hauteur est exprimée en PIXELS, PAS en pourcentage - un
    pourcentage sur .evo-barre (un enfant flex dans un conteneur
    flex-direction:column) s'est avéré ne pas produire de différence
    visuelle fiable entre des valeurs pourtant différentes (signalé :
    aucune différence visible entre 4.0 et 5.0) - un problème de
    résolution de hauteur en pourcentage dans ce contexte flex précis,
    qui ne se produit pas pour les barres HORIZONTALES du reste du
    rapport (celles-ci utilisent width, pas height, un mécanisme plus
    simple et fiable). Une valeur en pixels, calculée directement ici,
    élimine ce problème à la source.

    `limites_controle=True` (esprit carte de contrôle / Six Sigma) :
    calcule la moyenne et l'écart-type sur TOUTES les valeurs
    combinées (toutes dates confondues), puis marque distinctement
    (bordure) toute rencontre dont la moyenne s'écarte de plus d'un
    écart-type de cette moyenne globale - une aide visuelle pour
    distinguer une variation normale d'un signal qui mérite d'être
    creusé, sans confondre les deux.

    `detecter_derive=True` : détecte une tendance SOUTENUE sur les 3
    dernières rencontres (chacune strictement plus basse, ou plus
    haute, que la précédente) - un signal différent d'un point isolé
    hors norme (limites_controle ci-dessus) : une dérive lente et
    régulière ne déclenche pas forcément ce signal ponctuel, mais
    révèle souvent un problème (ou une amélioration) systémique."""
    dates_valides = {d: v for d, v in valeurs_par_date.items() if d and v}
    if len(dates_valides) < 2:
        return ""
    dates_triees = sorted(dates_valides.keys())
    moyennes = [round(sum(dates_valides[d]) / len(dates_valides[d]), 1) for d in dates_triees]
    etendue = (echelle_max - echelle_min) or 1
    hauteur_max_px = 70
    bornes_controle = None
    if limites_controle:
        toutes_valeurs = [v for date in dates_triees for v in dates_valides[date]]
        stats_globales = stats_description(toutes_valeurs)
        if stats_globales and stats_globales["ecart_type"]:
            bornes_controle = (
                stats_globales["moy"] - stats_globales["ecart_type"],
                stats_globales["moy"] + stats_globales["ecart_type"],
            )
    barres = []
    for date, moy in zip(dates_triees, moyennes):
        hauteur_px = max(round(((moy - echelle_min) / etendue) * hauteur_max_px), 2)
        # Étiquette texte en %, MÊME formule que stats_pourcentage_html() et
        # barre() (valeur/échelle_max*100, pas ancrée à echelle_min) - pour
        # rester cohérente avec le tooltip juste en dessous, qui affiche
        # les mêmes statistiques via stats_pourcentage_html() (signalé :
        # ces deux % différaient avant, calculés avec des formules
        # différentes pour la même moyenne). La HAUTEUR de la barre, elle,
        # reste ancrée à echelle_min (voir docstring ci-dessus) - un choix
        # de rendu visuel séparé de l'exactitude du chiffre affiché.
        moy_pct = round(moy / echelle_max * 100) if echelle_max else 0
        stats = stats_description(dates_valides[date])
        info_bulle = ""
        if stats:
            texte_stats = stats_pourcentage_html(
                dates_valides[date], echelle_min, echelle_max, texte_brut=True
            )
            info_bulle = f" data-rlq-tip=\"{echapper_attr(texte_stats)}\""
        classe_signal = ""
        if bornes_controle and not (bornes_controle[0] <= moy <= bornes_controle[1]):
            classe_signal = " evo-barre-signal"
        classe_couleur = f" evo-barre-{_classe_couleur_1a5(moy)}"
        barres.append(
            "<div class='evo-barre-conteneur'>"
            f"<div class='evo-barre-valeur'>{moy_pct}%</div>"
            f"<div class='evo-barre{classe_couleur} a-tooltip{classe_signal}' style='height:{hauteur_px}px'{info_bulle}></div>"
            f"<div class='evo-barre-date'>{lien_date(date)}</div>"
            "</div>"
        )
    legende_controle = (
        "<p class='titre-sondage evo-legende-controle'>▍ Barre à bordure marquée = s'écarte de plus d'un "
        "écart-type de la moyenne de toutes les rencontres affichées ici - possiblement un signal à "
        "examiner plutôt qu'une variation normale.</p>"
        if bornes_controle else ""
    )
    # Détection de DÉRIVE (esprit Six Sigma) : une tendance SOUTENUE sur
    # les 3 dernières rencontres (chacune strictement plus basse/haute que
    # la précédente) est un signal différent d'un simple point isolé hors
    # norme (voir limites_controle ci-dessus) - une dérive lente et
    # régulière ne déclenche pas forcément ce signal ponctuel (chaque
    # point pris seul peut rester dans les limites normales), mais révèle
    # souvent un problème systémique qu'un accident isolé ne révélerait
    # pas.
    message_derive = ""
    if detecter_derive and len(moyennes) >= 3:
        trois_dernieres = moyennes[-3:]
        if trois_dernieres[0] > trois_dernieres[1] > trois_dernieres[2]:
            message_derive = (
                "<p class='titre-sondage evo-derive-baisse'>⚠ Tendance à la BAISSE soutenue sur les 3 "
                "dernières rencontres (pas un point isolé) - possiblement un problème systémique à "
                "creuser plutôt qu'un accident ponctuel.</p>"
            )
        elif trois_dernieres[0] < trois_dernieres[1] < trois_dernieres[2]:
            message_derive = (
                "<p class='titre-sondage evo-derive-hausse'>✓ Tendance à la HAUSSE soutenue sur les 3 "
                "dernières rencontres.</p>"
            )
    return (
        "<div class='evo-serie evo-tendance-question'>"
        f"<h4>Tendance de la note moyenne : {echapper(titre)}</h4>"
        f"<div class='evo-graphique'>{''.join(barres)}</div>{legende_controle}{message_derive}</div>"
    )


def section_actions_suivi(texte):
    """Affiche les notes d'actions de suivi (champ persistant
    rlq_actions_suivi sur survey.survey, rempli manuellement depuis le
    formulaire natif du sondage) pour CETTE rencontre - ferme la
    boucle Plan-Do-Check-Act en rappelant, la prochaine fois que cette
    rencontre apparaît dans un rapport, ce qui avait été noté comme
    action entreprise suite à ses signaux. Retourne une chaîne vide si
    aucune note n'a été saisie - ne pas ajouter un encadré vide."""
    if not texte or not texte.strip():
        return ""
    texte_html = echapper(texte).replace("\n", "<br/>")
    return (
        "<div class='actions-suivi'>"
        "<h4>📋 Actions de suivi notées pour cette rencontre</h4>"
        f"<p>{texte_html}</p>"
        "</div>"
    )


def section_actions_suivi_consolidee(entrees):
    """Liste consolidée, en un seul endroit du rapport (dans la
    Synthèse), de TOUTES les notes d'"actions de suivi" des rencontres
    incluses dans ce rapport - contrairement à section_actions_suivi()
    ci-dessus, qui affiche la note d'UNE SEULE rencontre directement
    dans sa propre section, celle-ci permet de voir d'un coup d'œil,
    sans parcourir chaque rencontre une à une, tout ce qui a été noté
    comme action à travers la période couverte par ce rapport - les
    deux sections coexistent, chacune répondant à un besoin différent.

    `entrees` : liste de (date_rencontre, texte) - ne fournir que les
    rencontres ayant effectivement une note (à filtrer par l'appelant,
    comme pour section_actions_suivi()). Retourne une chaîne vide si
    `entrees` est vide."""
    if not entrees:
        return ""
    entrees_triees = sorted(entrees, key=lambda e: str(e[0]), reverse=True)
    lignes = []
    for date_r, texte in entrees_triees:
        texte_html = echapper(texte).replace("\n", "<br/>")
        lignes.append(
            "<li>"
            f"<strong>{lien_date(date_r)}</strong>"
            f"<div>{texte_html}</div>"
            "</li>"
        )
    return (
        "<div class='actions-suivi-consolidee'>"
        "<h3>📋 Actions de suivi notées, toutes rencontres confondues</h3>"
        f"<ul>{''.join(lignes)}</ul>"
        "</div>"
    )


def section_note_globale(valeurs, echelle_max=5, moyenne_reference=None, nb_reference=0):
    """Résumé compact de la "note globale" d'une rencontre - une
    moyenne composite combinant les valeurs de plusieurs questions clés
    (Organisation et logistique, Satisfaction globale, présentations),
    affichée en tête de chaque section de rencontre pour permettre une
    comparaison rapide entre rencontres (voir MOTS_CLES_NOTE_GLOBALE
    dans le wizard pour la liste des questions combinées). Retourne une
    chaîne vide si aucune valeur numérique n'est disponible pour cette
    rencontre (ex. aucune des 3 questions n'a été posée).

    `moyenne_reference` : moyenne des rencontres précédentes (calculée
    par l'appelant, ex. une moyenne mobile des N dernières) - si fournie
    avec `nb_reference` > 0, une phrase de comparaison est ajoutée
    ("0.4 point sous la moyenne des 6 dernières rencontres"),
    utile pour situer rapidement cette rencontre par rapport à
    l'historique récent sans avoir à consulter la Synthèse."""
    if not valeurs:
        return ""
    m = moyenne(valeurs)
    cellule_stats = stats_pourcentage_html(valeurs, echelle_min=1, echelle_max=echelle_max)
    comparaison_html = ""
    if moyenne_reference is not None and nb_reference > 0 and m is not None:
        # MÊME formule que stats_pourcentage_html()/barre() (valeur/échelle_max*100,
        # pas ancrée à 1) - signalé : la version précédente comparait des
        # pourcentages ancrés à 1, incohérents avec les autres % du rapport.
        m_pct = m / echelle_max * 100 if echelle_max else 0
        moyenne_reference_pct_brut = moyenne_reference / echelle_max * 100 if echelle_max else 0
        ecart_pct = m_pct - moyenne_reference_pct_brut
        moyenne_reference_pct = round(moyenne_reference_pct_brut)
        if abs(ecart_pct) < 1:
            texte_ecart = "égale à"
        else:
            sens = "au-dessus de" if ecart_pct > 0 else "sous"
            # "3% sous la moyenne", pas "3 point de % sous la moyenne" -
            # simplifié sur demande (l'écart entre deux % est techniquement
            # un nombre de points de pourcentage, mais la formulation plus
            # courte se lit mieux ici et le sens reste clair en contexte).
            texte_ecart = (
                f"{colorer_par_valeur(f'{abs(ecart_pct):.0f}%', num=(5 if ecart_pct > 0 else 1))} {sens}"
            )
        comparaison_html = (
            f"<p class='note-globale-comparaison'>{texte_ecart} la moyenne des "
            f"{nb_reference} rencontre(s) précédente(s) ({moyenne_reference_pct}%)</p>"
        )
    return (
        "<div class='note-globale'>"
        "<h3>📊 Note globale de cette rencontre</h3>"
        "<div class='note-globale-ligne'>"
        f"<div class='note-globale-corps'>{barre(m, echelle_max, style_pourcentage=True, colorer_seuils=True)}</div>"
        f"<p class='note-globale-stats'>{cellule_stats}</p>"
        "</div>"
        f"{comparaison_html}"
        "<p class='titre-sondage'>Moyenne combinée de « Organisation et logistique », "
        "« Satisfaction globale » et « Comment avez-vous aimé les présentations » - LE métrique "
        "à suivre dans le temps pour l'amélioration continue (voir la tendance dans la Synthèse).</p>"
        "</div>"
    )


def section_top_mouvements(mouvements, limite=3, echelle_min=1, echelle_max=5):
    """Résumé compact des questions dont la moyenne a le plus changé
    entre les deux dernières rencontres où elles ont été posées -
    permet de voir d'un coup d'œil où porter attention sans comparer
    chaque graphique de tendance un par un. `mouvements` : liste de
    (titre, valeur_avant, valeur_apres) - le delta et le tri sont
    calculés ICI (pas par l'appelant), pour que ce tri soit centralisé
    et cohérent avec l'affichage. Retourne une chaîne vide si la liste
    est vide (aucune question n'a au moins 2 rencontres à comparer).

    Affiché en % de l'échelle - valeur/échelle_max*100, la MÊME formule
    que stats_pourcentage_html()/barre() ailleurs dans ce module (voir
    leur docstring : PAS ancrée à echelle_min, un ancrage antérieur
    donnait des % incohérents avec le reste du rapport pour la même
    note). `echelle_min` n'intervient donc plus dans ce calcul - conservé
    dans la signature uniquement pour ne pas casser les appels
    existants."""
    if not mouvements:
        return ""
    with_delta = [(titre, avant, apres, apres - avant) for titre, avant, apres in mouvements]
    top = sorted(with_delta, key=lambda t: abs(t[3]), reverse=True)[:limite]
    lignes = []
    for titre, avant, apres, delta in top:
        avant_pct = avant / echelle_max * 100 if echelle_max else 0
        apres_pct = apres / echelle_max * 100 if echelle_max else 0
        delta_pct = apres_pct - avant_pct
        fleche = "▲" if delta > 0 else ("▼" if delta < 0 else "▬")
        classe = "val-positive" if delta > 0 else ("val-negative" if delta < 0 else "val-neutre")
        lignes.append(
            "<li>"
            f"<span class='{classe}'>{fleche} {abs(delta_pct):.0f}%</span> — {echapper(titre)} "
            f"({avant_pct:.0f}% → {apres_pct:.0f}%)"
            "</li>"
        )
    return (
        "<div class='top-mouvements'>"
        "<h3>Ce qui a le plus bougé depuis la dernière rencontre</h3>"
        f"<ul>{''.join(lignes)}</ul>"
        "</div>"
    )



def section_matrice(titre, lignes_data, echelle_max=5, ventiler=False, dates_par_item=None, colorer_seuils=True):
    """lignes_data : liste de dicts {"item": str, "valeurs": [float,...],
    "detail": [(texte, num, nom, date), ...]} - un dict par volet/ligne de
    la matrice, dans l'ordre d'affichage voulu.

    `colorer_seuils=False` : la barre de "Note moyenne" n'est PAS
    colorée selon des seuils de qualité (rouge/jaune/bleu/vert) - pour
    les questions d'AUTO-ÉVALUATION (ex. "Niveau de connaissance ?"),
    où une note basse ne signale pas un problème comme le ferait une
    note de satisfaction basse (voir MOTS_CLES_QUESTIONS_AUTO_EVALUATION
    dans le wizard, qui exclut déjà ces questions de la section "À
    surveiller" et des graphiques de tendance pour la même raison -
    signalé : la barre de ces questions restait colorée alors que le
    reste du traitement les exclut déjà comme non qualitatives)."""
    lignes_html = []
    for ligne in lignes_data:
        item, valeurs = ligne["item"], ligne["valeurs"]
        m = moyenne(valeurs)
        libelle_item = echapper(item)
        if dates_par_item and dates_par_item.get(item):
            date_item = dates_par_item[item]
            jour = jour_semaine(date_item)
            texte_date = f"Présenté le {date_item}" + (f" ({jour})" if jour else "")
            libelle_item = (
                f"<span class='a-tooltip' data-rlq-tip=\"{echapper_attr(texte_date)}\">{libelle_item}</span>"
            )
        cellule_stats = stats_pourcentage_html(valeurs, echelle_min=1, echelle_max=echelle_max, inclure_nb_reponses=False)
        # Détail des notes individuelles : une petite flèche cliquable
        # directement sur le chiffre "# réponses" (comme ailleurs dans le
        # rapport, ex. le nombre de membres d'une étiquette), plutôt
        # qu'une colonne "Détail" séparée avec le texte "Détail des
        # notes" - même contenu, présentation plus compacte.
        cellule_nombre = (
            rendu_nombre_avec_detail_notes(len(valeurs), ligne.get("detail", []))
            if ventiler else str(len(valeurs))
        )
        lignes_html.append(
            "<tr>"
            f"<td>{libelle_item}</td>"
            f"<td>{barre(m, echelle_max, style_pourcentage=True, colorer_seuils=colorer_seuils)}</td>"
            f"<td class='centre'>{cellule_nombre}</td>"
            f"<td class='stats-desc'>{cellule_stats}</td>"
            "</tr>"
        )
    return (
        f"<h3>{echapper(titre)}</h3>"
        "<table class='tableau'><thead><tr>"
        "<th>Volet</th><th>Note moyenne</th><th># réponses</th><th>Statistiques</th>"
        "</tr></thead><tbody>" + "".join(lignes_html) + "</tbody></table>"
    )


def section_oui_non(titre, lignes_data, emails=None, afficher_uniques=False):
    """lignes_data : liste de dicts {"item": str, "oui": [(nom,date),...],
    "non": int}."""
    lignes_html = []
    for ligne in lignes_data:
        item, oui, non = ligne["item"], ligne["oui"], ligne["non"]
        total = len(oui) + non
        pct = round(100 * len(oui) / total) if total else 0
        if oui:
            resume = f"{len(oui)} Oui"
            if afficher_uniques:
                uniques = {normaliser_nom(n) for n, _d in oui}
                resume += f" &middot; {len(uniques)} unique(s)"
            cellule_oui = construire_detail_personnes(oui, resume, emails)
        else:
            cellule_oui = "0"
        lignes_html.append(
            "<tr>"
            f"<td>{echapper(item)}</td>"
            f"<td class='centre'>{cellule_oui}</td>"
            f"<td class='centre'>{non}</td>"
            f"<td>{barre(pct, 100, style_pourcentage=True)}</td>"
            "</tr>"
        )
    return (
        f"<h3>{echapper(titre)}</h3>"
        "<table class='tableau'><thead><tr>"
        "<th>Volet</th><th>Oui</th><th>Non</th><th>% Oui</th>"
        "</tr></thead><tbody>" + "".join(lignes_html) + "</tbody></table>"
    )


def section_choix(titre, compteur, details=None, emails=None, precisions=None):
    """compteur : dict valeur -> n. details : dict valeur -> [(nom,date),...].
    precisions : liste de (nom, texte) pour les réponses "Autre" avec une
    précision écrite (ligne.value_char_box) - affichée en liste dépliable
    séparée, plutôt que d'éclater le comptage de "Autre" en une entrée
    distincte par personne (ce qui diluerait le pourcentage affiché)."""
    total = sum(compteur.values()) or 1
    lignes = []
    for valeur, n in sorted(compteur.items(), key=lambda kv: -kv[1]):
        pct = round(100 * n / total)
        cellule_n = rendu_avec_noms(str(n), details.get(valeur, []), emails) if details else str(n)
        lignes.append(
            "<tr>"
            f"<td>{echapper(valeur)}</td>"
            f"<td class='centre'>{cellule_n}</td>"
            f"<td>{barre(pct, 100, style_pourcentage=True)}</td>"
            "</tr>"
        )
    bloc_precisions = ""
    if precisions:
        puces = "".join(
            f"<li>{echapper(nom)} : {echapper(texte)}</li>"
            for nom, texte in sorted(precisions, key=lambda np: normaliser_nom(np[0]))
        )
        bloc_precisions = (
            f"<details class='detail-oui'><summary>Précisions données pour « Autre » "
            f"({len(precisions)})</summary><ul class='liste-texte'>{puces}</ul></details>"
        )
    return (
        f"<h3>{echapper(titre)}</h3>"
        "<table class='tableau'><thead><tr>"
        "<th>Réponse</th><th>#</th><th>Proportion</th>"
        "</tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
        + bloc_precisions
    )


def section_soumissions_participant(soumissions):
    """Liste, pour un participant, chacune de ses soumissions RÉELLES
    (survey.user_input) - pas une par rencontre, une par soumission : une
    même rencontre peut apparaître plusieurs fois si la personne a répondu
    plus d'une fois (ex. en changeant d'idée). `soumissions` : liste de
    dicts {"date_rencontre": ..., "date_reponse": str ou None,
    "date_limite": str ou None, "test": bool, "commentaire": str ou None}.
    Triées par date de réponse, la plus récente en premier. Retourne une
    chaîne vide si la liste est vide."""
    if not soumissions:
        return ""
    entrees_triees = sorted(soumissions, key=lambda s: s.get("date_reponse") or "", reverse=True)
    lignes = []
    for s in entrees_triees:
        morceaux = [f"{lien_date(s['date_rencontre'])}" if s.get("date_rencontre") else "Date inconnue"]
        if s.get("date_reponse"):
            morceaux.append(f"répondu le {echapper(s['date_reponse'])}")
        if s.get("date_limite"):
            morceaux.append(f"limite : {echapper(s['date_limite'])}")
        ligne = " — ".join(morceaux)
        if s.get("test"):
            ligne += " <span class='badge-test'>Entrée test</span>"
        if s.get("commentaire"):
            texte_commentaire = echapper(s["commentaire"]).replace("\n", "<br/>")
            ligne += f"<div class='commentaire-staff'>💬 {texte_commentaire}</div>"
        lignes.append(f"<li>{ligne}</li>")
    return (
        "<div class='soumissions-participant'>"
        "<h4>Détail des soumissions</h4>"
        f"<ul class='liste-texte'>{''.join(lignes)}</ul>"
        "</div>"
    )


def tableau_reponses_personne(reponses, colonnes, types_questions):
    """Tableau « une colonne par rencontre (ou par soumission, voir plus
    bas) » pour un participant, comme dans la version autonome du
    programme. `reponses` : dict {(colonne_id, titre): valeur}, où valeur
    est soit une chaîne (question simple/texte), soit une LISTE de chaînes
    (question à choix multiples - v1.86.0, une réponse par ligne, triée,
    plutôt que jointe par des virgules sur une seule ligne), soit un dict
    {item: valeur} (question matricielle, un sous-titre par volet).
    `types_questions` : dict titre -> question_type Odoo (ex. "matrix"),
    pour savoir comment restituer chaque question.

    `colonnes` (v1.87.0, remplace l'ancien paramètre `dates_triees` ;
    v1.90.0, "libelle" devient "ligne1"/"ligne2") : liste de dicts
    {"id": ..., "ligne1": str, "ligne2": str ou None, "duree": str ou
    None, "ancre": str ou None, "test": bool}, DÉJÀ TRIÉE par l'appelant
    (le tri dépend du mode - une colonne par rencontre, ou une colonne
    par soumission individuelle, voir combiner_reponses_meme_sondage
    dans le wizard) - "id" est la clé utilisée pour chercher dans
    `reponses`. "ligne1" : la date DU SONDAGE (extraite de son titre) -
    première ligne de l'en-tête, avec le lien vers l'ancre de la
    rencontre si "ancre" est fourni. "ligne2" : la date ET l'heure
    RÉELLES de réponse (peut différer de "ligne1" si la personne a
    répondu après coup) - deuxième ligne, sans lien, ou rien si
    inconnue (v1.90.0 : remplace l'ancien "libelle" combinant les deux
    de façon trompeuse - la partie "heure" de la réponse était affichée
    à côté de la date DU SONDAGE plutôt que de la date RÉELLE de
    réponse, signalé comme trompeur quand les deux diffèrent). "duree" :
    temps de réponse déjà formaté (voir duree_humaine()), affiché sur
    une troisième ligne si fourni. "test" affiche un badge "Entrée
    test" - remplace "Détail des soumissions" pour cette information en
    mode par soumission (redondant sinon)."""
    entetes = "".join(
        (
            "<th>"
            + (lien_ancre(c["ancre"], echapper(c["ligne1"])) if c.get("ancre") else echapper(c.get("ligne1", "")))
            + (f"<br/>{echapper(c['ligne2'])}" if c.get("ligne2") else "")
            + (f"<br/><span class='duree-reponse'>{echapper(c['duree'])}</span>" if c.get("duree") else "")
            + ("<br/><span class='badge-test'>Entrée test</span>" if c.get("test") else "")
            + "</th>"
        )
        for c in colonnes
    )
    nb_colonnes = len(colonnes) + 1
    titres_ordonnes = []
    for (_colonne_id, titre) in reponses.keys():
        if titre not in titres_ordonnes:
            titres_ordonnes.append(titre)
    lignes = []
    for titre in titres_ordonnes:
        qtype = types_questions.get(titre)
        if qtype == "matrix":
            items_ordonnes = []
            valeurs = {}
            for c in colonnes:
                v = reponses.get((c["id"], titre))
                if isinstance(v, dict):
                    for item, val in v.items():
                        if item not in items_ordonnes:
                            items_ordonnes.append(item)
                        valeurs[(c["id"], item)] = val
            if not items_ordonnes:
                continue
            lignes.append(f"<tr class='entete-groupe'><td colspan='{nb_colonnes}'>{echapper(titre)}</td></tr>")
            for item in items_ordonnes:
                cellules = "".join(
                    f"<td>{colorer_par_valeur(valeurs.get((c['id'], item), ''))}</td>" for c in colonnes
                )
                lignes.append(f"<tr><td class='sous-item'>{echapper(item)}</td>{cellules}</tr>")
        else:
            cellules_html = []
            for c in colonnes:
                v = reponses.get((c["id"], titre), "")
                if isinstance(v, list):
                    # Une réponse par ligne, triée - pas jointes par des
                    # virgules sur une seule ligne (signalé : trop difficile
                    # à lire pour une question à choix multiples avec
                    # plusieurs réponses sélectionnées).
                    contenu = "<br/>".join(echapper(x) for x in sorted(v, key=normaliser_nom))
                else:
                    contenu = echapper(v or "")
                cellules_html.append(f"<td>{contenu}</td>")
            lignes.append(f"<tr><td class='col-question'>{echapper(titre)}</td>{''.join(cellules_html)}</tr>")
    return (
        "<div class='tableau-scroll'><table class='tableau tableau-personne'>"
        f"<thead><tr><th class='col-question'>Question</th>{entetes}</tr></thead>"
        f"<tbody>{''.join(lignes)}</tbody></table></div>"
    )


def section_textes(titre, entries, dedupliquer=False, emails=None, attribuer_auteur=False):
    """entries : liste de (texte, nom, date)."""
    if not entries:
        return f"<h3>{echapper(titre)}</h3><p class='vide'>Aucune réponse.</p>"
    if attribuer_auteur and not dedupliquer:
        puces = "".join(
            f"<li>{rendu_avec_noms(echapper(texte), [(nom, date)], emails)}</li>"
            for texte, nom, date in sorted(entries, key=lambda e: normaliser_nom(e[1]))
        )
        return f"<h3>{echapper(titre)}</h3><ul class='liste-texte'>{puces}</ul>"
    if not dedupliquer:
        puces = "".join(f"<li>{echapper(t)}</li>" for t, _n, _d in sorted(entries, key=lambda e: normaliser_nom(e[0])))
        return f"<h3>{echapper(titre)}</h3><ul class='liste-texte'>{puces}</ul>"
    comptes = defaultdict(lambda: [0, None, []])
    for texte, nom, date in entries:
        cle = normaliser_nom(texte)
        comptes[cle][0] += 1
        if comptes[cle][1] is None:
            comptes[cle][1] = texte
        comptes[cle][2].append((nom, date))
    puces = []
    for n, texte, personnes in sorted(comptes.values(), key=lambda p: normaliser_nom(p[1])):
        badge = f" <span class='occurrences'>(x{n})</span>" if n > 1 else ""
        puces.append(f"<li>{rendu_avec_noms(echapper(texte) + badge, personnes, emails)}</li>")
    return f"<h3>{echapper(titre)}</h3><ul class='liste-texte'>{''.join(puces)}</ul>"


# ---------------------------------------------------------------------------
# CSS (thèmes) - identique en esprit au programme autonome
# ---------------------------------------------------------------------------

CSS = """
.rlq-rapport {
  --bleu: #1b4965; --bleu-clair: #62b6cb; --gris: #f4f6f7; --gris-fonce: #40474d;
  --bg-carte: #ffffff; --bg-entete-table: #eef3f6; --bg-barre: #e6ecef;
  --couleur-barre: #bfe2ec; --bordure: #e0e0e0; --texte-attenue: #667;
  font-family: "Segoe UI", Arial, sans-serif; color: var(--gris-fonce);
}
.rlq-rapport[data-theme="dark"] {
  --bleu: #7ec3e0; --bleu-clair: #4a90ad; --gris: #14171a; --gris-fonce: #e6e9ea;
  --bg-carte: #1f2428; --bg-entete-table: #262c31; --bg-barre: #333a40;
  --couleur-barre: #3d6b82; --bordure: #3a4147; --texte-attenue: #99a3a8;
}
.rlq-rapport[data-theme="green"] {
  --bleu: #1b6e4a; --bleu-clair: #6cc6a0; --bg-entete-table: #eaf7f1;
  --bg-barre: #e2f2ea; --couleur-barre: #a9dfc4; --bordure: #d4ede1;
}
.rlq-rapport[data-theme="purple"] {
  --bleu: #5b3a9e; --bleu-clair: #b39ddb; --bg-entete-table: #f3eefc;
  --bg-barre: #ece3f8; --couleur-barre: #d3bdf0; --bordure: #e6d9f5;
}
.rlq-rapport * { box-sizing: border-box; }
.rlq-rapport a { text-decoration: underline; color: var(--bleu); }
.rlq-rapport section.rencontre, .rlq-rapport section.personne {
  background: var(--bg-carte); border-radius: 8px; padding: 1.2rem 1.5rem;
  margin-bottom: 1.2rem; box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.rlq-rapport h2 { color: var(--bleu); border-bottom: 2px solid var(--bleu-clair); padding-bottom: .3rem; }
.rlq-rapport .actions-suivi {
  background: #eef7ee; border: 1px solid #a8d5a8; border-radius: 8px;
  padding: .7rem 1.1rem; margin-bottom: 1.2rem;
}
.rlq-rapport .actions-suivi h4 { margin: 0 0 .3rem 0; color: #1f7a3d; font-size: .95rem; }
.rlq-rapport .actions-suivi p { margin: 0; white-space: pre-line; }
.rlq-rapport .note-globale {
  background: var(--bg-entete-table); border: 2px solid var(--bleu-clair); border-radius: 8px;
  padding: .8rem 1.2rem; margin-bottom: 1.2rem;
}
.rlq-rapport .note-globale h3 { margin: 0 0 .5rem 0; color: var(--bleu); font-size: 1.05rem; }
.rlq-rapport .note-globale-ligne { display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap; }
.rlq-rapport .note-globale-corps { max-width: 320px; flex: 0 0 auto; min-width: 200px; }
.rlq-rapport .note-globale-stats { margin: 0; font-size: .9rem; }
.rlq-rapport .note-globale-comparaison { margin: .4rem 0 0 0; font-size: .88rem; font-style: italic; }
.rlq-rapport .top-mouvements {
  background: var(--bg-carte); border-radius: 8px; padding: .8rem 1.2rem; margin-bottom: 1.2rem;
}
.rlq-rapport .top-mouvements h3 { margin: 0 0 .4rem 0; color: var(--bleu); font-size: 1rem; }
.rlq-rapport .top-mouvements ul { margin: 0; padding-left: 1.2rem; }
.rlq-rapport .actions-suivi-consolidee {
  background: #eef7ee; border: 1px solid #a8d5a8; border-radius: 8px;
  padding: .7rem 1.1rem; margin-bottom: 1.2rem;
}
.rlq-rapport .actions-suivi-consolidee h3 { margin: 0 0 .4rem 0; color: #1f7a3d; font-size: 1rem; }
.rlq-rapport .actions-suivi-consolidee ul { margin: 0; padding-left: 1.2rem; }
.rlq-rapport .actions-suivi-consolidee li { margin-bottom: .5rem; }
.rlq-rapport .actions-suivi-consolidee li div { white-space: pre-line; }
.rlq-rapport h3 { color: var(--bleu); margin-top: 1.2rem; margin-bottom: .4rem; font-size: 1.02rem; }
.rlq-rapport table.tableau { width: 100%; border-collapse: collapse; margin-bottom: .5rem; font-size: .9rem; }
.rlq-rapport table.tableau th, .rlq-rapport table.tableau td {
  padding: .35rem .55rem; border-bottom: 1px solid var(--bordure); text-align: left;
}
.rlq-rapport table.tableau th { background: var(--bg-entete-table); }
.rlq-rapport .commentaire-lie { font-style: italic; color: var(--texte-attenue); max-width: 280px; }
.rlq-rapport .tableau-scroll { overflow-x: auto; }
.rlq-rapport table.tableau-personne { min-width: 500px; }
.rlq-rapport table.tableau-personne th.col-question, .rlq-rapport table.tableau-personne td.col-question {
  text-align: left; font-weight: 600; background: var(--bg-entete-table); white-space: nowrap;
  position: sticky; left: 0;
}
.rlq-rapport table.tableau-personne td { vertical-align: top; min-width: 140px; }
.rlq-rapport table.tableau-personne td:not(.col-question):not(.sous-item) {
  max-width: 30ch; overflow-wrap: break-word; word-break: break-word;
}
.rlq-rapport table.tableau-personne tbody tr:nth-child(even):not(.entete-groupe) td:not(.col-question) {
  background: var(--bg-zebre, rgba(0,0,0,.035));
}
.rlq-rapport tr.entete-groupe td {
  background: var(--bg-entete-table); font-weight: 700; color: var(--bleu);
  padding-top: .5rem; padding-bottom: .5rem;
}
.rlq-rapport td.sous-item {
  padding-left: 1.3rem; font-style: italic; color: var(--texte-attenue); white-space: nowrap;
  position: sticky; left: 0; background: var(--bg-carte);
}
.rlq-rapport td.centre, .rlq-rapport th.centre { text-align: center; }
.rlq-rapport .barre-ligne { display: flex; align-items: center; gap: .5rem; }
.rlq-rapport .barre-cadre { position: relative; background: var(--bg-barre); border-radius: 4px; height: 1rem; flex: 1; min-width: 90px; }
.rlq-rapport .barre-remplie { background: var(--couleur-barre); height: 100%; border-radius: 4px; }
.rlq-rapport .barre-remplie-vert { background: #1f7a3d; }
.rlq-rapport .barre-remplie-bleu { background: #1b6ec2; }
.rlq-rapport .barre-remplie-jaune { background: #d1af00; }
.rlq-rapport .barre-remplie-rouge { background: #b3261e; }
.rlq-rapport .barre-valeur { font-size: .82rem; font-weight: 700; min-width: 3.2em; text-align: right; }
.rlq-rapport .barre-valeur.pct-vert { color: #1f7a3d; }
.rlq-rapport .barre-valeur.pct-bleu { color: #1b6ec2; }
.rlq-rapport .barre-valeur.pct-jaune { color: #a68b00; }
.rlq-rapport .barre-valeur.pct-rouge { color: #b3261e; }
.rlq-rapport ul.liste-texte { margin: 0; padding-left: 1.1rem; }
.rlq-rapport ul.liste-texte li { margin-bottom: .25rem; }
.rlq-rapport .occurrences { color: var(--bleu); font-weight: 600; font-size: .82rem; }
.rlq-rapport details.detail-oui summary { cursor: pointer; color: var(--bleu); font-weight: 600; list-style: none; }
.rlq-rapport details.detail-oui summary::-webkit-details-marker { display: none; }
.rlq-rapport details.detail-oui summary::before { content: "▸ "; }
.rlq-rapport details.detail-oui[open] summary::before { content: "▾ "; }
.rlq-rapport .date-oui { color: var(--texte-attenue); font-size: .82rem; white-space: nowrap; }
.rlq-rapport .date-oui a { color: inherit; }
.rlq-rapport .val-positive { color: #1f7a3d; font-weight: 600; }
.rlq-rapport .val-negative { color: #b3261e; font-weight: 600; }
.rlq-rapport .val-neutre { color: #a68b00; font-weight: 600; }
.rlq-rapport .val-bleu { color: #1b6ec2; font-weight: 600; }
.rlq-rapport .champ-courriels { margin: .3rem 0 .5rem 0; }
.rlq-rapport .champ-courriels label { display: block; font-size: .75rem; color: var(--texte-attenue); }
.rlq-rapport .champ-courriels input {
  width: 100%; font-family: inherit; font-size: .82rem; padding: .3rem .45rem;
  border: 1px solid var(--bordure); border-radius: 4px; background: var(--bg-entete-table);
}
.rlq-rapport .stats-desc { font-size: .76rem; color: var(--texte-attenue); white-space: nowrap; }
.rlq-rapport .a-tooltip { position: relative; border-bottom: 1px dotted var(--texte-attenue); cursor: help; }
.rlq-rapport .a-tooltip::after {
  content: attr(data-rlq-tip); position: absolute; left: 0; bottom: calc(100% + 6px);
  background: #12242e; color: #fff; padding: .35rem .55rem; border-radius: 5px;
  font-size: .76rem; white-space: pre-line; width: max-content; max-width: 380px;
  z-index: 20; opacity: 0; visibility: hidden; pointer-events: none;
  transition: opacity .05s ease-out; box-shadow: 0 2px 8px rgba(0,0,0,.25);
}
.rlq-rapport .a-tooltip:hover::after { opacity: 1; visibility: visible; }
.rlq-rapport[data-theme="dark"] .a-tooltip::after {
  background: #f4f6f7; color: #14171a; box-shadow: 0 2px 8px rgba(0,0,0,.5);
}
.rlq-rapport .badge {
  display: inline-block; background: var(--bleu-clair); color: white;
  border-radius: 12px; padding: .05rem .6rem; font-size: .76rem; margin-left: .4rem;
}
.rlq-rapport .liste-participants { color: var(--texte-attenue); font-size: .88rem; margin-top: -.3rem; }
.rlq-rapport .titre-sondage { color: var(--texte-attenue); font-size: .85rem; font-style: italic; margin: -.6rem 0 .6rem 0; }
.rlq-rapport .jour-semaine { font-size: .85rem; font-weight: 400; color: var(--texte-attenue); }
.rlq-rapport details.detail-inline { display: inline-block; vertical-align: middle; }
.rlq-rapport details.detail-inline ul { position: absolute; z-index: 15; background: var(--bg-carte);
  border: 1px solid var(--bordure); border-radius: 6px; padding: .5rem .8rem; box-shadow: 0 2px 8px rgba(0,0,0,.15); }
.rlq-rapport .liste-participants a { color: var(--bleu); }
.rlq-rapport .selecteur-theme {
  text-align: right; margin-bottom: .8rem; font-size: .85rem; color: var(--texte-attenue);
}
.rlq-rapport .selecteur-theme button {
  font-family: inherit; font-size: .82rem; padding: .25rem .7rem; margin-left: .3rem;
  border: 1px solid var(--bordure); border-radius: 5px; background: var(--bg-carte);
  color: var(--gris-fonce); cursor: pointer;
}
.rlq-rapport .selecteur-theme button:hover { background: var(--bg-entete-table); }
.rlq-rapport nav.table-matieres {
  background: var(--bg-carte); border-radius: 8px; padding: 1rem 1.5rem;
  margin-bottom: 1.2rem; box-shadow: 0 1px 4px rgba(0,0,0,.08);
}
.rlq-rapport nav.table-matieres h2 { margin-top: 0; }
.rlq-rapport nav.table-matieres h3 { color: var(--bleu); font-size: .95rem; margin: 0 0 .4rem 0; }
.rlq-rapport ul.nav-sections {
  list-style: none; display: flex; flex-wrap: wrap; gap: .3rem 1.2rem; padding: 0;
  margin: 0 0 1rem 0; font-size: .9rem;
}
.rlq-rapport ul.nav-sections li::before { content: "→ "; color: var(--bleu-clair); }
.rlq-rapport .colonnes-tm { display: flex; gap: 2.5rem; flex-wrap: wrap; }
.rlq-rapport .colonnes-tm > div { flex: 1; min-width: 200px; }
.rlq-rapport .colonnes-tm ul { margin: 0; padding-left: 1.1rem; }
.rlq-rapport .colonnes-tm li { margin-bottom: .2rem; }
.rlq-rapport ul.liste-individus {
  columns: 2; column-gap: 1.3rem; max-height: 480px; overflow-y: auto; padding-right: .5rem;
}
.rlq-rapport ul.liste-individus-large {
  columns: 4; column-gap: 1.6rem;
}
@media (max-width: 900px) {
  .rlq-rapport ul.liste-individus-large { columns: 2; }
}
.rlq-rapport .courriel { color: var(--texte-attenue); font-size: .88rem; margin: -.3rem 0 .7rem 0; }
.rlq-rapport .infos-participant { color: var(--texte-attenue); font-size: .85rem; margin: -.3rem 0 .8rem 0; }
.rlq-rapport .infos-participant div { margin-bottom: .15rem; }
.rlq-rapport .soumissions-participant { margin-bottom: .8rem; }
.rlq-rapport .soumissions-participant h4 { margin: 0 0 .3rem 0; font-size: .92rem; color: var(--texte-attenue); font-weight: 600; }
.rlq-rapport .soumissions-participant ul { margin: 0; font-size: .85rem; }
.rlq-rapport .badge-test {
  display: inline-block; background: #f0c987; color: #5c4813; font-size: .72rem;
  font-weight: bold; border-radius: 4px; padding: .05rem .4rem; margin-left: .4rem;
}
.rlq-rapport .duree-reponse {
  display: inline-block; color: var(--texte-attenue); font-size: .78rem; font-weight: normal;
}
.rlq-rapport .commentaire-staff {
  margin-top: .2rem; padding: .3rem .6rem; background: #eef2f8; border-left: 3px solid var(--bleu);
  border-radius: 0 4px 4px 0; font-style: italic; white-space: pre-line;
}
.rlq-rapport .evo-section {
  margin: 1.2rem 0; padding: 1rem; background: var(--bg-carte); border-radius: 8px;
}
.rlq-rapport .evo-serie { margin-bottom: 1.2rem; }
.rlq-rapport .evo-serie h4 { margin: 0 0 .5rem 0; color: var(--bleu); font-size: .95rem; }
.rlq-rapport .evo-graphique {
  display: flex; align-items: flex-end; gap: .6rem; height: 110px; overflow-x: auto;
  padding-bottom: .3rem;
}
.rlq-rapport .evo-barre-conteneur {
  display: flex; flex-direction: column; align-items: center; justify-content: flex-end;
  height: 100%; min-width: 38px;
}
.rlq-rapport .evo-barre-valeur { font-size: .78rem; font-weight: 600; margin-bottom: .2rem; }
.rlq-rapport .evo-barre {
  width: 22px; background: var(--bleu-clair); border-radius: 3px 3px 0 0; min-height: 2px;
}
.rlq-rapport .evo-barre-vert { background: #1f7a3d; }
.rlq-rapport .evo-barre-bleu { background: #1b6ec2; }
.rlq-rapport .evo-barre-jaune { background: #d1af00; }
.rlq-rapport .evo-barre-rouge { background: #b3261e; }
.rlq-rapport .evo-barre-signal {
  outline: 2px solid #d93025; outline-offset: 1px;
}
.rlq-rapport .evo-legende-controle { font-size: .78rem; margin-top: .4rem; }
.rlq-rapport .evo-derive-baisse { color: #b3261e; font-weight: 600; font-size: .85rem; margin-top: .4rem; }
.rlq-rapport .evo-derive-hausse { color: #1f7a3d; font-weight: 600; font-size: .85rem; margin-top: .4rem; }
.rlq-rapport .evo-barre-date { font-size: .68rem; color: var(--texte-attenue); margin-top: .3rem; text-align: center; }
/* Empêche une impression exploitable (Ctrl+P, "Imprimer en PDF") du
   rapport à l'écran ou du fichier HTML déchiffré dans le navigateur :
   bloquer littéralement la combinaison de touches n'est pas fiable
   d'un navigateur à l'autre, mais masquer tout le contenu à
   l'impression - remplacé par un message explicite - empêche
   concrètement d'obtenir une copie utilisable de cette façon. Repose
   sur le respect standard de @media print par le navigateur - pas
   infaillible face à un navigateur trafiqué ou une capture d'écran
   manuelle, voir la documentation utilisateur pour les limites. */
@media print {
  .rlq-rapport * { visibility: hidden !important; }
  .rlq-rapport::before {
    visibility: visible !important;
    content: "🔒 Impression désactivée : ce rapport contient des renseignements personnels protégés.";
    display: block; text-align: center; padding: 4rem 2rem; font-size: 1.1rem;
    position: absolute; top: 0; left: 0; right: 0;
  }
}
"""
