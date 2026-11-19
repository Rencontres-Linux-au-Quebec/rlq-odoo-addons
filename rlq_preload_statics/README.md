# rlq_preload_statics

## Français

Module **server-wide** : il se met dans `server_wide_modules` de la configuration d'Odoo et ne s'installe **jamais** dans une base.

**Pourquoi.** Chaque worker d'Odoo dresse la liste des dossiers `static/` de tous les modules d'`addons_path`
(`odoo.http.root.statics`) au premier fichier statique qu'il sert : un manifeste lu et une icône cherchée dans chaque
dossier d'`addons_path`, pour chaque module. Mesuré en DEV le 2026-11-18 : 135 dossiers, 4480 modules, **10,1 s** par worker,
payées par un visiteur ou par le premier rapport PDF du worker (wkhtmltopdf lit ses polices chez Odoo).

**Ce qu'il fait.** Odoo charge les modules server-wide dans son processus principal, avant de créer ses workers. Ce module y
dresse la liste une seule fois ; chaque worker en hérite à sa création, y compris ceux qui remplacent un worker recyclé
(nombre maximal de requêtes, limite de mémoire). Rien dans le processus gevent (discussion en direct). En cas d'échec, une
ligne d'erreur dans le journal et rien d'autre : chaque worker dresse alors la liste lui-même, comme avant.

**Activation.** Le dossier de ce dépôt doit être dans `addons_path`, puis :

```
server_wide_modules = base,rpc,web,rlq_preload_statics
```

et un redémarrage d'Odoo. `nginx-hardening.sh --update --odoo-preload-statics` (rlq-admin-tools) le fait, avec une copie de la
configuration avant. Le journal d'Odoo dit alors :
`rlq_preload_statics: static folders of N modules listed in X s, before the workers start`.

Le démarrage d'Odoo dure X s de plus (la liste est faite avant la première réponse). Réduire `addons_path` aux dossiers qui
contiennent un module installé (`nginx-hardening.sh --update --odoo-trim-addons-path`) réduit X.

## English

**Server-wide** module: it goes into `server_wide_modules` of the Odoo configuration and is **never** installed in a database.

**Why.** Each Odoo worker lists the `static/` folders of every module of `addons_path` (`odoo.http.root.statics`) at the first
static file it serves: a manifest read and an icon looked for in every folder of `addons_path`, for every module. Measured in DEV
on 2026-11-18: 135 folders, 4480 modules, **10.1 s** per worker, paid by a visitor or by the first PDF report of the worker
(wkhtmltopdf reads its fonts from Odoo).

**What it does.** Odoo loads the server-wide modules in its main process, before it forks its workers. This module builds the list
there once; every worker inherits it when it is created, the ones that replace a recycled worker included (maximum number of
requests, memory limit). Nothing in the gevent process (live chat). On a failure, one error line in the log and nothing else: each
worker then builds the list itself, as before.

**Enabling.** The folder of this repository must be in `addons_path`, then:

```
server_wide_modules = base,rpc,web,rlq_preload_statics
```

and a restart of Odoo. `nginx-hardening.sh --update --odoo-preload-statics` (rlq-admin-tools) does it, with a copy of the
configuration first. The Odoo log then says:
`rlq_preload_statics: static folders of N modules listed in X s, before the workers start`.

Odoo takes X s more to start (the list is built before the first answer). Reducing `addons_path` to the folders that hold an
installed module (`nginx-hardening.sh --update --odoo-trim-addons-path`) reduces X.
