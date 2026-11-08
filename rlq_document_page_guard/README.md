# rlq_document_page_guard

*[Français](#français) · [English](#english)*

## Français

Protège le wiki (module OCA `document_page`) contre les pages trop lourdes pour être ouvertes.

- **Nettoyage automatique** : à chaque enregistrement, l'attribut technique `data-last-history-steps` de l'éditeur
  ne garde que son dernier identifiant d'étape. Sans ce nettoyage, il grossit à chaque enregistrement (24 Mo pour une
  page de 528 mots le 7 novembre 2026).
- **Validation** : une nouvelle version de plus de 5 Mo est refusée avec un message qui explique quoi faire (téléverser
  les images au lieu de les coller, découper la page). Une page déjà trop lourde peut toujours être allégée.
- **À l'installation** : les versions déjà gonflées sont nettoyées.

Paramètres (Configuration > Technique > Paramètres système) :

| Clé | Défaut | Rôle |
| --- | --- | --- |
| `rlq_document_page_guard.keep_history_steps` | 1 | Identifiants d'étape gardés (0 = retirer l'attribut) |
| `rlq_document_page_guard.max_content_mb` | 5 | Taille maximale d'une nouvelle version, en Mo (0 = aucune limite) |

Pour nettoyer de nouveau l'historique depuis `odoo-bin shell` :
`env["document.page.history"]._rlq_trim_existing_history(); env.cr.commit()`

## English

Guards the wiki (OCA module `document_page`) against pages too large to be opened.

- **Automatic cleaning**: at every save, the editor's technical attribute `data-last-history-steps` keeps only its last
  step id. Without it, the attribute grows at every save.
- **Validation**: a new version above 5 MB is refused with a message explaining what to do. A page already too large can
  always be made lighter.
- **At installation**: the versions already swollen are cleaned.

Settings: `rlq_document_page_guard.keep_history_steps` (1) and `rlq_document_page_guard.max_content_mb` (5, 0 = no limit).
History of the changes: `doc/CHANGELOG.md`.
