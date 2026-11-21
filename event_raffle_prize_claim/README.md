# Event Raffle Prize Claim (Lien du gagnant)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

A single-use prize link for each raffle winner, a website shop that shows
that winner the prizes they may take for their token, and the sale of
sponsored prizes to members while the sponsored shop is open. It builds on
`event_raffle_prize` (catalogue, token categories, stock, claim rules) and
`website_sale`. The French version follows the English one.

## Description

After a draw, the winner receives a message by chat or by email, from
OdooBot: *You won a prize (Prize Group B)! Choose it here: (link)
(valid 45 minutes)*. One token is one link and one prize. The link lasts
the **Link Validity** of the draw's token category, or the raffle's own
when the draw has no category. It opens for the winner's account only:
whoever opens it signs in first, and the sign-in page leads back to the
link (see *Winners and accounts*). A signed-in winner whose link is open
also finds the claim in the shop without opening the link. The link opens
the shop of the website, where the winner sees only the prizes of their draw's token category, their
attendance and their region, the closing prizes on a closing draw only,
with a unit left, while they are under quota: the rules of
`event_raffle_prize`. Each prize shows its sponsor, with a link to the
sponsor's website.

A banner on the shop, product, cart and checkout pages greets the winner,
gives their token and how long the link lasts, the time it stops working
and the minutes left, and offers **Decline the prize**. Every prize shows
its cost, the name of its token category, such as *Prize Group B*,
instead of a price: on the shop card, the product page, the product
snippets, the add-to-cart notification, the cart line and the order
summary, whose total is the token too. The cart holds one prize, one unit, at no
charge: the line keeps the value of the prize with a full discount, for the
sponsor reports. Choosing another prize replaces it. The checkout is in the
winner's name, with the free delivery method **Raffle prize handover**, and
**Confirm Order** reserves the prize: the claim of `event_raffle_prize`
runs then, under its locks, and the order becomes the prize order of the
draw. The winner then receives the **Your prize** email, in their
language: the prize, its token category, its sponsor with a link, and *We
will contact you about pick-up or delivery*, with no price nor order
number. It replaces the order confirmation email of website_sale for the
prize orders only.

## Sponsored prizes in the shop

While the sponsored shop is open, every visitor without a prize link sees
the published sponsored prizes in the shop:

- a prize marked **Sold to members** shows its price and goes to the cart
  as any product: it is paid and confirmed through the website's usual
  checkout, with any payment method the website offers, and the member
  receives Odoo's standard order confirmation. The order has no draw and
  never counts toward a quota;
- any other prize shows *Prize only: Prize Group B* (*Prize only*
  without a token category) instead of its price, and has no add to cart
  button: the cart refuses it, and so do the payment and the confirmation
  of a website order.

The product snippets of the website (newest, recently sold or viewed,
alternative products) follow the same rules.

### Remaining quantity on the shop cards

