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

## English

The registration confirmation page of an event no longer shows an error 500 or 404: a recognised visitor still sees
Odoo's page with the tickets; otherwise the page says that the registration is recorded and that the tickets are in the
confirmation e-mail, without showing any personal data. History of the changes: `doc/CHANGELOG.md`.
