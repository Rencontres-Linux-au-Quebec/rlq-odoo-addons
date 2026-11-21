# Event Raffle Prize Sponsors (Commanditaires des prix)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

The sponsors of an event submit their raffle prizes themselves, in the
portal, and the organization approves each one before it is offered; a
report then tells each sponsor's contribution, and one email per sponsor
thanks it with the list of its winners. It
builds on `event_raffle_prize_handover` (virtual prizes) and the modules
under it: `event_raffle_prize_claim` (winner shop, member sales) and
`event_raffle_prize` (catalogue, stock, claim rules). The French version
follows the English one.

## Description

### Event and registrations

- On the event form, **Manage with sponsors** opens the portal to the
  event's sponsors, and **Sponsorship managers** lists the internal users
  notified of each prize submitted, who also approve or refuse the prizes
  of that event. Without managers, the event's responsible user is
  notified.
- On an attendee's registration of such an event, **Is a sponsor** marks
  the person who represents a sponsor. The registration list has an
  optional column for it, and the search a **Sponsors** filter.
- The sponsor contact is the person who attends and signs in, never the
  person who booked. Only the organization sets it: marking the sponsor
  takes the registration's contact when its email is the attendee's;
  otherwise **Send invitation** takes an existing contact with the
  attendee's email that has no user, or creates one from the attendee's
  name and email. A contact that already has a user is never taken from
  its email alone, since Odoo does not verify that email: when an account
  already uses the attendee's email, the invitation asks to set that
  account's contact as the registration's contact. The sponsor contact
  stays the same when an email changes later. An attendee without an
  email cannot be invited.
- While that contact has no portal or internal user, the form warns *This
  sponsor has no account: they cannot add prizes in the portal* and shows
  **Send invitation**. It grants portal access and sends Odoo's standard
  portal invitation (the email template *Portal: User Invite*), through the
  same wizard as the Contacts app. Once sent and until the sponsor signs
  in, the form says *Invitation sent, not accepted yet* and the button
  sends it again. An internal user needs no invitation: the form shows
  neither. Nothing is sent automatically.
- Next to the button, **Invitation email** opens that email template, for
  the users who may edit email templates (*Mail Template Editor* or
  *Settings*); the others do not see it.

### Portal: Prizes for raffle

A signed-in user sees **Prizes for raffle** on **My account** while their
contact, or another contact of the same company, has a sponsor
registration, not cancelled, on a sponsor-managed event that is not over.
The pages list the prizes of the sponsor, by event, with their state,
value, offered quantity, kind, token category once set, and the reason of
a refusal. Once a prize is approved, the page also shows its **units
given**: the units shipped or handed over to winners (a virtual prize sent
counts as handed over), as a count, never the winners' names.

The form asks for the event (shown as text when the sponsor has one, a
list otherwise), the name, a plain-text description, a photo (JPEG, PNG,
GIF or WebP, resized to 1920 pixels and saved again without its
metadata, such as the position a phone records), the value in dollars
(the product's sales price), the offered quantity (informative: the
organization records the stock in the Inventory app when it receives the
units), and the kind of prize: a **physical prize** picked up on site
(winners checked in at the event) or a **virtual prize** sent by email
(any winner), with optional plain-text instructions.

The description fills the product's sale description and its eCommerce
description, which the product page of the shop shows. It stays plain
text: what looks like markup is shown as typed, a line break is kept and
an empty line starts a paragraph. Each change in the portal updates both,
as long as the eCommerce description is still the one the portal wrote
last (the product keeps a copy of it): once the organization rewrites it
in the backend, the sponsor's changes reach the sale description only,
until the organization empties it again. A change of the sale description
in the backend leaves the eCommerce description to the portal.

The sponsor of the prize is the company of the contact, or the person
when the contact has no company. Every contact of that company sees and
changes the company's prizes for its events; never another company's. A
submitted or refused prize can be changed or withdrawn; an approved prize
is read only.

### Approval

