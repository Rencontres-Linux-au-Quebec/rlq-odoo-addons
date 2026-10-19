# Notes de validation — rlq_survey_report

Ce module a été écrit **sans accès à une instance Odoo** pour le tester
(aucun outil de ce genre n'était disponible pendant sa rédaction). Il
repose sur la structure standard du module `survey` d'Odoo 18 CE. Avant
toute utilisation en production, validez les points suivants sur votre
**instance de dev/staging**.

## -72. Adresses courriel invalides des inscriptions (v1.109.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Après `-u rlq_survey_report`, les champs `rlq_email_issue` et `rlq_email_suggestion` (stockés, calculés depuis `email`) sont remplis pour les inscriptions EXISTANTES (Odoo calcule un champ stocké nouveau à la mise à jour) ; le menu Événements > Courriels invalides apparaît (parent `event.event_main_menu`, groupe `event.group_event_user` ; identifiants vérifiés dans les sources d'Odoo 18).
2. Inscription par le site avec `marie@gmail'com` (paramètre `registration_email_autofix` = `syntax`) : l'inscription est créée avec `marie@gmail.com`, note dans le fil, confirmation reçue à la bonne adresse. Avec `off` : adresse gardée, marquée « Adresse invalide », suggestion affichée.
3. Bouton « Corriger et renvoyer » (liste : bouton d'en-tête sur la sélection, et bouton de ligne ; formulaire : bloc « Adresse courriel ») : la fenêtre s'ouvre avec la suggestion, l'inscription et le contact sont corrigés, les `mail.mail` en échec repassent « En attente » (`mark_outgoing`) et la confirmation part (modèles des planificateurs « after_sub » de l'événement, sinon `event.event_subscription`). La notification finale ferme la fenêtre.
4. Traductions françaises (`i18n/fr.po`, nouveau dossier) chargées pour fr_CA : libellés « Problème de courriel », « Corriger et renvoyer », menus.
5. Les quatre tests de `tests/test_registration_email.py` n'ont pas été exécutés ; `tests/test_email_check.py` (sans Odoo) passe (run-all.sh, étape 4).

## -71. Tâche planifiée désactivée sans case cochée, intervalle par défaut, sommaire (v1.108.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Après `-u rlq_survey_report`, sans aucune case cochée : la tâche « RLQ Sondages et événements : synchronisation périodique… » est **désactivée** (Paramètres > Technique > Tâches planifiées, filtre « Archivé/inactif » ou liste complète) et le journal d'Odoo n'affiche plus « Job … starting » toutes les 5 minutes.
2. Cocher la case d'un sondage ou d'un événement la réactive (≤ quelques secondes) ; la décocher la désactive. La balise `<function model="survey.survey" name="_rlq_ajuster_cron"/>` s'exécute à la mise à jour du module sans erreur.
3. Le champ `active` n'étant plus dans le XML de la tâche, une mise à jour du module ne la réactive pas (à confirmer).
4. Le menu « Synchronisation : sommaire » s'ouvre (fenêtre) et l'HTML s'affiche sans échappement parasite (`Markup`) ; `cron.lastcall` / `nextcall` s'affichent dans le fuseau de l'utilisateur.
5. Paramètre système `rlq_survey_report.synchro_minutes_defaut` (ex. 30) : un nouveau sondage ou événement propose 30. Les trois tests `test_cron_active_seulement_si_une_case_est_cochee`, `test_intervalle_par_defaut_parametre_systeme`, `test_sommaire_dit_si_la_tache_est_desactivee` n'ont pas été exécutés.

## -70. Synchronisation périodique des événements (v1.107.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Le code de la tâche planifiée (deux instructions : sondages puis `env['event.event']._cron_rlq_synchroniser_evenements()`) s'exécute tel quel (`state=code`, saut de ligne accepté).
2. La liste « Synchronisation périodique (événements) » s'ouvre (domaine : événements avec préfixe) et le bouton de ligne appelle `action_rlq_synchroniser_groupes`.
3. `date_end` d'`event.event` est un Datetime (comparaison avec `fields.Datetime.now()`). Le test `test_synchro_periodique_evenement_intervalle_et_fin` n'a pas été exécuté.

## -69. Synchronisation périodique par sondage et page d'aide (v1.106.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. La liste modifiable « Synchronisation périodique » s'ouvre (menu Sondages > Rapports détaillés) et la modification en place de la case et des minutes s'enregistre ; le bouton de ligne appelle bien `action_rlq_appliquer_groupes_participants` (un `ir.actions.client` de notification dans une liste est normal).
2. La tâche « RLQ Sondages : synchronisation périodique… » apparaît dans Tâches planifiées (toutes les 5 minutes) ; avec `model_id` = `survey.model_survey_survey` et `code` = `model._cron_rlq_synchroniser_sondages()`.
3. Les champs apparaissent dans le bloc « Groupes des réponses » du formulaire du sondage (même xpath `//sheet` que le bouton existant).
4. `/rlq_survey_report/aide` sert le guide (type `http`, `auth="user"`) ; `odoo.tools.file_open` accepte le chemin `rlq_survey_report/doc/…` ; le menu « Guide d'utilisation » ouvre un nouvel onglet (`ir.actions.act_url`, `target=new`).
5. Les tests Odoo `test_synchro_periodique_*`, `test_synchro_intervalle_minimum`, `test_bouton_met_aussi_a_jour_les_etiquettes` n'ont pas été exécutés (comparaison d'heures : `fields.Datetime.now()` sans fuseau).

## -68. Répétition de l'avertissement d'inscriptions (v1.105.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Les nouveaux champs `rlq_alerte_repeter` et `rlq_alerte_palier` apparaissent dans le bloc « Avertissements par courriel » de l'événement (même xpath que 1.95).
2. À N = 2, quatre inscriptions confirmées donnent exactement deux courriels (à 2 et à 4) ; changer N remet le compteur à zéro.
3. Le test Odoo `test_repetition_a_chaque_multiple_de_n` n'a pas été exécuté (courriels `auto_delete` : adapter la recherche de `mail.mail` si besoin).

## -67. Groupes des inscrits (v1.98.0, annulation et sondage v1.99.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Un compte PORTAIL accepte un groupe personnalisé (sans catégorie) : Odoo n'interdit que le mélange de groupes de type d'utilisateur. Si l'écriture échoue, l'erreur est journalisée et l'inscription continue.
2. Nom du champ des groupes de `res.users` : `groups_id` (Odoo 18 habituel) ou `group_ids` ; le code détecte les deux (`_champ_groupes_utilisateur`).
3. `res.partner.user_ids` existe et contient le compte portail du contact de l'inscription ; une inscription sans contact (courriel seul) n'est jamais ajoutée.
4. Les vues `event.view_event_form` (avec `<sheet>`), `event.event_event_ticket_view_tree_from_event` (avec `<list>`) et `event.view_event_registration_form` (avec `<sheet>`) existent sous ces noms : sinon l'installation échoue sur le xpath (les champs existeraient quand même).
5. Le canal Discuss : « Groupes à abonner automatiquement » ajoute bien comme membres les utilisateurs du groupe, y compris portail, et ceux qui rejoignent le groupe plus tard. À défaut, ajouter les membres au canal par code (`discuss.channel.add_members`).
6. (v1.99.0) La vue `survey.survey_question_form` contient `<field name="suggested_answer_ids">` avec une `<list>` intégrée : sinon l'installation échoue sur ce xpath (le champ `rlq_group_id` de `survey.question.answer` existerait quand même).
7. (v1.99.0) Le champ `suggested_answer_id` des lignes `survey.user_input.line` et l'état `done` de `survey.user_input` ; la participation doit avoir un `partner_id` (personne connectée) : une réponse anonyme ne donne aucun groupe.
8. Les tests Odoo de `TestRlqGroupesInscrits` n'ont pas été exécutés.
9. (v1.101.0) `res.groups.name_create` : redéfini pour écrire `name` ; vérifier sur DEV que « Créer » dans le champ « Groupe Odoo » crée bien le groupe.

**Vie privée (Loi 25) :** le refus (« Ne pas ajouter au groupe ») est respecté à chaque synchronisation ; envisager une question explicite dans le formulaire d'inscription.

## -66. Courriel « sondage complété » (v1.96.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. `survey.user_input._mark_done()` est appelé à la soumission de la dernière page (voir -64) ; sinon aucun courriel ne part.
2. Le champ `survey_id` de `event.event` n'existe pas toujours (module d'événements avec sondage) : il n'est lu que s'il existe ; les sondages de type de billet (`rlq_survey_id`) fonctionnent sans lui.
3. La participation est reliée à l'inscription par `partner_id`, sinon par le courriel ; une personne qui répond avec un autre courriel que celui de son inscription apparaît avec le nom de son contact (ou « une personne »).
4. Les tests Odoo de `TestRlqAlerteSondage` n'ont pas été exécutés.

**Vie privée :** le courriel nomme la personne et son billet (comme la touche I de app-log-live.py) ; il ne contient ni ses réponses ni son courriel. Il part vers l'adresse de l'organisateur configurée.

## -65. Avertissement après N inscriptions (v1.95.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. La vue `event.view_event_form` existe sous ce nom et contient un `<sheet>` : sinon l'installation échoue sur le xpath (les champs `rlq_alerte_*` existeraient quand même).
2. `event.registration.state` prend bien les valeurs `open` et `done` pour une inscription confirmée / présente (Odoo 18) ; les inscriptions d'une boutique en ligne sont créées en brouillon puis confirmées : le `write()` sur `state` déclenche alors la vérification.
3. Un inscrit public (site web) ne peut pas lire l'événement : la vérification passe par `sudo()` ; confirmer qu'une inscription sur le site déclenche le courriel au seuil.
4. Le serveur de courriel sortant est configuré (expéditeur : courriel de la société ou `mail.default.from`) ; le courriel est mis en file puis envoyé par la tâche planifiée « Mail: Email Queue Manager ».
5. Le lien « Ouvrir l'événement dans Odoo » (`/odoo/event.event/ID`) suppose Odoo 18 et `web.base.url` correct.
6. Les tests Odoo de `TestRlqAlerteInscriptions` n'ont pas été exécutés.

**Vie privée :** le courriel ne contient que le nom de l'événement, sa date, le nombre d'inscriptions et le seuil.

## -64. Courriel des réponses au participant (v1.94.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. `survey.user_input._mark_done()` existe et est appelé à la soumission de la dernière page (Odoo 18) ; sinon le courriel ne part jamais — vérifier dans les journaux « courriel de réponses non envoyé » et le champ « Courriel de réponses envoyé le ».
2. Le serveur de courriel sortant est configuré ; le courriel est mis en file (`mail.mail`) puis envoyé par la tâche planifiée « Mail: Email Queue Manager » (jusqu'à quelques minutes).
3. Le modèle utilise `user.company_id.email_formatted` comme repli de l'expéditeur : si le sondage n'a pas de responsable, la société doit avoir un courriel.
4. Les champs de ligne de réponse lus (`value_text_box`, `value_char_box`, `suggested_answer_id`, `matrix_row_id`, `value_numerical_box`, `value_date`, `value_datetime`, `skipped`) sont lus avec `getattr` : un champ absent est simplement ignoré.
5. Les tests Odoo de `TestRlqCourrielReponses` n'ont pas été exécutés.

**Vie privée :** le courriel contient les réponses du participant et part en clair vers son adresse ; il est supprimé des courriels sortants après envoi (`auto_delete`). Informer les participants (Loi 25) si la case est cochée.

## -63. Mot de passe par défaut jamais écrasé, anonymisation des noms à parenthèses, listes sans courriel (v1.93.0)

**Remplace les sections -50, -51 et -61 sur un point : `noupdate="1"` NE protège PAS** ce paramètre.
Il ne protège que contre `-u`. En mode « init » (`-i`, ou réinstallation), Odoo recharge les données
en ignorant `noupdate`. Le paramètre n'est donc plus un `<record>` : il est créé par une balise
`<function>` seulement s'il est absent.

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. La balise `<function model="rlq.survey.report.wizard" …/>` s'exécute-t-elle bien au chargement ?
   Les erreurs y sont volontairement journalisées, pas levées : si le paramètre n'apparaît pas après
   `-u`, chercher « Impossible de créer le paramètre » dans les journaux serveur.
2. Après mise à jour, tester le scénario qui a échoué : relancer avec `-i` (ou réinstaller) et constater
   que la valeur définie est conservée.
3. `ir.model.data.unlink()` ne supprime que la ligne de liaison, pas l'enregistrement visé (attendu,
   non essayé ici).

**À décider :** `rlq_survey_report.url_aide` a la même fragilité (voir le changelog). Plusieurs textes
historiques de ce fichier affirment que `noupdate` protège une valeur : ils sont inexacts pour `-i`.

**Anonymisation :** `\b…\b` est remplacé par `(?<!\w)…(?!\w)` dans `rb.remplacer_nom_complet()`. Même
comportement pour un nom qui commence et finit par un caractère de mot ; seule différence : les noms
qui finissent ou commencent par un caractère NON alphanumérique sont enfin trouvés. « [courriel
masqué] » subsiste uniquement pour une adresse écrite dans une réponse libre.

## -62. Historique sans colonne en double, run-all.sh, ruff, guide HTML (v1.92.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. Feuille de style `static/src/css/historique_fichiers.css` : les sélecteurs supposent
   `th[data-name="fichier_telecharger"]` et `td[name="fichier_telecharger"]`. S'ils ne
   correspondent pas, rien ne casse mais la colonne reste étroite. Après mise à jour : Ctrl+F5.
2. `column_invisible="1"` sur `nom_fichier` tout en gardant `filename="nom_fichier"` sur le widget
   binaire : standard dans Odoo 17+, mais non essayé ici. Si le nom disparaissait de la colonne
   « Télécharger », rendre `nom_fichier` visible (`optional="show"`).
