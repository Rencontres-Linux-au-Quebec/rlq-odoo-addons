# Event Raffle Prizes (Prix de tirage)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

A catalogue of sponsored prizes with a real inventory for the raffles of
`event_raffle`, token categories, and an assisted prize claim for each winner.
The French version follows the English one.

## Description

Prizes are storable products, marked **Sponsored Prize**. Each one has a
sponsor (its website shows as a link), a value (the sales price), a token
category, the winners it is meant for (on site, virtual or both), an optional
region, an optional list of events, the **Closing Prize** flag, and **Sold to
members** when members may also buy it. Its stock is the Odoo inventory of
the company's default warehouse.

A winner earns one token of the token category of their draw: one token is
one prize link and one prize, and a prize of that category costs exactly
that token. Six categories come with the module, **Prize Group A** to
**Prize Group F**, listed in that order, with no value range yet and a link
validity of 45 minutes. An upgrade from an older version renames the three
former default categories to A, B and C, unless their name was changed.
A winner reads the cost of a prize as the name of its category, such as
*Prize Group B*.

After a draw, the event user opens the draw and clicks **Choose the Prize**.
The wizard lists only the prizes this winner may take, with their value,
sponsor and remaining quantity; the user picks one and reserves it. The
winner does not need a phone: the choice is made for them in Odoo.

Reserving creates a sale order at no charge for the winner and confirms it,
which reserves one unit at the warehouse. A module may hand the claim a
draft order of the draw instead, such as the winner's own cart: the claim
checks it holds one unit of that prize only, then confirms it under the
same locks and rules. **Decline the Prize** (a reason is
required) cancels the order and puts the unit back in stock at once; the
winner keeps the draw, and the wheel is spun again for another winner.
**Prize Handed Over** asks for a confirmation, then validates the delivery
and marks the prize received; it refuses an order or a delivery cancelled
from the Sales or Inventory app, which is declined instead. An absent winner
may still get a prize.

Each decline and each expiry of a claim is kept in the **Claims Ended**
list of the draw, the claim log: its date, the prize the claim held or
the winner had chosen (empty when none was), the reason and the user. A
draw that declines a prize, then claims another, keeps the first decline
there, where its claim fields show the current claim only.
**Raffle > Prizes > Claims Ended** lists the lines of every draw. A line
outlives its draw: it keeps a copy of the draw's name, date and token
category, raffle, event and company, taken when the line is written, so
deleting the draw, then its raffle or its event, leaves the line. A line
whose event is deleted belongs to no event and still names its prize.

A draw whose prize is reserved cannot be deleted: decline the prize first.
A draw whose prize was handed over or shipped cannot be deleted at all:
its prize order belongs to it. Nor can a raffle or an event while one of
its draws holds a prize (reserved, handed over or shipped): the database
would delete those draws with it, past their own guard. The refusal lists
the draws; a raffle or an event whose draws hold nothing is deleted.

## Configuration

- **Raffle > Prizes > Token Categories** (event managers): the categories,
  each with a value range and a **Link Validity (minutes)**. Set the ranges
  for the value of your prizes. A prize falls in the first category, in
  sequence order, whose range holds its sales price. The category is set
  again when the price changes, and can be changed by hand afterwards.
- **Raffle > Prizes > Sponsored Prizes** (event managers): the prizes. The
  *Sponsored Prize* tab holds the sponsor, the value, the token category,
  the initial quantity given by the sponsor, **Sold to members**, and who
  may win it. The stock itself is set in the Inventory app (*Update
  Quantity*). The product search has a **Sponsored Prizes** filter.
- On each raffle, tab **Settings**, group **Prizes**: the **Token category
  of this raffle**, the token each of its winners earns, the closing flag
  of the next draw, the **Default Quota** (1) and the **High Quota** (2),
  and the **High Quota Tickets**, the ticket types of the event that get
  the high quota.

## Who may take which prize

A prize is offered to a winner when all of these hold:

- it is a sponsored prize, and its events are empty or include the raffle's
  event;
