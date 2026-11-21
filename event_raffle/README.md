# Event Raffle (Tirage)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

Tirages animés (roue 3D three.js poussée par Tux) pour les événements Odoo, avec
historique des gagnants.

## Description

À partir d'un événement, démarrez une **activité de tirage** : les inscrits/présents
sont copiés en participants, auxquels vous pouvez ajouter des contacts (`res.partner`)
ou des invités libres. Lancez des **tirs** successifs : une roue 3D tourne et révèle
un gagnant avec feux d'artifice. Le gagnant est retiré du pool par défaut. Un smart
button sur l'événement affiche la liste des gagnants.

## Configuration

Aucune configuration requise. Par activité de tirage, l'onglet **Paramètres**
regroupe les réglages :

- **Tirage de test** (décoché par défaut) : marque un tirage de répétition
  ou d'essai. Le formulaire affiche alors un ruban **Test**, et la liste des
  tirages le montre en orange, avec la colonne *Tirage de test* cochée.
  Voir *Tirages de test et filtre Prod* ci-dessous.
- **Retirer le gagnant** : exclut le gagnant des tirs suivants (activé par défaut).
- **Durée de rotation** / **Nombre de tours** : cinématique de la roue.
- **Afficher les feux d'artifice** : feux à la révélation du gagnant.
- **Afficher le pingouin (Tux)** : montre Tux à côté de la roue.
  **Caché par défaut** (réglable par tirage et dans les paramètres généraux).
- **Logo du ventre** : appose un logo sur le ventre de Tux — *Aucun* (défaut)
  ou *Fleur-de-lys (Québec)*. Visible uniquement quand Tux est affiché.
- **Animation Tux** : voir *Animations de Tux* ci-dessous.
- **Texte du drapeau** : texte (multi-lignes) de l'animation *drapeau* ; une ligne
  est tirée au hasard à chaque tir (défaut : *Vive le logiciel libre*).
- **Thème** : *Clair* / *Sombre* / *Spectacle* (projecteurs) / *Théâtre*
  (dorures & anges à la trompette) / *Linux techno (sombre)* et
  *Linux techno (clair)* (terminal en arrière-plan, voir ci-dessous) /
  *Rave* (lasers).
- **Célébration du gagnant** : *Chandelles* (Tux danse, flamme réaliste),
  *Canon à confettis*, *Canon à feux d'artifice*, *Fanfare de trompette*
  (avec musique), *Jonglage de diabolo*, ou *Aléatoire* (une au hasard à
  chaque tir).
- **Notifier le gagnant automatiquement** (section *Notification du
  gagnant*, désactivé par défaut) : après chaque tir, **OdooBot** envoie au
  gagnant le **Message notification**, champ qui n'apparaît qu'une fois la
  case cochée, modifiable et alors obligatoire (défaut : *« Vous avez gagné
  un prix, venez le réclamer ! {lien} »*). Il accepte les mêmes paramètres
  que le **Message canal** ci-dessous. L'envoi suit les règles du bouton
  **Notifier** (étape 6 de *Usage*) : clavardage privé, sinon courriel. Un
  gagnant qu'on ne peut joindre n'empêche pas le tir : il ne reçoit rien et
  une note sur le tir l'explique ; sa colonne *Notifié* reste décochée.
