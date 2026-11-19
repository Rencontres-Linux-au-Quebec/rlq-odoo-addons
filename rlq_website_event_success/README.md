# rlq_website_event_success

*[Français](#français) · [English](#english)*

## Français

La page de confirmation d'une inscription à un événement (`/event/<événement>/registration/success`) n'affiche plus
d'erreur 500 ou 404.

| Situation | Odoo 18 seul | Avec ce module |
| --- | --- | --- |
| Visiteur reconnu | Page de confirmation avec les billets | Inchangé |
| Inscription trouvée, visiteur non reconnu (autre navigateur, connexion, application de courriel) | Erreur 404 | « Votre inscription est enregistrée », billets dans le courriel |
| Adresse sans `?registration_ids=` ou inscription introuvable | Erreur 500 ou 404 | Explication et bouton pour s'inscrire |

Aucune donnée personnelle d'une inscription n'est montrée à un visiteur non reconnu.

La page des billets (`/event/<id>/my_tickets`, lien des courriels) répond 404 au lieu d'une erreur 500 quand
`registration_ids` ou `tickets_hash` manque ou est illisible, par exemple quand le scanneur de liens d'un fournisseur de
courriel rejoue le lien du rappel en le modifiant. Un lien valide donne toujours les billets, comme dans Odoo.

## English

The registration confirmation page of an event no longer shows an error 500 or 404: a recognised visitor still sees
Odoo's page with the tickets; otherwise the page says that the registration is recorded and that the tickets are in the
confirmation e-mail, without showing any personal data. The ticket page (`/event/<id>/my_tickets`) answers 404
instead of an error 500 when `registration_ids` or `tickets_hash` is missing or unreadable (for example when an e-mail
link scanner replays the reminder link with changes); a valid link still gives the tickets. History of the changes: `doc/CHANGELOG.md`.