- the draw has no token category, or the prize is in the draw's category;
- its attendance is *both*, or matches the winner: **on site** when the
  winner's registration is marked attended (what the check-in scan does),
  **virtual** otherwise, including a participant without a registration;
- for a virtual winner, the address of the winner's contact is in its
  region: a listed state admits its residents; a listed country admits all
  of its residents when none of its states is listed, and defers to the
  listed states otherwise. The claim checks the region again on the
  delivery address of the prize order, the one the prize ships to: a
  delivery address outside the region is refused. On-site winners pick the
  prize up at the event;
- a closing prize goes to a closing draw only;
- a unit is free at the warehouse;
- the winner holds fewer prizes than their quota.

## Quotas

A person may hold the **High Quota** of prizes when the ticket of their
registration is one of the raffle's high quota tickets, else the **Default
Quota**. Held prizes are the claims reserved or handed over in any raffle of
the same event, by any participant that is the same person: the same record,
the same contact, or the same email (compared without case). A person at
quota leaves the wheel: they are no longer eligible to be drawn. A declined
prize frees its place in the quota.

## The wheel

Next to the prize input, the wheel shows a **token category selector**
(when categories exist) and a **Closing draw** toggle. Both are the
raffle's own settings (`prize_band_id`, `prize_closing_draw`), written as
soon as they change, and the next draw copies them under the raffle lock.
They stay set from one draw to the next, and both stay editable on the
draw afterwards.

## Member purchases

A prize marked **Sold to members** may also be bought at its sales price
(`event_raffle_prize_claim` opens it in the website shop). A member order is
an ordinary sale order: it has no draw, never counts toward a quota, and
never changes a draw. Purchases and claims share the stock. Each order line
of a sponsored prize records how it leaves, **Claimed with a token** or
**Bought by a member**, for the sponsor reports.

## Inventory

**Raffle > Prizes > Prize Inventory** lists the prizes with the initial
quantity, the units reserved and handed over by the claims, the remaining free
quantity, the sponsor, the token category, the attendance and the closing
flag, with filters by sponsor, category and event, groupings by sponsor,
category and attendance, and a pivot view. Every quantity, the remaining one included,
is summed per group and in the pivot.

## Access rights

Event users choose, decline and hand over prizes. Event managers manage the
token categories and create and edit products (the module grants them write access to
products for that). Event users get no sale or stock rights: the claim
checks the write access on the draw, then creates and confirms the sale
order, cancels it or validates its delivery as superuser. The order is
visible on the draw to sales users only. The claim fields of a draw are
written by those buttons only: a direct write or a context default is
refused or ignored, and the buttons act only on the order that points back
to its draw. Event users read the claim log; nobody writes it by hand.

## Concurrency

A claim locks the product row, then the rows of the winner's participants
over the event's raffles (`SELECT ... FOR UPDATE`, in id order), and updates
them in place. Under PostgreSQL's REPEATABLE READ, a second claim that waited
on the lock then fails with a serialization error when the first one
commits, and Odoo retries the request on a fresh snapshot, where the stock
and the quota include the first claim. The last unit therefore goes once,
and a quota holds against two claims running at the same time.

Confirming any order that holds a sponsored prize, a member purchase
included, takes the same product locks first, in ascending id order, so a
claim and a purchase of the last unit run one after the other: a claim
retried after a purchase finds no unit left. A paid order that confirms
after the last unit went to a winner follows Odoo's standard: it is
confirmed, and its delivery waits for stock.

## Known issues / Roadmap

- The winner's own choice through a link, the expiry of an unclaimed prize,
  the channel alert and the member sales in the shop come with
  `event_raffle_prize_claim`.
- The **Initial Quantity** is informative: it does not set the stock.
- A token category added or changed later does not move the products
  already priced: change their category by hand, or save their price
  again. A category whose range is still [0, 0] places no priced prize.
- The delivery of a warehouse with several steps is validated step by step
  by **Prize Handed Over**; a one-step delivery is expected.

## Development

