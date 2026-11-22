# rlq_web_dialog_size_fix

*[Français](#français) · [English](#english)*

## Français

Corrige une boucle du module OCA `web_dialog_size` (Odoo 18) quand la session Odoo a expiré.

Le bouton « agrandir » que `web_dialog_size` ajoute à chaque dialogue demande sa configuration au serveur
(`ir.config_parameter/get_web_dialog_size_config`) dès sa création. L'échec de cette demande n'est pris en charge
qu'une fois le dialogue affiché. Avec une session expirée, l'échec arrive avant : Odoo ouvre le dialogue
« Session expirée », qui a lui aussi ce bouton, qui refait la demande, qui échoue encore, et ainsi de suite.

Le 2026-11-20 à 17:38:53, le navigateur d'un membre de l'équipe resté sur `/odoo/discuss` a envoyé ainsi plusieurs
centaines de requêtes en une seconde. nginx a fini par répondre 429 (limite de débit `odoo_general`), ce qui a arrêté la
boucle.

Le module prend en charge l'échec dès la création de la demande. Le dialogue « Session expirée » s'affiche une seule
fois, puis Odoo renvoie vers la page de connexion, comme sans `web_dialog_size`. Il s'installe tout seul avec
`web_dialog_size` (`auto_install`).

## English

Fixes a loop of the OCA module `web_dialog_size` (Odoo 18) when the Odoo session has expired: the expand button asks
for its configuration when it is created but handles the failure only once the dialog is mounted, so each "Session
expired" dialog opens another one. The module handles the failure at once; the dialog is shown a single time.
Installed automatically with `web_dialog_size`. History of the changes: `doc/CHANGELOG.md`.
