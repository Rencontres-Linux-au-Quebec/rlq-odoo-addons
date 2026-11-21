# Event Raffle Survey (Tirage par sondage)

[![License: AGPL-3](https://img.shields.io/badge/license-AGPL--3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0-standalone.html)

Draw an event raffle among the respondents of a survey. The French version
follows the English one.

## Description

Adds the *Survey filled only* choice to the **Start a Raffle** wizard of an
event, from the `event_raffle` module. Pick a survey: its respondents enter the
raffle instead of the event's registrations.

The two *Questionnaire* choices of `event_raffle` are a different thing: they
keep the registrations that answered the event's own registration questions.

## Usage

1. Open an event, then click **Start a Raffle**.
2. Under **Participants**, choose *Survey filled only*, then pick the
   **Survey**. Closed surveys are listed too: closing a survey archives it, and
   the draw usually comes after.
3. Optionally, add questions of that survey to **Required Questions**, then
   choose under **Answered** whether a respondent must have answered *Each* of
   them (the default) or *At least one*.
4. Check **Respondents Entering**: it counts, as the choices change, the
   people the draw will hold. **Anonymous Among Them** shows up when some of
   them gave no contact, email or nickname.
5. Click **Start**. The survey's respondents become the raffle's
   participants, with the *Survey* source. The event's registrations are not
   copied.

## Who enters

An answer counts when it is completed, is not a test entry, and answers at
least one question. Ending a live session marks every answer of the survey
completed, even one that was only opened: the last condition keeps those out.
A question saved as the respondent's nickname or email does not count as an
answer, since Odoo fills it in for a logged-in respondent before they answer
anything.

When **Required Questions** lists questions, an answer must also answer each
of them, or at least one, as **Answered** says. Answering means giving a
non-blank answer, right or wrong. An empty list filters nobody, and picking
another survey empties it.

Each person enters once. Answers linked to the same contact are one person.
An answer with no contact joins the contact whose answers carry its email
(whatever its case, and `"Name" <address>` included), unless that address
shows on the answers of several contacts, a family address for instance,
which tells nobody apart; that is read from every answer of the survey,
finished or not, so a filter never hides it. The other answers group by
email, then by nickname; an answer with none of the three enters alone, as a
separate *Guest*. A person is named by their contact, else by their oldest
nickname, else by their oldest email, else *Guest*; the participant's email
is the oldest one their answers carry.

## Access rights

Reading a survey's answers needs the *Surveys: User* access right, which Odoo
gives every internal user when the survey module is installed. An event user
without it is not offered *Survey filled only*, and the survey fields stay
out of the form. The module never reads the answers as superuser, so a survey
restricted to some users stays restricted.

Only non-specialised surveys are offered (survey, live session, assessment,
custom): a recruitment survey keeps its answers to the Recruitment app.

## Known issues / Roadmap

- A survey left with Odoo's default settings (anyone with the link, no login)
  gives respondents with no contact, email or nickname. Each one enters as a
  separate *Guest*, and a guest who wins cannot be identified. For a raffle,
  require login, invite people, or add a question saved as email or nickname.

## Development

```bash
# Tests of both modules, on a fresh database (explicit ports: Odoo's test
# mode opens an HTTP server even with --stop-after-init).
./odoo_bin.sh db --drop --database test_event_raffle_survey
./test.sh -d test_event_raffle_survey --db-filter test_event_raffle_survey \
    -i event_raffle_survey --test-tags /event_raffle,/event_raffle_survey \
    --http-port=18069 --gevent-port=18072

# Formatting
./script/maintenance/format.sh \
    ./odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_survey

# Translations: export the template, then update fr_CA.po by hand against it
# and check the result (an export with -l fr_CA would blank every translation
# identical to its source)
./odoo_bin.sh -d test_event_raffle_survey --modules=event_raffle_survey \
    --i18n-export=odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_survey/i18n/event_raffle_survey.pot
msgfmt --check -o /dev/null \
    odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_survey/i18n/fr_CA.po
```

The wizard is also driven end to end in Firefox against a running instance:
see `selenium/README.md`.

## Credits

### Authors

- TechnoLibre

### Contributors

- Mathieu Benoit

### Maintainers

This module is maintained as part of ERPLibre.

---

# Event Raffle Survey (Tirage par sondage) — français

Tirer au sort un gagnant d'événement parmi les répondants d'un sondage.

## Description

Ajoute le choix *Sondage rempli seulement* à l'assistant **Démarrer un
tirage** d'un événement, issu du module `event_raffle`. Choisissez un sondage :
ses répondants entrent dans le tirage à la place des inscrits de l'événement.

Les deux choix *Questionnaire* d'`event_raffle` sont autre chose : ils gardent
les inscrits qui ont répondu aux questions d'inscription de l'événement.

## Utilisation

1. Ouvrir un événement, puis cliquer **Démarrer un tirage**.
2. Dans **Participants**, choisir *Sondage rempli seulement*, puis le
   **Sondage**. Les sondages fermés sont proposés aussi : fermer un sondage
   l'archive, et le tirage vient souvent après.
3. En option, ajouter des questions de ce sondage aux **Questions exigées**,
   puis choisir sous **Répondu à** si un répondant doit avoir répondu à
   *Chacune* (par défaut) ou à *Au moins une*.
4. Lire **Répondants retenus** : le compte, qui suit les choix, des personnes
   que le tirage contiendra. **Dont anonymes** apparaît quand certaines n'ont
   donné ni contact, ni courriel, ni pseudo.
5. Cliquer **Démarrer**. Les répondants du sondage deviennent les participants
   du tirage, avec la source *Sondage*. Les inscrits de l'événement ne sont pas
   copiés.

## Qui entre

Une participation compte si elle est terminée, n'est pas un test et répond à
au moins une question. Terminer une session en direct marque terminées toutes
les participations du sondage, même celles qui ont seulement été ouvertes : la
dernière condition les écarte. Une question enregistrée comme pseudo ou
courriel du répondant ne compte pas comme réponse : Odoo la remplit pour un
répondant connecté avant qu'il ne réponde à quoi que ce soit.

Si les **Questions exigées** contiennent des questions, une participation doit
aussi répondre à chacune, ou à au moins une, selon **Répondu à**. Répondre veut
dire donner une réponse non vide, juste ou non. Une liste vide ne filtre
personne, et choisir un autre sondage la vide.

Chaque personne n'entre qu'une fois. Les participations liées au même contact
sont une seule personne. Une participation sans contact rejoint le contact
dont les participations portent son courriel (quelle qu'en soit la casse,
`"Nom" <adresse>` compris), sauf si cette adresse figure sur les
participations de plusieurs contacts, une adresse familiale par exemple, qui
ne départage personne ; cela se lit sur toutes les participations du sondage,
terminées ou non, si bien qu'un filtre ne le cache jamais. Les autres
participations se regroupent par courriel, puis par pseudo ; une participation
sans aucun des trois entre seule, comme un *Invité* distinct. Une personne est
nommée par son contact, sinon par son plus ancien pseudo, sinon par son plus
ancien courriel, sinon *Invité* ; le courriel du participant est le plus
ancien que portent ses participations.

## Droits d'accès

Lire les participations d'un sondage demande le droit *Sondages :
Utilisateur*, qu'Odoo donne à tout utilisateur interne quand le module
`survey` s'installe. Un utilisateur des événements qui ne l'a pas ne se voit
pas proposer *Sondage rempli seulement*, et les champs du sondage restent hors
du formulaire. Le module ne lit jamais les participations en
superutilisateur, et un sondage réservé à certains utilisateurs le reste.

Seuls les sondages non spécialisés sont proposés (sondage, session en direct,
évaluation, personnalisé) : un sondage de recrutement garde ses participations
pour l'application Recrutement.

## Problèmes connus / Feuille de route

- Un sondage aux réglages par défaut d'Odoo (toute personne ayant le lien,
  sans connexion) donne des répondants sans contact, courriel ni pseudo.
  Chacun entre comme un *Invité* distinct, et un invité qui gagne ne peut pas
  être identifié. Pour un tirage, exiger la connexion, inviter les
  participants, ou ajouter une question enregistrée comme courriel ou pseudo.

## Développement

Les commandes de test, de formatage et de traduction sont celles de la section
*Development* ci-dessus. L'assistant est aussi parcouru de bout en bout dans
Firefox, contre une instance démarrée : voir `selenium/README.md`.

## Crédits

### Auteurs

- TechnoLibre

### Contributeurs

- Mathieu Benoit

### Mainteneurs

Ce module est maintenu dans le cadre d'ERPLibre.
