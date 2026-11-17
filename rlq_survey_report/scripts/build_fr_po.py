# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Rebuilds i18n/fr.po: scripts/fr_base.po (the entries of the older screens) + every term of the registration desk and
volunteers screens (models/event_registration_desk.py, models/volunteer_coordinator.py, views/event_registration_desk_views.xml).

Why a script: Odoo attaches a translation to a view, field, menu or action through the « #: » reference of its entry, and loads
the translation of a Python string only when the entry carries the comment « #. odoo-python ». Entries written by hand without
them stay in English on screen (seen in 18.0.1.121.0 and 18.0.1.122.0). The terms are extracted from the sources, so that none
is forgotten; each one must have a French translation in FR below, otherwise the script stops and names it.

Usage, from the module directory, after adding or changing a label of those screens (add its translation to FR first):

    python3 scripts/build_fr_po.py
"""
import ast
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict

MODULE = "rlq_survey_report"
root_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_po = sys.argv[2] if len(sys.argv) > 2 else os.path.join(root_dir, "scripts", "fr_base.po")

FR = {
    # survey.question
    "Show at the registration desk": "Afficher au bureau d'inscription",
    "If checked, the answer of each registered person to this question is shown in the RLQ registration desk of the event (Events > RLQ registration desk), and the answers are counted per ticket type. Useful for questions such as « On site or online? » or « Will you be there for lunch? ».":
        "Si coché, la réponse de chaque inscrit à cette question est affichée dans le bureau d'inscription RLQ de l'événement (Événements > Bureau d'inscription RLQ), et les réponses sont comptées par type de billet. Utile pour des questions comme « Sur place ou en ligne ? » ou « Serez-vous présent pour le dîner ? ».",
    "Short label at the registration desk": "Libellé court au bureau d'inscription",
    "Short name of this question in the registration desk (for example « Lunch »). Empty: the title of the question.":
        "Nom court de cette question dans le bureau d'inscription (par exemple « Dîner »). Vide : le titre de la question.",
    # event.registration
    "Left at": "Heure de départ",
    "Time when the person left the event, recorded with the « Left » button of the RLQ registration desk.":
        "Heure à laquelle la personne a quitté l'événement, enregistrée avec le bouton « Départ » du bureau d'inscription RLQ.",
    "Questions answered": "Questions répondues",
    "Questions answered / questions of the survey expected for this registration (pages excluded). Empty: no survey.":
        "Questions répondues / questions du sondage attendu pour cette inscription (pages exclues). Vide : aucun sondage.",
    "Answers": "Réponses",
    "Answers of this person to the survey questions checked « Show at the registration desk ».":
        "Réponses de cette personne aux questions du sondage cochées « Afficher au bureau d'inscription ».",
    # rlq.registration.desk
    "RLQ registration desk": "Bureau d'inscription RLQ",
    "Registration desk: %(event)s": "Bureau d'inscription : %(event)s",
    "Registration desk": "Bureau d'inscription",
    "Event": "Événement",
    "By default: the event in progress, otherwise the next one.": "Par défaut : l'événement en cours, sinon le prochain.",
    "Search": "Recherche",
    "Part of a name, an e-mail address or a company: only the matching registrations are listed. The summary always counts the whole event.":
        "Partie d'un nom, d'une adresse courriel ou d'une entreprise : seules les inscriptions correspondantes sont listées. Le sommaire compte toujours tout l'événement.",
    "Name, e-mail address or company": "Nom, adresse courriel ou entreprise",
    "Hide the people already present": "Masquer les personnes déjà présentes",
    "Survey": "Sondage",
    "Lists only the registrations whose survey is in this state.": "Liste seulement les inscriptions dont le sondage est dans cet état.",
    "All": "Tous",
    "Survey completed": "Sondage complété",
    "Survey started": "Sondage commencé",
    "Survey not started": "Sondage non commencé",
    "No survey": "Aucun sondage",
    "Sort by": "Trier par",
    "Order of the list below. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by ticket, then by name.":
        "Ordre de la liste ci-dessous. Les majuscules et les accents sont ignorés (« Élise » est classée avec les « e ») ; à valeur égale, le tri se fait par billet, puis par nom.",
    "Ticket": "Billet",
    "Name": "Nom",
    "Registration date": "Date d'inscription",
    "Status": "Statut",
    "Arrival": "Arrivée",
    "Departure": "Départ",
    "Descending": "Ordre décroissant",
    "Reverses the order of the list.": "Inverse l'ordre de la liste.",
    "Summary": "Sommaire",
    "Registrations": "Inscriptions",
    "Registrations listed": "Inscriptions listées",
    "Refresh": "Actualiser",
    "Open as a list": "Ouvrir en liste",
    "Present": "Présent",
    "Undo": "Annuler la présence",
    "Undo the presence of this person?": "Annuler la présence de cette personne ?",
    "Left": "Départ",
    "Undo the departure": "Annuler le départ",
    "Clear the departure time of this person?": "Effacer l'heure de départ de cette personne ?",
    "Registered on": "Inscrit le",
    "Arrived at": "Heure d'arrivée",
    "« Present » records the hour of arrival. The questions listed under « Answers » are the survey questions checked « Show at the registration desk ». A survey belongs to a registration when it was answered by the same contact or with the same e-mail address.":
        "« Présent » enregistre l'heure d'arrivée. Les questions listées sous « Réponses » sont les questions du sondage cochées « Afficher au bureau d'inscription ». Un sondage est rattaché à une inscription quand il a été rempli par le même contact ou avec la même adresse courriel.",
    "Person": "Personne",
    "Not present yet": "Pas encore présent",
    "Group By": "Regrouper par",
    "User guide": "Guide d'utilisation",
    "Export to a spreadsheet": "Exporter dans un chiffrier",
    "The spreadsheet export needs the Python library « openpyxl », which is not installed on this server (pip install openpyxl).":
        "L'export dans un chiffrier nécessite la bibliothèque Python « openpyxl », qui n'est pas installée sur ce serveur (pip install openpyxl).",
    "Enter the password of the spreadsheet first: it contains names and e-mail addresses.":
        "Saisissez d'abord le mot de passe du chiffrier : il contient des noms et des adresses courriel.",
    "The password is too weak, it lacks: %(criteria)s.": "Le mot de passe est trop faible, il lui manque : %(criteria)s.",
    "No volunteer to export for this event.": "Aucun bénévole à exporter pour cet événement.",
    "The survey « %(survey)s » has no question about the hour of arrival or of departure: the hours shown are those recorded at the registration desk (« Present », « Left »).":
        "Le sondage « %(survey)s » n'a pas de question sur l'heure d'arrivée ou de départ : les heures affichées sont celles enregistrées au bureau d'inscription (« Présent », « Départ »).",
    "Password of the spreadsheet": "Mot de passe du chiffrier",
    "The spreadsheet contains names and e-mail addresses: it is delivered in a ZIP archive encrypted with this password (same rules as the survey reports: at least 12 characters, with a lower-case letter, a capital letter, a digit and a special character). Pre-filled with the default password of the survey reports.":
        "Le chiffrier contient des noms et des adresses courriel : il est livré dans une archive ZIP chiffrée avec ce mot de passe (mêmes règles que les rapports de sondage : au moins 12 caractères, avec une minuscule, une majuscule, un chiffre et un caractère spécial). Pré-rempli avec le mot de passe par défaut des rapports de sondage.",
    # rlq.volunteer.coordinator
    "Volunteers": "Bénévoles",
    "Volunteers: %(event)s": "Bénévoles : %(event)s",
    "Lists only the volunteers whose survey is in this state.": "Liste seulement les bénévoles dont le sondage est dans cet état.",
    "Order of the table. Case and accents are ignored (« Élise » sorts with the « e »); equal values are sorted by name.":
        "Ordre du tableau. Les majuscules et les accents sont ignorés (« Élise » est classée avec les « e ») ; à valeur égale, le tri se fait par nom.",
    "Type": "Type",
    "Languages spoken": "Langues parlées",
    "Number of roles": "Nombre de rôles",
    "Reverses the order of the table.": "Inverse l'ordre du tableau.",
    "No question about the roles (title containing « rôle ») in the survey « %(survey)s ».":
        "Aucune question sur les rôles (titre contenant « rôle ») dans le sondage « %(survey)s ».",
    "No question about the languages (title containing « langue ») in the survey « %(survey)s ».":
        "Aucune question sur les langues (titre contenant « langue ») dans le sondage « %(survey)s ».",
    "The survey « %(survey)s » has no question about the type (on site or online): the type is deduced from the roles questions that the volunteer answered.":
        "Le sondage « %(survey)s » n'a pas de question sur le type (présentiel ou virtuel) : le type est déduit des questions sur les rôles auxquelles le bénévole a répondu.",
    "No question about the type (on site or online) in the survey « %(survey)s ».":
        "Aucune question sur le type (présentiel ou virtuel) dans le sondage « %(survey)s ».",
    "Some volunteer tickets have no survey: their volunteers are listed without answers.":
        "Certains billets bénévoles n'ont pas de sondage : leurs bénévoles sont listés sans réponses.",
}

terms = OrderedDict()          # msgid -> {"refs": [..], "python": bool}


def add(msgid, ref, python=False):
    msgid = " ".join(msgid.split())
    if not msgid:
        return
    entry = terms.setdefault(msgid, {"refs": [], "python": False})
    if ref not in entry["refs"]:
        entry["refs"].append(ref)
    entry["python"] = entry["python"] or python


# 1. views
tree = ET.parse(root_dir + "/views/event_registration_desk_views.xml")
for record in tree.getroot():
    xmlid = record.get("id")
    if record.tag == "menuitem":
        add(record.get("name"), "model:ir.ui.menu,name:%s.%s" % (MODULE, xmlid))
        continue
    model = record.get("model")
    if model in ("ir.actions.act_window", "ir.actions.act_url"):
        add(record.find("field[@name='name']").text, "model:%s,name:%s.%s" % (model, MODULE, xmlid))
    elif model == "ir.ui.view":
        ref = "model_terms:ir.ui.view,arch_db:%s.%s" % (MODULE, xmlid)
        arch = record.find("field[@name='arch']")
        for node in arch.iter():
            for attribute in ("string", "placeholder", "confirm", "help", "title"):
                if node.get(attribute):
                    add(node.get(attribute), ref)
            if node.tag in ("p", "span", "div", "label", "h1", "h2", "h3") and (node.text or "").strip():
                add(node.text, ref)


# 2. model fields and 3. _() calls
def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


for filename in ("event_registration_desk.py", "volunteer_coordinator.py"):
    source = open("%s/models/%s" % (root_dir, filename), encoding="utf-8").read()
    module_ast = ast.parse(source)
    code_ref = "code:addons/%s/models/%s:0" % (MODULE, filename)
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_" and node.args:
            text = literal(node.args[0])
            if isinstance(text, str):
                add(text, code_ref, python=True)
    for cls in [n for n in module_ast.body if isinstance(n, ast.ClassDef)]:
        attrs = {t.id: literal(s.value) for s in cls.body if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)}
        model = attrs.get("_name") or attrs.get("_inherit")
        if not model:
            continue
        under = model.replace(".", "_")
        if attrs.get("_name") and attrs.get("_description"):
            add(attrs["_description"], "model:ir.model,name:%s.model_%s" % (MODULE, under))
        for stmt in cls.body:
            if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)):
                continue
            func = stmt.value.func
            if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "fields"):
                continue
            field = stmt.targets[0].id
            kwargs = {k.arg: literal(k.value) for k in stmt.value.keywords}
            assert kwargs.get("string"), "field %s.%s has no string" % (model, field)
            add(kwargs["string"], "model:ir.model.fields,field_description:%s.field_%s__%s" % (MODULE, under, field))
            if kwargs.get("help"):
                add(kwargs["help"], "model:ir.model.fields,help:%s.field_%s__%s" % (MODULE, under, field))
            if func.attr == "Selection" and stmt.value.args:
                for value, label in literal(stmt.value.args[0]) or ():
                    add(label, "model:ir.model.fields.selection,name:%s.selection__%s__%s__%s" % (MODULE, under, field, value))

missing = [t for t in terms if t not in FR]
assert not missing, "no French translation for: %r" % missing
unused = [t for t in FR if t not in terms]
assert not unused, "translation without term: %r" % unused

# base file: header + entries; code entries get the « odoo-python » comment that Odoo requires to load them
base = open(base_po, encoding="utf-8").read().rstrip("\n")
header, _sep, body = base.partition("\n\n#. module:")
blocks = ["#. module:" + block for block in body.split("\n\n#. module:")]
out = []
for block in blocks:
    lines = block.split("\n")
    msgid = re.search(r'^msgid "(.*)"$', block, re.M).group(1)
    if any(line.startswith("#: code:") for line in lines) and "#. odoo-python" not in lines:
        lines.insert(1, "#. odoo-python")
    if msgid in terms:                                       # same English text already in the base file: add the references
        extra = terms.pop(msgid)
        assert re.search(r'^msgstr "(.*)"$', block, re.M).group(1) == FR[msgid], "different translation for %r" % msgid
        if extra["python"] and "#. odoo-python" not in lines:
            lines.insert(1, "#. odoo-python")
        at = max(i for i, line in enumerate(lines) if line.startswith("#"))
        lines[at + 1:at + 1] = ["#: " + ref for ref in extra["refs"] if "#: " + ref not in lines]
    out.append("\n".join(lines))
for msgid, entry in terms.items():
    lines = ["#. module: %s" % MODULE] + (["#. odoo-python"] if entry["python"] else [])
    lines += ["#: " + ref for ref in entry["refs"]]
    assert '"' not in msgid and '"' not in FR[msgid] and "\\" not in msgid
    lines += ['msgid "%s"' % msgid, 'msgstr "%s"' % FR[msgid]]
    out.append("\n".join(lines))
open(root_dir + "/i18n/fr.po", "w", encoding="utf-8").write(header + "\n\n" + "\n\n".join(out) + "\n")
ids = re.findall(r'^msgid "(.+)"$', "\n".join(out), re.M)
assert len(ids) == len(set(ids)), "duplicate msgid"
print("entries:", len(out), "- desk/volunteers terms:", len(FR))