Every card of the shop, in the grid and the list layouts, tells what is
left of a storable product, for every visitor: *3 left*, *1 left* or *Out
of stock*. It is the free quantity that the website can still sell
(`website_sale_stock`, the website's warehouse), and for a sponsored prize
the free quantity of `event_raffle_prize`, from which a unit reserved by a
winner's claim is already gone. A product with variants sums them. A
product that is not storable (service, consumable without stock) shows
nothing, and so does a sold out product still sold beyond its stock
(**Continue selling when out-of-stock**), as its product page. The product
page keeps its own availability messages. The quantities of a page are
computed once for all its cards.

Once the shop is closed, ordinary visitors no longer see the sponsored
prizes, not even by their address or in a product snippet, and a cart
holding one can no longer be paid; it can still be removed from the cart.
The winners' prize links keep working.

The link works once. It stops working when the winner confirms a prize or
declines it, when an event user chooses the prize for them (**Choose the
Prize**), when a new link is sent, and at its deadline. Then the claim is
marked expired, the cart is cancelled, nothing leaves the stock, and
OdooBot posts an alert in the raffle's alert channel. A declined prize
posts an alert too. No other winner is drawn automatically. The claim log
of the draw (**Claims Ended**, from `event_raffle_prize`) keeps the
decline or the expiry with the prize of the winner's last cart, read
before the cart is cancelled, or with no prize when the cart held none.

## Winners and accounts

The link opens to the user of the draw's contact, the winner: any user of
that contact matches, since each one signs in as that person, and no other
contact of the same company does. Opening the link without being signed
in leads to the sign-in page, which comes back to the link. A user who did
not win gets a refusal page that says nothing of the winner, with
**Sign in with another account**; no claim opens.

A signed-in winner finds the claim in the shop without opening the link:
the banner, the token costs, the cart, the checkout and **Decline the
prize** work as through the link. With several open links, the most recent
draw comes first; a link the session opened comes before it. An expired,
declined or used link gives nothing.

How the link reaches the winner:

- a winner with an internal user receives it by chat, and opens it signed
  in;
- a winner with a portal user receives it by email, and signs in with that
  account;
- a winner whose contact has no user receives it by email as an account
  invitation of the website (`auth_signup`, through `website_sale`): the
  link of the email creates a portal user for that contact, signs it in
  and opens the prize link. The message says so. No internal user is ever
  created. The invitation goes to the winner's own email only: the bare
  link, copied from the draw or shown in the web app, leads to the sign-in
  page, so that whoever holds a forwarded link cannot create the winner's
  account. Once the account exists, the invitation stops working and the
  next links go out bare;
- a participant without a contact gets one, from the participant's name
  and email, when the link is sent.

## Configuration

- On each raffle, tab **Settings**, group **Prize Link**: **Send the Link
  After Each Draw** (on by default), **Link Validity (minutes)** (45, used
  by the draws without a token category), and the **Alert Channel**, a
  Discuss channel. The link validity of each token category is set in
  **Raffle > Prizes > Token Categories**.
- **Raffle > Settings** (event managers), group **Sponsored Prizes in the
  Shop**: **Sponsored prizes in the shop** (on by default) and **Close
  sales on**, an optional date and time. The shop is
  open while the switch is on and the date, if any, is still ahead. To
  reopen it, tick the switch again and move or clear the date.
- Publish the prizes on the website: tab **Sponsored Prize**, **Offered on
  the Website**, and tick **Sold to members** for the prizes members may
  buy. A sponsored prize never sells beyond its stock: **Continue Selling**
  out of stock is forced off, since claims and purchases share the stock.
- The delivery method **Raffle prize handover** is free and offered to the
  prize carts only (**For Raffle Prizes**); the other carts never see it.
- Payments of the member purchases: the module needs no payment provider.
  To offer both ways, install **Click & Collect** (`website_sale_collect`),
  give its **Pick up in store** delivery method a warehouse and publish it,
  and enable its **Pay on Site** provider; then enable any online provider.
  The prize carts never get a payment: they cost nothing, and only the
  prize handover is offered to them.

## Usage

- The link goes out after each draw when at least one prize is available
  for the winner, and when the winner can be reached: an internal user by
  chat, anyone else by email. Each send is logged on the draw, as with
  **Notify the Winner**.
- The link is issued before the messages that follow the draw, so that
  the `{link}` / `{lien}` placeholder of the raffle's **Notification
  Message** and **Channel Message** (tab **Settings**, from `event_raffle`)
  shows it. The default messages end with it. The channel gets the bare
  link, which opens to the winner's account only; a winner without an
  account gets the account invitation in their own message. Without a link
  (no prize for the winner, links off, winner out of reach), the
  placeholder disappears.
- When the raffle also has **Notify the Winner Automatically** on, a
  **Notification Message** that holds `{link}` gives the winner the link:
  no second message follows, and the draw notes that the link went out.
  A message without `{link}` comes first, then the prize link message with
  the same link. Each message is logged on the draw, the link masked.
- On the draw, **Send the Prize Link** issues a new link and sends it; the
  previous one stops working. The draw shows the link state (*Not sent*,
  *Open*, *Expired*, *Used*), its deadline and, for event users, the link
  itself to copy.
- An on-site winner (checked in) gives a name and an email at most. A
  virtual winner gives the address Odoo asks for.

## Security

- The token has 256 random bits, a unique index, and is readable by event
  users only; it never appears in a list view nor in the chatter: the
  notification log of the draw keeps the message with the token masked. An
  unknown, forged, expired or used link gets the same page, with the same
  404 status.
- The session keeps the draw and the token, both checked again on every
  request, with the winner: the signed-in user's contact must be the
  draw's contact. Signing out ends the claim, and a claim opened before
  another user signs in on the same browser gives that user nothing, nor
  the confirmation page of a claim confirmed before. The pages act as
  superuser after that check, on that draw only, and write its claim
  fields through the claim methods. A link opens a claim on a website of
  its raffle's company only, any website for a raffle without a company.
- The log of a link sent as an account invitation shows the bare link,
  masked, never the invitation token.
- The decline form is a POST with a CSRF token and a required reason.
- Confirming a prize cart runs the claim of the draw, which locks the
  product and the winner's quota: two tabs, two browsers or a double click
  give one confirmed order at most. When the last unit is gone or the
  quota is reached meanwhile, the order is not confirmed, the winner sees
  why and the shop again, and the link keeps working until its deadline.
- The winner checks the prize cart out signed in, as any customer of the
  shop, with their own addresses. A user who signs in on a browser that
  holds a prize cart of another winner does not take it over.
- The prize cart takes a prize that the claim allows and that the website
  sells: active, sellable and published on the website. The add to cart
  and every quantity update check both; the prize choice of an event user
  in the backend reads the claim rules only.
- Deleting a draw, or its raffle, cancels the open prize carts of the
  draw, and a website order without a draw never confirms a prize that is
  not sold to members.
- A prize for tokens only is refused at every step of an ordinary cart:
  the add to cart (`_is_add_to_cart_allowed`, `_cart_update`, whether it
  adds or sets a quantity), the payment (`_check_cart_is_ready_to_be_paid`)
  and the confirmation. A prize sold to members follows the same steps
  while the sponsored shop is open only.
- Confirming any order that holds a sponsored prize locks the prize rows
  first, as a claim does: a claim and a purchase of the last unit run one
  after the other. A paid online order that confirms after the last unit
  went to a winner follows Odoo's standard: the order is confirmed and its
  delivery waits for stock. The checkout refuses a cart whose prize has no
  unit left before the payment.
- Removing or lowering a cart line is never refused, so a prize that
  stops being for sale can always leave the cart that holds it.
- A prize cart never opens a payment: it offers no express checkout, and
  the transaction route of the shop refuses it once the order's access
  token is checked, so that the refusal tells nothing to whoever does not
  hold the cart. The payment route of the customer portal
  (`/my/orders/<id>/transaction`) refuses it the same way, and refuses a
  website cart whose sponsored prize may not be paid for now.
- A prize cart sent for payment is never confirmed outside its claim: its
  confirmation runs the claim, which takes a draft only, and the end of
  the claim cancels it with the drafts.
- The variant data of a product page (`/website_sale/get_combination_info`)
  and the product configurator (`/website_sale/product_configurator/*`)
  give no price for a prize whose price the shop replaces (a price of
  0), and answer 404 for a prize the visitor may not see, as the product
  page does. The rule follows the variant priced, whatever template is
  sent beside it; the configurator leaves such a prize out of the optional
  products.

## Accessibility

The banner, the sponsor lines, the remaining quantities of the shop
cards, the token costs and the pages of the link follow WCAG 2.2 AA:
labelled form, visible focus, body colours, keyboard use, and a 390 px
wide layout. The deadline is written as a time, so the banner reads right
without JavaScript; a script refreshes the minutes left in a polite live
region, once a minute at most.

## Known issues / Roadmap

- A winner whose registration made a new contact, while an account
  already exists for the same person under another contact, cannot open
  the link with that account: the event team links the participant to the
  account's contact, then sends the link again. Matching by email is left
  out on purpose: a user may change the email of their own contact.

- Pickup or shipping by attendance, carriers by country, the photo, the
  public winners page and the web app card come with phase 3.
- The quantity input, the layout switch and the filters of the shop are
  website_sale's own markup: the module's accessibility test covers what
  the module renders.
- Closing the sponsored shop does not cancel the carts already paid: their
  orders confirm as usual.
- The order pages of the customer portal and the printed order still show
  the value of a prize order, with its full discount.

## Development

```bash
./odoo_bin.sh db drop --if-exists test_event_raffle_prize_claim
EWP_AXE_JS=/path/to/axe.min.js ./test.sh -d test_event_raffle_prize_claim \
    --db-filter '^test_event_raffle_prize_claim$' \
    -i event_raffle_prize_claim,event_raffle_survey,website_sale_collect,payment_demo \
    --test-tags /event_raffle_prize_claim,/event_raffle_prize,/event_raffle,/event_raffle_survey \
    --http-port=18069 --gevent-port=18072 --stop-after-init
```

Without `EWP_AXE_JS`, the accessibility test skips itself; set to a
missing file, it fails. The checkout test runs a browser tour as the
signed-in winner, from the shop, without opening the link. The member payment tests use `payment_demo` and
`website_sale_collect`, and skip themselves when those are not installed:
the module depends on neither.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

This module is maintained as part of ERPLibre.

---

# Event Raffle Prize Claim (Lien du gagnant), français

Un lien de prix à usage unique pour chaque gagnant d'un tirage, une
boutique du site web qui présente à ce gagnant les prix qu'il peut prendre
avec son jeton, et la vente des prix commandités aux membres tant que la
boutique commanditée est ouverte. Le module s'appuie sur
`event_raffle_prize` (catalogue, catégories de jeton, stock, règles
d'attribution) et sur `website_sale`.

## Description

Après un tir, le gagnant reçoit un message par clavardage ou par courriel,
d'OdooBot : *Vous avez gagné un prix (Groupe de prix B) ! Choisissez-le
ici : (lien) (valide 45 minutes)*. Un jeton vaut un lien et un prix. Le
lien dure la **Validité du lien** de la catégorie de jeton du tir, ou celle
du tirage quand le tir n'a pas de catégorie. Il ne s'ouvre que pour le
compte du gagnant : qui l'ouvre se connecte d'abord, et la page de
connexion ramène au lien (voir *Gagnants et comptes*). Un gagnant connecté
dont le lien est ouvert retrouve aussi l'attribution dans la boutique sans
ouvrir le lien. Le lien ouvre la boutique du site, où le gagnant ne voit
que les prix de la catégorie de jeton de son tir, de
son mode et de sa région, les prix de clôture sur un tir de clôture
seulement, avec une unité restante, tant qu'il est sous son quota : les
règles d'`event_raffle_prize`. Chaque prix affiche son commanditaire, avec
un lien vers son site web.

Une bannière sur les pages de la boutique, de l'article, du panier et du
paiement accueille le gagnant, donne son jeton et la durée du lien, l'heure
où il cesse de fonctionner et les minutes restantes, et propose **Refuser
le prix**. Chaque prix affiche son coût, le nom de sa catégorie de jeton,
par exemple *Groupe de prix B*, au lieu d'un prix : sur la carte de la
boutique, la page de l'article, les extraits de produits, la notification
d'ajout au panier, la ligne du panier et le résumé de la commande, dont le
total est aussi le jeton. Le panier contient un prix, une unité, sans frais : la
ligne garde la valeur du prix avec une remise complète, pour les bilans des
commanditaires. Choisir un autre prix le remplace. Le paiement est au nom
du gagnant, avec le mode de livraison gratuit **Remise du prix de tirage**,
et **Confirmer la commande** réserve le prix : l'attribution
d'`event_raffle_prize` s'exécute alors, sous ses verrous, et la commande
devient la commande du prix du tir. Le gagnant reçoit ensuite le courriel
**Votre prix**, dans sa langue : le prix, sa catégorie de jeton, son
commanditaire avec un lien, et *Nous communiquerons avec vous pour le
retrait ou la livraison*, sans prix ni numéro de commande. Il remplace le
courriel de confirmation de website_sale pour les commandes de prix
seulement.

## Prix commandités dans la boutique

Tant que la boutique commanditée est ouverte, tout visiteur sans lien de
prix voit les prix commandités publiés dans la boutique :

- un prix coché **En vente aux membres** affiche son prix et va au panier
  comme tout article : il se paie et se confirme par le paiement habituel
  du site, avec tout mode de paiement que le site offre, et le membre
  reçoit la confirmation de commande standard d'Odoo. La commande n'a pas
  de tir et ne compte jamais dans un quota ;
- tout autre prix affiche *Prix seulement : Groupe de prix B* (*Prix
  seulement* sans catégorie de jeton) au lieu de son prix, et n'a pas de
  bouton d'ajout au panier : le panier le refuse, tout comme le paiement
  et la confirmation d'une commande du site.

Les extraits de produits du site (nouveautés, ventes ou consultations
récentes, articles de remplacement) suivent les mêmes règles.

### Quantité restante sur les fiches de la boutique

Chaque fiche de la boutique, en grille comme en liste, dit ce qui reste
d'un article stocké, pour tout visiteur : *3 restants*, *1 restant* ou
*Épuisé*. C'est la quantité libre que le site peut encore vendre
(`website_sale_stock`, l'entrepôt du site), et pour un prix commandité la
quantité libre d'`event_raffle_prize`, dont une unité réservée par
l'attribution d'un gagnant est déjà retirée. Un article à variantes en fait
la somme. Un article non stocké (service, consommable sans stock)
n'affiche rien, pas plus qu'un article épuisé qui se vend encore au-delà de
son stock (**Continuez à vendre en cas de rupture de stock**), comme sa
page d'article. La page d'article garde ses propres messages de
disponibilité. Les quantités d'une page sont calculées une fois pour
toutes ses fiches.

Une fois la boutique fermée, les visiteurs ordinaires ne voient plus les
prix commandités, pas même par leur adresse ni dans un extrait de
produits, et un panier qui en contient un ne peut plus être payé ; le prix
peut toujours en être retiré. Les liens de prix des gagnants fonctionnent
toujours.

Le lien ne sert qu'une fois. Il cesse de fonctionner quand le gagnant
confirme un prix ou le refuse, quand un utilisateur des événements choisit
le prix pour lui (**Choisir le prix**), quand un nouveau lien est envoyé, et
à son échéance. L'attribution est alors marquée expirée, le panier est
annulé, rien ne sort du stock, et OdooBot publie une alerte dans le canal
d'alerte du tirage. Un prix refusé publie aussi une alerte. Aucun autre
gagnant n'est tiré automatiquement. Le journal des attributions du tir
(**Attributions terminées**, d'`event_raffle_prize`) garde le refus ou
l'expiration avec le prix du dernier panier du gagnant, lu avant
l'annulation du panier, ou sans prix quand le panier n'en contenait pas.

## Gagnants et comptes

Le lien s'ouvre pour l'utilisateur du contact du tir, le gagnant : tout
utilisateur de ce contact convient, puisque chacun se connecte en tant que
cette personne, et aucun autre contact de la même entreprise. Ouvrir le
lien sans être connecté mène à la page de connexion, qui ramène au lien.
Un utilisateur qui n'a pas gagné reçoit une page de refus qui ne dit rien
du gagnant, avec **Se connecter avec un autre compte** ; aucune
attribution ne s'ouvre.

Un gagnant connecté retrouve l'attribution dans la boutique sans ouvrir le
lien : la bannière, les coûts en jetons, le panier, le paiement et
**Refuser le prix** fonctionnent comme par le lien. Avec plusieurs liens
ouverts, le tir le plus récent passe d'abord ; un lien ouvert par la
session passe avant lui. Un lien expiré, refusé ou utilisé ne donne rien.

Comment le lien joint le gagnant :

- un gagnant avec un utilisateur interne le reçoit par clavardage, et
  l'ouvre connecté ;
- un gagnant avec un utilisateur portail le reçoit par courriel, et se
  connecte avec ce compte ;
- un gagnant dont le contact n'a pas d'utilisateur le reçoit par courriel
  sous forme d'invitation à créer un compte sur le site (`auth_signup`,
  par `website_sale`) : le lien du courriel crée un utilisateur portail
  pour ce contact, le connecte et ouvre le lien de prix. Le message le
  dit. Aucun utilisateur interne n'est jamais créé. L'invitation ne va
  qu'au courriel du gagnant : le lien nu, copié du tir ou affiché dans
  l'app web, mène à la page de connexion, si bien que qui détient un lien
  transféré ne peut pas créer le compte du gagnant. Une fois le compte
  créé, l'invitation cesse de fonctionner et les liens suivants partent
  nus ;
- un participant sans contact en reçoit un, tiré de son nom et de son
  courriel, à l'envoi du lien.

## Configuration

- Sur chaque tirage, onglet **Paramètres**, groupe **Lien de prix** :
  **Envoyer le lien après chaque tir** (coché par défaut), **Validité du
  lien (minutes)** (45, pour les tirs sans catégorie de jeton), et le
  **Canal d'alerte**, un canal de Discussion. La validité du lien de chaque
  catégorie de jeton se règle dans **Tirage > Prix > Catégories de jeton**.
- **Tirage > Paramètres** (gestionnaires des événements), groupe **Prix
  commandités dans la boutique** : **Prix commandités dans la boutique**
  (coché par défaut) et **Fermer les ventes le**, une date et heure
  facultative. La boutique est ouverte tant que la
  case est cochée et que la date, s'il y en a une, n'est pas passée. Pour
  la rouvrir, cocher la case de nouveau et déplacer ou effacer la date.
- Publier les prix sur le site web : onglet **Prix commandité**, **Offert
  sur le site web**, et cocher **En vente aux membres** pour les prix que
  les membres peuvent acheter. Un prix commandité ne se vend jamais
  au-delà de son stock : **Continuer à vendre** en rupture est forcé à non,
  puisque attributions et achats partagent le stock.
- Le mode de livraison **Remise du prix de tirage** est gratuit et offert
  aux paniers de prix seulement (**Pour les prix de tirage**) ; les autres
  paniers ne le voient jamais.
- Paiement des achats des membres : le module n'exige aucun fournisseur de
  paiement. Pour offrir les deux façons, installer **Click & Collect**
  (`website_sale_collect`), donner un entrepôt à son mode de livraison
  **Retrait en magasin** et le publier, et activer son fournisseur
  **Paiement sur place** ; puis activer tout fournisseur en ligne. Les
  paniers de prix ne reçoivent jamais de paiement : ils ne coûtent rien, et
  seule la remise du prix leur est offerte.

## Utilisation

- Le lien part après chaque tir quand au moins un prix est offert au
  gagnant, et quand on peut le joindre : un utilisateur interne par
  clavardage, tout autre par courriel. Chaque envoi est journalisé sur le
  tir, comme avec **Notifier le gagnant**.
- Le lien est émis avant les messages qui suivent le tir, pour que le
  paramètre `{lien}` / `{link}` du **Message notification** et du **Message
  canal** du tirage (onglet **Paramètres**, venu d'`event_raffle`) le
  montre. Les messages par défaut se terminent par lui. Le canal reçoit le
  lien nu, qui ne s'ouvre qu'au compte du gagnant ; un gagnant sans compte
  reçoit l'invitation à le créer dans son propre message. Sans lien (aucun
  prix pour le gagnant, liens désactivés, gagnant injoignable), le
  paramètre disparaît.
- Quand le tirage a aussi **Notifier le gagnant automatiquement** activé,
  un **Message notification** qui contient `{lien}` donne le lien au
  gagnant : aucun second message ne suit, et le tir note que le lien est
  parti. Un message sans `{lien}` part d'abord, puis le message du lien de
  prix, avec le même lien. Chaque message est journalisé sur le tir, le
  lien masqué.
- Sur le tir, **Envoyer le lien de prix** émet un nouveau lien et l'envoie ;
  le précédent cesse de fonctionner. Le tir affiche l'état du lien (*Non
  envoyé*, *Ouvert*, *Expiré*, *Utilisé*), son échéance et, pour les
  utilisateurs des événements, le lien lui-même à copier.
- Un gagnant sur place (scanné à l'accueil) donne au plus un nom et un
  courriel. Un gagnant virtuel donne l'adresse qu'Odoo demande.

## Sécurité

- Le jeton a 256 bits aléatoires, un index unique, et n'est lisible que par
  les utilisateurs des événements ; il n'apparaît ni dans une vue liste ni
  dans le fil de discussion : le journal des notifications du tir garde le
  message avec le jeton masqué. Un lien inconnu, falsifié, expiré ou utilisé
  reçoit la même page, avec le même statut 404.
- La session garde le tir et le jeton, vérifiés de nouveau à chaque
  requête, avec le gagnant : le contact de l'utilisateur connecté doit
  être celui du tir. Se déconnecter met fin à l'attribution, et une
  attribution ouverte avant qu'un autre utilisateur se connecte sur le
  même navigateur ne donne rien à celui-ci, pas plus que la page de
  confirmation d'une attribution confirmée avant. Les pages agissent en
  superutilisateur après cette vérification, sur ce tir seulement, et
  écrivent ses champs d'attribution par les méthodes d'attribution. Un
  lien n'ouvre une attribution que sur un site web de la société de son
  tirage, sur tout site pour un tirage sans société.
- Le journal d'un lien envoyé sous forme d'invitation montre le lien nu,
  masqué, jamais le jeton de l'invitation.
- Le formulaire de refus est un POST avec un jeton CSRF et une raison
  obligatoire.
- Confirmer un panier de prix exécute l'attribution du tir, qui verrouille
  l'article et le quota du gagnant : deux onglets, deux navigateurs ou un
  double clic donnent au plus une commande confirmée. Quand le dernier
  exemplaire est parti ou le quota atteint entre-temps, la commande n'est
  pas confirmée, le gagnant voit pourquoi et la boutique de nouveau, et le
  lien fonctionne jusqu'à son échéance.
- Le gagnant passe à la caisse connecté, comme tout client de la
  boutique, avec ses propres adresses. Un utilisateur qui se connecte sur
  un navigateur qui porte le panier de prix d'un autre gagnant ne le
  reprend pas.
- Le panier de prix prend un prix que l'attribution permet et que le site
  web vend : actif, vendable et publié sur le site. L'ajout au panier et
  chaque changement de quantité vérifient les deux ; le choix du prix par
  un utilisateur de l'événement dans le système ne lit que les règles de
  l'attribution.
- Supprimer un tir, ou son tirage, annule les paniers de prix ouverts du
  tir, et une commande du site web sans tir ne confirme jamais un prix qui
  n'est pas en vente aux membres.
- Un prix réservé aux jetons est refusé à chaque étape d'un panier
  ordinaire : l'ajout au panier (`_is_add_to_cart_allowed`, `_cart_update`,
  qu'il ajoute ou fixe une quantité), le paiement
  (`_check_cart_is_ready_to_be_paid`) et la confirmation. Un prix en vente
  aux membres suit les mêmes étapes tant que la boutique commanditée est
  ouverte seulement.
- Confirmer toute commande qui porte un prix commandité verrouille d'abord
  les lignes des prix, comme une attribution : une attribution et un achat
  du dernier exemplaire passent l'un après l'autre. Une commande payée en
  ligne qui se confirme après que le dernier exemplaire est allé à un
  gagnant suit la norme d'Odoo : la commande est confirmée et sa livraison
  attend le stock. Le paiement refuse d'avance un panier dont le prix n'a
  plus d'unité.
- Retirer une ligne du panier ou en baisser la quantité n'est jamais
  refusé : un prix qui cesse d'être en vente peut toujours quitter le
  panier qui le contient.
- Un panier de prix n'ouvre jamais de paiement : il n'offre pas de
  paiement express, et la route de transaction de la boutique le refuse
  une fois le jeton d'accès de la commande vérifié, si bien que le refus
  n'apprend rien à qui ne détient pas le panier. La route de paiement du
  portail client (`/my/orders/<id>/transaction`) le refuse de la même
  façon, et refuse un panier du site web dont le prix commandité ne peut
  pas être payé maintenant.
- Un panier de prix envoyé pour paiement n'est jamais confirmé hors de son
  attribution : sa confirmation exécute l'attribution, qui ne prend qu'un
  brouillon, et la fin de l'attribution l'annule avec les brouillons.
- Les données de variante d'une page d'article
  (`/website_sale/get_combination_info`) et le configurateur d'article
  (`/website_sale/product_configurator/*`) ne donnent aucun prix pour un
  prix dont la boutique remplace le prix (un prix de 0), et répondent 404
  pour un prix que le visiteur ne peut pas voir, comme la page d'article.
  La règle suit la variante dont le prix est calculé, quel que soit le
  modèle envoyé avec elle ; le configurateur retire un tel prix des
  articles optionnels.

## Accessibilité

La bannière, les lignes du commanditaire, les quantités restantes des
fiches de la boutique, les coûts en jetons et les pages du lien suivent
WCAG 2.2 AA : formulaire étiqueté, focus visible, couleurs du corps de page,
usage au clavier, et une mise en page à 390 px de large. L'échéance est
écrite comme une heure, si bien que la bannière se lit sans JavaScript ; un
script rafraîchit les minutes restantes dans une zone annoncée poliment,
une fois par minute au plus.

## Problèmes connus / Feuille de route

- Un gagnant dont l'inscription a créé un nouveau contact, alors qu'un
  compte existe déjà pour la même personne sous un autre contact, ne peut
  pas ouvrir le lien avec ce compte : l'équipe de l'événement lie le
  participant au contact du compte, puis envoie le lien de nouveau. La
  correspondance par courriel est écartée exprès : un utilisateur peut
  changer le courriel de son propre contact.

- Le retrait sur place ou l'envoi selon le mode, les transporteurs par
  pays, la photo, la page publique des gagnants et la carte de l'app web
  viennent avec la phase 3.
- Le champ de quantité, le sélecteur de disposition et les filtres de la
  boutique sont le balisage de website_sale : le test d'accessibilité du
  module couvre ce que le module affiche.
- Fermer la boutique commanditée n'annule pas les paniers déjà payés :
  leurs commandes se confirment comme d'habitude.
- Les pages de commande du portail client et la commande imprimée montrent
  encore la valeur d'une commande de prix, avec sa remise complète.

## Développement

Les commandes de test sont celles de la section *Development* ci-dessus.
Sans `EWP_AXE_JS`, le test d'accessibilité se met de côté ; si la
variable nomme un fichier absent, il échoue. Le test du paiement exécute
une visite guidée dans un navigateur, en gagnant connecté, depuis la
boutique, sans ouvrir le lien. Les tests de
paiement des membres utilisent `payment_demo` et `website_sale_collect`, et
se mettent de côté quand ils ne sont pas installés : le module ne dépend
d'aucun des deux.

## Crédits

### Auteurs

- TechnoLibre

### Contributeurs

- Mathieu Benoit

### Mainteneurs

Ce module est maintenu dans le cadre d'ERPLibre.
