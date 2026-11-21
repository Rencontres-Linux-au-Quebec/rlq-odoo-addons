# Event Raffle Prize Handover (Remise des prix)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

How a reserved raffle prize reaches its winner: picked up on site at a
pick-up location, sent by email when it is virtual, or shipped by hand to
a virtual winner. A phone screen lets the event team find a winner and
hand the prize over with a photo, and a public page lists the winners of
an event hour by hour. It builds on `event_raffle_prize_claim` (prize
link, winner shop, "Your prize" email) and `event_raffle_prize`
(catalogue, stock, claim rules). The French version follows the English
one.

## Description

Each reserved prize reaches the winner one of three ways, chosen from the
prize and the winner's attendance:

- **Pick-up**: a physical prize for a winner checked in at the event. The
  "Your prize" email and the confirmation page of the prize link say
  *Pick up your prize at (pick-up location)*. An event user hands it over
  from the draw (**Prize Handed Over**, unchanged) or from the hand-over
  screen.
- **Virtual prize**: a prize marked **Virtual prize (no delivery)**. The
  winner's checkout asks for a name and an email only. The email and the
  page say *Your prize will be sent to you by email*. On the draw, **Send
  the Virtual Prize** opens a message prefilled with the prize's
  instructions in the winner's language, adds an optional code, emails it
  and validates the delivery: the prize is handed over and one unit leaves
  the stock, so codes or licences are still counted. A virtual prize ships
  nowhere: its region applies to the winner's contact only, never to the
  delivery address of the order.
- **Shipping**: a physical prize for a virtual winner. The email and the
  page say *Your prize will be shipped to you*. On the draw, **Mark as
  Shipped** asks for the tracking number and, optionally, the carrier: the
  delivery is validated, the claim becomes **Shipped** and the winner
  receives an email with the tracking number. **Mark as Received** then
  sets it handed over. A shipped prize still counts toward the winner's
  quota. A carrier module may replace this manual step later.

### Public name

A contact may have a **Public name**, a nickname. Every public page of the
raffle shows the public name when it is set, else the winner's name as the
draw gives it: the attendee's own name, even when another person booked
the registration and is its contact. The winner sets it on the confirmation page of the prize link, or in **My
account** of the portal when signed in; an event user sets it on the draw
or on the contact.

### Hand-over screen

**Raffle > Prize Hand-over** opens `/raffle/handover`, made for a phone:
the reserved prizes to pick up, of the raffles that are not done, with a
search on the winner's name, public name, email or draw number. Each
winner shows the prize, its sponsor and its token category, and **Hand
over** opens the step: an optional photo taken with the phone's camera
(the winner with the sponsor), then **Confirm the hand-over**, which runs
the hand-over of the draw. The list then shows the prize handed over.
While the form is sent, the button says **Sending...** and another tap
sends nothing; the same form sent again just after the hand-over leads to
its success message, not to a refusal.

### Winners page

When the event's **Publish the winners page** is ticked,
`/raffle/winners/(event)` lists the winners of the event's raffles as
soon as they are drawn, newest first, grouped by hour in the event's time
zone: public name, prize, sponsor with a link, and token category. A
winner who has not chosen yet shows the token category and "prize to
choose", such as "Prize group A, prize to choose", until the choice
replaces it with the prize; a prize typed on the wheel shows only for a
draw that never had a prize link. A declined prize says "Prize declined",
and a claim that ended without a choice "No prize chosen"; such a winner
stays listed. The draws marked absent are left out, and a test raffle lists
its chosen prizes only. The page refreshes every 10 minutes in place,
without moving the focus, and announces the new winners; without
JavaScript it reloads itself. The event form gives the page's address.

## Configuration

- On each raffle, tab **Settings**, group **Prizes**: **Pick-up
  location**, such as a desk or a room.
- On a sponsored prize, tab **Sponsored Prize**: **Virtual prize (no
  delivery)** and its **Virtual prize instructions**, translatable.
- On the event: **Publish the winners page**.

## Usage

- On the phone of a volunteer with the event user rights, open **Raffle >
  Prize Hand-over**, or `/raffle/handover` on the website, search the
  winner, tap **Hand over**, take the photo if the sponsor is there, and
  confirm.
- For a virtual winner of a physical prize: ship it, then **Mark as
  Shipped** with the tracking number; **Mark as Received** once it
  arrives.
