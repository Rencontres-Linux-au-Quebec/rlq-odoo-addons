# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
{
    "name": "Événements : page de confirmation d'inscription sans erreur / Events: registration confirmation page without errors",
    "summary": "Remplace l'erreur 500 ou 404 de la page de confirmation d'inscription par une page de remerciement. "
               "Replaces the error 500 or 404 of the registration confirmation page by a thank-you page.",
    "description": """
Page de confirmation d'inscription sans erreur
==============================================

Dans Odoo 18, la page /event/<événement>/registration/success affiche :

* une erreur 500 quand elle est ouverte sans le paramètre registration_ids (page rechargée, lien copié incomplet) ;
* une erreur 404 quand le témoin (cookie) du visiteur n'est pas reconnu (autre navigateur, connexion, navigateur
  intégré d'une application de courriel), alors que l'inscription existe et que le courriel de confirmation est parti.

Des participants croient alors que l'inscription a échoué et s'inscrivent une deuxième fois.

Ce module garde la page d'Odoo quand le visiteur est reconnu. Sinon, il affiche que l'inscription est enregistrée et que
les billets sont dans le courriel, sans aucune donnée personnelle de l'inscription, ou explique comment vérifier son
inscription si aucune n'est trouvée.

Registration confirmation page without errors
=============================================

Replaces the error 500 (missing registration_ids) and the error 404 (visitor not recognised) of the registration
confirmation page by a page saying that the registration is recorded and the tickets are in the e-mail.

Copyright (C) 2026 Services-Conseils Linux Inc. (info@rencontres-linux.quebec)
Copyright (C) 2026 Rencontres Linux au Québec contributors
GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
""",
    "version": "18.0.1.0.0",
    "category": "Marketing/Events",
    "author": "Services-Conseils Linux Inc. (info@rencontres-linux.quebec), Rencontres Linux au Québec contributors",
    "maintainer": "Rencontres Linux au Québec <info@rencontres-linux.quebec>",
    "website": "https://www.rencontres-linux.quebec",
    "license": "AGPL-3",
    "depends": ["website_event"],
    "data": [
        "views/registration_templates.xml",
    ],
    "installable": True,
    "application": False,
}
