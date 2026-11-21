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

Le menu **Tirage → Paramètres** définit les valeurs par défaut (thème,
célébration, animation, etc.) appliquées à chaque nouveau tirage. Le gagnant
**reste sur la roue** après un tir et n'est retiré du pool qu'au **tir suivant**.
Les noms longs sont **répartis sur plusieurs lignes** (max 4) dans la roue.

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

## Bug Tracker

Signaler les anomalies via le suivi du dépôt ERPLibre.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

Ce module est maintenu dans le cadre d'ERPLibre.