- For a virtual prize: **Send the Virtual Prize**, check the message, add
  the code, send.

## Security

- The hand-over screen is for event users only: a visitor gets the sign-in
  page, a portal user or an internal user without the event rights gets
  403, and nothing of the list is sent to them. It reads the draws with
  the user's own rights, and its confirmation is a POST with a CSRF token
  that runs the hand-over of `event_raffle_prize`, with its access checks.
- The hand-over photo is resized on the server to 1920 pixels on its
  largest side, checked to be an image, and kept in the draw's
  **Hand-over photo** and as an attachment of the draw. Neither is public:
  `/web/content` and `/web/image` refuse them to anyone who cannot read
  the draw.
- The public name form of the confirmation page is a POST with a CSRF
  token. It changes the contact of the claim this session confirmed and
  nothing else: the request gives the name only, never a contact or a
  draw. A session without a confirmed claim gets the page of an invalid
  link.
- The tracking number, the carrier, the shipping date and the photo are
  written by the buttons only, as the other claim fields.
- The winners page and its JSON data hold the public fields only: public
  name or winner's name, prize, the status of the prize (`chosen`,
  `to_choose`, `declined`, `expired`), sponsor and its link, token
  category, and the draw id, used to spot the new winners. No email, no
  address, no photo, no reason of a declined prize.
  Both answer 404 until the event publishes them, and on a website of
  another company than the event's. They list the raffles of the event's
  company, and those without one.
- The draws, their raffles and participants follow the company rules of
  `event_raffle`: the hand-over screen lists and opens the draws of the
  user's companies only, and answers 403 for a draw of another one.
- The code of a virtual prize goes in the email only: the notification log
  of the draw masks it.

## Accessibility

The hand-over screen, the public name forms and the winners page follow
WCAG 2.2 AA: labelled fields, visible focus, the body's colours, use with
the keyboard, and a layout that works at 390 pixels wide without sideways
scrolling. The buttons and fields of the hand-over screen and of the
public name form of the confirmation page are 48 pixels high at least;
the public name field of **My account** keeps the size of the portal's
other fields. The success message of a hand-over is a polite live region
that takes the focus, and the hand-over form says in a polite status
region that it is being sent. The winners page
announces the new winners in a polite live region, keeps the focus where
it is when it refreshes, and gives the time of the last update.

## Known issues / Roadmap

- The shipping is manual: a carrier module with weight, size, boxes and
  tracking will replace **Mark as Shipped**.
- The confirmation page shows the public name form only right after the
  claim, in the session that made it; later, the winner uses **My
  account**, or asks the event team.
- A raffle marked done leaves the hand-over screen: hand its prizes over
  from the draws.

## Development

Run the tests with the other raffle modules:

```bash
EWP_AXE_JS=/path/to/axe.min.js ./test.sh -d test_db \
  -i event_raffle_prize_handover,event_raffle_survey,website_sale_collect,payment_demo \
  --test-tags /event_raffle_prize_handover,/event_raffle_prize_claim,/event_raffle_prize,/event_raffle,/event_raffle_survey \
  --log-level=test --stop-after-init
```

Without `EWP_AXE_JS`, the accessibility test is skipped; when the variable
names a missing file, it fails. The winners page test runs its refresh in
a browser.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

This module is maintained as part of ERPLibre.

---

# Event Raffle Prize Handover (Remise des prix), français