```bash
# Tests on a fresh database (explicit ports: Odoo's test mode opens an HTTP
# server even with --stop-after-init).
./odoo_bin.sh db drop --if-exists test_event_raffle_prize
./test.sh -d test_event_raffle_prize --db-filter '^test_event_raffle_prize$' \
    -i event_raffle_prize,event_raffle_survey \
    --test-tags /event_raffle_prize,/event_raffle,/event_raffle_survey \
    --http-port=18069 --gevent-port=18072 --stop-after-init

# Translations: export the template, then update fr_CA.po against it
./odoo_bin.sh -d test_event_raffle_prize --modules=event_raffle_prize \
    --i18n-export=odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_prize/i18n/event_raffle_prize.pot
msgfmt --check -o /dev/null \
    odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_prize/i18n/fr_CA.po
```

The concurrency tests commit their data through real cursors and remove it
afterwards: run them on a test database only.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

This module is maintained as part of ERPLibre.

---

# Event Raffle Prizes (Prix de tirage), français

Un catalogue de prix commandités avec un vrai inventaire pour les tirages
d'`event_raffle`, des catégories de jeton, et une attribution assistée du
prix de chaque gagnant.

## Description

Les prix sont des articles stockables, cochés **Prix commandité**. Chacun a
un commanditaire (son site web s'affiche en lien), une valeur (le prix de
vente), une catégorie de jeton, les gagnants à qui il est destiné (sur
place, virtuels ou les deux), une région facultative, une liste facultative
d'événements, la case **Prix de clôture**, et **En vente aux membres**
quand les membres peuvent aussi l'acheter. Son stock est l'inventaire Odoo
de l'entrepôt par défaut de la société.

Un gagnant obtient un jeton de la catégorie de jeton de son tir : un jeton
vaut un lien de prix et un prix, et un prix de cette catégorie coûte
exactement ce jeton. Six catégories viennent avec le module, **Groupe de
prix A** à **Groupe de prix F**, listées dans cet ordre, sans intervalle de
valeur encore et avec un lien valide 45 minutes. Une mise à jour depuis une
version antérieure renomme les trois anciennes catégories par défaut en A,
B et C, à moins que leur nom ait été changé. Un gagnant lit le coût d'un
prix comme le nom de sa catégorie, par exemple *Groupe de prix B*.

Après un tir, l'utilisateur des événements ouvre le tir et clique **Choisir
le prix**. L'assistant ne liste que les prix que ce gagnant peut prendre,
avec leur valeur, leur commanditaire et la quantité restante ; l'utilisateur
en choisit un et le réserve. Le gagnant n'a pas besoin de téléphone : le
choix se fait pour lui dans Odoo.

Réserver crée une commande de vente sans frais au nom du gagnant et la
confirme, ce qui réserve une unité à l'entrepôt. Un module peut plutôt
remettre à l'attribution une commande brouillon du tir, comme le panier du
gagnant lui-même : l'attribution vérifie qu'elle ne porte qu'une unité de ce
prix, puis la confirme sous les mêmes verrous et les mêmes règles. **Refuser
le prix** (une
raison est exigée) annule la commande et remet l'unité en stock aussitôt ;
le gagnant garde son tir, et on relance la roue pour un autre gagnant.
**Prix remis** demande une confirmation, puis valide la livraison et marque
le prix reçu ; il refuse une commande ou une livraison annulée depuis
l'application Ventes ou Inventaire, qu'on refuse alors. Un gagnant absent
peut tout de même recevoir un prix.

