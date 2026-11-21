# Event Web App Plan - Raffle Prizes (`event_webapp_plan_raffle`)

*[English](#english) · [Français](#français)*

## English

Odoo 18.0 module. It brings the raffle prizes of
`event_raffle_prize_handover` into the web app of `event_webapp_plan`
(`/webapp_event`): a **My prize** card for the logged-in winner, the
**public name** of the winners page, and an optional **I am on site**
toggle. The generic module `event_webapp_plan` keeps no dependency on the prize
modules: only this bridge brings them.

### Setup

1. Install the module; it needs `event_webapp_plan` and
   `event_raffle_prize_handover`.
2. In **Event Web App > Event days**, the day lists its events; the raffles
   of those events, and the raffles listed on the day, are the raffles of
   the card. The raffle block lists the raffles listed on the day only
   (tab **Raffles** of the day): list a raffle there to show its winners
   in the web app.
3. Nothing else for the card: it reads the draws, their prize link and
   their claim, as the raffle and prize modules set them.
4. **On-site card** (**Settings > Event Web App > Home page**, off by
   default, also on a database that updates the module): tick it to show
   the **On site** card on every day of the web app.

### What the attendee sees

- **My prize** (home page, first card of the main column, slot
  `webapp_slot_home_cards`): one item per draw of the day whose winner is
  the contact of the logged-in user (draws marked absent left out). Each
  item has a heading (raffle and draw number), the prize, its sponsor and
  token category, and its state in words:
  - prize link open: "Choose your prize before <time>." and the button
    **Choose my prize**, the prize link of that winner;
  - no link yet, or the link expired: a sentence that says so;
  - prize reserved: how it reaches the winner, from
    `event_raffle_prize_handover` (pick-up location, sent by email, or
    shipped);
  - shipped: the tracking number and the carrier;
  - handed over, sent, received; declined; expired.
  The card is hidden for a user who won nothing.
- **Public name**: under the items, "Your name on the winners page", the
  name shown now and a form to set it (empty shows the full name again).
  The winners page of `event_raffle_prize_handover` and the raffle block of
  the web app show it.
- **Raffles** (the raffle block of `event_webapp_plan`): a winner shows as
  soon as drawn, with the prize as on the winners page: the token
  category and "prize to choose" ("Prize group A, prize to choose", or
  "Prize to choose" without a category) until the winner chooses, then the
  prize; "Prize declined" for a declined prize and "No prize chosen" for a
  claim that ended without a choice. The live refresh and the new winner
  announcement of the block say the same text.
- **On site** (after the other cards), while the setting **On-site card**
  is ticked: for a user registered to an event of the day, a toggle button
  **I am on site**, and the time it was declared.

### Live updates

The script of the page (`static/src/webapp/prize.js`) asks
`/webapp_event/<day>/my_prize` every minute while the tab is visible, when
the tab shows again, two seconds after the raffle block of the web app sees
a new winner (`ewp:raffle-drawn`), and at the deadline of an open link.
When the answer changes, the body of the card is replaced (never while the
focus is inside it: the next change waits until the focus leaves), the
card shows or hides, and each item whose state is new is said once in the
shared live region ("Your prize, Morning, draw 3: Choose your prize before
3:45 PM."). The focus never moves. The row "My prize" of the automatic
updates of the web app counts down to the earliest of these requests.

The two forms post with fetch when the script runs: the block is
re-rendered, the focus stays on the field or the button, and the result is
said in the live region. Without script they post and come back to the home
page, which shows the result once.

### Self-declared attendance

`event.registration` gets **Declared on site** (`attendance_declared`) and
its time (`attendance_declared_date`), read only in the backend. The draw
form shows them for its winner, beside the attendance mode. They are
**information only**: the attendance mode of the raffles
(`attendance_mode`, module `event_raffle_prize`) still comes from the
check-in scan, and so do the eligibility, the quotas and the delivery mode.
The tests check that declaring changes none of them.

The setting **On-site card** (config parameter
`event_webapp_plan_raffle.onsite_card`) only shows or hides the card and
opens or closes its route: turning it off keeps the attendance already
declared, which the backend still shows and the card shows again once it
is back on. The check-in at the welcome desk does not depend on it.

### Access

- Every route is `auth="user"` and applies the checks of the web app: an
  unknown or archived day gives 404, a day outside its window gives 403 to
  a visitor (moderators may preview).
- The card reads the draws of the partner of the current user only
  (`event.webapp._ewp_prize_draws()`); no partner, draw or registration id
  of the request is read. The prize link (a token) reaches its own winner
  only. No e-mail, address or photo leaves the server.
- **JSON route** `/webapp_event/<day>/my_prize` (GET): `signature`,
  `count`, `html` (the body of the card).
- **Public name** `/webapp_event/<day>/public_name` (POST, CSRF): writes the
  public name of the user's contact, and of the contact of a prize order of
  their draws when that contact has no user account (a contact made by the
  claim). A contact of another account is never changed.
- **On site** `/webapp_event/<day>/presence` (POST, CSRF, `on_site` "1" or
  "0"): writes the registrations of the user's contact to the events of
  the day only; 404 while the setting **On-site card** is off.

### Accessibility

Headings (`h2` card, `h3` item), lists, words for every state (the bar
beside an item only repeats it), touch targets of 44 px and more, labels,
text-only mode (one column of text), no animation. The tests run axe-core
(WCAG 2.2 A and AA) on the home page at desktop and phone width, in the dark
scheme and in text-only mode.

### Tests

```bash
odoo-bin -d TEST_DB -i event_webapp_plan_raffle --test-enable \
    --http-port 8369 --gevent-port 8372 \
    --test-tags /event_webapp_plan_raffle --stop-after-init
```

Use a disposable database and free ports. `tests/test_models.py` covers the
draws of a day won by a contact, the registrations of a contact and the
declared attendance (attendance mode unchanged), the setting **On-site
card** (off by default, written by the settings form);
`tests/test_controllers.py`
the card (hidden, prize link of its own winner, states with the pick-up
location, e-mail and tracking number), the JSON route, the public name form
(CSRF, own contact only, raffle block), the toggle (CSRF, own registrations
only; absent with its route while the setting is off, the declared
attendance kept), the text-only mode and French; `tests/test_selenium_prize.py`, in a
real browser, the card that comes in with a new draw, both forms by
keyboard, and axe-core when `EWP_AXE_JS` names a copy of `axe.min.js` (the
test skips without the variable and fails when the file is missing).

## Français

Module Odoo 18.0. Il amène les prix de tirage de
`event_raffle_prize_handover` dans l'app web de `event_webapp_plan`
(`/webapp_event`) : une carte **Mon prix** pour la personne gagnante
connectée, le **nom public** de la page des gagnants et un bouton optionnel
**Je suis sur place**. Le module générique `event_webapp_plan` ne dépend pas des
modules de prix : seul ce pont les amène.

### Mise en place

1. Installer le module ; il demande `event_webapp_plan` et
   `event_raffle_prize_handover`.
2. Dans **App web d'événement > Journées**, la journée liste ses
   événements ; les tirages de ces événements, et ceux listés sur la
   journée, sont les tirages de la carte. Le bloc des tirages ne liste que
   les tirages listés sur la journée (onglet **Tirages** de la journée) :
   y lister un tirage pour montrer ses gagnants dans l'app web.
3. Rien d'autre pour la carte : elle lit les tirs, leur lien de prix et
   leur attribution, tels que les modules de tirage et de prix les
   tiennent.
4. **Carte « Sur place »** (**Paramètres > Application web d'événement >
   Page d'accueil**, désactivée par défaut, aussi sur une base qui met le
   module à jour) : la cocher pour afficher la carte **Sur place** sur
   toutes les journées de l'app web.

### Ce que voit la personne inscrite

- **Mon prix** (accueil, première carte de la colonne principale, gabarit
  `webapp_slot_home_cards`) : un élément par tir de la journée gagné par le
  contact de l'utilisateur connecté (les tirs marqués absents exclus). Chaque
  élément porte un titre (tirage et numéro du tir), le prix, son
  commanditaire et sa catégorie de jeton, et son état en mots :
  - lien de prix ouvert : « Choisissez votre prix avant <heure>. » et le
    bouton **Choisir mon prix**, le lien de cette personne ;
  - pas encore de lien, ou lien expiré : une phrase le dit ;
  - prix réservé : comment il arrive à la personne, selon
    `event_raffle_prize_handover` (lieu de retrait, courriel ou expédition) ;
  - expédié : le numéro de suivi et le transporteur ;
  - remis, envoyé, reçu ; refusé ; expiré.
  La carte reste masquée pour qui n'a rien gagné.
- **Nom public** : sous les éléments, « Votre nom sur la page des
  gagnants », le nom affiché et un formulaire pour le changer (vide, le nom
  complet revient). La page des gagnants de `event_raffle_prize_handover` et
  le bloc des tirages de l'app web l'affichent.
- **Tirages** (le bloc des tirages de `event_webapp_plan`) : un gagnant
  apparaît dès son tir, avec le prix comme sur la page des gagnants : la
  catégorie de jeton et « prix à choisir » (« Groupe de prix A, prix à
  choisir », ou « Prix à choisir » sans catégorie) jusqu'au choix, puis le
  prix ; « Prix refusé » pour un prix refusé et « Aucun prix choisi » pour
  une attribution terminée sans choix. Le rafraîchissement en direct et
  l'annonce des nouveaux gagnants du bloc disent le même texte.
- **Sur place** (après les autres cartes), tant que le paramètre **Carte
  « Sur place »** est coché : pour une personne inscrite à un événement de
  la journée, un bouton à bascule **Je suis sur place** et l'heure de la
  déclaration.

### Mises à jour en direct

Le script de la page (`static/src/webapp/prize.js`) interroge
`/webapp_event/<journée>/my_prize` chaque minute tant que l'onglet est
visible, quand l'onglet revient, deux secondes après que le bloc des
tirages voit un nouveau gagnant (`ewp:raffle-drawn`), et à l'échéance d'un
lien ouvert. Quand la réponse change, le corps de la carte est remplacé
(jamais pendant que le focus y est : le changement attend qu'il en sorte),
la carte s'affiche ou se masque, et chaque élément dont l'état est nouveau
est annoncé une fois dans la région live partagée. Le focus ne bouge
jamais. La ligne « Mon prix » des mises à jour automatiques de l'app web
compte à rebours jusqu'à la plus proche de ces requêtes.

Les deux formulaires passent par fetch quand le script tourne : le bloc
est réaffiché, le focus reste sur le champ ou le bouton, et le résultat est
annoncé. Sans script, ils sont envoyés et reviennent à l'accueil, qui
affiche le résultat une fois.

### Présence déclarée

`event.registration` reçoit **Déclaré sur place** (`attendance_declared`)
et son heure (`attendance_declared_date`), en lecture seule dans le
backend. La fiche du tir les montre pour sa personne gagnante, à côté du
mode de participation. C'est **à titre d'information seulement** : le mode
de participation des tirages (`attendance_mode`, module
`event_raffle_prize`) vient toujours de la lecture du billet à l'accueil,
comme l'admissibilité, les quotas et le mode de remise. Les tests vérifient
qu'une déclaration ne change aucun d'eux.

Le paramètre **Carte « Sur place »** (paramètre de configuration
`event_webapp_plan_raffle.onsite_card`) ne fait qu'afficher ou masquer la
carte et ouvrir ou fermer sa route : le désactiver conserve la présence
déjà déclarée, que le backend montre toujours et que la carte affiche de
nouveau une fois réactivée. L'enregistrement à l'accueil n'en dépend pas.

### Accès

- Toutes les routes sont `auth="user"` et suivent les contrôles de l'app
  web : journée inconnue ou archivée, 404 ; journée hors de sa fenêtre,
  403 pour un visiteur (les modérateurs peuvent la prévisualiser).
- La carte ne lit que les tirs du contact de l'utilisateur courant
  (`event.webapp._ewp_prize_draws()`) ; aucun identifiant de contact, de tir
  ou d'inscription venu de la requête n'est lu. Le lien de prix (un jeton)
  ne va qu'à sa propre personne gagnante. Aucun courriel, adresse ni photo
  ne quitte le serveur.
- **Route JSON** `/webapp_event/<journée>/my_prize` (GET) : `signature`,
  `count`, `html` (le corps de la carte).
- **Nom public** `/webapp_event/<journée>/public_name` (POST, CSRF) : écrit
  le nom public du contact de l'utilisateur, et celui du contact d'une
  commande de prix de ses tirs quand ce contact n'a pas de compte (un
  contact créé par l'attribution). Le contact d'un autre compte n'est
  jamais modifié.
- **Sur place** `/webapp_event/<journée>/presence` (POST, CSRF, `on_site`
  « 1 » ou « 0 ») : n'écrit que les inscriptions du contact de
  l'utilisateur aux événements de la journée ; 404 tant que le paramètre
  **Carte « Sur place »** est désactivé.

### Accessibilité

Titres (`h2` pour la carte, `h3` pour un élément), listes, des mots pour
chaque état (la barre à côté d'un élément ne fait que le répéter), cibles
tactiles de 44 px et plus, étiquettes, mode texte seul (une colonne de
texte), aucune animation. Les tests lancent axe-core (WCAG 2.2 A et AA) sur
l'accueil, en largeur bureau et téléphone, en thème sombre et en mode texte
seul.

### Tests

Voir la commande de la section anglaise. `tests/test_models.py`,
`tests/test_controllers.py` et `tests/test_selenium_prize.py` couvrent les
tirs d'une journée, la présence déclarée (mode de participation inchangé),
le paramètre **Carte « Sur place »** (désactivé par défaut, absent avec sa
route une fois désactivé, présence déclarée conservée), la carte et ses
états, la route JSON, les deux formulaires (CSRF, contact
et inscriptions de l'utilisateur seulement), le mode texte seul, le
français, et axe-core quand `EWP_AXE_JS` nomme une copie de `axe.min.js`.

## License / Licence

AGPL-3.0 or later. Copyright (C) 2026 Services-Conseils Linux Inc.,
Rencontres Linux au Québec contributors.