Comment un prix réservé arrive à son gagnant : retiré sur place à un lieu
de retrait, envoyé par courriel quand il est virtuel, ou expédié à la main
à un gagnant virtuel. Un écran pour téléphone permet à l'équipe de
l'événement de trouver un gagnant et de lui remettre le prix avec une
photo, et une page publique liste les gagnants d'un événement heure par
heure. Le module s'appuie sur `event_raffle_prize_claim` (lien du
gagnant, boutique du gagnant, courriel « Votre prix ») et
`event_raffle_prize` (catalogue, stock, règles d'attribution).

## Description

Chaque prix réservé arrive au gagnant d'une de trois façons, selon le prix
et la présence du gagnant :

- **Retrait** : un prix physique pour un gagnant présent à l'événement.
  Le courriel « Votre prix » et la page de confirmation du lien disent
  *Lieu de retrait de votre prix : (lieu de retrait)*. Un utilisateur de
  l'événement le remet depuis le tir (**Prix remis**, inchangé) ou depuis
  l'écran de remise.
- **Prix virtuel** : un prix coché **Prix virtuel (sans livraison)**. Le
  paiement du gagnant ne demande qu'un nom et un courriel. Le courriel et
  la page disent *Votre prix vous sera envoyé par courriel*. Sur le tir,
  **Envoyer le prix virtuel** ouvre un message prérempli avec les
  instructions du prix dans la langue du gagnant, ajoute un code
  facultatif, l'envoie par courriel et valide la livraison : le prix est
  remis et une unité sort du stock, si bien que les codes ou licences
  restent comptés. Un prix virtuel n'est expédié nulle part : sa région
  s'applique au contact du gagnant seulement, jamais à l'adresse de
  livraison de la commande.
- **Expédition** : un prix physique pour un gagnant virtuel. Le courriel
  et la page disent *Votre prix vous sera expédié*. Sur le tir, **Marquer
  comme expédié** demande le numéro de suivi et, au besoin, le
  transporteur : la livraison est validée, l'attribution passe à
  **Expédié** et le gagnant reçoit un courriel avec le numéro de suivi.
  **Marquer comme reçu** la passe ensuite à remis. Un prix expédié compte
  toujours dans le quota du gagnant. Un module de transporteur pourra
  remplacer plus tard cette étape manuelle.

### Nom public

Un contact peut avoir un **Nom public**, un pseudo. Toutes les pages
publiques du tirage montrent le nom public s'il existe, sinon le nom du
gagnant tel que le tir le donne : celui du participant, même quand une
autre personne a fait l'inscription et en est le contact. Le gagnant le choisit sur la page de confirmation du lien, ou
dans **Mon compte** du portail une fois connecté ; un utilisateur de
l'événement le change sur le tir ou sur le contact.

### Écran de remise

**Tirage > Remise des prix** ouvre `/raffle/handover`, pensé pour un
téléphone : les prix réservés à retirer, des tirages qui ne sont pas
terminés, avec une recherche sur le nom, le nom public, le courriel ou le
numéro du tir. Chaque gagnant montre le prix, son commanditaire et sa
catégorie de jeton, et **Remettre** ouvre l'étape : une photo facultative
prise avec la caméra du téléphone (le gagnant avec le commanditaire), puis
**Confirmer la remise**, qui exécute la remise du tir. La liste montre
ensuite le prix remis. Pendant l'envoi du formulaire, le bouton affiche
**Envoi en cours...** et un autre toucher n'envoie rien ; le même
formulaire renvoyé juste après la remise mène à son message de réussite,
pas à un refus.

### Page des gagnants

Quand la case **Publier la page des gagnants** de l'événement est cochée,
`/raffle/winners/(événement)` liste les gagnants des tirages de
l'événement dès leur tir, du plus récent au plus ancien, groupés par
heure dans le fuseau horaire de l'événement : nom public, prix,
commanditaire avec un lien, et catégorie de jeton. Un gagnant qui n'a pas
encore choisi affiche la catégorie de jeton et « prix à choisir », par
exemple « Groupe de prix A, prix à choisir », jusqu'à ce que son choix la
remplace par le prix ; un prix tapé sur la roue ne s'affiche que pour un
tir qui n'a jamais eu de lien de prix. Un prix refusé indique « Prix
refusé », et une attribution terminée sans choix « Aucun prix choisi » ;
ce gagnant reste dans la liste. Les tirs marqués absents n'y sont pas, et un tirage de
test ne liste que ses prix choisis. La page se rafraîchit toutes les 10
minutes sur place, sans déplacer
le focus, et annonce les nouveaux gagnants ; sans JavaScript, elle se
recharge. Le formulaire de l'événement donne l'adresse de la page.

## Configuration

- Sur chaque tirage, onglet **Paramètres**, groupe **Prix** : **Lieu de
  retrait**, comme un comptoir ou une salle.
- Sur un prix commandité, onglet **Prix commandité** : **Prix virtuel
  (sans livraison)** et ses **Instructions du prix virtuel**,
  traduisibles.
- Sur l'événement : **Publier la page des gagnants**.

## Utilisation

- Sur le téléphone d'un bénévole qui a les droits d'utilisateur de
  l'événement, ouvrir **Tirage > Remise des prix**, ou `/raffle/handover`
  sur le site, chercher le gagnant, toucher **Remettre**, prendre la photo
  si le commanditaire est là, et confirmer.
- Pour un gagnant virtuel d'un prix physique : l'expédier, puis **Marquer
  comme expédié** avec le numéro de suivi ; **Marquer comme reçu** une
  fois arrivé.
- Pour un prix virtuel : **Envoyer le prix virtuel**, relire le message,
  ajouter le code, envoyer.

## Sécurité

- L'écran de remise est réservé aux utilisateurs de l'événement : un
  visiteur reçoit la page de connexion, un utilisateur du portail ou un
  utilisateur interne sans les droits de l'événement reçoit 403, et rien
  de la liste ne lui est envoyé. Il lit les tirs avec les droits de
  l'utilisateur, et sa confirmation est un POST avec un jeton CSRF qui
  exécute la remise d'`event_raffle_prize`, avec ses contrôles d'accès.
- La photo de remise est redimensionnée sur le serveur à 1920 pixels sur
  son plus grand côté, vérifiée comme image, et gardée dans la **Photo de
  remise** du tir et en pièce jointe du tir. Aucune n'est publique :
  `/web/content` et `/web/image` les refusent à qui ne peut pas lire le
  tir.
- Le formulaire du nom public de la page de confirmation est un POST avec
  un jeton CSRF. Il change le contact de l'attribution que cette session a
  confirmée, et rien d'autre : la requête ne donne que le nom, jamais un
  contact ni un tir. Une session sans attribution confirmée reçoit la page
  d'un lien invalide.
- Le numéro de suivi, le transporteur, la date d'expédition et la photo ne
  s'écrivent que par les boutons, comme les autres champs d'attribution.
- La page des gagnants et ses données JSON ne portent que les champs
  publics : nom public ou nom du gagnant, prix, état du prix (`chosen`,
  `to_choose`, `declined`, `expired`), commanditaire et son lien,
  catégorie de jeton, et l'identifiant du tir, qui sert à repérer les
  nouveaux gagnants.
  Aucun courriel, aucune adresse, aucune photo, aucun motif de refus. Les deux répondent 404 tant
  que l'événement ne les publie pas, et sur le site web d'une autre
  société que celle de l'événement. Elles listent les tirages de la
  société de l'événement, et ceux sans société.
- Les tirs, leurs tirages et leurs participants suivent les règles de
  société d'`event_raffle` : l'écran de remise ne liste et n'ouvre que les
  tirs des sociétés de l'utilisateur, et répond 403 pour un tir d'une
  autre société.
- Le code d'un prix virtuel ne va que dans le courriel : le journal des
  notifications du tir le masque.

## Accessibilité

L'écran de remise, les formulaires du nom public et la page des gagnants
suivent WCAG 2.2 AA : champs étiquetés, focus visible, couleurs du corps
de page, usage au clavier, et une mise en page qui fonctionne à 390
pixels de large sans défilement horizontal. Les boutons et les champs de
l'écran de remise et du formulaire du nom public de la page de
confirmation font au moins 48 pixels de haut ; le champ du nom public de
**Mon compte** garde la taille des autres champs du portail. Le message
de réussite d'une remise est une zone annoncée poliment qui prend le
focus, et le formulaire de remise dit dans une zone de statut polie qu'il
est en cours d'envoi. La page des gagnants annonce les nouveaux gagnants dans une zone
polie, garde le focus en place quand elle se rafraîchit, et donne l'heure
de la dernière mise à jour.

## Problèmes connus / Feuille de route

- L'expédition est manuelle : un module de transporteur avec poids,
  dimensions, boîtes et suivi remplacera **Marquer comme expédié**.
- La page de confirmation ne montre le formulaire du nom public que juste
  après l'attribution, dans la session qui l'a faite ; ensuite, le gagnant
  passe par **Mon compte** ou demande à l'équipe de l'événement.
- Un tirage marqué terminé quitte l'écran de remise : remettre ses prix
  depuis les tirs.

## Développement

Les commandes de test sont celles de la section *Development* ci-dessus.
Sans `EWP_AXE_JS`, le test d'accessibilité se met de côté ; si la
variable nomme un fichier absent, il échoue. Le test de la page des
gagnants exécute son rafraîchissement dans un navigateur.

## Crédits

### Auteurs

- TechnoLibre

### Contributeurs

- Mathieu Benoit

### Mainteneurs

Ce module est maintenu dans le cadre d'ERPLibre.
