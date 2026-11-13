# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Vérification de session pour nginx / Session check for nginx",
    "summary": "Route /rlq/session/check : dit à nginx (auth_request) si le navigateur est connecté à Odoo, et membre d'un groupe. "
               "Route /rlq/session/check: tells nginx (auth_request) whether the browser is signed in to Odoo, and in a group.",
    "description": """
Vérification de session pour nginx
==================================

La route /rlq/session/check répond à nginx (auth_request) :

* 204 : le navigateur est connecté à Odoo (portail compris), et membre du groupe ?group=XMLID s'il est donné ;
* 401 : pas connecté (nginx envoie alors vers /web/login) ;
* 403 : connecté mais pas dans le groupe, ou groupe inconnu (refusé, jamais ouvert par erreur).

La réponse est vide : rien sur l'utilisateur. Utilisée par nginx-link-page.sh (rlq-admin-tools, LINK_n_ACCESS=odoo)
pour montrer des liens réservés aux membres connectés.

Session check for nginx
=======================

/rlq/session/check answers nginx (auth_request): 204 signed in (and in ?group=XMLID), 401 not signed in, 403 not in
the group or unknown group. Empty answer. Used by nginx-link-page.sh (LINK_n_ACCESS=odoo).

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.0.0",
    "category": "Hidden/Tools",
    "author": "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), Rencontres Linux au Québec contributors",
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["web"],
    "data": [],
    "installable": True,
    "application": False,
}