3. Aucun attribut `width` utilisé volontairement (validité inconnue pour la liste d'Odoo 18).
4. Infobulle impossible sans JavaScript (le widget binaire n'en a pas) : remplacée par le retour
   à la ligne du nom complet.
5. `run-all.sh` : l'étape 5 n'a été validée qu'avec de fausses commandes. Hypothèses : le résumé des
   tests dans le journal d'Odoo se présente comme « N failed, M error(s) of T tests » (repli sur le
   code de retour sinon), et `--test-tags=/rlq_survey_report` sélectionne tous les tests du module.

**ruff** : configuration volontairement restreinte aux bogues (E4, E7, E9, F, B). Cette version de
ruff active par défaut des dizaines de règles de style qui contredisent les conventions d'Odoo
(déclaration d'encodage, tri des imports...). B905 ignorée (changement de comportement possible).

**À décider :** `pdf_saut_page_participant` (défaut `True` dans le code, « décoché par défaut » dans
son aide) ; nom de la tâche planifiée de purge contenant encore « RLQ ».

**Guide utilisateur** : reconstruit sans l'ancien `.html` (seul le `.md` du 10 septembre était
disponible). Si ce `.html` contenait des captures d'écran ou des retouches manuelles, elles ne sont
pas reportées ; les emplacements de capture gardent la numérotation de l'ancien guide.

## -61. Fusion de deux branches : mot de passe, anonymisation, doc/ (v1.91.0)

**Points non vérifiés sans accès à une instance, à confirmer en priorité :**
1. L'encadré d'avertissement (`div.alert` conditionné par `invisible`, champ `Char` -
   JAMAIS `Html`) et le bouton « Ouvrir le paramètre » (fiche `ir.config_parameter`
   ouverte en dialogue ; si aucune vue formulaire n'est définie, Odoo en génère une).
2. La règle « écran » (mot de passe exigé à l'écran si non anonymisé) a été conservée
   alors que l'autre branche voulait un accès sans mot de passe pour un utilisateur connecté :
   AMBIGUÏTÉ à trancher. Pour la lever, passer `"screen"` à la liste de formats de
   `_mot_de_passe_requis()` ET retirer `or not self.anonymiser` de `action_generate()` -
   attention : `_sauvegarder_copie_ecran()` stocke alors en clair une copie non anonymisée.
3. Les copies d'écran anonymisées sont stockées SANS chiffrement (même avec un mot de passe
   par défaut pré-rempli) : cohérent avec la rétention indéfinie des copies anonymisées (v1.80.0).
4. `test_wizard.py` n'a pas pu être exécuté : les tests ajoutés ou adaptés sont à lancer
   sur une base de test jetable.

**Décisions** : voir « Décisions de fusion » dans `doc/CHANGELOG.md`, entrée 18.0.1.91.0.
`forcecreate="False"` NON utilisé sur le paramètre du mot de passe : en mode mise à jour,
il empêcherait sa CRÉATION sur une base qui n'avait pas encore ce paramètre.

## -60. Détail des soumissions par participant, commentaire du personnel, réponses multiples une par ligne (v1.86.0)

**Points non vérifiés sans accès à une instance, à confirmer en
priorité :**

1. **`end_datetime` comme "date de réponse"** - déjà un champ CONFIRMÉ
   sur `survey.user_input` (utilisé pour calculer une durée moyenne
   depuis plusieurs versions de ce module), mais son usage ICI (comme
   valeur affichée directement à l'utilisateur, pas seulement comme
   opérande d'une soustraction) suppose qu'il correspond bien au moment
   RÉEL de soumission pour une réponse "done" - à vérifier sur une
   soumission réelle dont l'heure de réponse est connue par ailleurs.
2. **`survey.survey_user_input_view_form`** - l'external ID de la vue
   formulaire native de `survey.user_input`, choisi PAR ANALOGIE avec
   `survey.survey_survey_view_form` (confirmé fonctionner sur cette
   instance pour `survey.survey`) - PAS confirmé lui-même. Si
   l'installation échoue avec "External ID not found" précisément sur
   le bloc `view_survey_user_input_form_rlq_commentaire`, chercher le
   bon nom via Réglages > Technique > Vues (filtrer par modèle
   `survey.user_input`) et corriger cette seule référence - le champ
   `rlq_commentaire_staff` reste utilisable sur le modèle même si cette
   vue précise ne charge pas.
3. **Droits d'écriture du rôle "Sondage : Utilisateur" sur
   `survey.user_input`** - aucune nouvelle règle d'accès ajoutée pour
   `rlq_commentaire_staff`, en présumant que ce rôle a déjà accès en
   écriture à ce modèle nativement (pour gérer/réviser les réponses) -
   à confirmer qu'un compte avec seulement ce rôle peut bel et bien
   remplir ce nouveau champ.

**Choix de conception à noter** : le "Détail des soumissions" liste
chaque `survey.user_input` séparément (une personne ayant répondu deux
fois au même sondage voit ses deux soumissions), mais le grand tableau
de réponses par question, lui, N'A PAS été restructuré - il reste une
colonne par RENCONTRE (pas par soumission individuelle), donc en cas de
double soumission, seule la dernière traitée par la boucle existante
apparaît dans ce tableau. Une refonte plus large aurait été nécessaire
pour éviter ça complètement, jugée hors de la portée de cette demande
précise.

## -59. Second filtre "test" trouvé et retiré, codé en dur dans la vue (v1.85.0)

Après le retrait du `default="test"` sur `exclude_title_keywords`
(v1.84.0), l'utilisateur signale toujours ne pas voir de sondages
"test". Cause réelle : un DEUXIÈME mécanisme, `domain="[('title', 'not
ilike', 'test')]"` directement sur le champ `survey_ids` dans
`views/rlq_survey_report_views.xml` - invisible lors du premier
correctif puisqu'il n'est pas dans le code Python du modèle mais dans
la vue XML. Retiré. Recherche exhaustive faite pour confirmer qu'aucune
troisième occurrence ne subsiste dans le module (modèles et vues).

**Leçon retenue** : quand un comportement semble "câblé en dur" plutôt
qu'issu d'un champ configurable évident, chercher AUSSI dans les
fichiers de vue (domaines, contexts par défaut), pas seulement dans le
modèle Python - les deux peuvent imposer des restrictions indépendantes
sur le même champ.

## -58. Filtre "test" par défaut retiré, lien de téléchargement corrigé (v1.84.0)

**[1]** `exclude_title_keywords` avait `default="test"` depuis
l'origine du module - masquait silencieusement tout sondage sélectionné
contenant "test" dans son titre. Retiré (vide par défaut).

**[2]** `fichier_telecharger` dans la liste "Historique et fichiers déjà
générés" n'affichait aucun lien cliquable - `widget="binary"` explicite
ajouté à la vue. NON CONFIRMÉ SANS ACCÈS À UNE INSTANCE que ceci
suffise à lui seul (hypothèse la plus probable pour un champ Binary
invisible en vue liste, mais pas testée). Rappel important pour la
vérification : seules les entrées générées APRÈS la mise à jour vers la
v1.83.0 (qui a introduit la copie de contenu indépendante) ont
effectivement un fichier à télécharger - les entrées antérieures
resteront sans lien, ce n'est pas un bogue résiduel.

## -57. CORRECTIF CRITIQUE - la règle d'accès ir.attachment de v1.80.0 cassait l'accès aux pièces jointes de tout Odoo (v1.83.0)

**Confirmé en production, régression grave** : la règle `ir.rule`
ajoutée en v1.80.0 (`ir_rule_attachment.xml`, censée permettre à
d'autres utilisateurs de télécharger un rapport généré par quelqu'un
d'autre) a cassé l'accès à TOUTES les pièces jointes de tout Odoo pour
quiconque dans le groupe Sondage - y compris des images de site web
sans aucun rapport avec ce module. Message d'erreur Odoo reçu par
l'utilisateur, citant explicitement cette règle par son nom.

**Cause exacte** : mauvaise compréhension de la sémantique des règles
`ir.rule` liées à un groupe dans Odoo. Une telle règle ne s'ADDITIONNE
JAMAIS à l'accès existant - elle le REMPLACE par sa propre condition,
pour TOUT LE MODÈLE visé, dès qu'elle est la seule règle de ce type
pour ce groupe sur ce modèle. J'avais bien noté dans `NOTES_VALIDATION.md`
(v1.80.0) que ce mécanisme n'était "pas vérifié sans instance", mais
j'anticipais un risque de "ne fonctionne pas comme prévu" (le partage ne
marche pas), pas un risque de RÉGRESSION ACTIVE sur des fonctionnalités
sans aucun rapport. Une sous-estimation du risque réel de cette
approche - à retenir : une règle ir.rule scope à un groupe sur un
modèle PARTAGÉ (utilisé par d'autres parties d'Odoo, comme
`ir.attachment`) est TOUJOURS un risque de ce type, pas seulement "à
tester".

**Corrigé** : retrait complet de la règle. Le partage de fichiers entre
utilisateurs (menu "Historique et fichiers déjà générés") passe
maintenant par une COPIE INDÉPENDANTE du contenu stockée directement sur
`rlq.survey.report.acces` (`fichier_telecharger`, `attachment=False`),
gouvernée uniquement par les droits d'accès de ce modèle propre au
module - plus aucune dépendance envers les droits de `ir.attachment` en
général.

**Leçon retenue pour la suite** : ne plus jamais ajouter de règle
d'accès (`ir.rule`) sur un modèle Odoo générique et partagé par
d'autres fonctionnalités (`ir.attachment`, `res.partner`, etc.) pour
résoudre un besoin propre à ce module - toujours passer par un modèle
dédié au module (déjà la pratique pour tout le reste de ce module,
c'est cette seule exception qui a causé le problème).

**Action manuelle immédiate recommandée** (avant même la mise à jour du
module) : Réglages → Technique → Sécurité → Règles d'enregistrement →
supprimer "Pièces jointes rlq_survey_report - lecture pour le groupe
Sondage" - débloque l'accès tout de suite, sans attendre le déploiement
de cette version.

## -56. Lien de sondage par billet corrigé - `get_start_url()` plutôt que `survey.id` (v1.82.0)

**Confirmé en conditions réelles** : après le correctif v1.81.0 (champ
enfin visible dans l'outil Placeholder dynamique), le lien apparaissait
bien dans le courriel reçu (`.../survey/start/70`) mais ne menait à
aucun sondage. Cause : `survey.id` (la clé interne en base de données)
n'est pas l'identifiant attendu par la route publique
`/survey/start/...` - une erreur d'autant plus évitable que ce module
avait DÉJÀ appris cette leçon ailleurs (`_lien_test_sondage()` dans
`rlq_survey_report_wizard.py`, après 3 tentatives ratées avant
d'aboutir à `get_start_url()`/`action_test_survey()`) - cette leçon
n'avait simplement pas été reprise lors de l'écriture de
`event_ticket_survey.py` (v1.73.0), un fichier séparé écrit plus tard.

**Corrigé** : `get_start_url()`, la méthode native d'Odoo, avec repli
sur `access_token` (jamais `id`) si cette méthode échoue.

**PAS ENCORE CONFIRMÉ** : que `get_start_url()` fonctionne aussi bien
pour un lien de PARTICIPATION réelle (le cas d'usage ici) que pour le
lien de TEST déjà validé (`_lien_test_sondage()`, un cas d'usage
légèrement différent - mode test vs réponse réelle). À confirmer par un
envoi de courriel réel après mise à jour.

**Leçon à retenir pour la suite** : toute nouvelle fonctionnalité de ce
module construisant une URL vers un sondage devrait chercher
`_lien_test_sondage()`/`get_start_url()` comme référence AVANT d'écrire
sa propre logique de construction d'URL - au moins deux bogues
similaires (URL de sondage cassée) ont maintenant été rencontrés dans
ce module pour cette même raison.

## -55. `rlq_lien_sondage_billet` invisible dans l'outil Placeholder dynamique - rendu stocké (v1.81.0)

**Symptôme rapporté** : en configurant le courriel de confirmation
(v1.73.0), `rlq_survey_id` (sur le billet) apparaît bien dans la
recherche de l'outil « Placeholder dynamique », mais
`rlq_lien_sondage_billet` (sur l'inscription) reste introuvable même en
cherchant son nom technique complet.

**Hypothèse retenue et appliquée** : `rlq_lien_sondage_billet` était un
champ calculé NON STOCKÉ (`compute=..., store=False` implicite) -
contrairement à `rlq_survey_id`, une vraie colonne. Rendu stocké
(`store=True` + `@api.depends`).

**NON CONFIRMÉ SANS ACCÈS À UNE INSTANCE** - deux issues possibles à la
prochaine vérification :
1. Le champ apparaît maintenant dans l'outil après la mise à jour du
   module → hypothèse confirmée, rien d'autre à faire.
2. Le champ reste introuvable même stocké → la cause est ailleurs
   (pistes à explorer alors : un problème de chargement du module lui-
   même sur `event.registration` précisément, une limite d'affichage de
   l'outil de recherche non liée au stockage, ou un tout autre
   mécanisme propre à cette version d'Odoo/ERPLibre). Dans ce cas,
   vérifier directement via Réglages > Technique > Structure de la base
   de données > Modèles > event.registration > onglet Champs, qui
   liste tous les champs réels du modèle indépendamment de l'outil
   Placeholder.

Par ailleurs, corrigé au passage : plusieurs commentaires et textes
d'aide du fichier `event_ticket_survey.py` référençaient encore l'ancienne
syntaxe `${object.champ}` (Jinja), retirée des gabarits de courriel Odoo
depuis la version 15 - remplacée par QWeb (corps) et `{{ }}` (champs
simples), voir l'échange en conversation pour le détail confirmé par le
code source public d'Odoo.

## -54. Bibliothèque de fichiers déjà générés, rétention indéfinie pour les copies anonymisées (v1.80.0)

**Confirmé fonctionnel en théorie, NON VÉRIFIÉ SUR UNE VRAIE INSTANCE :**
le partage d'une pièce jointe ENTRE PLUSIEURS PERSONNES (pas seulement
celle qui l'a générée) dépend de la nouvelle règle
`security/ir_rule_attachment.xml`. Odoo gère l'accès aux pièces jointes
(`ir.attachment`) en partie via du code Python propre au cœur du
framework, en plus des règles ir.rule standards - il est arrivé,
historiquement, sur certaines versions, que ce code central ne respecte
pas pleinement une règle personnalisée dans certains contextes précis
(ex. le contrôleur `/web/content` peut avoir sa propre logique d'accès,
distincte d'une recherche ORM classique).

**À TESTER EN PRIORITÉ avant de compter sur ce partage :**
1. Générer un rapport (à l'écran ou téléchargé) avec le compte A.
2. Se connecter avec un compte B différent, membre du même groupe
   (`survey.group_survey_user`).
3. Ouvrir "Sondage > Rapports détaillés > Historique et fichiers déjà
   générés" et essayer de télécharger le fichier généré par le compte A.
4. Si le compte B obtient une erreur d'accès refusé : la règle
   `ir_rule_attachment.xml` ne suffit pas à elle seule sur cette version
   d'Odoo/ERPLibre - il faudra investiguer le code source
   d'`ir.attachment` (`_check_attachment_access` ou équivalent) pour
   trouver le bon mécanisme (possiblement `public=True` sur la pièce
   jointe, avec les implications de sécurité que cela comporte - un
   attachment public est accessible par lien direct sans authentification,
   à ne considérer qu'après avoir bien pesé ce compromis).

**Autre point à surveiller** : sans purge automatique pour les copies
anonymisées (retirée sur demande explicite), le volume de pièces
jointes va croître de façon continue, y compris pour de simples essais
de filtres abandonnés en cours de route (chaque affichage à l'écran en
sauvegarde une copie). Aucune action requise immédiatement, mais à
surveiller si l'espace disque devient un enjeu - le nettoyage se fait
alors manuellement (suppression des pièces jointes, l'historique lui-
même reste intact grâce à `ondelete="set null"`).

## -53. Correctif "nom d'une seule lettre non anonymisé", avis conditionnel, menu redondant retiré, historique sur deux lignes (v1.79.0)

**[1] Bogue confirmé en conditions réelles.** Un participant ayant
"F" comme nom sur sa fiche contact restait visible, non anonymisé, dans
un rapport pourtant anonymisé - exactement le scénario que le garde-fou
de v1.56.0 anticipait (voir son commentaire d'origine, désormais
obsolète) mais résolvait par EXCLUSION plutôt que par une protection
véritable. Corrigé avec une limite de mot regex (`\b...\b`) - vérifié
manuellement (script Python autonome, hors Odoo) que "F" est maintenant
remplacé correctement SANS corrompre "Filtre", et que l'ordre
long-vers-court (ex. "Jean Dupont" avant "Jean") reste respecté.
NON VÉRIFIÉ SUR UNE VRAIE INSTANCE : le chemin complet (génération d'un
rapport anonymisé avec un participant nommé d'une seule lettre) n'a pu
être testé qu'en isolant la logique de remplacement dans un script
Python autonome, pas via le wizard réel sur des données Odoo.

**[3] Menu retiré.** "Tous les sondages (terminé et commencé)" retiré
de "Rapports détaillés" - le raccourci "Filtrer par titre : Tous" dans
l'assistant lui-même couvre déjà ce besoin. `action_menu_tous()`
retirée ; `_survey_ids_tous()` CONSERVÉE (toujours utilisée par le
raccourci "Filtrer par titre" lui-même).

**[4] Historique d'accès.** `resume_sondages` passé de `Char` à `Text` -
affiche maintenant toutes les dates (plus de troncature), sur deux
lignes si la liste dépasse 10 dates. Vue mise à jour avec
`widget="text"` pour un rendu multi-lignes correct dans la liste.

## -52. Anonymisation par contexte (jetons de présentateurs), historique d'accès affichant des dates (v1.78.0)

Correction suite au retour utilisateur sur la v1.77.0 : l'exclusion
globale des noms de présentateurs (ajoutée pour préserver leur nom dans
"Appréciation des présentateurs") les gardait visibles PARTOUT dans le
rapport, y compris dans "Liste des participants" - pas le comportement
voulu. Remplacé par un mécanisme de jetons contextuels (voir
`jeton_presentateur()`/`proteger_nom_dans_titre()` dans
`report_builder.py`, et `_resoudre_jetons_presentateurs()` dans le
wizard) : le nom reste visible SEULEMENT dans les titres de
présentation et la section "Appréciation des présentateurs", anonymisé
partout ailleurs (y compris pour la même personne si elle a aussi
répondu à un sondage).

NON VÉRIFIABLE SANS ACCÈS À UNE INSTANCE : ce mécanisme, plus complexe
que le précédent (protection avant anonymisation, résolution après),
n'a été validé que par les tests unitaires sur les fonctions pures de
`report_builder.py` (`test_report_builder.py`) - le chemin complet
(protection → anonymisation → résolution, sur un vrai rapport généré
avec un présentateur qui a aussi répondu à un sondage) n'a pas pu être
testé de bout en bout sur une instance réelle. À vérifier en priorité
avant une mise en production : générer un rapport anonymisé où AU MOINS
UNE personne est à la fois présentatrice et répondante, et confirmer
que son nom apparaît anonymisé dans "Liste des participants"/sa fiche,
mais reste visible (nom réel, PAS un jeton du style
"⟦RLQ-PRESENTATEUR:...⟧") dans "Appréciation des présentateurs" et dans
le "Volet" de la question Présentations.

Aussi dans cette version : `rlq.survey.report.acces.resume_sondages`
affiche désormais des dates plutôt que des titres complets, sur demande
(trop long avec les titres).

## -51. Anonymisation renforcée, mot de passe obligatoire à l'écran si non anonymisé, nouvel historique d'accès (v1.77.0)

**[1] Anonymisation renforcée.** Sur demande, suite à la discussion sur
la conformité Loi 25 de l'anonymisation existante (voir échange
précédent : ce qui était implémenté correspondait à de la
"dépersonnalisation" au sens de la loi, pas à une "anonymisation"
irréversible - la distinction reste vraie, ce renforcement RÉDUIT le
risque de réidentification sans nécessairement atteindre le seuil légal
strict de l'anonymisation, qui exige une analyse de risque documentée
et l'irréversibilité complète). Concrètement :
  - Présentateurs exemptés du remplacement par pseudonyme (ils
    restent nommés).
  - Coordonnées (courriel, téléphone, mobile, ville, pays) et
    étiquettes RETIRÉES du rendu HTML, pas seulement masquées - élimine
    le risque qu'une occurrence échappe au remplacement textuel en aval
    (le mécanisme existant, `_anonymiser_html()`, reste utilisé pour le
    NOM, où un remplacement en aval demeure nécessaire puisque le nom
    apparaît dans de très nombreux endroits générés séparément - ancre
    HTML, table des matières, en-têtes de section...).

**[2] Mot de passe obligatoire à l'écran si non anonymisé.** Avant
cette version, le mot de passe n'était exigé QUE pour un téléchargement
(HTML/PDF) - un affichage à l'écran, même avec les vrais noms des
participants visibles, ne le demandait jamais. Corrigé : dès que
"Anonymiser les participants" est décoché, le mot de passe est
maintenant exigé même pour un simple affichage à l'écran.

**[3] Nouvel historique d'accès.** NON VÉRIFIABLE SANS ACCÈS À UNE
INSTANCE :
  - Le nouveau modèle `rlq.survey.report.acces` et ses droits d'accès
    n'ont pas pu être testés sur une instance réelle - à vérifier que
    la création d'une entrée (via `sudo()`) fonctionne bel et bien
    sans erreur de droits, et que le menu "Historique d'accès aux
    rapports" s'affiche correctement sous "Rapports détaillés".
  - Le groupe `base.group_system` utilisé pour la gestion complète
    (lecture/écriture/suppression) de cet historique est un groupe
    Odoo standard très stable, mais son usage exact pour CE modèle
    précis (plutôt qu'un groupe "Administrateur Sondage" dédié, dont le
    nom n'a pas pu être confirmé sans accès au code source du module
    `survey` à ce sujet précis) est un choix par défaut, ajustable si
    vous préférez restreindre différemment.
  - Portée légale de cet historique volontairement limitée dans la
    documentation du modèle : ce n'est PAS le registre d'incidents de
    confidentialité formellement exigé par la Loi 25 (art. 3.5, qui
    porte sur les INCIDENTS, pas sur les accès normaux) - à confirmer
    avec un conseiller juridique si vous voulez vous appuyer dessus
    pour une obligation légale précise plutôt que comme simple bonne
    pratique de traçabilité.

## -50. Flèche toujours cliquable, pourcentages corrigés, libellé simplifié, retrait de "RLQ" (v1.75.0)

**[1] Flèche non cliquable sous 2 personnes.** `rendu_nombre_avec_
detail_notes()` utilisait un simple tooltip au survol (non cliquable)
en dessous d'un seuil de 2 personnes distinctes, empêchant d'accéder à
la fiche de cette personne dans ce cas précis - incohérent avec le
comportement au-dessus du seuil (liste dépliable, chaque nom
cliquable). Le seuil est retiré : toujours la liste dépliable,
peu importe le nombre de personnes (même une seule).

**[2] Pourcentages incohérents entre la barre et les statistiques
textuelles.** Signalé par l'utilisateur : une note de 2/5 affichait 25%
dans la colonne "Statistiques", alors que la barre juste à côté
suggérait 40% (2 sur 5). Cause confirmée : `barre()` et
`_classe_pourcentage()` utilisaient déjà `valeur/échelle_max*100`
(0% à 0, 100% au maximum), mais `stats_pourcentage_html()`,
`section_tendance_question()` (étiquette texte), `section_note_globale()`
(statistiques ET comparaison historique) et `section_top_mouvements()`
utilisaient une formule ANCRÉE à `echelle_min=1`
((valeur-echelle_min)/(échelle_max-echelle_min)*100) - un reliquat de
la fonction originale, jamais harmonisé avec `barre()` depuis
l'introduction des pourcentages en v1.72.0/v1.73.0, malgré un
commentaire dans le code signalant DÉJÀ une incohérence similaire pour
les seuils de coloration (voir `_classe_pourcentage()`, dont les seuils
100/80/40% supposaient, eux, la bonne formule depuis le début). Corrigé
partout pour utiliser `valeur/échelle_max*100`, la même formule que
`barre()`.

**Choix délibéré non touché :** la HAUTEUR (en pixels) des barres du
graphique de tendance reste ancrée à `echelle_min` - un choix de rendu
VISUEL distinct de l'exactitude du CHIFFRE affiché (voir le
commentaire dans `section_tendance_question()`), pour continuer à bien
distinguer visuellement des valeurs rapprochées (ex. 4.0 vs 5.0, un
ancrage à 0 compresserait cet écart visuellement). Seule l'étiquette
texte (%) a été corrigée.

**[3] Libellé simplifié.** "Note globale de cette rencontre" :
"3% sous la moyenne" plutôt que "3 point de % sous la moyenne".

**[4] Retrait de "RLQ" de tout ce qui est visible.** Sur demande
explicite - l'objectif est que d'autres organisations puissent utiliser
ce module sans porter la marque de Rencontres Linux au Québec. Retiré
de : le nom du module dans la liste des Apps Odoo, tous les libellés de
menu/action ("Rapport de sondage RLQ" → "Rapport de sondage", "Rapport
RLQ - Pause café" → "Rapport - Pause café", etc.), le groupe
"Amélioration continue (RLQ)" → "Amélioration continue", les titres de
page du rapport HTML/PDF généré, les noms de fichiers téléchargés
(`RapportSondage-RLQ-...` → `RapportSondage-...`), le guide utilisateur
HTML. CONSERVÉ intentionnellement : les champs `author`/`maintainer`/
`website` du manifeste et le pied de page du guide (attribution
d'auteur normale pour un module open source, distincte de l'acronyme
technique affiché dans l'interface). Une seule occurrence de "RLQ"
subsiste dans le code, un commentaire de docstring interne
(`survey_survey.py`) jamais affiché à l'utilisateur - laissée telle
quelle.

## -49. Correctif bloquant au chargement - `<tree>` renommé `<list>` (v1.74.0)

**Erreur rapportée** (journal de démarrage réel de l'utilisateur, la
première confirmation en conditions réelles depuis l'écriture de ce
module) : `L'élément '<xpath expr="//tree">' ne peut être localisé dans
la vue parente`, sur `views/event_ticket_survey_views.xml`, empêchant le
chargement du module entier. Cause : Odoo a renommé la balise racine des
vues liste de `<tree>` à `<list>` à partir de la version 17 - non
appliqué par erreur dans la vue ajoutée en v1.73.0 (écrite sans accès à
une instance pour le vérifier). Corrigé : `//tree` → `//list`.

**Point confirmé au passage** : le journal de démarrage montre que la
vue parente ciblée
(`event.event_event_ticket_view_tree_from_event`) existe bel et bien sur
cette instance (`view.parent': ir.ui.view(623,)` dans le contexte
d'erreur) - seule sa balise racine différait de l'hypothèse initiale.
Ce point, jusqu'ici listé comme "à vérifier" dans l'entrée -48
ci-dessous, est donc réglé.

**CONFIRMÉ EN PLUS, cette fois par consultation directe du code source
public d'Odoo 18 CE (github.com/odoo/odoo) :**
  - `event_ticket_id` est bien le nom du champ Many2one sur
    `event.registration` pointant vers `event.event.ticket` (confirmé
    par la présence de `self.event_ticket_id.name` /
    `self.event_ticket_id.color` dans le code source réel du module
    `event`) - le champ calculé `rlq_lien_sondage_billet` ajouté en
    v1.73.0 utilise déjà ce nom exact, aucune correction nécessaire.
  - La vue `event.event_event_ticket_view_tree_from_event` est une vue
    standard actuellement maintenue par l'équipe Odoo (modifiée dans une
    tâche de développement de janvier 2025 pour y ajouter un champ,
    exactement le même genre d'opération que la nôtre) - confirme,
    indépendamment du journal de démarrage de l'utilisateur ci-dessus,
    qu'il s'agit bien du bon identifiant de vue à cibler.
  - Racine `<list>` (pas `<tree>`) confirmée par la documentation
    officielle Odoo (renommage à partir de la version 17).

Les deux points de l'entrée -48 encore marqués "non vérifiable sans
accès à une instance" sont donc désormais résolus - sans changement de
code additionnel, la version 1.73.0 utilisait déjà les bons noms.

## -48. Batch de 7 demandes - sondage par type de billet, liste consolidée des actions de suivi, "Ce qui a bougé" en %, date d'événement manquante, libellé filtre (v1.73.0)

**[1] Sondage différent par type de billet.** Nouveau module dépendant
ajouté : `event` (auparavant seulement une dépendance OPTIONNELLE,
détectée à l'exécution - voir `event_dispo` dans le wizard, qui reste en
place pour le RAPPORT lui-même). Nouveau champ `rlq_survey_id` sur
`event.event.ticket` (le type de billet), et nouveau champ calculé
`rlq_lien_sondage_billet` sur `event.registration` (lien public vers ce
sondage), à insérer dans un modèle de courriel de confirmation
d'inscription via `${object.rlq_lien_sondage_billet}`. NON VÉRIFIABLE
SANS INSTANCE :
  - l'existence du champ `event_ticket_id` sur `event.registration` sous
    ce nom exact (nom standard depuis plusieurs versions, mais non
    confirmé sur cette instance ERPLibre) ;
  - l'existence de la vue `event.event_event_ticket_view_tree_from_event`
    ciblée par notre xpath pour afficher le nouveau champ dans la liste
    des billets - si elle n'existe pas sous ce nom, le champ reste
    fonctionnel sur le modèle mais n'apparaît pas automatiquement dans
    l'interface (voir la vue elle-même pour la marche à suivre) ;
  - le lien généré (`/survey/start/<id>`) est un lien PUBLIC ANONYME, pas
    un lien à jeton personnalisé - un enregistrement `survey.user_input`
    est créé au moment où la personne clique, pas avant.

**[2] Liste consolidée des actions de suivi.** Nouvelle section dans la
Synthèse (`section_actions_suivi_consolidee()`), listant TOUTES les notes
d'actions de suivi des rencontres incluses dans ce rapport, en plus
(inchangée) de la note affichée sur chaque rencontre individuellement.

**[3] "Ce qui a le plus bougé" en %.** `section_top_mouvements()`
affiche maintenant les valeurs et le delta en % de l'échelle (comme
`section_note_globale()` et `stats_pourcentage_html()` ailleurs dans ce
module), plutôt qu'en points bruts sur 5.

**[4] Date d'événement manquante dans "Événements inscrits".** Avant :
une inscription dont l'événement lié n'avait pas de `date_begin` était
silencieusement OMISE de la liste des dates affichées, alors que le
total "Événements inscrits" la comptait quand même (décompte
incohérent). Corrigé : affiche maintenant "date non disponible dans ce
rapport (nom de l'événement)" en texte simple, sans lien - aucune
tentative de trouver cette date ailleurs (site web, calendrier
externe...), donc rien qui ouvre une page nécessitant une connexion
Internet depuis un rapport déjà exporté en HTML/PDF.

**[5] Vérifié, déjà fait.** Les messages "X point de % sous la moyenne
des N rencontre(s) précédente(s)" (`section_note_globale()`) étaient
déjà exprimés en % depuis la v1.72.0 - seul le commentaire de la
fonction citait encore un ancien exemple en points bruts, corrigé pour
éviter la confusion.

**[6] Libellé du filtre.** "Participants ayant débuté ou terminé
(minimum)" renommé "Minimum ayant débuté ou terminé?" (champ
`filtre_participants_min`).

**Garde-fous et cas limites traités :**
- La liste consolidée [2] ne reprend QUE les rencontres ayant une note
  non vide (même filtre que la note par rencontre) - pas d'encadré vide.
- Le texte de repli [4] reste local (nom de l'événement déjà en mémoire,
  aucune requête réseau) - conforme à la demande de ne "pas sortir sur
  Internet".
- `rlq_lien_sondage_billet` [1] retourne `False` (vide) si le type de
  billet n'a pas de sondage assigné - le champ ne s'affiche simplement
  pas dans le courriel plutôt que de générer un lien cassé.

**Vérifications effectuées :** suite `test_report_builder.py` mise à
jour (nouveaux tests pour le format en % de `section_top_mouvements()`
et pour `section_actions_suivi_consolidee()`) et repassée à 100% ; test
manuel de la formule de conversion sur les bornes (1 -> 0%, 5 -> 100%).
Syntaxe Python et XML validées. La nouvelle dépendance module `event`
et la nouvelle vue [1] n'ont pas pu être testées sur une instance réelle
(voir points non vérifiables ci-dessus).

**Action requise :** mettre à jour le module et redémarrer le service.
Comme `event` devient une dépendance obligatoire, vérifiez que le
module Événements est bien installé avant la mise à jour (c'est déjà le
cas sur votre instance de production d'après les données déjà utilisées
par ce rapport). Pour le point [1], configurez le sondage de chaque
type de billet (fiche du billet, nouveau champ "Sondage pour ce type de
billet"), puis ajoutez `${object.rlq_lien_sondage_billet}` au modèle de
courriel de confirmation d'inscription (Événements > votre événement >
onglet Communication).



**[6] Champ "Actions de suivi" introuvable.** La vue héritée du
formulaire natif du Sondage (v1.71.0) dépendait d'un xpath dont la
structure exacte n'a pas pu être vérifiée sans accès à une instance -
possiblement ajoutée mais mal placée (après un bloc d'onglets,
peu visible). Corrigé en ajoutant un accès GARANTI et INDÉPENDANT :
nouveau menu "Actions de suivi (amélioration continue)" sous Sondage,
ouvrant une liste dédiée entièrement définie par nous-mêmes (aucune
dépendance à la structure d'une vue externe). La vue héritée reste en
place comme bonus si elle fonctionne, mais n'est plus le seul moyen
d'accès.

**[1] Résumé des paramètres incomplet.** Ajouté : filtre présentateur,
anonymisation, personnes n'ayant pas répondu, section "À surveiller",
format de sortie - tous manquaient auparavant.

**[4] Lien "Aide" pas souligné malgré le correctif de la v1.70.0.**
Hypothèse : la classe `btn-link` d'Odoo force `text-decoration:none`
avec une priorité CSS plus forte que notre style en ligne - renforcé
avec `!important`. Non vérifiable sans accès à une instance.

**[2] Couleur des histogrammes.** La barre de REMPLISSAGE elle-même
change maintenant de couleur (nouvelles classes `barre-remplie-vert/
bleu/jaune/rouge` et `evo-barre-vert/bleu/jaune/rouge`), pas seulement
le texte du pourcentage à sa droite comme c'était le cas depuis la
v1.66.0.

**[3] Présentateurs par rencontre.** Nouvelle liste sous "Participants
:" dans chaque section de rencontre, avec des liens vers la ligne
spécifique du présentateur dans "Appréciation des présentateurs"
(ancre unique `id="presentateur-{slug}"` ajoutée à chaque ligne du
tableau).

**[5] Statistiques en pourcentage, avec P95 partout.** Nouvelle
fonction centralisée `stats_pourcentage_html()` (avec un paramètre
`texte_brut` pour les tooltips via `data-rlq-tip`, qui n'interprètent
jamais le HTML qu'ils contiendraient) - remplace les calculs de
statistiques bruts dans `section_tendance_question()` (tooltip ET
étiquette de valeur des barres), `section_note_globale()` (stats ET
texte de comparaison historique, maintenant en points de %), et
`section_appreciation_presentateurs()` (P95 qui manquait ici).
`section_matrice()` (avait déjà P95, mais en valeurs brutes)
également alignée pour la cohérence.

**INCIDENT DE PROCESSUS** : une modification de `section_note_globale()`
a été appliquée avec une parenthèse orpheline (erreur de ma part lors
d'un remplacement partiel), cassant la syntaxe du fichier - détecté et
corrigé au TOUR SUIVANT (avant toute livraison, aucune version cassée
n'a été livrée) grâce à l'habitude de toujours revérifier la syntaxe
après un remplacement, même en fin de tour sous contrainte de temps.



**1. Boucle PDCA fermée - actions de suivi persistantes.** Nouveau
champ `rlq_actions_suivi` (Text) sur `survey.survey` - PAS calculé,
rempli manuellement depuis le formulaire natif du sondage (nouvelle
vue héritée `view_survey_survey_form_rlq_actions`, xpath sur `//sheet`
plutôt qu'un élément plus spécifique - **INCERTITUDE NON VÉRIFIÉE** :
`ref="survey.survey_survey_view_form"` est le nom de vue standard que
je connais pour Odoo 18, mais je n'ai aucun moyen de le confirmer sans
accès à une instance - si l'installation échoue avec une erreur
mentionnant cet ID, c'est probablement la cause). Le rapport rappelle
maintenant ces notes (si présentes) juste après la Note globale de
chaque rencontre - ferme la boucle Plan-Do-Check-Act, qui n'existait
pas avant (le rapport ne faisait que diagnostiquer, jamais suivre les
actions prises).

**2. Détection de dérive (tendance soutenue, pas un point isolé).**
Nouveau paramètre `detecter_derive` sur `section_tendance_question()`
- détecte 3 rencontres consécutives strictement croissantes ou
décroissantes (peu importe si chaque point individuel reste dans les
limites de contrôle) - un signal SPC différent et complémentaire du
point isolé hors écart-type. Activé sur la tendance de la Note
globale.

**3. Comparaison par catégorie de rencontre.** La moyenne de référence
(comparaison à la moyenne mobile, ajoutée en v1.68.0) ne compare
maintenant une rencontre qu'aux rencontres PRÉCÉDENTES DE LA MÊME
CATÉGORIE (Premier mardi/Pause café/Portes ouvertes/Autre, réutilise
les méthodes `_survey_ids_XXX()` existantes) - une Portes ouvertes
chronologiquement entre deux Pause café n'influence plus leur
comparaison mutuelle. Nouveau test vérifiant ce comportement avec 3
rencontres construites spécifiquement pour ce cas.



**Nouveau filtre par présentateur.** Nouveau champ `filtre_presentateur`
(Selection dynamique, `_get_presentateurs_disponibles()`) - liste tous
les présentateurs reconnus (voir `rb.extraire_presentateur`) dans TOUS
les sondages de la base, pas seulement ceux déjà sélectionnés. Choisir
un nom (via `_onchange_filtre_presentateur()`) remplace la sélection
de sondages par UNIQUEMENT les rencontres où ce présentateur a donné
au moins une présentation - permet d'envoyer un rapport ciblé à un
bénévole présentateur, sans devoir chercher manuellement dans quelles
rencontres il a présenté. Réutilise `self._get_rows(question)` (déjà
existante, gère les variations de nom de champ entre versions d'Odoo)
plutôt que d'accéder directement à `matrix_row_ids`.

**Seuils de couleur des histogrammes - VRAIE INCOHÉRENCE TROUVÉE ET
CORRIGÉE.** `_classe_pourcentage()` (barres horizontales) utilisait
des seuils COMPLÈTEMENT DIFFÉRENTS (90/70/60%, avec une catégorie
"orange" inexistante ailleurs) de `colorer_par_valeur()` (2/4/5 sur
échelle 1-5, utilisée pour les chiffres) - un vrai défaut de
cohérence visuelle dans le rapport, pas juste une préférence
esthétique. Alignés exactement : <=40% (valeur <=2) rouge, <80%
(valeur 3) jaune, <100% (valeur 4) bleu, 100% (valeur 5) vert.
Nouvelle fonction `_classe_couleur_1a5()` pour les histogrammes
VERTICAUX (barres pleines sans texte, ont besoin d'une classe de
couleur de FOND plutôt que de texte) - appliquée dans
`section_tendance_question()`. `section_evolution()` et
`section_taux_reponse()` (comptes et pourcentages d'engagement, pas
des notes) restent avec leur couleur fixe, cette échelle de couleur
n'ayant pas de sens pour ces métriques.

**Bouton "Aide" souligné**, pour signaler visuellement que c'est un
lien plutôt qu'un bouton d'action classique.



**Horodatage UTC dans le nom des fichiers - CORRIGÉ.** Les trois
méthodes de téléchargement (HTML, PDF, Excel) utilisaient
`fields.Datetime.now().strftime(...)` directement - `fields.Datetime.now()`
retourne l'heure UTC (convention Odoo), jamais convertie en heure
locale contrairement à ce qui est fait ailleurs dans le module (ex. le
bandeau de génération du rapport, `fields.Datetime.context_timestamp()`).
Corrigé aux trois endroits avec le même mécanisme de conversion déjà
utilisé et éprouvé ailleurs.

**"Niveau de connaissance ?" exclu de "Ce qui a le plus bougé".**
Signalé : cette question n'est plus posée dans les sondages récents,
et son apparition dans ce résumé n'a pas de sens (une auto-évaluation,
pas une question de satisfaction). Réutilisé `MOTS_CLES_QUESTIONS_AUTO_EVALUATION`
(déjà utilisée pour exclure cette même question de "À surveiller"),
plutôt que d'ajouter une exclusion ad hoc distincte.



Suite à une question ouverte de l'utilisateur ("as-tu d'autres
améliorations utiles ?"), 7 pistes ont été proposées puis toutes
implémentées sur demande :

1. **Limites de contrôle sur la tendance** (`limites_controle=True`
   dans `section_tendance_question()`) - marque distinctement (bordure)
   toute rencontre s'écartant de plus d'un écart-type de la moyenne
   globale de toutes les rencontres affichées. Activé sur la tendance
   de la Note globale.
2. **Comparaison à la moyenne historique** (`section_note_globale()`,
   nouveaux paramètres `moyenne_reference`/`nb_reference`) - moyenne
   mobile des 6 rencontres précédentes (chronologiquement, PAS les 6
   premières de la liste qui est triée du plus récent au plus ancien -
   piège évité en utilisant les index SUIVANTS dans `dates_rencontres`).
3. **"Ce qui a le plus bougé"** (`section_top_mouvements()`) - compare
   la moyenne des deux dernières rencontres pour chaque question,
   affiche les 3 plus gros changements en tête de la Synthèse.
4. **Taux de réponse en tendance distincte** (`section_taux_reponse()`)
   - terminé/inscrit en %, séparé de la Note globale (satisfaction) -
   protégé contre une division par zéro si une rencontre n'a aucun
   inscrit.
5. **Tendance par présentateur** (indicateur ▲▼▬ dans
   `section_appreciation_presentateurs()`) - compare la première et la
   dernière présentation DATÉES d'un présentateur ayant plusieurs
   présentations ; aucun indicateur si les dates sont inconnues ou s'il
   n'y a qu'une seule présentation.
6. **Note globale ajoutée à l'export Excel** (`action_export_excel()`)
   - nouvelle feuille dédiée, réutilise `rb.convertir_numerique()`
   plutôt que de dupliquer toute la logique d'extraction des questions
   matricielles du rapport principal (risque de divergence évité).
7. **Commentaires libres reliés aux notes basses** dans "À surveiller"
   - nouvelle méthode `_commentaire_libre_pour(user_input)`, cherche
   une réponse texte libre de LA MÊME personne dans LE MÊME sondage.
   Changement de structure : `alertes_notes_basses` passe de 5 à 6
   éléments par tuple (ajout de `commentaire`) - `section_a_surveiller()`
   et ses tests mis à jour en conséquence.

Aucune de ces 7 fonctionnalités n'a pu être vérifiée visuellement sur
une vraie instance Odoo (comme pour tout ce module) - seule la logique
métier a été testée en isolation (81 tests dans
`test_report_builder.py`, plus de nouveaux tests dans `test_wizard.py`
non exécutables ici).



**Exclusion par mot-clé n'est plus un "problème".** Chaque sondage
exclu par `exclude_title_keywords` ajoutait une entrée aux
diagnostics, alimentant le bandeau "N problème(s) rencontré(s)" -
signalé à juste titre : exclure un sondage par mot-clé est un
comportement VOULU par l'utilisateur, pas une erreur. Ce filtre est
déjà visible dans le résumé des paramètres en haut du rapport
(`_resume_parametres()`) - l'information n'est donc pas perdue en
retirant cette entrée des diagnostics.

**Titre du formulaire simplifié.** Reste toujours "Rapport de
sondage", peu importe le sous-menu utilisé pour l'ouvrir - le nom du
sous-menu (`menu_origine`) reste affiché dans le résumé des
paramètres ("Sous-menu utilisé : ...") et utilisé dans le nom de
fichier (si `filtre_titre_predefini` n'est pas déjà défini), seul son
usage dans le titre du formulaire lui-même a été retiré.
`action_menu_tous()` (le sous-menu "Tous les sondages") règle
maintenant aussi `filtre_titre_predefini` sur "tous" par défaut, pour
que le filtre rapide reflète correctement la sélection faite par ce
raccourci.



**Alignement de l'en-tête - vraie cause trouvée.** `justify-content:
space-between` (v1.65.0) n'avait aucun effet parce que `.oe_title` ne
prend pas toute la largeur du formulaire par défaut - sans
`width:100%` explicite, les éléments flex restent groupés à leur
propre largeur naturelle, sans espace où se répartir. Ajouté.

**Notification "Générer" - HTML confirmé non interprété.** Le
commentaire de `chiffres_gras()` (déjà présent dans le code) documentait
qu'une tentative précédente avec des balises `<strong>` dans cette même
notification avait échoué (affichées en texte brut échappé) - `<br/>`
aurait donc échoué pour la même raison. Utilisé le caractère Unicode
U+2028 (LINE SEPARATOR) à la place - un vrai saut de ligne selon la
spec Unicode/CSS, respecté même en texte brut, contrairement à "\n"
qui est traité comme un espace collapsible par défaut en HTML.
Agrandir la FENÊTRE elle-même n'est pas possible depuis notre code -
sa taille est gérée par le CSS propre au composant de notification
d'Odoo, hors de notre contrôle.

**Diagnostic "0/N réponses retenues" rendu conditionnel.** Supprimé
entièrement (pas seulement adouci) quand `filtre_participants_min >= 1`
(sa valeur par défaut) - affiché seulement si explicitement mis à 0.
Note : la valeur par défaut du champ étant 1, ce diagnostic ne
s'affichera plus du tout pour la plupart des utilisateurs à moins
qu'ils ne changent volontairement ce paramètre.

**Moyenne manquante ajoutée** dans la cellule de statistiques
d'"Appréciation des présentateurs" (Min/Max/É-T sans Moy - oubli de
ma part lors de la construction initiale).

**Notes de "À surveiller" formatées sans décimale** (`:g` plutôt que
l'affichage brut) - les votes sont des entiers de 1 à 5.

**"Note globale de cette rencontre" réorganisée** : histogramme et
statistiques désormais côte à côte (flex) plutôt qu'empilés
verticalement, pour réduire l'espace vertical utilisé.

**extraire_presentateur() supporte maintenant les parenthèses en plus
des crochets** - `[\\[\\(]...[\\]\\)]` plutôt qu'uniquement `\\[...\\]` -
les deux formats sont utilisés selon l'utilisateur.



**action_test_survey() CONFIRMÉ FONCTIONNEL** par l'utilisateur - le
bandeau "Ceci est une entrée d'un sondage test." apparaît maintenant.
Libellé changé de "ouvrir" à "Tester sondage" en conséquence. Une des
rares fois où une piste technique fournie par l'utilisateur (repérée
en mode debug d'Odoo) a mené directement à une solution qui fonctionne
du premier coup.

**En-tête non aligné à droite.** `justify-content:space-between`
ajouté au conteneur flex du titre - le `gap` seul ne pousse pas les
éléments aux extrémités, il ne fait qu'espacer des éléments déjà
groupés à gauche. Cet ajout était manquant dans le correctif de la
v1.63.0.

**Liens "Événements inscrits" toujours externes malgré le correctif
par ID (v1.62.0).** Cause exacte encore incertaine - possiblement que
`_lien_evenement()` ne trouve pas d'événement pour certaines
rencontres (aucune relation directe en base ET sa propre recherche par
date ne trouve rien), alors qu'un event.registration existe bel et
bien à cette date. Ajouté un SECOND mécanisme de repli, par
comparaison de DATE (comme la toute première tentative, v1.60.0) - EN
PLUS de la comparaison par ID (v1.62.0), pas à sa place. Les deux
mécanismes sont maintenant essayés (ID d'abord, date ensuite) avant de
retomber sur le lien externe. Non garanti de résoudre le problème,
faute de pouvoir diagnostiquer avec certitude sans accès à l'instance.

**Confirmation avant fermeture via Esc - DÉCLINÉ, cohérent avec la
décision précédente (section -34).** Un dialogue de confirmation
avant fermeture (peu importe le déclencheur - clic sur X, bouton
Fermer, ou touche Esc) nécessiterait d'intercepter le cycle de vie du
modal en JavaScript. Rien n'a changé depuis la décision précédente
(section -34) qui rendrait ce risque plus acceptable - au contraire,
l'incident confirmé de la section -33 (un vrai plantage causé par une
tentative JS/CSS pourtant plus simple) renforce cette prudence. Non
implémenté.



Piste concrète fournie par l'utilisateur (mode debug d'Odoo) : le
bouton natif "Test" du formulaire Sondage indique appeler une action
nommée `action_test_survey`. `_lien_test_sondage()` tente maintenant
d'appeler CETTE MÊME méthode directement sur `survey.survey` (si elle
existe), extrayant l'url de l'action retournée (attendue de type
`ir.actions.act_url` avec une clé `url`) - plutôt que de retomber
d'emblée sur `get_start_url()`. Repli sur `get_start_url()` conservé
si la méthode n'existe pas, échoue, ou ne retourne pas la structure
attendue - AUCUN risque de faire échouer tout le rapport si mon
hypothèse sur la structure de retour est incorrecte.

**Libellé du lien volontairement gardé "ouvrir" plutôt que "tester"** :
je ne peux pas confirmer avec certitude, sans accès à une instance,
que cette méthode fonctionne comme je le suppose - si l'utilisateur
confirme que le nouveau lien affiche bien le bandeau de test, le
libellé pourra être changé pour "tester" en toute confiance.

Test correspondant réécrit pour rester souple sur la forme exacte de
l'url retournée (`test_lien_test_sondage_retourne_une_url_valide`) -
je ne connais pas la structure de retour réelle d'action_test_survey()
sur toutes les instances.



Nouvel élément fourni par l'utilisateur (deux URL réelles, même jeton
de sondage, jetons de réponse différents) - ÉLIMINE l'hypothèse d'une
session anonyme/déconnectée (confirmé connecté normalement dans les
deux cas). Conclusion : la différence de comportement (bandeau de test
affiché ou non) dépend de logique interne au contrôleur du module
Sondage d'Odoo lui-même (peut-être liée à l'historique des réponses
précédentes de cet utilisateur pour CE sondage précis, ou à d'autres
heuristiques non documentées) - PAS de la façon dont notre lien est
construit. Le bouton natif "Test" du backend reste fiable parce qu'il
appelle une action serveur DÉDIÉE qui force explicitement
test_entry=True, contrairement au point d'entrée générique
`/survey/start/<jeton>` (utilisé par `get_start_url()`, donc par notre
lien "ouvrir"), qui ne passe pas par ce même mécanisme explicite.

AUCUN changement de code pour ce point - confirmé hors de portée de
notre module. Recommandation inchangée : utiliser le bouton natif
"Test" du backend pour un mode test fiable.



**En-tête du formulaire.** La version du module (`debug_info`) passe
de `Html` à `Char` (plus de risque de plantage lié au widget Html,
voir l'incident de la section -33, et le contenu n'a plus besoin de
mise en forme) - placée maintenant à droite du titre "Rapport de
sondage", sur la même ligne (`display:flex`), en texte normal (ni
gras ni plus petit que la normale, juste `text-muted` + taille
légèrement réduite). Format simplifié : `rlq_survey_report vX.Y.Z
(AAAA-MM-JJ HH:MM FUSEAU)`, sans plus le préfixe "installé/mis à jour
le".

**Appréciation des présentateurs - redondance retirée.** Le résumé
"Moyenne combinée de N présentations :" avec son propre histogramme,
ajouté en v1.62.0, faisait doublon avec la colonne "Note moyenne"
déjà affichée sur la ligne principale du présentateur (qui EST déjà
cette moyenne combinée) - retiré. Les statistiques PAR présentation
individuelle (ajoutées au même moment) restent, puisqu'elles
n'existaient nulle part ailleurs.

## -36. Correspondance par ID plutôt que par date pour les liens internes, stats individuelles par présentation (v1.62.0)

**Liens "Événements inscrits" toujours externes - vraie cause
trouvée.** La comparaison par date (v1.60.0) échouait probablement
parce que la date d'un événement (`date_begin`) ne correspond pas
forcément EXACTEMENT à la date extraite du titre du sondage
(`date_titre_extraite`) utilisée pour ancrer la section de la
rencontre - deux représentations de la "même" date logique, mais avec
des sources différentes, pouvant légèrement diverger. Corrigé en
comparant par IDENTIFIANT D'ÉVÉNEMENT plutôt que par date - réutilise
`_lien_evenement()`, déjà appelé une fois par rencontre pour associer
un sondage à SON événement, plutôt qu'une nouvelle comparaison de
dates. Mécanisme étendu aussi aux dates de "Sondages remplis"
(demandé), comparées par ID DE SONDAGE cette fois (plus direct, pas
besoin de passer par un événement intermédiaire).

**Stats individuelles par présentation.** Quand un présentateur a
plus d'une présentation, chacune affiche maintenant sa propre moyenne
et son nombre de réponses dans la liste dépliable, en plus d'un résumé
"Moyenne combinée de N présentations" - pour une seule présentation,
ce détail serait redondant avec la ligne principale et n'est donc pas
affiché.

**Champs déplacés par erreur remis en place.** Seul "Format de
sortie" devait être déplacé vers la colonne de droite (v1.61.0) -
"À partir du"/"Jusqu'au" ont été déplacés par erreur en même temps,
et sont remis dans la colonne de gauche.



**Preuve concrète obtenue** : l'utilisateur a fourni une trace
d'erreur JavaScript complète (`OwlError` dans
`HtmlViewer.retargetLinks`, `TypeError: Cannot read properties of
null (reading 'querySelectorAll')`). Le champ `apercu_solidite_mot_de_passe`
était passé à `fields.Html` en v1.60.0 pour supporter un tooltip CSS
autonome - mais le widget Html d'Odoo (`HtmlViewer`) tente un
post-traitement de son contenu (probablement pour retargeter les
liens `<a>` vers de nouveaux onglets) qui PLANTE face à notre contenu
(un `<style>` suivi d'un `<span>`, une structure inhabituelle pour ce
widget, normalement utilisé pour du contenu WYSIWYG).

**Corrigé définitivement** : le champ redevient un `Char` simple.
Après DEUX échecs sur DEUX mécanismes différents pour révéler
temporairement le mot de passe (title= natif : ne fonctionnait pas ;
widget Html + CSS : plantait Odoo), aucune troisième tentative n'est
prévue. Le champ confirme désormais seulement que les deux saisies
correspondent et respectent les critères ("✓ Les deux mots de passe
correspondent et sont suffisamment solides"), SANS JAMAIS afficher le
mot de passe sous quelque forme que ce soit - la correspondance exacte
de deux champs masqués saisis séparément est déjà, en pratique, une
garantie suffisante contre une erreur de frappe.

**Leçon retenue** : les widgets Odoo destinés à un usage précis (ici,
Html/HtmlViewer, conçu pour du contenu WYSIWYG structuré) peuvent
avoir un comportement fragile face à un contenu qui sort de cet usage
prévu (ici, un fragment HTML minimal avec CSS intégré) - une raison de
plus de privilégier des mécanismes simples (texte brut) quand la
fonctionnalité recherchée n'est pas essentielle.

## -34. Confirmation avant de quitter le rapport - décliné, JavaScript requis (v1.61.0)

Confirmé par l'utilisateur : demande d'un dialogue "Voulez-vous
vraiment quitter sans télécharger ?" avant la fermeture du wizard.
DÉCLINÉ : Odoo ne considère pas ce wizard comme "non sauvegardé" une
fois `action_generate()` exécuté (le enregistrement TransientModel EST
écrit en base) - son mécanisme natif d'avertissement pour changements
non sauvegardés ne s'appliquerait donc pas ici. Implémenter cela
demanderait d'intercepter manuellement la fermeture du modal en
JavaScript - et l'incident de la section -33 ci-dessus (un plantage
RÉEL et CONFIRMÉ causé par une tentative relativement simple
d'interagir avec le cadre d'affichage d'Odoo) illustre concrètement le
risque d'aller plus loin dans cette direction. Non implémenté.

## -35. Champs déplacés de la colonne gauche vers la droite (v1.61.0)

Signalé : trop de champs dans la colonne de gauche. `output_format`,
`date_from` et `date_to` déplacés vers le haut de la colonne de
droite, au-dessus des cases à cocher - la colonne de gauche ne
contient plus que les champs directement liés au filtre rapide et aux
exclusions.



**Liens "Liste des participants"/"À surveiller"/"Appréciation des
présentateurs" pointant hors du rapport - CORRIGÉ.** Bogue confirmé :
la navigation ajoutée en v1.57.0 utilisait des `<a href="#...">`
BRUTS plutôt que `rb.lien_ancre()` (le mécanisme existant, DÉJÀ
DOCUMENTÉ dans le code, gérant justement ce problème précis - un
`href='#id'` brut est intercepté par le routeur d'Odoo dans le widget
Html plutôt que de faire défiler jusqu'à l'ancre). Une inattention de
ma part : j'ai réintroduit une régression déjà résolue ailleurs dans
le même fichier, faute d'avoir réutilisé le mécanisme existant.
Corrigé en utilisant `lien_ancre()`.

**Dates des "Événements inscrits" pointant hors du rapport.** Ces
liens visaient délibérément la fiche de configuration de l'événement
dans le backend Odoo (comme les liens de configuration de sondage) -
mais l'utilisateur veut qu'ils pointent DANS le rapport quand la date
correspond à une rencontre incluse. `liste_dates_avec_liens()` accepte
maintenant un url préfixé par "#" comme marqueur d'ancre interne (géré
via `lien_ancre()`) plutôt qu'un lien externe classique - le wizard
compare la date de chaque événement à `dates_rencontres` (l'ensemble
des dates des rencontres incluses dans CE rapport, pas "tous temps")
pour décider laquelle des deux formes utiliser.

**"0/N réponses retenues" présenté comme un problème.** Signalé :
avec `filtre_participants_min` réglé pour n'inclure que des sondages
ayant au moins N réponses (basé sur rlq_answer_done_count/
in_progress_count, des compteurs globaux), un sondage peut quand même
finir avec 0 réponse RETENUE une fois `_user_inputs()` appliqué -
CETTE méthode filtre EN PLUS par date_from/date_to et les exclusions
(participant, étiquette), des critères que `filtre_participants_min`
NE VÉRIFIE PAS lors de la sélection initiale. Les deux mécanismes ne
sont donc PAS parfaitement réconciliés (amélioration possible, non
faite ici par prudence face à la complexité et au risque). Corrigé
partiellement : le bandeau devient neutre (bleu, "ℹ") plutôt qu'une
alarme rouge ("⚠ problème") lorsque TOUS les diagnostics sont de ce
type précis - une conséquence probable des propres filtres de
l'utilisateur plutôt qu'une vraie erreur technique.

**Tooltip du mot de passe - CHANGEMENT DE MÉCANISME (2e tentative).**
Le tooltip via l'attribut HTML natif `title=` (v1.59.0) a été signalé
NE PAS FONCTIONNER (ni au survol, ni au clic) - la cause exacte reste
incertaine (le widget Html d'Odoo pourrait traiter cet attribut
différemment de ce qui était attendu). Remplacé par un mécanisme CSS
AUTONOME : un `<style>` intégré DIRECTEMENT dans le contenu du champ
lui-même (donc indépendant de toute feuille de style externe),
utilisant `::after` déclenché par `:hover` (survol) ET `:focus` (clic,
via `tabindex="0"`) - un mécanisme différent du précédent essai, pas
seulement une nouvelle tentative de la même chose. Non vérifié en
conditions réelles, faute d'accès à une instance.

**Point non traité, besoin de clarification : confirmation avant de
quitter le rapport.** L'utilisateur signale que "sortir du rapport"
ne fonctionne pas actuellement, et suggère qu'une confirmation
devrait être demandée. Ambigu tel que formulé - est-ce un bogue (le
bouton Fermer ne répond pas ?) ou une demande de fonctionnalité (un
dialogue de confirmation avant fermeture, qui nécessiterait du
JavaScript pour intercepter la fermeture du modal) ? Clarification
demandée avant d'agir plutôt que deviner.



Deux tentatives précédentes (v1.40.0, cherchant `value_char_box` sur la
ligne du choix) avaient échoué parce que la prémisse était fausse : le
commentaire "Autre, précisez" est enregistré par Odoo comme une **ligne
séparée** du choix sélectionné, sans `suggested_answer_id`. Confirmé
par la documentation officielle d'Odoo (comportement "Comment is an
answer" du module Sondage) et par un correctif Odoo récent (PR
#165853) mentionnant explicitement "2 lignes distinctes : la réponse à
choix simple et le commentaire". Le code a été corrigé en conséquence -
**mais n'a pas pu être vérifié avec de vraies données Odoo**, faute
d'accès à une instance. Si la précision n'apparaît toujours pas après
cette version, le nom exact du champ contenant le texte pourrait
différer (`value_char_box` vs `value_text_box` selon le type de
widget configuré pour le champ commentaire) - vérifiable en mode
développeur sur une ligne de réponse contenant un commentaire "Autre"
connu.

## -16. Pages PDF presque vides : correctif probable, non vérifié visuellement (v1.42.0)

Diagnostic : les nouveaux graphiques "Évolution"/"Tendance" (v1.39.0/
v1.40.0) utilisent `display: flex`, une mise en page dont wkhtmltopdf a
des bogues déjà rencontrés (histogrammes, corrigés en v1.31.0).
Retirés du PDF en conséquence. **Si des pages restent presque vides
après cette version**, la cause serait ailleurs - pistes à explorer
dans l'ordre : (1) l'interaction entre le nouveau format 11x17
portrait (v1.41.0, plus haut que large) et les sauts de page forcés
par rencontre ET par participant (les deux actifs par défaut
maintenant) - un contenu modeste sur une page de 17 pouces de haut
peut sembler "presque vide" même s'il n'est pas tronqué ; (2) la liste
de participants en colonnes CSS (`columns: 4`, section "table des
matières") - également un type de mise en page avec des bogues connus
sur wkhtmltopdf, non modifiée dans cette version faute de certitude
suffisante sur son implication réelle.

## -31. Espace fixe à gauche de la liste des sondages (corrigé) ; mot de passe affiché en tooltip natif plutôt qu'en texte permanent (v1.59.0)

**Espace fixe à gauche, indépendant de la largeur de fenêtre.** Cause
trouvée : le champ `survey_ids` n'avait pas `nolabel="1"` - Odoo
réserve alors une colonne de largeur FIXE pour son étiquette dans la
grille du `<group>`, peu importe la largeur de la fenêtre (d'où le
symptôme "même en agrandissant, l'espace est toujours là"). Corrigé
avec `nolabel="1"` sur le champ, et un `<div>` simple (plutôt qu'un
`<label>`, pour éviter tout comportement de grille similaire) affichant
le même texte au-dessus, en pleine largeur.

**Mot de passe affiché seulement en tooltip.** Après plusieurs
demandes infructueuses d'un délai d'affichage automatique (nécessitant
un minuteur JavaScript, jamais ajouté dans ce projet), l'utilisateur a
proposé une alternative BEAUCOUP PLUS SIMPLE : un tooltip plutôt qu'un
texte permanent. `apercu_solidite_mot_de_passe` est passé de `Char` à
`Html` (`sanitize=False`), et affiche maintenant le mot de passe
confirmé dans l'attribut HTML natif `title=` d'un `<span>` - un
tooltip du NAVIGATEUR LUI-MÊME (pas notre CSS personnalisé du rapport,
puisque ce formulaire utilise le cadre d'Odoo), visible seulement au
survol, sans aucun JavaScript. Le mot de passe est échappé
(`rb.echapper_attr`) avant d'être placé dans l'attribut, pour éviter
qu'un guillemet dans le mot de passe ne casse la structure HTML -
testé avec un mot de passe contenant explicitement un guillemet.



Confirmé par l'utilisateur : les "scroll-list" visées sont les champs
"Participants à exclure" et "Exclure par étiquette" (widget
many2many_tags, qui ouvre une liste déroulante de suggestions au
clic). `style="max-width:66%;"` ajouté aux deux - réduits aux deux
tiers de leur largeur, comme demandé au départ.



**"scroll-list" (point 1) - ma première interprétation était erronée.**
L'utilisateur a précisé qu'il s'agissait des listes déroulantes pour
les DIFFÉRENTES OPTIONS en bas du formulaire (pas la liste des
sondages, sur laquelle j'avais appliqué un correctif par erreur en
v1.56.0 - annulé). Je n'ai pas encore identifié avec certitude
QUEL élément précis est visé (many2many_tags ? le select de filtre
rapide ? autre chose ?) - à clarifier avant d'appliquer un nouveau
correctif, pour éviter une troisième tentative erronée sur ce même
point.

**Accents non anonymisés - CORRIGÉ.** Confirmé : un nom contenant un
accent (ex. "Fabián") peut être représenté en Unicode de deux façons
visuellement identiques mais avec des octets différents (forme
composée NFC vs décomposée NFD) - si le titre de présentation (tapé
séparément, peut-être copié d'une source différente) utilise une
forme différente de celle de la fiche contact, `html.replace()` (une
comparaison exacte) échoue à faire correspondre les deux. Corrigé en
normalisant (forme NFC) le HTML ET chaque nom avant comparaison.
Testé avec un cas reproduisant exactement le scénario (nom en NFC
dans la fiche contact, NFD dans le titre).

**Navigation de sections ajoutée** en tête de la table des matières
(Liste des participants, À surveiller, Appréciation des présentateurs)
- les liens vers des sections conditionnelles ne sont inclus QUE si
cette section aura effectivement du contenu, pour ne jamais pointer
vers une ancre inexistante. Nécessité de déplacer le calcul de
`donnees_presentateurs` plus tôt dans le code (avant la construction
de la table des matières plutôt qu'après) pour savoir si cette
section existera.

**Statistiques complètes ajoutées** (tooltip) sur chaque barre des
graphiques de tendance (Min/Moy/Max/É-T/# réponses par date), incluant
celui de la nouvelle "Note globale" - format demandé reproduit
exactement.



**Bogue "Participant Niltre" - VRAIE CAUSE TROUVÉE.** L'indice de
l'utilisateur (seulement avec l'anonymisation activée) a permis de
confirmer : `_anonymiser_html()` fait un remplacement global de
chaîne (`html.replace(nom, pseudo)`) pour chaque participant - si un
participant a un nom TRÈS COURT (ex. une seule lettre "F", probable
fiche contact incomplète dans Odoo), CE REMPLACEMENT AFFECTE TOUTE
OCCURRENCE DE CETTE LETTRE DANS TOUT LE DOCUMENT, y compris dans
"Filtre" ("Filtre" -> "[Participant N]iltre"). Corrigé avec une garde
de longueur minimale (3 caractères) : un nom trop court n'est plus
anonymisé du tout (reste visible sous son nom réel), avec un
avertissement dans les logs signalant la fiche contact à corriger.
Testé avec un participant nommé exactement "F".

**Nouvelle métrique "Note globale" de chaque rencontre.** Combine les
valeurs de "Organisation et logistique", "Satisfaction globale" et
"Comment avez-vous aimé les présentations" en une moyenne composite
unique par rencontre, affichée en tête de chaque section (avant le
détail des questions individuelles), avec histogramme et statistiques.
Une tendance de cette même métrique à travers toutes les rencontres
est affichée en tête de la Synthèse - LE métrique proposé par
l'utilisateur pour le suivi de l'amélioration continue.
`MOTS_CLES_NOTE_GLOBALE` (dans le wizard) liste les mots-clés
identifiant les 3 questions combinées - ajustable si les titres réels
diffèrent.

**Cases à cocher remises à droite**, avec une largeur personnalisée
(flex 45%/50% plutôt que la grille Odoo par défaut) plutôt qu'en
pleine largeur comme tenté en v1.55.0 - correctif du RETOUR à la
position d'origine demandé par l'utilisateur, tout en conservant la
largeur suffisante pour éviter le retour à la ligne sur 3 lignes.

**Navigation clavier dans le rapport affiché dans Odoo (`tabindex="0"`
ajouté)** : tentative à risque FAIBLE mais SANS GARANTIE - dépend de la
façon dont le widget Html d'Odoo enveloppe notre contenu, hors de notre
contrôle direct. Non vérifiable sans accès à une instance.

**Histogrammes individuels par volet pour "Organisation et
logistique"** : extension du mécanisme déjà utilisé pour "Satisfaction
globale" (nouvelle constante `MOTS_CLES_TENDANCE_PAR_ITEM`).

**Hyperliens ajoutés** : sur les dates de la section "À surveiller",
et sur le titre de chaque présentation dans "Appréciation des
présentateurs" (tooltip de date) + détail des votants sur le chiffre
de réponses (même patron que les autres sections du rapport).

**Barres verticales décimales (item 5)** : le changement de la v1.55.0
(hauteur en pixels, indépendante du type de valeur) devrait déjà
couvrir ce cas - non modifié davantage faute de piste supplémentaire
identifiée. À confirmer avec la v1.56.0 spécifiquement.

**Lien de test (item 7)** : aucun changement - le compromis (retour à
get_start_url(), sans bandeau de test) reste celui documenté en
v1.55.0 après 3 échecs du mécanisme précédent.



**Lien de test du sondage - ABANDON définitif du mécanisme
"test_entry".** Un troisième échec confirmé par l'utilisateur (une
NOUVELLE entrée, jamais réutilisée, toujours en erreur d'accès)
malgré deux correctifs successifs (v1.54.0). Retour à `get_start_url()`
(fiable dans tous les rapports testés) plutôt qu'une quatrième
tentative spéculative. Si un vrai mode test est nécessaire à l'avenir,
recommandé : utiliser le bouton natif "Test" directement dans le
formulaire Sondage du backend Odoo (fonctionne dans le même contexte/
session que celui qui l'utilise, contrairement à un lien partagé dans
un rapport exporté).

**Hauteur des barres verticales - changement de mécanisme (percent →
pixels).** Signalé une seconde fois (aucune différence visible entre
4.0 et 5.0) malgré le changement d'échelle de la v1.54.0 (qui
améliorait l'ÉCART CALCULÉ mais pas nécessairement son RENDU VISUEL).
Diagnostic révisé : un pourcentage sur `.evo-barre` (enfant flex dans
un conteneur `flex-direction:column`) ne se résout pas de façon fiable
dans ce contexte précis - les histogrammes HORIZONTAUX (qui utilisent
`width`, jamais affectés par ce problème) fonctionnaient pourtant
bien, un indice qui aurait dû orienter plus tôt vers une cause CSS
plutôt que vers le calcul lui-même. Passé à une hauteur en PIXELS,
calculée directement en Python (70px max) - élimine le problème de
résolution de pourcentage à la source. Non vérifié visuellement dans
un vrai navigateur, mais le mécanisme (une valeur absolue, indépendante
de toute résolution de pourcentage par le moteur de rendu) est
nettement plus robuste.

**Version du module toujours visible.** Retiré `groups=
"base.group_no_one"`, qui limitait l'affichage au mode développeur.
Intégré au titre du formulaire plutôt que sur sa propre ligne séparée,
réduisant l'espace vertical utilisé.

**Heure UTC retirée partout.** Formulaire (version du module) et
rapport (bandeau de génération) n'affichent plus que l'heure locale.

**Cases à cocher en pleine largeur.** Sorties de la grille en 2
colonnes de `<group>` (qui confinait leurs longs libellés à une
largeur fixe, causant un retour à la ligne sur 3 lignes malgré
beaucoup d'espace inutilisé à droite) - chacune est maintenant un
`<div>` en `display:flex` occupant toute la largeur du formulaire.

**Dates des "Événements inscrits" rendues cliquables**, pointant vers
la fiche de configuration de l'événement correspondant (même patron
que les liens déjà existants vers la configuration d'un sondage).

**Mot de passe révélé pendant un délai fixe (2s puis 3s demandées) -
toujours non implémenté.** Redemandé une seconde fois. Comme documenté
en section -26 : nécessite un minuteur JavaScript, non ajouté pour les
mêmes raisons (JavaScript personnalisé impossible à tester dans cet
environnement). Le mécanisme actuel (affichage permanent jusqu'à
modification d'un des deux champs) reste en place.



Signalé : dans la section "Paramètres utilisés pour ce rapport", le
début de la ligne "Filtre rapide utilisé" affiche un texte corrompu
("Participant 11iltre rapide utilisé : ..."). Recherche approfondie
effectuée dans `_resume_parametres()` et son assemblage dans le
gabarit global (`table_matieres`) - AUCUNE cause trouvée par relecture
du code (structure HTML des `<li>` bien formée, wrapping `<details>`
correct, aucune collision évidente avec le mécanisme d'anonymisation).

**Pour diagnostiquer avec certitude, il faudrait** :
1. Le contexte exact : ce texte apparaît-il à l'écran dans Odoo, dans
   le fichier HTML téléchargé, ou dans le PDF ?
2. Idéalement, le code source HTML brut autour de cette ligne (clic
   droit → Inspecter, ou Afficher le code source de la page) - la
   VERSION RENDUE peut fusionner ou masquer un caractère qui serait
   visible dans le HTML BRUT.
3. Le rapport était-il anonymisé au moment de cette capture ?

Sans cette information, je préfère ne pas proposer de correctif
spéculatif après plusieurs tentatives de diagnostic infructueuses par
la seule relecture du code.

## -26. Mot de passe révélé pour 2 secondes puis effacé (v1.54.0) - non implémenté

Demandé : afficher le mot de passe en clair pendant exactement 2
secondes après validation, puis l'effacer automatiquement. Comme pour
la demande précédente (révéler au clic sur le champ, v1.53.0), ceci
nécessite un minuteur JavaScript (`setTimeout`) - aucun mécanisme Odoo
natif (onchange, champ calculé) ne peut déclencher une action après un
délai fixe sans intervention de l'utilisateur. Non implémenté, pour
les mêmes raisons déjà documentées (JavaScript personnalisé impossible
à tester dans cet environnement). Le mécanisme actuel (affichage
permanent jusqu'à la prochaine modification d'un des deux champs,
depuis la v1.41.0) reste en place et répond au même besoin sous-jacent
(vérifier l'absence d'erreur de frappe), sans le délai automatique
demandé.



**Avertissements au chargement** : suite au retrait d'`external_dependencies`
(v1.52.0), chaque bibliothèque optionnelle absente (pypdf/PyPDF2,
pyzipper, openpyxl) déclenche maintenant un `_logger.warning()` clair
au chargement du module (visible dans les logs du serveur au
démarrage/à la mise à jour), sans jamais faire échouer le chargement -
`_logger` a été déplacé plus haut dans le fichier pour être disponible
à cet endroit. Logique testée en isolation (simulation d'une
bibliothèque absente) - confirmé que l'avertissement s'affiche sans
interrompre le chargement.

**Mot de passe révélable au clic sur le champ** : demandé, mais NON
implémenté. Recherche effectuée : Odoo n'offre aucun widget natif pour
ça - seuls des modules tiers non garantis installés (ex.
"password_eyes_icon") ou du JavaScript personnalisé (widget OWL
étendant CharField) permettraient un vrai bouton "œil" DANS le champ.
Étant donné les difficultés déjà rencontrées dans ce projet avec du
JavaScript non testable dans cet environnement, aucun code n'a été
ajouté pour cette demande précise. Piste suggérée à l'utilisateur :
plusieurs navigateurs modernes (Edge, et dans une certaine mesure
Chrome) affichent NATIVEMENT une icône "œil" sur n'importe quel champ
`type="password"` (ce qu'est déjà le champ mot de passe actuel via
`password="True"`) - à vérifier directement dans le navigateur utilisé
avant d'envisager tout développement supplémentaire. Le mécanisme
actuel (ligne de texte séparée affichant le mot de passe une fois
confirmé et solide, ajoutée en v1.41.0) reste en place et répond au
même besoin de vérification.



La déclaration `external_dependencies` ajoutée en v1.51.0 (suite à la
revue de code externe) a causé un échec CONFIRMÉ en conditions
réelles : `pyzipper` n'étant pas installé sur l'environnement Python
de cette instance, Odoo a **refusé de charger le registre au complet**
(`Failed to initialize database`), pas seulement de bloquer la mise à
jour de ce module - un échec bien plus grave que celui que cette
déclaration visait à prévenir (une erreur d'import tardive au moment
de l'usage réel d'une fonctionnalité optionnelle).

**Corrigé en v1.52.0** : `external_dependencies` retiré du manifeste.
Le code dispose déjà, à l'exécution, d'une gestion propre de l'absence
de chacune de ces bibliothèques (`pypdf`/PyPDF2, `openpyxl`,
`pyzipper`) - un `UserError` clair et actionnable (« installez X via
pip install X ») au moment précis où la fonctionnalité concernée est
utilisée, plutôt qu'un blocage total et immédiat du chargement du
module pour toute l'instance. C'est le bon compromis pour des
dépendances qui ne sont nécessaires qu'à des fonctionnalités
OPTIONNELLES (export PDF/Excel protégés) et non au fonctionnement de
base du module (affichage à l'écran, export HTML).

**Leçon retenue** : une suggestion de revue de code, même
techniquement correcte en apparence, peut avoir des conséquences plus
graves que le problème qu'elle visait à corriger selon le contexte
réel de déploiement - à valider par un test réel avant d'appliquer,
quand c'est possible, plutôt que par le raisonnement seul.



Une revue de code par un outil externe a signalé 9 points. Chacun a
été vérifié contre le code réel (pas pris pour acquis) avant d'agir :

**Corrigés :**
- Fuite d'ancre à l'anonymisation (déjà documentée comme limite
  connue) - `_anonymiser_html()` remplace maintenant aussi le slug
  d'ancre (`personne-jean-dupont` -> `personne-3`), pas seulement le
  texte visible. Testé avec un cas de collision de préfixe (Jean vs
  Jean-Paul) pour confirmer l'absence de corruption croisée.
- Pièces jointes jamais purgées - nouvelle tâche planifiée
  quotidienne (`_cron_purger_pieces_jointes`, voir
  `data/ir_cron_purge.xml`), rétention de 3 jours par défaut.
- Dépendances Python externes non déclarées - `pypdf`, `openpyxl`,
  `pyzipper` ajoutés à `external_dependencies` du manifeste.

**Non corrigés, avec justification :**
- **`sudo()` sur les étiquettes** : la revue propose de restreindre
  aux partenaires du rapport courant, mais l'INTENTION d'origine de
  cette fonctionnalité (depuis v1.14.0) est justement de montrer TOUS
  les membres de la communauté partageant une étiquette, pas
  seulement ceux de ce rapport - appliquer ce correctif casserait la
  fonctionnalité. Si cette instance est multi-société, un filtre
  `company_id` serait le correctif approprié à la vraie
  préoccupation (fuite inter-société) sans casser l'intention -
  reste à confirmer si applicable ici.
- **Mot de passe affiché en clair** : c'est une demande EXPLICITE de
  l'utilisateur (voir plus haut dans ce fichier / CHANGELOG v1.41.0),
  pas un oubli. Décision à l'utilisateur de garder ou non ce
  compromis.
- **N+1 dans `_compute_rlq_stats`** : réel en principe, mais peu
  prioritaire à l'échelle réaliste de ce module (sondages mensuels
  d'un groupe meetup, pas des milliers de réponses). Le remplacement
  SQL proposé par la revue calcule en plus la MAUVAISE métrique
  (l'étendue entre la première et la dernière réponse, pas la durée
  moyenne par personne) - non implémenté.
- **`commit()` dans `_envoyer_notification`** : délibéré et déjà
  documenté en commentaire dans le code lui-même - nécessaire pour
  qu'une notification bus soit visible pendant qu'une transaction est
  encore en cours. Compromis assumé, pas un oubli.
- **Doublon de déclaration de vue** (survey_ids) : doublon réel, mais
  un commentaire déjà présent dans le code explique qu'il a été
  introduit pour contourner un problème réel observé (mauvaises
  colonnes dans la fenêtre "Ajouter une ligne"). Retirer l'un des
  deux mécanismes sans pouvoir tester sur une instance réelle risque
  de réintroduire ce problème - non touché par prudence.
- **Remplacement `lxml` de `retirer_divs_par_prefixe_classe`** :
  le code exact proposé par la revue a été TESTÉ dans cet
  environnement - il perd silencieusement tout texte apparaissant
  avant la première balise HTML (`root.text` n'est jamais capturé par
  la boucle `for child in root` du code proposé). Confirmé par un
  test direct montrant une vraie perte de contenu. L'implémentation
  manuelle existante (déjà testée par 5 tests dédiés) est conservée.



**Bonne nouvelle confirmée par l'utilisateur** : le retour au
mécanisme `display_notification` direct (v1.49.0) pour le cas écran a
réglé le problème - la fenêtre en haut à droite apparaît maintenant
après le clic sur Générer. Le message "avant le clic"
(`apercu_ampleur`) n'a pas été reconfirmé dans ce message - à
revalider si le sujet revient.

**Nouveauté** : "Sondages remplis (total, tous temps)" et "Événements
inscrits", sous chaque participant, affichent maintenant aussi la
LISTE des dates (pas seulement le total), sous forme de texte simple
sous le seuil de 4, ou d'une liste dépliable au-delà - construite par
requêtes groupées (pas une par participant) pour rester performant
avec un grand nombre de participants.



Signalé une TROISIÈME fois : ni la notification bus (v1.37.0-ish), ni
l'onchange (v1.46.0), ni le champ calculé (v1.48.0) ne semblent
s'afficher. Information clé de l'utilisateur : « cela a déjà bien
fonctionné à un moment donné » - ce qui a motivé, pour le message
"après le clic" spécifiquement, un retour au mécanisme `display_
notification` retourné DIRECTEMENT (chaîné via "next" vers le
rechargement) plutôt que le bus - un mécanisme confirmé par un
commentaire retrouvé dans le code lui-même ("confirmé (retour
utilisateur) : la notification d'Odoo affiche le message... déjà
observée à l'écran par le passé").

**Pour le message "avant le clic" (`apercu_ampleur`), qui reste non
confirmé fonctionnel malgré 3 mécanismes différents essayés** :
avant d'essayer un QUATRIÈME mécanisme, **vérifiez d'abord que la
mise à jour du module a bien été prise en compte** - en mode
développeur, la version affichée sous le titre du formulaire
devrait indiquer `18.0.1.49.0` (ou plus récente). Si une version
antérieure s'affiche, la mise à jour elle-même n'a peut-être pas
été complètement appliquée (`-u rlq_survey_report` suivi d'un
redémarrage COMPLET du service, pas juste un rechargement de page) -
ce serait alors la cause réelle, indépendamment de tout mécanisme de
champ.

## -19. Aperçu d'ampleur invisible : onchange remplacé par un champ calculé (v1.48.0)

Signalé : `apercu_ampleur` (v1.46.0, sensé remplacer la notification
bus peu fiable) ne s'affichait ni avant ni après le clic sur Générer -
c'est-à-dire pas du tout. Cause probable : ce champ était basé sur
`@api.onchange`, qui ne se déclenche de façon fiable que sur un
changement de champ fait INTERACTIVEMENT dans le formulaire - or ce
formulaire s'ouvre le plus souvent avec `survey_ids` DÉJÀ REMPLI via
le contexte (`default_survey_ids`, voir `_action_ouvrir_wizard_pour`),
pas par une saisie interactive de l'utilisateur. Un onchange peut ne
pas se déclencher dans ce scénario précis, selon la version d'Odoo et
la structure de la vue.

**Corrigé** : `apercu_ampleur` devient un champ CALCULÉ
(`compute="_compute_apercu_ampleur"`, non stocké) plutôt qu'un
onchange - un mécanisme fondamentalement différent qui s'évalue
chaque fois que le formulaire est affiché ou que sa dépendance change,
peu importe COMMENT `survey_ids` a reçu sa valeur (contexte ou saisie
interactive). C'est un mécanisme structurellement plus robuste pour ce
cas précis - non vérifié en conditions réelles faute d'accès à une
instance, mais le principe (les champs calculés se réévaluent à la
lecture de l'enregistrement, contrairement aux onchange) est un
comportement standard et bien établi d'Odoo.



L'utilisateur a fourni l'URL exacte obtenue en cliquant sur le bouton
natif « Test » d'un sondage déjà démarré (avec de vraies réponses),
ainsi que l'URL normale de ce même sondage pour comparaison :

- Normale (`get_start_url()`, confirmée correcte) :
  `/survey/start/<jeton du sondage>`
- Test réelle (bandeau « Ceci est une entrée d'un sondage test ») :
  `/survey/<jeton du sondage>/<jeton d'une entrée survey.user_input>`

**Confirmé** : contrairement au lien normal, le lien de test a besoin
du jeton d'une entrée `survey.user_input` PRÉCISE, déjà créée en base
avec `test_entry: True` - il ne suffit pas de construire une URL à
partir du seul identifiant du sondage, comme c'était le cas pour les
deux tentatives précédentes.

**Effet de bord assumé** : `_lien_test_sondage()` crée maintenant une
vraie entrée `survey.user_input` (test_entry=True) si aucune n'existe
déjà pour ce sondage et cet utilisateur - réutilisée aux générations
suivantes plutôt que d'en créer une nouvelle à chaque fois (voir
`test_lien_test_sondage_reutilise_entree_existante` dans
`test_wizard.py`). Cette entrée reste en base de façon permanente,
mais est automatiquement exclue des statistiques réelles par Odoo (le
filtre « Sauf entrées test » est actif par défaut sur la liste des
réponses) - un compromis jugé raisonnable pour obtenir un vrai lien de
test fonctionnel.

**Non vérifié** : le champ `test_entry` sur `survey.user_input` -
confirmé exister dans une ancienne version d'Odoo (2015), supposé
inchangé depuis, mais pas revérifié directement sur cette instance.
Si la création de l'entrée de test échoue (champ inexistant ou autre
erreur), le code retombe silencieusement sur le lien normal
(`get_start_url()`) plutôt que de faire échouer tout le rapport -
vérifiez dans les logs si un avertissement "Impossible de créer une
entrée de test" apparaît, signe que ce repli a été utilisé.




Deux fichiers dans `tests/` :

- **`test_report_builder.py`** — 39 tests, **exécutés et confirmés
  passants** dans l'environnement de développement (aucune dépendance
  à Odoo). Couvre les fonctions de construction HTML/statistiques,
  avec une attention particulière aux endroits où de vraies
  régressions se sont produites (tooltip de date, sauts de page
  flex/PDF, précision "Autre", fenêtres superposées). Peut s'exécuter
  n'importe où :
  ```
  cd rlq_survey_report && python3 -m unittest tests.test_report_builder -v
  ```
- **`test_wizard.py`** — tests Odoo (`TransactionCase`), **non exécutés
  ni vérifiés** faute d'accès à une instance Odoo. Suit les mêmes
  hypothèses de nommage de champs que le reste du module (voir les
  sections précédentes) - si un test échoue avec une erreur de champ
  inexistant, c'est probablement le même ajustement qui serait
  nécessaire pour le module lui-même. À exécuter avec :
  ```
  odoo-bin -d BASE_DE_TEST -i rlq_survey_report --test-enable \
      --test-tags rlq_survey_report --stop-after-init
  ```
  **Utilisez une base jetable, jamais votre base de production.**

**Recommandation** : lancez `test_wizard.py` sur une copie de test
après chaque mise à jour du module, avant de déployer en production -
c'est le moyen le plus fiable de détecter une régression avant qu'elle
n'affecte un vrai rapport.

## -14. Tooltip de date : RÉSOLU - la fusion elle-même était la cause du problème (v1.43.0)

**Cause réelle, enfin identifiée** : le tooltip fonctionnait en fait
depuis le début - le problème n'était jamais son absence, mais son
EMPLACEMENT. La fusion faite en v1.35.0 (combiner la date avec la
moyenne dans le tooltip de la barre, pour "corriger" un doublon
perçu) était en réalité une mauvaise interprétation : les DEUX
tooltips distincts (moyenne sur la barre, date sur le nom de l'item)
étaient le comportement CORRECT et voulu depuis le début - percevoir
ça comme un "doublon" en survolant près de la frontière entre les
deux éléments adjacents était une fausse piste. La fusion a ensuite
fait dépendre l'AFFICHAGE de la date de la présence d'une moyenne
numérique (`info_bulle`), et a placé l'info sur le mauvais élément
(la barre plutôt que le nom).

**Corrigé en v1.43.0** : les deux tooltips sont maintenant à nouveau
séparés - le nom de chaque volet/présentation porte son propre
tooltip avec la date (`Présenté le AAAA-MM-JJ (jour)`), indépendant de
la barre, qui garde son tooltip de moyenne. Confirmé fonctionner même
sans moyenne numérique (aucune réponse chiffrée pour cet item).

**Le renommage `data-tooltip` → `data-rlq-tip` (v1.41.0)**, fait sur
l'hypothèse d'une collision avec un mécanisme interne d'Odoo, était
probablement un correctif inutile pour CE problème précis (la vraie
cause étant la fusion elle-même) - conservé néanmoins, n'étant pas
nuisible en soi et pouvant rester utile par prudence.



Nouvel indice précieux de l'utilisateur : le doublon de tooltip
("Organisation et logistique", "Contenu et expérience Linux")
n'apparaît QUE dans l'app Odoo (PWA), jamais dans le fichier HTML
autonome - qui, lui, est décrit comme correct. Ceci pointe vers une
collision avec un mécanisme propre au client web d'Odoo plutôt qu'un
défaut dans notre HTML/CSS lui-même. Notre attribut `data-tooltip` a
été renommé `data-rlq-tip` partout, sur l'hypothèse qu'Odoo pourrait
avoir son propre traitement interne du nom `data-tooltip` (utilisé par
certains widgets Odoo) qui interférerait avec le nôtre.

**Le tooltip de date toujours absent spécifiquement pour "Comment
avez-vous aimé les présentations ?"** (alors qu'il fonctionne pour
d'autres questions matricielles) reste NON RÉSOLU - hypothèse toujours
non confirmée : cette question a-t-elle des volets qui changent d'un
mois à l'autre (noms de présentations) plutôt que des volets fixes
comme "Organisation et logistique" ? Si oui, une légère variation du
titre exact de la question d'un sondage à l'autre (accent, espace,
majuscule) fragmenterait silencieusement les données de ce module,
qui utilise le titre comme clé. Pour confirmer : inspecter le code
source de la page (clic droit → Inspecter) au niveau de cette question
précise resterait le moyen le plus direct d'avancer.

**Après ce renommage, vérifiez** : le doublon a-t-il disparu dans
l'app Odoo ? Si NON, l'hypothèse de collision d'attribut est écartée,
et la piste suivante serait de comparer le HTML réellement rendu par
Odoo (vue Inspecter) à celui généré par ce module (fichier HTML
téléchargé) pour repérer ce qu'Odoo ajoute ou modifie.

## -13bis. Format de papier PDF changé en 11x17 portrait (v1.41.0) - mise en page non vérifiée

Le format est passé de 8x14 paysage à 11x17 portrait (279 x 432 mm).
Un format plus étroit (portrait vs paysage) peut affecter la lisibilité
des tableaux à plusieurs colonnes (ex. le tableau récapitulatif, les
tableaux par participant) - à vérifier visuellement sur un vrai PDF
généré. Si des colonnes semblent trop compressées, envisager de
réduire le nombre de colonnes affichées par défaut dans le PDF, ou
d'ajuster la taille de police spécifique au PDF dans le CSS.



**Confirmé en production** : `odoo.addons.base.models.ir_rule: Access
Denied by record rules for operation: read on record ids: [3], uid: 4,
model: res.partner`. Plusieurs endroits de ce module lisaient des
champs d'une fiche contact (`_respondent_nom`, `_respondent_email`, les
détails du participant - téléphone, ville, pays, étiquettes) sans
`sudo()`. Un « Utilisateur » du module Sondage peut légitimement
générer ce rapport, mais les règles d'enregistrement d'Odoo peuvent lui
refuser un accès DIRECT à telle ou telle fiche contact individuelle
(ex. un contact d'une autre société, en environnement multi-société).
Puisque montrer ces coordonnées est le but même de ce rapport (déjà
protégé par ailleurs : confirmation obligatoire, mot de passe pour
tout téléchargement), lire ces champs précis en `sudo()` a été jugé
raisonnable plutôt que de continuer à lever cette erreur. **Si
d'autres erreurs similaires ("Access Denied by record rules") apparaissent dans les logs pour un autre modèle**, le même correctif
(ajouter `.sudo()` au bon endroit) s'applique probablement.

## -13. Tooltip de date : investigation approfondie supplémentaire, toujours pas de cause trouvée (v1.39.0)

Signalé une troisième fois. Nouvel indice fourni : les tooltips
fonctionnent bien dans des questions à choix/texte libre ("Quel sujet
de discussion avez-vous aimé le plus ?", etc.), et un doublon de
tooltip (un rapide, un après ~1 seconde) persiste dans certaines
questions matricielles ("Organisation et logistique", "Contenu et
expérience Linux") malgré la fusion faite en v1.35.0 - alors que
"Comment avez-vous aimé les présentations ?" n'affiche AUCUN tooltip.

**Recherche effectuée** : le timing "rapide puis après 1 seconde"
correspond typiquement à un tooltip natif du navigateur (attribut HTML
`title=""`, délai natif d'affichage) coexistant avec un tooltip
personnalisé (CSS, immédiat) - une recherche exhaustive de `title=`
dans tout `report_builder.py` et `rlq_survey_report_wizard.py` n'a
trouvé AUCUNE occurrence d'un tel attribut généré par ce module. La
structure du tooltip CSS personnalisé (`section_matrice()`) a été
revérifiée ligne par ligne : un seul mécanisme de tooltip par barre
(pas de span dupliqué), inchangé depuis la fusion de la v1.35.0.

**Hypothèse non vérifiable sans accès à l'instance** : si "Comment
avez-vous aimé les présentations ?" a des volets (noms de
présentation) qui changent à chaque rencontre plutôt que des volets
fixes et récurrents (contrairement à "Organisation et logistique",
dont les volets - Salle, Accueil, etc. - sont probablement identiques
d'une rencontre à l'autre), le TITRE EXACT de la question pourrait
légèrement différer d'une rencontre à l'autre si les sondages sont
recréés manuellement chaque mois plutôt que dupliqués depuis un
modèle - un espace, un accent ou une majuscule différente ferait de
"titre" une clé distincte à chaque fois pour ce module, fragmentant
les données. Ceci resterait à confirmer.

**Pour avancer, il faudrait une des informations suivantes :**
1. Dans un navigateur, clic droit sur l'histogramme concerné →
   « Inspecter » (ou « Afficher le code source » sur toute la page) -
   copier le HTML de la ligne concernée (le `<div class="barre-cadre
   ...">`) permettrait de voir directement s'il y a un attribut
   `title=` inattendu ou une structure inattendue.
2. Confirmer si "Comment avez-vous aimé les présentations ?" a des
   volets qui changent d'un mois à l'autre (noms de présentations) ou
   des volets fixes.
3. Confirmer si le doublon de tooltip (question 5) se produit
   uniquement à l'écran dans Odoo, uniquement dans le fichier HTML
   téléchargé, ou dans les deux.

Sans cette information, je ne veux pas proposer un troisième correctif
spéculatif après deux tentatives infructueuses.

## -12. Deux problèmes signalés mais NON reproduits après relecture et nouveaux tests (v1.38.0)

Après relecture attentive du code et de nouveaux tests en isolation,
je n'ai trouvé aucun bogue dans les deux cas suivants - documentés ici
plutôt que corrigés à l'aveuglette, pour éviter de deviner un correctif
qui ne réglerait pas le vrai problème :

**Message de progression au clic sur « Générer » manquant.** Le code
qui l'envoie (`_envoyer_notification`, via le bus temps réel d'Odoo)
est bien présent et appelé au bon endroit. Étant donné qu'un problème
de même nature (notification bus non visible) a déjà été confirmé pour
l'avertissement de mot de passe faible (voir plus loin, corrigé en
v1.37.0 par un champ permanent plutôt qu'une notification), **le bus de
notifications semble ne pas fonctionner de façon fiable sur cette
instance** - possiblement un problème d'infrastructure (ex. le worker
de longpolling n'est pas démarré, ou le canal n'est pas écouté
correctement côté navigateur). `_envoyer_notification` journalise un
avertissement (`_logger.warning`) si l'envoi échoue - **vérifiez les
logs du serveur juste après avoir cliqué sur « Générer »** : si un tel
avertissement y apparaît, cela confirme un échec d'envoi ; s'il
n'apparaît PAS, l'envoi a réussi côté serveur mais ne s'affiche pas
côté navigateur pour une autre raison (configuration du bus à
vérifier avec votre administrateur système).

**Tooltip de date des présentations dans la Synthèse.** Retesté en
isolation (`section_matrice()` avec `dates_par_item` peuplé) : le
tooltip est bien généré. Le câblage dans `_compute_report()`
(`synth_item_date[titre][item] = date_rencontre`, puis
`dates_par_item=synth_item_date.get(titre)` au moment de construire la
Synthèse) a été relu ligne par ligne sans trouver d'erreur. Pistes à
vérifier avant de chercher plus loin : (1) la Synthèse n'apparaît que
si 2 rencontres ou plus sont incluses - est-ce bien le cas ? (2) la
version affichée correspond-elle bien à v1.37.0 ou plus récente
(vérifiable via l'info de version en mode debug) ? (3) le survol
fonctionne-t-il ailleurs dans le rapport (ex. sur le nombre de
participants d'une étiquette) ? Si le tooltip manque PARTOUT (pas
seulement dans la Synthèse), la piste à explorer serait plutôt le CSS
lui-même (`.a-tooltip::after`) que le calcul des dates.



`_html_details_evenement()` couvre les champs standards du module
Événements d'Odoo (lieu, horaire, places, description, photo),
recherchés dynamiquement. **Commanditaires, kiosques, et gagnants d'un
tirage au sort ne sont PAS couverts** - rien n'indique que ces notions
existent sous forme de champs standards sur `event.event`, elles sont
donc probablement des champs propres à votre instance (ou à un module
tiers), dont je n'ai aucun moyen de connaître le nom exact.

**Pour les ajouter vous-même** (ou me fournir l'information pour que je
le fasse) : ouvrez un événement en mode développeur dans Odoo, activez
l'affichage des noms techniques de champs, et notez le nom exact du
champ contenant chacune de ces informations. Puis, dans
`_html_details_evenement()` (`rlq_survey_report_wizard.py`), ajoutez
une entrée suivant le même patron que les champs déjà couverts, par
exemple pour un champ `x_commanditaires` de type texte :
```python
for nom_champ in ("x_commanditaires",):
    if nom_champ in evenement._fields and evenement[nom_champ]:
        morceaux.append(f"Commanditaires : {rb.echapper(str(evenement[nom_champ]))}")
        break
```
Ce patron (vérifier l'existence du champ avant d'y accéder) garantit
qu'aucune erreur n'est levée si le nom s'avère incorrect ou si le champ
n'existe pas du tout sur un enregistrement donné.

## -8. Lien "ouvrir" un sondage : RÉSOLU (v1.37.0), confirmait l'incertitude signalée en v1.35.0

Le chemin `/survey/test/<id>` (v1.35.0) a été **confirmé cassé** par
l'utilisateur - il menait à la page d'accueil plutôt qu'au sondage.
Remplacé par `survey.get_start_url()`, une méthode confirmée exister
sur ce modèle. **Point important à retenir** : contrairement à ce que
le chemin `/survey/test/` promettait, ce lien ne crée PAS une réponse
« test » exclue des statistiques - l'ouvrir et y répondre compte comme
une réponse RÉELLE. Le libellé affiché (« ouvrir », pas « tester ») a
été choisi en conséquence, pour ne pas induire en erreur sur ce point.
Si un vrai mode test s'avère nécessaire plus tard, il faudrait trouver
le mécanisme exact utilisé par le bouton « Test » natif du formulaire
Sondage sur cette version précise d'Odoo (inspecter l'URL obtenue en
cliquant dessus).

## -9. Dépendance supplémentaire pour l'export Excel (v1.37.0)

L'export Excel (`action_export_excel`) nécessite la bibliothèque
`openpyxl`, en plus de `pyzipper` (déjà nécessaire depuis la v1.36.0
pour la protection par mot de passe des exports). Les deux sont
indépendantes : l'une génère le fichier Excel, l'autre le protège.
Message d'erreur clair si l'une des deux manque - jamais d'export
silencieusement non protégé ou vide.

## -10. Sens exact d'"Inscrits"/"Présents" (seats_reserved/seats_used) : à valider (v1.36.0, libellés ajustés en v1.37.0)

Signalé par l'utilisateur : les chiffres affichés semblaient
incohérents (Présents > Inscrits). Compris (avec confiance modérée,
non vérifiée directement sur cette instance) : `seats_reserved` et
`seats_used` représentent normalement deux groupes DISTINCTS
(inscriptions confirmées mais présence non encore validée, vs présence
déjà validée) plutôt qu'une relation sous-ensemble - donc pas
nécessairement une incohérence. Libellés ajustés en conséquence
(« Inscrits (en attente de présence) » / « Présence confirmée »).
**À valider vous-même** sur un événement dont vous connaissez déjà les
vrais chiffres, pour confirmer que cette interprétation correspond
bien au comportement réel de cette instance.

## -7. Champ mot de passe invisible : problème persistant, simplifié radicalement (v1.33.0)

Signalé une seconde fois après le correctif de la v1.32.0 (retrait du
mécanisme à deux champs dupliqués). N'ayant pas pu observer le
formulaire directement pour diagnostiquer la cause exacte, la v1.33.0
retire **toute** condition `invisible`/`required` dynamique sur le
champ `mot_de_passe` - il est désormais un champ ordinaire, toujours
affiché, sans aucune logique conditionnelle dans la vue.

**Si le problème persiste malgré ce troisième correctif**, deux pistes
à vérifier avant de chercher plus loin dans le code :

1. **Cache de vue non rafraîchi** - après une mise à jour de module,
   un rechargement forcé du navigateur (Ctrl+Maj+R, ou vider le cache)
   est parfois nécessaire pour qu'Odoo serve la version à jour du
   formulaire. Vérifiez aussi, via le mode développeur, que le module
   affiche bien la version `18.0.1.33.0` (visible dans l'info de
   version sous le titre du formulaire, en mode debug) - si une
   version antérieure s'affiche encore, la mise à jour du module
   elle-même n'a peut-être pas été prise en compte (ex. redémarrage du
   service incomplet, module non réellement mis à jour avec `-u`).
2. **Une personnalisation tierce sur cette instance ERPLibre** pourrait
   interférer avec le rendu de ce formulaire précis d'une façon que le
   code de ce module ne peut pas anticiper - si les deux vérifications
   ci-dessus n'expliquent rien, ce serait la piste suivante à explorer,
   idéalement avec un accès direct à l'instance (voir la discussion
   sur Claude Code plus tôt dans le projet).

## -6. Histogrammes PDF : deuxième tentative de correctif (v1.31.0)

Un premier correctif (v1.29.0, largeur/affichage figés en CSS sur les
`<div>` imbriqués de l'histogramme, contournant un bogue connu de
wkhtmltopdf avec flexbox) ne semble pas avoir suffi - toujours signalé
invisible en v1.30.0. Changement d'approche en v1.31.0 : les
histogrammes sont maintenant remplacés, pour le PDF uniquement, par un
simple `<table>` à deux cellules (une colorée représentant le
remplissage, une non colorée représentant le reste) - une technique
supportée de façon fiable par pratiquement n'importe quel moteur de
rendu HTML depuis les tout débuts du web. **Si les histogrammes restent
invisibles malgré ce second correctif**, le problème n'est probablement
pas la structure HTML/CSS mais quelque chose de plus fondamental sur
cette installation précise de wkhtmltopdf (version très ancienne,
configuration particulière, etc.) - dans ce cas, décrire précisément ce
qui apparaît à la place (une zone vide ? un cadre sans remplissage ? une
erreur de génération ?) aiderait à cibler la cause réelle plutôt que de
continuer à deviner des correctifs CSS.

## -5. INCIDENT CRITIQUE RÉSOLU : un enregistrement Odoo n'accepte pas d'attributs arbitraires sur self (v1.30.0)

**Confirmé en production** : `_html_pour_pdf()` tentait d'écrire
`self._compteur_rencontre_pdf = 0` directement sur l'enregistrement du
wizard (pour compter les occurrences lors de l'insertion de sauts de
page en ligne, v1.29.0) - ce qui provoquait un plantage
(`AttributeError`) empêchant **toute génération de PDF**.

**Leçon pour toute future modification de ce module** : ne jamais
utiliser `self.nom_quelconque = valeur` sur un enregistrement Odoo
(`self` dans une méthode de modèle) pour de l'état temporaire/de
travail, même pour un nom commençant par un souligné - seuls les
champs déclarés (`fields.Xxx(...)`) peuvent être affectés ainsi. Pour
de l'état local à une méthode (ex. un compteur utilisé par une
fonction de remplacement `re.sub()`), utiliser une variable locale
capturée par une fermeture (closure), comme le fait maintenant
`_inserer_sauts_de_page_sauf_premier()` - voir le CHANGELOG, version
1.30.0, pour le détail complet et la démarche de vérification suivie.

## -4bis. Chiffrement PDF corrigé : RC4 (par défaut) remplacé par AES-256 (v1.30.0)

**Confirmé par une vérification de la documentation officielle de
pypdf** : la méthode `PdfWriter.encrypt(mot_de_passe)`, utilisée sans
préciser le paramètre `algorithm`, chiffre par défaut avec **RC4** -
un algorithme non sécurisé, cassable en quelques secondes avec les
outils actuels (hérité pour compatibilité avec de très vieux lecteurs
PDF). Le code de la v1.29.0 avait cette faille. Corrigé en précisant
explicitement `algorithm="AES-256"`. **Testé de bout en bout avec un
vrai fichier PDF** (chiffrement confirmé, déchiffrement réussi avec le
bon mot de passe, rejeté avec un mauvais) - contrairement à la partie
HTML (section -4 ci-dessous), cette partie PDF a donc pu être
validée avec un test réel, pas seulement en isolation.

## -4. Protection par mot de passe (PDF/HTML) - À TESTER AVANT TOUTE UTILISATION RÉELLE (v1.29.0, obligatoire depuis v1.31.0)

Protection par mot de passe, ajoutée suite à une préoccupation de
conformité légale (Loi 25 au Québec, RGPD en Europe) sur la protection
des renseignements personnels contenus dans le rapport (noms,
coordonnées des participants). **Depuis la v1.31.0, cette protection
n'est plus optionnelle** : le mot de passe est requis dès que le
format de sortie n'est pas « Écran », et doit respecter un niveau de
complexité minimal (12 caractères, 4 types de caractères - voir
l'aide du champ dans le formulaire pour le détail).

**PDF** : chiffrement standard via la bibliothèque Python `pypdf` (ou
`PyPDF2` en repli) - `PdfWriter.encrypt(mot_de_passe, algorithm=
"AES-256")`. Mécanisme robuste et éprouvé, identique à celui de
n'importe quel PDF protégé par mot de passe dans un lecteur usuel
(Adobe Reader, etc.) - **testé de bout en bout avec un vrai fichier
PDF en v1.30.0** (voir section -4bis ci-dessus) : chiffrement,
déchiffrement avec le bon mot de passe, rejet d'un mauvais. Nécessite
que `pypdf`/`PyPDF2` ET une bibliothèque de chiffrement AES
(`cryptography` ou `pycryptodome`) soient installées sur l'instance -
messages d'erreur clairs sinon, invitant à les installer ou à
décocher l'option.

**HTML** : mécanisme différent, puisqu'un fichier HTML n'a pas
d'équivalent natif à la protection par mot de passe d'un PDF. Le
contenu est chiffré côté serveur (AES-256-GCM, clé dérivée du mot de
passe via PBKDF2-SHA256 à 210 000 itérations - recommandation OWASP
actuelle - avec la bibliothèque Python `cryptography`), puis le
fichier livré contient une page d'invite qui déchiffre le contenu
**dans le navigateur** au moment de l'ouverture, via l'API Web Crypto
native (aucune bibliothèque JavaScript externe, aucune donnée envoyée
à un serveur - tout se passe localement une fois le fichier
téléchargé).

**⚠️ IMPORTANT - la partie HTML n'a pas pu être testée en conditions
réelles** (contrairement au PDF, testé de bout en bout - voir
section -4bis) : le round-trip de chiffrement/déchiffrement AES-GCM a
été validé **côté Python uniquement**
(chiffrer avec un mot de passe puis déchiffrer avec succès ; un
mauvais mot de passe est correctement rejeté) - voir le CHANGELOG pour
le détail de ce test. La partie JavaScript (déchiffrement dans le
navigateur via l'API Web Crypto) utilise les MÊMES paramètres
(PBKDF2-SHA256, 210 000 itérations, AES-GCM 256 bits) et suit un
patron standard bien établi, mais **n'a pu être exécutée dans aucun
navigateur** faute d'environnement disponible pour ce faire.

**Avant de vous fier à cette fonctionnalité pour une obligation
légale** :
1. Générez un rapport HTML avec la protection activée.
2. Ouvrez le fichier téléchargé dans un navigateur.
3. Essayez d'abord un MAUVAIS mot de passe - vérifiez qu'un message
   d'erreur clair apparaît et qu'AUCUN contenu du rapport n'est
   visible ni accessible (inspectez le code source de la page : le
   contenu doit être illisible, seulement du texte chiffré en base64).
4. Essayez ensuite le BON mot de passe - vérifiez que le rapport
   complet s'affiche correctement.
5. Répétez pour le PDF : essayez d'ouvrir le fichier sans mot de passe
   (le lecteur PDF doit le refuser), puis avec le bon mot de passe.

Si l'une de ces étapes échoue, ne considérez pas cette fonctionnalité
comme fiable pour une obligation légale tant que le problème n'est pas
corrigé - signalez ce qui a été observé pour correction.

**Ceci ne remplace pas un avis juridique** sur vos obligations exactes
en matière de protection des renseignements personnels (la Loi 25 et
le RGPD ont des exigences qui dépassent le seul chiffrement d'un
fichier - minimisation des données, durée de conservation, etc.).

## -3. INCIDENT CRITIQUE RÉSOLU : ne jamais redéclarer store=True sur un champ natif sans son compute= (v1.27.0)

En v1.26.0, `answer_count` et `answer_done_count` (champs natifs du
module Sondage, calculés mais non stockés) avaient été redéclarés dans
`survey_survey.py` avec seulement `store=True`, dans le but de les
rendre triables dans la liste de sélection. Ceci a provoqué
l'avertissement Odoo suivant, confirmé en production :

> UserWarning: survey.survey: inconsistent 'store' for computed
> fields... Use distinct compute methods for stored and non-stored
> fields.

Plus grave : cet avertissement est apparu **sur des pages n'ayant
aucun rapport avec les sondages** (visible dans le traitement de
requêtes HTTP ordinaires, via `res.lang.get_installed()`), signe qu'il
affectait la cohérence du registre de champs pour l'ensemble de
l'instance, pas seulement ce module.

**Corrigé en v1.27.0** : cette redéclaration est totalement retirée.
`rlq_answer_count` et `rlq_answer_done_count` (nos propres champs,
calculés indépendamment dans `_compute_rlq_stats`) servent de copies
triables à la place - ils ne touchent à aucune définition existante,
donc aucun risque de ce genre n'est possible.

**Leçon pour toute future modification de ce module** : ne jamais
redéclarer un champ natif d'Odoo (même seulement pour ajouter
`store=True`) sans reproduire fidèlement sa méthode de calcul complète
(avec le même `@api.depends`) - ou, plus simplement et plus
prudemment, toujours préférer un nouveau champ (`rlq_...`) qui ne
touche à rien d'existant.

## -2. Compatibilité Odoo 18 CE et Odoo 19 CE (v18.0.1.22.0)

La convention de version « 18.0.x.y.z » est **conservée** (décision de
l'utilisateur). Point important à garder en tête : Odoo valide
strictement qu'un préfixe de série dans le numéro de version
corresponde à la version du serveur qui tente l'installation - un
module numéroté « 18.0.x.y.z » **refuse littéralement de s'installer**
sur un serveur Odoo 19 (erreur `ValueError: Invalid version`). Passer
ce module à une instance Odoo 19 nécessitera donc de changer ce préfixe
(« 18.0. » → « 19.0. ») dans `__manifest__.py` avant la mise à jour -
une simple modification de configuration, acceptée comme suffisante.

Recherche effectuée (voir CHANGELOG.md pour le détail complet) : les
notes de version officielles d'Odoo 19
(odoo.com/odoo-19-release-notes) ne mentionnent, pour la section
Sondages, que des ajouts (qualification de leads, analyse dans
Spreadsheet) - aucun renommage de champ ni restructuration du modèle.
Les champs standards utilisés par ce module (`title`, `user_id`,
`answer_count`, `answer_done_count`, `question_ids`,
`start_datetime`/`end_datetime`) devraient donc rester valides sur
Odoo 19 tels quels.

**Ce qui reste à vérifier concrètement, dès qu'une instance Odoo 19 de
test sera disponible :**
1. Changer le préfixe de version dans `__manifest__.py` (« 18.0. » →
   « 19.0. »).
2. Installer le module normalement (`-u rlq_survey_report`).
3. Vérifier que la détection dynamique du modèle des réponses
   individuelles (section 2 ci-dessous) trouve toujours le bon champ -
   c'est le point le plus susceptible de varier, puisqu'il dépend d'un
   module tiers (le fork de « débrandisation » identifié précédemment
   sur cette instance ERPLibre), pas du cœur d'Odoo lui-même.
4. Générer un rapport test et comparer visuellement avec un rapport
   équivalent généré sur Odoo 18, pour repérer d'éventuelles
   différences de rendu (peu probable côté serveur, mais le rendu HTML
   dans le client web pourrait différer légèrement avec la refonte de
   l'interface annoncée pour Odoo 19).

## -1. Toujours mettre à jour le module après une nouvelle version

Si une nouvelle version ajoute ou modifie un champ (visible dans le
CHANGELOG.md), un **redémarrage du service Odoo seul ne suffit pas** :
il faut explicitement demander la mise à jour du module pour que la
base de données ajoute/modifie les colonnes correspondantes :

```bash
./odoo-bin -d VOTRE_BASE -u rlq_survey_report --stop-after-init
```

Sans cette étape, vous obtiendrez une erreur du type
`psycopg2.errors.UndefinedColumn: column "xxx" of relation
"rlq_survey_report_wizard" does not exist` dès que le formulaire tente
d'enregistrer le nouveau champ.

**Autre symptôme du même genre de problème** : une erreur du type
`AttributeError: 'rlq.survey.report.wizard' object has no attribute
'action_menu_xxx'` lors du clic sur un sous-menu de raccourci, alors
même que la méthode existe bel et bien dans le fichier livré. Cela
signifie que le **processus Odoo en cours d'exécution n'a jamais
rechargé le nouveau code Python** : la mise à jour du module (`-u`) met
à jour les données XML (dont le texte des actions serveur) sans
nécessairement redémarrer le processus qui exécute déjà ce code en
mémoire, selon la configuration du service. Si `-u` ne suffit pas,
**redémarrez complètement le service Odoo** (ex. `systemctl restart
odoo-dev` ou équivalent) après avoir déployé les nouveaux fichiers.

## 0. Si le rapport reste vide après avoir cliqué « Générer »

Une nouvelle version (1.1.0) affiche maintenant un **message de
diagnostic explicite** dans ces cas plutôt qu'un rapport vide, mais si
vous étiez sur la version précédente, la cause la plus probable était :

- Le sondage sélectionné n'a aucune réponse au statut **Terminé**
  (`state = 'done'`) sur `survey.user_input` - le module ne compte, par
  défaut, que les réponses terminées. Cochez **« Inclure les réponses
  partielles »** dans le formulaire, ou vérifiez le statut réel des
  réponses de ce sondage.
- Une plage de dates (À partir du / Jusqu'au) ou une exclusion de
  participant trop restrictive.

Le bouton « Générer » ne devrait plus jamais laisser l'écran vide sans
explication : si c'est encore le cas, une exception a probablement été
levée côté serveur - consultez les logs Odoo (la version 1.1.0 y
consigne la trace complète via `_logger.exception`) et le message
d'erreur affiché à l'écran, qui identifie généralement le nom de champ
en cause.

## 1. Installation

```bash
# Copier le dossier dans le répertoire addons de votre instance, puis :
./odoo-bin -d VOTRE_BASE -u rlq_survey_report --stop-after-init
# ou, via l'interface : Apps > Mettre à jour la liste des Apps > rechercher
# "RLQ - Rapport de sondage mensuel" > Installer.
```

Si l'installation échoue avec une erreur `ValueError: External ID not
found` sur `security/ir.model.access.csv`, c'est que le groupe
`survey.group_survey_user` n'existe pas sous ce nom exact sur votre
version : remplacez-le par le groupe approprié (`base.group_user`
fonctionne toujours, mais donne accès à tous les utilisateurs internes).

## 2. Champs ORM à vérifier

**Mise à jour (v1.3.0)** : le module n'a plus besoin de connaître à
l'avance le nom du modèle des réponses individuelles - il le détecte
automatiquement à partir des champs One2many de `survey.user_input`.
Sur au moins une instance ERPLibre testée, ce modèle ne s'appelait PAS
`survey.user_input_line` comme dans Odoo CE standard.

Si une question précise est ignorée avec un avertissement dans le
rapport, c'est qu'un champ *interne* à cette question (colonne, ligne
matricielle, valeur) ne correspond pas à votre instance. Ouvrez le mode
développeur, puis sur un enregistrement `survey.question` existant,
affichez les champs techniques pour confirmer :

| Supposé dans le code | Rôle | Si différent |
|---|---|---|
| `question.suggested_answer_ids` | options / colonnes | ajuster `_get_columns()` dans `rlq_survey_report_wizard.py` |
| `question.matrix_row_ids` | lignes d'une question matricielle | ajuster `_get_rows()` |
| `survey.question.answer.value` | texte affiché d'une option/ligne | ajuster les `.value` dans le wizard |
| `survey.user_input.email` | courriel du répondant anonyme | ajuster `_respondent_email()` |
| *(champ de ligne)*`.matrix_row_id` | ligne choisie (matriciel) | ajuster `_traiter_question()` |
| *(champ de ligne)*`.suggested_answer_id` | option/colonne choisie | idem |
| *(champ de ligne)*`.value_text_box` / `.value_char_box` | texte libre | idem |

La façon la plus rapide de vérifier : dans le shell Odoo
(`./odoo-bin shell -d VOTRE_BASE`), inspecter un `survey.question` réel :

```python
q = env['survey.question'].search([], limit=1)
q.fields_get().keys()          # liste tous les champs disponibles
q.suggested_answer_ids.value   # doit retourner une liste de textes

# Pour le modèle des lignes de réponse (détecté automatiquement, mais
# vérifiable manuellement) :
ui = env['survey.user_input'].search([], limit=1)
[(f, d.comodel_name) for f, d in ui._fields.items() if d.type == 'one2many']
```

## 3. Association rencontre <-> date

Le module déduit la date d'une rencontre à partir de la première
réponse soumise (`min(create_date)` des `survey.user_input` liés). Si
RLQ associe déjà chaque sondage mensuel à un évènement (`event.event`)
ou une date précise ailleurs dans Odoo, il serait préférable
d'utiliser ce champ directement (voir `_rencontre_date()` dans le
wizard) plutôt que de déduire la date des réponses.

## 3bis. Critères des 5 sous-menus de sélection rapide

Vérifiez, pour chaque sous-menu, que la sélection pré-remplie
correspond à vos attentes (ouvrez le wizard via le sous-menu et
regardez le champ « Sondages » avant de cliquer sur « Générer ») :

- **Premier mardi du mois** : le titre du sondage ne contenant pas ces
  mots, le classement se base sur la **date** qu'il contient (ex.
  « 4 août 2026 », « 4 nov 2025 » avec diminutif de mois, ou même
  « 31 juillet » sans année du tout - voir section 4ter sur les replis
  d'année) et son jour de la semaine - mardi, dans les 7 premiers jours
  du mois. Si le format de date dans vos titres diffère encore,
  ajustez `MOIS_FR`/`_MOTIF_DATE_FR` dans `rlq_survey_report_wizard.py`.
- **Pause café** : recherche « pause café »/« pause-café » (avec ou
  sans accent) dans le titre du sondage.
- **Sondage annuel** (v1.20.0) : sondages ayant reçu plus de 100
  réponses ET dont la date tombe en septembre - vérifiée en priorité
  via le titre, avec repli sur le mois de la première réponse soumise
  si le titre ne contient AUCUNE date exploitable (ni jour, ni mois -
  seulement une année, comme « ...Linux 2025 », ou rien du tout). Si
  le seuil ou le mois doivent changer, ajustez les paramètres
  `seuil`/`mois` de `_survey_ids_annuel()`.
- **Portes ouvertes** (nouveau, v1.20.0) : recherche « portes ouvertes »
  dans le titre - alternative fiable au critère par date pour ce genre
  de sondage, dont le titre ne contient souvent qu'une année.
- **Tous les autres** : calculé par exclusion des quatre catégories
  précédentes - vérifiez-le en dernier, une fois les autres critères
  confirmés corrects.

## 4. Groupement des questions à travers plusieurs mois (Synthèse)

La section « Synthèse » fusionne les questions de plusieurs sondages
**par correspondance exacte du titre** (`question.title`). Si le
libellé exact d'une question a changé d'un mois à l'autre (même une
espace ou une majuscule différente), elle sera traitée comme deux
questions distinctes dans la synthèse. Un premier passage sur vos
données réelles permettra de repérer ces cas.

## 4ter. Dates d'envoi/expiration et correspondance d'événement (v1.17.0)

Trois nouveaux mécanismes de détection dynamique (v1.17.0), tous conçus
pour ne jamais lever d'erreur si rien n'est trouvé :

- **Date d'envoi / date d'expiration** (`_dates_envoi_expiration()`) :
  cherche un champ Date/Datetime sur `survey.survey` dont le nom
  contient "send"/"envoi"/"invit" (envoi) ou "expir"/"deadline"/
  "cloture"/"closing"/"fin_" (expiration). Si aucun champ de ce genre
  n'existe sur votre instance, ces deux dates n'apparaissent tout
  simplement pas dans le rapport - vérifiez en mode développeur si de
  tels champs existent réellement sur `survey.survey`, et sous quel
  nom exact, si vous vous attendiez à les voir.
- **Année de repli** (`_annee_repli_titre()`) : quand le titre d'un
  sondage omet l'année (ex. « 31 juillet »), l'année de la date
  d'envoi (ci-dessus) sert de repli. Si aucune date d'envoi n'est
  trouvée, un tel titre n'aura pas de date exploitable du tout.
- **Correspondance d'événement par date** (`_lien_evenement_par_date()`) :
  utilisée seulement si aucune relation directe en base n'a été
  trouvée (voir section 2 plus haut sur `_lien_evenement()`). Cherche
  un `event.event`/`calendar.event` dont un champ de date parmi
  `date_begin`, `start`, `date_start`, `start_date` ou `date`
  (le premier trouvé sur le modèle réel) tombe le même jour que la
  date du sondage. Risque théorique de faux positif si un autre
  événement sans rapport tombe par coïncidence le même jour.

## 4bis. Colonnes de la liste de sondages - noms de champs vérifiés

**Mise à jour (v1.12.0)** : les noms de champs ci-dessous ont été
vérifiés directement dans le code source d'Odoo 18 CE sur GitHub
(`addons/survey/models/survey_survey.py`), plutôt que devinés :

| Colonne affichée | Champ technique | Confirmé |
|---|---|---|
| Titre | `title` | Oui (déjà utilisé partout dans le module) |
| Date (titre) | `rlq_date_titre` | Champ ajouté par ce module (v1.24.0) - date extraite du titre, réutilise `_extraire_date_titre()` |
| Jour de la semaine | `rlq_jour_semaine` | Champ ajouté par ce module (v1.26.0) - dérivé de `rlq_date_titre` |
| Date de création | `create_date` | Natif Odoo, toujours présent sur tout modèle - remplace, depuis la v1.26.0, une tentative de détecter une "date d'envoi" séparée qui n'avait rien trouvé sur cette instance |
| Inscrit | `answer_count` | Oui (label source : "Registered") - redéclaré `store=True` en v1.26.0 pour le rendre triable |
| Terminé | `answer_done_count` | Oui - compte réellement le statut `done`, malgré son label anglais "Attempts" - redéclaré `store=True` en v1.26.0 |
| Débuté sans terminer | `rlq_answer_in_progress_count` | Champ ajouté par ce module (models/survey_survey.py) - garanti correct puisque nous le définissons nous-mêmes |
| Durée moyenne (s) | `rlq_answer_duration_avg_seconds` | Idem - calculé directement à partir de `start_datetime`/`end_datetime`, plafonné à 999s |
| Nb. questions | `rlq_question_count` | Idem - `len(question_ids)` |
| Responsable | `user_id` | Oui (label source : "Responsible") - masqué par défaut |

« Taux de réussite » (`success_ratio`) et « Note moyenne »
(`answer_score_avg`) ont été retirés de la liste depuis la v1.20.0 (non
pertinents pour ce club).

**Point de vigilance (v1.26.0)** : `answer_count` et `answer_done_count`
ont été redéclarés avec `store=True` dans `survey_survey.py`, sans
préciser de nouveau `compute=` - technique standard pour rendre un champ
calculé natif triable, qui réutilise la méthode de calcul déjà définie
dans le module Sondage d'origine. Un risque légèrement plus élevé que
pour nos propres champs (ceux-ci touchent des champs NATIFS d'Odoo,
pas seulement des ajouts) : si l'installation échoue précisément sur ce
point, retirez ces deux lignes de `survey_survey.py` (le tri par ces
deux colonnes ne fonctionnera alors plus, sans affecter le reste).

Le risque d'échec d'installation sur ces champs est donc maintenant
faible (ils font partie du cœur standard d'Odoo, pas d'un module
optionnel, ou sont définis par ce module lui-même). Si une erreur
`Field "xxx" does not exist` survenait malgré tout (ex. si votre
instance ERPLibre personnalise aussi `survey.survey`, pas seulement les
lignes de réponse) :

1. Ouvrez `views/rlq_survey_report_views.xml`.
2. Repérez le bloc `<record id="view_survey_survey_list_rlq" ...>`
   (ou le `<field name="survey_ids" ...><list>...</list></field>` en
   ligne dans le formulaire, qui reprend les mêmes colonnes).
3. Supprimez uniquement la ligne `<field name="...">` nommée dans le
   message d'erreur, dans les DEUX endroits si elle y figure deux fois.
4. Relancez la mise à jour du module.

Les autres colonnes (et le reste du module) ne sont pas affectés par
la suppression d'une seule de ces lignes.

## 4quater. Vue liste dédiée pour la fenêtre "Ajouter une ligne" (v1.24.0)

**Problème corrigé** : la sous-vue `<list>` intégrée au champ
`survey_ids` ne gouverne que l'affichage des sondages DÉJÀ sélectionnés
dans le formulaire - cliquer sur "Ajouter une ligne" pour choisir un
NOUVEAU sondage ouvrait une fenêtre de sélection séparée qui, faute
d'indication contraire, utilisait la vue liste PAR DÉFAUT de Sondage
(avec ses propres colonnes : Responsable, Taux de réussite, etc.),
même si ces colonnes avaient été retirées de notre sous-vue en ligne.

**Correctif appliqué** : une vue liste autonome et dédiée
(`view_survey_survey_list_rlq`) a été créée avec nos colonnes
souhaitées, puis référencée sur le champ `survey_ids` via le contexte :
```xml
context="{'list_view_ref': 'rlq_survey_report.view_survey_survey_list_rlq',
          'tree_view_ref': 'rlq_survey_report.view_survey_survey_list_rlq'}"
```
Les deux clés de contexte (`list_view_ref`, terminologie Odoo 17+, et
`tree_view_ref`, l'ancienne terminologie) sont fournies simultanément
par prudence, une clé non reconnue étant simplement ignorée sans
erreur.

**À vérifier concrètement** : je n'ai aucun moyen de confirmer, sans
accès à une instance Odoo, que cette clé de contexte gouverne bien la
fenêtre "Ajouter une ligne" sur cette version précise d'Odoo/ERPLibre.
Après la mise à jour, ouvrez le wizard, cliquez sur "Ajouter une ligne"
dans le champ Sondages, et vérifiez que les colonnes affichées
correspondent bien à celles de `view_survey_survey_list_rlq` (Titre,
Date (titre), Date d'envoi, Inscrit, Terminé, Débuté sans terminer...)
plutôt qu'aux colonnes par défaut de Sondage. Si ce n'est pas le cas,
dites-le-moi : il existe d'autres mécanismes possibles (ex. remplacer
entièrement la vue par défaut de survey.survey via une vue héritée) à
explorer, mais avec un risque plus élevé qu'une simple vue autonome
additive comme celle-ci.

## 5. Fonctionnalités non portées dans cette première version

Pour rester raisonnable en taille, cette version ne couvre pas :

- Les types de question `numerical_box`, `date`, `datetime` (facile à
  ajouter en suivant le même patron que les autres types dans
  `action_generate()`).
- Le menu est maintenant disponible à **deux endroits** : sous « Rapports
  RLQ » (menu racine indépendant, garanti fonctionnel) et sous
  « Sondage » (`survey.menu_surveys` > « Rapport détaillé »). Si
  `survey.menu_surveys` n'est pas le bon identifiant sur votre instance,
  **seule cette seconde entrée** empêchera l'installation - repérez le
  `<menuitem id="menu_rlq_survey_report_in_survey_app">` dans
  `views/rlq_survey_report_views.xml` et corrigez ou supprimez-le ; le
  menu racine « Rapports RLQ » continuera de fonctionner normalement.
- Trois sorties sont maintenant disponibles depuis le formulaire, une
  fois le rapport généré : affichage à l'écran (déjà présent),
  téléchargement HTML (fichier autonome, via une pièce jointe
  temporaire), et téléchargement PDF (moteur QWeb/wkhtmltopdf standard
  d'Odoo). Le rendu PDF n'a pas pu être vérifié visuellement (aucun
  accès à wkhtmltopdf pendant l'écriture) : les listes dépliables y sont
  forcées à « toujours ouvertes » (l'interactivité n'a pas de sens en
  PDF), mais la fidélité exacte du CSS (dégradés, `flexbox`, variables
  CSS) sous l'ancien moteur WebKit de wkhtmltopdf est à vérifier en
  premier lieu lors de vos tests.
- L'export/impression en PDF (le rapport est actuellement uniquement
  consultable à l'écran, dans le widget Html du formulaire).
- Les tests automatisés (aucun test unitaire Odoo `tests/` fourni).

## 5bis. Audit sécurité et performance (v1.15.0)

**Sécurité :**
- Toutes les valeurs insérées dans le HTML du rapport (titres de
  sondage, noms, courriels, étiquettes, commentaires, coordonnées de
  contact...) passent par `echapper()` (contenu) ou `echapper_attr()`
  (attributs HTML/JavaScript) avant insertion - vérifié systématiquement
  sur `report_builder.py` et `rlq_survey_report_wizard.py`, aucune
  insertion brute trouvée.
- `lien_ancre()` assainit désormais explicitement l'identifiant d'ancre
  (lettres, chiffres, tirets et tirets bas uniquement) avant de
  l'insérer dans un attribut HTML et dans une chaîne JavaScript - une
  mesure de prudence supplémentaire, ces identifiants étant déjà
  systématiquement produits par `slug()` dans tout le module.
- Les requêtes SQL directes (`_survey_ids_annuel()`) utilisent des
  paramètres liés (`%s` avec un tuple de valeurs, jamais de
  concaténation de chaînes) - aucun risque d'injection SQL.
- **Point à surveiller** (non corrigé automatiquement, risque de
  suppression de données jugé disproportionné pour une correction
  automatique) : le téléchargement HTML crée une pièce jointe
  (`ir.attachment`) contenant des données personnelles des
  participants (courriels, coordonnées...). Cette pièce jointe persiste
  en base au-delà de la génération du rapport, même si l'enregistrement
  transitoire (wizard) qui l'a créée est éventuellement purgé par Odoo.
  Il est recommandé de nettoyer périodiquement ces pièces jointes
  (Paramètres > Technique > Pièces jointes, filtrer sur le modèle
  `rlq.survey.report.wizard`) si des rapports contenant des données
  personnelles ont été téléchargés.

**Performance :**
- `_survey_ids_annuel()` (sous-menu « Sondage annuel ») interrogeait
  individuellement TOUS les sondages du système, avec une recherche
  imbriquée par sondage - un coût qui grandit avec l'historique de
  l'instance. Remplacé par une seule requête SQL agrégée
  (GROUP BY / HAVING), sans boucle Python.
- Le calcul de « Sondages remplis (total) » et « Événements inscrits »
  par participant effectuait une requête séparée par personne. Ces deux
  décomptes sont maintenant calculés par lot (une requête groupée
  chacune, pour tous les participants du rapport) avant la boucle
  d'affichage.
- Le chargement des lignes de réponse (déjà optimisé en v1.13.0) reste
  fait une seule fois par rencontre plutôt qu'une fois par question.

**Autres points à vérifier visuellement (v1.15.0) :**
- La durée moyenne (colonne masquée par défaut) doit maintenant
  refléter uniquement les réponses au statut Terminé - comparez-la
  manuellement, pour un sondage connu, avec une moyenne calculée à la
  main sur quelques réponses terminées.
- Le champ `debug_info` (mode développeur) devrait maintenant
  apparaître dès l'ouverture du formulaire, avant même de cliquer sur
  « Générer ».
- Vérifiez qu'aucune notification ne reste affichée plus de quelques
  secondes après avoir cliqué sur « Générer ».

## 6. Suggestion de démarche de validation

1. Installer sur le staging.
2. Ouvrir Rapports RLQ > Rapport de sondage mensuel.
3. Sélectionner **un seul** sondage récent (peu de réponses) pour un
   premier essai rapide.
4. Comparer le rapport généré avec le chiffrier Excel exporté du même
   sondage (déjà en votre possession) pour confirmer que les comptes,
   moyennes et libellés concordent.
5. Élargir progressivement à plusieurs sondages pour valider la
   section Synthèse.

## 10. Étiquettes de contact des groupes (v1.102.0, NON TESTÉ)

À vérifier sur DEV (jamais la production) :

1. Un événement avec préfixe : les groupes « PRÉFIXE-Billet » ont chacun une étiquette de même nom (Contacts > filtre Étiquettes).
2. Retirer / ajouter un utilisateur dans un groupe (formulaire utilisateur, puis formulaire du groupe) : l'étiquette de son contact suit aussitôt.
3. Archiver l'utilisateur : l'étiquette disparaît ; renommer le groupe : l'étiquette est renommée.
4. Un contact SANS compte utilisateur, étiqueté à la main : son étiquette reste après « Créer / synchroniser les groupes ».
5. Tâche planifiée « RLQ Groupes d'inscrits : synchronisation des étiquettes de contact » (Réglages > Technique > Actions planifiées) : « Exécuter manuellement » ne produit aucune erreur.
6. Paramètre `rlq_survey_report.etiquettes_groupes` = 0 : plus aucune étiquette créée ni modifiée.

Hypothèses de code à confirmer : champ des membres de `res.groups` (`users` en Odoo 18, `user_ids` plus récent) et champs `in_group_*` / `sel_groups_*` du formulaire utilisateur (le code les gère par préfixe).

## 11. Suppression des étiquettes, assistant de vérification, préfixe RLQ- (v1.104.0, NON TESTÉ)

À vérifier sur DEV (jamais la production) :

1. Supprimer un groupe lié à un billet (après avoir vidé le champ du billet) : son étiquette disparaît des contacts ; une étiquette utilisée par un autre groupe reste.
2. Renommer un groupe : l'étiquette est renommée.
3. Menu Sondages > Rapports détaillés > « Vérifier les groupes et étiquettes » : l'aperçu liste les constats sans rien modifier ; « Appliquer les changements » demande une confirmation, puis l'aperçu final indique 0 constat.
4. Événement avec préfixe « JPOL26 » : les groupes créés s'appellent « RLQ-JPOL26-Visiteur »… ; saisir « Présentiel » dans le champ Groupe Odoo d'une réponse puis « Créer » donne « RLQ-Présentiel ».

Hypothèses de code à confirmer : le menu parent `menu_rlq_survey_report_in_survey_app` existe (défini dans rlq_survey_report_views.xml) ; l'attribut `confirm=` d'un bouton de pied de page d'assistant ; `markupsafe.escape` accepté dans un champ Html non assaini.
