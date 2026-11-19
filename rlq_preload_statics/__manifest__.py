# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Dossiers static listés avant les workers / Static folders listed before the workers",
    "summary": "Module server-wide : le processus principal d'Odoo dresse une seule fois la liste des dossiers static de tous les modules, avant ses workers. "
               "Server-wide module: the main process of Odoo lists the static folders of every module once, before its workers.",
    "description": """
Dossiers static listés avant les workers
=========================================

Module « server-wide » : à mettre dans server_wide_modules (configuration d'Odoo), jamais à installer dans une base.

Chaque worker d'Odoo dresse la liste des dossiers static/ de tous les modules d'addons_path au premier fichier statique
qu'il sert (odoo.http.root.statics) : environ 10 s avec ERPLibre (135 dossiers, 4480 modules), payées par un visiteur ou
par le premier rapport PDF du worker. Ce module la fait dresser une seule fois par le processus principal, avant qu'il
crée ses workers : chaque worker en hérite, y compris ceux qui remplacent un worker recyclé.

Static folders listed before the workers
=========================================

Server-wide module: to put in server_wide_modules (Odoo configuration), never to install in a database.

Each Odoo worker lists the static/ folders of every module of addons_path at the first static file it serves
(odoo.http.root.statics): about 10 s with ERPLibre (135 folders, 4480 modules), paid by a visitor or by the first PDF
report of the worker. This module has the main process list them once, before it forks its workers: every worker
inherits the list, the ones that replace a recycled worker included.
""",
    "version": "18.0.1.0.0",
    "category": "Hidden/Tools",
    "author": "Services-Conseils Linux Inc., Rencontres Linux au Québec",
    "website": "https://github.com/Rencontres-Linux-au-Quebec/rlq-odoo-addons",
    "license": "AGPL-3",
    "depends": ["base"],
    "data": [],
    "post_load": "post_load",
    "installable": True,
    "auto_install": False,
    "application": False,
}