- **Annoncer chaque tir dans un canal de discussion** (section *Annonce dans
  un canal*, désactivé par défaut) : après chaque tir, **OdooBot** publie le
  **Message canal** dans le **Canal de discussion** choisi (un canal ou une
  discussion de groupe de *Discussion*). Les deux champs n'apparaissent
  qu'une fois la case cochée, et deviennent alors obligatoires. L'utilisateur
  qui fait le tir n'a pas à être membre du canal. Le message accepte des
  paramètres, en français ou en anglais : `{gagnant}` / `{winner}` (le nom du
  gagnant tel qu'affiché sur le tir et la roue), `{numéro}` / `{number}` (le
  numéro du tir), `{tirage}` / `{raffle}` (le nom du tirage), `{prix}` /
  `{prize}` (le lot saisi sur la roue ; avec *event_raffle_prize*, sinon la
  catégorie de jeton du tir) et `{lien}` / `{link}` (le lien de prix du tir,
  avec *event_raffle_prize_claim* ; il n'ouvre la réclamation qu'au compte
  du gagnant connecté). Défaut : *« Tir #{numéro} : {gagnant} a gagné !
  ({prix}) {lien} »*. Un paramètre sans valeur disparaît avec l'espace qui
  le précède, et un paramètre seul entre parenthèses disparaît avec elles,
  d'où *« Tir #3 : Alice a gagné ! »* sans lot ni lien. Une accolade isolée
  ou un nom inconnu reste tel quel. Un canal archivé ou
  supprimé, ou une publication refusée, n'empêche pas le tir : une note sur
  le tir l'explique. OdooBot publie au nom du superutilisateur un texte que
  les utilisateurs du tirage écrivent : l'utilisateur qui choisit le canal
  doit pouvoir le lire (canal ouvert à ses groupes, discussion de groupe
  dont il est membre), sinon l'enregistrement est refusé. Une discussion
  directe n'est jamais acceptée : ni au choix, ni à la publication, qui
  laisse alors une note sur le tir.

Le menu **Tirage → Paramètres** définit les valeurs par défaut (thème,
célébration, animation, etc.) appliquées à chaque nouveau tirage. Le gagnant
**reste sur la roue** après un tir et n'est retiré du pool qu'au **tir suivant**.
Les noms longs sont **répartis sur plusieurs lignes** (max 4) dans la roue.

Sa section **Messages** donne aussi les valeurs de départ de chaque nouveau
tirage : **Notifier le gagnant automatiquement**, **Message notification**,
**Annoncer chaque tir dans un canal de discussion**, **Canal de discussion**
et **Message canal**. Un message laissé vide donne le message standard, dans
la langue de l'utilisateur qui crée le tirage. Annoncer par défaut exige un
canal ; un canal archivé ou supprimé depuis, ou que l'utilisateur qui crée
le tirage ne peut pas lire, n'est pas repris, et l'annonce reste alors
désactivée sur le nouveau tirage. Les tirages existants gardent leurs
valeurs.

Un tirage appartient à sa **société** : le tirage, ses participants, ses
tirs et leurs notifications ne se lisent que dans les sociétés où
l'utilisateur travaille (règles d'enregistrement globales, comme celles
d'Odoo). Un tirage sans société se lit de partout.

