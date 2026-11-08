# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Wiki : protection contre les pages trop lourdes / Wiki: guard against oversized pages",
    "summary": "Nettoie l'attribut data-last-history-steps et refuse les pages wiki trop lourdes. "
               "Cleans the data-last-history-steps attribute and refuses oversized wiki pages.",
    "description": """
Wiki : protection contre les pages trop lourdes
===============================================

Le 7 novembre 2026, des pages du wiki (module OCA document_page) ne s'ouvraient plus (MemoryError) : l'attribut
technique data-last-history-steps de l'éditeur collaboratif grossissait à chaque enregistrement (24 Mo pour une page
de 528 mots), et chaque version de l'historique en gardait une copie.

Ce module :

* nettoie chaque contenu enregistré dans une page ou son historique : l'attribut ne garde que son dernier identifiant
  d'étape, le seul que l'éditeur utilise (paramètre rlq_document_page_guard.keep_history_steps) ;
* refuse une nouvelle version de plus de 5 Mo (paramètre rlq_document_page_guard.max_content_mb, 0 = aucune limite),
  sauf si elle n'est pas plus lourde que la version actuelle, pour qu'une page lourde puisse toujours être allégée ;
* nettoie à l'installation les versions déjà gonflées.

Guard against oversized wiki pages
==================================

Cleans the data-last-history-steps attribute of every saved content (only the last step id is kept), refuses a new
version above 5 MB unless it is not larger than the current one, and cleans the stored versions at installation.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.0.0",
    "category": "Knowledge",
    "author": "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), Rencontres Linux au Québec contributors",
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["document_page"],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
