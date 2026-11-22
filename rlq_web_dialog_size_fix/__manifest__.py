# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Agrandir les dialogues : plus de boucle quand la session expire / Dialog size: no loop when the session expires",
    "summary": "Empêche web_dialog_size d'ouvrir des centaines de dialogues « Session expirée » à la suite. "
               "Stops web_dialog_size from opening hundreds of \"Session expired\" dialogs in a row.",
    "description": """
Agrandir les dialogues : plus de boucle quand la session expire
===============================================================

Le module OCA web_dialog_size ajoute un bouton « agrandir » à chaque dialogue. Ce bouton demande sa configuration au
serveur (ir.config_parameter.get_web_dialog_size_config) dès sa création, mais ne prend en charge l'échec de cette
demande qu'une fois le dialogue affiché. Quand la session Odoo a expiré, la demande échoue avant l'affichage : Odoo
ouvre alors le dialogue « Session expirée », qui a lui aussi le bouton, qui refait la demande, qui échoue encore...
Le 2026-11-20, un navigateur a ainsi envoyé plusieurs centaines de requêtes en une seconde, jusqu'à la limite de débit
de nginx (réponses 429).

Ce module prend en charge l'échec de la demande dès sa création : le dialogue « Session expirée » s'affiche une seule
fois, comme sans web_dialog_size.

Dialog size: no loop when the session expires
=============================================

The expand button of the OCA module web_dialog_size asks the server for its configuration when it is created, but
handles a failure only once the dialog is mounted. With an expired session, the failure comes first: Odoo opens the
"Session expired" dialog, which has the button too, which asks again... This module handles the failure as soon as the
request is made: the "Session expired" dialog is shown once.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.0.0",
    "category": "Hidden",
    "author": "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), Rencontres Linux au Québec contributors",
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["web_dialog_size"],
    "assets": {
        "web.assets_backend": [
            "rlq_web_dialog_size_fix/static/src/expand_button_patch.esm.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
