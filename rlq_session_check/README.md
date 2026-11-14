# rlq_session_check

*Français plus bas.*

Route `/rlq/session/check` that tells **nginx** (`auth_request`) whether the browser that asks is signed in to Odoo.
Used by `nginx-link-page.sh` ([rlq-admin-tools](https://github.com/Rencontres-Linux-au-Quebec/rlq-admin-tools)) with
`LINK_n_ACCESS=odoo` (any signed-in user, portal included) or `LINK_n_ACCESS=odoo:base.group_user` (members of a group).

| Answer | When | nginx does |
|---|---|---|
| 204 | signed in, and in `?group=XMLID` when given | serves the page of the members |
| 401 | not signed in | sends to `/web/login?redirect=...` |
| 403 | signed in, not in the group; group not valid or unknown | refuses |

- The answer is empty (nothing about the user) and never cached (`private, no-store`, `Vary: Cookie`).
- It only describes the session of the browser that asks: it reveals nothing about anyone else.
- `save_session=False`: a visitor who is not signed in gets no new session.
- Any other answer (Odoo down, module not installed: 404) makes nginx refuse the access: never open by default.

## /rlq/session/me (18.0.1.1.0)

JSON read by the script of the link pages (`PAGE_n_GREETING=yes` of nginx-link-page): `{"signed_in": false}`, or
`{"signed_in": true, "first_name": "Marie"}`, plus `details` (name, address, e-mail, phone, visible groups) for the members of
the group set in the system parameter **`rlq_session_check.profile_group`** (XML id, default `base.group_user`; Settings >
Technical > System Parameters). Only the data of the person who asks; no CORS header (same site only); never cached.

Install: `odoo-bin -d DB -i rlq_session_check` (or Apps). Check: `curl -i https://SITE/rlq/session/check` answers `401`.

## Français

Route `/rlq/session/check` qui dit à **nginx** (`auth_request`) si le navigateur est connecté à Odoo. Utilisée par
`nginx-link-page.sh` avec `LINK_n_ACCESS=odoo` (toute personne connectée, portail compris) ou
`LINK_n_ACCESS=odoo:base.group_user` (membres d'un groupe).

- 204 : connecté (et membre de `?group=XMLID` s'il est donné) ; 401 : pas connecté (nginx envoie vers `/web/login`) ;
  403 : pas dans le groupe, ou groupe inconnu.
- Réponse vide, jamais mise en cache ; elle ne parle que de la session du navigateur qui demande.
- Toute autre réponse (Odoo arrêté, module absent) : nginx refuse l'accès, jamais ouvert par défaut.

`/rlq/session/me` (JSON) : le prénom à saluer et, pour les membres du groupe du paramètre système
`rlq_session_check.profile_group` (défaut `base.group_user`), nom, adresse, courriel, téléphone et groupes visibles.

Vérifier : `curl -i https://SITE/rlq/session/check` doit répondre `401`.