A prize created in the portal starts **Submitted**; a prize created in the
backend is **Approved**. A submitted or refused prize is archived and
unpublished, so it is offered nowhere: not in the prize choice of a draw,
the winner's shop, the member sales, the product snippets nor the winners
page. Its managers find it in **Raffle > Sponsored Prizes to Review** (or
with the **To review** filter of the sponsored prizes). A reviewer checks
the token category, which follows the value as for any prize, then clicks
**Approve**: the prize is restored, published and offered. Without a token
category, the approval is refused. Only a submitted or refused prize is
approved: an approved prize that an event manager archived or unpublished
stays so. **Refuse** asks for a reason, shown to the sponsor in the
portal; when the sponsor changes a refused prize, it is submitted again.
The sponsor receives no email for either: the portal shows the state.

A change of a submitted prize in the portal writes only the values that
differ: a form saved unchanged writes nothing. When a value changes, the
prize stays submitted and its managers are told (*Prize changed*), so
that they check it again before approving it. A new value recomputes the
token category, unless a reviewer chose another category than the one the
value gives: that choice stays.

The reviewers are the event managers, for every prize, and the
sponsorship managers of an event, for its sponsored prizes, without any
other right on the products. A prize of several events needs a
sponsorship manager of all of them; a prize offered to any event (no
event set) or without a sponsor is left to the event managers. The menu and the filter are shown to the event managers
and to the users listed as sponsorship managers on an event, who see the
prizes of their events there; the buttons are shown to the reviewers of
each prize only. A sponsorship manager cannot change the token category:
an event manager does when the value does not set the right one.

Each submission, and each submission after a refusal, notifies the
sponsorship managers of the event, else its responsible user, in their
inbox or by email as each one prefers, with a link to the prize.

### Shop category

An approved prize with a sponsor enters the shop category **Sponsored**
(*Commandite* in French), which the module creates: visitors find the
sponsored prizes there. Its other categories are kept. The prize leaves
the category when it is no longer approved or loses its sponsor; a
withdrawn prize is deleted. The organization's own prizes (without a
sponsor) are never put in it, though the organization may add any
product by hand. The shop lists the category only while it holds a
product the visitor may see: with the sponsored shop closed, ordinary
visitors do not see it. A deleted category is not recreated by the
approvals, which go on without it; as any data of a module, an update of
the module creates it again.

### Sponsor report

**Raffle > Reporting > Sponsor Report** (pivot by default, graph and list)
tells, for each sponsor, event and prize of the approved prizes:

| Measure | Computed from |
| --- | --- |
| Offered, Value Offered | the prize's Initial Quantity, times its value (sales price) |
| Won | the draws whose claim is reserved, shipped or handed over |
| Reserved, Value Reserved | the reserved claims, at the value stored on each claim |
| Shipped | the claims shipped and not received yet |
| Handed Over | the claims handed over on site, sent by email (virtual) or received |
| Declined | each decline of a claim, after the prize was reserved or through the link once the prize was in the cart |
| Expired | each link that ran out while its cart held the prize: the winner's interest, no unit spent |
| Bought by Members, Member Sales | the lines of confirmed member orders (quantity, untaxed amount in the company currency); a cancelled order leaves the report |
| Value Distributed | the shipped and handed-over claims, at the value stored on each claim |
| Remaining Stock | the quantity minus the reserved quantity in the internal locations |

Won, Reserved, Shipped and Handed Over follow the current state of each
draw. Declined and Expired read the claim log of the draws, which keeps
each decline and each expiry: a draw that declines a prize, then claims
another, counts both. A log line keeps the event, the token category, the
company and the date of its draw, so it keeps counting once the draw is
deleted, and once its raffle or its event is: a line whose event is
deleted counts for its prize with no event, which the sponsorship
managers, who read their events only, no longer see. A link declined or
run out with no prize in its cart counts on a line of its own,
**Declined, no choice** or **Expired link, no choice**, with no prize and
no sponsor, in the event and the token category of its draw; the **No
choice** filter lists them, and the Declined and Expired filters include
them. The stock moves do not change the claim figures, and a partial
delivery changes the remaining stock by the units actually moved. The
offered quantity, the remaining stock and the member purchases belong to
the prize's event when it has exactly one, else to no event: a prize of
several events is counted once. Filters and groupings by event, sponsor,
prize, token category, state and date. The sponsor is the company of the
prize's sponsor contact, or the person.