Chaque refus et chaque expiration d'une attribution est gardé dans la
liste **Attributions terminées** du tir, le journal des attributions : sa
date, le prix que l'attribution réservait ou que le gagnant avait choisi
(vide quand il n'en avait pas), la raison et l'utilisateur. Un tir qui
refuse un prix, puis en choisit un autre, y garde le premier refus, là où
ses champs d'attribution ne montrent que l'attribution actuelle.
**Tirage > Prix > Attributions terminées** liste les lignes de tous les
tirs. Une ligne survit à son tir : elle garde une copie du nom, de la
date et de la catégorie de jeton du tir, de son tirage, de son événement
et de sa société, prise quand la ligne est écrite ; supprimer le tir, puis
son tirage ou son événement, laisse donc la ligne. Une ligne dont
l'événement est supprimé n'appartient à aucun événement et nomme toujours
son prix.

Un tir dont le prix est réservé ne peut pas être supprimé : refuser
d'abord le prix. Un tir dont le prix a été remis ou expédié ne peut plus
être supprimé du tout : sa commande de prix lui appartient. Un tirage ou
un événement ne peut pas non plus être supprimé tant qu'un de ses tirs
garde un prix (réservé, remis ou expédié) : la base supprimerait ces tirs
avec lui, sans passer par leur propre garde. Le refus liste les tirs ; un
tirage ou un événement dont les tirs ne gardent rien se supprime.

## Configuration

- **Tirage > Prix > Catégories de jeton** (gestionnaires des événements) :
  les catégories, chacune avec un intervalle de valeur et une **Validité du
  lien (minutes)**. Régler les intervalles selon la valeur de vos prix. Un
  prix tombe dans la première catégorie, dans l'ordre de séquence, dont
  l'intervalle contient son prix de vente. La catégorie est recalculée quand
  le prix change, et reste modifiable à la main ensuite.
- **Tirage > Prix > Prix commandités** (gestionnaires des événements) : les
  prix. L'onglet *Prix commandité* porte le commanditaire, la valeur, la
  catégorie de jeton, la quantité initiale donnée par le commanditaire,
  **En vente aux membres**, et qui peut le gagner. Le stock lui-même se
  règle dans l'application Inventaire (*Mettre à jour la quantité*). La
  recherche des articles a un filtre **Prix commandités**.
- Sur chaque tirage, onglet **Paramètres**, groupe **Prix** : la
  **Catégorie de jeton du tirage**, le jeton que chacun de ses gagnants
  obtient, la case de clôture du prochain tir, le **Quota par défaut** (1)
  et le **Quota élevé** (2), et les **Billets à quota élevé**, les types de
  billet de l'événement qui ont le quota élevé.

## Qui peut prendre quel prix

Un prix est offert à un gagnant quand tout ceci est vrai :

- c'est un prix commandité, et ses événements sont vides ou comprennent
  l'événement du tirage ;
- le tir n'a pas de catégorie de jeton, ou le prix est dans la catégorie du
  tir ;
- son mode est *les deux*, ou correspond au gagnant : **sur place** quand
  l'inscription du gagnant est marquée présente (ce que fait le scan à
  l'accueil), **virtuel** sinon, y compris un participant sans inscription ;
- pour un gagnant virtuel, l'adresse de son contact est dans la région du
  prix : une province listée admet ses résidents ; un pays listé admet tous
  ses résidents quand aucune de ses provinces n'est listée, et s'en remet
  aux provinces listées sinon. L'attribution vérifie de nouveau la région
  sur l'adresse de livraison de la commande du prix, celle où le prix est
  expédié : une adresse de livraison hors de la région est refusée. Les
  gagnants sur place prennent le prix à l'événement ;
- un prix de clôture ne va qu'à un tir de clôture ;
- une unité est libre à l'entrepôt ;
- le gagnant détient moins de prix que son quota.

## Quotas

Une personne peut détenir le **Quota élevé** de prix quand le billet de son
inscription est l'un des billets à quota élevé du tirage, sinon le **Quota
par défaut**. Les prix détenus sont les attributions réservées ou remises
dans n'importe quel tirage du même événement, par tout participant qui est
la même personne : le même enregistrement, le même contact ou le même
courriel (sans égard à la casse). Une personne au quota quitte la roue :
elle n'est plus tirée. Un prix refusé libère sa place dans le quota.

## La roue

À côté du champ du lot, la roue affiche un **sélecteur de catégorie de
jeton** (quand des catégories existent) et une case **Tir de clôture**. Les
deux sont des réglages du tirage (`prize_band_id`, `prize_closing_draw`),
enregistrés dès qu'ils changent, et le tir suivant les copie sous le verrou
du tirage. Ils restent réglés d'un tir à l'autre, et restent modifiables
sur le tir ensuite.

## Ventes aux membres

Un prix coché **En vente aux membres** peut aussi s'acheter à son prix de
vente (`event_raffle_prize_claim` l'ouvre dans la boutique du site). Une
commande de membre est une commande ordinaire : elle n'a pas de tir, ne
compte jamais dans un quota et ne change jamais un tir. Achats et
attributions partagent le stock. Chaque ligne d'un prix commandité garde
comment il part, **Réclamé avec un jeton** ou **Acheté par un membre**,
pour les bilans des commanditaires.

## Inventaire

**Tirage > Prix > Inventaire des prix** liste les prix avec la quantité
initiale, les unités réservées et remises par les attributions, la quantité
libre restante, le commanditaire, la catégorie de jeton, le mode et la case
de clôture, avec des filtres par commanditaire, catégorie et événement, des
regroupements par commanditaire, catégorie et mode, et une vue pivot. Chaque quantité, la
restante comprise, est totalisée par regroupement et dans le pivot.

## Droits d'accès

Les utilisateurs des événements choisissent, refusent et remettent les
prix. Les gestionnaires des événements gèrent les catégories de jeton, et
créent et
modifient les articles (le module leur donne pour cela l'écriture sur les
articles). Les utilisateurs des événements n'ont aucun droit sur les ventes
ni sur l'inventaire : l'attribution vérifie le droit d'écriture sur le tir,
puis crée et confirme la commande, l'annule ou valide sa livraison en
superutilisateur. La commande n'est visible sur le tir que pour les
utilisateurs des ventes. Les champs d'attribution d'un tir ne s'écrivent que
par ces boutons : une écriture directe ou une valeur par défaut du contexte
est refusée ou ignorée, et les boutons n'agissent que sur la commande qui
renvoie à son tir. Les utilisateurs des événements lisent le journal des
attributions ; personne ne l'écrit à la main.

## Concurrence

Une attribution verrouille la ligne de l'article, puis celles des
participants du gagnant dans les tirages de l'événement (`SELECT ... FOR
UPDATE`, par ordre d'identifiant), et les met à jour sur place. Sous le
REPEATABLE READ de PostgreSQL, une seconde attribution qui attendait le
verrou échoue alors par une erreur de sérialisation quand la première est
validée, et Odoo rejoue la requête sur un instantané frais, où le stock et
le quota comptent la première. Le dernier exemplaire ne part donc qu'une
fois, et un quota tient contre deux attributions simultanées.

Confirmer toute commande qui porte un prix commandité, achat de membre
compris, prend d'abord les mêmes verrous d'article, par ordre croissant
d'identifiant : une attribution et un achat du dernier exemplaire passent
l'un après l'autre, et une attribution rejouée après un achat ne trouve
plus d'unité. Une commande payée qui se confirme après que le dernier
exemplaire est allé à un gagnant suit la norme d'Odoo : elle est
confirmée, et sa livraison attend le stock.

## Problèmes connus / Feuille de route

- Le choix par le gagnant lui-même au moyen d'un lien, l'expiration d'un
  prix non réclamé, l'alerte dans le canal et les ventes aux membres dans
  la boutique viennent avec `event_raffle_prize_claim`.
- La **Quantité initiale** est informative : elle ne règle pas le stock.
- Une catégorie de jeton ajoutée ou modifiée plus tard ne déplace pas les
  articles déjà tarifés : changer leur catégorie à la main, ou enregistrer
  leur prix de nouveau. Une catégorie dont l'intervalle est encore [0, 0]
  ne place aucun prix tarifé.
- La livraison d'un entrepôt à plusieurs étapes est validée étape par étape
  par **Prix remis** ; une livraison en une étape est attendue.

## Développement

Les commandes de test et de traduction sont celles de la section
*Development* ci-dessus. Les tests de concurrence valident leurs données par
de vrais curseurs et les retirent ensuite : les lancer sur une base de test
seulement.

## Crédits

### Auteurs

- TechnoLibre

### Contributeurs

- Mathieu Benoit

### Mainteneurs

Ce module est maintenu dans le cadre d'ERPLibre.
