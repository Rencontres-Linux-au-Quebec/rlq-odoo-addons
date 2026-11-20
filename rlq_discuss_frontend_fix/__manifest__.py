# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Discussion : plus d'erreur « closeChatWindow » sur le site / Discuss: no more \"closeChatWindow\" error on the website",
    "summary": "Corrige l'erreur JavaScript « thread.closeChatWindow is not a function » quand un canal de discussion est supprimé. "
               "Fixes the JavaScript error \"thread.closeChatWindow is not a function\" when a discussion channel is deleted.",
    "description": """
Plus d'erreur « closeChatWindow » sur le site
=============================================

Dans Odoo 18, quand un canal de discussion est supprimé (canal de clavardage en direct fermé et nettoyé, canal ou
conversation supprimé), le serveur l'annonce à tous les navigateurs abonnés. Sur le site web (et sur les pages
publiques de discussion), Odoo appelle alors thread.closeChatWindow(), une fonction qui n'existe que dans l'interface
d'administration : le navigateur affiche « UncaughtClientError > TypeError : thread.closeChatWindow is not a function »
et le canal supprimé n'est pas retiré de la page.

Ce module ajoute la fonction manquante aux paquets de fichiers du site (im_livechat.assets_embed_core, inclus dans
web.assets_frontend) et des pages publiques (mail.assets_public). Elle ferme la fenêtre de discussion du canal s'il y en
a une. Si une version future d'Odoo fournit cette fonction, c'est la sienne qui est appelée.

No more "closeChatWindow" error on the website
==============================================

In Odoo 18, when a discussion channel is deleted, the website and the public discussion pages call
thread.closeChatWindow(), which exists only in the back-office bundle: the browser shows "UncaughtClientError >
TypeError: thread.closeChatWindow is not a function". This module adds the missing function to the website and public
bundles; it closes the chat window of the channel, if any. When Odoo provides the function, Odoo's own is called.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.0.0",
    "category": "Productivity/Discuss",
    "author": "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), Rencontres Linux au Québec contributors",
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["mail", "im_livechat"],
    "assets": {
        # Website (web.assets_frontend includes it) and the external livechat embed.
        "im_livechat.assets_embed_core": [
            "rlq_discuss_frontend_fix/static/src/thread_model_patch.js",
        ],
        # Public discussion pages (/chat/..., /discuss/channel/...).
        "mail.assets_public": [
            "rlq_discuss_frontend_fix/static/src/thread_model_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