Each line has a date for the Date filter: the date of the draw, of the
member order, and for the offered quantity and the remaining stock the
start of the prize's first event (else the creation of the prize). The
amounts are in the currency of the line's company: the raffle's or the
event's for a claim, the order's for a purchase, and for the offer the
prize's, else the company of its events when they share one.

The event users read every line; a sponsorship manager reads the lines of
the events that list them.

### Thank the sponsors

**Thank the Sponsors**, on the event (once a sponsored prize has a
winner) and in the list of the report (select the lines of one event),
opens one line per sponsor whose prizes have a winner holding them:
reserved, shipped or handed over. Each line gives the recipients, the
number of winners, a **Send** box, and a status: why the line cannot be
ticked, and *Already thanked on <date>* when an email was already sent for
that sponsor and event; such a line starts unticked and may be ticked
again. Without any sponsored winner, the wizard says so and offers no
**Send**.

The recipients are the sponsor contacts of the event (the **Sponsor
contact** of its sponsor registrations not cancelled, under the sponsor's
company) that have an email; without any, the sponsor itself when it has
an email. A sponsor without any email is listed, cannot be ticked, and the
line says why.

The email comes from the template **Thanks to the sponsor** (Settings >
Technical > Email > Email Templates, in developer mode; the wizard links it
for the template editors), in the language of the first recipient. It lists the winners of
the sponsor's prizes for the event: the winner's public name (the public
name of the contact, else the winner's name, as on the winners page),
never their email, phone or photo, the prize, its token category, the date
of the draw and how the prize reached them (handed over on site, shipped,
sent by email, reserved). The wizard shows the rendered email of the
chosen sponsor before sending.

**Send** queues one email per ticked sponsor in the mail queue, logs it in
the event's chatter (sponsor, number of winners, recipients) and on the
sponsor's contact, and keeps the date for the next warning.

## Configuration

1. On the event, tick **Manage with sponsors** and choose the
   **Sponsorship managers**.
2. On each sponsor's registration, tick **Is a sponsor**, then click
   **Send invitation** when the form says the sponsor has no account.
3. Set the value ranges of the token categories (`event_raffle_prize`), so
   that each submitted prize gets its category from its value.

## Security

- Portal users get no new access right. The portal pages check that the
  user sponsors an open event, then read and write the prizes as
  superuser. A prize id from the request is looked up among the prizes of
  the user's company for the allowed events only: any other id answers
  404.
- The form writes a fixed list of fields (name, description, photo, value,
  offered quantity, kind and instructions), parsed and checked by the
  controller; the event comes from the allowed events. The sponsor, the
  approval state, the token category, the sale and publication flags and
  the stock are set by the module or the organization, never from the
  request. Every POST checks Odoo's CSRF token.
- The instructions are plain text, escaped into HTML. The photo must be a
  JPEG, PNG, GIF or WebP image: SVG is refused.
- Withdrawing deletes the prize only when no stock move nor order line
  holds it; otherwise the sponsor asks the organization.
- A submitted or refused prize cannot be restored by hand: **Approve**
  does it.
- The report is a read-only SQL query. Its record rules give every line
  to the event users, and the lines of their events to a sponsorship
  manager; a user in both groups reads every line.
- **Send invitation** creates a portal account: it is open to the event
  users only (checked on the server), not to the registration desk,
  which writes registrations as well.
- Thank the Sponsors is open to the event users and to the sponsorship
  managers of the event (checked on the server). The email is rendered and
  sent as superuser to the recipients computed from the event when
  sending: a line of the wizard never chooses an address, and a line of
  another event is refused.
- The users listed as sponsorship managers of at least one event join the
  hidden group *Raffle: sponsorship manager (set from the events)*: the
  module adds and removes them each time an event's list changes, and
  never adds a portal user. The group shows the review menu and filter,
  and reads the events and the token categories. Approve and Refuse check
  the events of each prize on the server, then write the approval fields
  as superuser: the group grants no write access on the products.

## Accessibility

The pages follow WCAG 2.2 AA: every field has a label, required fields
are marked and announced, a form sent with errors starts with a summary
that takes the focus and links to each field, and each field in error
names its message (`aria-invalid`, `aria-describedby`). Buttons, fields
and choices are 48 px high at least, and the pages fit a 390 px wide
screen.

## Known issues / Roadmap

- A sponsor is not notified of the approval or the refusal: they read the
  state in the portal.
- The portal writes the source text of the translated fields (name,
  description, instructions): the organization translates them after the
  approval.
- The remaining stock of the report sums every internal location, where
  the prize inventory reads the default warehouse only.
- A sponsor with contacts in several languages receives the email in the
  language of the first contact.

## Development

Run the tests with the other raffle modules:

```bash
EWP_AXE_JS=/path/to/axe.min.js ./test.sh -d test_db \
  -i event_raffle_prize_sponsor,event_raffle_survey,website_sale_collect,payment_demo \
  --test-tags /event_raffle_prize_sponsor,/event_raffle_prize_handover,/event_raffle_prize_claim,/event_raffle_prize,/event_raffle,/event_raffle_survey \
  --log-level=test --stop-after-init
```

Without `EWP_AXE_JS`, the accessibility test is skipped; when the variable
names a missing file, it fails.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

This module is maintained as part of ERPLibre.

---

# Event Raffle Prize Sponsors (Commanditaires des prix), français

Les commanditaires d'un événement soumettent eux-mêmes leurs prix pour
tirage, dans le portail, et l'organisation approuve chacun avant de
l'offrir. Le module s'appuie sur `event_raffle_prize_handover` (prix
virtuels) et les modules sous lui : `event_raffle_prize_claim` (boutique
du gagnant, ventes aux membres) et `event_raffle_prize` (catalogue, stock,
règles d'attribution). Un bilan dit ensuite l'apport de chaque
commanditaire, et un courriel par commanditaire le remercie avec la liste
de ses gagnants.

## Description

### Événement et inscriptions

- Sur la fiche de l'événement, **Gérer avec commanditaires** ouvre le
  portail aux commanditaires de l'événement, et **Responsables des
  commandites** liste les utilisateurs internes avisés de chaque prix
  soumis, qui approuvent ou refusent aussi les prix de cet événement. Sans
  responsable, le responsable de l'événement est avisé.
- Sur l'inscription d'un participant d'un tel événement, **Est
  commanditaire** marque la personne qui représente un commanditaire. La
  liste des inscriptions a une colonne facultative pour la case, et la
  recherche un filtre **Commanditaires**.
- Le contact du commanditaire est la personne qui participe et se
  connecte, jamais celle qui a réservé. Seule l'organisation le choisit :
  cocher la case prend le contact de l'inscription quand son courriel est
  celui du participant ; sinon **Envoyer invitation** prend un contact
  existant sans utilisateur qui a le courriel du participant, ou en crée
  un du nom et du courriel du participant. Un contact qui a déjà un
  utilisateur n'est jamais pris d'après son seul courriel, qu'Odoo ne
  vérifie pas : quand un compte utilise déjà le courriel du participant,
  l'invitation demande de mettre le contact de ce compte comme contact de
  l'inscription. Le contact du commanditaire ne change pas quand un
  courriel change ensuite. Un participant sans courriel ne peut pas être
  invité.
- Tant que ce contact n'a pas d'utilisateur portail ou interne, la fiche
  avertit *Ce commanditaire n'a pas de compte : il ne peut pas ajouter de
  prix dans le portail* et montre **Envoyer invitation**. Le bouton donne
  l'accès au portail et envoie l'invitation standard d'Odoo (le modèle de
  courriel de l'invitation au portail), par le même assistant
  que l'application Contacts. Une fois envoyée et jusqu'à la première
  connexion du commanditaire, la fiche dit *Invitation envoyée, pas encore
  acceptée* et le bouton la renvoie. Un utilisateur interne n'a pas besoin
  d'invitation : la fiche n'affiche ni l'un ni l'autre. Rien n'est envoyé
  automatiquement.
- À côté du bouton, **Courriel d'invitation** ouvre ce modèle de courriel,
  pour les utilisateurs qui peuvent modifier les modèles (*Éditeur de
  modèles de courriel* ou *Configuration*) ; les autres ne le voient pas.

### Portail : Prix pour tirage

Un utilisateur connecté voit **Prix pour tirage** dans **Mon compte** tant
que son contact, ou un autre contact de la même entreprise, a une
inscription de commanditaire, non annulée, à un événement géré avec
commanditaires qui n'est pas terminé. Les pages listent les prix du
commanditaire, par événement, avec leur état, leur valeur, la quantité
offerte, leur type, la catégorie de jeton une fois choisie, et la raison
d'un refus. Une fois un prix approuvé, la page montre aussi ses **unités
données** : les unités expédiées ou remises aux gagnants (un prix virtuel
envoyé compte comme remis), en nombre seulement, jamais le nom des
gagnants.

Le formulaire demande l'événement (affiché en texte quand le
commanditaire n'en a qu'un, en liste sinon), le nom, une description en
texte simple, une photo (JPEG, PNG, GIF ou WebP, réduite à 1920 pixels
et enregistrée de nouveau sans ses métadonnées, comme la position qu'un
téléphone y inscrit), la valeur en dollars (le prix de vente du
produit), la quantité offerte (à titre indicatif : l'organisation
inscrit le stock dans l'application Inventaire à la réception des
unités), et le type de prix : un **prix physique** à récupérer sur place
(gagnants présents à l'événement) ou un **prix virtuel** envoyé par
courriel (tout gagnant), avec des instructions facultatives en texte
simple.

La description remplit la description de vente du produit et sa
description pour le commerce en ligne, que la page d'article de la
boutique affiche. Elle reste du texte simple : ce qui ressemble à du
balisage s'affiche tel que saisi, un saut de ligne est gardé et une ligne
vide commence un paragraphe. Chaque modification dans le portail met les
deux à jour, tant que la description pour le commerce en ligne est encore
celle que le portail a écrite en dernier (le produit en garde une copie) :
une fois que l'organisation la réécrit dans le système, les modifications
du commanditaire ne touchent plus que la description de vente, jusqu'à ce
que l'organisation la vide de nouveau. Une modification de la description
de vente dans le système laisse au portail la description pour le
commerce en ligne.

Le commanditaire du prix est l'entreprise du contact, ou la personne
quand le contact n'a pas d'entreprise. Chaque contact de cette entreprise
voit et modifie les prix de l'entreprise pour ses événements ; jamais
ceux d'une autre entreprise. Un prix soumis ou refusé peut être modifié
ou retiré ; un prix approuvé est en lecture seule.

### Approbation

Un prix créé dans le portail commence **Soumis** ; un prix créé dans le
système est **Approuvé**. Un prix soumis ou refusé est archivé et non
publié : il n'est offert nulle part, ni dans le choix du prix d'un tir,
ni dans la boutique du gagnant, les ventes aux membres, les blocs
de produits du site ou la page des gagnants. Ses responsables le trouvent
dans **Tirage > Prix commandités à réviser** (ou avec le filtre **À
réviser** des prix commandités). Un réviseur vérifie la catégorie de
jeton, qui suit la valeur comme pour tout prix, puis clique **Approuver** :
le prix est restauré, publié et offert. Sans catégorie de jeton,
l'approbation est refusée. Seul un prix soumis ou refusé est approuvé : un
prix approuvé qu'un gestionnaire des événements a archivé ou dépublié le
reste. **Refuser** demande une raison, affichée au commanditaire dans le
portail ; quand le commanditaire modifie un prix
refusé, il est soumis de nouveau. Le commanditaire ne reçoit aucun
courriel pour l'un ou l'autre : le portail affiche l'état.

Une modification d'un prix soumis dans le portail n'écrit que les valeurs
qui changent : un formulaire enregistré sans changement n'écrit rien.
Quand une valeur change, le prix reste soumis et ses responsables en sont
avisés (*Prix modifié*), pour qu'ils le vérifient de nouveau avant de
l'approuver. Une nouvelle valeur recalcule la catégorie de jeton, sauf si
un réviseur a choisi une autre catégorie que celle que donne la valeur :
ce choix reste.

Les réviseurs sont les gestionnaires des événements, pour tous les prix,
et les responsables des commandites d'un événement, pour ses prix
commandités, sans autre droit sur les produits. Un prix de plusieurs
événements demande un responsable des commandites de chacun ; un prix
offert à tout événement (aucun événement choisi) ou sans commanditaire
revient aux gestionnaires des événements. Le
menu et le filtre s'affichent aux gestionnaires des événements et aux
utilisateurs nommés responsables des commandites d'un événement, qui y
voient les prix de leurs événements ; les boutons s'affichent aux seuls
réviseurs de chaque prix. Un responsable des commandites ne change pas la
catégorie de jeton : un gestionnaire des événements le fait quand la
valeur ne donne pas la bonne.

Chaque soumission, et chaque soumission après un refus, avise les
responsables des commandites de l'événement, sinon son responsable, dans
leur boîte de réception ou par courriel selon la préférence de chacun,
avec un lien vers le prix.

### Catégorie de la boutique

Un prix approuvé qui a un commanditaire entre dans la catégorie
**Commandite** de la boutique (*Sponsored* en anglais), que le module
crée : les visiteurs y trouvent les prix commandités. Ses autres
catégories sont gardées. Le prix quitte la catégorie quand il n'est plus
approuvé ou perd son commanditaire ; un prix retiré est supprimé. Les prix
de l'organisation (sans commanditaire) n'y sont jamais mis, même si
l'organisation peut y ajouter tout article à la main. La boutique ne
montre la catégorie que tant qu'elle contient un article que le visiteur
peut voir : la boutique commanditée fermée, les visiteurs ordinaires ne la
voient pas. Une catégorie supprimée n'est pas recréée par les
approbations, qui se poursuivent sans elle ; comme toute donnée d'un
module, une mise à jour du module la crée de nouveau.

### Bilan des commandites

**Tirage > Analyse > Bilan des commandites** (tableau croisé par défaut,
graphique et liste) donne, pour chaque commanditaire, événement et prix
des prix approuvés :

| Mesure | Calculée à partir de |
| --- | --- |
| Offert, Valeur offerte | la quantité initiale du prix, multipliée par sa valeur (prix de vente) |
| Gagnés | les tirs dont l'attribution est réservée, expédiée ou remise |
| Réservé, Valeur réservée | les attributions réservées, à la valeur gardée sur chacune |
| Expédié | les attributions expédiées et pas encore reçues |
| Remis | les attributions remises sur place, envoyées par courriel (virtuelles) ou reçues |
| Refusé | chaque refus d'une attribution, après la réservation du prix ou par le lien quand le prix était au panier |
| Expiré | chaque lien échu pendant que son panier contenait le prix : l'intérêt du gagnant, aucune unité dépensée |
| Achetés par des membres, Ventes aux membres | les lignes des commandes de membres confirmées (quantité, montant hors taxes dans la devise de la société) ; une commande annulée quitte le bilan |
| Valeur distribuée | les attributions expédiées et remises, à la valeur gardée sur chacune |
| Stock restant | la quantité moins la quantité réservée dans les emplacements internes |

Gagnés, Réservé, Expédié et Remis suivent l'état actuel de chaque tir.
Refusé et Expiré lisent le journal des attributions des tirs, qui garde
chaque refus et chaque expiration : un tir qui refuse un prix, puis en
choisit un autre, compte les deux. Une ligne du journal garde
l'événement, la catégorie de jeton, la société et la date de son tir :
elle compte donc encore une fois le tir supprimé, et une fois son tirage
ou son événement supprimé. Une ligne dont l'événement est supprimé compte
pour son prix sans événement, et les gestionnaires des commandites, qui
ne lisent que leurs événements, ne la voient plus. Un lien refusé ou échu
sans prix au panier compte sur une ligne à part, **Refusé sans choix** ou
**Lien expiré sans choix**, sans prix ni commanditaire, dans l'événement
et la catégorie de jeton de son tir ; le filtre **Sans choix** les liste,
et les filtres Refusé et Expiré les incluent. Les mouvements de stock ne
changent pas les chiffres des attributions, et une livraison partielle
change le stock restant des seules unités déplacées. La quantité offerte,
le stock restant et les achats des membres vont à l'événement du prix
quand il n'en a qu'un, sinon à aucun événement : un prix de plusieurs
événements compte une fois. Filtres et regroupements par événement,
commanditaire, prix, catégorie de jeton, état et date. Le commanditaire
est l'entreprise du contact commanditaire du prix, ou la personne.

Chaque ligne a une date pour le filtre Date : celle du tir, celle de la
commande du membre, et pour la quantité offerte et le stock restant le
début du premier événement du prix (sinon la création du prix). Les
montants sont dans la devise de la société de la ligne : celle du tirage
ou de l'événement pour une attribution, celle de la commande pour un
achat, et pour l'offre celle du prix, sinon celle de ses événements quand
ils en partagent une.

Les utilisateurs des événements lisent toutes les lignes ; un responsable
des commandites lit les lignes des événements qui le nomment.

### Remercier les commanditaires

**Remercier les commanditaires**, sur l'événement (une fois qu'un prix
commandité a un gagnant) et dans la liste du bilan (choisir les lignes
d'un seul événement), ouvre une ligne par commanditaire dont un prix a un
gagnant qui le détient : réservé, expédié ou remis. Chaque ligne donne les
destinataires, le nombre de gagnants, une case **Envoyer**, et un état :
pourquoi la ligne ne peut pas être cochée, et *Déjà remercié le <date>*
quand un courriel a déjà été envoyé pour ce commanditaire et cet
événement ; une telle ligne commence décochée et peut être cochée de
nouveau. Sans aucun gagnant commandité, l'assistant le dit et n'offre pas
**Envoyer**.

Les destinataires sont les contacts commanditaires de l'événement (le
**Contact du commanditaire** de ses inscriptions de commanditaire non
annulées, sous l'entreprise du commanditaire) qui ont un courriel ; sans
aucun, le commanditaire lui-même s'il a un courriel. Un commanditaire sans
aucun courriel est listé, ne peut pas être coché, et la ligne dit
pourquoi.

Le courriel vient du modèle **Merci au commanditaire** (Paramètres >
Technique > E-mail > Modèles d'e-mail, en mode développeur ; l'assistant y
mène les éditeurs de modèles), dans la langue du premier destinataire. Il liste les gagnants
des prix du commanditaire pour l'événement : le nom public du gagnant (le
nom public du contact, sinon le nom du gagnant, comme sur la page des
gagnants), jamais son courriel, son téléphone ni sa photo, le prix, sa
catégorie de jeton, la date du tir et la façon dont le prix lui est
parvenu (remis sur place, expédié, envoyé par courriel, réservé).
L'assistant montre le courriel rendu du commanditaire choisi avant
l'envoi.

**Envoyer** met dans la file d'envoi un courriel par commanditaire coché,
l'inscrit dans le fil de l'événement (commanditaire, nombre de gagnants,
destinataires) et sur le contact du commanditaire, et garde la date pour
l'avertissement suivant.

## Configuration

1. Sur l'événement, cocher **Gérer avec commanditaires** et choisir les
   **Responsables des commandites**.
2. Sur l'inscription de chaque commanditaire, cocher **Est
   commanditaire**, puis cliquer **Envoyer invitation** quand la fiche dit
   que le commanditaire n'a pas de compte.
3. Régler les intervalles de valeur des catégories de jeton
   (`event_raffle_prize`), pour que chaque prix soumis reçoive sa
   catégorie selon sa valeur.

## Sécurité

- Les utilisateurs du portail ne reçoivent aucun nouveau droit d'accès.
  Les pages du portail vérifient que l'utilisateur commandite un
  événement ouvert, puis lisent et écrivent les prix en superutilisateur.
  Un identifiant de prix venu de la requête est cherché parmi les prix de
  l'entreprise de l'utilisateur pour les événements permis seulement :
  tout autre identifiant répond 404.
- Le formulaire écrit une liste fixe de champs (nom, description, photo,
  valeur, quantité offerte, type et instructions), lus et vérifiés par le
  contrôleur ; l'événement vient des événements permis. Le commanditaire,
  l'état d'approbation, la catégorie de jeton, les cases de vente et de
  publication et le stock sont réglés par le module ou l'organisation,
  jamais par la requête. Chaque POST vérifie le jeton CSRF d'Odoo.
- Les instructions sont du texte simple, échappé en HTML. La photo doit
  être une image JPEG, PNG, GIF ou WebP : le SVG est refusé.
- Retirer supprime le prix seulement quand aucun mouvement de stock ni
  aucune ligne de commande ne le porte ; sinon, le commanditaire s'adresse
  à l'organisation.
- Un prix soumis ou refusé ne peut pas être restauré à la main :
  **Approuver** le fait.
- Le bilan est une requête SQL en lecture seule. Ses règles d'accès
  donnent toutes les lignes aux utilisateurs des événements, et les lignes
  de leurs événements à un responsable des commandites ; un utilisateur
  des deux groupes lit toutes les lignes.
- **Envoyer invitation** crée un compte du portail : il n'est ouvert
  qu'aux utilisateurs des événements (vérifié sur le serveur), pas à
  l'accueil des inscriptions, qui écrit aussi les inscriptions.
- Remercier les commanditaires est ouvert aux utilisateurs des événements
  et aux responsables des commandites de l'événement (vérifié sur le
  serveur). Le courriel est rendu et envoyé en superutilisateur aux
  destinataires calculés depuis l'événement à l'envoi : une ligne de
  l'assistant ne choisit jamais d'adresse, et une ligne d'un autre
  événement est refusée.