La roue a un **cadre en bois** et un **pion à chaque intersection** ; la flèche
dévie quand un pion passe dessous, puis **revient droite** en douceur à l'arrêt. Sous le gagnant, un panneau **Historique des
gagnants** (repliable, replié par défaut) permet de cliquer un tir pour voir ses
détails (lot, courriel, date, **présent**). La **présence** de chaque participant
se règle dans la **liste des participants** (colonne *Présent*, cochée par
défaut) ; marquer un gagnant absent la décoche. Les noms ajoutés puis **sauvegardés**
apparaissent automatiquement sur la roue. Le bouton **Plein écran** (dans la
barre d'outils, à la place du bouton *Quitter*) est désactivé pendant un tirage.
Le bouton **Prochain tirage** se désactive automatiquement quand il ne reste
plus assez de participants (évite l'erreur « aucun participant éligible »).
Tux se tient à **gauche** de la roue, sauf pour les thèmes *Linux* où il passe
à **droite** pour laisser voir le terminal d'arrière-plan. Dans la barre
d'outils, le champ *Lot* est à gauche, le **gagnant est centré**, et le bouton
*Prochain tirage* est à droite au-dessus de l'historique.

## Tirages de test et filtre Prod

La liste des tirages (menu **Tirage → Tirages**, et bouton intelligent
**Tirages** de l'événement) s'ouvre sur le filtre **Prod**, qui n'affiche que
les tirages dont la case **Tirage de test** est décochée. Le filtre **Test**
montre les tirages de test ; cocher les deux, ou retirer la facette *Prod*,
affiche tous les tirages. La liste des gagnants offre les mêmes filtres
**Prod** et **Test**, d'après le tirage de chaque tir, sans en appliquer
aucun par défaut.

## Usage

1. Ouvrir un événement → bouton **« Démarrer un tirage »**.
2. Choisir qui entre dans le tirage (champ **Participants**) :
   - *Présents seulement* : les inscrits marqués présents ;
   - *Inscrits et présents* : les inscrits confirmés et les présents ;
   - *Questionnaire rempli seulement* : les inscrits, présents ou non, qui ont
     répondu à au moins une question du questionnaire d'inscription (onglet
     *Questions* de l'événement). Seules les questions de type *Sélection* ou
     *Saisie de texte* comptent. Les types d'identification *Nom*, *E-mail*,
     *Téléphone* et *Société* sont ignorés : ils disent qui est l'inscrit, et
     Odoo ajoute d'office les trois premiers, que le formulaire en ligne
     pré-remplit ;
   - *Questionnaire rempli et présent* : la même chose, pour les présents
     seulement.

   Les inscriptions qui partagent un même identifiant (le contact, sinon le
   courriel, sinon le nom) n'entrent qu'une fois. Le module `event_raffle_survey`
   ajoute *Sondage rempli seulement*, qui prend les répondants d'un sondage
   (`survey`).
3. Ajouter au besoin des participants (contact ou invité) dans l'onglet Participants,
   puis **sauvegarder** : ils apparaissent automatiquement sur la roue. La colonne
   *Exclu* et les boutons **Tout inclure** / **Tout exclure** retirent quelqu'un de
   la roue sans l'effacer.
4. Cliquer **« Démarrer le tirage »** (ou **« Plein écran »** pour projeter ; le bouton
   **« Quitter le plein écran »** revient à la vue précédente).
5. Enchaîner avec **« Prochain tirage »**. Marquer un gagnant **absent** depuis le tir
   (une note/activité peut être ajoutée dans le chatter).
6. **Notifier le gagnant** : dans l'onglet **Tirs**, ouvrir la ligne du tir puis
   cliquer **« Notifier »**. L'assistant choisit l'expéditeur (**OdooBot** par
   défaut, ou **Moi**, l'utilisateur courant ; jamais un autre utilisateur) et
   propose un message modifiable, par défaut *« Vous avez gagné un prix, venez
   le réclamer ! {lien} »*, ou le **Message notification** du tirage quand
   celui-ci notifie ses gagnants automatiquement. Les paramètres du message
   (`{gagnant}`, `{lien}`, etc.) sont remplacés à l'envoi. L'envoi dépend du
   gagnant :
   - son contact a un **compte utilisateur interne** actif : un **clavardage
     privé** dans *Discussion*, la conversation directe entre l'expéditeur et
     le gagnant, créée au besoin ;
   - sinon, s'il a un **courriel** (celui du contact, ou celui saisi sur le tir) :
     le même message par **courriel**. Un utilisateur **portail** passe par
     ici : il n'a pas accès à *Discussion* et un clavardage ne lui parviendrait
     pas ;
   - sinon : l'assistant explique pourquoi et n'offre pas de bouton *Envoyer*.

   Un gagnant **absent** peut être notifié : c'est l'usage principal. Chaque
   envoi est consigné sur le tir (section *Notifications* du formulaire) et
   laisse une note dans le chatter. Les listes des tirs et des gagnants
   affichent, après *Date*, les colonnes **Notifié**, **Lu** (le gagnant a vu
   la dernière notification par clavardage ; jamais coché pour un courriel)
   et **Notifications** (le nombre d'envois). Peut notifier qui peut modifier
   les tirs (groupe *Événements / Utilisateur*). Les notifications ne se
   créent ni ne se modifient à la main : seul l'assistant les écrit, après
   ses vérifications ; un gestionnaire peut en supprimer une.

## Animations de Tux

Avant chaque tir, Tux le pingouin joue une petite animation puis lance la roue.
Quatre animations sont disponibles (champ **Animation Tux** de l'onglet Paramètres) :

| Valeur | Animation |
|--------|-----------|
| **Peace** | Tux saute sur place avec un signe ✌. |
| **Saut avec sourire** | Grand saut avec squash/stretch et un `:)`. |
| **Drapeau du logiciel libre** | Tux brandit un drapeau ; le texte vient du champ **Texte du drapeau** (une ligne au hasard). |
| **Danse** | Tux se déhanche et pirouette sur une note ♪. |
| **Rotation (alterne toutes)** | *(défaut)* alterne les quatre animations d'un tir à l'autre. |

Tux et les célébrations sont **procéduraux** (construits en three.js, aucun
asset externe). Tux est modélisé comme un vrai pingouin : corps en poire, tête
allongée sur un **cou** (plus fin que la tête), **blanc continu du ventre au
menton** avec des **pectoraux**, **pieds palmés à trois orteils**, long bec (avec
ligne de bouche, **narines** et dégradé orange), **sourcils**, et des bras
(nageoires) mis **vers l'avant** sur pivots. Il **cligne des yeux** aléatoirement
et **se gratte parfois la tête** au repos ; pendant la danse **et quand la roue
tourne** il **pivote sur l'axe vertical** (gauche↔droite) pour montrer son
volume 3D. La taille de Tux est normalisée à ~33 % de la hauteur de la roue et
la scène est recadrée pour rester entièrement visible.

## Thèmes Linux : terminal en arrière-plan

Les thèmes **Linux techno (sombre)** et **Linux techno (clair)** affichent un
**terminal** en arrière-plan (style **GNOME Terminal** : titre centré, boutons
_min / max / fermer_ à droite) derrière la roue transparente. Il « tape » les
commandes pilotant chaque tir, avec un **curseur qui clignote**, et **Tux sort
un clavier** et pianote pendant la saisie. À chaque tirage, la séquence jouée
est :

```console
raffle@tux:~$ clear
raffle@tux:~$ tux_animation --type <animation> [--flag "..."]
raffle@tux:~$ run
[run] playing '<animation>' choreography…
raffle@tux:~$ wheel --spin --entries <N>
[wheel] <N> names: <participants…>
[wheel] spinning… ▀▄▀▄▀▄
>>> WINNER: <gagnant>
raffle@tux:~$ echo "🎉 <gagnant>" | festival
```

Les commandes sont saisies caractère par caractère (effet machine à écrire),
puis l'animation de Tux, la rotation de la roue et le gagnant s'enchaînent en
synchronisation avec le transcript. Au repos, un bandeau d'accueil est affiché.
L'effet est surtout pensé pour le mode **plein écran** (projection).

## Known issues / Roadmap

- Tux est modélisé procéduralement (primitives three.js) pour ressembler à la
  mascotte ; aucun fichier 3D externe n'est requis.

## Changes

- **18.0.1.7.0** : case **Tirage de test** dans l'onglet *Paramètres* du
  tirage, ruban **Test** sur le formulaire et colonne dans la liste. La
  liste des tirages s'ouvre sur le nouveau filtre **Prod**, qui cache les
  tirages de test ; filtres **Prod** et **Test** aussi dans la liste des
  gagnants. Les tirages existants restent en production.
- **18.0.1.6.0** : paramètre `{lien}` / `{link}`, le lien de prix du tir,
  dans le **Message canal** et dans le **Message notification**, qui accepte
  désormais tous les paramètres du message canal, à l'envoi automatique
  comme dans l'assistant **Notifier**. Un paramètre sans valeur disparaît
  sans laisser d'espace. Nouveaux messages par défaut, terminés par
  `{lien}` ; à la mise à jour, un tirage dont le message est encore
  exactement un ancien défaut (anglais ou français) reçoit le nouveau dans
  la même langue, un message modifié reste tel quel.
- **18.0.1.4.0** : réglage **Notifier le gagnant automatiquement** et
  champ **Message notification** dans l'onglet *Paramètres* du tirage :
  OdooBot envoie le message à chaque gagnant après le tir, par clavardage
  privé ou par courriel, et le consigne sur le tir comme le bouton
  **Notifier**. Avec `event_raffle_prize_claim`, le gagnant reçoit ce
  message d'abord, puis le lien de prix. À la mise à jour, le message des
  tirages existants est écrit dans la langue de leur créateur, ou de leur
  société quand le créateur n'existe plus.
- **18.0.1.3.0** : bouton **Notifier** sur le tir. Notification du gagnant
  par clavardage privé (OdooBot ou l'utilisateur courant) quand il a un
  compte interne, sinon par courriel (y compris un utilisateur portail) ;
  suivi par tir (colonnes *Notifié*, *Lu* et compteur *Notifications*),
  écrit par l'assistant seul.

## Bug Tracker

Signaler les anomalies via le suivi du dépôt ERPLibre.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

Ce module est maintenu dans le cadre d'ERPLibre.
