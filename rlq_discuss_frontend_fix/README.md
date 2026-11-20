# rlq_discuss_frontend_fix

*[Français](#français) · [English](#english)*

## Français

Corrige l'erreur JavaScript d'Odoo 18 affichée sur le site web quand un canal de discussion est supprimé :

```
UncaughtClientError > TypeError
Uncaught Javascript Error > thread.closeChatWindow is not a function
    at Proxy._handleNotificationChannelDelete (web.assets_frontend_lazy.min.js)
```

Quand un canal est supprimé (clavardage en direct fermé puis nettoyé, canal ou conversation supprimé), Odoo prévient tous
les navigateurs abonnés. Le code commun de la discussion appelle alors `thread.closeChatWindow()`, qui n'est défini que
dans l'interface d'administration (`mail/static/src/core/web/thread_model_patch.js`). Sur le site web et sur les pages
publiques de discussion, la fonction n'existe pas : l'erreur s'affiche et le canal supprimé reste dans la page.

Le module ajoute cette fonction aux paquets du site (`im_livechat.assets_embed_core`, inclus dans `web.assets_frontend`) et
des pages publiques (`mail.assets_public`). Elle ferme la fenêtre de discussion du canal s'il y en a une, comme dans
l'interface d'administration. L'interface d'administration n'est pas touchée. Si une version future d'Odoo définit
elle-même la fonction, c'est la sienne qui est appelée.

Installation : copier le dossier dans `addons_path`, mettre à jour la liste des applications, installer
« Discussion : plus d'erreur closeChatWindow sur le site ». Aucun redémarrage d'Odoo n'est nécessaire : les paquets de
fichiers sont régénérés à l'installation (les visiteurs reçoivent le nouveau paquet au prochain chargement de page).

## English

Fixes the Odoo 18 JavaScript error "thread.closeChatWindow is not a function" shown on the website when a discussion
channel is deleted: the common Discuss code calls a function defined only in the back-office bundle. The module adds
it to the website bundle (`im_livechat.assets_embed_core`, included in `web.assets_frontend`) and to the public
discussion pages (`mail.assets_public`); it closes the chat window of the channel, if any. The back-office is not
changed; when Odoo defines the function itself, Odoo's own is called. History of the changes: `doc/CHANGELOG.md`.