- Les utilisateurs nommés responsables des commandites d'au moins un
  événement entrent dans le groupe caché *Tirage : responsable des
  commandites (selon les événements)* : le module les ajoute et les retire
  à chaque changement de la liste d'un événement, et n'y ajoute jamais un
  utilisateur du portail. Le groupe affiche le menu et le filtre de
  révision, et lit les événements et les catégories de jeton. Approuver et
  Refuser vérifient les événements de chaque prix sur le serveur, puis
  écrivent les champs d'approbation en superutilisateur : le groupe ne
  donne aucun droit d'écriture sur les produits.

## Accessibilité

Les pages suivent les WCAG 2.2 AA : chaque champ a une étiquette, les
champs obligatoires sont marqués et annoncés, un formulaire envoyé avec
des erreurs commence par un résumé qui prend le focus et mène à chaque
champ, et chaque champ en erreur nomme son message (`aria-invalid`,
`aria-describedby`). Les boutons, champs et choix ont 48 px de haut au
moins, et les pages tiennent sur un écran de 390 px de large.

## Problèmes connus / Feuille de route

- Un commanditaire n'est pas avisé de l'approbation ni du refus : il lit
  l'état dans le portail.
- Le portail écrit le texte source des champs traduits (nom, description,
  instructions) : l'organisation les traduit après l'approbation.
- Le stock restant du bilan additionne tous les emplacements internes, là
  où l'inventaire des prix lit l'entrepôt par défaut seulement.
- Un commanditaire dont les contacts ont plusieurs langues reçoit le
  courriel dans la langue du premier contact.

## Développement

Les commandes de test sont celles de la section *Development* ci-dessus.
Sans `EWP_AXE_JS`, le test d'accessibilité se met de côté ; si la
variable nomme un fichier absent, il échoue.

## Crédits

### Auteurs

- TechnoLibre

### Contributeurs

- Mathieu Benoit

### Mainteneurs

Ce module est maintenu dans le cadre d'ERPLibre.
