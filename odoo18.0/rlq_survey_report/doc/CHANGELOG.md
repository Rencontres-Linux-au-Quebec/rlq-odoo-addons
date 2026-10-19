# Changelog — rlq_survey_report

## 18.0.1.111.0

**Short title:** copyright holder: Services-Linux Conseils Inc.

**Reason for the request:** « [1] Il faudrait changer le copywrite de RLQ à Services-Linux Conseils Inc, le courriel reste toujours Martial@Bigras.ca et tu peux rajouter Martial.Bigras@Services-Conseils-Linux.com »

**Changes:** `__manifest__.py` (author « Services-Linux Conseils Inc (Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com) », maintainer with both addresses, description), `static/description/index.html`, header notice of every model (`models/*.py`), footer of the generated reports (`rlq_survey_report_wizard.py`), user guide (`doc/Guide-utilisateur-rlq_survey_report.html`, version and footer): « © Services-Linux Conseils Inc — Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com » instead of « © Rencontres Linux au Québec — Martial@Bigras.ca ». No change of behavior.

**Bugs fixed:** none.

**Safeguards and edge cases:** the module's name, its technical name and its data are unchanged (only notices); the AGPL-3 license is unchanged.

**Checks:** run-all.sh (syntax, manifest, standalone tests); HTML of the guide parsed.

**Action required:** update the module (`-u rlq_survey_report`) so that Apps shows the new author.

## 18.0.1.110.0

**Short title:** user guide (/rlq_survey_report/aide) updated for the invalid e-mail addresses of registrations.

**Reason for the request:** « peux-tu me générer une mise à jour de la documentation pour le module rlq_survey_report sur le site à rlq_survey_report/aide »

**Changes:**

- `doc/Guide-utilisateur-rlq_survey_report.html` (served by `controllers/aide.py` at `/rlq_survey_report/aide`): version 18.0.1.110.0; « Nouveautés » mentions the new section; new § 13 « Adresses courriel invalides des inscriptions » (where to find the list, step by step: fix and resend, the three kinds of problem — invalid / typo / disposable —, automatic correction at registration time, failed e-mails for administrators, what is never changed); table of contents; former sections 13-15 renumbered 14-16 and every cross-reference updated; two new rows in « Dépannage » (confirmation never received, address corrected by itself); the parameter `rlq_survey_report.registration_email_autofix` points to § 13.
- `__manifest__.py`: version.

**Bugs fixed:** the guide of v1.109.0 only listed the new menu in « Nouveautés » and referred to sections whose numbers had changed.

**Safeguards and edge cases:** no code change; the page is still a static file read by the controller (no module update needed to see it… except the version shown in Apps).

**Checks:** HTML parsed (html.parser, balanced tags); every « § » and « section N » reference checked against the headings; anchors of the table of contents exist.

**Action required:** update the module (`-u rlq_survey_report`) or simply copy the new `doc/` folder; open `/rlq_survey_report/aide`.

## 18.0.1.109.0

**Short title:** invalid e-mail addresses of event registrations: detected, corrected at registration time when no letter changes, menu to fix the registration and its contact and resend the e-mails.

**Reason for the request:** « Lors de l'inscription à un événement sur Odoo, il faudrait valider si les gens ont écrit un courriel valide. Voici un exemple "mariebc33@gmail'com", il faudrait rajouter une option dans un menu afin de sortir tous les courriels d'erreurs qui a rapport au mauvais courriel et faire des corrections dans le contact de l'utilisateur et renvoyer un courriel avec le courriel corrigé. »

**Changes:**

- `models/email_check.py` (new, pure Python, same rules as `apps/_email_check.py` of nginx-tools): `check`, `suggest`, `syntax_fix` (punctuation / spaces only, no letter changed), `issue` (invalid / typo / disposable).
- `models/event_registration_email.py` (new, code in English): `event.registration` fields `rlq_email_issue` (selection, stored, indexed), `rlq_email_suggestion` (stored), `rlq_failed_mail_count`; `create()` applies `syntax_fix` BEFORE the registration exists (so the confirmation leaves to the right address) and posts a note; `action_rlq_fix_email`; `_rlq_resend_confirmation` (templates of the event's « after each registration » schedulers, otherwise `event.event_subscription`). Wizard `rlq.registration.email.fix` (+ lines): corrected address checked again, registration and contact (only if it holds the same wrong address) fixed, failed e-mails re-addressed and `mark_outgoing()`, confirmation resent, note posted.
- `views/event_registration_email_views.xml` (new): list (header and row buttons « Fix and resend »), search (invalid / typo / disposable, not cancelled, group by event), block on the registration form, wizard, action « Failed e-mails » (mail.mail in exception); menus Events > Invalid e-mails (registrations; failed e-mails for administrators) and Surveys > Detailed reports > Invalid e-mails (registrations).
- `data/ir_config_parameter_registration_email.xml` (new, noupdate): `rlq_survey_report.registration_email_autofix` = `syntax` (`off`, `typos`).
- `i18n/fr.po` (new): French of every new label, menu and message (the new code and views are in English).
- `security/ir.model.access.csv`: wizard models for `event.group_event_user`. `tests/test_email_check.py` (standalone, run by run-all.sh 1.1), `tests/test_registration_email.py` (Odoo, NOT run). Guide (§ 12, § 13), `NOTES_VALIDATION.md` (§ -72).

**Bugs fixed:** none.

**Safeguards and edge cases:** a registration is never refused; a domain name is never changed automatically (only punctuation and spaces, unless `typos`); an address with a space inside the part before « @ » is never guessed; the login of an Odoo account is never changed; the contact is changed only when it holds the same wrong address; every identifier used (`event.view_event_registration_form`, `event.event_main_menu`, `event.group_event_user`, `event.event_subscription`, `event.mail.template_ref` / `interval_type`, `mail.mail.mark_outgoing`) was checked in the Odoo 18 sources; list and search views validated against Odoo's RelaxNG schemas.

**Checks:** ruff; run-all.sh (syntax, manifest, standalone tests including test_email_check); XML parsed; views validated with Odoo 18's `list_view.rng` / `search_view.rng`; Odoo tests NOT run (no instance).

**Action required:** update the module (`-u rlq_survey_report`) on DEV first; open Events > Invalid e-mails and fix the listed registrations; check that a registration with `marie@gmail'com` is corrected; if the automatic correction is not wanted: system parameter `rlq_survey_report.registration_email_autofix` = `off`.

## 18.0.1.108.0

**Titre court :** la tâche de synchronisation périodique n'est active que si une case est cochée ; intervalle par défaut configurable ; menu « Synchronisation : sommaire ».

**Motif de la demande :** « Je vois dans les logs, toutes les 5 min, `Job 'RLQ Sondages et événements : synchronisation périodique des groupes et étiquettes' (55) starting` mais je ne pense pas l'avoir activée […] Peux-tu rajouter dans un sommaire si ces options sont activées ? Est-ce vraiment utile de synchroniser si, après chaque nouvelle inscription ou sondage soumis, on fait la synchro ? […] Il faudrait pouvoir changer le 15 min par défaut. »

**Diagnostic :** la tâche planifiée était livrée ACTIVE (v1.106.0) et Odoo écrit « Job … starting » à CHAQUE passage, même quand aucun sondage ni événement n'est coché (elle ne faisait alors qu'une requête). Ce n'était donc pas une case activée par erreur. La synchronisation immédiate existait déjà : inscription créée ou modifiée, sondage terminé (`_mark_done`), compte créé ; la périodique ne sert qu'à rattraper un changement fait hors de ces cas.

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : `_rlq_ajuster_cron()` (sondages) active la tâche seulement si au moins un sondage ou un événement a la case cochée ; appelée par `create` / `write` (`rlq_synchro_active`, `active`) / `unlink` de `survey.survey` et `event.event`. `_synchro_minutes_defaut()` : intervalle par défaut lu dans le paramètre système `rlq_survey_report.synchro_minutes_defaut` (15 s'il est absent ou invalide, jamais moins de 5), utilisé par les deux champs `rlq_synchro_minutes`.
- `data/ir_cron_synchro_sondages.xml` : champ `active` retiré (une mise à jour ne réactive plus la tâche) ; `<function … _rlq_ajuster_cron/>` aligne l'état à chaque installation ou mise à jour.
- `models/synchro_sommaire.py` (nouveau), `views/event_groupes_inscrits_views.xml`, `security/ir.model.access.csv`, `models/__init__.py` : menu Sondages > Rapports détaillés > « Synchronisation : sommaire » (lecture seule) : tâche active ou non, dernier et prochain passage, synchronisations immédiates, intervalle par défaut, sondages et événements cochés avec dernier passage et résultat.
- `doc/Guide-utilisateur-rlq_survey_report.html` (§ 12), `doc/NOTES_VALIDATION.md` (§ -71), `tests/test_groupes.py` (3 tests, NON exécutés), `docs/fr/14-rlq_survey_report.md` (nginx-tools).

**Bugs corrigés :** bruit dans le journal : une ligne « Job … starting » toutes les 5 minutes sans aucune synchronisation cochée. Correction : tâche désactivée tant que rien n'est coché.

**Garde-fous et cas limites traités :** paramètre non numérique ou inférieur à 5 : 15 ou 5 ; sondage ou événement archivé ou supprimé : la tâche est réévaluée ; la tâche ne s'éteint jamais elle-même pendant son exécution (le verrou de la ligne ir.cron n'est pas touché) ; les synchronisations immédiates ne dépendent pas de la tâche.

**Vérifications effectuées :** ruff ; run-all.sh ; syntaxe Python/XML ; tests Odoo NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; vérifier que la tâche (55) est désactivée et que le journal est silencieux ; ouvrir le menu « Synchronisation : sommaire » ; au besoin créer le paramètre `rlq_survey_report.synchro_minutes_defaut`.

## 18.0.1.107.0

**Titre court :** mise à jour des groupes et étiquettes d'un événement précis (bouton + périodique), au même menu que les sondages.

**Motif de la demande :** « Afin de mettre à jour les groupes et étiquettes, rajouter une option dans le menu afin de faire des mises à jour après un événement ou un sondage spécifique ».

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : champs de `event.event` `rlq_synchro_active`, `rlq_synchro_minutes`, `rlq_synchro_derniere`, `rlq_synchro_resultat` ; `_cron_rlq_synchroniser_evenements()` (intervalle écoulé, arrêt automatique un jour après la fin de l'événement) ; `action_rlq_synchroniser_groupes()` mémorise l'heure et le résultat.
- `data/ir_cron_synchro_sondages.xml` : la tâche (toutes les 5 minutes) traite aussi les événements.
- `views/event_groupes_inscrits_views.xml` : champs dans le bloc « Groupes des inscrits » ; liste modifiable + menu « Synchronisation périodique (événements) » avec bouton « Synchroniser maintenant » ; le menu des sondages devient « Synchronisation périodique (sondages) ».
- `tests/test_groupes.py` : test de l'intervalle et de l'arrêt automatique (NON exécuté) ; guide : section 12 complétée.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** événement sans préfixe : liste limitée aux événements à groupes ; un événement en erreur n'arrête pas les autres ; événement terminé depuis plus d'un jour : ignoré.

**Vérifications effectuées :** ruff ; run-all.sh ; syntaxe Python/XML ; tests Odoo NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; sur DEV, cocher la synchronisation d'un événement (N = 5) et vérifier le groupe d'une nouvelle inscription après ≤ 10 minutes.

## 18.0.1.106.0

**Titre court :** synchronisation périodique (N minutes) des groupes et étiquettes d'un sondage ; guide d'utilisation dans Odoo ; documentation à jour.

**Motif de la demande :** « Afin de mettre à jour les groupes et étiquettes, rajouter une option dans le menu afin de faire des mises à jour périodiques à N minutes pour un sondage spécifique » et « Mettre à jour la doc de rlq_survey_report, peux-tu créer une page web ou wiki sur Odoo ? ».

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : champs de `survey.survey` `rlq_synchro_active`, `rlq_synchro_minutes` (défaut 15, minimum 5), `rlq_synchro_derniere`, `rlq_synchro_resultat` ; `_rlq_synchroniser_groupes_et_etiquettes()` (groupes des participants + étiquettes des groupes du sondage, mémorise l'heure et le résultat) ; `action_rlq_appliquer_groupes_participants()` l'utilise (le bouton met donc aussi les étiquettes à jour) ; `_cron_rlq_synchroniser_sondages()` ; contrainte sur l'intervalle.
- `data/ir_cron_synchro_sondages.xml` (nouveau) : tâche planifiée toutes les 5 minutes.
- `views/event_groupes_inscrits_views.xml` : champs dans le bloc « Groupes des réponses » du sondage ; liste modifiable en place + recherche + menu Sondages > Rapports détaillés > « Synchronisation périodique » (responsables) avec bouton « Synchroniser maintenant » par ligne ; menu « Guide d'utilisation ».
- `controllers/aide.py` (nouveau) : page `/rlq_survey_report/aide` qui sert `doc/Guide-utilisateur-rlq_survey_report.html` (utilisateurs connectés du groupe Sondage : Utilisateur) ; aucune dépendance au module « Site web » (Odoo Community n'a pas Knowledge).
- `static/description/index.html` : page du module dans Apps. `doc/Guide-utilisateur-rlq_survey_report.html` : nouvelle section 12 « Groupes et étiquettes » (billets, réponses, mise à jour périodique, vérification, étiquettes), sections suivantes renumérotées, paramètre `etiquettes_groupes` et tâches planifiées documentés. `doc/CONTEXTE.md`, `doc/NOTES_VALIDATION.md` mis à jour.
- `tests/test_groupes.py` : intervalle respecté / sondages non cochés ignorés, intervalle minimum, bouton + étiquettes (NON exécutés).

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** un sondage en erreur n'arrête pas les autres ; une personne en erreur n'arrête pas les autres ; marge de 30 s (la tâche ne tombe jamais pile sur l'intervalle) ; sans sondage coché la tâche ne fait qu'une recherche ; intervalle < 5 refusé ; champs non copiés à la duplication d'un sondage ; page d'aide refusée aux non-utilisateurs des sondages.

**Vérifications effectuées :** ruff ; run-all.sh (156 tests autonomes OK) ; syntaxe Python/XML ; tests Odoo écrits mais NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; cocher la synchronisation d'un sondage de DEV avec N = 5, répondre, constater le groupe après ≤ 10 minutes ; ouvrir Sondages > Rapports détaillés > Guide d'utilisation.

## 18.0.1.105.0

**Titre court :** événements : option « Répéter tous les N inscriptions » (courriel à N, 2N, 3N…).

**Motif de la demande :** « Rajoute une option dans les événements avoir de recevoir un courriel à tous les N inscriptions envoyé au courriel par défaut dans Odoo (ou autres spécifiés) ».

**Détail des modifications :**

- `models/event_inscriptions_alerte.py` : champs `rlq_alerte_repeter` (case) et `rlq_alerte_palier` (dernier multiple avisé, lecture seule) ; `_rlq_envoyer_alerte_si_atteint()` utilise `report_builder.palier_alerte()` ; `write()` remet envoyée/palier à zéro quand N, l'activation ou la répétition change. Destinataire inchangé : courriel de l'événement, puis paramètre système `rlq_survey_report.courriel_inscriptions`, puis courriel par défaut d'Odoo (société).
- `models/report_builder.py` : `palier_alerte(nombre, seuil, repeter, dernier)` (fonction pure) ; `html_alerte_inscriptions(..., repeter)` : texte adapté.
- `views/event_inscriptions_alerte_views.xml` : cases « Répéter tous les N inscriptions » et « Dernier palier avisé ».
- `tests/` : test_report_builder (paliers, valeurs invalides, corps), test_wizard (répétition ; NON exécuté).

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** sans la case, le comportement est inchangé (un seul courriel) ; plusieurs multiples franchis d'un coup (import) : un seul courriel, le plus récent ; annulation puis nouvelle inscription : rien avant le multiple suivant ; verrou de ligne conservé (pas de doublon) ; N < 1 ignoré ; aucune donnée personnelle dans le courriel ; une erreur d'envoi n'empêche jamais l'inscription.

**Vérifications effectuées :** ruff ; test_report_builder (156 tests autonomes OK) ; tests Odoo écrits mais NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module ; sur DEV : cocher l'avertissement et « Répéter », mettre N = 2, inscrire 4 personnes et constater 2 courriels (à 2 et à 4).

## 18.0.1.104.0

**Titre court :** suppression du groupe = suppression de l'étiquette ; assistant « Vérifier les groupes et étiquettes » avec confirmation ; groupes créés en « RLQ- ».

**Motif de la demande :** « Si le groupe est effacé, il faudrait que l'étiquette aussi le soit. Si le groupe est renommé, il faudrait que les étiquettes le soit aussi. Peut-être prévoir une option dans le menu des sondages afin de vérifier tout les sondages. Demande une confirmation avant de faire les changements. Au lieu de JPOL-, utilise RLQ- pour le début des groupes à créer. »

**Détail des modifications :**

- `models/groupes_etiquettes.py` : `res.groups.unlink()` supprime l'étiquette du groupe (sauf si un autre groupe s'en sert encore) ; `_rlq_renommer_etiquette()` ; le renommage du groupe renomme déjà l'étiquette (1.102, conservé).
- `models/verification_groupes.py` (nouveau) : assistant `rlq.groupes.verification` (TransientModel) : aperçu SANS écriture (groupes de billets manquants, étiquettes à créer/renommer, étiquettes de contacts à poser/retirer, participants de sondages à ajouter/retirer — estimation), puis `action_appliquer()` qui réutilise les opérations des boutons existants (événements, sondages, étiquettes).
- `views/event_groupes_inscrits_views.xml` : formulaire de l'assistant, action et menu Sondages > Rapports détaillés > « Vérifier les groupes et étiquettes » (responsables des sondages) ; bouton « Appliquer les changements » avec boîte de confirmation (`confirm=`) ; placeholder du préfixe mis à jour.
- `security/ir.model.access.csv` : accès de l'assistant (responsable des sondages, administrateur).
- `models/report_builder.py` : `nom_groupe_rlq()` ; `nom_groupe_billet()` produit « RLQ-<préfixe>-<billet> ». `models/event_groupes_inscrits.py` : `name_create` de `res.groups` préfixe « RLQ- » (jamais doublé). Les groupes existants ne sont PAS renommés.
- `tests/` : test_report_builder (préfixe RLQ-), test_groupes (suppression, étiquette partagée, aperçu puis application) ; `__manifest__.py` : 18.0.1.104.0.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** l'aperçu ne modifie rien et l'application exige un clic de confirmation ; bouton masqué s'il n'y a rien à changer ; étiquette partagée par un autre groupe conservée ; erreur d'un événement/sondage journalisée sans arrêter les autres ; « RLQ- » seul (sans nom) ne crée aucun groupe ; la suppression d'un groupe n'échoue jamais à cause de l'étiquette.

**Vérifications effectuées :** ruff ; tests autonomes (report_builder) ; tests Odoo écrits mais NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module ; sur DEV : supprimer un groupe de test et constater la disparition de son étiquette ; ouvrir le menu « Vérifier les groupes et étiquettes », lire l'aperçu, annuler, puis refaire et confirmer.

## 18.0.1.103.0

**Titre court :** bouton « Appliquer les groupes aux participants » sur le sondage.

**Motif de la demande :** « Lorsque je rajoute des groupes dans les sondages sur une réponse spécifique, il faudrait avoir une option afin de mettre à jour tous les groupes de tous ceux ayant soumis un sondage spécifique. »

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : `survey.survey.action_rlq_appliquer_groupes_participants()` : pour chaque personne qui a terminé le sondage (une fois par personne), appelle `_rlq_appliquer_groupes_sondage()` (inscription liée, refus, annulation et « dernière réponse seulement » respectés) ; notification : participants mis à jour, sans compte, erreurs.
- `views/event_groupes_inscrits_views.xml` : bouton dans le formulaire du sondage (groupe « Groupes des réponses »). Les étiquettes de contact suivent automatiquement (1.102).
- `tests/test_groupes.py` : test_appliquer_les_groupes_a_tous_ceux_qui_ont_deja_repondu ; `__manifest__.py` : 18.0.1.103.0.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** idempotent (relançable sans doublon) ; personnes sans compte portail comptées et ajoutées plus tard à la création du compte ; une erreur sur une personne n'arrête pas les autres ; participants anonymes (sans contact) ignorés ; retirer un groupe d'une réponse ne retire PAS le groupe aux personnes qui l'ont déjà (seul l'ajout est rétroactif).

**Vérifications effectuées :** ruff ; test Odoo écrit mais NON exécuté (aucune instance).

**Action requise de ma part :** mettre à jour le module ; sur DEV : lier un groupe à une réponse d'un sondage déjà répondu, puis cliquer « Appliquer les groupes aux participants » dans le formulaire du sondage.

## 18.0.1.102.0

**Titre court :** étiquettes de contact qui reflètent les groupes d'inscrits, tenues à jour.

**Motif de la demande :** « Serait-il intéressant de créer des tags associés au groupe que tu as créé ? Quand on regarde les contacts, on voit des étiquettes seulement et non les groupes, et on peut faire des recherches facilement par étiquettes mais pas par groupe. Il faut s'assurer que s'il y a des changements dans les groupes, la liste des tags est mise à jour. Pour notre club, ainsi tous les membres du groupe peuvent voir les groupes et étiquettes dont les gens font partie. »

**Détail des modifications :**

- `models/groupes_etiquettes.py` (nouveau) : `res.groups.rlq_category_id` (étiquette `res.partner.category` de même nom, trouvée ou créée) ; `_rlq_assurer_etiquette()` et `_rlq_synchroniser_etiquette()` : le contact de chaque utilisateur membre du groupe porte l'étiquette, le contact d'un utilisateur qui n'est plus membre la perd.
- Déclencheurs : groupe lié à un billet ou à une réponse de sondage (création / modification de `rlq_group_id`) ; `res.users.create` et `write` (groupes, archivage, contact ; y compris les champs « in_group_ » / « sel_groups_ » du formulaire utilisateur) ; `res.groups.write` (membres, renommage : l'étiquette est renommée) ; bouton « Créer / synchroniser les groupes » de l'événement ; tâche planifiée quotidienne `_cron_rlq_synchroniser_etiquettes` (filet de sécurité).
- `data/ir_cron_etiquettes_groupes.xml` : la tâche planifiée et le paramètre système `rlq_survey_report.etiquettes_groupes` (1 ; 0 = désactivé) ; `__manifest__.py` : 18.0.1.102.0 ; `tests/test_groupes.py` : 7 tests.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :** seuls les groupes liés à un billet ou à une réponse reçoivent une étiquette (jamais « Utilisateur interne » & co) ; l'étiquette est GÉRÉE par le groupe, mais les contacts SANS compte utilisateur ne sont jamais touchés (une étiquette posée à la main leur reste) ; une étiquette existante du même nom est réutilisée ; un groupe supprimé laisse son étiquette (non supprimée) ; toute erreur est journalisée sans bloquer l'opération d'origine ; les comptes archivés perdent l'étiquette.

**Vérifications effectuées :** ruff ; tests Odoo écrits mais NON exécutés (aucune instance). Points à confirmer sur DEV : `res.groups.users` / `user_ids` et `res.partner.category` (champ `category_id` du contact).

**Action requise de ma part :** mettre à jour le module (`odoo-update-module.sh`), puis sur DEV : ouvrir un événement avec préfixe > « Créer / synchroniser les groupes » ; vérifier dans Contacts le filtre par étiquette « JPOL26-… » ; retirer un utilisateur d'un groupe à la main et constater que l'étiquette suit.

## 18.0.1.101.0

**Titre court :** créer un groupe depuis un formulaire (nom saisi puis « Créer ») ne plante plus.

**Motif de la demande :** « Lorsque je crée un groupe dans le formulaire des sondages, j'ai cette erreur : null value in column "name" of relation "res_groups" violates not-null constraint ».

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : classe `ResGroupsCreationRapide` (héritage de `res.groups`) : `name_create(name)` crée le groupe avec son nom et retourne `(id, nom affiché)`.
- `tests/test_groupes.py` : `test_creation_rapide_d_un_groupe_par_son_nom` ; `__manifest__.py` : 18.0.1.101.0.

**Bugs corrigés :** symptôme : « Créer » dans le champ « Groupe Odoo » (réponses suggérées d'une question) insérait `INSERT INTO res_groups (create_date, …)` sans nom → erreur PostgreSQL « null value in column "name" ». Diagnostic (probable, non exécuté ici) : le `name_create` standard écrit dans le champ de nom affiché de `res.groups` (calculé, `full_name`), pas dans `name`. Correction : `name_create` explicite qui écrit `name`.

**Garde-fous et cas limites traités :** seul `name_create` est redéfini (le formulaire complet « Créer et modifier… » n'est pas touché) ; le droit de créer un groupe reste celui d'Odoo (administrateur).

**Vérifications effectuées :** ruff ; 151 tests autonomes ; test Odoo écrit mais NON exécuté (aucune instance).

**Action requise de ma part :** mettre à jour le module (`odoo-update-module.sh`) puis recréer un groupe depuis le formulaire du sondage.

## 18.0.1.100.0

**Titre court :** refaire le sondage : seule la dernière réponse compte pour les groupes.

**Motif de la demande :** « Si quelqu'un répond « Oui » puis refait le sondage avec « Non », il NE DOIT PAS rester dans le groupe. »

**Détail des modifications :**

- `models/event_groupes_inscrits.py` : `survey.user_input._rlq_groupes_reponses(contact, sondages)` retourne les groupes de TOUTES les réponses terminées de la personne et ceux de sa DERNIÈRE réponse terminée à chaque sondage. `event.registration._rlq_groupes_de_inscription()` s'en sert : groupes voulus = ceux du billet + ceux de la dernière réponse ; groupes concernés = ceux du billet + ceux de toutes les réponses (donc retirés si la dernière réponse ne les donne plus).
- `survey.user_input._rlq_appliquer_groupes_sondage()` : sans inscription liée, ajoute les groupes de la dernière réponse et retire ceux des réponses précédentes. Ne fait rien si le sondage n'a aucune réponse liée à un groupe.
- `tests/test_groupes.py` : test_oui_puis_non_retire_du_groupe (avec et sans inscription liée) ; `__manifest__.py` : 18.0.1.100.0.

**Bugs corrigés :** la 1.99 gardait le groupe après un « Oui » suivi d'un « Non » (symptôme signalé par l'utilisateur ; cause : les groupes n'étaient que ajoutés, jamais retirés, pour les sondages sans annulation).

**Garde-fous et cas limites traités :** la dernière réponse = la participation terminée dont l'identifiant est le plus grand ; le groupe du billet n'est jamais touché par un changement de réponse ; une participation sans contact (anonyme) ne change rien.

**Vérifications effectuées :** ruff ; 151 tests autonomes ; tests Odoo écrits mais NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; sur DEV, répondre « Oui » puis « Non » avec un compte de test.

## 18.0.1.99.0

**Titre court :** une inscription annulée retire du groupe ; une réponse au sondage peut ajouter à un groupe.

**Motif de la demande :** « [1] Une inscription annulée DOIT retirer la personne du groupe. [2] Dans le module sondage, il faudrait rajouter une colonne pour rajouter un groupe si les gens ont répondu à une question. Par exemple, « Serez-vous présent à l'ÉTS ? » = oui = JPOL26-Présentiel. »

**Détail des modifications :**

- `models/event_groupes_inscrits.py` :
  - `event.registration._rlq_synchroniser_groupe()` réécrite : pour chaque personne, groupes « concernés » (billet + réponses aux sondages liés, toutes ses inscriptions) et « voulus » (inscriptions actives `open` / `done`, sans refus) ; ajout des voulus, retrait de concernés − voulus. Une inscription annulée ou refusée retire donc la personne, sauf si une autre inscription active la lui donne encore. Nouvelles méthodes `_rlq_sondages()` (sondage du billet, puis de l'événement s'il existe) et `_rlq_groupes_de_inscription()`.
  - `survey.question.answer.rlq_group_id` (« Groupe Odoo ») : colonne des réponses suggérées d'une question ; on peut taper un nom puis « Créer » pour créer le groupe.
  - `survey.user_input._mark_done()` étendu : à la fin du sondage, la personne est ajoutée aux groupes des réponses choisies (via la synchronisation des inscriptions liées à ce sondage — refus et annulation respectés — sinon ajout simple).
  - `res.users.create()` : un compte créé après coup rattrape inscriptions ET réponses de sondage.
- `views/event_groupes_inscrits_views.xml` : colonne « Groupe Odoo » dans la liste des réponses du formulaire de question (`survey.survey_question_form`).
- `tests/test_groupes.py` : 4 tests Odoo ajoutés (annulation, réponse « Oui » puis annulation, réponse « Non », sondage sans inscription) ; `__manifest__.py` : 18.0.1.99.0.

**Bugs corrigés :** la 1.98 laissait la personne dans le groupe après une annulation (voulu à l'époque, corrigé sur demande).

**Garde-fous et cas limites traités :**
- Une personne avec deux inscriptions (même billet ou non) garde un groupe tant qu'une inscription active le lui donne.
- Changer sa réponse plus tard (nouveau sondage « Non ») ne retire pas le groupe ; seule l'annulation ou le refus de l'inscription liée le fait.
- Sondage sans inscription liée (aucun billet n'y pointe) : ajout simple, sans retrait automatique.
- Jamais de blocage de la soumission du sondage (erreurs journalisées sans nom ni courriel). Personne sans compte portail : rattrapée à la création du compte.

**Vérifications effectuées :** ruff ; 151 tests autonomes ; tests Odoo écrits mais NON exécutés (aucune instance).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; sur DEV, ouvrir la question « Serez-vous présent à l'ÉTS ? », choisir le groupe de la réponse « Oui », puis vérifier avec un compte de test (réponse, annulation) — voir NOTES_VALIDATION.md, section -67.

## 18.0.1.98.0

**Titre court :** groupes Odoo des inscrits, un par type de billet (JPOL26-Visiteur, JPOL26-Bénévole, JPOL26-Commanditaire).

**Motif de la demande :** « Si les gens sont inscrits à l'événement « Journée portes ouvertes sur Linux 2026 » ayant comme ticket Visiteur = JPOL26-Visiteur, Bénévole = JPOL26-Bénévole, Commanditaire = JPOL26-Commanditaire. Idéalement, il faudrait choisir le groupe dans la création de l'événement, et le créer s'il n'existe pas. » (but : ajouter les 150 à 250 inscrits à un canal de discussion sans le faire à la main, et pouvoir retirer quelqu'un qui ne veut pas y être).

**Détail des modifications :**

- `models/event_groupes_inscrits.py` (nouveau) :
  - `event.event.rlq_groupe_prefixe` (ex. « JPOL26 ») ; `create()` / `write()` créent les groupes manquants ; bouton `action_rlq_synchroniser_groupes()` (« Créer / synchroniser les groupes »).
  - `event.event.ticket.rlq_group_id` : groupe du billet ; trouvé par son nom « <préfixe>-<billet> » ou CRÉÉ s'il n'existe pas ; un autre groupe existant peut être choisi à la main.
  - `event.registration` : `rlq_groupe_refus` (« Ne pas ajouter au groupe ») ; `create()` / `write()` (état, billet, contact, refus) ajoutent l'utilisateur du contact au groupe de son billet (inscription `open` ou `done`), ou l'en retirent si refus.
  - `res.users.create()` : un compte portail créé APRÈS l'inscription (première connexion) est ajouté aux groupes de ses inscriptions.
- `models/report_builder.py` : fonction pure `nom_groupe_billet(prefixe, billet)`.
- `views/event_groupes_inscrits_views.xml` (nouveau) : bloc « Groupes des inscrits » et bouton sur l'événement, colonne « Groupe des inscrits » dans la liste des billets, case de refus sur l'inscription.
- `tests/test_report_builder.py` (3 tests), `tests/test_groupes.py` (nouveau, Odoo) ; `__manifest__.py` : version 18.0.1.98.0 et nouvelle vue.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :**
- Idempotent : relancer le bouton ne crée aucun doublon (groupe cherché par son nom avant d'être créé).
- Jamais de blocage : une erreur de groupe est journalisée (sans courriel ni nom) et l'inscription, le billet ou la création du compte continuent.
- Inscription sans compte portail : ignorée pour l'instant, rattrapée à la création du compte ; brouillons et annulations jamais ajoutés ; billet sans groupe : rien.
- Retirer quelqu'un du groupe à la main ne suffit pas (une synchronisation le rajouterait) : cocher « Ne pas ajouter au groupe ». Une inscription annulée ne retire pas la personne du groupe.
- Le canal de discussion n'est pas créé par ce module : associer chaque groupe au canal (Discuss > canal > « Groupes à abonner automatiquement »).

**Vérifications effectuées :** ruff ; 151 tests autonomes (3 nouveaux) ; tests Odoo `test_groupes.py` écrits mais NON exécutés (aucune instance Odoo ici) ; XML de la vue bien formé.

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`) ; sur DEV, vérifier les points de la section -67 de `doc/NOTES_VALIDATION.md` (surtout : un compte portail peut recevoir un groupe personnalisé, et le canal s'abonne bien aux membres du groupe) ; renseigner le préfixe « JPOL26 » sur l'événement, cliquer sur le bouton, puis associer les groupes aux canaux.

## 18.0.1.97.0

**Titre court :** le courriel « sondage complété » reprend le tableau de la touche « I ».

**Motif de la demande :** « Oui, je veux le format complet dans le courriel (comme avec « I ») ».

**Détail des modifications :**

- `models/report_builder.py` : fonction pure `tableau_inscriptions_html()` ; `html_alerte_sondage()` reçoit `dernieres` (tableau « Dernières inscriptions (30 jours) » : date, personne, billet, état, puis sondage complété avec sa date, « NON terminé », ou « AUCUN — inscription non confirmée »).
- `models/event_inscriptions_alerte.py` : `event.event._rlq_dernieres_inscriptions(limite=10)` (heures dans le fuseau de l'événement) ; utilisée par `_rlq_alerte_sondage_complete()`.
- `__manifest__.py` : version 18.0.1.97.0.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :**
- Les 10 dernières inscriptions des 30 derniers jours seulement ; jamais de réponses ni d'adresse de courriel ; tout est échappé. Sans sondage attendu pour le billet : « — ».
- Sondage retrouvé par contact puis par courriel (comparaison seulement), en préférant la participation terminée.

**Vérifications effectuées :** ruff ; 148 tests autonomes (1 nouveau) ; 1 assertion ajoutée dans `tests/test_wizard.py` (non exécutable sans Odoo).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`).

## 18.0.1.96.0

**Titre court :** courriel à l'organisateur quand un sondage associé à un événement est complété.

**Motif de la demande :** « J'aimerais recevoir aussi si le sondage associé à un événement a été complété : comme lorsque j'appuie sur « I » » (la touche I de app-log-live.py montre, pour chaque inscription, le sondage complété).

**Détail des modifications :**

- `models/event_inscriptions_alerte.py` :
  - `event.event` : nouveau champ `rlq_alerte_sondage` (case « Avertir aussi à chaque sondage complété ») ; méthodes `_rlq_alerte_sondage_complete()`, `_rlq_surveys_associes()` ; l'envoi (`_rlq_destinataire_alerte()`, `_rlq_envoyer_courriel()`, `_rlq_url()`, `_rlq_debut_texte()`) est mis en commun avec l'avertissement d'inscriptions (même destinataire : courriel de l'événement, paramètre `rlq_survey_report.courriel_inscriptions`, courriel de la société).
  - `survey.user_input` : champ `rlq_alerte_evenement_envoyee` ; `_mark_done()` étendu ; `_rlq_alerte_sondage_evenement()`.
- `models/report_builder.py` : fonctions pures `sujet_alerte_sondage()` et `html_alerte_sondage()`.
- `views/event_inscriptions_alerte_views.xml` : la case est ajoutée au bloc (désormais « Avertissements par courriel (inscriptions, sondages) ») ; elle est indépendante de la case d'inscriptions.
- `__manifest__.py` : version 18.0.1.96.0. Guide utilisateur, NOTES_VALIDATION.md (section -66) et CONTEXTE.md mis à jour.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :**
- Sondages associés = celui de chaque type de billet de l'événement (`rlq_survey_id`) et le sondage de l'événement (`survey_id`) seulement si ce champ existe.
- Un seul courriel par participation (`rlq_alerte_evenement_envoyee`) ; jamais pour un essai (`test_entry`), ni pour une participation non terminée, ni pour un sondage non associé à un événement avec la case cochée.
- Le courriel donne le nom de la personne, son billet, le sondage et l'avancement (sondages complétés sur inscriptions confirmées) ; jamais ses réponses ni son courriel. Supprimé des courriels sortants après envoi.
- La personne est retrouvée par son contact, sinon par son courriel (comparaison seulement) ; sans inscription retrouvée, le nom du contact du sondage est utilisé.
- Aucune adresse valide : avertissement dans les journaux. Toute erreur est journalisée dans un `savepoint` : la soumission du sondage n'est JAMAIS bloquée.

**Vérifications effectuées :** ruff : aucun problème ; XML bien formé ; 147 tests autonomes (2 nouveaux). 2 tests Odoo ajoutés dans `tests/test_wizard.py` (classe `TestRlqAlerteSondage`) mais NON exécutés (pas d'instance Odoo ici).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`), cocher « Avertir aussi à chaque sondage complété » sur l'événement, terminer un sondage de billet et vérifier la réception ; voir NOTES_VALIDATION.md section -66.

## 18.0.1.95.0

**Titre court :** un événement peut avertir par courriel quand il atteint N inscriptions.

**Motif de la demande :** « Il faudrait que sur certains événements avoir une option afin de recevoir un courriel après N inscriptions, envoyé au courriel par défaut dans Odoo (ou une autre à spécifier dans les paramètres systèmes). »

**Détail des modifications :**

- **Nouveau fichier** `models/event_inscriptions_alerte.py` :
  - `event.event` : champs `rlq_alerte_active` (case, décochée par défaut), `rlq_alerte_seuil` (N, défaut 50), `rlq_alerte_courriel` (adresse(s) propres à l'événement), `rlq_alerte_envoyee` (date d'envoi, lecture seule), `rlq_inscriptions_comptees` (calculé, affichage) ; méthodes `_rlq_verifier_alerte()`, `_rlq_envoyer_alerte_si_atteint()` et `_creer_parametre_courriel_inscriptions_si_absent()` ; `write()` réarme l'avertissement si le seuil ou la case change.
  - `event.registration` : `create()` et `write()` (état ou événement modifié) vérifient le seuil après le traitement natif.
- **Destinataire**, par ordre : courriel de l'événement, paramètre système `rlq_survey_report.courriel_inscriptions` (plusieurs adresses permises, séparées par des virgules), courriel par défaut d'Odoo (celui de la société de l'événement).
- `models/report_builder.py` : fonctions pures `courriels_valides()`, `destinataire_alerte_inscriptions()`, `sujet_alerte_inscriptions()`, `html_alerte_inscriptions()`.
- **Nouveaux** `views/event_inscriptions_alerte_views.xml` (bloc « Avertissement par courriel après N inscriptions » sur le formulaire de l'événement) et `data/ir_config_parameter_courriel_inscriptions.xml` (crée le paramètre, vide, seulement s'il est absent).
- `__manifest__.py` : version 18.0.1.95.0, deux fichiers de données ajoutés. `models/__init__.py` : import du nouveau fichier. Guide utilisateur, CONTEXTE.md et NOTES_VALIDATION.md mis à jour.

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :**
- Compte seulement les inscriptions confirmées (`open`) ou présentes (`done`) ; brouillons et annulations ne comptent pas ; une inscription confirmée plus tard (brouillon → confirmée) est comptée à ce moment.
- Un seul courriel par seuil (`rlq_alerte_envoyee`) ; modifier N ou recocher la case le réarme ; si le seuil est déjà atteint à ce moment, le courriel part tout de suite.
- Verrou de ligne (`SELECT … FOR UPDATE`) : deux inscriptions simultanées n'envoient pas deux courriels.
- Jamais d'erreur remontée à la personne qui s'inscrit : l'envoi est dans un `savepoint` avec `try/except` ; un échec est journalisé et l'inscription n'est jamais bloquée.
- Aucune adresse valide : avertissement dans les journaux, rien d'envoyé, nouvelle tentative à l'inscription suivante.
- Le courriel ne contient aucune donnée personnelle (ni nom ni courriel des inscrits : Loi 25), tout est échappé, et il est supprimé des courriels sortants après envoi ; une note « Avertissement envoyé à … » est ajoutée au fil de l'événement.
- Seuil inférieur à 1 refusé quand la case est cochée.
- Le paramètre système est créé vide seulement s'il est absent (même méthode que le mot de passe par défaut : jamais écrasé).

**Vérifications effectuées :** ruff : aucun problème ; XML bien formé ; 145 tests autonomes (4 nouveaux). 5 tests Odoo ajoutés dans `tests/test_wizard.py` (classe `TestRlqAlerteInscriptions`) mais NON exécutés (pas d'instance Odoo ici).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`), ouvrir un événement, cocher « Avertir par courriel après N inscriptions », fixer N et vérifier la réception ; renseigner au besoin le paramètre `rlq_survey_report.courriel_inscriptions` ; voir NOTES_VALIDATION.md section -65.

## 18.0.1.94.0

**Titre court :** le participant peut recevoir par courriel une copie de ses réponses dès qu'il termine un sondage (activable sondage par sondage).

**Motif de la demande :** « Lorsque l'on remplit un sondage sur Odoo, est-il possible de recevoir par courriel les réponses que nous avons soumises ? Rajoute cette fonctionnalité dans le module rlq_survey_report. »

**Détail des modifications :**

- **Nouveau fichier** `models/survey_reponses_courriel.py` :
  - `survey.survey` : champs `rlq_envoyer_reponses` (case, décochée par défaut) et `rlq_modele_courriel_reponses` (modèle de courriel au choix).
  - `survey.user_input` : champs `rlq_reponses_html` (calculé, questions et réponses en HTML) et `rlq_courriel_reponses_envoye` (date de mise en file) ; méthode `rlq_envoyer_reponses_courriel(force=False)` ; surcharge de `_mark_done()` qui appelle l'envoi après le traitement natif.
- **Nouveau** `data/mail_template_reponses.xml` : modèle « Sondage : vos réponses (rlq_survey_report) » (`noupdate="1"`), modifiable dans Modèles de courriel.
- `models/report_builder.py` : fonction pure `html_reponses_courriel()` (échappement, retours à la ligne, questions sans réponse omises).
- `views/rlq_survey_report_views.xml` : bloc « Courriel de réponses au participant » sur le formulaire du sondage.
- `__manifest__.py` : version 18.0.1.94.0, fichier de données ajouté. `models/__init__.py` : import du nouveau fichier.
- Guide utilisateur : nouvelle sous-section sous « Un sondage par type de billet ».

**Bugs corrigés :** aucun.

**Garde-fous et cas limites traités :**
- Jamais d'erreur remontée au participant : l'envoi est dans un `savepoint` avec `try/except` ; un échec est journalisé (« courriel de réponses non envoyé ») et la soumission n'est jamais bloquée.
- Pas pour une entrée de test (`test_entry`), pas si la participation n'est pas terminée, pas deux fois (champ de date, `force=True` pour renvoyer manuellement), pas sans adresse (sondage anonyme).
- Les réponses libres sont échappées (aucun HTML injecté dans le courriel).
- `auto_delete` : le courriel est supprimé des courriels sortants après envoi, pour ne pas conserver les réponses (Loi 25).
- Le modèle est lu en `sudo()` : un participant public n'a pas accès aux modèles de courriel.

**Vérifications effectuées :** ruff : aucun problème ; XML bien formé ; 141 tests autonomes (4 nouveaux). 4 tests Odoo ajoutés dans `tests/test_wizard.py` (classe `TestRlqCourrielReponses`) mais NON exécutés (pas d'instance Odoo ici).

**Action requise de ma part :** mettre à jour le module (`-u rlq_survey_report`), cocher la case sur un sondage, répondre avec une adresse de courriel et confirmer la réception ; voir NOTES_VALIDATION.md section -64.

## 18.0.1.93.0

**Titre court :** le mot de passe par défaut n'est plus jamais écrasé (le paramètre n'est créé que
s'il est absent) ; un participant dont le nom se termine par une parenthèse est maintenant
anonymisé ; plus de lien ✉ ni de « [courriel masqué] » dans les listes d'un rapport anonymisé.

**Motif de la demande :** trois problèmes signalés après l'installation de la v1.92.0 : le mot de
passe défini dans `rlq_survey_report.mot_de_passe_defaut` a été perdu ; un participant dont le nom
contenait des parenthèses (« Andre Courchesne (visiblair.com) ») restait visible dans un rapport
HTML anonymisé ; un rapport anonymisé affichait encore des liens ✉ et « [courriel masqué] ».

**Détail des modifications :**

- **[1]** `data/ir_config_parameter_mot_de_passe.xml` ne contient plus de `<record>` mais une balise
  `<function>` (hors `noupdate`) qui appelle la nouvelle méthode
  `_creer_parametre_mot_de_passe_si_absent()` : elle crée le paramètre avec le marqueur
  `!CHANGE-MOI@` SEULEMENT s'il n'existe pas ; une valeur existante, même vide, n'est jamais
  remplacée. Elle détache aussi l'ancien identifiant XML créé par les versions 1.75 à 1.92, pour
  que le paramètre ne soit plus supprimé avec le module à la désinstallation.
- **[2]** Nouvelles fonctions pures `motif_nom_complet()` et `remplacer_nom_complet()` dans
  `report_builder.py` ; `_anonymiser_html()` les utilise à la place de la boucle `\b…\b`.
- **[3]** `_compute_report()` ne remplit plus le dictionnaire `emails` en mode anonymisé : plus de
  lien ✉, plus de suffixe « - courriel » dans les infobulles, plus de champ « Courriels (N) » à copier.

**Bugs corrigés :**
- **[1]** Symptôme : le mot de passe par défaut est redevenu le marqueur après l'installation de la
  v1.92.0. Diagnostic : `noupdate="1"` ne protège que contre une mise à jour (`-u`) ; quand Odoo
  traite un module en mode « init » (installation avec `-i`, ou désinstallation puis réinstallation),
  il recharge les données EN IGNORANT `noupdate`. La commande exacte utilisée n'a pas pu être
  déterminée. Correction : le paramètre n'est plus géré par un enregistrement XML.
- **[2]** Symptôme : un participant nommé « Nom (organisation.com) » restait lisible, les autres
  étaient masqués. Diagnostic : les limites de mot `\b…\b` n'existent pas entre « ) » et un espace
  ou un « < » : le motif ne correspondait JAMAIS à un nom finissant par une parenthèse (ni par un
  point, comme « Jr. », ni à un nom commençant par une parenthèse). Correction : lookarounds « pas
  collé à un caractère de mot », identiques à `\b` pour un nom ordinaire.
- **[3]** Symptôme : un lien ✉ (vers `mailto:[courriel masqué]`) et des « [courriel masqué] »
  apparaissaient dans un rapport anonymisé. Diagnostic : le courriel était masqué APRÈS coup, mais les
  listes continuaient à le recevoir. Correction : il n'est plus fourni aux listes.

**Garde-fous et cas limites traités :**
- La méthode de création ne lève jamais d'erreur (savepoint, exception journalisée) : elle ne peut pas
  empêcher le chargement du module.
- La balise `<function>` est placée HORS de `noupdate` : en noupdate, elle ne serait pas exécutée lors
  d'une mise à jour, et le paramètre ne serait jamais créé sur une base qui ne l'avait pas encore.
- Le remplacement des noms garde le comportement de `\b` pour un nom ordinaire : « F » n'est jamais
  remplacé à l'intérieur de « Filtre », « Jean » jamais à l'intérieur de « Jeanne ».
- Le remplacement est littéral : aucun caractère du pseudonyme n'est interprété.
- « [courriel masqué] » peut encore apparaître dans UN seul cas : une adresse de courriel écrite dans
  une réponse libre. La supprimer silencieusement laisserait un trou dans la phrase.

**Constats NON modifiés (à décider) :**
- `rlq_survey_report.url_aide` (`data/ir_config_parameter_aide.xml`) repose encore sur un `<record>`
  `noupdate="1"` : une URL d'aide modifiée serait remplacée de la même façon par une installation en
  mode « init ». Même correction possible.

**Vérifications effectuées :** ruff : aucun problème ; syntaxe Python et XML ; 137 tests autonomes
(13 nouveaux). Vérifié que le nouveau test du cas signalé ÉCHOUE avec l'ancien code (le nom restait
visible). La vraie méthode `_anonymiser_html()`, extraite du fichier livré et exécutée sans Odoo, masque
le nom à parenthèses, son ancre, son courriel et un courriel dans une réponse libre, et conserve le
courriel d'attribution du pied de page. NON vérifié (aucune instance Odoo) : l'exécution de la balise
`<function>` au chargement du module, et les 5 nouveaux tests de `tests/test_wizard.py` (4 sur le
paramètre, 1 sur un rapport anonymisé complet).

**Action requise :** mettre à jour le module (-u), puis REDÉFINIR le mot de passe par défaut (la valeur
perdue ne peut pas être récupérée par le module ; une sauvegarde de la base la contient peut-être).
Pour vérifier la correction : relancer ensuite une installation (`-i`) ou réinstaller le module, et
constater que la valeur est conservée. Régénérer un rapport anonymisé : plus de ✉, plus de
« [courriel masqué] » dans les listes, et le nom à parenthèses masqué.

---

## 18.0.1.92.0

**Titre court :** liste « Historique et fichiers déjà générés » sans colonne en double et
avec une colonne « Télécharger » élargie ; script `run-all.sh` (ruff, tests autonomes, base
PostgreSQL de test et tests Odoo) ; guide utilisateur HTML mis à jour ; code validé avec ruff.

**Motif de la demande :** batch de 4 demandes - voir le détail par point.

**Détail des modifications :**

- **[1]** `views/rlq_survey_report_views.xml` : la colonne « Nom du fichier » n'est plus affichée
  (`column_invisible="1"`) - elle doublait « Télécharger », qui affiche déjà le nom. Le champ
  reste dans la vue, car le widget binaire en a besoin (attribut `filename`). Nouvelle feuille de
  style `static/src/css/historique_fichiers.css`, déclarée dans `assets` du manifeste : colonne
  « Télécharger » élargie (46 rem) et nom du fichier qui passe à la ligne, pour que le nom
  complet soit toujours visible.
- **[2]** Nouveaux fichiers : `run-all.sh` (ruff, syntaxe et manifeste, tests autonomes, puis
  création d'une base PostgreSQL de test et tests Odoo, base supprimée ensuite), `ruff.toml`,
  `scripts/run-all.conf.exemple`, `scripts/LISEZMOI.md`, `doc/run-all.changelog.txt`.
- **[3]** `doc/Guide-utilisateur-rlq_survey_report.html` : guide réécrit à partir de l'ancien
  guide (qui décrivait la v1.32.0), du changelog et des libellés réels du formulaire.
- **[4]** Validation avec ruff, configurée dans `ruff.toml` (règles E4, E7, E9, F, B). Corrigé :
  3 chaînages d'exceptions manquants (`raise ... from exc`, B904 : la cause d'origine apparaît
  maintenant dans les journaux serveur), 2 variables de boucle inutilisées renommées (B007),
  2 noms de variable ambigus `l` renommés (E741). Faux positifs signalés par un `noqa` expliqué :
  B023 (fonction exécutée immédiatement par `filtered()`) et E402 (import après le bloc des
  bibliothèques optionnelles). B905 (`zip` sans `strict=`) ignorée, voir plus bas.
- **Aide du champ « Anonymiser les participants » réécrite** (voir Bugs corrigés).

**Bugs corrigés :**
- Symptôme : l'infobulle de « Anonymiser les participants » affirmait que les dates (sondages
  remplis, événements inscrits) restent visibles et que les présentateurs restent nommés partout.
  Diagnostic : texte de la v1.77.0, devenu faux avec la v1.78.0 (présentateurs par contexte) puis
  avec la fusion de la v1.91.0 (lignes de dates retirées). Correction : réécrite d'après le code.

**Garde-fous et cas limites traités :**
- Aucun attribut `width` sur la colonne : sa validité n'a pas pu être vérifiée pour Odoo 18, et un
  attribut invalide empêcherait le module de se charger (comme `<tree>` en v1.74.0). La feuille de
  style, elle, ne casse rien si ses sélecteurs ne correspondent pas : la colonne garde alors sa
  largeur automatique.
- Pas d'infobulle : le widget binaire d'Odoo n'en offre pas ; le retour à la ligne garantit la
  visibilité du nom complet sans JavaScript.
- B905 ignorée : passer à `strict=True` ferait planter la génération si deux listes parallèles
  n'avaient pas la même longueur, ce qui passe peut-être silencieusement aujourd'hui.

**Constats NON modifiés (à décider) :**
- `pdf_saut_page_participant` : le code met `default=True`, mais l'aide du champ dit « décoché par
  défaut pour cette raison » (risque de PDF trop volumineux). L'un des deux est faux.
- La tâche planifiée de purge s'appelle encore « RLQ Rapport de sondage : … » (visible dans
  Technique > Tâches planifiées), malgré le retrait de « RLQ » de tout ce qui est visible (v1.75.0).

**Vérifications effectuées :** ruff : aucun problème ; syntaxe Python et XML ; 124 tests autonomes ;
fichiers du manifeste (dont la feuille de style) tous présents. `run-all.sh` : 27 vérifications
automatisées réussies (étapes 1 à 4 exécutées pour de vrai ; étape 5 avec de fausses commandes
psql/createdb/dropdb/odoo-bin). Guide : HTML bien formé, 14 liens internes valides, libellés et
valeurs par défaut vérifiés contre le code. NON vérifié (aucune instance Odoo) : le chargement
de la vue modifiée, l'effet réel de la feuille de style, `tests/test_wizard.py` (dont le nouveau
test), la création réelle de la base PostgreSQL et l'exécution réelle des tests Odoo.

**Action requise :** mettre à jour le module (-u), puis actualiser le navigateur (Ctrl+F5) pour
charger la feuille de style. Lancer `./run-all.sh` sur une machine avec PostgreSQL et Odoo et nous
transmettre le résultat : ce sera la première exécution réelle de `tests/test_wizard.py`.

---

## 18.0.1.91.0

**Titre court :** version FUSIONNÉE de la v1.90.0 et d'une branche parallèle
de travail (v1.73 à v1.77 de sa propre numérotation) : documentation dans
`doc/`, mot de passe requis seulement quand il le faut (jamais pour un HTML/PDF
anonymisé), mot de passe par défaut configurable en base avec avertissement,
anonymisation complétée (historique de dates, liens internes, filet anti-courriel).

**Motif de la demande :** appliquer sur la v1.90.0 tous les changements faits
dans une autre séance de travail, et livrer désormais des archives portant leur
numéro de version (`rlq_survey_report.18.0.1.91.0.zip`) pour pouvoir revenir en arrière.

**Détail des modifications :**

- **Documentation dans `doc/`** : `CHANGELOG.md` et `NOTES_VALIDATION.md` déplacés
  dans `doc/` (contenu inchangé), nouveau `doc/CONTEXTE.md` (vue d'ensemble du
  projet). Références mises à jour dans `__manifest__.py` et l'en-tête du wizard,
  qui disaient « à la racine du module ».
- **Règle du mot de passe** (`_mot_de_passe_requis`) : à l'écran, HTML et PDF - requis
  SEULEMENT si le rapport n'est PAS anonymisé ; un fichier HTML/PDF anonymisé est
  livré en clair (pas de chiffrement, pas de préfixe `enc`). **Excel - TOUJOURS requis** :
  cet export n'applique pas l'anonymisation (vrais noms et courriels).
  La règle « écran » de la v1.77.0 (mot de passe exigé même à l'écran si non
  anonymisé) est CONSERVÉE telle quelle.
- **Mot de passe par défaut** : pré-rempli (champ et confirmation) depuis le paramètre
  système `rlq_survey_report.mot_de_passe_defaut`, créé à l'installation par
  `data/ir_config_parameter_mot_de_passe.xml` en `noupdate="1"` (une mise à jour -u
  n'écrase jamais une valeur déjà en base ; une valeur vide désactive le
  pré-remplissage). La valeur LIVRÉE n'est qu'un marqueur (`!CHANGE-MOI@`),
  refusé avec un message qui indique où le changer. Champ masqué ; bouton « Afficher
  le mot de passe » (notification, sans HTML ni JavaScript).
- **Avertissement visible** : tant que le mot de passe du formulaire est le marqueur,
  un encadré dit où le changer (menu Technique > Paramètres système, mode développeur
  requis) ; bouton « Ouvrir le paramètre » réservé au groupe Administrateur.
- **Anonymisation complétée** : en mode anonymisé, les lignes « Sondages remplis
  (total, tous temps) » et « Événements inscrits » (listes de dates précises) sont
  AUSSI retirées ; les liens vers le backend Odoo (configuration du sondage,
  « Tester sondage », événement) deviennent du texte simple ; un filet générique
  par expression régulière masque tout texte ayant la forme d'un courriel.
- **Titre du sondage** : quand un seul sondage est sélectionné, son titre figure dans
  le nom du fichier et en évidence en tête du rapport.
- **Copie d'écran sauvegardée** (`_sauvegarder_copie_ecran`) : chiffrée seulement si un
  mot de passe est réellement requis.

**Bugs corrigés :**
- Symptôme : le nom du fichier Excel portait « anonyme » quand la case était cochée,
  alors que l'Excel contient les vrais noms. Diagnostic : `_prefixe_nom_fichier()`
  s'appliquait à tous les formats. Correction : jamais « anonyme » sur l'Excel, et
  `enc` reflète maintenant si le fichier est réellement chiffré.
- Symptôme : un courriel restait visible dans un rapport anonymisé. Cause exacte non
  confirmée (hypothèse : courriel tapé dans une réponse libre). Le filet générique le
  couvre quelle que soit son origine.

**Garde-fous et cas limites traités :**
- Le courriel d'attribution d'auteur du pied de page est EXEMPTÉ du filet anti-courriel
  (constante `COURRIELS_ATTRIBUTION`), sinon il aurait été masqué dans chaque rapport
  anonymisé.
- Le refus du marqueur ne s'applique que là où un mot de passe est requis.
- Une base qui contient déjà un autre mot de passe par défaut le garde tel quel
  (`noupdate`) : le modifier à la main si on le souhaite.
- Le mot de passe réel d'une version intermédiaire livrée en dehors de cette branche
  ne figure plus nulle part dans le module ni dans la documentation.

**Décisions de fusion (conflits entre les deux branches) :**
1. Règle « écran » : celle de la v1.77.0 conservée, MES règles s'y ajoutent.
2. Les dates « Sondages remplis / Événements inscrits » : la v1.77.0 les gardait en mode
   anonymisé (jugées non identifiantes) ; elles sont retirées ici, sur demande explicite.
3. Avis de confidentialité : le libellé conditionnel de la v1.79.0 est conservé
   (l'autre branche en avait un différent, non appliqué).
4. Tests : `_wizard()` fournit un mot de passe valide par défaut (un rapport non
   anonymisé en exige un même à l'écran, ce que plusieurs tests existants ignoraient).

**Vérifications effectuées :** syntaxe Python et XML validées sur tous les fichiers ;
aucun doublon de méthode ni de champ ; recherche de toute affectation risquée sur `self` -
aucune ; `test_report_builder.py` 124/124 (fichier inchangé) ; vérifié par script que
`report_builder.py`, `event_ticket_survey.py`, `rlq_survey_report_acces.py`,
`survey_survey.py` et les autres fichiers non concernés sont IDENTIQUES à la v1.90.0 ;
aucun « RLQ » ajouté dans du texte visible. `test_wizard.py` : tests adaptés ou ajoutés
pour toutes les règles ci-dessus - NON exécutables ici, faute d'instance Odoo.
Non vérifié visuellement : l'encadré d'avertissement, les boutons, et la fiche du
paramètre ouverte en dialogue.

**Action requise :** mettre à jour le module (-u), puis définir le mot de passe par
défaut dans les paramètres système. Vérifier à l'usage la règle « écran » (voir la
décision 1 ci-dessus).

---

## 18.0.1.90.0

**Titre court :** libellé "Limiter aux dernières X heures?" ; coordonnées
d'un participant sur une seule ligne ; correctif de la date affichée
dans les colonnes (date du sondage et date de réponse séparées, plus
jamais mélangées) ; temps de réponse ajouté.

**Motif de la demande :** [1] cohérence du libellé avec les autres
options. [2] lisibilité des coordonnées. [3] la colonne affichait par
erreur la date DU SONDAGE combinée à l'HEURE de réponse (pas sa date) -
trompeur quand la personne répond plusieurs jours après la rencontre.
[4] connaître le temps de réponse d'une personne.

**Détail des modifications :**
- **[1]** Champ `filtre_dernieres_heures` renommé "Limiter aux
  dernières X heures?" (auparavant "Limiter aux inscriptions des X
  dernières heures").
- **[2]** Téléphone/Mobile/Ville/Pays d'un participant regroupés sur une
  seule ligne, séparés par une virgule et 4 espaces INSÉCABLES (`\xa0` -
  de simples espaces auraient été réduits à un seul par le rendu HTML) -
  plutôt qu'une ligne par coordonnée. Étiquettes reste sur sa propre
  ligne (peut être longue).
- **[3]** `tableau_reponses_personne()` : le paramètre `colonnes`
  n'utilise plus une seule clé `"libelle"` mais `"ligne1"` (date DU
  SONDAGE, extraite du titre - INCHANGÉE) et `"ligne2"` (date ET heure
  RÉELLES de réponse) - affichées sur deux lignes distinctes (`<br/>`)
  dans l'en-tête de colonne, plutôt que combinées en une chaîne
  trompeuse mélangeant la date de l'une avec l'heure de l'autre.
- **[4]** Nouvelle fonction pure `duree_humaine(secondes)` dans
  `report_builder.py` (ex. "5 min 12 s", "1 h 05 min") - calculée à
  partir de `end_datetime - start_datetime` sur `survey.user_input`,
  affichée sur une troisième ligne de l'en-tête de colonne quand
  disponible.

**Bugs corrigés :**
- Symptôme : la colonne affichait "2026-08-04 21:37" pour une personne
  ayant répondu le 2026-08-07, laissant croire à tort qu'elle avait
  répondu le jour de la rencontre. Diagnostic : le libellé combinait la
  date DE LA RENCONTRE (extraite du titre) avec seulement la PARTIE
  HEURE de `date_reponse_locale`, perdant sa date réelle au passage.
  Corrigé : les deux dates sont maintenant conservées et affichées
  séparément, sans jamais se substituer l'une à l'autre.

**Garde-fous et cas limites traités :**
- [4] `duree_humaine()` retourne `None` (rien affiché) si `end_datetime`
  précède `start_datetime` (données incohérentes) ou si l'un des deux
  horodatages manque - jamais de durée négative ou fantaisiste affichée.
- [2] Le regroupement ne s'applique qu'en mode NON anonymisé (ces
  coordonnées restent entièrement retirées en mode anonymisé, comme
  depuis la v1.77.0 - inchangé).

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 124 tests (mise à jour du schéma `colonnes` dans les tests existants,
6 nouveaux tests : `duree_humaine()` et le nouvel affichage à deux
lignes) - tous confirmés passants. Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module.

---

## 18.0.1.89.0

**Titre court :** nouvelle option pour limiter aux inscriptions des X
dernières heures (reflétée dans le nom du fichier) ; date/heure de
remplissage ajoutée à la colonne en mode combiné.

**Motif de la demande :** [1] besoin d'un suivi à chaud (ex. juste
après une rencontre) sans avoir à ajuster les filtres de date complets.
[2] en mode "Combiner les réponses..." (coché), la colonne du tableau
de réponses ne montrait que la date de la rencontre (extraite du
titre), pas quand la personne avait réellement répondu.

**Détail des modifications :**
- **[1]** Nouveau champ `filtre_dernieres_heures` (Integer, 0 par
  défaut = aucune limite) - "Limiter aux inscriptions des X dernières
  heures". Appliqué dans `_user_inputs()` comme un filtre additionnel
  sur `create_date` (se combine avec "À partir du"/"Jusqu'au" si
  renseignés aussi - le plus restrictif des deux s'applique). Reflété
  dans le préfixe du nom de fichier (`_prefixe_nom_fichier()`, ex.
  `...-24h-...`) et dans le résumé "Paramètres utilisés pour ce
  rapport".
- **[2]** En mode combiné (`combiner_reponses_meme_sondage` coché), le
  libellé de la colonne inclut maintenant la date/heure de la DERNIÈRE
  soumission traitée entre parenthèses, en plus de la date de la
  rencontre (conservée telle quelle, base du libellé et de l'ancre) -
  ex. « 2026-08-04 (2026-08-04 14:30) ». Le mode par défaut (décoché)
  l'affichait déjà depuis la v1.87.0.

**Garde-fous et cas limites traités :**
- [1] Un `filtre_dernieres_heures` de 0 (ou vide) ne change rien au
  comportement existant - entièrement rétrocompatible.
- [2] Si `date_reponse_locale` est indisponible (aucune réponse
  terminée ni commencée), le libellé retombe sur la date de la
  rencontre seule, comme avant.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(118 tests, aucun impact - ces changements touchent le wizard, non
couvert par cette suite). Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module.

---

## 18.0.1.88.0

**Titre court :** « Détail des soumissions » retiré en mode par
soumission (redondant avec les colonnes) ; badge « Entrée test »
déplacé dans l'en-tête de colonne.

**Motif de la demande :** en mode par défaut (une colonne par
soumission, v1.87.0), "Détail des soumissions" répétait des
informations déjà visibles dans les en-têtes de colonnes (date/heure) -
demandé de le retirer dans ce mode, et de rajouter le statut "Entrée
test" directement dans les colonnes puisqu'il n'apparaissait nulle part
ailleurs une fois "Détail des soumissions" retiré.

**Détail des modifications :**
- `_compute_report()` : "Détail des soumissions" (`section_soumissions_
  participant()`) ne s'affiche plus que si l'option "Combiner les
  réponses d'un utilisateur à un même sondage" est cochée - en mode par
  soumission (par défaut), il ne s'affiche plus du tout.
- Nouveau champ `"test"` (bool) dans les dicts de colonne
  (`p["colonnes"]`), rempli dans les deux modes (combiné et par
  soumission).
- `tableau_reponses_personne()` dans `report_builder.py` : affiche un
  badge "Entrée test" directement sous le libellé de l'en-tête de
  colonne quand `colonne["test"]` est vrai.

**Garde-fous et cas limites traités :**
- En mode COMBINÉ (case cochée), "Détail des soumissions" reste affiché
  comme avant - c'est le seul endroit où voir les soumissions
  individuelles dans ce mode, puisque le tableau n'a alors qu'une seule
  colonne par rencontre.
- Les tests existants qui ne fournissent pas de clé `"test"` dans leurs
  dicts de colonne continuent de fonctionner sans erreur (`.get("test")`
  défensif, aucun badge affiché par défaut).

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 118 tests (2 nouveaux : badge affiché quand `test=True`, absent sinon)
- tous confirmés passants. Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module.

---

## 18.0.1.87.0

**Titre court :** une colonne par soumission (date ET heure) par défaut
dans le tableau de réponses d'un participant, avec une option pour
revenir au comportement combiné précédent.

**Motif de la demande :** suite au "Détail des soumissions" (v1.86.0),
qui liste chaque soumission séparément mais sans que le grand tableau
de réponses par question en tienne compte (il continuait à combiner
plusieurs soumissions au même sondage dans une seule colonne). Demandé :
une option pour garder ce comportement combiné, mais par défaut une
colonne par soumission réelle, avec la date et l'heure.

**Détail des modifications :**
- Nouveau champ `combiner_reponses_meme_sondage` (Boolean, décoché par
  défaut) - "Combiner les réponses d'un utilisateur à un même sondage".
- `_traiter_question()` reçoit un nouveau paramètre `colonne_par_ui`
  (dict `{user_input_id: colonne_id}`), utilisé pour indexer
  `participants[...]["reponses"]` À LA PLACE de `date_rencontre` -
  `date_rencontre` lui-même reste inchangé pour toute la logique de
  SYNTHÈSE (agrégée par rencontre, jamais par soumission individuelle).
- Par défaut (décoché) : chaque soumission (`survey.user_input`) obtient
  sa propre colonne, avec un libellé "date heure" (ex. "2026-08-04
  14:30") basé sur `end_datetime`/`start_datetime` (déjà utilisés pour
  "Détail des soumissions" en v1.86.0).
- Coché : une seule colonne par rencontre, comme avant v1.86.0 - en cas
  de soumissions multiples, seule la dernière traitée reste visible
  dans ce tableau (les autres restent visibles dans "Détail des
  soumissions").
- `tableau_reponses_personne()` dans `report_builder.py` : signature
  changée, le paramètre `dates_triees` (liste de dates) devient
  `colonnes` (liste de dicts `{"id", "libelle", "ancre"}`) - plus
  flexible, permet un libellé différent de la clé de recherche et un
  lien d'ancre optionnel.

**Garde-fous et cas limites traités :**
- L'ancre du lien d'en-tête de colonne reste basée sur la RENCONTRE
  (pas la soumission individuelle) - c'est la section de la rencontre
  qui existe dans le rapport, pas une section par soumission.
- Le compteur "X participation(s)" et la table des matières des
  participants restent basés sur les RENCONTRES distinctes (inchangé),
  pas sur le nombre de colonnes du tableau de réponses.
- Le tri des colonnes utilise une clé texte comparable (date+heure ou
  date seule selon le mode) - jamais mélangé au sein d'un même rapport
  puisque l'option s'applique uniformément à toute la génération.

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 116 tests (mise à jour de la signature de `tableau_reponses_personne`
dans les tests existants, 2 nouveaux tests pour les colonnes par
soumission avec heure et l'absence de lien quand aucune ancre n'est
fournie) - tous confirmés passants. Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module. Le nouveau comportement
par défaut (une colonne par soumission) s'applique à tous les rapports
générés après la mise à jour, sauf si l'option est cochée.

---

## 18.0.1.86.0

**Titre court :** détail des soumissions par participant (date/heure de
réponse, date limite, entrée test), commentaire du personnel sur une
réponse, réponses à choix multiples une par ligne, alternance de fond
dans le détail des participants.

**Motif de la demande :** batch de 6 demandes sur la fiche participant
et la gestion des réponses.

**Détail des modifications :**

- **[1], [2], [3]** Nouvelle section "Détail des soumissions" dans la
  fiche de chaque participant (`section_soumissions_participant()`
  dans `report_builder.py`) - une entrée par soumission RÉELLE
  (`survey.user_input`), pas par rencontre : si la personne a répondu
  plusieurs fois au même sondage (ex. en changeant d'idée), chaque
  soumission apparaît séparément, triée par date de réponse (la plus
  récente en premier). Chaque entrée affiche :
  - la date/heure de réponse (`end_datetime`, avec repli sur
    `start_datetime` si la réponse est restée partielle) ;
  - la date limite de réponse (`deadline`), si elle est définie ;
  - un badge "Entrée test" si `test_entry` est vrai sur cette
    soumission.
  Ces trois champs (`end_datetime`, `deadline`, `test_entry`) sont déjà
  confirmés/déjà utilisés ailleurs dans ce module ou dans le code
  source d'Odoo consulté.
- **[4]** Question à choix multiples : chaque réponse sélectionnée
  s'affiche maintenant sur sa propre ligne, triée, dans le tableau de
  détail du participant (`tableau_reponses_personne()`) - au lieu
  d'être toutes jointes par des virgules sur une seule ligne.
  `participants[...]["reponses"]` stocke maintenant une LISTE pour ce
  type de question, plutôt qu'une chaîne concaténée.
- **[5]** Alternance de fond (zébrures) sur les lignes du tableau de
  détail d'un participant (CSS `nth-child(even)`), pour mieux
  distinguer chaque question - la colonne de gauche (nom de la
  question) et les lignes d'en-tête de groupe (questions
  matricielles) gardent leur propre style, non affectées.
- **[6]** Nouveau champ `rlq_commentaire_staff` (Text) sur
  `survey.user_input` (`models/survey_survey.py`, classe
  `SurveyUserInput`) - un membre de l'équipe (rôle Sondage :
  Utilisateur ou plus) peut y noter un commentaire libre sur la
  réponse d'UNE personne précise, rappelé dans le "Détail des
  soumissions" de cette personne une fois le rapport généré. Vue
  ajoutée sur le formulaire de `survey.user_input`
  (`views/rlq_survey_report_views.xml`).

**Garde-fous et cas limites traités :**
- [1]-[3] : n'affecte pas la table des réponses elle-même (toujours une
  colonne par RENCONTRE, pas par soumission individuelle) - une
  personne ayant répondu deux fois au même sondage verra ses deux
  soumissions listées dans "Détail des soumissions", mais une seule
  colonne de valeurs dans le grand tableau (celle traitée en dernier
  par la boucle existante) - une refonte plus large de cette
  architecture n'a pas été jugée nécessaire pour répondre à la demande.
- [4] : seules les questions à choix multiples/simple sont affectées -
  aucun changement pour les questions matricielles ou texte libre.

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 114 tests (7 nouveaux : réponses à choix multiples une par ligne,
détail des soumissions - tri, badge test, date limite, commentaire
échappé) - tous confirmés passants. Syntaxe Python et XML validées.
**NON VÉRIFIÉ SUR UNE VRAIE INSTANCE** :
- que `end_datetime` correspond bel et bien au moment de la soumission
  pour une réponse "done" (déjà utilisé ailleurs dans ce module pour un
  calcul de durée, mais pas encore pour un AFFICHAGE direct comme ici) ;
- que la vue ajoutée sur `survey.user_input`
  (`survey.survey_user_input_view_form`) existe bien sous ce nom -
  choisi par analogie avec le nom confirmé pour `survey.survey`, mais
  pas confirmé lui-même ;
- que le rôle "Sondage : Utilisateur" a bien accès en écriture au champ
  ajouté sur `survey.user_input` (aucune nouvelle règle d'accès
  ajoutée, en présumant que ce rôle peut déjà modifier ce modèle
  nativement).

**Action requise :** mettre à jour le module. Vérifier que la vue sur
`survey.user_input` s'affiche (voir NOTES_VALIDATION.md si erreur au
chargement), et que le rôle Utilisateur peut bel et bien écrire dans le
nouveau champ Commentaire.

---

## 18.0.1.85.0

**Titre court :** retrait d'un second filtre "test", codé en dur dans
la vue, qui empêchait même de sélectionner ces sondages.

**Motif de la demande :** suite au retrait du filtre par défaut en
v1.84.0 (`exclude_title_keywords`), l'utilisateur signale ne toujours
pas voir de sondages contenant "test" dans le titre.

**Détail des modifications :**
- `views/rlq_survey_report_views.xml` : retrait de
  `domain="[('title', 'not ilike', 'test')]"` sur le champ `survey_ids`
  du formulaire principal - un DEUXIÈME mécanisme d'exclusion,
  complètement indépendant du champ `exclude_title_keywords` corrigé en
  v1.84.0, codé directement dans la vue plutôt que dans un champ
  configurable. Ce domaine empêchait tout sondage contenant "test" dans
  son titre d'être ne serait-ce que SÉLECTIONNABLE dans le sélecteur -
  peu importe la valeur de `exclude_title_keywords`, qui n'intervient
  qu'APRÈS la sélection.

**Bugs corrigés :**
- Symptôme : aucun sondage contenant "test" dans le titre n'était
  visible, même après avoir vidé le champ "Exclure les sondages dont le
  titre contient" en v1.84.0. Diagnostic : deux mécanismes distincts
  excluaient "test" indépendamment l'un de l'autre - un champ
  configurable (`exclude_title_keywords`, corrigé en v1.84.0) ET un
  domaine codé en dur directement sur le sélecteur de sondages dans la
  vue XML (non découvert lors du premier correctif, puisqu'il n'est pas
  dans le modèle Python). Recherche exhaustive faite cette fois sur
  l'ensemble des fichiers du module pour confirmer qu'aucune troisième
  occurrence ne subsiste.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - ce correctif touche uniquement une vue XML).
Syntaxe Python et XML validées. Recherche exhaustive de "test" dans
tous les domaines/filtres du module (modèles ET vues) pour confirmer
qu'il ne reste aucune autre exclusion cachée.

**Action requise :** mettre à jour le module. Les sondages contenant
"test" dans leur titre devraient maintenant apparaître dans le
sélecteur de sondages.

---

## 18.0.1.84.0

**Titre court :** retrait du filtre par défaut "test" (masquait
silencieusement des sondages), lien de téléchargement corrigé dans
"Historique et fichiers déjà générés".

**Motif de la demande :** [1] aucun sondage contenant "test" dans son
titre n'était jamais visible dans le rapport, même sélectionné
explicitement - retracé à une valeur par défaut. [2] la liste
"Historique et fichiers déjà générés" n'affichait aucun lien cliquable
pour télécharger les fichiers déjà générés.

**Détail des modifications :**
- **[1]** `exclude_title_keywords` (« Exclure les sondages dont le
  titre contient ») : retrait de `default="test"`. Ce champ excluait
  silencieusement tout sondage sélectionné dont le titre contient
  "test", sans que ce soit visible ou voulu par la personne générant le
  rapport - vide par défaut désormais, à remplir explicitement si
  besoin.
- **[2]** `views/rlq_survey_report_views.xml` : ajout de
  `widget="binary"` explicite sur le champ `fichier_telecharger` dans
  la liste "Historique et fichiers déjà générés" - sans lui, une vue
  liste Odoo n'affiche pas toujours l'icône/le lien de téléchargement
  pour un champ Binary, même quand il contient des données.

**Garde-fous et cas limites traités :**
- [2] Les entrées créées AVANT la v1.83.0 (qui a introduit la copie
  indépendante du contenu du fichier) n'ont jamais eu de contenu dans
  `fichier_telecharger` - elles resteront donc sans lien de
  téléchargement même après ce correctif, ce n'est pas un nouveau bogue
  mais une limite attendue (rien n'a été régénéré rétroactivement pour
  ces entrées). Seules les entrées générées après la mise à jour vers
  la v1.83.0 ou plus récente ont un fichier à télécharger.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - ces deux correctifs touchent le wizard et une
vue XML, non couverts par cette suite). Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module. Pour [2], vérifier le
lien de téléchargement sur une entrée générée APRÈS cette mise à jour
(pas une ancienne entrée déjà existante, qui restera sans fichier).

---

## 18.0.1.83.0 — CORRECTIF CRITIQUE

**Titre court :** retrait d'une règle d'accès qui bloquait l'accès aux
pièces jointes de TOUT Odoo (pas seulement celles de ce module) pour le
groupe Sondage.

**Motif de la demande :** régression grave signalée en production -
message "Erreur d'accès" en tentant d'insérer une image sur une page
web, et impossibilité de voir des images déjà téléversées, avec un
message pointant explicitement vers la règle
`security/ir_rule_attachment.xml` ajoutée en v1.80.0.

**Détail des modifications :**
- **Fichier `security/ir_rule_attachment.xml` retiré entièrement**
  (supprimé du module et de `__manifest__.py`). Une mise à jour du
  module devrait automatiquement supprimer l'enregistrement `ir.rule`
  correspondant en base (la règle n'étant plus produite par aucun
  fichier de données du module) - **mais voir "Action requise"
  ci-dessous pour un retrait manuel immédiat, plus rapide que d'attendre
  une mise à jour.**
- `models/rlq_survey_report_acces.py` : le téléchargement depuis
  "Historique et fichiers déjà générés" ne dépend plus DU TOUT des
  droits d'accès de `ir.attachment`. Le champ `fichier_telecharger`
  n'est plus lié (`related`) à la pièce jointe - c'est maintenant une
  COPIE INDÉPENDANTE du contenu, stockée directement sur l'entrée
  d'historique elle-même (`attachment=False` explicite sur le champ,
  pour qu'Odoo ne recrée pas silencieusement une pièce jointe séparée
  derrière ce champ). `attachment_id` est conservé, mais seulement à
  titre de référence/traçabilité - plus utilisé pour le téléchargement
  lui-même.
- `models/rlq_survey_report_wizard.py`, `_journaliser_acces()` : copie
  maintenant `attachment.datas` dans `fichier_telecharger` au moment de
  la création de l'entrée d'historique.

**Bugs corrigés :**
- Symptôme : "Erreur d'accès" en tentant d'insérer une image sur une
  page web dans Odoo ; images déjà téléversées invisibles - pour
  N'IMPORTE QUELLE personne du groupe Sondage, sur N'IMPORTE QUELLE
  pièce jointe de tout Odoo, pas seulement celles de ce module.
  Diagnostic : une règle d'accès (`ir.rule`) liée à un groupe ne fait
  JAMAIS qu'ajouter une permission dans Odoo - elle RESTREINT l'accès du
  groupe visé à ce que sa condition autorise, pour TOUT LE MODÈLE visé
  (ici `ir.attachment`), pas seulement pour le cas d'usage visé. En
  ajoutant la première règle de ce genre pour le groupe Sondage sur
  `ir.attachment`, cette règle est devenue LA SEULE restriction
  appliquée à ce groupe sur ce modèle - bloquant l'accès à toute pièce
  jointe ne correspondant pas à sa condition (`res_model =
  'rlq.survey.report.wizard'`), y compris des images de site web sans
  aucun lien avec ce module. Une erreur de conception, pas un simple cas
  limite non couvert. Correction : retrait complet de cette règle,
  remplacée par une copie de contenu indépendante (voir ci-dessus) qui
  n'a besoin d'aucune règle d'accès sur `ir.attachment`.

**Garde-fous et cas limites traités :** le nouveau design ne touche plus
JAMAIS aux droits d'accès d'un modèle Odoo générique et partagé
(`ir.attachment`) - toute future fonctionnalité de partage de fichier
dans ce module devra suivre ce même principe : ne jamais ajouter de
règle d'accès sur un modèle utilisé par d'autres parties d'Odoo, se
limiter aux modèles propres à ce module.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact). Syntaxe Python et XML validées, y compris la
confirmation que `security/ir_rule_attachment.xml` n'existe plus dans le
module. **NE PEUT PAS être vérifié davantage sans accès à une instance**
- mais la correction retire simplement le mécanisme fautif plutôt que
d'introduire un nouveau mécanisme risqué, ce qui limite la probabilité
d'une régression supplémentaire du même type.

**Action requise - URGENT :**
1. **Immédiatement, sans attendre la mise à jour du module** : dans
   Réglages → Technique → Sécurité → Règles d'enregistrement, cherchez
   "Pièces jointes rlq_survey_report - lecture pour le groupe Sondage"
   et supprimez-la manuellement. Ceci débloque l'accès aux images/pièces
   jointes tout de suite.
2. Mettre à jour le module (confirmera/complètera le retrait de cette
   règle de façon permanente, et applique le nouveau mécanisme de
   téléchargement indépendant).
3. Vérifier que le téléchargement depuis "Historique et fichiers déjà
   générés" fonctionne toujours après la mise à jour (pour une nouvelle
   entrée générée après la mise à jour - les entrées déjà existantes
   n'auront pas rétroactivement de copie dans `fichier_telecharger`,
   seulement les nouvelles).

---

## 18.0.1.82.0

**Titre court :** correctif du lien de sondage par billet, qui ne menait
à aucun sondage.

**Motif de la demande :** confirmé en conditions réelles - après le
correctif v1.81.0 (champ visible dans l'outil Placeholder dynamique), le
lien apparaît bien dans le courriel reçu, mais ne mène à aucun sondage.

**Détail des modifications :**
- `models/event_ticket_survey.py`,
  `_compute_rlq_lien_sondage_billet()` : construit maintenant l'URL avec
  `survey.get_start_url()` (méthode native d'Odoo), plutôt qu'en
  assemblant `/survey/start/{survey.id}` à la main - `survey.id` (la clé
  interne en base) n'est pas ce qu'attend cette route publique. Repli
  sur `/survey/start/{survey.access_token}` si `get_start_url()` échoue
  ou n'existe pas sur cette version d'Odoo/ERPLibre - jamais sur `id`.

**Bugs corrigés :**
- Symptôme : le lien du sondage apparaissait correctement dans le
  courriel de confirmation, mais menait à une page qui n'affichait
  aucun sondage. Diagnostic : `survey.id` (l'identifiant interne,
  utilisé par erreur) n'est pas le bon identifiant pour la route
  publique `/survey/start/...` - cette même erreur (construire une URL
  de sondage à la main plutôt qu'avec les méthodes natives d'Odoo)
  avait déjà été rencontrée et corrigée ailleurs dans ce module (voir
  `_lien_test_sondage()`, après plusieurs tentatives) au moment de
  l'écriture de la fonctionnalité "Sondage par type de billet" - cette
  leçon n'avait pas été reprise à ce moment-là. Correction : utiliser
  `get_start_url()`, la méthode native d'Odoo, comme le fait déjà
  `_lien_test_sondage()`.

**Garde-fous et cas limites traités :** le repli sur `access_token` est
conservé (jamais sur `id`) si `get_start_url()` n'est pas disponible ou
échoue pour une raison quelconque - ne doit jamais faire échouer le
calcul du champ ni bloquer l'envoi du courriel.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - ce fichier n'est pas couvert par cette
suite). Syntaxe Python validée. **NON VÉRIFIÉ SUR UNE VRAIE INSTANCE** :
`get_start_url()` est une méthode native déjà confirmée fonctionnelle
ailleurs dans CE module (`_lien_test_sondage()`), mais son usage précis
ici (pour un lien de PARTICIPATION réelle, pas de test) n'a pas encore
été confirmé par un envoi de courriel réel après cette version.

**Action requise :** mettre à jour le module. Renvoyer un courriel de
test (ou consulter une inscription existante) pour confirmer que le
lien mène maintenant bel et bien au bon sondage.

---

## 18.0.1.81.0

**Titre court :** `rlq_lien_sondage_billet` rendu stocké - hypothèse de
correctif pour son absence dans l'outil « Placeholder dynamique ».

**Motif de la demande :** en configurant le courriel de confirmation
d'inscription (v1.73.0), le champ `rlq_lien_sondage_billet` n'apparaît
pas dans la recherche de l'outil « Placeholder dynamique » du corps du
courriel, contrairement à `rlq_survey_id` (qui, lui, apparaît).

**Détail des modifications :**
- `models/event_ticket_survey.py` : `rlq_lien_sondage_billet` passe de
  calculé-à-la-volée à **stocké** (`store=True`, avec `@api.depends`
  sur `event_ticket_id` et `event_ticket_id.rlq_survey_id` pour un
  recalcul automatique) - hypothèse principale : certains outils de
  recherche de champs (dont potentiellement celui du Placeholder
  dynamique) ne listent que les champs stockés.
- Documentation du champ et du modèle corrigée : la syntaxe `${object.champ}`
  (Jinja), mentionnée par erreur dans les versions précédentes, a été
  retirée des gabarits de courriel Odoo depuis la version 15 - remplacée
  par l'outil Placeholder dynamique (qui insère la syntaxe QWeb correcte
  automatiquement) pour le corps, et par `{{ object.champ }}` pour les
  champs simples (objet, etc.).

**Garde-fous et cas limites traités :** aucun changement de
comportement pour les rapports déjà générés - ce correctif ne touche
que le calcul du lien de sondage par billet.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - ce correctif touche un fichier non couvert
par cette suite). Syntaxe Python validée. **NON VÉRIFIÉ SUR UNE VRAIE
INSTANCE** : l'hypothèse (champ non stocké invisible dans l'outil de
recherche) n'a pas pu être confirmée ni infirmée sans accès à
l'instance - à valider après mise à jour (voir NOTES_VALIDATION.md).
Si le champ reste invisible malgré `store=True`, la cause est ailleurs
et il faudra vérifier directement via Réglages > Technique > Structure
de la base de données > Modèles (voir la procédure de diagnostic
donnée en conversation).

**Action requise :** mettre à jour le module (pas seulement redémarrer
le service - une mise à jour est nécessaire pour qu'Odoo calcule et
stocke la valeur pour les inscriptions déjà existantes). Confirmer que
le champ apparaît maintenant dans l'outil Placeholder dynamique du
corps du courriel de confirmation.

---

## 18.0.1.80.0

**Titre court :** bibliothèque de fichiers déjà générés (réutilisables
sans régénérer), rétention indéfinie pour les copies anonymisées.

**Motif de la demande :** suite à une question sur l'opportunité de
conserver les rapports anonymisés sur le serveur pour éviter de les
régénérer d'une personne à l'autre - confirmé, avec deux précisions :
inclure aussi les affichages à l'écran (pas seulement les
téléchargements), et conserver les copies anonymisées jusqu'à
suppression manuelle (pas de purge automatique).

**Détail des modifications :**

- **[1]** `action_generate()` sauvegarde maintenant systématiquement une
  copie du rapport affiché à l'écran comme pièce jointe
  (`_sauvegarder_copie_ecran()`) - protégée par mot de passe si un mot
  de passe a été saisi (obligatoire si non anonymisé depuis v1.77.0),
  non chiffrée sinon (cohérent avec le comportement déjà existant pour
  un affichage à l'écran anonymisé).
- **[2]** Nouveau champ `attachment_id` (Many2one vers `ir.attachment`)
  sur `rlq.survey.report.acces`, plus un champ lié `fichier_telecharger`
  (Binary) - le menu "Historique d'accès aux rapports" devient
  "Historique et fichiers déjà générés" et permet de télécharger
  directement les copies déjà produites, sans régénérer. Les 4 points de
  journalisation (`_journaliser_acces`, appelée par
  `action_generate`/`action_download_html`/`action_download_pdf`/
  `action_export_excel`) transmettent maintenant la pièce jointe
  correspondante.
- **[3]** `_cron_purger_pieces_jointes()` exclut désormais les pièces
  jointes liées à une entrée d'historique **anonymisée** - conservées
  indéfiniment (jusqu'à suppression manuelle), cohérent avec le principe
  de minimisation (une copie dépersonnalisée comporte moins de risque à
  garder qu'une copie avec des noms réels, qui continue d'être purgée
  après 3 jours comme avant).
- **[4]** Nouvelle règle d'accès (`security/ir_rule_attachment.xml`) :
  lecture seule, pour le groupe `survey.group_survey_user`, sur toute
  pièce jointe liée à ce wizard - NÉCESSAIRE pour qu'une personne autre
  que celle qui a généré le rapport puisse le télécharger depuis cette
  nouvelle liste (sans cette règle, Odoo pourrait restreindre l'accès au
  seul créateur de la pièce jointe, ce qui viderait la fonctionnalité de
  son intérêt).
- `_creer_attachment_zip()` retourne maintenant `(attachment,
  action_telechargement)` plutôt que seulement l'action, pour permettre
  à `action_export_excel()` de journaliser l'accès avec la pièce jointe.

**Garde-fous et cas limites traités :**
- La sauvegarde de la copie à l'écran ne lève jamais d'erreur qui
  bloquerait l'affichage du rapport lui-même (`try/except` dédié,
  journalisé mais silencieux pour l'utilisateur).
- L'entrée d'historique reste intacte même si la pièce jointe liée est
  supprimée plus tard (`ondelete="set null"` sur `attachment_id`) - le
  nettoyage manuel du volume de fichiers ne casse jamais la traçabilité.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - changements dans le wizard et un nouveau
fichier de sécurité, non couverts par cette suite). Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés/ajoutés.
**NON VÉRIFIÉ SANS ACCÈS À UNE INSTANCE** : l'accès aux pièces jointes
dans Odoo comporte une logique propre au cœur du framework qui peut, sur
certaines versions, se comporter de façon particulière avec des règles
`ir.rule` personnalisées - à tester en priorité avec un second compte
utilisateur avant de compter sur le partage entre personnes (voir
NOTES_VALIDATION.md).

**Action requise :** mettre à jour le module et redémarrer le service.
Tester avec un compte différent de celui qui génère les rapports que le
téléchargement depuis "Historique et fichiers déjà générés" fonctionne
bel et bien (voir NOTES_VALIDATION.md). Sans purge automatique pour les
copies anonymisées, un nettoyage manuel occasionnel (suppression des
pièces jointes) sera éventuellement nécessaire si le volume devient
important.

---

## 18.0.1.79.0

**Titre court :** correctif du bogue "nom d'une seule lettre non
anonymisé", libellé conditionnel de l'avis de confidentialité, retrait
du menu "Tous les sondages" (redondant), historique d'accès affichant
toutes les dates sur deux lignes.

**Motif de la demande :** batch de 4 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[1]** `_anonymiser_html()` : remplacement par expression régulière
  avec limites de mot (`\b...\b`) plutôt qu'une simple sous-chaîne - le
  garde-fou précédent (v1.56.0), qui EXCLUAIT ENTIÈREMENT tout nom de
  moins de 3 caractères pour éviter une corruption de texte, est retiré
  : il n'est plus nécessaire, puisque la limite de mot empêche déjà
  cette corruption pour un nom de N'IMPORTE QUELLE longueur.
- **[2]** Nouveau libellé conditionnel de l'avis en tête de rapport,
  selon `self.anonymiser` : "⚠ Ce rapport PEUT contenir des
  renseignements personnels sur les participants qui n'auraient pas été
  bien anonymisés." quand l'anonymisation est active, le libellé
  existant sinon.
- **[3]** Menu "Tous les sondages (terminé et commencé)" retiré de
  "Rapports détaillés" (`views/rlq_survey_report_views.xml`), avec
  l'action serveur et la méthode `action_menu_tous()` associées - déjà
  accessible via le raccourci "Filtrer par titre : Tous" dans
  l'assistant lui-même, rendant ce menu séparé redondant.
- **[4]** `rlq.survey.report.acces.resume_sondages` : champ converti de
  `Char` à `Text` - affiche maintenant TOUTES les dates des sondages
  inclus (plus de troncature "+N autre(s)"), réparties sur deux lignes
  si plus de 10 dates.

**Bugs corrigés :**
- Symptôme : un participant ayant entré une seule lettre ("F") comme
  nom sur sa fiche contact restait entièrement visible (non anonymisé)
  dans un rapport pourtant anonymisé. Diagnostic : le garde-fou de
  v1.56.0 excluait délibérément tout nom de moins de 3 caractères d'un
  remplacement de sous-chaîne sans limite de mot, pour éviter de
  corrompre du texte sans rapport (ex. "Filtre" → "[Participant
  N]iltre") - un compromis qui laissait la personne exposée plutôt que
  protégée. Correction : voir [1] ci-dessus - une limite de mot permet
  de remplacer ce nom en toute sécurité, sans plus jamais l'exclure.

**Garde-fous et cas limites traités :**
- L'ordre de remplacement (du nom le plus long au plus court) reste
  respecté avec la nouvelle méthode - un nom court contenu dans un nom
  plus long (ex. "Jean" dans "Jean Dupont") ne corrompt toujours pas ce
  dernier, vérifié manuellement (voir NOTES_VALIDATION.md).
- Le remplacement échappe les antislashs du texte de remplacement avant
  de les passer à `re.sub()` (qui interprète autrement des séquences
  comme "\1" comme des rétro-références) - sans effet sur les
  remplacements actuels (aucun n'en contient), mesure défensive.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(107 tests, aucun impact - ces changements touchent
`rlq_survey_report_wizard.py`, non couvert par cette suite). Le
correctif [1] a été vérifié manuellement par un script Python autonome
reproduisant exactement le bogue signalé (nom "F" à côté du mot
"Filtre") et confirmant qu'il ne se reproduit plus, sans corrompre le
mot "Filtre" ni casser l'ordre de remplacement long-vers-court. Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.78.0

**Titre court :** anonymisation par contexte (nom des présentateurs
préservé UNIQUEMENT dans les titres de présentation et l'appréciation
des présentateurs, retiré partout ailleurs, y compris "Liste des
participants") ; historique d'accès affichant des dates plutôt que des
titres complets.

**Motif de la demande :** correction suite au retour utilisateur - la
v1.77.0 gardait le nom d'un présentateur visible PARTOUT dans le
rapport dès qu'il était exempté (y compris dans "Liste des
participants", ce qui n'était pas souhaité), et l'historique d'accès
affichait des titres de sondage trop longs.

**Détail des modifications :**

- **[1] et [2] Anonymisation par contexte** (`models/report_builder.py`,
  `models/rlq_survey_report_wizard.py`) :
  - Nouvelles fonctions pures `jeton_presentateur(nom)` et
    `proteger_nom_dans_titre(item_texte)` dans `report_builder.py` : un
    jeton stable et déterministe (dérivé du nom par hachage MD5, aucun
    état partagé nécessaire) remplace le nom réel là où il doit rester
    visible - immunisé structurellement contre le remplacement global
    par pseudonyme (qui ne reconnaît que le TEXTE du nom, pas son
    contexte), puisque l'occurrence protégée ne contient plus ce texte.
  - `_anonymiser_html()` : retour à un remplacement de nom
    INCONDITIONNEL (retrait de l'exclusion globale des présentateurs
    ajoutée en v1.77.0, devenue incorrecte) - un présentateur qui a
    aussi répondu à un sondage voit maintenant son nom anonymisé dans
    "Liste des participants" et sa fiche personnelle, comme n'importe
    quel autre répondant.
  - Le jeton est utilisé à 3 endroits précis (protégés AVANT
    l'anonymisation, résolus vers le nom réel APRÈS - voir nouvelle
    méthode `_resoudre_jetons_presentateurs()`) : le nom dans le "Volet"
    d'une question matricielle de type Présentations (titre "Titre
    [Nom]"), le lien "Présentateur(s) :" de chaque rencontre, et la
    colonne "Présentateur" de la section "Appréciation des
    présentateurs".
  - `section_appreciation_presentateurs()` : nouvelle clé optionnelle
    `presentateur_affichage` dans les dicts d'entrée - le texte AFFICHÉ
    peut différer du texte utilisé pour l'ancre/le tri
    (`presentateur`), pour que la navigation interne continue de
    fonctionner peu importe ce qui est affiché.
  - Les dicts `dates_par_item`/`synth_item_date` correspondants ont dû
    être reconstruits avec les mêmes clés PROTÉGÉES que les items
    affichés, sans quoi le tooltip de date pour les présentations aurait
    silencieusement disparu (clés qui ne correspondraient plus).
- **[3] Historique d'accès : dates plutôt que titres**
  (`models/rlq_survey_report_acces.py`,
  `models/rlq_survey_report_wizard.py`) : `resume_sondages` liste
  maintenant les dates (`rlq_date_titre`, déjà stockée sur
  `survey.survey`) des sondages inclus, pas leurs titres complets -
  beaucoup plus court et lisible pour un rapport couvrant de nombreuses
  rencontres. Libellé et aide du champ mis à jour en conséquence.

**Garde-fous et cas limites traités :**
- Le jeton n'utilise que des caractères sans signification XML (⟦⟧ et
  hexadécimal) - jamais altéré par `echapper()`/`echapper_attr()`, donc
  toujours reconnaissable pour la résolution finale.
- `_resoudre_jetons_presentateurs()` s'exécute TOUJOURS, anonymisé ou
  non - un jeton ne doit jamais rester visible tel quel dans un rapport
  livré.
- Les tuples `detail` (qui listent les RÉPONDANTS ayant noté une
  présentation, pas le présentateur lui-même) ne sont pas touchés par
  ce mécanisme - ces personnes restent normalement anonymisables comme
  n'importe quel autre répondant.

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 107 tests (7 nouveaux tests pour `jeton_presentateur()` et
`proteger_nom_dans_titre()`, dont l'insensibilité du jeton à
`echapper()`) - tous confirmés passants. Une erreur de structure
introduite en cours d'édition des tests (deux tests existants déplacés
par erreur dans une nouvelle classe) a été détectée et corrigée avant
livraison. Syntaxe Python et XML validées sur l'ensemble des fichiers
modifiés.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.77.0

**Titre court :** anonymisation renforcée (coordonnées et étiquettes
retirées, présentateurs exemptés), mot de passe obligatoire à l'écran
si non anonymisé, nouvel historique d'accès aux rapports.

**Motif de la demande :** suite à la question sur la conformité Loi 25
de l'anonymisation existante - trois demandes pour renforcer la
protection des renseignements personnels de ce module.

**Détail des modifications :**

- **[1] Anonymisation renforcée** (`_anonymiser_html()`,
  `models/rlq_survey_report_wizard.py`) :
  - Nouveau paramètre `noms_presentateurs` sur `_anonymiser_html()` :
    les présentateurs ne sont JAMAIS remplacés par un pseudonyme, même
    s'ils ont aussi répondu à un sondage - déjà identifiés
    publiquement par leur présentation, contrairement aux simples
    répondants. Alimenté par `donnees_presentateurs` (déjà calculé
    pour la section "Appréciation des présentateurs").
  - Courriel, téléphone, mobile, ville, pays et étiquettes : RETIRÉS
    entièrement (plus rendus du tout dans le HTML) en mode anonymisé,
    plutôt que masqués après coup par une substitution de texte - plus
    robuste (aucun risque de fuite par un remplacement manqué). Les
    dates (sondages remplis, événements inscrits) restent affichées.
  - Texte d'aide du champ "Anonymiser les participants" mis à jour
    pour refléter cette portée élargie.
- **[2] Mot de passe obligatoire à l'écran si non anonymisé**
  (`action_generate()`) : la vérification du mot de passe, auparavant
  déclenchée seulement pour un téléchargement (HTML/PDF), l'est
  maintenant aussi dès que "Anonymiser les participants" est décoché -
  même pour un simple affichage à l'écran. Textes d'aide et message de
  la fenêtre de demande de mot de passe mis à jour en conséquence.
- **[3] Historique d'accès aux rapports** (nouveau) :
  - Nouveau modèle `rlq.survey.report.acces`
    (`models/rlq_survey_report_acces.py`) : qui, quand, quelle action
    (écran/HTML/PDF/Excel), nom du fichier le cas échéant, anonymisé
    ou non, sondages concernés.
  - Journalisation automatique aux 4 points de succès réels :
    `action_generate` (écran), `action_download_html`,
    `action_download_pdf`, `action_export_excel` - jamais en cas
    d'erreur, jamais avant confirmation du succès.
  - Nouveau menu "Historique d'accès aux rapports" sous "Rapports
    détaillés" - liste en LECTURE SEULE dans l'interface (aucune
    création/modification/suppression manuelle possible, pour que cet
    historique reste digne de confiance).
  - Nouveaux droits d'accès (`security/ir.model.access.csv`) :
    lecture/création pour `survey.group_survey_user` (le même groupe
    que le reste du module), gestion complète réservée à
    `base.group_system`.

**Garde-fous et cas limites traités :**
- La journalisation utilise `sudo()` pour ne jamais échouer par
  manque de droit d'accès - un historique qui pourrait silencieusement
  ne pas s'écrire perdrait l'utilité recherchée.
- `_journaliser_acces()` est appelée APRÈS le succès réel de chaque
  action (après la création de la pièce jointe pour les
  téléchargements), jamais avant ni en cas d'exception.
- Portée de l'historique d'accès clairement documentée dans le code et
  `NOTES_VALIDATION.md` : une bonne pratique de traçabilité, PAS le
  registre d'incidents de confidentialité formellement exigé par la
  Loi 25 (art. 3.5), un concept différent (incidents, pas accès
  normaux) - à garder en tête si vous voulez vous appuyer dessus pour
  une obligation légale précise.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(100 tests, aucun impact - les changements de cette version touchent
`rlq_survey_report_wizard.py` et un nouveau modèle, non couverts par
cette suite qui ne teste que les fonctions pures de
`report_builder.py`). Syntaxe Python et XML validées sur l'ensemble
des fichiers modifiés/ajoutés. Le nouveau modèle et ses droits d'accès
n'ont pas pu être testés sur une instance réelle.

**Action requise :** mettre à jour le module et redémarrer le service.
Les rapports déjà générés/téléchargés avant cette version ne sont pas
rétroactivement anonymisés davantage ni journalisés - seules les
nouvelles générations après la mise à jour sont concernées.

---

## 18.0.1.76.0

**Titre court :** ligne "Thème" retirée du résumé des paramètres,
coloration par seuils désactivée pour "Niveau de connaissance ?".

**Motif de la demande :** batch de 2 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[1]** `_resume_parametres()` : la ligne "Thème : Bleu (défaut)"
  retirée du bloc "Paramètres utilisés pour ce rapport" - redondante
  avec le sélecteur de thème déjà présent et fonctionnel directement
  dans le rapport HTML généré (boutons Bleu/Sombre/Vert/Violet), qui
  permet de changer le thème après coup sans regénérer.
- **[2]** `section_matrice()` : nouveau paramètre `colorer_seuils`
  (défaut `True`, comportement inchangé pour toutes les autres
  questions) - à `False`, la barre "Note moyenne" garde son
  pourcentage mais n'est plus colorée selon les seuils de qualité
  (rouge/jaune/bleu/vert). Appliqué automatiquement aux questions
  d'auto-évaluation (actuellement "Niveau de connaissance ?", voir
  `MOTS_CLES_QUESTIONS_AUTO_EVALUATION`) aux deux endroits où elles
  apparaissent (détail par rencontre et Synthèse) - ces questions
  étaient déjà exclues de la section "À surveiller" et des graphiques
  de tendance pour la même raison (une note basse n'y signale pas un
  problème comme le ferait une note de satisfaction basse), mais leur
  barre restait colorée par erreur, contrairement au reste du
  traitement qui les considère déjà comme non qualitatives.

**Garde-fous et cas limites traités :**
- Le pourcentage et la barre elle-même restent affichés pour "Niveau de
  connaissance ?" - seule la coloration par seuils disparaît, pas
  l'information.
- Si d'autres questions sont ajoutées à
  `MOTS_CLES_QUESTIONS_AUTO_EVALUATION` à l'avenir, elles bénéficient
  automatiquement du même traitement (coloration désactivée) sans
  modification supplémentaire.

**Vérifications effectuées :** suite `test_report_builder.py` complétée
à 100 tests (nouveaux tests pour `colorer_seuils`) - tous confirmés
passants. Syntaxe Python et XML validées.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.75.0

**Titre court :** flèche de détail toujours cliquable (même pour une
seule personne), formule des pourcentages corrigée dans tout le rapport,
libellé "Note globale" simplifié, retrait de "RLQ" de tout ce qui est
visible (menus, titres, noms de fichiers).

**Motif de la demande :** batch de 4 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[1]** `rendu_nombre_avec_detail_notes()` : toujours la liste
  dépliable cliquable sur la colonne "# réponses" (Organisation et
  logistique, Satisfaction globale...), peu importe le nombre de
  personnes distinctes. Le paramètre `seuil` (retiré) faisait
  auparavant basculer vers un simple tooltip au survol, non cliquable,
  en dessous de 2 personnes - empêchant d'accéder à la fiche de cette
  personne dans ce cas précis.
- **[2]** Formule des pourcentages corrigée dans `stats_pourcentage_html()`,
  `section_tendance_question()` (étiquette texte, pas la hauteur des
  barres), `section_note_globale()` (statistiques ET comparaison
  historique) et `section_top_mouvements()` : `valeur/échelle_max*100`
  partout (comme `barre()` et `_classe_pourcentage()`, qui utilisaient
  déjà cette formule), plutôt qu'ancrée à `echelle_min` (donnait 25%
  pour une note de 2/5 au lieu des 40% attendus - incohérent avec la
  barre visuelle juste à côté affichant, elle, le bon pourcentage).
- **[3]** "Note globale de cette rencontre" : "3% sous la moyenne"
  plutôt que "3 point de % sous la moyenne" (simplifié).
- **[4]** "RLQ" retiré de tout ce qui est visible dans Odoo et dans la
  documentation : nom du module (Apps), menus, actions, titres de
  rapport HTML/PDF, noms de fichiers téléchargés
  (`RapportSondage-RLQ-...` → `RapportSondage-...`), groupe "Actions de
  suivi", guide utilisateur - pour permettre à d'autres organisations
  d'utiliser ce module sans porter la marque de Rencontres Linux au
  Québec. L'attribution d'auteur (champs `author`/`maintainer`/
  `website`, pied de page du guide) est conservée telle quelle.

**Bugs corrigés :**
- Symptôme : une note de 2/5 affichait 25% dans la colonne
  "Statistiques", alors que la barre juste à côté (et l'intuition -
  2 sur 5, donc 40%) suggérait 40%. Diagnostic : deux formules de
  pourcentage différentes coexistaient dans le même rapport - `barre()`
  utilisait déjà `valeur/max*100`, mais `stats_pourcentage_html()` et
  les fonctions apparentées utilisaient une formule ancrée à
  `echelle_min=1` ((valeur-1)/(max-1)*100), un reliquat jamais harmonisé
  depuis son introduction en v1.72.0. Correction : toutes les fonctions
  utilisent maintenant la même formule que `barre()`.
- Symptôme : sous la colonne "# réponses", une seule personne donnait un
  tooltip au survol au lieu de la flèche cliquable habituelle,
  empêchant de cliquer sur son nom. Corrigé (voir [1] ci-dessus).

**Garde-fous et cas limites traités :**
- La HAUTEUR (en pixels) des barres du graphique de tendance
  (`section_tendance_question()`) reste volontairement ancrée à
  `echelle_min` - un choix de rendu visuel séparé de l'exactitude du
  chiffre affiché (voir le commentaire dans le code), pour continuer à
  bien distinguer visuellement des valeurs rapprochées (ex. 4.0 vs
  5.0). Seule l'étiquette TEXTE (%) affichée au-dessus a été corrigée.
- Le code couleur des notes (`colorer_par_valeur`, seuils sur la valeur
  BRUTE 1-5) n'est pas affecté par ce correctif - seule la façon
  d'exprimer un pourcentage change, pas la signification d'une note.

**Vérifications effectuées :** suite `test_report_builder.py` mise à
jour (98 tests : formules de pourcentage recalculées à la main pour
plusieurs cas de test - ex. Min 95%→96%, 25%→40% - et nouveaux tests
pour la flèche toujours cliquable et le libellé simplifié) - tous
confirmés passants. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Recherche exhaustive de "RLQ" dans tous les fichiers
de vue et modèles pour confirmer qu'aucune occurrence visible n'a été
oubliée (une seule reste, dans un commentaire de code interne non
affiché à l'utilisateur).

**Action requise :** mettre à jour le module et redémarrer le service.
Les rapports déjà générés/téléchargés avant cette version restent
inchangés (ils ne se régénèrent pas automatiquement) - seuls les
nouveaux rapports générés après la mise à jour afficheront les
pourcentages corrigés et les nouveaux libellés.

---

## 18.0.1.74.0

**Titre court :** correctif bloquant au chargement du module - `<tree>`
renommé `<list>` (Odoo 17/18).

**Motif de la demande :** erreur au démarrage rapportée par l'utilisateur
(journal de chargement du module joint) - le module entier refusait de
charger.

**Détail des modifications :**
- **[1]** `views/event_ticket_survey_views.xml` : xpath ciblant la racine
  de la vue liste des billets changé de `//tree` à `//list`.

**Bugs corrigés :**
- Symptôme : `odoo.tools.convert.ParseError: L'élément '<xpath
  expr="//tree">' ne peut être localisé dans la vue parente`, empêchant le
  chargement complet du module (échec de `load_modules`, base de données
  non initialisée).
- Diagnostic : la vue parente ciblée
  (`event.event_event_ticket_view_tree_from_event`) utilise `<list>` comme
  élément racine, pas `<tree>` - Odoo a renommé cette balise à partir de la
  version 17 (confirmé via la documentation Odoo et plusieurs rapports de
  la communauté). Une erreur de ma part en v1.73.0 : je n'avais pas
  d'accès à une instance Odoo 18 pour vérifier ce détail au moment
  d'écrire cette vue (voir NOTES_VALIDATION.md).
- Correction : `<xpath expr="//tree">` → `<xpath expr="//list">`. Aucun
  autre endroit du module n'utilisait `<tree>` (vérifié par recherche sur
  l'ensemble des fichiers de vue).

**Garde-fous et cas limites traités :** aucun autre changement dans cette
version - correctif isolé pour limiter le risque avant une nouvelle mise
à jour en production.

**Vérifications effectuées :** suite `test_report_builder.py` repassée
(97 tests, aucun impact - ce correctif ne touche que du XML) ; syntaxe
XML validée sur `views/event_ticket_survey_views.xml`. Toujours pas
vérifiable sans instance : l'existence même de cette vue parente sous ce
nom sur votre instance ERPLibre (si elle diffère, le message d'erreur
serait différent - probablement "n'existe pas" plutôt que "élément
introuvable dans la vue" - donc ce point précis est maintenant
implicitement confirmé par votre propre journal : la vue existe bel et
bien).

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.73.0

**Titre court :** sondage différent par type de billet, liste consolidée
des actions de suivi, "Ce qui a bougé" et messages de comparaison en %,
date d'événement manquante affichée sans lien externe, libellé de
filtre renommé.

**Motif de la demande :** batch de 7 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[1]** Nouveau champ `rlq_survey_id` sur `event.event.ticket`
  (Many2one vers `survey.survey`) et nouveau champ calculé
  `rlq_lien_sondage_billet` sur `event.registration`, pour envoyer un
  sondage différent selon le type de billet choisi à l'inscription
  (bénévole/visiteur/commanditaire...) plutôt que le sondage unique de
  l'événement natif d'Odoo. Nouvelle dépendance module : `event`
  (fichiers : `models/event_ticket_survey.py`,
  `views/event_ticket_survey_views.xml`).
- **[2]** Nouvelle fonction `section_actions_suivi_consolidee()` -
  liste, dans la Synthèse, de toutes les notes d'actions de suivi des
  rencontres incluses dans le rapport, en plus (inchangée) de la note
  par rencontre individuelle.
- **[3]** `section_top_mouvements()` ("Ce qui a le plus bougé depuis la
  dernière rencontre") affiche maintenant ses valeurs en % de l'échelle
  plutôt qu'en points bruts sur 5.
- **[4]** Dans la fiche participant, une inscription à un événement
  sans `date_begin` connu affiche maintenant "date non disponible dans
  ce rapport (nom de l'événement)" en texte simple au lieu d'être
  omise silencieusement (le total affiché ne correspondait plus au
  nombre de dates listées) - aucun lien externe généré dans ce cas.
- **[6]** Champ `filtre_participants_min` renommé "Minimum ayant
  débuté ou terminé?" (auparavant "Participants ayant débuté ou
  terminé (minimum)").

**Bugs corrigés :**
- Symptôme : le nombre total "Événements inscrits" d'un participant ne
  correspondait pas au nombre de dates listées juste à côté. Diagnostic :
  une inscription sans `date_begin` sur l'événement était comptée dans
  le total mais totalement omise de la liste de dates, sans aucune
  indication. Correction : voir [4] ci-dessus.

**Garde-fous et cas limites traités :**
- [5] Vérifié en cours de route : les messages "X point de % sous la
  moyenne des N rencontre(s) précédente(s)" étaient déjà en % depuis la
  v1.72.0 - seul un commentaire de code obsolète laissait croire le
  contraire ; corrigé pour éviter la confusion future, aucun changement
  de comportement.
- [4] Le texte de repli reste construit uniquement à partir de données
  déjà en mémoire (nom de l'événement) - aucune requête externe, aucun
  lien généré dans ce cas précis.
- [1] `rlq_lien_sondage_billet` retourne une valeur vide (pas un lien
  cassé) quand le type de billet n'a pas de sondage assigné.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée (nouveaux tests pour le format en % de
`section_top_mouvements()` et pour `section_actions_suivi_consolidee()`)
- tous confirmés passants. Syntaxe Python et XML validées sur
l'ensemble des fichiers modifiés/ajoutés. Les changements touchant
`event.event.ticket`/`event.registration` et la nouvelle vue [1] n'ont
pas pu être testés sur une instance réelle (voir NOTES_VALIDATION.md).

**Action requise :** mettre à jour le module et redémarrer le service.
Le module Événements (`event`) devient une dépendance obligatoire -
déjà installé sur votre instance d'après les données déjà utilisées
ailleurs dans ce rapport, mais à confirmer avant la mise à jour. Pour
le point [1] : assigner un sondage à chaque type de billet concerné,
puis ajouter `${object.rlq_lien_sondage_billet}` au modèle de courriel
de confirmation d'inscription (onglet Communication de l'événement).

---

## 18.0.1.72.0

**Titre court :** accès garanti aux actions de suivi (nouveau menu
dédié), résumé des paramètres complété, couleur des histogrammes
étendue à la barre elle-même, présentateurs listés par rencontre,
statistiques en pourcentage (avec P95) partout dans le rapport.

**Motif de la demande :** batch de 6 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[6]** Nouveau menu "Actions de suivi (amélioration continue)" sous
  Sondage, ouvrant une liste dédiée et entièrement définie par nous-
  mêmes (aucune dépendance à la structure exacte du formulaire natif
  du Sondage, contrairement à la vue héritée de la v1.71.0 qui reste
  en place comme bonus).
- **[1]** Résumé des paramètres complété : filtre présentateur,
  anonymisation, personnes n'ayant pas répondu, section "À
  surveiller", format de sortie.
- **[4]** `!important` ajouté au soulignement du lien "Aide" -
  hypothèse que la classe `btn-link` d'Odoo l'annulait autrement.
- **[2]** La barre de remplissage des histogrammes change maintenant
  de couleur elle-même (nouvelles classes `barre-remplie-*` et
  `evo-barre-*`), pas seulement le texte du pourcentage.
- **[3]** Liste des présentateurs ajoutée sous "Participants :" pour
  chaque rencontre, avec liens vers leur ligne dans "Appréciation des
  présentateurs" (nouvelle ancre unique par présentateur).
- **[5]** Nouvelle fonction centralisée `stats_pourcentage_html()` -
  statistiques (Min/Moy/Max/É-T/P95) exprimées en % de l'échelle
  partout (tendance de la note moyenne, Note globale, Appréciation des
  présentateurs, détail par volet), avec une variante texte brut pour
  les tooltips (qui n'interprètent jamais le HTML).

**Garde-fous et cas limites :**
- Le code couleur reste basé sur la valeur BRUTE (`colorer_par_valeur`
  avec `num=`), pas le pourcentage affiché - la signification d'une
  note ne change pas selon la façon dont on l'affiche.
- Un incident de syntaxe (parenthèse orpheline) introduit lors d'un
  remplacement partiel en fin de tour précédent a été détecté et
  corrigé avant toute livraison - aucune version cassée n'a été
  transmise.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 92 tests (nouveaux tests pour la couleur de la barre
remplie et les statistiques en pourcentage avec P95) - tous confirmés
passants. Syntaxe Python et XML validées sur l'ensemble des fichiers
modifiés. Recherche automatisée de toute affectation risquée sur
`self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Pour le point 6, le nouveau menu "Actions de suivi" devrait
maintenant être visible sous Sondage, peu importe si la vue héritée du
formulaire natif fonctionne ou non.

---

## 18.0.1.71.0

**Titre court :** boucle PDCA fermée (actions de suivi persistantes
sur le sondage), détection de dérive (tendance soutenue sur 3
rencontres), comparaison de la Note globale par catégorie de
rencontre plutôt que toutes mélangées.

**Motif de la demande :** trois pistes d'amélioration proposées par
l'assistant puis toutes retenues par l'utilisateur pour fermer la
boucle d'amélioration continue et affiner les comparaisons entre
rencontres.

**Détail des modifications :**

- **Actions de suivi persistantes.** Nouveau champ `rlq_actions_suivi`
  (Text, non calculé) sur `survey.survey` - rempli manuellement depuis
  le formulaire natif du Sondage (nouvelle vue héritée
  `view_survey_survey_form_rlq_actions`). Le rapport rappelle
  automatiquement ces notes (si présentes) juste après la Note
  globale de chaque rencontre - nouvelle fonction
  `rb.section_actions_suivi()`. **Point d'incertitude non vérifiable
  ici** : la vue est héritée via `ref="survey.survey_survey_view_form"`,
  le nom standard que je connais pour Odoo 18, mais sans accès à une
  instance pour le confirmer - à surveiller à l'installation.
- **Détection de dérive.** Nouveau paramètre `detecter_derive` sur
  `rb.section_tendance_question()` - signale 3 rencontres consécutives
  strictement croissantes ou décroissantes, un signal SPC distinct et
  complémentaire du point isolé hors écart-type déjà détecté
  (`limites_controle`). Activé sur la tendance de la Note globale.
- **Comparaison par catégorie.** La moyenne de référence (moyenne
  mobile, v1.68.0) ne compare maintenant une rencontre qu'aux
  rencontres PRÉCÉDENTES DE LA MÊME CATÉGORIE (réutilise les méthodes
  `_survey_ids_XXX()` existantes) - une Portes ouvertes entre deux
  Pause café n'influence plus leur comparaison mutuelle.

**Garde-fous et cas limites :**
- `section_actions_suivi()` retourne une chaîne vide si le champ n'est
  pas rempli (ou ne contient que des espaces) - pas d'encadré vide
  dans le rapport.
- La détection de dérive exige un STRICT ordre croissant ou
  décroissant sur les 3 dernières valeurs - une valeur égale à la
  précédente ne compte pas comme une dérive continue.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 90 tests (nouvelles classes pour les actions de suivi et
la détection de dérive) - tous confirmés passants. Nouveaux tests
ajoutés à `test_wizard.py` pour le filtre par présentateur et la
comparaison par catégorie (avec un jeu de données construit
spécifiquement pour vérifier qu'une catégorie intercalée n'influence
pas la comparaison) - non exécutables ici, faute d'instance Odoo.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Recherche automatisée de toute affectation risquée sur `self` -
aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Si l'installation échoue avec une erreur mentionnant
`survey_survey_view_form`, ce nom de vue devra être ajusté - point
d'incertitude documenté ci-dessus.

---

## 18.0.1.70.0

**Titre court :** nouveau filtre par présentateur (envoyer un rapport
ciblé à un bénévole), CORRECTIF d'une vraie incohérence de seuils de
couleur entre les histogrammes et les chiffres, bouton Aide souligné.

**Motif de la demande :** (1) besoin d'un filtre par présentateur pour
envoyer un rapport ciblé sur ses propres rencontres ; (2) le bouton
Aide devrait être souligné pour indiquer que c'est un lien ; (3) les
histogrammes devraient utiliser les mêmes seuils de couleur que les
chiffres (<=2 rouge, 3 jaune, 4 bleu, 5 vert) ; (4) suggestions
d'amélioration supplémentaires.

**Détail des modifications :**

- **[1]** Nouveau champ `filtre_presentateur` (liste déroulante
  dynamique, `_get_presentateurs_disponibles()`) - liste tous les
  présentateurs reconnus dans TOUS les sondages de la base. Le
  choisir (`_onchange_filtre_presentateur()`) remplace la sélection
  par uniquement les rencontres où il a présenté.
- **[2]** Bouton "Aide" souligné (`text-decoration:underline`).
- **[3] - vraie incohérence trouvée.** `_classe_pourcentage()`
  (barres horizontales) utilisait des seuils COMPLÈTEMENT DIFFÉRENTS
  de `colorer_par_valeur()` (les chiffres) - corrigé pour utiliser
  exactement les mêmes seuils (2/4/5 sur échelle 1-5). Nouvelle
  fonction `_classe_couleur_1a5()` pour les histogrammes VERTICAUX
  (couleur de fond plutôt que de texte), appliquée à
  `section_tendance_question()` - les comptes/pourcentages
  d'engagement (`section_evolution()`, `section_taux_reponse()`)
  gardent leur couleur fixe, cette échelle n'ayant pas de sens pour
  ces métriques.
- **[4]** Documentation à mettre à jour séparément si de nouvelles
  suggestions sont retenues.

**Garde-fous et cas limites :**
- Le filtre par présentateur cherche parmi TOUS les sondages de la
  base (pas seulement ceux déjà sélectionnés) - une sélection
  manuelle précédente est entièrement remplacée, pas complétée.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 83 tests (nouveaux tests pour les seuils de couleur
alignés et la coloration des histogrammes verticaux) - tous confirmés
passants. Nouveau test ajouté à `test_wizard.py` pour le filtre par
présentateur (recherche dans un sondage distinct de celui déjà
sélectionné) - non exécutable ici, faute d'instance Odoo. Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.69.0

**Titre court :** CORRECTIF de l'horodatage UTC dans le nom des
fichiers téléchargés (HTML/PDF/Excel) - passé à l'heure locale ;
"Niveau de connaissance ?" exclu de "Ce qui a le plus bougé".

**Motif de la demande :** (1) l'heure dans le nom des fichiers
téléchargés est en UTC plutôt qu'en heure locale ; (2) "Niveau de
connaissance ?" (une question plus posée dans les sondages récents)
apparaît dans "Ce qui a le plus bougé", ce qui n'a pas de sens pour
une auto-évaluation.

**Détail des modifications :**

- **[1]** Les trois méthodes de téléchargement (`action_download_html`,
  `action_download_pdf`, `action_export_excel`) utilisaient
  `fields.Datetime.now().strftime(...)` directement (heure UTC, jamais
  convertie) - corrigé avec `fields.Datetime.context_timestamp()`, le
  même mécanisme déjà utilisé et éprouvé ailleurs dans le module (le
  bandeau de génération du rapport).
- **[2]** "Ce qui a le plus bougé" exclut maintenant les questions
  d'auto-évaluation (réutilise `MOTS_CLES_QUESTIONS_AUTO_EVALUATION`,
  déjà utilisée pour la même exclusion dans "À surveiller").
- **[3]** Documentation HTML mise à jour et bonifiée (voir fichier
  séparé livré à côté du module).

**Vérifications effectuées :** confirmé qu'aucune occurrence de
`fields.Datetime.now().strftime` ne subsiste dans le fichier. Suite
`test_report_builder.py` réexécutée (81/81 passent, aucun changement
dans ce fichier). Nouveau test ajouté à `test_wizard.py` pour
l'exclusion de "Niveau de connaissance ?" - non exécutable ici, faute
d'instance Odoo. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Recherche automatisée de toute affectation risquée
sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.68.0

**Titre court :** sept améliorations pour l'amélioration continue
(esprit Lean Six Sigma) - limites de contrôle, comparaison
historique, "ce qui a le plus bougé", taux de réponse, tendance par
présentateur, Note globale dans l'Excel, commentaires liés aux notes
basses.

**Motif de la demande :** l'utilisateur a demandé des suggestions
d'amélioration, dans le contexte de l'analyse de sondages de
satisfaction pour l'amélioration continue (Lean Six Sigma) - 7 pistes
proposées, toutes implémentées sur demande de l'utilisateur.

**Détail des modifications :**

- **Limites de contrôle** (`section_tendance_question(...,
  limites_controle=True)`) - marque distinctement toute rencontre
  s'écartant de plus d'un écart-type de la moyenne globale. Activé sur
  la tendance de la Note globale.
- **Comparaison à la moyenne historique** (`section_note_globale(...,
  moyenne_reference=..., nb_reference=...)`) - moyenne mobile des 6
  rencontres précédentes, calculée dans le bon sens chronologique
  malgré le tri du plus récent au plus ancien.
- **"Ce qui a le plus bougé"** (`section_top_mouvements()`) - les 3
  questions ayant le plus changé entre les deux dernières rencontres,
  en tête de la Synthèse.
- **Taux de réponse en tendance distincte** (`section_taux_reponse()`)
  - terminé/inscrit en %, séparé de la satisfaction - protégé contre
  une division par zéro.
- **Tendance par présentateur** - indicateur ▲▼▬ comparant la première
  et la dernière présentation datées d'un présentateur en ayant
  plusieurs.
- **Note globale ajoutée à l'export Excel** - nouvelle feuille dédiée,
  réutilise `convertir_numerique()` du rapport principal plutôt que de
  dupliquer la logique d'extraction (évite toute divergence).
- **Commentaires libres reliés aux notes basses** - nouvelle méthode
  `_commentaire_libre_pour()`, nouvelle colonne dans "À surveiller".
  `alertes_notes_basses` passe de 5 à 6 éléments par tuple.

**Garde-fous et cas limites :**
- La tendance par présentateur ne s'affiche que si au moins 2
  présentations ont une date connue - sinon, aucun indicateur plutôt
  qu'un calcul basé sur un ordre arbitraire.
- Le taux de réponse ignore les rencontres sans aucun inscrit (évite
  une division par zéro) plutôt que de les exclure du rapport entier.
- La recherche de commentaire libre est protégée par un bloc
  try/except - un échec ne fait jamais échouer tout le rapport.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 81 tests (nouvelles classes pour chacune des 7
fonctionnalités testables en isolation) - tous confirmés passants,
y compris 2 tests existants mis à jour pour le nouveau format à 6
éléments de `alertes_notes_basses`. Nouveaux tests ajoutés à
`test_wizard.py` pour le commentaire lié - non exécutables ici, faute
d'instance Odoo. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Recherche automatisée de toute affectation risquée
sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Aucune de ces 7 fonctionnalités n'a pu être vérifiée
visuellement sur une vraie instance - une revue attentive du rendu
est recommandée avant diffusion large.

---

## 18.0.1.67.0

**Titre court :** l'exclusion volontaire par mot-clé n'est plus
présentée comme un problème ; le titre du formulaire reste toujours
"Rapport de sondage" peu importe le sous-menu utilisé.

**Motif de la demande :** (1) exclure un sondage par mot-clé
(comportement voulu) était présenté comme un "problème" dans le
bandeau de diagnostic ; (2) le sous-menu "Tous les sondages (terminé
et commencé)" change le titre du formulaire en y ajoutant son propre
nom - devrait plutôt régler le filtre "Filtrer par titre" sur "Tous
les sondages" et laisser le titre du formulaire simple.

**Détail des modifications :**

- **[1]** Chaque sondage exclu par mot-clé (`exclude_title_keywords`)
  n'est plus ajouté aux diagnostics - ce filtre est déjà visible dans
  le résumé des paramètres en haut du rapport, l'information n'est
  donc pas perdue. Une exclusion volontaire par l'utilisateur n'est
  pas une erreur.
- **[2]** Le titre du formulaire ("Rapport de sondage") ne change
  plus selon le sous-menu utilisé pour l'ouvrir. `menu_origine` reste
  affiché dans le résumé des paramètres ("Sous-menu utilisé : ...") et
  utilisé dans le nom de fichier en repli - seul son usage dans le
  titre du formulaire est retiré. `action_menu_tous()` règle
  maintenant aussi `filtre_titre_predefini` sur "tous" par défaut.

**Vérifications effectuées :** suite `test_report_builder.py`
réexécutée (65/65 passent, aucun changement dans ce fichier). Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.66.0

**Titre court :** CORRECTIF de l'alignement de l'en-tête (vraie cause
trouvée), contournement Unicode pour les sauts de ligne dans la
notification, diagnostic "0 réponse" rendu conditionnel, moyenne
manquante ajoutée, notes sans décimale dans "À surveiller", "Note
globale" réorganisée, extraction du présentateur supporte les
parenthèses.

**Motif de la demande :** batch de 7 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[1] - vraie cause trouvée.** `justify-content:space-between`
  (v1.65.0) n'avait aucun effet car `.oe_title` ne prend pas toute la
  largeur du formulaire par défaut - `width:100%` ajouté.
- **[2]** Un commentaire déjà présent dans le code (`chiffres_gras()`)
  confirmait qu'une tentative précédente de balises HTML dans cette
  notification avait déjà échoué - `<br/>` aurait donc échoué pour la
  même raison, jamais essayé. Utilisé le caractère Unicode U+2028
  (LINE SEPARATOR) à la place, qui EST un vrai saut de ligne pour le
  moteur de rendu même en texte brut, contrairement à "\n". La taille
  de la fenêtre elle-même n'est pas modifiable depuis notre code
  (CSS propre au composant de notification d'Odoo).
- **[3]** Le diagnostic "0/N réponses retenues" est maintenant
  entièrement supprimé (pas seulement adouci) quand
  `filtre_participants_min >= 1` (sa valeur par défaut) - affiché
  seulement si explicitement mis à 0.
- **[4]** Moyenne ("Moy") ajoutée à la cellule de statistiques
  d'"Appréciation des présentateurs" - manquait depuis l'ajout de
  cette section (Min/Max/É-T sans Moy).
- **[5]** Notes de "À surveiller" formatées sans décimale inutile
  (`:g`) - les votes sont des entiers de 1 à 5.
- **[6]** `section_note_globale()` réorganisée : histogramme et
  statistiques côte à côte (flex) plutôt qu'empilés verticalement.
- **[7]** `extraire_presentateur()` reconnaît maintenant un nom entre
  PARENTHÈSES en plus des crochets - motif étendu de `\\[...\\]`
  à `[\\[\\(]...[\\]\\)]`.

**Garde-fous et cas limites :**
- Le motif étendu pour le présentateur reste ancré à la FIN du titre
  uniquement - des parenthèses ou crochets ailleurs dans le titre
  restent ignorés, comme avant.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 65 tests (nouveau test pour le format parenthèses) - tous
confirmés passants. Format U+2028 et échappement testés en isolation.
Formatage `:g` testé avec un entier et un flottant. Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.65.0

**Titre court :** action_test_survey() CONFIRMÉ FONCTIONNEL - libellé
changé pour "Tester sondage" ; en-tête du formulaire enfin aligné à
droite ; second mécanisme de repli pour les liens d'événements ;
confirmation avant fermeture (Esc) déclinée par cohérence.

**Motif de la demande :** (1) confirmation que le test de sondage
fonctionne, demande de renommer le lien ; (2) le texte de version
n'est pas aligné à droite, doit le rester peu importe la largeur de la
fenêtre ; (3) les liens "Événements inscrits" pointent toujours à
l'extérieur ; (4) demande d'une confirmation avant fermeture via la
touche Esc.

**Détail des modifications :**

- **[1] - SUCCÈS CONFIRMÉ.** `action_test_survey()` fonctionne
  réellement (bandeau de test affiché, confirmé par l'utilisateur).
  Libellé changé de "ouvrir" à "Tester sondage".
- **[2]** `justify-content:space-between` ajouté au conteneur flex du
  titre - manquant dans le correctif de la v1.63.0 (le `gap` seul
  espace des éléments déjà groupés à gauche, il ne les pousse pas aux
  extrémités du conteneur).
- **[3]** Deuxième mécanisme de repli ajouté pour les liens
  "Événements inscrits" : comparaison par DATE (en plus de la
  comparaison par ID d'événement de la v1.62.0, pas à sa place) - au
  cas où `_lien_evenement()` ne trouverait pas d'événement lié pour
  certaines rencontres. Non garanti de résoudre le problème
  complètement, faute de diagnostic certain sans accès à l'instance.
- **[4] - décliné, cohérent avec la décision précédente.** Une
  confirmation avant fermeture (Esc, X, ou bouton Fermer)
  nécessiterait d'intercepter le cycle de vie du modal en JavaScript -
  le risque reste le même qu'à la demande précédente (voir
  NOTES_VALIDATION.md section -34), renforcé par l'incident confirmé
  de plantage (section -33). Non implémenté.

**Vérifications effectuées :** suite `test_report_builder.py`
réexécutée (64/64 passent, aucun changement dans ce fichier). Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Pour le point 3, si les liens pointent toujours à
l'extérieur après cette mise à jour, il faudra probablement examiner
directement les données (un exemple de sondage + événement où la
correspondance échoue) pour diagnostiquer avec certitude plutôt que de
deviner un troisième mécanisme.

---

## 18.0.1.64.0

**Titre court :** nouvelle tentative pour un vrai lien de test -
appel direct de `action_test_survey()` (la même action que le bouton
natif « Test »), avec repli sûr sur `get_start_url()`.

**Motif de la demande :** l'utilisateur a repéré, en mode debug
d'Odoo, que le bouton natif « Test » du formulaire Sondage appelle une
action nommée `action_test_survey` - une piste concrète pour obtenir
un vrai lien de test, après l'échec confirmé de `get_start_url()` sur
ce point (voir NOTES_VALIDATION.md, section -38).

**Détail des modifications :**

- `_lien_test_sondage()` tente maintenant d'appeler
  `survey.action_test_survey()` directement (si cette méthode existe
  sur le modèle) - réutilisant la MÊME action que le bouton natif,
  plutôt que d'essayer de reconstruire son comportement. L'url est
  extraite du dict d'action retourné (attendu de type
  `ir.actions.act_url`, clé `url`). Repli sur `get_start_url()`
  conservé si la méthode n'existe pas, échoue, ou ne retourne pas la
  structure attendue.
- Le libellé du lien reste « ouvrir » (pas « tester ») pour l'instant
  - je ne peux pas confirmer avec certitude que cette méthode
    fonctionne comme supposé sans accès à une instance ; si
    l'utilisateur confirme que le bandeau de test apparaît
    maintenant, le libellé pourra être changé en toute confiance.

**Garde-fous et cas limites :**
- Toute exception levée par `action_test_survey()` est interceptée et
  journalisée (`_logger.warning`) - ne fait jamais échouer la
  génération du reste du rapport.
- Si l'url retournée par l'action est relative (commence par `/`),
  elle est complétée avec `web.base.url` avant d'être utilisée.

**Vérifications effectuées :** test correspondant réécrit pour rester
souple sur la forme exacte de l'url retournée (je ne connais pas avec
certitude la structure de retour réelle d'`action_test_survey()`) -
confirme seulement qu'une url non vide est retournée sans exception.
Suite `test_report_builder.py` réexécutée (64/64 passent, aucun
changement dans ce fichier). Syntaxe Python et XML validées. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service, puis vérifier si le lien « ouvrir » affiche maintenant le
bandeau « Ceci est une entrée d'un sondage test. ».

---

## 18.0.1.63.0

**Titre court :** en-tête du formulaire allégé (version à droite du
titre, en texte normal, champ repassé en Char), redondance retirée
dans "Appréciation des présentateurs".

**Motif de la demande :** (1) l'en-tête du formulaire prend trop de
place - version demandée à droite du titre, en texte normal, format
"rlq_survey_report vX.Y.Z (AAAA-MM-JJ HH:MM FUSEAU)" ; (2) le résumé
"Moyenne combinée de N présentations" fait doublon avec la colonne
Note moyenne déjà affichée.

**Détail des modifications :**

- **[1]** `debug_info` repasse de `Html` à `Char` (le contenu n'a plus
  besoin de mise en forme, et ceci élimine tout risque résiduel lié
  au widget Html après l'incident documenté en NOTES_VALIDATION.md,
  section -33). Placé à droite du titre "Rapport de sondage" sur la
  même ligne (`display:flex`), en texte normal. Format simplifié :
  `rlq_survey_report vX.Y.Z (AAAA-MM-JJ HH:MM FUSEAU)`.
- **[2]** Le résumé "Moyenne combinée de N présentations :" avec son
  propre histogramme (ajouté en v1.62.0) retiré de
  `section_appreciation_presentateurs()` - il faisait doublon avec la
  colonne "Note moyenne" déjà affichée sur la ligne principale du
  présentateur. Les statistiques par présentation individuelle
  restent inchangées.

**Vérifications effectuées :** format de sortie du nouveau
`_default_debug_info()` vérifié en isolation, correspond exactement à
l'exemple demandé. Suite `test_report_builder.py` réexécutée (64/64
passent après mise à jour d'un test qui vérifiait l'ancien résumé
maintenant retiré). Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Recherche automatisée de toute affectation risquée
sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.62.0

**Titre court :** CORRECTIF des liens internes (comparaison par ID
plutôt que par date), dates de "Sondages remplis" aussi cliquables,
statistiques individuelles par présentation, champs remis à leur
place après un déplacement erroné.

**Motif de la demande :** (1) seul "Format de sortie" devait être
déplacé à droite, pas "À partir du"/"Jusqu'au" ; (2) afficher les
stats de chaque présentation individuelle, pas seulement la moyenne
combinée ; (3) les liens "Événements inscrits" pointent toujours à
l'extérieur malgré le correctif précédent ; (4) rendre aussi les
dates de "Sondages remplis" cliquables ; (5) mettre à jour et
bonifier la documentation HTML.

**Détail des modifications :**

- **[1]** "À partir du"/"Jusqu'au" remis dans la colonne de gauche -
  seul "Format de sortie" reste dans la colonne de droite, comme
  demandé à l'origine.
- **[3] - vraie cause trouvée.** La comparaison par date (v1.60.0)
  échouait probablement parce que la date d'un événement
  (`date_begin`) ne correspond pas forcément exactement à la date
  extraite du titre du sondage - deux représentations de la même date
  logique pouvant légèrement diverger. Corrigé en comparant par
  IDENTIFIANT D'ÉVÉNEMENT plutôt que par date, en réutilisant
  `_lien_evenement()` (déjà appelé une fois par rencontre). Nouveau
  suivi parallèle `evenements_rencontres` (l'ID de l'événement lié à
  chaque rencontre, le cas échéant).
- **[4]** Même mécanisme appliqué à "Sondages remplis" - comparaison
  par ID DE SONDAGE (plus direct, pas d'intermédiaire événement).
  Nouveau suivi parallèle `survey_ids_rencontres`. Un sondage inclus
  dans ce rapport pointe maintenant vers sa propre section ; un
  sondage "tous temps" hors de ce rapport pointe vers sa fiche de
  configuration dans le backend Odoo (comme avant pour les
  événements).
- **[2]** `section_appreciation_presentateurs()` affiche maintenant,
  pour un présentateur ayant fait plusieurs présentations, la moyenne
  et le nombre de réponses de CHACUNE dans la liste dépliable, en plus
  d'un résumé "Moyenne combinée de N présentations" - pour une seule
  présentation, ce détail serait redondant et n'est pas affiché.
- **[5]** Documentation HTML mise à jour et bonifiée (voir fichier
  séparé livré à côté du module).

**Garde-fous et cas limites :**
- Si une rencontre incluse n'a pas de date extraite (repli sur le
  titre du sondage pour son ancre), le lien "Sondages remplis"
  correspondant reste externe plutôt que de pointer vers une ancre
  incorrecte basée sur une date absente.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 64 tests (nouveaux tests pour les stats individuelles par
présentation, avec et sans présentation multiple) - tous confirmés
passants après correction d'un faux positif dans mon propre test
(assertion trop large, faisait un faux match avec le texte
d'introduction générique de la section). Syntaxe Python et XML
validées sur l'ensemble des fichiers modifiés. Recherche automatisée
de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Vérifiez en priorité : les dates d'"Événements inscrits" et
de "Sondages remplis" défilent-elles maintenant correctement DANS le
rapport quand elles correspondent à une rencontre incluse ?

---

## 18.0.1.61.0

**Titre court :** CORRECTIF CRITIQUE - le widget Html utilisé pour le
tooltip du mot de passe (v1.60.0) plantait réellement Odoo (OwlError
confirmé), abandon définitif de toute révélation du mot de passe.
Champs de sortie déplacés vers la colonne de droite.

**Motif de la demande :** (1) confirmation que l'utilisateur veut un
dialogue "Voulez-vous vraiment quitter sans télécharger ?" ; (2) trace
d'erreur JavaScript complète fournie après la saisie du mot de passe ;
(3) trop de champs dans la colonne de gauche du formulaire.

**Détail des modifications :**

- **[2] - CORRECTIF CRITIQUE, incident confirmé.** La trace d'erreur
  fournie (`OwlError` dans `HtmlViewer.retargetLinks`, `TypeError:
  Cannot read properties of null`) confirme que le widget Html
  d'Odoo, utilisé depuis la v1.60.0 pour le tooltip CSS du mot de
  passe, PLANTAIT RÉELLEMENT l'interface - pas seulement "ne
  fonctionnait pas". `apercu_solidite_mot_de_passe` redevient un
  `Char` simple. Après deux mécanismes de révélation ayant chacun
  échoué différemment (title= natif : sans effet ; widget Html : un
  plantage), AUCUNE troisième tentative n'est prévue - le champ
  confirme désormais seulement la correspondance et la solidité,
  sans jamais afficher le mot de passe.
- **[1]** Décliné - un dialogue de confirmation avant fermeture
  demanderait d'intercepter la fermeture du modal en JavaScript, un
  risque jugé trop élevé après l'incident du point précédent (une
  interaction relativement simple avec le cadre d'Odoo ayant déjà
  causé un vrai plantage).
- **[3]** `output_format`, `date_from` et `date_to` déplacés de la
  colonne de gauche vers le haut de la colonne de droite, au-dessus
  des cases à cocher - la colonne de gauche ne contient plus que les
  champs liés au filtre rapide et aux exclusions.

**Garde-fous et cas limites :**
- Le test correspondant (`test_mot_de_passe_jamais_affiche`, renommé)
  confirme maintenant l'ABSENCE totale du mot de passe dans le champ,
  peu importe le mécanisme - une garantie plus stricte et plus simple
  à maintenir que de vérifier un mécanisme d'affichage précis.

**Vérifications effectuées :** suite `test_report_builder.py`
réexécutée (62/62 passent, aucun changement dans ce fichier). Test
Odoo mis à jour pour refléter le nouveau comportement (non exécutable
ici, faute d'instance Odoo). Syntaxe Python et XML validées sur
l'ensemble des fichiers modifiés. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service
IMMÉDIATEMENT - la version précédente pouvait faire planter le
formulaire après la saisie du mot de passe.

---

## 18.0.1.60.0

**Titre court :** CORRECTIF d'une régression que j'avais moi-même
introduite (liens de navigation pointant hors du rapport - mécanisme
existant non réutilisé), dates d'événements pointant maintenant dans
le rapport quand pertinent, bandeau de diagnostic moins alarmiste pour
les cas attendus, second mécanisme de tooltip pour le mot de passe.

**Motif de la demande :** (1) le tooltip du mot de passe ne fonctionne
toujours pas (ni survol ni clic) ; (2) des sondages à "0/10 réponses
retenues" signalés comme un problème alors que le filtre de
participants minimum était déjà actif ; (3) les liens de navigation
(Liste des participants, À surveiller, Appréciation des présentateurs)
pointent hors du rapport ; (4) les dates des "Événements inscrits"
pointent aussi hors du rapport ; (5) demande de confirmation avant de
quitter le rapport - non traité, clarification demandée.

**Détail des modifications :**

- **[3] - régression de mon propre fait, corrigée.** Les liens de
  navigation ajoutés en v1.57.0 utilisaient un `<a href="#...">` BRUT
  plutôt que `rb.lien_ancre()` - le mécanisme EXISTANT, DÉJÀ
  DOCUMENTÉ DANS LE CODE LUI-MÊME, gérant précisément ce problème
  (un href brut est intercepté par le routeur d'Odoo dans le widget
  Html plutôt que de faire défiler jusqu'à l'ancre). Corrigé en
  réutilisant `lien_ancre()`.
- **[4]** `liste_dates_avec_liens()` accepte maintenant un url préfixé
  par "#" comme marqueur d'ancre interne (rendu via `lien_ancre()`)
  plutôt qu'un lien externe classique. Le wizard compare la date de
  chaque événement inscrit à `dates_rencontres` (les dates des
  rencontres incluses dans CE rapport précis) - une correspondance
  donne un lien interne vers cette section ; sinon, le lien externe
  vers la fiche de configuration de l'événement est conservé.
- **[2]** `filtre_participants_min` (compteurs globaux du sondage) et
  `_user_inputs()` (qui filtre en plus par date_from/date_to et les
  exclusions) ne sont pas parfaitement réconciliés - un sondage peut
  passer le premier filtre mais finir à 0 réponse retenue après le
  second. Non résolu entièrement (risque jugé trop élevé pour une
  réconciliation complète des deux mécanismes), mais le bandeau
  devient neutre (bleu, "ℹ") plutôt qu'une alarme rouge ("⚠") lorsque
  TOUS les diagnostics du rapport sont de ce type précis - une
  conséquence probable des filtres choisis par l'utilisateur plutôt
  qu'une vraie erreur technique.
- **[1] - second mécanisme essayé.** Le tooltip via l'attribut HTML
  natif `title=` (v1.59.0) ne fonctionnait pas. Remplacé par un
  mécanisme CSS AUTONOME : un `<style>` intégré directement dans le
  contenu du champ, utilisant `::after` déclenché par `:hover`
  (survol) ET `:focus` (clic, via `tabindex="0"`) - un mécanisme
  fondamentalement différent du précédent essai.
- **[5] - non traité.** Formulation ambiguë (bogue de fermeture, ou
  demande d'un dialogue de confirmation nécessitant du JavaScript ?) -
  clarification demandée plutôt que deviner une nouvelle fois.

**Garde-fous et cas limites :**
- Le bandeau de diagnostic ne devient neutre QUE si TOUS les
  diagnostics sont du type "0/N réponses retenues" - un mélange avec
  une autre catégorie d'erreur garde le bandeau rouge d'alarme.

**Vérifications effectuées :** nouveau test ajouté à
`test_report_builder.py` pour la distinction lien interne/externe
dans `liste_dates_avec_liens()` - suite complète à 62 tests, tous
passants. Test existant du mécanisme de tooltip mis à jour pour le
nouveau mécanisme CSS. Syntaxe Python et XML validées sur l'ensemble
des fichiers modifiés. Recherche automatisée de toute affectation
risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Vérifiez en priorité : les liens de navigation défilent-ils
maintenant correctement DANS le rapport ? Le tooltip du mot de passe
apparaît-il enfin (au survol ou au clic) ?

---

## 18.0.1.59.0

**Titre court :** CORRECTIF de l'espace fixe à gauche de la liste des
sondages (nolabel manquant), mot de passe affiché seulement en
tooltip natif du navigateur plutôt qu'en texte permanent.

**Motif de la demande :** (1) espace vide persistant à gauche de la
liste des sondages, indépendant de la largeur de la fenêtre ; (2) le
mot de passe reste affiché en permanence - proposition de
l'utilisateur : l'afficher seulement en tooltip plutôt que d'essayer
un délai automatique.

**Détail des modifications :**

- **[1] - cause trouvée et corrigée.** Le champ `survey_ids` n'avait
  pas `nolabel="1"` - Odoo réserve alors une colonne de largeur FIXE
  pour son étiquette dans la grille du `<group>`, peu importe la
  largeur de la fenêtre (expliquant "même en agrandissant, l'espace
  est toujours là"). `nolabel="1"` ajouté ; le texte de l'étiquette
  ("Sondages (rencontres) à inclure") reste affiché, mais via un
  `<div>` simple en pleine largeur au-dessus du champ plutôt qu'une
  colonne d'étiquette dédiée.
- **[2] - solution de l'utilisateur, plus simple qu'un délai
  automatique.** `apercu_solidite_mot_de_passe` passe de `Char` à
  `Html` (`sanitize=False`) - le mot de passe confirmé est maintenant
  placé dans l'attribut HTML natif `title=` d'un `<span>`, un tooltip
  du NAVIGATEUR LUI-MÊME (ce formulaire utilise le cadre d'Odoo, pas
  notre CSS personnalisé du rapport) - visible seulement au survol,
  sans aucun JavaScript ni minuteur. Le mot de passe est échappé
  (`rb.echapper_attr`) avant d'être inséré dans l'attribut, pour
  éviter qu'un guillemet dans le mot de passe ne casse la structure
  HTML.

**Garde-fous et cas limites :**
- Les messages d'état SANS le mot de passe (champs incomplets, ne
  correspondent pas, critères manquants) restent du texte simple,
  affiché normalement - seul le message de succès (contenant le mot
  de passe) utilise le mécanisme de tooltip.

**Vérifications effectuées :** échappement testé en isolation avec un
mot de passe contenant explicitement un guillemet - confirmé
correctement échappé (`&quot;`), ne casse pas la structure HTML.
Nouveau test ajouté à `test_wizard.py` confirmant que le mot de passe
n'apparaît que dans l'attribut `title=`, jamais dans le texte visible
- non exécutable ici, faute d'instance Odoo. Suite
`test_report_builder.py` réexécutée (61/61 passent). Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.58.0

**Titre court :** correctif du bon élément cette fois - largeur des
champs "Participants à exclure" et "Exclure par étiquette" réduite
aux deux tiers.

**Motif de la demande :** confirmation de l'utilisateur - les
"scroll-list" visées depuis le début sont ces deux champs
many2many_tags, pas la liste des sondages (déjà annulée en v1.57.0).

**Détail des modifications :**

- `style="max-width:66%;"` ajouté aux champs `exclude_partner_ids` et
  `exclude_tag_ids` (widget `many2many_tags`) - réduits aux deux tiers
  de leur largeur, tel que demandé initialement.

**Vérifications effectuées :** syntaxe XML validée. Suite
`test_report_builder.py` réexécutée (61/61 passent, aucune régression
attendue pour ce changement de vue uniquement).

**Action requise :** mettre à jour le module et redémarrer le
service.

---

## 18.0.1.57.0

**Titre court :** annulation d'un correctif erroné (largeur de la
liste de sondages), correction d'un vrai bogue d'anonymisation avec
les accents (normalisation Unicode), navigation vers les sections
principales ajoutée en tête du rapport, statistiques complètes sur
les graphiques de tendance.

**Motif de la demande :** (1) précision - le correctif de largeur
visait le mauvais élément, à annuler et reclarifier ; (2) plus de
statistiques sur la note globale dans la Synthèse ; (3) documentation
à mettre à jour ; (4) un nom de présentateur avec accent pas
anonymisé ; (5) navigation vers les sections principales dans la
table des matières.

**Détail des modifications :**

- **[1] - correctif erroné annulé.** La réduction de largeur de la
  v1.56.0 visait `survey_ids` (la liste des sondages) - annulée,
  cette liste retrouve sa largeur d'origine. L'utilisateur a précisé
  viser plutôt les "scroll-list" pour les options en bas du
  formulaire - non encore identifié avec certitude quel élément
  précis est visé, à clarifier avant un nouveau correctif.
- **[4] - vrai bogue d'anonymisation corrigé.** Un nom contenant un
  accent (ex. "Fabián") peut être représenté en Unicode de deux façons
  visuellement identiques mais avec des octets différents (forme
  composée NFC vs décomposée NFD) - si le titre de présentation
  utilise une forme différente de celle de la fiche contact,
  `html.replace()` (comparaison exacte) échoue à faire correspondre
  les deux, laissant le nom visible. Corrigé en normalisant (NFC) le
  HTML et chaque nom avant comparaison, dans `_anonymiser_html()`.
  Testé avec un cas reproduisant exactement le scénario signalé.
- **[5]** Navigation ajoutée en tête de la table des matières (Liste
  des participants, À surveiller, Appréciation des présentateurs) -
  les sections conditionnelles n'apparaissent dans cette navigation
  que si elles auront effectivement du contenu. Nécessité de déplacer
  le calcul de `donnees_presentateurs` plus tôt dans le code.
- **[2]** Chaque barre des graphiques de tendance (dont la nouvelle
  "Note globale") porte maintenant un tooltip avec les statistiques
  complètes de sa date (Min/Moy/Max/É-T/# réponses), pas seulement la
  moyenne déjà affichée au-dessus de la barre.
- **[3]** Documentation HTML mise à jour (voir fichier séparé livré à
  côté du module).

**Garde-fous et cas limites :**
- Le lien "Liste des participants" pointe toujours vers la section
  (toujours présente s'il y a au moins une réponse) ; les deux autres
  liens ne sont ajoutés QUE si leur section aura du contenu.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 61 tests (nouveau test pour le tooltip de statistiques
complet sur les graphiques de tendance) - tous confirmés passants.
Nouveau test ajouté à `test_wizard.py` pour la normalisation Unicode
des accents (reproduisant le scénario exact signalé - NFC en fiche
contact, NFD dans le titre) - non exécutable ici, faute d'instance
Odoo. Syntaxe Python et XML validées sur l'ensemble des fichiers
modifiés. Recherche automatisée de toute affectation risquée sur
`self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Pour le point 1, précisez quel élément exact vous appelez
"scroll-list" (idéalement avec une capture d'écran ou le nom du champ
visible) pour que je puisse corriger le bon élément cette fois.

---

## 18.0.1.56.0

**Titre court :** CORRECTIF (vraie cause enfin trouvée pour le bogue
d'affichage - un nom de participant trop court corrompait le
document entier une fois anonymisé), nouvelle métrique "Note globale"
composite par rencontre (avec tendance), cases à cocher remises à
droite, hyperliens ajoutés (À surveiller, présentateurs), histogrammes
individuels étendus à Organisation et logistique.

**Motif de la demande :** batch de 11 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[4] - vraie cause du bogue "Participant Niltre" trouvée et
  corrigée.** L'indice de l'utilisateur (seulement avec l'anonymisation
  activée) a permis de confirmer : `_anonymiser_html()` remplace
  chaque nom de participant par une chaîne globale
  (`html.replace(nom, pseudo)`) - un nom TRÈS COURT (ex. une seule
  lettre "F", probable fiche contact incomplète) remplace ALORS CETTE
  LETTRE PARTOUT DANS LE DOCUMENT, y compris dans "Filtre". Corrigé
  avec une garde de longueur minimale (3 caractères) : un nom trop
  court n'est plus anonymisé (reste visible tel quel), avec un
  avertissement dans les logs. Testé avec un participant nommé "F".
- **[11] - nouvelle métrique "Note globale" composite.** Combine les
  valeurs de "Organisation et logistique", "Satisfaction globale" et
  "Comment avez-vous aimé les présentations" en une moyenne unique par
  rencontre - affichée en tête de chaque section de rencontre
  (histogramme + statistiques), avec une tendance de cette métrique à
  travers toutes les rencontres en tête de la Synthèse. Nouvelle
  fonction `section_note_globale()`, nouvelle constante
  `MOTS_CLES_NOTE_GLOBALE`. Nouveau suivi parallèle `dates_rencontres`
  pour associer chaque section de rencontre triée à sa date d'origine,
  nécessaire pour calculer sa note composite après coup.
- **[1] - cases à cocher remises à droite.** Restructurées en flex
  personnalisé (45%/50%) plutôt qu'en pleine largeur (tenté en
  v1.55.0, mais pas la position voulue) - conserve une largeur
  suffisante pour éviter le retour à la ligne sur 3 lignes tout en
  gardant la position à droite.
- **[2]** Libellés simplifiés ("Filtrer par titre",
  "Sondages des N derniers mois" avec "(0 = tous)" déplacé dans le
  tooltip).
- **[3]** Largeur de la liste de sondages réduite aux deux tiers
  (`max-width:66%`).
- **[6]** `tabindex="0"` ajouté à la racine du rapport, tentative à
  risque faible pour la navigation clavier - sans garantie, dépend du
  widget Html d'Odoo.
- **[9]** Dates de la section "À surveiller" rendues cliquables.
- **[10]** Histogrammes de tendance par volet étendus à "Organisation
  et logistique" (déjà en place pour "Satisfaction globale").
- **[8]** Section "Appréciation des présentateurs" enrichie : détail
  des votants sur le chiffre de réponses (flèche cliquable, même
  patron que le reste du rapport), tooltip de date sur le titre de
  chaque présentation.
- **[5]/[7] - pas de changement supplémentaire.** Le correctif de
  hauteur en pixels (v1.55.0) devrait déjà couvrir le cas décimal vs
  entier signalé au point 5 (le mécanisme est indépendant du type de
  valeur) - à confirmer avec cette version précise. Pour le point 7,
  le compromis du lien de test (v1.55.0, sans bandeau de test) reste
  inchangé après 3 échecs du mécanisme précédent.

**Garde-fous et cas limites :**
- La note globale composite retourne une chaîne vide (rien affiché) si
  aucune des 3 questions n'a de valeur numérique pour une rencontre
  donnée, plutôt qu'un histogramme vide trompeur.
- Le garde-fou sur les noms courts s'applique aussi au slug d'ancre
  associé (même risque de correspondance accidentelle).

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 60 tests (nouveaux tests pour `section_note_globale()`,
le détail des votants et le tooltip de date des présentateurs) - tous
confirmés passants. Nouveaux tests ajoutés à `test_wizard.py`
(anonymisation avec nom court, présence de la note globale) - non
exécutables ici, faute d'instance Odoo. Syntaxe Python et XML validées
sur l'ensemble des fichiers modifiés. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : le bogue d'affichage a-t-il disparu avec
l'anonymisation activée ? La nouvelle "Note globale" apparaît-elle
correctement en tête de chaque rencontre ?

---

## 18.0.1.55.0

**Titre court :** correction du vrai nom de format pour les
présentateurs (crochets, pas un tiret), hauteur des barres verticales
passée en pixels (élimine un problème de résolution CSS), abandon
définitif du lien de test après un 3e échec, version toujours visible,
heure locale seulement, cases à cocher en pleine largeur, dates
d'événements cliquables, répartition inscrit/terminé/débuté dans
l'aperçu, option "Tous les sondages" dans le filtre rapide.

**Motif de la demande :** batch de 11 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **[11] Format réel des présentateurs (corrigé).** Confirmé par
  l'utilisateur : le nom est entre CROCHETS en fin de titre (ex.
  "Titre [Nom Prénom]"), pas après un tiret comme d'abord supposé en
  v1.54.0. `extraire_presentateur()` réécrite avec une expression
  régulière ancrée en fin de chaîne - des crochets ailleurs dans le
  titre (pas en position finale) sont correctement ignorés.
- **[7] Hauteur des barres verticales (corrigé, mécanisme changé).**
  Toujours aucune différence visible entre 4.0 et 5.0 malgré le
  changement d'échelle de la v1.54.0. Nouveau diagnostic : un
  pourcentage sur un enfant flex dans un conteneur
  flex-direction:column ne se résout pas de façon fiable dans ce
  contexte - les barres HORIZONTALES (utilisant width, jamais
  affectées) fonctionnaient pourtant bien, ce qui pointait vers une
  cause CSS plutôt que le calcul. `section_tendance_question()` ET
  `section_evolution()` calculent maintenant une hauteur en PIXELS
  directement (au lieu d'un pourcentage), éliminant le problème à la
  source.
- **[8] Lien de test (abandonné définitivement).** Troisième échec
  confirmé malgré deux correctifs. Retour à `get_start_url()`, fiable
  dans tous les rapports testés - voir NOTES_VALIDATION.md pour la
  recommandation alternative (bouton natif "Test" du backend).
- **[2]/[3] Version et espacement du formulaire.** `groups=
  "base.group_no_one"` retiré (la version s'affiche maintenant en tout
  temps, pas seulement en mode développeur) ; le champ est intégré au
  titre du formulaire plutôt que sur sa propre ligne.
- **Heure UTC retirée** du formulaire et du bandeau de génération du
  rapport - seule l'heure locale est affichée.
- **[1] Cases à cocher en pleine largeur.** Sorties de la grille en 2
  colonnes de `<group>` qui les confinait à une largeur fixe (3 lignes
  de texte malgré l'espace inutilisé à droite) - chacune est
  maintenant un `<div>` flex occupant toute la largeur disponible.
- **[4]** Option "Tous les sondages" ajoutée au filtre rapide,
  réutilisant `_survey_ids_tous()` (déjà utilisée par le sous-menu
  équivalent).
- **[9]** L'aperçu avant génération indique maintenant aussi le
  nombre d'inscrits, de terminé et de débuté sans terminer (sommés sur
  tous les sondages sélectionnés), pas seulement le total.
- **[10]** Les dates des "Événements inscrits" sont maintenant
  cliquables, menant à la fiche de configuration de l'événement -
  nouvelle fonction `liste_dates_avec_liens()`, `dates_evenements_par_partenaire`
  associe maintenant chaque date à l'URL de l'événement correspondant.
- **[6]** Règle CSS ajoutée garantissant le soulignement de tous les
  liens du rapport.
- **[5] Mot de passe révélé pendant un délai fixe (redemandé, toujours
  non implémenté).** Nécessite un minuteur JavaScript - voir
  NOTES_VALIDATION.md pour le raisonnement complet, inchangé depuis la
  demande précédente.

**Garde-fous et cas limites :**
- `extraire_presentateur()` ignore toujours les crochets qui
  n'apparaissent PAS en toute fin de titre, pour éviter une confusion
  avec un autre usage des crochets dans un titre.
- `liste_dates_avec_liens()` affiche une date en texte simple (sans
  lien) si son URL n'est pas disponible, plutôt que de générer un lien
  vide ou cassé.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 56 tests (tests mis à jour pour le format crochets,
nouveaux tests pour la hauteur en pixels et les dates avec liens) -
tous confirmés passants. Tests correspondants mis à jour dans
`test_wizard.py` (non exécutables ici, faute d'instance Odoo). Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : la section "Appréciation des présentateurs"
reconnaît-elle maintenant vos noms de présentateurs ? Voit-on
maintenant une différence de hauteur claire entre les barres de la
Tendance ?

---

## 18.0.1.54.0

**Titre court :** CORRECTIF (lien de test réutilisant une entrée déjà
terminée, confirmé par deux URL fournies), nouvelle section
"Appréciation des présentateurs", tooltips retirés (3 sections +
toutes les barres), dates cliquables dans les graphiques de tendance,
échelle des barres de tendance améliorée, bouton d'aide configurable,
nom de fichier enrichi (anonyme + plage de dates), message de mot de
passe en pleine largeur.

**Motif de la demande :** batch de 11 demandes - voir le détail par
point ci-dessous.

**Détail des modifications :**

- **Lien de test cassé (corrigé).** Confirmé par deux URL réelles
  fournies par l'utilisateur (une cassée, une fonctionnelle) : la
  logique de réutilisation d'une entrée de test existante ne
  vérifiait pas son état - une entrée déjà "done" causait une "Erreur
  d'accès au sondage" en tentant de la rouvrir. Corrigée pour ne
  réutiliser que les entrées encore fraîches (`state != 'done'`),
  sinon en créer une nouvelle.
- **Message mot de passe en pleine largeur.** Sorti de la grille en
  colonnes (qui le confinait à une largeur étroite malgré un
  `colspan="2"` déjà tenté en v1.48.0) - placé directement dans le
  `<sheet>`, juste avant la zone du rapport.
- **Bouton d'aide.** Nouveau bouton "Aide" ouvrant une URL externe
  dans un nouvel onglet - configurable via le paramètre système
  `rlq_survey_report.url_aide` (Réglages > Technique > Paramètres
  système), avec une valeur par défaut fournie par
  `data/ir_config_parameter_aide.xml` (`noupdate="1"` : une valeur
  modifiée par un administrateur n'est jamais écrasée par une mise à
  jour du module).
- **Nom de fichier enrichi.** `_prefixe_nom_fichier()` indique
  maintenant aussi "anonyme" (si l'anonymisation est active) et les
  sous-options du filtre rapide (ex. "5derniersmois", "3pmin").
  Nouvelle méthode `_suffixe_plage_dates_nom_fichier()` ajoutant la
  plage de dates au format "AAAAMMJJ__a__AAAAMMJJ" (tiret bas doublé
  autour de "a" plutôt que "à", pour éviter les accents dans un nom de
  fichier) - à partir des filtres explicites (À partir du/Jusqu'au) si
  renseignés, sinon calculée à partir des dates réelles des sondages
  inclus.
- **Tooltips retirés.** L'exclusion du tooltip de date sur le nom d'un
  volet (déjà en place pour "Satisfaction globale") est étendue à
  "Organisation et logistique", "Niveau de connaissance ?" et "Contenu
  et expérience Linux" (nouvelle constante partagée
  `MOTS_CLES_VOLETS_FIXES`). Le tooltip de moyenne sur la BARRE
  elle-même est retiré complètement, pour toutes les questions du
  rapport (l'information reste visible via le pourcentage déjà
  affiché à côté).
- **Dates cliquables dans les graphiques de tendance.**
  `section_tendance_question()` utilise maintenant `lien_date()` pour
  ses libellés de date (comme `section_evolution()` le fait déjà) -
  cohérence entre les deux types de graphiques.
- **Échelle des graphiques de tendance améliorée.** La hauteur des
  barres était calculée relativement au maximum DE LA SÉRIE elle-même
  et ancrée à 0 - ce qui compresse les écarts visuels entre des
  valeurs qui se ressemblent, une note ne descendant jamais sous 1.
  Recalculée sur une échelle FIXE (1 à 5 par défaut), ancrée à 1 -
  testé avec l'exemple fourni (4.9 vs 3.6) : l'écart mesuré passe de
  27 à 33 points de pourcentage.
- **Nouvelle section "Appréciation des présentateurs".** Nouvelles
  fonctions `extraire_presentateur()` et
  `section_appreciation_presentateurs()` dans `report_builder.py` :
  regroupe toutes les présentations (tous volets, toutes rencontres
  confondues) de la question "Comment avez-vous aimé les
  présentations ?" par nom de présentateur, avec note moyenne, %,
  nombre de réponses et statistiques par présentateur. **Basé sur une
  HEURISTIQUE** (format supposé du titre : "Titre de la présentation -
  Nom Prénom", un nom plausible = 2 à 4 mots commençant par une
  majuscule) - non vérifiable sans accès à de vraies données ; si le
  format réel diffère, la section n'affichera simplement aucun nom
  reconnu (aucun risque de fausse attribution, voir le test dédié au
  cas "Partie 2" non confondu avec un nom).

**Non appliqué, avec justification :**
- **Mot de passe révélé au clic sur le champ, puis révélé 2 secondes
  avant effacement automatique** : les deux nécessitent du JavaScript
  personnalisé (minuteur, gestion d'événement de focus), impossible à
  tester dans cet environnement de développement - non implémenté,
  voir NOTES_VALIDATION.md sections -24 et -26 pour le détail complet
  du raisonnement.
- **Bogue d'affichage "Participant 11iltre..."** : recherche
  approfondie sans résultat concluant - voir NOTES_VALIDATION.md
  section -25 pour l'information précise nécessaire pour avancer.

**Garde-fous et cas limites :**
- `extraire_presentateur()` ne tente JAMAIS de deviner un nom dans un
  titre qui ne suit pas le format attendu - un titre technique se
  terminant par un nombre (ex. "Partie 2") est explicitement rejeté
  par le test "mot commençant par une majuscule" (un chiffre échoue ce
  test).
- Le nom de fichier peut devenir long avec toutes ces informations
  combinées - voulu, pour représenter fidèlement le contenu sans avoir
  à ouvrir le fichier.

**Vérifications effectuées :** 6 nouveaux tests ajoutés à
`test_report_builder.py` pour `extraire_presentateur()` et
`section_appreciation_presentateurs()` (nom plausible, trait d'union,
non-confusion avec une fin de titre technique, absence de tiret,
section vide, section avec données) - suite complète à 51 tests, tous
passants. Nouveaux tests ajoutés à `test_wizard.py` (lien de test
n'étant plus réutilisé si "done", préfixe indiquant "anonyme", plage
de dates avec et sans filtre explicite, section Appréciation des
présentateurs de bout en bout) - non exécutables ici, faute d'instance
Odoo. Syntaxe Python et XML validées sur l'ensemble des fichiers
modifiés et nouveaux. Une erreur de syntaxe (guillemets imbriqués dans
un f-string) a été détectée et corrigée avant livraison.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : le lien "tester" fonctionne-t-il maintenant de
façon fiable ? La nouvelle section "Appréciation des présentateurs"
reconnaît-elle bien vos noms de présentateurs (si non, le format réel
de vos titres diffère probablement de l'hypothèse "Titre - Nom
Prénom") ?

---

## 18.0.1.53.0

**Titre court :** avertissements clairs dans les logs pour toute
bibliothèque Python optionnelle manquante au chargement (sans jamais
faire échouer le chargement, contrairement à `external_dependencies`
retiré en v1.52.0) ; mot de passe révélable au clic sur le champ :
recherché mais non implémenté, avec piste alternative suggérée.

**Motif de la demande :** (1) le mot de passe pourrait-il apparaître
en clair au clic sur son champ, plutôt que sur une ligne séparée ; (2)
serait-il possible de signaler les bibliothèques manquantes au
démarrage sans faire planter le module (suite à l'incident de la
v1.51.0/1.52.0).

**Détail des modifications :**

- **(2)** `_logger` déplacé plus haut dans le fichier pour être
  disponible dès les imports optionnels. Chaque bibliothèque absente
  (pypdf/PyPDF2, pyzipper, openpyxl) déclenche maintenant un message
  `_logger.warning()` clair et actionnable (« pip install X ») dans
  les logs du serveur au chargement du module - sans jamais interrompre
  le chargement, contrairement à `external_dependencies` (retiré en
  v1.52.0 suite à l'incident confirmé en production). Logique testée
  en isolation (bibliothèque manquante simulée) - confirmé que
  l'avertissement s'affiche sans plantage.
- **(1) - recherché, non implémenté.** Odoo n'a aucun widget natif
  pour révéler un mot de passe au clic sur son propre champ - seuls
  des modules tiers non garantis installés, ou du JavaScript
  personnalisé (widget OWL), le permettraient. Étant donné les
  difficultés déjà rencontrées dans ce projet avec du JavaScript
  impossible à tester dans cet environnement, aucun code n'a été
  ajouté pour cette demande précise. Piste suggérée : plusieurs
  navigateurs modernes (Edge notamment) affichent NATIVEMENT une
  icône "œil" sur tout champ `type="password"` (ce que ce champ est
  déjà) - à vérifier directement dans le navigateur utilisé.

**Garde-fous et cas limites :**
- Les avertissements de bibliothèque manquante n'apparaissent qu'au
  CHARGEMENT du module (une fois par redémarrage du serveur), pas à
  chaque utilisation - pour un rappel à chaque tentative d'usage
  réelle, le `UserError` déjà en place (voir v1.52.0) reste le
  mécanisme pertinent.

**Vérifications effectuées :** logique d'avertissement testée en
isolation avec une bibliothèque manquante simulée - confirmé que le
message s'affiche et que le chargement se poursuit normalement. Suite
`test_report_builder.py` réexécutée (45/45 passent). Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Pour le point (1), essayez de cliquer dans le champ mot de passe avec
votre navigateur habituel pour voir si une icône "œil" apparaît déjà
nativement, avant de demander un développement supplémentaire.

---

## 18.0.1.52.0

**Titre court :** CORRECTIF CRITIQUE (régression confirmée en
production) : `external_dependencies` (ajouté en v1.51.0) empêchait
Odoo de charger le registre au complet dès que `pyzipper` n'était pas
installé - retiré.

**Motif de la demande :** log d'erreur réel fourni par l'utilisateur -
`Failed to initialize database` au démarrage/à la mise à jour du
module, `External dependency pyzipper not installed`.

**Détail des modifications :**

- `external_dependencies` retiré du manifeste. Cette déclaration,
  ajoutée en v1.51.0 suite à une suggestion de revue de code externe,
  a un effet BIEN PLUS SÉVÈRE que prévu : plutôt que de simplement
  empêcher l'installation de CE module si une dépendance manque, elle
  fait échouer le CHARGEMENT COMPLET DU REGISTRE ODOO dès que
  n'importe quel module en cours de mise à jour référence une
  dépendance manquante - bloquant potentiellement l'accès à
  l'INSTANCE ENTIÈRE, pas seulement à ce module. Confirmé en
  conditions réelles par le log d'erreur fourni.
- Le code dispose déjà, à l'exécution, d'un `UserError` clair pour
  chacune de ces trois bibliothèques (`pypdf`/PyPDF2, `openpyxl`,
  `pyzipper`) si elle est absente au moment précis où une
  fonctionnalité qui en a besoin est utilisée (export PDF/Excel
  protégés) - vérifié à nouveau, toujours en place, inchangé. C'est
  le bon compromis pour des dépendances nécessaires seulement à des
  fonctionnalités optionnelles, pas au fonctionnement de base du
  module (écran, export HTML).

**Garde-fous et cas limites :**
- Sans `pyzipper` installé, l'export Excel protégé par mot de passe
  échouera avec un message clair au moment de l'utiliser - mais le
  reste du module (génération à l'écran, export HTML, export PDF si
  `pypdf` est disponible) continue de fonctionner normalement.

**Vérifications effectuées :** confirmé que la gestion d'erreur à
l'exécution pour les trois bibliothèques concernées est toujours en
place et inchangée (message clair, pas de plantage). Suite
`test_report_builder.py` réexécutée (45/45 passent). Syntaxe Python
et XML validées sur l'ensemble des fichiers modifiés.

**Action requise : mettre à jour le module IMMÉDIATEMENT** pour
restaurer l'accès à l'instance. Si `pip install pyzipper` (et
`openpyxl` si also absent) est possible sur cette instance, cela
reste recommandé pour profiter des exports protégés par mot de passe
- mais n'est plus une condition pour que le module (ou l'instance)
fonctionne.

---

## 18.0.1.51.0

**Titre court :** suite à une revue de code externe (9 points) :
correction de la fuite d'ancre à l'anonymisation, nouvelle purge
automatique des pièces jointes accumulées, dépendances Python
déclarées explicitement. Plusieurs autres points de la revue
évalués et délibérément non appliqués, avec justification détaillée.

**Motif de la demande :** l'utilisateur a fait analyser le module par
un outil de revue de code externe et a demandé de vérifier la
justesse et la pertinence de chaque point avant d'agir.

**Détail des modifications :**

- **Fuite d'ancre à l'anonymisation (corrigé).** `_anonymiser_html()`
  ne remplaçait que le texte visible et les courriels, laissant les
  ancres de lien (`id='personne-jean-dupont'`) dérivées du nom réel -
  une limite déjà documentée dans le code, confirmée par la revue.
  Corrigé en étendant le même mécanisme de remplacement global
  existant pour aussi substituer le slug d'ancre par un index anonyme
  - corrige à la fois l'attribut `id=` de la section ET tout lien y
  pointant (`lien_personne()`, qui construit ses liens à partir du nom
  réel sans connaître l'anonymisation). Testé avec un cas de collision
  de préfixe (Jean vs Jean-Paul Untel) pour confirmer l'absence de
  corruption croisée entre deux ancres partageant un préfixe.
- **Pièces jointes non purgées (corrigé).** Chaque téléchargement crée
  un `ir.attachment` permanent qui ne disparaît jamais (contrairement
  au wizard lui-même, un TransientModel nettoyé par Odoo, mais dont le
  nettoyage ne supprime pas les pièces jointes qui le référencent).
  Nouvelle méthode `_cron_purger_pieces_jointes(jours=3)` et tâche
  planifiée quotidienne correspondante (`data/ir_cron_purge.xml`).
- **Dépendances Python non déclarées (corrigé).** `pypdf`, `openpyxl`
  et `pyzipper` ajoutés à `external_dependencies` du manifeste - Odoo
  donnera maintenant une erreur claire à l'installation si l'un
  manque, plutôt qu'une erreur d'import tardive au moment de l'usage.
- **`sudo()` trop large sur les étiquettes (non appliqué).** Le
  correctif proposé par la revue (restreindre aux partenaires du
  rapport courant) casserait l'intention d'origine de cette
  fonctionnalité (depuis v1.14.0) : montrer TOUS les membres de la
  communauté partageant une étiquette, pas seulement ceux de ce
  rapport précis. Si l'instance est multi-société, un filtre
  `company_id` serait le correctif approprié à la vraie préoccupation
  (fuite inter-société) - à confirmer si applicable.
- **Mot de passe affiché en clair (non appliqué).** C'est une demande
  explicite formulée par l'utilisateur (v1.41.0), pas un oubli -
  laissé à sa discrétion de le conserver ou non.
- **N+1 dans `_compute_rlq_stats` (non appliqué).** Réel en principe,
  mais peu prioritaire à l'échelle réaliste de ce module. Le
  remplacement SQL proposé par la revue calcule en plus la mauvaise
  métrique (étendue première/dernière réponse, pas la durée moyenne
  par personne) - vérifié en le testant mentalement contre sa propre
  logique, pas implémenté.
- **`commit()` dans `_envoyer_notification` (non appliqué).**
  Délibéré et déjà documenté en commentaire dans le code - nécessaire
  pour qu'une notification bus soit visible pendant qu'une transaction
  est encore en cours.
- **Doublon de déclaration de vue (non appliqué).** Doublon réel, mais
  un commentaire déjà présent dans le code explique qu'il contourne un
  problème réel déjà rencontré (mauvaises colonnes dans la fenêtre
  "Ajouter une ligne"). Non touché par prudence, faute de pouvoir
  tester sur une instance réelle.
- **Remplacement `lxml` proposé (non appliqué, testé et invalidé).**
  Le code exact proposé a été testé dans cet environnement : il perd
  silencieusement tout texte apparaissant avant la première balise
  HTML (`root.text` non capturé par la boucle proposée) - confirmé par
  un test direct montrant une vraie perte de contenu. L'implémentation
  manuelle existante (5 tests dédiés, tous passants) est conservée.

**Garde-fous et cas limites :**
- La purge des pièces jointes ne s'applique qu'à
  `res_model = 'rlq.survey.report.wizard'` - aucune autre pièce
  jointe de l'instance n'est affectée.
- Le remplacement d'ancre lors de l'anonymisation suit le même tri
  "du plus long au plus court" déjà utilisé pour les noms, évitant
  qu'un slug plus court corrompe un slug plus long qui le contient.

**Vérifications effectuées :** correctif d'ancre testé en isolation
(cas de collision de préfixe). Code `lxml` proposé par la revue
testé directement et confirmé défaillant (perte de texte). Suite
`test_report_builder.py` réexécutée (45/45 passent). Quatre nouveaux
tests ajoutés à `test_wizard.py` (purge après 3 jours, non-purge
avant, cohérence des ancres anonymisées) - non exécutables ici, faute
d'instance Odoo. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés et nouveaux. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le
service. Vérifiez que la tâche planifiée "RLQ Rapport de sondage :
purge des pièces jointes" apparaît bien dans Réglages > Technique >
Tâches planifiées. Pour le point sur `sudo()`/étiquettes : précisez
si cette instance est multi-société pour qu'un correctif approprié
puisse être proposé si nécessaire.

---

## 18.0.1.50.0

**Titre court :** CONFIRMÉ - le message "après le clic" fonctionne
maintenant ; ajout de la liste des dates de participation à vie
(sondages remplis, événements inscrits) sous chaque participant, pas
seulement le total.

**Motif de la demande :** (1) sous les noms des participants, afficher
la liste de toutes les dates auxquelles un participant a assisté,
pour "Sondages remplis (total, tous temps)" et "Événements inscrits" -
pas seulement le total actuel ; (2) confirmation que la fenêtre en
haut à droite apparaît maintenant après le clic sur Générer.

**Détail des modifications :**

- **(2)** Aucun changement de code nécessaire - confirmation reçue que
  le correctif de la v1.49.0 (retour au mécanisme `display_
  notification` direct plutôt que le bus) fonctionne. Noté dans
  NOTES_VALIDATION.md.
- **(1)** Nouvelle fonction `liste_dates_simple()` dans
  `report_builder.py` (même patron que `liste_personnes_simple()`,
  déjà utilisée pour les membres d'étiquette) : affiche une liste de
  dates triées de la plus récente à la plus ancienne, en texte simple
  sous le seuil de 4 dates, ou en liste dépliable au-delà. Le bloc de
  requêtes groupées existant (déjà optimisé pour éviter une requête
  par participant, voir le correctif de la v1.49.0) est étendu pour
  aussi récupérer, en deux requêtes groupées additionnelles
  (`survey.user_input`/`event.registration`), la date de chaque
  sondage rempli et de chaque événement inscrit - la date d'un
  sondage réutilise `rlq_date_titre` (champ calculé disponible sur
  N'IMPORTE QUEL sondage, pas seulement ceux inclus dans ce rapport),
  avec repli sur la date de création. Les deux lignes existantes
  ("Sondages remplis"/"Événements inscrits") affichent maintenant le
  total ET la liste des dates correspondantes.

**Garde-fous et cas limites :**
- Le seuil de bascule vers une liste dépliable est plus élevé pour les
  dates (4) que pour les noms de personnes (2) - un historique de
  plusieurs années peut légitimement compter plus d'entrées avant
  qu'une liste dépliable soit préférable à du texte simple.
- Les dates sont dédupliquées (au cas où, en théorie, deux sondages
  auraient exactement la même date).

**Vérifications effectuées :** `liste_dates_simple()` testée en
isolation (vide, sous le seuil, au-dessus du seuil, tri, déduplication)
- 5 nouveaux tests, suite complète à 45 tests, tous confirmés passants.
Nouveau test ajouté à `test_wizard.py` pour confirmer l'affichage des
dates dans un rapport réel (non exécutable ici, faute d'instance
Odoo). Syntaxe Python validée. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.49.0

**Titre court :** CORRECTIF (vraie duplication trouvée : "Sondages
remplis"/"Événements inscrits" apparaissaient deux fois - une
implémentation équivalente existait déjà), tooltips retirés pour
"Satisfaction globale", message "après le clic" restauré via le
mécanisme historique prouvé fiable.

**Motif de la demande :** (1) toujours rien avant ni après le clic sur
Générer - précision cruciale : "cela a déjà bien fonctionné à un
moment donné" ; (2) retirer les tooltips sur le texte de "Satisfaction
globale" ; (3) doublons signalés sous le nom des participants
("Sondages remplis"/"Événements inscrits" chacun affiché deux fois).

**Détail des modifications :**

- **(3) - vraie cause trouvée.** En cherchant la source de la
  duplication, découverte qu'une implémentation de "Sondages remplis
  (total, tous temps)"/"Événements inscrits" existait DÉJÀ dans le
  code (basée sur `_read_group`, une requête groupée pour tous les
  participants à la fois - plus efficace qu'une requête par
  personne). La fonctionnalité ajoutée en v1.46.0 dupliquait donc
  purement et simplement quelque chose de déjà présent, sans que je
  m'en rende compte. Le bloc ajouté par erreur est retiré ; seule
  l'implémentation déjà existante (et plus efficace) demeure. Un test
  de non-régression est ajouté (`test_totaux_a_vie_pas_dupliques`)
  pour éviter de réintroduire ce genre de doublon à l'avenir.
- **(2)** Les questions matricielles dont le titre contient
  "satisfaction" (ex. "Satisfaction globale") n'envoient plus
  `dates_par_item` à `section_matrice()`, ni dans la vue par
  rencontre ni dans la Synthèse - leurs volets sont fixes et
  récurrents d'une rencontre à l'autre (contrairement aux
  présentations, uniques chaque mois), un tooltip de date n'y apporte
  donc rien d'utile. La variable de détection déjà utilisée pour les
  graphiques de tendance par volet est réutilisée pour cohérence et
  éviter un calcul redondant.
- **(1)** Pour le message "après le clic" (cas écran) : retour au
  mécanisme `display_notification` retourné DIRECTEMENT (chaîné via
  "next" vers le rechargement) plutôt que la notification par bus -
  confirmé par un commentaire retrouvé dans le code lui-même comme
  ayant déjà fonctionné de façon fiable par le passé sur cette
  instance, contrairement au bus/websocket. S'applique désormais que
  des avertissements existent ou non (auparavant, aucun message
  n'était montré en l'absence d'avertissement). Les cas HTML/PDF
  restent inchangés (notification par bus), leur action de retour
  (téléchargement) étant incompatible avec ce chaînage direct. Pour le
  message "avant le clic" (`apercu_ampleur`), qui a maintenant connu 3
  mécanismes différents sans confirmation de succès : voir
  NOTES_VALIDATION.md, section -20, pour la vérification à faire AVANT
  d'envisager un 4e mécanisme (confirmer que la mise à jour du module
  a bien été prise en compte).

**Garde-fous et cas limites :**
- Le retrait du tooltip pour "Satisfaction globale" n'affecte que le
  tooltip de DATE sur le nom de l'item - la barre garde son propre
  tooltip de moyenne comme pour toute autre question matricielle.

**Vérifications effectuées :** suite `test_report_builder.py`
complétée à 40 tests (39 précédents + 1 nouveau pour l'exclusion du
tooltip) - tous confirmés passants. Nouveaux tests ajoutés à
`test_wizard.py` pour la non-duplication des totaux à vie (non
exécutables ici, faute d'instance Odoo). Syntaxe Python et XML
validées sur l'ensemble des fichiers modifiés. Recherche automatisée
de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : les doublons sous le nom des participants
ont-ils disparu ? Un message s'affiche-t-il maintenant après le clic
sur Générer (cas écran) ? Pour le message AVANT le clic, voir la
vérification de version demandée dans NOTES_VALIDATION.md avant de
signaler à nouveau.

---

## 18.0.1.48.0

**Titre court :** confirmation des renseignements personnels déplacée
tout en haut du formulaire en pleine largeur (ne prend plus 3 lignes),
note sur le mot de passe raccourcie et étendue (2 lignes au lieu de
4), aperçu d'ampleur (v1.46.0) converti d'un onchange à un champ
calculé après avoir été signalé complètement invisible.

**Motif de la demande :** (1) la case de confirmation, dans une
colonne étroite, prend 3 lignes - la mettre tout en haut, avant le
titre ; (2) la note sur le mot de passe prend 4 lignes en colonne -
l'afficher sur 2 lignes ; (3) toujours aucun message visible ni avant
ni après le clic sur Générer (clarifié : l'aperçu d'ampleur de la
v1.46.0 ne s'affichait tout simplement jamais, pas seulement après le
clic).

**Détail des modifications :**

- **(1)** L'encadré de confirmation est déplacé tout en haut du
  `<sheet>`, avant même le titre du formulaire (`<div class="oe_title">`),
  et n'est plus un enfant direct d'un `<group>` (qui l'aurait confiné à
  une seule cellule de sa grille à 2 colonnes, causant le retour à la
  ligne sur 3 lignes) - il prend maintenant naturellement toute la
  largeur du formulaire.
- **(2)** Le texte explicatif du mot de passe reçoit `colspan="2"`
  (span sur les deux colonnes du groupe plutôt qu'une seule) et est
  légèrement raccourci, pour tenir sur environ 2 lignes plutôt que 4.
- **(3) - cause réelle trouvée.** `apercu_ampleur` (v1.46.0) reposait
  sur `@api.onchange`, qui ne se déclenche de façon fiable que sur un
  changement de champ INTERACTIF - or ce formulaire s'ouvre le plus
  souvent avec `survey_ids` déjà rempli via le contexte
  (`default_survey_ids`, depuis un sous-menu ou le filtre rapide), pas
  par une saisie interactive, ce qui peut empêcher l'onchange de se
  déclencher. Converti en champ CALCULÉ
  (`compute="_compute_apercu_ampleur"`, non stocké) - un mécanisme
  différent, qui se réévalue à chaque affichage du formulaire peu
  importe comment `survey_ids` a reçu sa valeur. Test correspondant
  mis à jour dans `test_wizard.py` (accéder au champ suffit à
  déclencher son calcul, plus besoin d'appeler une méthode onchange
  explicitement).

**Garde-fous et cas limites :**
- Un champ calculé non stocké (`store` non précisé, donc `False` par
  défaut) se réévalue à chaque lecture de l'enregistrement - aucune
  écriture supplémentaire en base, contrairement à un champ stocké.

**Vérifications effectuées :** `test_report_builder.py` réexécuté
(39/39 passent, aucune régression). `test_wizard.py` mis à jour et
retesté syntaxiquement (non exécutable ici, faute d'instance Odoo).
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Recherche automatisée de toute affectation risquée sur `self` -
aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que l'aperçu d'ampleur s'affiche maintenant bien,
peu importe comment le formulaire a été ouvert (sous-menu, filtre
rapide, ou sélection manuelle).

---

## 18.0.1.47.0

**Titre court :** RÉSOLU - vrai lien de test du sondage, grâce à deux
URL réelles fournies par l'utilisateur (bandeau « Ceci est une entrée
d'un sondage test » confirmé).

**Motif de la demande :** l'utilisateur a fourni l'URL exacte obtenue
en cliquant sur le bouton natif « Test » d'Odoo, ainsi que l'URL
normale du même sondage pour comparaison - permettant de corriger ce
point avec certitude après deux tentatives infructueuses.

**Détail des modifications :**

- Confirmé par comparaison directe des deux URL : le lien de test
  suit le format `/survey/<jeton du sondage>/<jeton d'une entrée
  survey.user_input>`, différent du lien normal (`/survey/start/<jeton
  du sondage>`, confirmé correct pour `get_start_url()`). Contrairement
  au lien normal, le lien de test a besoin du jeton d'une entrée
  précise, déjà créée en base avec `test_entry: True`.
- `_lien_test_sondage()` réécrite : cherche d'abord une entrée de test
  déjà créée par l'utilisateur courant pour ce sondage (évite d'en
  créer une nouvelle à chaque génération de rapport) ; sinon, en crée
  une. Repli silencieux sur `get_start_url()` si la création échoue
  (ex. champ `test_entry` inexistant sur cette instance), avec un
  avertissement dans les logs plutôt qu'un rapport en échec.
- Le lien affiché redevient « tester » (au lieu de « ouvrir », son nom
  temporaire depuis la v1.37.0) - honnête maintenant que c'est un vrai
  lien de test.

**Garde-fous et cas limites :**
- **Effet de bord assumé** : une vraie entrée `survey.user_input` est
  créée en base à la première génération de rapport pour chaque
  sondage (par utilisateur), et y reste de façon permanente - elle est
  cependant automatiquement exclue des statistiques réelles par Odoo
  (filtre « Sauf entrées test », actif par défaut).
- Si la création échoue pour une raison quelconque, le rapport n'est
  jamais mis en échec - repli sur le lien normal.

**Vérifications effectuées :** format de l'URL construite comparé
caractère pour caractère à l'URL réelle fournie - identique. Deux
nouveaux tests ajoutés à `test_wizard.py` (création de l'entrée de
test, réutilisation plutôt que duplication) - non exécutables ici,
faute d'instance Odoo. `test_report_builder.py` réexécuté (39/39
passent, aucune régression). Syntaxe Python validée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez que le lien « tester » affiche maintenant bien le bandeau
« Ceci est une entrée d'un sondage test ».

---

## 18.0.1.46.0

**Titre court :** aperçu permanent de l'ampleur de la génération
(remplace la notification bus peu fiable), lifetime sondages/
événements par participant, confirmation déplacée en haut, message de
patience à côté du bouton Générer, champ Thème retiré du formulaire.

**Motif de la demande :** (1) le message indiquant le nombre de
sondages/participants à traiter ne s'affiche plus - demande de
changer le curseur pour indiquer une attente ; (2) le lien "ouvrir"
un sondage ne mène pas à un vrai sondage test ; (3) ajouter le nombre
total (tous temps) de sondages remplis et d'événements auxquels un
participant s'est inscrit ; (4) afficher le message de patience à
droite du bouton Générer ; (5) déplacer la case de confirmation entre
la liste des sondages et les filtres, pour mieux la voir ; (6) retirer
le champ Thème du formulaire, changeable après génération.

**Détail des modifications :**

- **(1)** Même diagnostic et même solution que pour l'avertissement de
  mot de passe faible (v1.37.0) : la notification bus ne s'affiche
  visiblement pas de façon fiable sur cette instance. Nouveau champ
  `apercu_ampleur`, mis à jour par `@api.onchange("survey_ids",
  "include_partial")`, affiché en permanence juste après la case de
  confirmation - "X sondage(s) sélectionné(s), Y participant(s) au
  total à traiter." La notification bus correspondante est retirée
  de `action_generate()` (devenue redondante). **Sur le changement de
  curseur demandé** : ceci nécessiterait l'ajout de JavaScript
  personnalisé (enregistrement d'un bundle d'assets), une
  complexité et un risque jugés injustifiés étant donné les
  difficultés déjà rencontrées avec du JavaScript non testable dans
  ce projet - voir la réponse donnée dans la conversation pour le
  détail de ce choix.
- **(2)** Toujours pas résolu - voir NOTES_VALIDATION.md, section -18,
  pour l'explication complète (le bandeau "sondage test" est lié à
  l'état du sondage, pas à un lien spécial) et l'information précise
  nécessaire pour corriger ceci avec certitude plutôt que deviner une
  quatrième fois.
- **(3)** Pour chaque participant ayant une fiche contact liée, deux
  nouvelles lignes : "Sondages remplis (total, tous temps)"
  (`survey.user_input` au statut "done", tous sondages confondus, pas
  seulement ceux du rapport courant) et "Événements inscrits" (compte
  total de `event.registration`), toutes deux en `sudo()` par
  cohérence avec le reste du module (voir l'incident v1.38.0).
- **(4)** Le message de patience devient un `<span>` inline dans le
  pied de page, juste après le bouton "Générer", plutôt qu'un encadré
  séparé plus haut dans le formulaire.
- **(5)** La case de confirmation est déplacée juste après la liste des
  sondages, avant la section des filtres.
- **(6)** Le champ `theme` est retiré de la vue (la valeur par défaut
  reste appliquée à la première génération ; le sélecteur de thème
  déjà présent dans le rapport généré permet de le changer ensuite).

**Garde-fous et cas limites :**
- `apercu_ampleur` se vide simplement si aucun sondage n'est
  sélectionné, sans erreur.
- Les totaux à vie (3) ne s'affichent que si le participant a une
  fiche contact liée (comme les autres coordonnées de ce même bloc).

**Vérifications effectuées :** `test_report_builder.py` réexécuté
(39/39 passent, aucune régression). Deux nouveaux tests ajoutés à
`test_wizard.py` pour `_onchange_apercu_ampleur()` (non exécutables
ici, faute d'instance Odoo). Syntaxe Python et XML validées sur
l'ensemble des fichiers modifiés. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.
Pour le point (2), voir la question posée dans la réponse à
l'utilisateur - votre retour est nécessaire pour corriger ce point
avec certitude.

---

## 18.0.1.45.0

**Titre court :** ajout d'une suite de tests automatisés - 39 tests
pour `report_builder.py` (exécutés et confirmés passants) et des tests
Odoo `TransactionCase` pour le wizard (non exécutables sans instance
Odoo, mais prêts à l'emploi).

**Motif de la demande :** demande de tests locaux supplémentaires, et
question sur l'existence d'un cadre de test Odoo pour valider
l'ensemble des fonctionnalités du module.

**Détail des modifications :**

- Nouveau dossier `tests/`, avec `__init__.py` import défensif
  (`test_wizard` échoue proprement si le paquet `odoo` est absent,
  sans empêcher `test_report_builder` de s'exécuter seul).
- **`test_report_builder.py`** (39 tests, **exécutés avec succès**
  dans cet environnement, aucune dépendance à Odoo) : couvre la
  normalisation de noms, l'échappement HTML, les statistiques, et
  surtout la logique la plus manipulée au fil des versions - avec un
  test dédié pour chaque régression déjà rencontrée : le retrait
  correct des `<div>` imbriqués (v1.42.0), la séparation des deux
  tooltips sur le nom vs la barre (résolu en v1.43.0), l'absence de la
  classe `-inline` causant des fenêtres superposées (v1.44.0), et la
  non-fragmentation du comptage par les précisions "Autre" (v1.42.0).
- **`test_wizard.py`** (tests Odoo `TransactionCase`, **non exécutés**
  faute d'accès à une instance) : crée un sondage de référence avec
  une question matricielle, une question à choix et une question texte
  libre, deux réponses avec des notes contrastées, puis vérifie la
  génération de base, la moyenne calculée, la section "À surveiller",
  l'anonymisation, la précision "Autre", la validation du mot de passe
  (manquant, faible, non correspondant), et le filtre rapide.

**Garde-fous et cas limites :**
- `test_wizard.py` suit les mêmes hypothèses de nommage de champs que
  le reste du module - un échec de test pointant vers un champ
  inexistant indiquerait probablement le même ajustement nécessaire
  pour le module principal sur cette instance.

**Vérifications effectuées :** `test_report_builder.py` exécuté
directement (`python3 -m unittest tests.test_report_builder -v`) -
39/39 tests passent. Syntaxe de tous les fichiers (y compris
`test_wizard.py`, non exécutable ici) validée par analyse syntaxique.

**Action requise :** aucune pour le fonctionnement du module lui-même.
Recommandé : exécutez `test_wizard.py` sur une base de test (jamais la
production) après cette mise à jour, avec
`odoo-bin -d BASE_DE_TEST -i rlq_survey_report --test-enable --test-tags rlq_survey_report --stop-after-init`.

---

## 18.0.1.44.0

**Titre court :** graphique de tendance retiré pour les questions
d'auto-évaluation (ex. "Niveau de connaissance ?"), fenêtres de détail
superposées corrigées (comportement uniforme avec les autres flèches
du rapport).

**Motif de la demande :** (1) le graphique "Tendance de la note
moyenne : Niveau de connaissance ?" n'est pas pertinent (question
d'auto-évaluation, pas de satisfaction) ; (2) dans "Organisation et
logistique", cliquer sur la nouvelle flèche à côté d'un chiffre ouvre
une fenêtre par-dessus le reste du contenu, et plusieurs fenêtres
ouvertes en même temps se superposent plutôt que d'agrandir la zone du
rapport comme les autres flèches.

**Détail des modifications :**

- **(1)** La constante `MOTS_CLES_EXCLUS_A_SURVEILLER` (introduite en
  v1.41.0 pour la section "À surveiller") est renommée
  `MOTS_CLES_QUESTIONS_AUTO_EVALUATION` et sert maintenant aussi à
  exclure le graphique de tendance par question - même logique dans
  les deux cas : une note basse (ou son évolution) à une question
  d'auto-évaluation ne reflète pas un problème de satisfaction.
- **(2)** `rendu_nombre_avec_detail_notes()` (nouvelle en v1.42.0)
  utilisait la classe `detail-inline`, dont le CSS positionne sa liste
  en `position: absolute` - un choix approprié pour un petit total
  entre parenthèses (son usage d'origine), mais qui produit exactement
  le symptôme signalé (fenêtre flottante superposée aux autres,
  plusieurs fenêtres qui s'empilent) pour une liste potentiellement
  plus longue de notes individuelles. Remplacée par la classe
  `detail-oui` seule (sans le modificateur `-inline`), déjà utilisée
  ailleurs dans le rapport pour un comportement qui repousse
  naturellement le contenu suivant plutôt que de flotter par-dessus.

**Vérifications effectuées :** les deux changements retestés en
isolation (présence/absence des classes CSS attendues dans le HTML
généré). Syntaxe Python validée. Recherche automatisée de toute
affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.43.0

**Titre court :** RÉSOLU - le tooltip de date des présentations
fonctionnait depuis le début ; c'est la fusion faite en v1.35.0 (pour
"corriger" un doublon perçu) qui plaçait l'information au mauvais
endroit. Les deux tooltips sont maintenant séparés comme prévu à
l'origine.

**Motif de la demande :** précision cruciale de l'utilisateur - le
tooltip de date apparaît bel et bien dans "Comment avez-vous aimé les
présentations ?", mais sur l'histogramme plutôt que sur le nom de la
présentation.

**Détail des modifications :**

- Cette précision révèle que l'enquête menée sur plusieurs versions
  (v1.35.0 à v1.41.0) partait d'une prémisse erronée : le mécanisme
  n'a en réalité jamais cessé de fonctionner. Le "doublon" perçu à
  l'origine (deux tooltips, un rapide et un après ~1 seconde) était
  vraisemblablement le comportement CORRECT de deux tooltips DISTINCTS
  sur deux éléments ADJACENTS (le nom du volet et sa barre) - survoler
  près de leur frontière commune déclenche l'un puis l'autre selon la
  position exacte du curseur, ce qui peut se percevoir comme un
  "doublon" sans en être un.
- `section_matrice()` (`report_builder.py`) : la date n'est plus
  fusionnée dans le tooltip de la barre (`info_bulle`, qui ne montre
  maintenant plus que la moyenne) - elle est de nouveau portée par un
  tooltip séparé sur le nom du volet/présentation lui-même
  (`<span class='a-tooltip' data-rlq-tip="Présenté le ...">`),
  indépendant de la présence ou non d'une moyenne numérique. Une ligne
  dupliquée qui aurait écrasé ce nouveau libellé a été retirée au
  passage.
- Le renommage `data-tooltip` → `data-rlq-tip` (v1.41.0), fait sur une
  hypothèse de collision avec un mécanisme interne d'Odoo, était
  vraisemblablement un correctif inutile pour ce problème précis (la
  vraie cause étant la fusion elle-même) - conservé néanmoins, n'étant
  pas nuisible.

**Vérifications effectuées :** testé en isolation - confirmé deux
tooltips bien distincts et positionnés correctement (date sur le nom,
moyenne sur la barre), y compris dans les cas limites (aucune date
connue pour un item, aucune valeur numérique pour un item avec une
date connue). Syntaxe Python validée. Comme toujours, le rendu réel
dans Odoo n'a pas pu être vérifié faute d'accès à une instance, mais
la nature du correctif (isolé, testé précisément sur le point signalé)
donne une bonne confiance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez que le tooltip de date apparaît maintenant bien au survol du
nom de la présentation, pas de l'histogramme.

---

## 18.0.1.42.0

**Titre court :** CORRECTIF probable des pages PDF presque vides
(graphiques d'évolution/tendance en mise en page flex retirés du PDF),
CORRECTIF de la précision "Autre" (la vraie cause enfin trouvée),
champs mot de passe déplacés à droite, saut de page par participant
activé par défaut, préfixe informatif dans le nom des fichiers,
filtres affichés dans le résumé des paramètres, nettoyage de code mort.

**Motif de la demande :** (1) trop de choses à gauche dans le
formulaire, déplacer tout ce qui concerne le mot de passe à droite ;
(2) activer par défaut le saut de page forcé par participant ; (3)
indiquer dans le nom du fichier généré s'il est chiffré et quel filtre
a été utilisé ; (4) indiquer les filtres utilisés dans "Paramètres
utilisés pour ce rapport" ; (5) la précision "Autre" ne fonctionne
toujours pas ; (6) les pages 2 à 5 du PDF sont presque vides, avec
seulement quelques dates.

**Détail des modifications :**

- **(5) - la vraie cause enfin trouvée.** Une recherche sur le
  fonctionnement exact d'Odoo a révélé que le commentaire "Autre,
  précisez" d'une question à choix est enregistré par Odoo comme une
  LIGNE SÉPARÉE (sans `suggested_answer_id`), et non sur la même ligne
  que le choix sélectionné - confirmé par la documentation officielle
  et le code source d'Odoo (un correctif Odoo récent, PR #165853,
  confirme explicitement l'existence de "2 lignes distinctes : la
  réponse à choix simple et le commentaire"). Le code de ce module
  ignorait systématiquement ces lignes de commentaire
  (`if not ligne.suggested_answer_id: continue`), d'où l'échec
  persistant malgré la tentative précédente (v1.40.0), qui cherchait à
  tort `value_char_box` sur la ligne DU CHOIX lui-même. Corrigé : les
  lignes sans `suggested_answer_id` mais avec un texte
  (`value_char_box`/`value_text_box`) sont maintenant traitées comme
  des précisions, rattachées au répondant via `user_input_id`.
- **(6) - correctif probable des pages presque vides.** Les nouveaux
  graphiques "Évolution dans le temps" et "Tendance de la note
  moyenne" (v1.39.0/v1.40.0) utilisent une mise en page flex
  (`display: flex`) - déjà source de bogues connus avec wkhtmltopdf
  pour les histogrammes (corrigés en v1.31.0 en les remplaçant par des
  tableaux). Nouvelle fonction générale
  `retirer_divs_par_prefixe_classe()` dans `report_builder.py`,
  gérant CORRECTEMENT l'imbrication des balises `<div>` (contrairement
  à une expression régulière non gourmande, qui s'arrêterait au
  premier `</div>` imbriqué rencontré) - testée en isolation avec une
  vraie structure de graphique imbriquée, incluant plusieurs
  occurrences consécutives. Les graphiques d'évolution/tendance sont
  maintenant entièrement retirés du PDF (le rapport à l'écran/HTML
  reste complet) plutôt que reconstruits en tableaux, jugés moins
  prioritaires visuellement qu'un histogramme de note.
- **(1)** Les champs `mot_de_passe`, `mot_de_passe_confirmation`,
  `apercu_solidite_mot_de_passe` et leur texte explicatif sont
  déplacés de la colonne de gauche vers la colonne de droite du
  formulaire.
- **(2)** `pdf_saut_page_participant` passe à `default=True`.
- **(3)** Nouvelle méthode `_prefixe_nom_fichier()` : construit un
  préfixe (ex. `enc-pause-cafe-`) inséré avant la date/heure dans le
  nom de chaque fichier téléchargé (HTML, PDF, Excel) - "enc" si le
  mot de passe est renseigné, puis un mot-clé correspondant à la
  catégorie de sondages choisie (filtre rapide ou sous-menu d'origine).
  Testée en isolation (avec/sans mot de passe, différentes catégories,
  gestion correcte des accents via la fonction `slug()` existante).
- **(4)** `_resume_parametres()` affiche maintenant une ligne "Filtre
  rapide utilisé" avec la catégorie choisie et les éventuels réglages
  additionnels (mot-clé personnalisé, seuil de participants, texte
  exclu, nombre de mois), quand un filtre rapide a été utilisé.
- **Nettoyage.** Du code mort a été repéré et retiré : un reste de
  l'ancien export CSV séparé (consolidé en Excel depuis la v1.37.0)
  traînait après un `return`, jamais exécuté mais référençant une
  variable (`tampon_texte`) qui n'existe plus dans ce contexte -
  aucun impact fonctionnel (le code n'était jamais atteint), mais
  source de confusion à la lecture.

**Garde-fous et cas limites :**
- `retirer_divs_par_prefixe_classe()` s'arrête prudemment (sans lever
  d'erreur) si la structure HTML ne correspond pas à ce qui est
  attendu (balise fermante manquante) - jamais de boucle infinie ni de
  contenu tronqué de façon inattendue.
- Le préfixe de nom de fichier est purement indicatif - aucune
  incidence sur le contenu ou la protection du fichier lui-même.

**Vérifications effectuées :** `retirer_divs_par_prefixe_classe()`
testée en isolation avec une vraie structure de graphique imbriquée
(occurrence simple et multiples occurrences consécutives) - contenu
environnant confirmé intact dans les deux cas. Préfixe de nom de
fichier testé en isolation pour plusieurs combinaisons, y compris avec
des accents (via la vraie fonction `slug()`, pas une version
simplifiée). Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Recherche automatisée de toute affectation risquée
sur `self` - aucune trouvée. Comme toujours, le rendu réel dans Odoo
(disparition effective des pages presque vides, apparition de la
précision "Autre" dans un vrai rapport) n'a pas pu être vérifié faute
d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité absolue : les pages du PDF sont-elles maintenant
correctement remplies ? La précision "Autre" apparaît-elle enfin pour
"Où avez-vous vu l'annonce ?" ?

---

## 18.0.1.41.0

**Titre court :** mot de passe demandé deux fois (avec affichage en
clair une fois confirmé), erreur de mot de passe fiable (fenêtre
native Odoo plutôt qu'une notification bus), critères PCI DSS
toujours visibles, liens sous les dates rendus absolus, tentative de
correction du doublon de tooltip (renommage d'attribut), format PDF
en 11x17 portrait, filtre par nombre de mois, détail des notes déplacé
sur une flèche inline, description du manifeste allégée, et plusieurs
autres ajustements.

**Motif de la demande :** (1) filtre pour les X derniers mois ; (2) le
mot de passe devrait être demandé deux fois et affiché pour vérifier
l'absence d'erreur ; (3) la fenêtre reste ouverte après un
téléchargement HTML réussi, et le texte de la norme PCI DSS devrait
être visible en permanence ; (4) le doublon de tooltip n'apparaît que
dans l'app Odoo (PWA), pas dans le fichier HTML - et le tooltip de
date manque toujours pour "Comment avez-vous aimé les présentations
?" ; (5) retirer "Niveau de connaissance ?" de la section À
surveiller ; (6) lien sur "licence AGPL-3" ; (7) confirmation que la
précision "Autre" fonctionne toujours ; (8) format 11x17 (A3) portrait
pour le PDF ; (9) les liens sous les dates pointent vers un
emplacement local plutôt que le serveur ; (10) l'erreur de mot de
passe invalide devrait s'afficher dans une fenêtre plus grande, avec
le message détaillé ; (11) déplacer le détail des notes sur une
flèche inline plutôt qu'une colonne séparée ; (12) alléger la
description du module affichée dans les Apps ; (13) réponses
partielles et anonymisation activées par défaut.

**Détail des modifications :**

- **(2), (3), (10) - flux du mot de passe repensé.** Nouveau champ
  `mot_de_passe_confirmation` : le mot de passe est maintenant demandé
  deux fois, dans le formulaire principal ET la fenêtre de demande
  dédiée. `_onchange_mot_de_passe()` (déclenché sur les deux champs)
  affiche en direct : rien tant que les deux sont vides, une invite à
  remplir les deux champs si un seul est rempli, un avertissement de
  non-correspondance si les deux diffèrent, les critères manquants si
  le mot de passe est trop faible, ou - une fois les deux identiques
  ET suffisamment solides - le mot de passe **affiché en clair** pour
  vérification visuelle (« ✓ Confirmé et solide : ... »).
  `_verifier_mot_de_passe_ou_demander()` refondue : si l'un des deux
  champs est vide, rouvre simplement la fenêtre de demande (rien à
  signaler) ; si les deux sont remplis mais ne correspondent pas ou
  sont trop faibles, lève maintenant une UserError - une fenêtre
  native d'Odoo, fiable et bien visible, plutôt qu'une notification
  bus qui s'est déjà avérée peu fiable sur cette instance. Les
  critères PCI DSS sont désormais aussi affichés en texte permanent
  (pas seulement au survol) à côté du champ, dans les deux vues.
- **(3) - fenêtre qui ne se ferme pas après téléchargement.**
  Recherche effectuée : combiner "déclencher un téléchargement" et
  "fermer la fenêtre" en un seul retour n'est pas possible nativement
  dans Odoo sans un module tiers (`ir.actions.act_multi`, non garanti
  installé) - `close_on_report_download` existe mais ne s'applique
  qu'aux rapports natifs (`report_action()`), pas à notre flux qui
  doit intercepter les octets pour les chiffrer. Une notification
  collante (sticky) est ajoutée après un téléchargement HTML/PDF
  réussi, expliquant clairement que la fenêtre ne se ferme pas
  automatiquement (limite connue d'Odoo) et qu'il est normal/sûr de la
  fermer avec le bouton Annuler.
- **(9) - liens locaux plutôt que vers le serveur.** Nouvelle méthode
  `_url_absolue()` préfixant un chemin relatif avec `web.base.url` -
  appliquée aux liens de configuration du sondage et de l'événement
  (auparavant des chemins relatifs `/web#model=...`, corrects à
  l'écran dans Odoo mais incorrects une fois le rapport exporté hors
  d'Odoo). Le lien de page publique de l'événement (`website_url`,
  généralement un chemin relatif dans Odoo) est aussi corrigé de la
  même façon si nécessaire.
- **(4) - nouvelle tentative pour le doublon de tooltip.** L'indice
  fourni (doublon seulement dans l'app Odoo/PWA, absent du fichier
  HTML autonome) a orienté vers une collision possible avec un
  mécanisme propre au client web d'Odoo. Notre attribut `data-tooltip`
  est renommé `data-rlq-tip` partout (CSS et HTML généré) - un
  changement mécanique à faible risque. Le tooltip de date toujours
  manquant pour "Comment avez-vous aimé les présentations ?"
  spécifiquement reste à diagnostiquer (voir NOTES_VALIDATION.md).
- **(5)** Nouvelle constante `MOTS_CLES_EXCLUS_A_SURVEILLER` (mot-clé
  "niveau de connaissance" pour l'instant, extensible) : une question
  correspondante n'alimente plus la section "À surveiller", une note
  basse d'auto-évaluation n'étant pas un signe d'insatisfaction.
- **(6)** Le texte "AGPL-3" du pied de rapport devient un lien vers
  https://www.gnu.org/licenses/why-affero-gpl.fr.html.
- **(7)** Vérifié : le mécanisme de précision "Autre" (v1.40.0) est
  toujours en place et correctement câblé.
- **(1)** Nouveau champ "Sondages des N derniers mois (0 = tous)",
  basé sur `rlq_date_titre` (déjà utilisé partout ailleurs dans le
  module comme date canonique d'une rencontre), intégré au même
  mécanisme de filtre rapide que les autres (catégorie, seuil de
  participants, exclusion par texte).
- **(8)** Format de papier du PDF changé de 8x14 paysage à 11x17
  portrait (279 x 432 mm). Non vérifié : l'apparence du tableau et des
  colonnes en format portrait, plus étroit qu'en paysage - à valider
  visuellement.
- **(11)** Nouvelle fonction `rendu_nombre_avec_detail_notes()` dans
  `report_builder.py`, réutilisant le même patron que
  `liste_personnes_simple()` (déjà utilisé ailleurs pour le nombre de
  membres d'une étiquette) : une petite flèche cliquable directement
  sur le chiffre "# réponses", plutôt qu'une colonne "Détail" séparée
  avec le texte "Détail des notes". `section_matrice()` simplifiée en
  conséquence (colonne "Détail" retirée). Testé en isolation, avec et
  sans ventilation activée.
- **(12)** Description du manifeste réduite de 289 à 48 lignes :
  retrait du paragraphe de compatibilité Odoo 19 (déjà présent dans
  NOTES_VALIDATION.md, rien perdu) et de l'historique complet des
  versions dupliqué depuis CHANGELOG.md. **Changement de convention à
  partir de maintenant : l'historique des versions n'est plus ajouté
  à la description du manifeste, seulement à CHANGELOG.md.**
- **(13)** `include_partial` et `anonymiser` passent à `default=True`.

**Garde-fous et cas limites :**
- Le message d'erreur du mot de passe (UserError) ne s'affiche que
  lorsque LES DEUX champs sont remplis - un seul champ rempli rouvre
  simplement la fenêtre de demande sans accusation d'erreur, le
  formulaire n'ayant pas encore été réellement soumis à ce stade.
- Le mot de passe affiché en clair (`apercu_solidite_mot_de_passe`)
  n'apparaît que lorsque les deux saisies correspondent ET respectent
  les critères - jamais affiché prématurément ou sur une saisie encore
  incomplète.

**Vérifications effectuées :** logique complète du nouvel onchange
testée en isolation (quatre cas : vide, un seul champ rempli,
non-correspondance, correspondance avec mot de passe faible,
correspondance avec mot de passe solide). `rendu_nombre_avec_detail_notes()`
et `section_matrice()` retestées en isolation. Recherche automatisée
de toute affectation risquée sur `self` - aucune trouvée. Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Comme
toujours, le rendu réel dans Odoo (affichage du mot de passe en
clair, disparition effective du doublon de tooltip, mise en page du
PDF en portrait) n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : le doublon de tooltip a-t-il disparu dans l'app
Odoo ? Le PDF en 11x17 portrait reste-t-il lisible ?

---

## 18.0.1.40.0

**Titre court :** section "À surveiller" (notes ≤ 2), précisions
"Autre" pour les choix, menu allégé, filtre déplacé en tête, seuil de
participation reformulé, chiffres en gras, tendances par item pour la
satisfaction globale, troisième investigation du tooltip de date.

**Motif de la demande :** (1) demande d'une section "À surveiller"
listant toutes les notes ≤ 2 (date, participant) ; (2) déplacer le
filtre de catégorie de titre en tête du formulaire ; (3) retirer 5
sous-menus spécifiques de "Rapports détaillés" ; (4) remplacer "Sondage
terminé seulement" par un seuil de participants ayant débuté ou
terminé ; (5) doublon de tooltip persistant sur certains histogrammes ;
(6) ajouter la précision "Autre" (texte libre) pour les questions à
choix ; (7) tendances par item pour 5 éléments de "Satisfaction
globale" ; (8) tooltip de date toujours absent dans "Comment avez-vous
aimé les présentations ?" ; (9) mettre les chiffres en gras sous les
dates.

**Détail des modifications :**

- **(1)** Nouveau champ "Ajouter une section « À surveiller » (notes ≤
  2)" (coché par défaut). Nouvel accumulateur `alertes_notes_basses`,
  peuplé au même endroit que les autres statistiques de note (aucune
  donnée supplémentaire à récupérer). Nouvelle fonction
  `section_a_surveiller()` : tableau Date/Question/Volet/Participant/
  Note, trié par note croissante (les pires en premier) puis par date
  décroissante - ajoutée à la toute fin du rapport, après les fiches de
  participants. Testée en isolation.
- **(6)** Le texte de précision d'un "Autre" (`ligne.value_char_box`)
  est maintenant capturé et affiché dans une liste dépliable séparée
  ("Précisions données pour « Autre »"), plutôt que d'être ajouté
  directement à la valeur du choix (ce qui aurait fragmenté le
  comptage - chaque personne ayant précisé un texte différent serait
  devenue sa propre ligne dans le tableau, diluant le pourcentage
  affiché pour "Autre"). `section_choix()` accepte maintenant un
  paramètre `precisions` optionnel. Testé en isolation.
- **(3)** Les sous-menus "Portes ouvertes", "Pause café", "Premier
  mardi du mois", "Sondage annuel (>100 inscriptions)" et "Tous les
  autres sondages" sont retirés du menu Rapports détaillés. Les actions
  serveur et méthodes Python sous-jacentes (`_survey_ids_pause_cafe()`,
  etc.) restent intactes, puisque le nouveau filtre rapide du
  formulaire (v1.38.0) les réutilise directement.
- **(2)** "Filtrer par catégorie de titre" et les champs qui en
  dépendent sont déplacés en tête de la colonne de gauche du
  formulaire, avant les champs d'exclusion.
- **(4)** `filtre_sondage_termine` (basé sur `date_deadline`) remplacé
  par `filtre_participants_min` (Integer, défaut 1) : exclut les
  sondages de la catégorie choisie ayant reçu moins que ce nombre de
  réponses débutées OU terminées (`rlq_answer_done_count +
  rlq_answer_in_progress_count`) - les invitations jamais ouvertes ne
  comptent pas.
- **(9)** Les chiffres des lignes "Inscrit/Terminé/Débuté sans
  terminer" et des places d'événement (Inscrits, Présence confirmée...)
  sont maintenant en gras (`<strong>`).
- **(7)** Nouvel accumulateur `synth_item_par_date` (titre -> item ->
  date -> valeurs), plus granulaire que `synth_question_date` (qui
  combine tous les volets d'une question en une seule moyenne). Pour
  toute question matricielle dont le titre contient "satisfaction"
  (recherche insensible à la casse, plutôt qu'une correspondance
  exacte fragile), un graphique de tendance séparé est affiché pour
  CHAQUE volet de la question, en plus du graphique combiné existant.
- **(5) et (8)** Troisième signalement du problème de tooltip de date.
  Nouvel indice fourni par l'utilisateur (le timing "rapide puis après
  1 seconde" évoque un tooltip natif du navigateur) ayant motivé une
  recherche exhaustive de tout attribut `title=` dans le code généré -
  aucune occurrence trouvée. La structure du tooltip CSS personnalisé a
  été revérifiée ligne par ligne sans trouver de duplication. Une
  hypothèse (titres de question légèrement différents d'une rencontre à
  l'autre, si les volets - noms de présentations - changent chaque
  mois plutôt que d'être fixes) est documentée dans
  NOTES_VALIDATION.md avec des questions précises pour avancer, plutôt
  que de proposer un troisième correctif spéculatif après deux
  tentatives infructueuses.

**Garde-fous et cas limites :**
- La section "À surveiller" ne s'affiche pas s'il n'y a aucune note ≤
  2 (`section_a_surveiller` retourne une chaîne vide dans ce cas).
- Les tendances par item de "Satisfaction globale" ne s'affichent que
  s'il y a au moins 2 dates avec au moins une valeur numérique pour cet
  item précis, comme pour le graphique de tendance déjà existant.

**Vérifications effectuées :** `section_a_surveiller()` et
`section_choix()` (avec précisions) testées en isolation. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
`report_builder.py` retesté en isolation.

**Action requise :** mettre à jour le module et redémarrer le service.
Pour les points (5)/(8), voir les questions posées dans la réponse à
l'utilisateur - une inspection du code source de la page (clic droit →
Inspecter) serait la façon la plus directe d'avancer sur ce point.

---

## 18.0.1.39.0

**Titre court :** nouvelle vue "Tendance" par question dans la
Synthèse - évolution de la note moyenne à travers les rencontres.

**Motif de la demande :** demande d'une vue "tendance" par question,
en complément du graphique d'évolution de la participation déjà
existant (v1.36.0), qui ne couvrait que Inscrit/Terminé/Débuté, pas le
contenu des réponses elles-mêmes.

**Détail des modifications :**

- Nouvel accumulateur `synth_question_date` (titre -> date -> valeurs
  numériques, tous volets/items de la question combinés), alimenté au
  même endroit que `synth_matrice`/`synth_item_date` pendant le
  traitement de chaque rencontre - aucune donnée supplémentaire à
  récupérer, juste un regroupement différent de ce qui était déjà
  calculé.
- Nouvelle fonction `section_tendance_question()` dans
  `report_builder.py` : même technique de graphique en barres CSS que
  `section_evolution()` (sans JavaScript ni SVG), mais montrant la note
  MOYENNE d'une question matricielle à travers les dates où elle a été
  posée, en ordre chronologique. N'apparaît que s'il y a au moins 2
  dates avec au moins une valeur numérique (une date sans aucune
  réponse numérique - ex. tout le monde a répondu "Je n'étais pas là" -
  ne produit pas de barre vide trompeuse). Insérée juste après le
  tableau habituel de chaque question matricielle dans la Synthèse.

**Vérifications effectuées :** testée en isolation avec plusieurs
dates et valeurs, ainsi que les cas limites (une seule date, aucune
donnée) - comportement conforme à l'attendu dans chaque cas. Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Recherche
automatisée de toute affectation risquée sur `self` - aucune trouvée.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.38.0

**Titre court :** CORRECTIF (erreur "Access Denied by record rules" sur
res.partner, confirmée en production), filtres "Sondage terminé" et
"Exclure si le titre contient" remplaçant les précédents, titre du
formulaire simplifié, deux problèmes signalés documentés après
investigation n'ayant trouvé aucun bogue de code.

**Motif de la demande :** (1) remplacer le filtre "Inscriptions
minimum" par "Sondage terminé" ; (2) remplacer le filtre par champ
personnalisé par une exclusion de texte dans le titre ; (3) simplifier
le titre du formulaire ; (4) le message de progression au clic sur
« Générer » ne s'affiche plus ; (5) le tooltip de date des présentations
manque toujours dans la Synthèse ; (7) erreur confirmée dans les logs
Odoo : "Access Denied by record rules... model: res.partner".

**Détail des modifications :**

- **Erreur res.partner (priorité absolue).** `_respondent_nom()`,
  `_respondent_email()`, et la construction des détails d'un
  participant (téléphone, mobile, ville, pays, étiquettes) lisaient des
  champs de `res.partner` sans `sudo()`. Un « Utilisateur » du module
  Sondage peut légitimement générer ce rapport sans avoir un accès
  direct, via les règles d'enregistrement d'Odoo, à CHAQUE fiche
  contact individuelle (ex. environnement multi-société) - confirmé
  par l'erreur observée. Puisque montrer ces coordonnées est le but
  même de ce rapport (déjà protégé par ailleurs), lire ces champs
  précis en `sudo()` est corrigé à la source, plus la recherche des
  membres d'une étiquette et celle des inscriptions d'événement
  (`event.registration`), par cohérence préventive.
- **(1)** `filtre_inscriptions_min` (Integer) remplacé par
  `filtre_sondage_termine` (Boolean) : ne garde que les sondages dont
  la date limite de réponse (`date_deadline`, si le champ existe et est
  renseigné) est déjà passée.
- **(2)** `exclure_champ_custom_nom`/`exclure_champ_custom_valeur`
  remplacés par `filtre_exclure_titre_contient` (Char) : tout sondage
  de la catégorie choisie dont le titre contient ce texte est exclu -
  plus simple et plus direct que l'ancienne approche par nom de champ
  technique.
- **(3)** Titre du formulaire simplifié de « Rapport de sondage RLQ »
  à « Rapport de sondage » (tant la valeur par défaut que la variante
  dynamique avec le menu d'origine) - le titre du contenu du rapport
  lui-même (PDF, page HTML) n'est volontairement pas touché, la
  demande portant sur « le titre du formulaire ».
- **(4) et (5)** Les deux signalés comme non fonctionnels, mais AUCUN
  bogue trouvé après relecture complète du code et de nouveaux tests en
  isolation (voir le détail dans NOTES_VALIDATION.md, sections -11/-12).
  Pour (4) : le mécanisme d'envoi est intact, mais étant donné qu'un
  problème de même nature (notification bus non visible) a déjà été
  confirmé pour l'avertissement de mot de passe faible - corrigé en
  v1.37.0 en abandonnant le bus au profit d'un champ permanent -
  l'hypothèse la plus probable est un problème d'infrastructure de
  notification propre à cette instance, pas un bogue de ce module.
  Pour (5) : `section_matrice()` avec des dates a été retesté en
  isolation avec succès ; des questions de clarification sont posées
  dans la réponse à l'utilisateur plutôt que de deviner un correctif
  qui ne réglerait pas le vrai problème.

**Garde-fois et cas limites :**
- `_sondage_est_termine()` retourne toujours False (jamais "terminé")
  si `date_deadline` n'existe pas ou n'est pas renseigné - un sondage
  sans date limite n'est jamais exclu par erreur par ce filtre.

**Vérifications effectuées :** recherche systématique de tous les
accès à `res.partner`/`.partner_id` dans le module pour identifier tous
les endroits à corriger, pas seulement celui de l'erreur observée.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Recherche automatisée de toute affectation risquée sur `self` (voir
l'incident de la v1.30.0) - aucune trouvée. `report_builder.py`
retesté en isolation, y compris le mécanisme de tooltip par date.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité absolue que l'erreur "Access Denied" a disparu des
logs. Pour les points (4) et (5), voir les questions posées dans la
réponse à l'utilisateur - votre retour est nécessaire pour avancer.

---

## 18.0.1.37.0

**Titre court :** retour visuel permanent sur la solidité du mot de
passe, lien « ouvrir » du sondage corrigé, heure d'événement en heure
locale, notes d'événement retirées, espacement corrigé, libellés
inscrits/présents clarifiés, titre du formulaire dynamique, filtre
rapide par catégorie de titre, export Excel multi-feuilles remplaçant
le CSV.

**Motif de la demande :** (1) demande de remplacer le CSV par un
classeur Excel unique, pour permettre des tableaux croisés dynamiques ;
(2) les heures d'événement s'affichaient en UTC plutôt qu'en heure
locale ; (3) trop d'information avec les notes d'événement affichées ;
(4) le lien « tester » un sondage menait en fait à la page d'accueil ;
(5) espacement insuffisant avant la ligne « Créé le » ; (6) question
sur le sens exact d'« Inscrits » vs « Présents » (des chiffres qui
semblaient incohérents) ; (7) demande d'un filtre par catégorie de
titre (liste déroulante) avec un champ pour un mot-clé personnalisé ;
(8) demande d'un seuil minimum d'inscriptions ; (9) demande d'un filtre
d'exclusion par champ personnalisé ; (10) demande de rendre le titre du
formulaire dynamique selon le menu d'origine ; validation du mot de
passe qui semblait avoir disparu (aucune erreur visible si le mot de
passe ne respecte pas les critères PCI DSS).

**Détail des modifications :**

- **Validation du mot de passe (rapporté comme disparue).** Le code de
  validation lui-même était intact et correctement appelé - mais le
  seul retour à l'utilisateur en cas de mot de passe trop faible
  passait par une notification bus, un mécanisme déjà pris en défaut
  une fois (l'incident `notify_warning`) et qui semble avoir échoué
  silencieusement ici aussi (le `try/except` autour de l'envoi avale
  l'erreur sans en informer l'utilisateur). Nouveau champ
  `apercu_solidite_mot_de_passe`, mis à jour EN DIRECT par un
  `@api.onchange` pendant la saisie, affiché en permanence dans le
  formulaire (pas seulement via une notification transitoire) : « ⚠ Il
  manque : ... » ou « ✓ Mot de passe suffisamment solide. ». Cette
  méthode ne dépend d'aucune infrastructure de notification, donc ne
  peut pas échouer silencieusement de la même façon.
- **(4)** Confirmé par l'utilisateur : le chemin `/survey/test/<id>`,
  déjà signalé comme non revérifié en v1.35.0, ne fonctionne
  effectivement pas sur cette instance. Remplacé par `get_start_url()`
  (méthode confirmée exister sur survey.survey), et le lien renommé de
  « tester » à « ouvrir » dans l'affichage : contrairement à un vrai
  mode test, l'utiliser compte comme une réponse RÉELLE - le nouveau
  libellé ne prétend plus le contraire. Aucun lien affiché si l'URL
  obtenue est vide.
- **(2)** Les heures de l'événement (`date_begin`/`date_end`) passent
  par `fields.Datetime.context_timestamp()` avant affichage, comme
  déjà fait ailleurs dans ce module pour la date de génération - elles
  étaient auparavant affichées telles quelles (UTC, le format de
  stockage des champs Datetime d'Odoo).
- **(3)** Le bloc « Notes » (description de l'événement, tronquée à 300
  caractères) est retiré de `_html_details_evenement()`.
- **(5)** Espacement (`margin-top`) ajouté sur la ligne « Créé le / 
  Expire le », qui suivait immédiatement les listes dépliables de
  répondants sans séparation visuelle suffisante.
- **(6)** Les libellés « Inscrits » et « Présents (validés) » sont
  renommés « Inscrits (en attente de présence) » et « Présence
  confirmée », avec un commentaire expliquant que `seats_reserved` et
  `seats_used` représentent normalement deux groupes DISTINCTS
  (inscriptions confirmées vs présence validée), pas une relation
  sous-ensemble - une valeur de présence supérieure aux inscriptions
  en attente n'est donc pas nécessairement une incohérence. Incertitude
  assumée : le sens exact de ces deux champs sur cette instance précise
  n'a pas pu être vérifié directement.
- **(7), (8), (9)** Nouveaux champs `filtre_titre_predefini` (liste
  déroulante : Pause café / Portes ouvertes / Premier mardi du mois /
  Autre), `filtre_titre_autre` (mot-clé personnalisé, visible seulement
  si « Autre » est choisi), `filtre_inscriptions_min` (seuil, défaut 1)
  et `exclure_champ_custom_nom`/`exclure_champ_custom_valeur`
  (exclusion par champ personnalisé, nom technique vérifié dynamiquement
  avant utilisation). Un nouvel `@api.onchange` réutilise directement
  les méthodes déjà existantes des sous-menus de sélection rapide
  (`_survey_ids_pause_cafe()`, etc.) plutôt que de dupliquer leur
  logique, puis applique le seuil et l'exclusion en plus.
- **(10)** Le titre du formulaire (`<h1>`) devient dynamique : « Rapport
  de sondage RLQ » par défaut, ou « Rapport de sondage : {menu_origine}
  » si le formulaire a été ouvert depuis un sous-menu (le champ
  `menu_origine` contenait déjà cette information, utilisée jusqu'ici
  seulement dans le résumé des paramètres).
- **(1)** Les deux exports CSV (v1.36.0) sont remplacés par un export
  Excel unique (`action_export_excel`, bouton « Exporter en Excel »),
  produisant un classeur à 3 feuilles via `openpyxl` : « Participations »
  (une ligne par participation), « Réponses » (une ligne par réponse
  individuelle, toutes questions confondues, structure plate pensée
  pour un tableau croisé dynamique - nouvelle méthode générique
  `_valeur_ligne_texte()` couvrant texte libre, choix, numérique, date
  et matricielle) et « Réponses libres » (le sous-ensemble texte libre
  uniquement). Toujours protégé par le même mot de passe, dans une
  archive ZIP chiffrée (inchangé). **Testé de bout en bout dans cet
  environnement** : classeur construit, sauvegardé, rechargé, contenu
  vérifié - openpyxl y est disponible, confirmant que le mécanisme
  fonctionne réellement (pas seulement en théorie).

**Garde-fous et cas limites :**
- L'export Excel nécessite `openpyxl` (message d'erreur clair sinon) en
  plus de `pyzipper` (pour la protection par mot de passe) - les deux
  bibliothèques sont indépendantes l'une de l'autre.
- Le filtre rapide par catégorie de titre REMPLACE la sélection
  actuelle de sondages dès qu'une catégorie est choisie (cohérent avec
  le comportement des sous-menus équivalents) - il ne s'additionne pas
  à une sélection manuelle déjà faite.

**Vérifications effectuées :** export Excel testé de bout en bout avec
openpyxl réellement installé dans cet environnement (construction,
sauvegarde en octets, relecture, contenu vérifié) - contrairement à
pyzipper, non disponible ici mais dont l'usage suit exactement le même
patron déjà utilisé (et non modifié) depuis la v1.36.0. Recherche
automatisée de toute affectation risquée sur `self` (voir l'incident de
la v1.30.0) - aucune trouvée. `report_builder.py` retesté en isolation.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le rendu réel dans Odoo (retour en direct sur le mot de
passe, lien "ouvrir", filtre rapide, tableau croisé dynamique construit
à partir du fichier Excel) n'a pas pu être vérifié faute d'accès à une
instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Installez `openpyxl` si ce n'est pas déjà fait (`pip install openpyxl`)
pour l'export Excel. Vérifiez en priorité : le lien "ouvrir" sous un
sondage mène-t-il maintenant au bon endroit ? Le message de solidité du
mot de passe apparaît-il bien en tapant un mot de passe trop faible ?

---

## 18.0.1.36.0

**Titre court :** case de confirmation encadrée (contraste garanti),
bouton Annuler de la fenêtre mot de passe corrigé, anonymisation
optionnelle, exports CSV protégés par mot de passe, graphique
d'évolution dans le temps, détails supplémentaires sur l'événement et
répartition présent/inscrit/non-inscrit des répondants.

**Motif de la demande :** (1) la case de confirmation restait peu
visible malgré le passage au bleu (le carré lui-même manquait de
contraste) ; (2) demande d'une option d'anonymisation ; (3) demande
d'un bouton d'export CSV/Excel protégé par mot de passe ; (4) demande
d'un graphique d'évolution dans le temps des métriques ; (5) demande de
plus de détails sur l'événement lié (inscriptions, présences, lieu,
horaire, etc.) et d'un rapprochement entre répondants et statut de
présence/inscription ; (6) le bouton Annuler de la fenêtre de demande
de mot de passe sortait du rapport plutôt que d'y revenir ; (7) demande
d'un export dédié aux réponses libres uniquement ; (8) suggestions
d'options supplémentaires (voir la réponse donnée dans la conversation).

**Détail des modifications :**

- **(1)** La case est maintenant encadrée dans une boîte blanche à
  bordure noire épaisse, garantissant le contraste indépendamment du
  rendu natif du navigateur ou de la couleur de fond environnante -
  une approche plus robuste que la précédente tentative (`accent-color`
  sur le champ), qui ne semblait pas suffire.
- **(6)** Le bouton « Annuler » de la fenêtre de demande de mot de
  passe utilisait l'attribut spécial `special="cancel"` d'Odoo, dont le
  comportement de fermeture semblait renvoyer à l'application Sondage
  plutôt qu'au formulaire du rapport (cette fenêtre ayant remplacé,
  plutôt qu'empilé sur, la fenêtre du formulaire principal). Remplacé
  par une nouvelle méthode `action_annuler_mot_de_passe()` qui rouvre
  explicitement le formulaire principal.
- **(2)** Nouveau champ « Anonymiser les participants » :
  `_anonymiser_html()` remplace, par substitution textuelle globale sur
  le rapport déjà construit, le nom de chaque participant par
  « Participant N » (même numéro partout pour une même personne, les
  plus longs noms remplacés en premier pour éviter qu'un nom court
  contenu dans un nom plus long ne le corrompe) et son courriel par
  « [courriel masqué] ». Un bogue de numérotation (qui supposait à tort
  exactement deux remplacements par personne) a été détecté et corrigé
  pendant les tests en isolation. Portée assumée et documentée : nom et
  courriel seulement, pas les autres coordonnées ; les identifiants
  d'ancre (slugs dérivés des noms) ne sont pas remplacés, une personne
  inspectant le code source pourrait donc encore deviner un nom.
- **(3) et (7)** Deux nouveaux boutons d'export, tous deux protégés par
  le même mot de passe que le HTML/PDF : « Exporter en CSV » (une ligne
  par participation : date, sondage, participant, courriel, statut,
  horodatage) et « Exporter les réponses libres » (uniquement les
  questions de type texte libre). Le CSV est encodé avec un BOM UTF-8
  pour un affichage correct des accents dans Excel. La protection par
  mot de passe utilise une archive ZIP chiffrée en AES via la
  bibliothèque `pyzipper` (le module `zipfile` standard de Python ne
  sait pas ÉCRIRE d'archive chiffrée, seulement en lire) - message
  d'erreur clair si elle n'est pas installée, plutôt que de generer un
  export non protégé silencieusement.
- **(4)** Nouvelle fonction `section_evolution()` dans
  `report_builder.py` : un graphique en barres CSS (sans JavaScript ni
  SVG, donc fonctionnel dans un fichier HTML autonome hors ligne)
  montrant l'évolution d'Inscrit/Terminé/Débuté sans terminer à travers
  les rencontres incluses, en ordre chronologique (contrairement au
  reste du rapport, en ordre inverse). N'apparaît que si au moins 2
  rencontres sont incluses. Testée en isolation avec des données
  simulées.
- **(5)** Nouvelle méthode `_html_details_evenement()` : lieu, horaire
  (sans jour de semaine), places (inscrits/présents/maximum/restantes),
  description et photo de l'événement lié - chaque élément recherché
  dynamiquement parmi les champs réels du modèle, rien n'est affiché
  s'il est absent. Nouvelle méthode
  `_repartition_presence_evenement()` : recherche les inscriptions
  (event.registration) de l'événement lié et classe chaque répondant du
  sondage en 3 groupes (Présent validé, Inscrit sans présence validée,
  Non inscrit à l'événement), par rapprochement des courriels -
  affichés en 3 listes dépliables. **Non couvert, sciemment** :
  commanditaires, kiosques, gagnants de tirage au sort - des champs
  probablement propres à votre instance, trop incertains pour être
  devinés sans risque de se tromper de nom (voir NOTES_VALIDATION.md
  pour la marche à suivre si vous voulez les ajouter).

**Garde-fous et cas limites :**
- Les exports CSV échouent avec un message clair si `pyzipper` n'est
  pas installé - confirmé absent dans l'environnement de test utilisé
  pour ce projet, probablement aussi absent par défaut sur une
  installation Odoo standard (à installer : `pip install pyzipper`).
- Le graphique d'évolution et les détails d'événement n'affichent
  simplement rien s'il n'y a pas assez de données (moins de 2
  rencontres pour le premier, aucun champ reconnu pour le second) -
  jamais d'erreur.
- Le rapprochement présence/inscription se fait par courriel
  exclusivement ; un répondant ayant utilisé une adresse courriel
  différente de celle de son inscription à l'événement apparaîtra à
  tort comme « non inscrit ».

**Vérifications effectuées :** recherche automatisée de toute
affectation risquée sur `self` (voir l'incident de la v1.30.0) -
aucune trouvée. Anonymisation retestée en isolation après correction
du bogue de numérotation. Graphique d'évolution testé en isolation
(cas normal et cas limite à moins de 2 rencontres). Construction du
CSV testée en isolation (accents, BOM UTF-8, valeurs contenant une
virgule correctement échappées par le module `csv` standard). Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés. Comme
toujours, le rendu réel dans Odoo (rapprochement présence/inscription,
affichage de la photo, export CSV protégé) n'a pas pu être vérifié
faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Installez `pyzipper` si vous comptez utiliser les exports CSV protégés
(`pip install pyzipper`). Vérifiez en priorité la case de confirmation
(maintenant bien visible ?) et le bouton Annuler de la fenêtre de mot
de passe (revient-il au bon endroit ?).

---

## 18.0.1.35.0

**Titre court :** case de confirmation moins jaune-sur-jaune, mot de
passe faible redemande maintenant correctement, tooltip de date des
présentations disponible même sans section Synthèse, lien de test du
sondage et lien de page publique de l'événement ajoutés, impression
bloquée par CSS, options PDF déplacées dans une fenêtre dédiée.

**Motif de la demande :** (1) la case à cocher de confirmation était
peu visible (jaune sur fond jaune) ; (2) un mot de passe entré mais
trop faible affichait une erreur sans offrir de le corriger sur place,
contrairement à un mot de passe manquant ; (3) le tooltip de date des
présentations avait disparu ; (4) demande d'ajouter, sous chaque
sondage/événement, un second lien (test du sondage, page publique de
l'événement) en plus des liens de configuration déjà présents ; (5)
possibilité de bloquer l'impression (Ctrl+P) pour empêcher de
contourner la protection par mot de passe via une sauvegarde en PDF ;
(6) déplacer les options spécifiques au PDF dans un bouton séparé,
puisque rarement utilisées ; (7) suggestions d'options supplémentaires
pour plus de flexibilité (voir la réponse donnée dans la conversation).

**Détail des modifications :**

- **(1)** L'encadré de confirmation passe de `alert-warning` (jaune) à
  `alert-info` (bleu), évitant le problème de contraste.
- **(2)** `_valider_solidite_mot_de_passe()` (qui levait une erreur
  franche) est complétée par `_criteres_manquants_mot_de_passe()`
  (calcule la liste sans lever d'exception) et
  `_verifier_mot_de_passe_ou_demander()` : cette dernière gère
  maintenant de façon uniforme l'absence ET la faiblesse d'un mot de
  passe, dans les deux cas en envoyant une notification expliquant le
  problème précis puis en rouvrant la fenêtre de demande de mot de
  passe pour une correction immédiate - utilisée aux trois points
  d'entrée (`action_generate`, `action_download_html`,
  `action_download_pdf`) à la place de l'ancienne vérification en deux
  étapes séparées.
- **(3)** Le paramètre `dates_par_item` de `section_matrice()` n'était
  câblé que pour la section Synthèse, laquelle est omise quand une
  seule rencontre est incluse dans le rapport (règle ajoutée en
  1.21.0) - expliquant la disparition apparente du tooltip dans ce cas,
  sans qu'il y ait de régression du mécanisme lui-même (retesté et
  confirmé fonctionnel en isolation). Câblé maintenant aussi pour la
  vue par rencontre individuelle (chaque item y reçoit la date de
  cette rencontre) - redondant avec la date déjà visible dans l'en-tête
  de section, mais garantit que le tooltip reste disponible même sans
  Synthèse.
- **(4)** `_lien_evenement()` retourne désormais l'ENREGISTREMENT
  événement trouvé (plutôt que du HTML déjà construit), permettant à
  l'appelant de construire plusieurs liens à partir du même
  enregistrement. Nouvelles méthodes : `_lien_test_sondage()` (lien
  `/survey/test/<id>`, le chemin utilisé historiquement par le bouton
  "Test" du formulaire Sondage natif d'Odoo - confirmé sur une version
  antérieure du code source d'Odoo, non revérifié spécifiquement sur
  cette instance) et `_lien_evenement_public()` (champ `website_url`
  de l'événement, recherché dynamiquement, sans erreur si absent).
  Chaque rencontre affiche maintenant le lien de configuration du
  sondage suivi de son lien de test, et le lien de configuration de
  l'événement suivi de sa page publique si elle existe.
- **(5)** Nouvelle règle CSS `@media print` masquant tout le contenu du
  rapport à l'impression, remplacé par un message explicite - empêche
  d'obtenir une copie utilisable via Ctrl+P ou "Imprimer en PDF".
  Repose sur le respect standard de cette règle par le navigateur, pas
  infaillible face à un navigateur trafiqué ou une capture d'écran
  manuelle (limite documentée dans le CSS et à communiquer aux
  utilisateurs).
- **(6)** Les trois options spécifiques au PDF (tableaux par
  participant, sauts de page par rencontre/participant) sont retirées
  du formulaire principal et déplacées dans une nouvelle fenêtre
  dédiée (`view_rlq_survey_report_wizard_form_options_pdf`), ouverte
  via un bouton "Options PDF" à côté de "Télécharger en PDF" (visible
  uniquement une fois le rapport généré, comme "Télécharger en PDF"
  lui-même).

**Garde-fous et cas limites :**
- Le lien de test du sondage (`/survey/test/<id>`) est la partie la
  moins certaine de cette version : si ce chemin ne correspond pas à
  cette version précise d'Odoo, le lien pourrait mener à une erreur
  404 plutôt que de démarrer le sondage en mode test - à vérifier en
  priorité, contrairement aux autres liens de ce module qui reposent
  sur des mécanismes déjà vérifiés ou intrinsèquement sans risque
  (recherche dynamique de champ).
- Le blocage d'impression ne protège que contre l'impression
  classique du navigateur - il ne protège pas contre une capture
  d'écran, un outil de capture PDF externe au navigateur, ou
  l'inspection du code source par une personne suffisamment
  déterminée et techniquement outillée.

**Vérifications effectuées :** rendu des liens sondage (config + test)
testé en isolation - structure HTML confirmée correcte. Tooltip de
date retesté en isolation après le câblage supplémentaire pour la vue
par rencontre. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. `report_builder.py` retesté en isolation (présence
de la règle `@media print` confirmée). Comme toujours, le rendu réel
dans Odoo (fonctionnement du lien de test, blocage effectif de
l'impression, fenêtre d'options PDF) n'a pas pu être vérifié faute
d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité le lien "tester" sous chaque sondage - c'est le
point le moins certain de cette version.

---

## 18.0.1.34.0

**Titre court :** demande directe du mot de passe (petite fenêtre)
plutôt qu'un simple message d'erreur, quand il manque pour un
téléchargement HTML/PDF.

**Motif de la demande :** le message d'erreur indiquant qu'un mot de
passe est requis n'offrait aucun moyen direct de le saisir à ce
moment précis - il fallait fermer le message, retrouver le champ dans
le formulaire, puis recliquer sur le bouton d'origine.

**Détail des modifications :**

- Nouvelle vue réduite (`view_rlq_survey_report_wizard_form_password`)
  ne montrant que le champ mot de passe et un avertissement expliquant
  pourquoi il est requis (Loi 25, RGPD) - ouverte à la place du simple
  message d'erreur, sur le même enregistrement (aucun autre paramètre
  déjà choisi n'est perdu).
- Nouvelle méthode `_action_demander_mot_de_passe(action_suivante)`,
  appelée aux trois endroits où l'absence de mot de passe est détectée
  (`action_generate`, `action_download_html`, `action_download_pdf`),
  transmettant via le contexte QUELLE action relancer une fois le mot
  de passe saisi.
- Nouvelle méthode `action_continuer_apres_mot_de_passe`, appelée par
  le bouton « Continuer » de cette petite fenêtre : elle relance la
  bonne action d'origine (lue depuis le contexte) plutôt que de
  toujours relancer « Générer » - une distinction nécessaire, puisque
  les boutons « Télécharger en HTML »/« Télécharger en PDF » (utilisés
  après une génération à l'écran) n'ont pas le même effet que
  « Générer » et ne doivent pas être confondus avec lui.

**Garde-fous et cas limites :**
- Si le mot de passe saisi via cette fenêtre ne respecte pas les
  critères de solidité (niveau PCI DSS), l'erreur habituelle s'affiche
  par-dessus cette même fenêtre, qui reste ouverte pour corriger et
  réessayer immédiatement.
- Un repli sûr existe si le contexte contenait une valeur inattendue
  pour l'action à relancer (retombe sur « Générer » par défaut).

**Vérifications effectuées :** relecture complète confirmant la
cohérence entre les trois points d'appel, la nouvelle vue et le
bouton qui la référence. Syntaxe Python et XML validées sur l'ensemble
des fichiers modifiés. Comme toujours, le comportement réel dans Odoo
n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.

---

## 18.0.1.33.0

**Titre court :** CORRECTIF CRITIQUE (persistant) - le champ mot de
passe restait invisible malgré le correctif de la v1.32.0. Retiré
toute condition dynamique sur ce champ : il est maintenant TOUJOURS
visible et modifiable dans le formulaire.

**Motif de la demande :** rapport, une seconde fois, du même problème
bloquant que la v1.32.0 était censée corriger - le champ mot de passe
demeurait introuvable dans le formulaire, empêchant de le saisir alors
qu'il est exigé pour générer un HTML/PDF.

**Détail des modifications :**

- Le correctif de la v1.32.0 (retrait du mécanisme à deux champs
  dupliqués) n'a apparemment pas suffi. Plutôt que de continuer à
  deviner la cause exacte d'un problème de rendu que je ne peux pas
  observer directement, la condition `invisible="output_format ==
  'screen'"` et l'attribut `required="output_format != 'screen'"` sur
  `mot_de_passe` sont retirés **entièrement** de la vue : le champ est
  désormais un champ ordinaire, sans aucune logique conditionnelle,
  **toujours affiché** dans le formulaire - qu'importe le format de
  sortie choisi. Sa note explicative (Loi 25/RGPD), juste en dessous,
  devient également toujours visible.
- L'obligation de le remplir pour un téléchargement HTML/PDF (et la
  validation de sa solidité, niveau PCI DSS) restent entièrement
  appliquées **côté serveur**, inchangées, dans `action_generate()` et
  dans `action_download_html()`/`action_download_pdf()` - seul
  l'affichage conditionnel dans la vue est retiré, pas la règle
  elle-même. Pour un rapport à l'écran, le champ reste donc visible
  mais peut être laissé vide sans conséquence.
- Documentation utilisateur mise à jour en conséquence (le champ
  n'apparaît plus conditionnellement - il est décrit comme toujours
  visible, avec l'obligation de le remplir précisée pour HTML/PDF
  uniquement).

**Garde-fous et cas limites :**
- Cette version privilégie délibérément la fiabilité (un champ simple,
  sans condition, garanti de s'afficher) à l'élégance (un champ
  masqué quand non pertinent) - un compromis jugé nécessaire après
  deux signalements du même problème bloquant.

**Vérifications effectuées :** relecture complète et attentive de la
section concernée de la vue, confirmant l'absence de toute condition
résiduelle sur le champ. Syntaxe Python et XML validées sur l'ensemble
des fichiers modifiés.

**Action requise :** mettre à jour le module et redémarrer le service,
puis **vider le cache du navigateur** (rechargement forcé, ex.
Ctrl+Maj+R) avant de vérifier - si le problème persistait à cause d'un
cache de vue non rafraîchi plutôt que du code lui-même, ceci pourrait
expliquer pourquoi le correctif précédent n'a pas semblé fonctionner.
Vérifiez en priorité absolue que le champ mot de passe est maintenant
visible en tout temps dans le formulaire.

---

## 18.0.1.32.0

**Titre court :** CORRECTIF CRITIQUE (le champ mot de passe avait
disparu du formulaire), formulaire réorganisé en deux colonnes
(paramètres à gauche, cases à cocher à droite).

**Motif de la demande :** (1) trop d'options dans le formulaire -
demande de déplacer les champs de paramètres (non-cases à cocher) vers
la gauche, pour ne garder que des cases à cocher à droite ; (2) rapport
d'un bogue bloquant : le champ mot de passe avait complètement disparu
du formulaire suite à la v1.31.0, empêchant de le saisir alors que le
message d'erreur en réclamait un pour générer un HTML/PDF.

**Détail des modifications :**

- **(2) CORRECTIF CRITIQUE, traité en priorité.** Le mécanisme
  « afficher/masquer le mot de passe » introduit en v1.30.0 faisait
  apparaître le champ `mot_de_passe` **deux fois** dans la même vue
  (une fois masqué, une fois en clair, avec des conditions `invisible`
  opposées) - cette duplication du même champ dans une seule vue est
  la cause la plus probable de sa disparition complète observée par
  l'utilisateur. Retiré entièrement : le champ `afficher_mot_de_passe`
  est supprimé du modèle, et `mot_de_passe` redevient un champ **unique**
  dans la vue (toujours masqué par des points, sans option de
  révélation) - une perte mineure de confort face à un bogue bloquant.
- **(1)** Le formulaire est réorganisé en deux colonnes distinctes :
  à gauche, les champs de paramètres (participants/étiquettes exclus,
  mot-clé d'exclusion, format de sortie, thème, dates, mot de passe et
  sa note explicative) ; à droite, uniquement des cases à cocher
  (réponses partielles, non-répondants, options PDF, ventilation,
  dédoublonnage). Les conditions `invisible`/`required` du mot de passe
  (basées sur `output_format`) continuent de fonctionner normalement
  malgré la séparation visuelle, puisqu'elles ne dépendent que des
  valeurs des champs, pas de leur position dans la vue.

**Garde-fous et cas limites :**
- Recherche systématique effectuée : aucune référence résiduelle à
  `afficher_mot_de_passe` ne subsiste dans le modèle ou les vues.
- La case à cocher « Confirmation des renseignements personnels »,
  dans son propre encadré distinct, n'est pas affectée par cette
  réorganisation.

**Vérifications effectuées :** recherche automatisée de toute
référence résiduelle au champ retiré - aucune trouvée en dehors du
CHANGELOG (historique, non modifié). Syntaxe Python et XML validées
sur l'ensemble des fichiers modifiés. `report_builder.py` retesté en
isolation. Comme toujours, le rendu réel du formulaire réorganisé n'a
pas pu être vérifié visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité absolue que le champ mot de passe est bien visible
et utilisable en sélectionnant le format HTML ou PDF.

---

## 18.0.1.31.0

**Titre court :** validation de solidité du mot de passe (niveau PCI
DSS v4.0), protection par mot de passe rendue obligatoire (non plus
optionnelle) pour tout téléchargement HTML/PDF, histogrammes PDF
remplacés par des tableaux HTML, espace ajouté entre les noms et
leurs badges, note sur les renseignements personnels ajoutée
directement dans le rapport.

**Motif de la demande :** (1) demande de valider la solidité du mot de
passe selon la règle PCI, avec les critères indiqués en tooltip ; (2)
demande de rendre le mot de passe obligatoire pour tout téléchargement
HTML/PDF, en citant la Loi 25 ; (3) les histogrammes ne s'affichent
toujours pas dans le PDF malgré un correctif précédent, et le nom des
participants est collé au badge « N participation(s) » ; (4) demande
d'ajouter la note « Ce rapport contient des renseignements personnels
sur les participants (noms, courriels, coordonnées) » dans le fichier
HTML et PDF.

**Détail des modifications :**

- **(1)** Recherche effectuée pour confirmer la règle PCI DSS exacte
  actuellement en vigueur : PCI DSS v4.0.1, exigence 8.3.6 (obligatoire
  depuis le 31 mars 2025), impose un minimum de 12 caractères. La norme
  elle-même n'exige littéralement que des caractères alphabétiques ET
  numériques ; la nouvelle méthode `_valider_solidite_mot_de_passe()`
  va plus loin, comme demandé, en exigeant les 4 types de caractères
  (minuscule, majuscule, chiffre, spécial) - testée en isolation contre
  plusieurs mots de passe de complexité croissante. Les critères exacts
  sont maintenant détaillés dans l'aide (tooltip) du champ mot de
  passe, avec la précision que l'exigence des 4 types dépasse la lettre
  stricte de la norme PCI DSS.
- **(2)** Le champ « Protéger le fichier par un mot de passe » (case à
  cocher optionnelle) est retiré : la protection est désormais
  automatique et obligatoire dès que le format de sortie n'est pas
  « Écran » - `mot_de_passe` devient un champ requis dans ce cas
  (`required="output_format != 'screen'"`), avec une note visible dans
  le formulaire citant la Loi 25 et le RGPD. La validation (mot de
  passe renseigné + solidité suffisante) se fait maintenant tôt dans
  `action_generate()`, avant même de lancer la génération du rapport -
  un mot de passe manquant ou trop faible échoue donc immédiatement,
  sans faire attendre l'utilisateur pour une génération qui aurait de
  toute façon échoué à la fin.
- **(3)** Le correctif précédent (largeur/affichage CSS figés sur les
  `<div>` imbriqués de l'histogramme) ne semble pas avoir suffi.
  Changement d'approche pour le PDF : les histogrammes sont maintenant
  remplacés par un simple `<table>` à deux cellules dont la largeur en
  pourcentage détermine le remplissage - une technique prise en charge
  de façon fiable par pratiquement n'importe quel moteur de rendu HTML
  depuis les tout débuts du web, contrairement à flexbox ou même aux
  largeurs CSS figées sur des `<div>` imbriqués. Testé en isolation.
  Un espace littéral (plutôt qu'une marge CSS, potentiellement ignorée
  par le même moteur PDF capricieux) est ajouté entre le nom d'un
  participant ou la date d'une rencontre et son badge, pour ne plus les
  voir collés (ex. « Jean Dupont1 participation(s) »).
- **(4)** Un bandeau bien visible (fond jaune pâle) avec le texte exact
  demandé est ajouté en tête de chaque rapport généré (HTML et PDF,
  puisqu'ils partagent le même contenu de base) - omis uniquement dans
  le cas « aucune réponse trouvée », où aucune donnée personnelle
  n'est en réalité présente.

**Garde-fous et cas limites :**
- Les vérifications de mot de passe (présence + solidité) dans
  `action_download_html()`/`action_download_pdf()` sont conservées en
  plus de celle, plus précoce, dans `action_generate()` - une
  redondance défensive au cas où ces méthodes seraient appelées
  autrement.
- Une recherche systématique a confirmé qu'aucune référence au champ
  retiré (`proteger_mot_de_passe`) ne subsiste nulle part dans le
  module.

**Vérifications effectuées :** validation de solidité testée en
isolation contre 4 mots de passe de complexité croissante (résultats
conformes à l'attendu dans chaque cas). Remplacement des histogrammes
par des tableaux testé en isolation. Recherche automatisée de toute
référence résiduelle au champ retiré, et de toute affectation risquée
sur `self` (voir l'incident de la v1.30.0) - aucune trouvée. Syntaxe
Python et XML validées sur l'ensemble des fichiers modifiés.
`report_builder.py` retesté en isolation. Comme toujours, le rendu
réel dans Odoo n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que les histogrammes s'affichent maintenant
correctement dans un PDF généré.

---

## 18.0.1.30.0

**Titre court :** CORRECTIF CRITIQUE (plantage confirmé en production
à la génération d'un PDF), CORRECTIF SÉCURITÉ (chiffrement PDF en RC4
au lieu d'AES-256), licence changée pour AGPL-3, affichage du mot de
passe en clair, confirmation obligatoire sur les renseignements
personnels avant génération.

**Motif de la demande :** rapport d'une erreur serveur confirmée en
production lors de la génération d'un PDF (`AttributeError:
'rlq.survey.report.wizard' object has no attribute
'_compteur_rencontre_pdf'`). Questions/demandes : (1) la licence
AGPL-3 serait-elle plus appropriée que LGPL-3 pour un groupe
d'utilisateurs Linux ? (2) permettre de revoir le mot de passe en clair
après l'avoir entré ; (3) le chiffrement HTML/PDF est-il vraiment
sécuritaire, difficile à pirater ? (5) demande d'une confirmation
obligatoire avant de générer, avertissant de la présence de
renseignements personnels.

**Détail des modifications :**

- **CORRECTIF CRITIQUE (priorité absolue).** `_html_pour_pdf()`
  tentait d'écrire `self._compteur_rencontre_pdf = 0` (et l'équivalent
  pour les participants) directement sur l'enregistrement du wizard,
  pour compter les occurrences lors de l'insertion des sauts de page
  en ligne (v1.29.0). Un enregistrement Odoo **refuse l'affectation
  d'attributs arbitraires** en dehors de ses champs déclarés - d'où le
  plantage confirmé, empêchant toute génération de PDF. Corrigé en
  retirant complètement cette approche : le comptage utilise
  maintenant une variable locale capturée par une fermeture
  (closure), dans une nouvelle méthode statique
  `_inserer_sauts_de_page_sauf_premier()`, qui ne touche jamais à
  `self`. Testé en isolation, y compris en simulant un objet à
  `__slots__` restrictif pour reproduire fidèlement le scénario de
  plantage - confirmé résolu. Une recherche systématique (script
  Python parcourant l'arbre syntaxique du fichier) n'a trouvé aucune
  autre affectation de ce genre ailleurs dans le module.
- **CORRECTIF SÉCURITÉ.** En vérifiant la solidité du chiffrement PDF
  suite à la question de l'utilisateur, découverte que `pypdf`
  chiffre par défaut avec **RC4** (algorithme non sécurisé, cassable
  en quelques secondes avec les outils actuels) si l'algorithme n'est
  pas précisé explicitely - ce que le code ne faisait pas.
  `redacteur.encrypt(mot_de_passe)` devient
  `redacteur.encrypt(mot_de_passe, algorithm="AES-256")`. **Testé de
  bout en bout avec un vrai fichier PDF** : chiffrement confirmé,
  déchiffrement réussi avec le bon mot de passe, rejeté avec un
  mauvais. Absence de la dépendance AES (`cryptography`/
  `pycryptodome`) maintenant interceptée avec un message clair plutôt
  qu'une erreur brute.
- **(1)** Licence changée de LGPL-3 à AGPL-3 dans le manifeste, les
  en-têtes des trois fichiers Python, et le pied de chaque rapport
  généré. Confirmé par une recherche que l'AGPL-3 est la convention
  par défaut de facto de l'OCA (Odoo Community Association) pour la
  grande majorité de ses modules communautaires - précisément parce
  qu'un module Odoo tourne comme un service web, jamais « distribué »
  au sens classique, ce qui fait qu'aucune obligation de partage du
  code source ne se déclenche jamais sous LGPL/GPL pour ce type
  d'usage (la « faille ASP/SaaS ») ; l'AGPL comble spécifiquement
  cette faille.
- **(2)** Nouveau champ `afficher_mot_de_passe` (case à cocher) :
  bascule entre l'affichage masqué (points) et en clair du mot de
  passe déjà entré, en utilisant deux fois le même champ dans la vue
  avec des conditions d'affichage opposées - aucun widget JavaScript
  personnalisé, pour éviter un nouveau risque d'API non testée après
  les incidents précédents de ce genre.
- **(3)** Voir le correctif sécurité ci-dessus pour le PDF. Pour le
  HTML (AES-256-GCM + PBKDF2-SHA256, 210 000 itérations, inchangé
  depuis la v1.29.0) : les deux mécanismes utilisent des algorithmes
  solides, mais comme pour tout chiffrement par mot de passe, la
  résistance réelle dépend entièrement de la force du mot de passe
  choisi - une fois le fichier entre les mains d'un attaquant, rien
  n'empêche des essais de mots de passe hors ligne, à la vitesse que
  permet son matériel. Un mot de passe long et aléatoire est
  nécessaire pour une protection réellement difficile à casser.
- **(5)** Nouveau champ obligatoire
  `confirmation_renseignements_personnels` (case à cocher, encadré
  orange bien visible) : `action_generate()` refuse de procéder tant
  qu'elle n'est pas cochée, avec un message clair.

**Garde-fous et cas limites :**
- Le correctif critique ne change aucun comportement visible pour
  l'utilisateur - les sauts de page en ligne fonctionnent exactement
  comme prévu en v1.29.0, simplement sans plantage.
- La confirmation sur les renseignements personnels doit être recochée
  à chaque nouvelle génération (elle n'est pas mémorisée d'une fois à
  l'autre), le wizard étant un enregistrement temporaire recréé à
  chaque ouverture.

**Vérifications effectuées :** correctif critique testé en isolation
avec un objet simulant les restrictions d'un enregistrement Odoo
(`__slots__`) pour reproduire fidèlement le plantage - confirmé résolu.
Chiffrement PDF testé de bout en bout avec un vrai fichier PDF généré
par pypdf (chiffrement, déchiffrement avec bon/mauvais mot de passe).
Recherche automatisée de tout autre risque du même genre (affectation
sur self) dans l'ensemble du fichier - aucun trouvé. Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité absolue que la génération d'un PDF fonctionne à
nouveau sans plantage - c'était complètement bloqué avant ce correctif.

---

## 18.0.1.29.0

**Titre court :** message de progression dynamique au démarrage,
notification « prêt » déplacée pour n'apparaître qu'après un
téléchargement HTML/PDF réussi, doublon de tooltip corrigé, sauts de
page PDF renforcés, histogrammes PDF réparés, critère du sondage
annuel simplifié, lien vers le sondage sous chaque date, menus
restreints au groupe Utilisateur, option de protection par mot de
passe.

**Motif de la demande :** (1) le message « Le rapport est prêt
ci-dessous » apparaissait pour le mauvais format de sortie et pas au
bon moment, absence d'un message dynamique de démarrage ; (2) deux
tooltips de date de présentation apparaissaient (un rapide, un après
~1 seconde) ; (3) les histogrammes ne s'affichent pas dans le PDF ;
(4) les options de saut de page forcé (PDF) restent sans effet ; (5)
le menu « sondage annuel » n'affiche toujours rien ; (6) demande de
rendre cliquable le nom du sondage sous chaque date, vers sa fiche
Odoo ; (7) les permissions doivent être restreintes au groupe
Utilisateur des sondages, menus cachés pour les autres ; (8) demande
d'une option de mot de passe pour le PDF/HTML, motivée par la Loi 25
(Québec) et le RGPD (Europe).

**Détail des modifications :**

- **(1)** `action_generate()` restructurée : un message dynamique
  (« Génération du rapport, il y a X sondage(s) à traiter (pour un
  total de X participant(s))… ») est envoyé dès le clic sur
  « Générer », avant même de commencer le traitement. Les
  avertissements éventuels sont maintenant envoyés via le bus (plutôt
  que chaînés à l'action retournée), donc visibles quel que soit le
  format choisi. Le message « Le rapport est prêt » n'est plus lié au
  format écran (où il n'a pas vraiment de sens) : il n'apparaît
  maintenant que pour HTML/PDF, une fois le fichier réellement généré
  (après l'appel à `action_download_html()`/`action_download_pdf()`,
  pas avant). Nouvelle méthode générale `_envoyer_notification()`
  (dont `_envoyer_progression()` devient un raccourci), pour ces
  différents types de messages.
- **(2)** La barre de moyenne (`info_bulle`, déjà son propre tooltip
  au survol) et le nouveau tooltip de date (ajouté sur le nom de
  l'item en 1.24.0) étaient deux zones de survol adjacentes dans la
  même ligne, donnant l'impression de deux tooltips distincts. Fusionnés
  en un seul : la date de présentation est maintenant ajoutée au
  tooltip existant de la moyenne (ex. « 4.5 / 5 · Présenté le
  2026-08-04 (mardi) »), le tooltip séparé sur le nom de l'item est
  retiré.
- **(3)** Les histogrammes utilisent `flex: 1` pour remplir l'espace
  disponible - wkhtmltopdf (moteur de rendu ancien, WebKit) a des
  bogues connus avec flexbox, pouvant effondrer leur largeur à 0px
  indépendamment de la couleur (déjà figée en 1.16.0 sans régler le
  problème). Ajout d'une largeur figée (140px) et d'un affichage en
  bloc, indépendants de tout calcul flexbox, dans le CSS PDF.
- **(4)** Les règles CSS de saut de page (classes `.rencontre`/
  `.personne`) sont maintenant renforcées par des styles **en ligne**
  directement sur chaque balise `<section>` concernée (sauf la toute
  première de chaque type) - les styles en ligne ont la spécificité la
  plus élevée et sont les plus fiablement respectés par un moteur PDF
  capricieux, une ceinture-et-bretelles par rapport aux seules règles
  par classe. Testé en isolation (comptage correct des occurrences,
  première section toujours épargnée).
- **(5)** Le critère « doit tomber en septembre » de
  `_survey_ids_annuel()` (v1.16.0) était vraisemblablement erroné :
  rien n'indique que l'événement visé (190 inscriptions) ait
  effectivement lieu en septembre. Cette contrainte de mois est
  retirée : le critère se limite maintenant au seuil de réponses
  (>100), sans égard au mois - le menu et son libellé sont ajustés en
  conséquence (« Sondage annuel (>100 inscriptions) »).
- **(6)** Le titre du sondage affiché sous chaque date de rencontre
  est maintenant un lien cliquable vers sa fiche dans Odoo (même
  patron que le lien événement : `/web#model=survey.survey&id=...`).
- **(7)** Les droits d'accès (`ir.model.access.csv`) utilisaient déjà
  le groupe `survey.group_survey_user` (Utilisateur, pas
  Administrateur) - correct, mais aucun menuitem n'avait de
  restriction de groupe correspondante, les rendant visibles même sans
  ces droits. Ajout de `groups="survey.group_survey_user"` aux 8
  menuitems du module (le menu conteneur et ses 7 sous-menus).
- **(8)** Nouvelle option « Protéger le fichier par un mot de passe »
  avec un champ mot de passe associé (masqué à l'affichage). **PDF** :
  chiffrement standard via la bibliothèque `pypdf` (ou `PyPDF2` en
  repli) - `action_download_pdf()` génère les octets du PDF elle-même
  (`ir.actions.report._render_qweb_pdf()`) pour pouvoir les chiffrer
  avant de les proposer au téléchargement comme pièce jointe, plutôt
  que de laisser Odoo servir le PDF directement (chemin normal
  inchangé quand la protection n'est pas demandée). **HTML** :
  chiffrement AES-256-GCM (clé dérivée du mot de passe via
  PBKDF2-SHA256, 210 000 itérations - recommandation OWASP), déchiffré
  **dans le navigateur** via l'API Web Crypto native au moment de
  l'ouverture du fichier - aucune bibliothèque JavaScript externe,
  aucune donnée envoyée à un serveur. **Le round-trip de chiffrement/
  déchiffrement a été validé côté Python** (bon mot de passe accepté,
  mauvais mot de passe rejeté avec `InvalidTag`), **mais la partie
  JavaScript n'a pu être testée dans aucun navigateur** - voir
  NOTES_VALIDATION.md, section -4, pour la démarche de test à suivre
  avant de s'y fier pour une obligation légale.

**Garde-fous et cas limites :**
- La protection par mot de passe du PDF nécessite `pypdf`/`PyPDF2` ;
  celle du HTML nécessite `cryptography` - messages d'erreur clairs si
  l'une de ces bibliothèques est absente, invitant à l'installer ou à
  décocher l'option (aucune n'est ajoutée comme dépendance obligatoire
  du module, pour ne pas bloquer l'installation de tout le module chez
  qui n'utilise jamais cette fonctionnalité).
- Le mot de passe n'est jamais affiché ni intégré dans le contenu du
  rapport lui-même (vérifié : son seul usage dans le code sert au
  chiffrement).

**Vérifications effectuées :** round-trip de chiffrement/déchiffrement
AES-GCM+PBKDF2 testé en isolation côté Python (succès avec le bon mot
de passe, rejet propre avec un mauvais). Logique d'insertion des
styles de saut de page en ligne testée en isolation. Format du message
de progression dynamique testé en isolation. Fusion du tooltip
retestée (un faux positif de comptage initial - « data-tooltip »
contient accidentellement le sous-texte « a-tooltip » - corrigé par
une vérification plus précise confirmant un seul tooltip réel).
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le rendu réel dans Odoo (notifications, sauts de page
et histogrammes PDF, menus cachés selon les droits, déchiffrement HTML
en navigateur) n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : (a) le sous-menu « Sondage annuel » retrouve
maintenant le sondage attendu ; (b) les histogrammes et les sauts de
page apparaissent bien dans un PDF généré ; (c) **avant toute
utilisation réelle de la protection par mot de passe**, suivez la
démarche de test de NOTES_VALIDATION.md, section -4.

---

## 18.0.1.28.0

**Titre court :** sauts de page PDF (par rencontre, par participant)
devenus deux options indépendantes du wizard, second mécanisme
(`create="false"`) pour retirer le bouton « Nouveau » du sélecteur de
sondage.

**Motif de la demande :** (1) demande de pouvoir choisir, comme options
du rapport, si le saut de page forcé s'applique à chaque rencontre
et/ou à chaque participant dans le PDF (plutôt qu'un choix fixé dans le
code) ; (2) le bouton « Nouveau » apparaissait toujours dans la fenêtre
de sélection d'un sondage malgré le correctif de la version précédente
(`no_create`/`no_create_edit`) ; (3) question sur une erreur CSRF dans
les logs.

**Détail des modifications :**

- **(1)** Deux nouveaux champs sur le wizard : « Saut de page forcé par
  rencontre (PDF) » (coché par défaut, comportement historique) et
  « Saut de page forcé par participant (PDF) » (décoché par défaut,
  avec un avertissement dans l'aide sur le risque déjà rencontré pour
  un grand nombre de participants). Les règles CSS correspondantes ne
  sont plus fixées dans le gabarit QWeb : `_html_pour_pdf()` les génère
  maintenant dynamiquement selon ces deux choix et les insère en tête
  du document.
- **(2)** Le correctif précédent (`no_create`/`no_create_edit` sur le
  champ) reste en place mais s'est visiblement avéré insuffisant à lui
  seul. Un second mécanisme, plus direct, est ajouté en renfort :
  l'attribut `create="false"` sur la balise `<list>` elle-même, dans
  les deux vues concernées (la vue dédiée `view_survey_survey_list_rlq`
  et la sous-vue intégrée au formulaire) - cette combinaison des deux
  mécanismes devrait couvrir le cas quel que soit celui réellement
  utilisé par cette version d'Odoo pour la fenêtre de sélection.
- **(3)** Clarification : l'erreur CSRF rapportée (« No CSRF validation
  token provided for path '/' », requête POST depuis une adresse IP
  externe) n'a aucun rapport avec ce module - c'est la protection CSRF
  générique d'Odoo réagissant à une requête externe (vraisemblablement
  un robot ou un scanner automatisé) visant la page d'accueil du site,
  pas le formulaire du sondage. Aucune modification apportée pour ce
  point.

**Garde-fous et cas limites :**
- Les deux options de saut de page sont indépendantes : les quatre
  combinaisons (aucune, rencontre seule, participant seul, les deux)
  sont possibles et ont été testées en isolation (génération correcte
  du CSS dans chaque cas).
- Si `create="false"` n'est pas reconnu comme attribut valide sur cette
  version précise d'Odoo, seule cette ligne serait à retirer - le reste
  de la vue n'est pas affecté.

**Vérifications effectuées :** génération du CSS de saut de page testée
en isolation pour les quatre combinaisons possibles. Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. Comme toujours, le
rendu réel dans Odoo (bouton Nouveau effectivement absent, sauts de
page respectés selon les options) n'a pas pu être vérifié faute d'accès
à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité si le bouton « Nouveau » a bien disparu cette
fois-ci.

---

## 18.0.1.27.0

**Titre court :** CORRECTIF CRITIQUE (avertissement affectant toute
l'instance Odoo, retiré), `t-raw` déprécié remplacé, bouton « Nouveau »
retiré du sélecteur, « Tous les sondages » exclut ceux à 0 réponse,
notification de progression toutes les 3 secondes, tooltip de date pour
les présentations en Synthèse, PDF : saut de page forcé retiré pour les
participants (troncature à 86 pages) avec option de secours, copyright/
licence LGPL-3 dans tous les fichiers source.

**Motif de la demande :** (1) le bouton « Nouveau » apparaissait dans
la fenêtre de sélection d'un sondage ; (2) « Tous les sondages (terminé
et commencé) » affichait quand même des sondages à 0 réponse ; (3)
absence de progression visible pendant une génération longue ; (4)
demande d'indiquer la date d'une présentation en tooltip dans la
section « Comment avez-vous aimé les présentations ? » ; (5) le rapport
PDF s'arrêtait à 86 pages, incomplet ; (6) avertissement Odoo dans les
logs : directive `t-raw` dépréciée ; (7) demande d'ajouter le copyright
et la licence LGPL-3 ; (8) **erreur critique rapportée dans les logs** :
avertissement « inconsistent 'store' for computed fields » sur
`answer_count`/`answer_done_count`, visible sur des pages sans aucun
rapport avec les sondages.

**Détail des modifications :**

- **(8) CORRECTIF CRITIQUE, traité en priorité absolue.** La
  redéclaration de `answer_count`/`answer_done_count` avec
  `store=True` seul (v1.26.0, pour les rendre triables) a provoqué
  l'avertissement Odoo confirmé par l'utilisateur - visible jusque dans
  le traitement de requêtes HTTP ordinaires (`res.lang.get_installed()`
  notamment), donc affectant potentiellement **toute l'instance**, pas
  seulement ce module. Retiré immédiatement. Remplacé par deux champs
  entièrement nôtres, `rlq_answer_count` et `rlq_answer_done_count`
  (calculés dans `_compute_rlq_stats`, déjà existante), qui n'entrent
  en conflit avec aucune définition native - aucun risque de ce genre
  possible. Toutes les vues et tout le code du wizard mis à jour pour
  utiliser ces nouveaux champs à la place des champs natifs.
- **(6)** `<t t-raw="doc._html_pour_pdf()"/>` (déprécié, avertissement
  confirmé dans les logs) remplacé par `<t t-out="doc._html_pour_pdf()"/>`.
  `_html_pour_pdf()` enveloppe maintenant son résultat dans
  `markupsafe.Markup(...)`, sans quoi `t-out` aurait échappé tout le
  HTML du rapport (l'affichant comme texte brut plutôt que de le
  rendre) - `t-out` n'affiche du HTML non échappé que pour un contenu
  explicitement marqué comme sûr.
- **(1)** `options="{'no_create': True}"` devient
  `options="{'no_create': True, 'no_create_edit': True}"` sur le champ
  `survey_ids` - la combinaison standard pour retirer entièrement la
  possibilité de créer un enregistrement depuis un widget de sélection.
- **(2)** `_survey_ids_tous()` ne retourne plus que les sondages ayant
  au moins une réponse terminée ou en cours
  (`rlq_answer_done_count > 0 or rlq_answer_in_progress_count > 0`).
- **(3)** Nouvelle méthode `_envoyer_progression()`, utilisant le bus
  temps réel d'Odoo (`bus.bus._sendone`) suivi d'un commit immédiat
  pour rendre la notification visible pendant que la génération se
  poursuit (sans risque : aucune donnée persistante n'est encore écrite
  à ce stade). Appelée depuis la boucle principale toutes les 3
  secondes (mesurées via `time.time()`), uniquement si plus d'un
  sondage est à traiter. Protégée par un try/except, comme toute
  tentative de notification depuis l'incident avec `notify_warning`.
- **(4)** Le paramètre `dates_par_item` de `section_matrice()` existait
  déjà dans le code mais n'était alimenté ni transmis nulle part -
  fonctionnalité restée inachevée. Un nouvel accumulateur
  `synth_item_date` (titre -> item -> date de première occurrence) est
  maintenant alimenté en même temps que `synth_matrice_detail`, et
  transmis à `section_matrice()` pour la section Synthèse. L'affichage
  est passé d'un texte visible en permanence à côté de l'item à un
  véritable tooltip au survol (« Présenté le AAAA-MM-JJ (jour) »),
  comme demandé.
- **(5)** Le saut de page forcé (`page-break-before: always`) et le
  « ne pas couper » (`page-break-inside: avoid`) ajoutés en 1.20.0/
  1.21.0 pour chaque section `personne` sont retirés (conservés pour
  `rencontre` uniquement, bien moins nombreuses) - la cause la plus
  probable d'une génération PDF s'arrêtant prématurément (tronquée à
  86 pages observés) pour un sondage à grand nombre de participants
  (ex. ~190 pour la Journée Portes Ouvertes) : un saut de page forcé
  par participant produit un document si volumineux que wkhtmltopdf
  semble atteindre une limite de temps ou de mémoire. Nouvelle option
  de secours, « Tableaux de réponses par participant dans le PDF »
  (cochée par défaut) : décochée, le tableau détaillé de chaque
  participant est omis du PDF (coordonnées conservées) pour réduire
  encore la taille du document si le problème persistait malgré le
  retrait des sauts de page forcés.
- **(7)** Le copyright et la licence LGPL-3 étaient déjà présents dans
  le manifeste (`license`, `author`, `maintainer`) et dans le pied de
  chaque rapport généré, mais absents ou incomplets dans l'en-tête de
  certains fichiers source. Ajoutés/complétés de façon cohérente dans
  les trois fichiers Python du module (`rlq_survey_report_wizard.py`,
  `report_builder.py`, `survey_survey.py`).

**Garde-fous et cas limites :**
- Après l'incident du point (8), toute redéclaration future d'un champ
  natif d'Odoo (pas seulement `store=True`) devrait être évitée par
  défaut au profit d'un champ entièrement nôtre, sauf nécessité
  clairement justifiée.
- La notification de progression peut ne rien afficher si l'API du bus
  diffère de ce qui est attendu sur cette instance - protégée pour ne
  jamais faire échouer la génération dans ce cas, comme demandé.
- L'option de secours pour le PDF (point 5) modifie uniquement la
  sortie PDF - le rapport à l'écran reste toujours complet, quel que
  soit ce réglage.

**Vérifications effectuées :** relecture minutieuse et ligne par ligne
de toute la zone touchée par la boucle de progression, après une
erreur d'édition détectée et corrigée en cours de route (un
remplacement de texte avait involontairement scindé une méthode
existante) - structure des méthodes reconfirmée saine (comptage des
définitions de méthode, vérification des deux points de retour de
`_compute_report`). Transformation de retrait du tableau participant
en PDF testée en isolation. Tooltip de date testé en isolation.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le comportement réel dans Odoo (absence d'avertissement
au démarrage, génération PDF complète, notification de progression)
n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité absolue que l'avertissement "inconsistent 'store'"
a bien disparu des logs au démarrage, puis que le PDF de la Journée
Portes Ouvertes se génère maintenant en entier.

---

## 18.0.1.26.0

**Titre court :** « Date d'envoi » remplacée par « Date de création »
(create_date, natif et toujours fiable), colonne Jour de la semaine,
toutes les colonnes de comptage rendues triables (y compris deux champs
natifs redéclarés avec store=True), membres d'étiquette absents de ce
rapport affichés en noir plutôt qu'en lien, gras de la notification
remplacé par de vrais caractères Unicode gras.

**Motif de la demande :** (1) la colonne « Date d'envoi » reste vide -
utiliser plutôt la date de création (visible dans le fil de discussion
du sondage : « Sondage créé »), masquée par défaut ; (2) ajouter une
colonne Jour de la semaine, masquée par défaut ; (3) toutes les colonnes
(Inscrit, Terminé, etc.) devraient être triables ; (4) dans la liste des
membres d'une étiquette, distinguer ceux qui ne sont pas cliquables (pas
dans ce rapport) en les affichant en noir ; (5) le gras de la
notification (tenté en 1.25.0) n'a pas fonctionné.

**Détail des modifications :**

- **(1)** Toute la logique de détection d'une « date d'envoi » (recherche
  de champ par mots-clés, puis repli sur le fil de discussion) est
  retirée et remplacée par `create_date`, un champ natif TOUJOURS présent
  sur `survey.survey` - plus simple et plus fiable que ce qui a été
  tenté jusqu'ici. `_dates_envoi_expiration()` et `_annee_repli_titre()`
  simplifiées en conséquence (cette dernière perd son paramètre
  `date_envoi`, devenu inutile). Le libellé affiché dans chaque section
  de rencontre passe de « Envoyé le » à « Créé le ». Colonne « Date de
  création » ajoutée à la liste de sélection, masquée par défaut.
  Constante `_SENTINEL`, devenue inutilisée par cette simplification,
  retirée.
- **(2)** Nouveau champ `rlq_jour_semaine` (Char, stocké) sur
  `survey.survey`, dérivé de `rlq_date_titre` dans le même calcul -
  colonne ajoutée à la liste, masquée par défaut.
- **(3)** Tous les champs de comptage sont maintenant stockés
  (`store=True`), donc triables par un clic sur l'en-tête de colonne :
  nos propres champs (`rlq_answer_in_progress_count`,
  `rlq_answer_duration_avg_seconds`, `rlq_question_count`), ainsi que
  deux champs NATIFS du module Sondage (`answer_count`,
  `answer_done_count`), redéclarés avec `store=True` seulement (sans
  toucher à leur méthode de calcul d'origine) - une technique standard
  d'héritage de champ Odoo, mais qui touche pour la première fois des
  champs natifs plutôt que nos propres ajouts (risque légèrement plus
  élevé - voir NOTES_VALIDATION.md, section 4bis, pour le repli en cas
  de problème à l'installation).
- **(4)** `liste_personnes_simple()` accepte maintenant un ensemble
  optionnel de noms ayant réellement une fiche dans le rapport en cours
  (`noms_avec_fiche`) - un nom absent de cet ensemble est affiché en
  texte noir simple plutôt qu'en lien bleu. Le wizard calcule cet
  ensemble une fois (`set(participants.keys())`) et le transmet à
  chaque appel pour l'affichage des étiquettes.
- **(5)** Confirmé par l'utilisateur : le HTML n'est pas rendu dans le
  message d'une notification Odoo (texte brut échappé). Remplacé par
  une conversion des chiffres en leur équivalent Unicode "gras"
  (`rb.chiffres_gras()`, mathematical bold digits U+1D7CE-U+1D7D7) - de
  vrais caractères, pas des balises, qui s'affichent en gras dans
  n'importe quel contexte texte brut. Les balises HTML restantes dans
  les diagnostics (utilisées pour le bandeau du rapport, un contexte
  HTML réel) sont retirées avant cette conversion pour cet usage précis.

**Garde-fous et cas limites :**
- Si la redéclaration de `answer_count`/`answer_done_count` avec
  `store=True` échoue à l'installation sur votre instance (champ déjà
  stocké différemment, ou personnalisation tierce), retirez ces deux
  lignes de `survey_survey.py` - le reste du module n'est pas affecté,
  seul le tri par ces deux colonnes cesserait de fonctionner.
- `rlq_jour_semaine` reste vide si `rlq_date_titre` n'a pas pu être
  déterminé (même limite que pour la date elle-même).

**Vérifications effectuées :** conversion en chiffres Unicode gras
testée en isolation - rendu confirmé (`0/6` devient `𝟎/𝟔`).
`liste_personnes_simple()` retestée avec le nouveau paramètre - un nom
"dans le rapport" reste un lien, les autres s'affichent en texte noir.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le rendu réel dans Odoo (tri des colonnes, affichage
des chiffres gras dans la notification, colonnes Date de
création/Jour de la semaine) n'a pas pu être vérifié visuellement
faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que l'installation réussit malgré la redéclaration
des deux champs natifs (point le plus à risque de cette version), puis
que les chiffres de la notification s'affichent bien en gras cette
fois-ci.

---

## 18.0.1.25.0

**Titre court :** repli supplémentaire pour la date d'envoi (via le fil
de discussion), gras conservé dans la notification, couleurs du
bandeau rouge et du tooltip fixées pour le thème sombre, durée
moyenne/nombre de questions ajoutés au tableau récapitulatif, menu
« Rapports détaillés » (pluriel) avec un nouveau raccourci « Tous les
sondages (terminé et commencé) ».

**Motif de la demande :** (1) la colonne « Date d'envoi » reste vide ;
(2) le message temporaire en haut à droite après avoir cliqué sur
« Générer » devrait aussi afficher ses chiffres en gras ; (3) en thème
sombre, les messages du bandeau rouge d'avertissement deviennent
invisibles ; (4) en thème sombre, le tooltip devrait avoir un fond pâle
plutôt que foncé ; (5) ajouter la durée moyenne et le nombre de
questions au tableau récapitulatif en tête de rapport ; (6) mettre
« Rapports détaillés » au pluriel et ajouter un raccourci « Tous les
sondages (terminé et commencé) » ; (7) masquer par défaut les colonnes
Durée moyenne/Responsable/Nb. questions.

**Détail des modifications :**

- **(1)** Aucun champ « date d'envoi » n'a pu être détecté sur
  `survey.survey` pour au moins certains sondages. Un second repli a
  été ajouté à `_dates_envoi_expiration()` : à défaut de champ, le plus
  ancien message de type courriel logué sur le fil de discussion
  (chatter) du sondage est utilisé - l'action « Envoyer par courriel »
  d'Odoo y laisse généralement une trace. Reste possible que la colonne
  demeure vide si aucune des deux méthodes ne trouve rien sur cette
  instance précise.
- **(2)** Le nettoyage des balises HTML dans le message de la
  notification (ajouté par erreur en 1.24.0, en présumant à tort que
  les notifications d'Odoo n'affichent que du texte brut) est retiré :
  les balises `<strong>` sont conservées, comme le fait déjà, par
  exemple, le `<br/>` de certaines notifications du cœur d'Odoo.
- **(3)** Le bandeau rouge d'avertissement n'avait pas de couleur de
  texte propre : son contenu héritait de la couleur générale du thème
  actif, qui devient claire en thème sombre - illisible sur le fond
  rose clair fixe du bandeau. Une couleur de texte foncée et fixe
  (`#5c2b27`) a été ajoutée au conteneur, indépendante du thème choisi.
- **(4)** Nouvelle règle CSS `.rlq-rapport[data-theme="dark"]
  .a-tooltip::after` donnant au tooltip un fond pâle et un texte foncé
  spécifiquement en thème sombre (le thème clair garde son tooltip à
  fond foncé/texte blanc, inchangé).
- **(5)** Le tableau récapitulatif en tête de rapport affiche
  maintenant aussi « Durée moyenne (s) » et « Nb. questions » par
  rencontre, à partir des champs déjà calculés sur `survey.survey`.
- **(6)** Le menu « Rapport détaillé » devient « Rapports détaillés ».
  Nouveau raccourci « Tous les sondages (terminé et commencé) »
  (`_survey_ids_tous()`, `action_menu_tous()`) : sélectionne tous les
  sondages sans distinction de catégorie, avec « Inclure les réponses
  partielles » précoché par défaut (`default_include_partial: True`
  dans le contexte) pour couvrir aussi bien les réponses terminées que
  commencées. `_action_ouvrir_wizard_pour()` accepte maintenant un
  contexte supplémentaire optionnel pour ce genre de préréglage.
- **(7)** Vérification faite : `optional="hide"` est déjà présent sur
  ces trois colonnes, dans la vue intégrée ET la vue dédiée créée en
  1.24.0 - aucun changement de code nécessaire. Si elles apparaissent
  quand même visibles par défaut, il s'agit probablement d'une
  préférence de colonnes mise en cache par le navigateur lors d'une
  interaction précédente (avant l'ajout de `optional="hide"`) plutôt
  que d'un problème côté serveur - un clic sur l'icône d'options de
  colonnes pour les décocher une fois devrait normalement corriger
  cette préférence pour la suite.

**Garde-fous et cas limites :**
- Le repli chatter pour la date d'envoi suppose que `message_type =
  'email'` est bien la valeur utilisée pour un courriel sortant sur
  cette instance - une hypothèse standard d'Odoo, mais non vérifiée ici.
- Si la notification d'Odoo sur cette instance rend effectivement le
  message en texte brut échappé (plutôt qu'en HTML), les chiffres y
  apparaîtront avec des balises `<strong>` littérales plutôt qu'en gras -
  un compromis accepté pour tenter de répondre à la demande, à
  confirmer visuellement.

**Vérifications effectuées :** syntaxe Python et XML validées sur
l'ensemble des fichiers modifiés. `report_builder.py` retesté en
isolation (présence de la nouvelle règle CSS du tooltip sombre
confirmée). Comme toujours, le rendu réel dans Odoo (couleurs en thème
sombre, gras dans la notification, détection de la date d'envoi via le
chatter) n'a pas pu être vérifié visuellement faute d'accès à une
instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité : (a) la lisibilité du bandeau rouge et du tooltip
en thème sombre ; (b) si la date d'envoi apparaît maintenant pour au
moins certains sondages ; (c) si les chiffres de la notification
s'affichent bien en gras (sinon, dites-le-moi - le compromis pourrait
devoir être revu).

---

## 18.0.1.24.0

**Titre court :** vue liste dédiée pour la fenêtre « Ajouter une
ligne » (corrige les colonnes indésirables provenant de la vue par
défaut de Sondage), nouvelles colonnes triables Date (titre)/Date
d'envoi, durée moyenne plafonnée à 999s, chiffres en gras dans l'info
de version et les bandeaux du rapport, PDF : sélecteur de thème
retiré, saut de page par participant, titre ajouté en début de
document.

**Motif de la demande :** (1) en cliquant sur « Ajouter une ligne »
pour choisir un sondage, toutes les colonnes indésirables (Responsable,
Taux de réussite, « Réussite », Note moyenne) réapparaissaient malgré
leur retrait de la liste - demande d'ajouter aussi une colonne Date
d'envoi et une colonne avec la date déduite du titre, triables, et de
plafonner la durée moyenne à 999 secondes ; (2) demande de mettre en
gras les chiffres dans l'info de version (haut du formulaire) et le
bandeau de génération (bas du rapport) ; (3) demande de mettre en gras
les chiffres dans le bandeau rouge d'avertissement (ex. « 0/6
réponse(s) retenue(s) ») ; (4) dans le PDF, retirer le sélecteur de
thème (inutile, non fonctionnel à l'impression), faire commencer chaque
sondage ET chaque participant en haut d'une page, et ajouter le titre
« Rapport de sondage RLQ » en début de document.

**Détail des modifications :**

- **(1) Diagnostic** : la sous-vue `<list>` intégrée au champ
  `survey_ids` ne gouverne que l'affichage des sondages DÉJÀ
  sélectionnés dans le formulaire - la fenêtre « Ajouter une ligne »
  ouvre une fenêtre de sélection séparée qui, faute d'indication
  contraire, utilise la vue liste PAR DÉFAUT de Sondage (avec ses
  propres colonnes). Corrigé en créant une vue liste autonome et dédiée
  (`view_survey_survey_list_rlq`), référencée sur le champ via le
  contexte (`list_view_ref`/`tree_view_ref` simultanément, l'un des
  deux étant ignoré selon la version). Cette correction n'a pas pu être
  vérifiée sur une instance réelle - voir NOTES_VALIDATION.md, section
  4quater, pour la démarche de vérification et le repli si elle ne
  fonctionne pas comme prévu.
- **(1)** Deux nouveaux champs sur `survey.survey`, stockés (donc
  triables par un clic sur l'en-tête de colonne) : `rlq_date_titre`
  (date extraite du titre, en réutilisant `_extraire_date_titre()` du
  wizard plutôt que de dupliquer cette logique - appelée via un
  recordset vide du modèle du wizard, un patron standard pour invoquer
  une méthode utilitaire indépendante d'un `self` réel) et
  `rlq_date_envoi` (date d'envoi détectée dynamiquement, réutilisant
  `_trouver_champ_date()`). Les deux dépendent de `write_date` en plus
  de leur dépendance propre, faute de pouvoir déclarer une dépendance
  précise sur un champ dont le nom n'est connu qu'à l'exécution.
  `rlq_answer_duration_avg_seconds` est maintenant plafonné à 999
  secondes pour l'affichage (`min(moyenne, 999)`).
- **(2)** `debug_info` converti de `Char` à `Html` (sanitize=False,
  comme `report_html`) pour permettre l'insertion de balises
  `<strong>` autour du numéro de version et des deux dates (UTC et
  locale). Le bandeau de génération du rapport (bas de page) reçoit le
  même traitement. Le pied de page ne ré-échappe plus le résultat de
  `_default_debug_info()` (il retourne maintenant du HTML légitime, pas
  du texte brut à échapper).
- **(3)** Les 4 messages de diagnostic (exclusion par mot-clé, sondage
  à 0 réponse, date de titre non reconnue, question ignorée) sont
  maintenant construits comme du HTML sûr dès leur création - la partie
  utilisateur (titre du sondage, message d'exception) est échappée
  individuellement à la construction plutôt que sur l'ensemble du
  message plus tard, ce qui permet d'entourer les chiffres clés de
  balises `<strong>` (fait pour le cas « 0/N réponse(s) retenue(s) »).
  Le bandeau rouge du rapport insère maintenant ces messages tels
  quels (ils sont déjà sûrs) ; la notification à l'écran, qui affiche
  du texte brut, retire les balises HTML de l'aperçu qu'elle affiche.
  Un test de détection interne (déclenchant l'explication générale sur
  les sondages à 0 réponse) a été ajusté en conséquence, la balise
  `<strong>` ayant changé le texte exact recherché.
- **(4)** `_html_pour_pdf()` retire maintenant aussi le bloc du
  sélecteur de thème. La règle `page-break-before: always` s'applique
  désormais à `section.personne` en plus de `section.rencontre` (avec
  la même exception pour le tout premier élément de chaque type, pour
  éviter une page blanche au tout début). Un titre
  « Rapport de sondage RLQ » (h1, non dépendant du CSS du rapport lui-
  même) a été ajouté en tête du gabarit PDF.

**Garde-fous et cas limites :**
- Si votre instance ne reconnaît ni `list_view_ref` ni `tree_view_ref`
  comme clé de contexte pour ce mécanisme, la fenêtre « Ajouter une
  ligne » continuera d'utiliser la vue par défaut de Sondage - sans
  erreur, mais sans la correction attendue non plus. À vérifier
  concrètement (voir NOTES_VALIDATION.md).
- `rlq_date_envoi`/`rlq_date_titre` peuvent rester vides si aucune date
  n'est détectable, comme avant pour les mêmes calculs côté wizard.

**Vérifications effectuées :** transformations regex du PDF (retrait du
sélecteur de thème) testées en isolation. Détection du motif
« réponse(s) retenue(s) » validée après le changement de format des
diagnostics. Syntaxe Python et XML validées sur l'ensemble des fichiers
modifiés. `report_builder.py` retesté en isolation. Comme toujours, le
comportement réel dans Odoo (fenêtre "Ajouter une ligne", tri par date,
rendu du gras, mise en page PDF) n'a pas pu être vérifié visuellement
faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité la fenêtre « Ajouter une ligne » du champ
Sondages (point le plus incertain de cette version) et signalez si les
colonnes indésirables réapparaissent malgré tout.

---

## 18.0.1.23.0

**Titre court :** convention de version « 18.0.x.y.z » restaurée (sur
demande explicite), audit complet et minutieux de sécurité et de
performance, retrait de code mort, correction d'un commentaire de vue
obsolète, harmonisation des marges PDF.

**Motif de la demande :** « Non, conserve la convention 18.0.1.21.0...
Peux-tu vérifier que tout est bien optimisé et sécuritaire ? Prends le
temps de bien revérifier. »

**Détail des modifications :**

- **Convention de version restaurée.** Le numéro « x.y.z » sans
  préfixe (introduit en 1.22.0 pour la compatibilité multi-versions)
  est abandonné : la convention « 18.0.x.y.z » est conservée telle
  quelle. La note explicative dans `__manifest__.py` et
  `NOTES_VALIDATION.md` a été corrigée en conséquence - passer à Odoo
  19 nécessitera de changer manuellement le préfixe (« 18.0. » →
  « 19.0. »), ce qui a été confirmé comme suffisant.

- **Audit de sécurité (aucune faille trouvée).** Recherche automatisée
  (script Python parcourant systématiquement toute interpolation de
  variable dans du HTML) puis relecture manuelle ligne par ligne de
  chaque résultat, sur les deux fichiers principaux
  (`rlq_survey_report_wizard.py`, `report_builder.py`). Chaque valeur
  provenant d'une source utilisateur (titres de sondage, noms de
  participants, coordonnées de contact, noms d'étiquettes, réponses
  libres, libellés de volets matriciels) a été retracée jusqu'à son
  point d'insertion dans le HTML : toutes passent par
  `echapper()`/`echapper_attr()`. Confirmé également : aucune requête
  SQL brute nulle part dans le module, aucun usage d'`eval`/`exec`,
  `sudo()` limité à deux appels en lecture seule (consultation de la
  version installée du module), droits d'accès correctement restreints
  au groupe `survey.group_survey_user` plutôt qu'ouverts à tous, et le
  champ d'information technique (mode debug) correctement protégé par
  `base.group_no_one`. L'assainissement de `lien_ancre()` (ajouté
  précédemment en défense en profondeur) est toujours en place.

- **Audit de performance - un vrai problème trouvé et corrigé.** La
  détection de la date d'envoi/d'expiration du sondage
  (`_dates_envoi_expiration()`) et l'année de repli qui en découle
  (`_annee_repli_titre()`) étaient recalculées **trois fois par
  sondage** dans la boucle principale de génération (une fois pour la
  date de la rencontre, une fois pour le lien événement, une fois pour
  l'affichage direct). Sans provoquer de requêtes SQL supplémentaires
  grâce à la mise en cache native de l'ORM, ce triple calcul restait un
  gaspillage de cycles CPU inutile. `_rencontre_date()` et
  `_annee_repli_titre()` acceptent maintenant un paramètre optionnel
  pour réutiliser une valeur déjà connue ; la boucle principale calcule
  `date_envoi`/`date_expiration` une seule fois par sondage et la
  réutilise partout où elle est nécessaire.

- **Code mort retiré.** Deux méthodes qui n'étaient plus appelées nulle
  part (`_get_input_lines()`, laissée par l'optimisation du chargement
  groupé des réponses en 1.17.0 ; `_version_module()`, supplantée par
  `_default_debug_info()` en 1.13.0) ont été supprimées - leur présence
  aurait pu induire en erreur lors d'une future intervention sur le
  code, en laissant croire qu'elles faisaient encore partie du chemin
  actif.

- **Commentaire de vue corrigé.** Le commentaire décrivant les colonnes
  de la liste de sondages mentionnait encore `success_ratio`
  (« Taux de réussite ») et `answer_score_avg` (« Note moyenne »)
  comme si ces champs étaient toujours affichés, alors qu'ils avaient
  été retirés de la liste réelle en 1.20.0 - une contradiction directe
  entre le commentaire et le code qui aurait pu semer la confusion lors
  d'une prochaine modification. Corrigé pour refléter fidèlement les
  colonnes réellement présentes.

- **Marges PDF harmonisées.** `header_spacing` (espacement réservé pour
  un en-tête) était resté à 18mm alors que les marges avaient été
  réduites à 3mm dans une version précédente sur demande explicite
  (« marges minimum ») - un oubli qui laissait un espace vide en haut
  de chaque page malgré des marges par ailleurs minimales. Réduit à
  3mm également, par cohérence.

**Garde-fous et cas limites :**
- Le calcul unique de `date_envoi`/`date_expiration` par sondage
  suppose que `_dates_envoi_expiration()` reste un calcul cohérent pour
  un même sondage au sein d'une seule génération de rapport (le cas
  normal) - aucun changement de comportement pour l'utilisateur, cette
  optimisation est purement interne.

**Vérifications effectuées :** recherche automatisée de toute
interpolation HTML suivie d'une relecture manuelle complète, sans
exception, de chaque résultat obtenu (dizaines de lignes passées en
revue une à une). Compte des appels redondants confirmé par recherche
textuelle avant et après le correctif de performance. Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. `report_builder.py`
retesté en isolation après coup - aucune régression.

**Action requise :** mettre à jour le module et redémarrer le service.
Aucun changement de comportement visible n'est attendu de cette version
(uniquement de la robustesse, de la propreté de code et une économie de
cycles CPU internes) - à l'exception de l'espacement PDF légèrement
réduit en haut de page.

---

## 18.0.1.22.0

**Titre court :** retour à la convention de version « 18.0.x.y.z »
suite à la décision explicite de l'utilisateur de la conserver plutôt
que d'adopter un format sans préfixe de série - voir la version
18.0.1.23.0 ci-dessus pour le détail complet de cette décision et de
l'audit qui l'accompagne.

---

## 1.22.0

**Titre court :** compatibilité assurée avec Odoo 18 CE **et** Odoo 19
CE - format du numéro de version corrigé (retrait du préfixe de série),
audit du code et des champs utilisés pour Odoo 19.

**Motif de la demande :** s'assurer que ce module fonctionne aussi bien
sur Odoo 18 CE que sur Odoo 19 CE.

**Recherche effectuée :** consultation des notes de version officielles
d'Odoo 19 (odoo.com/odoo-19-release-notes) et de son changelog technique
(ORM), avec une attention particulière à la section « Surveys » et aux
changements techniques listés (Python 3.12 minimum, retrait de méthodes
XML-RPC, références d'héritage de vue explicites, OR natif dans les
règles d'enregistrement, modules JS ES).

**Détail des modifications :**
- **Format du numéro de version corrigé** (le plus important) : Odoo
  valide strictement qu'un préfixe de série dans le numéro de version
  du manifeste (ex. « 18.0. ») corresponde à la version du serveur en
  cours d'exécution - un module numéroté « 18.0.x.y.z » **refuse
  littéralement de s'installer** sur un serveur Odoo 19, avec une
  erreur explicite (« Invalid version »). Confirmé par un cas réel
  rapporté sur le forum Odoo pour un module 16.0 refusé sur un serveur
  17. Le format `x.y.z` **sans aucun préfixe de série**, en revanche,
  est accepté sur n'importe quelle version. Le numéro de version est
  donc passé de `18.0.1.21.0` à `1.21.0` (prochaine version : `1.22.0`)
  - permettant au même fichier module de s'installer tel quel sur Odoo
  18 CE comme sur Odoo 19 CE, sans aucune modification requise entre
  les deux.
- **Audit du code pour Odoo 19** : la section « Surveys » des notes de
  version officielles d'Odoo 19 ne mentionne que des ajouts (génération
  de leads depuis les réponses, analyse des résultats dans Spreadsheet)
  - aucun renommage de champ ni restructuration du modèle n'y est
  signalé. Les champs standards utilisés par ce module (`title`,
  `user_id`, `answer_count`, `answer_done_count`, `question_ids`,
  `start_datetime`/`end_datetime` sur les réponses) devraient donc
  rester valides sur Odoo 19. Les autres changements techniques listés
  pour Odoo 19 (Python 3.12, XML-RPC, règles d'enregistrement, modules
  JS ES) ne concernent aucune fonctionnalité utilisée par ce module
  (pas de règles `ir.rule`, pas d'appel XML-RPC, pas de fichier
  JavaScript en asset - seulement du JavaScript en ligne dans le HTML
  généré, exécuté par le navigateur indépendamment d'Odoo).
- La vue utilise déjà la balise `<list>` (syntaxe moderne depuis
  Odoo 17), et le code utilise déjà `_read_group()` plutôt que l'ancien
  `read_group()` (explicitement mentionné comme déprécié dans le
  changelog technique d'Odoo 19 - `_read_group()` reste la méthode
  recommandée) : aucun changement nécessaire sur ces deux points.

**Garde-fous et cas limites :**
- Cet audit porte sur le cœur standard d'Odoo. La détection dynamique
  du modèle des réponses individuelles (déjà en place depuis la version
  1.3.0, suite à la divergence trouvée sur cette instance ERPLibre)
  demeure la meilleure protection contre un renommage imprévu propre à
  votre distribution - que ce soit sur Odoo 18 ou sur une future
  installation Odoo 19, si jamais un module tiers (comme le fork de
  « débrandisation » identifié précédemment) modifie encore ce modèle.
- Cette vérification reste une revue de documentation et de code,
  faute d'accès à une instance Odoo 19 réelle pour un test
  d'installation effectif.

**Vérifications effectuées :** recherche des notes de version
officielles d'Odoo 19 et de son changelog ORM technique. Confirmation,
via un cas documenté sur le forum Odoo, du comportement exact de la
validation du numéro de version selon la série du serveur. Syntaxe du
manifeste validée après modification.

**Action requise :** mettre à jour le module sur votre instance Odoo 18
actuelle (le nouveau numéro `1.22.0` s'installe normalement). Si/quand
une instance Odoo 19 CE devient disponible pour test, ce même fichier
module (zip) devrait s'installer sans modification - à confirmer lors
d'un premier essai réel, en particulier la détection dynamique du
modèle des réponses individuelles et l'apparence du rapport généré.

---

## 18.0.1.21.0

**Titre court :** table des matières restructurée (Synthèse regroupée
avec les dates dans le tableau récapitulatif, colonne « Rapport
global » redondante retirée, liste des participants sur 4 colonnes),
licence LGPL-3 en pied de rapport, limite de 20 participants détaillés
retirée, « Détail des notes » entièrement retiré du PDF, valeurs des
paramètres en gras.

**Motif de la demande :** (1) depuis l'ajout du tableau Inscrit/
Terminé/Débuté (1.20.0), la colonne « Rapport global » listant les
mêmes dates devenait redondante - demande de fusionner la Synthèse
avec ce tableau et de libérer l'espace pour plus de colonnes de
participants ; (2) demande d'indiquer la licence LGPL et le nom du
programme en fin de rapport ; (3) la limite à 20 participants détaillés
(introduite en 1.16.0 sur demande explicite) n'est en fait pas voulue -
tout le monde doit avoir sa fiche complète ; (4) demande de retirer
entièrement les lignes « Détail des notes » du PDF (pas seulement les
rendre non repliables) ; (5) demande de mettre en gras la valeur de
chaque paramètre dans la section « Paramètres utilisés pour ce
rapport ».

**Détail des modifications :**
- **(1)** La colonne « Rapport global » (qui ne faisait que lister les
  mêmes dates que le nouveau tableau récapitulatif) est retirée. La
  Synthèse apparaît maintenant comme une ligne de plus dans ce tableau
  (avec des tirets à la place des trois chiffres, qui n'ont pas de sens
  pour elle), juste au-dessus des rencontres. La liste des participants
  utilise maintenant toute la largeur disponible, répartie sur 4
  colonnes (2 sur petit écran) au lieu de 2.
- **(2)** Le pied de chaque rapport indique maintenant explicitement :
  « rlq_survey_report est distribué sous licence LGPL-3. », en plus du
  copyright déjà présent.
- **(3)** La limite de 20 fiches détaillées et le renvoi vers une simple
  liste pour le reste (introduits en 1.16.0) sont entièrement retirés :
  chaque participant, quel que soit leur nombre, reçoit maintenant sa
  fiche complète (informations de contact, tableau par date).
- **(4)** `_html_pour_pdf()` retire maintenant entièrement les blocs
  « Détail des notes » du PDF (le bloc `<details>` et tout son contenu),
  plutôt que de les convertir en contenu toujours visible comme les
  autres listes dépliables (ex. les listes de noms « Oui », les membres
  d'une étiquette) - ce ciblage se fait par le texte exact du résumé
  (« Détail des notes »), sans affecter les autres types de listes
  dépliables, qui restent converties en blocs visibles comme avant.
- **(5)** Chaque valeur affichée dans le résumé des paramètres (nombre
  de sondages, dates, participants/étiquettes exclus, thème, etc.) est
  maintenant en gras, la distinguant visuellement du libellé.

**Garde-fous et cas limites :**
- Retirer la limite de 20 participants (point 3) peut rendre le
  rapport significativement plus long pour un grand nombre de
  répondants (ex. la Journée Portes Ouvertes avec 190 inscrits) -
  attendez-vous à un temps de génération et un poids de page plus
  importants dans ce cas.
- Le retrait ciblé de « Détail des notes » en PDF repose sur une
  correspondance exacte du texte du résumé - si ce libellé change un
  jour dans le code (`section_matrice()`), le motif de retrait devra
  être mis à jour en parallèle.

**Vérifications effectuées :** transformation PDF retestée en
isolation avec un exemple mêlant un bloc « Détail des notes » (retiré)
et un bloc « 31 Oui » (converti, conservé) - comportement conforme.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le rendu réel dans Odoo (mise en page à 4 colonnes,
temps de génération avec tous les participants) n'a pas pu être
vérifié visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité le temps de génération et la mise en page pour un
sondage à grand nombre de participants (ex. la Journée Portes
Ouvertes), maintenant que tous reçoivent une fiche détaillée.

---

## 18.0.1.20.0

**Titre court :** marges PDF minimales, bouton « Modifier les
paramètres » corrigé, nouveau sous-menu « Portes ouvertes » et repli
sur la date de soumission pour le sondage annuel (corrige le cas d'un
titre sans jour/mois), tableau récapitulatif Inscrit/Terminé/Débuté en
tête de rapport, Synthèse masquée s'il n'y a qu'une seule rencontre,
étiquettes affichant tous leurs membres réels, date de génération et
date de version du module affichées, nombre de questions par sondage
en colonne optionnelle.

**Motif de la demande :** (1) marges PDF trop grandes ; (2) le nombre
d'inscrits/terminé/débuté par rencontre, déjà ajouté en 1.19.0 dans
chaque section, était voulu plutôt regroupé en tête du « Rapport
global » ; (3) le sous-menu « Sondage annuel » ne trouvait toujours pas
un sondage à 190 inscriptions, dont le titre ne contient qu'une année
sans jour ni mois ; (4) demande d'un sous-menu dédié aux sondages dont
le titre contient « Portes Ouvertes » ; (5) la section Synthèse est
redondante quand un seul sondage/une seule date est sélectionné ; (6)
le bouton « Modifier les paramètres » ne faisait rien et fermait la
fenêtre ; (7) demande d'un tooltip listant tous les membres d'une
étiquette comme « Collaborateurs-2026 », pas seulement ceux du rapport ;
(8) demande d'afficher, en fin de rapport (HTML/PDF), la date de la
version du module (UTC et locale) ; (9) demande d'afficher la date de
génération du rapport en tête ; (10) demande du nombre de questions par
sondage, en colonne optionnelle de la liste de sélection.

**Détail des modifications :**
- **(1)** Marges du format de page PDF réduites de 18/10mm à 3mm sur
  les quatre côtés.
- **(6)** `action_back()` : même correctif que `action_generate()` en
  1.15.0 - retourner `True` ne rechargeait pas la fiche de façon
  fiable sur cette instance (« ne fait rien et sort »). Retourne
  maintenant une action de rechargement explicite (`ir.actions.
  act_window` sur le même enregistrement), ramenant bien à l'écran des
  paramètres pour ajuster la sélection.
- **(3)/(4)** `_survey_ids_annuel()` : le titre signalé
  (« ...Linux 2025 ») ne contient qu'une année, sans jour ni mois -
  aucune date n'était donc jamais extraite, faisant échouer le critère
  quel que soit le nombre de réponses. Un second repli a été ajouté :
  si le titre ne fournit aucune date exploitable du tout, le mois de
  la première réponse soumise est utilisé à sa place - uniquement pour
  les sondages qui dépassent déjà le seuil de réponses, afin de limiter
  le risque de faux positif. Nouveau sous-menu indépendant « Portes
  ouvertes » (`_survey_ids_portes_ouvertes()`) : recherche « portes
  ouvertes » dans le titre, sans dépendre d'aucune date - solution plus
  directe et fiable pour ce sondage précis.
- **(2)** Nouveau tableau (une ligne par rencontre, colonnes Inscrit/
  Terminé/Débuté sans terminer) affiché juste après le résumé des
  paramètres, en tête du rapport - en plus des mêmes informations déjà
  présentes dans chaque section de rencontre individuelle (non
  retirées, la redondance n'étant pas gênante à cet endroit).
- **(5)** Quand une seule rencontre est incluse dans le rapport
  (`len(stats_rencontres) <= 1`), le lien et le contenu de la section
  Synthèse sont omis - elle serait de toute façon identique au détail
  de cette unique rencontre.
- **(7)** L'affichage d'une étiquette dans la fiche d'un participant
  interroge maintenant directement `res.partner` pour lister TOUS les
  contacts portant cette étiquette (mis en cache pour éviter de
  répéter la requête si plusieurs participants du rapport la
  partagent), plutôt que de se limiter aux seuls participants déjà
  présents dans ce rapport.
- **(8)** Le pied de page réutilise maintenant `_default_debug_info()`
  (déjà au format « vX.Y - installé/mis à jour le UTC (locale) »)
  plutôt que le seul numéro de version - la date de la version du
  module apparaît donc désormais aussi en pied de rapport (HTML comme
  PDF, puisque c'est le même contenu HTML sous-jacent).
- **(9)** La date et l'heure de génération du rapport lui-même (UTC et
  heure locale, distinctes de la date de version du module) sont
  maintenant affichées en tête, juste sous le sélecteur de thème.
- **(10)** Nouveau champ `rlq_question_count` (extension de
  `survey.survey`, comptant `len(question_ids)`), ajouté comme colonne
  « Nb. questions » masquée par défaut dans la liste de sélection des
  sondages - disponible via le menu d'options de colonnes.

**Garde-fous et cas limites :**
- Le tableau récapitulatif en tête de rapport suit le même ordre
  chronologique inversé que le reste du rapport.
- Le cache des membres d'étiquette (`membres_etiquette_cache`) est
  local à la génération du rapport en cours - recalculé à chaque
  nouvelle génération, ce qui reste correct même si des étiquettes
  changent entre deux générations.

**Vérifications effectuées :** `liste_personnes_simple()` retestée en
isolation après les changements adjacents - fonctionne toujours
correctement. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Comme toujours, le comportement réel dans Odoo
(sondage annuel enfin trouvé, bouton Modifier les paramètres, tableau
récapitulatif) n'a pas pu être vérifié visuellement faute d'accès à une
instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que le sondage « Journée Portes Ouvertes Linux
2025 » apparaît maintenant via le sous-menu « Portes ouvertes » (et
possiblement aussi via « Sondage annuel », selon le mois de ses
premières réponses), et que « Modifier les paramètres » ramène bien à
l'écran de sélection.

---

## 18.0.1.19.0

**Titre court :** « Réponses partielles » ne couvre plus les invitations
jamais ouvertes, nouvelle option pour voir les non-répondants,
diagnostics d'exclusion par mot-clé en une ligne par sondage, second
repli d'année sur la date de soumission (corrige 5 cas réels signalés),
statistiques Inscrit/Terminé/Débuté affichées par rencontre, sous-menu
utilisé indiqué dans les paramètres, nouveau code couleur des notes
(rouge/jaune/bleu/vert).

**Motif de la demande :** (1) cocher « Inclure les réponses partielles »
incluait aussi, à tort, les invitations jamais ouvertes (statut
« Nouveau ») ; (2) demande d'une option pour voir qui n'a pas répondu ;
(3) le message d'exclusion par mot-clé mettait tous les sondages
concernés sur une seule ligne, illisible dès qu'il y en avait
plusieurs ; (4) cinq titres réels sans année n'étaient toujours pas
reconnus malgré le repli d'année introduit en 1.17.0 ; (5) demande
d'afficher, pour chaque rencontre, le nombre d'inscrits/terminé/débuté ;
(6) demande d'indiquer, dans le résumé des paramètres, quel sous-menu
de raccourci a été utilisé pour sélectionner les sondages ; (7) nouveau
code couleur demandé pour les notes 1-5.

**Détail des modifications :**
- **(1)** `_user_inputs()` : quand « Inclure les réponses partielles »
  est coché, le filtre est maintenant `state in ('done', 'in_progress')`
  au lieu d'aucun filtre du tout - les invitations au statut 'new'
  (jamais ouvertes) ne sont plus jamais comptées comme des réponses,
  qu'elles soient incluses ou non.
- **(2)** Nouveau champ « Voir les personnes n'ayant pas répondu »
  (`voir_non_repondants`) : quand coché, chaque rencontre affiche la
  liste des personnes dont le sondage est au statut 'new' pour ce
  sondage - sous réserve que de tels enregistrements existent
  effectivement (dépend de la façon dont les invitations sont créées
  sur cette instance).
- **(3)** Le diagnostic d'exclusion par mot-clé du titre crée
  maintenant une entrée distincte par sondage exclu (donc une ligne
  chacun dans le bandeau), plutôt qu'une seule ligne listant tous les
  titres concaténés par des virgules.
- **(4)** Les cinq titres signalés (« ...24 avril... », « ...22 mai... »,
  etc.) avaient tous un point commun : aucune année dans le titre, ET
  aucun champ « date d'envoi » trouvable sur `survey.survey` pour ces
  sondages précis (le premier repli, introduit en 1.17.0, ne
  s'appliquait donc jamais). `_annee_repli_titre()` retombe maintenant,
  en dernier recours, sur l'année de la toute première réponse soumise
  au sondage - une approximation raisonnable, les réponses arrivant
  généralement la même année que l'envoi.
- **(5)** Chaque section de rencontre affiche maintenant « Inscrit :
  X · Terminé : Y · Débuté sans terminer : Z », à partir des champs
  déjà ajoutés à `survey.survey` en 1.16.0 (`answer_count`,
  `answer_done_count`, `rlq_answer_in_progress_count`).
- **(6)** Nouveau champ `menu_origine` (texte, readonly), rempli via le
  contexte (`default_menu_origine`) quand le wizard est ouvert depuis
  l'un des 4 sous-menus de raccourci. Affiché en premier dans la
  section « Paramètres utilisés pour ce rapport » quand renseigné (rien
  n'apparaît pour une sélection manuelle).
- **(7)** `colorer_par_valeur()` (report_builder.py) : nouveau code
  couleur pour les notes 1-5 - rouge si ≤ 2, jaune si égal à 3, bleu si
  ≥ 4 (donc en pratique la note 4), vert si ≥ 5 (donc la note 5).
  Nouvelle classe CSS `.val-bleu`, y compris sa variante à couleur
  figée pour le PDF (indépendante des variables CSS).

**Garde-fous et cas limites :**
- « Voir les personnes n'ayant pas répondu » peut ne rien afficher même
  coché, si aucun enregistrement `survey.user_input` au statut 'new'
  n'existe réellement pour les invitations non ouvertes sur cette
  instance (certaines configurations ne créent l'enregistrement qu'au
  moment où la personne ouvre effectivement le lien).
- Le second repli d'année (sur la date de soumission) suppose qu'au
  moins une réponse existe déjà pour le sondage concerné ; un sondage
  sans aucune réponse et sans date d'envoi détectable resterait donc
  toujours sans date reconnaissable.

**Vérifications effectuées :** nouveau code couleur testé en isolation
sur les 5 valeurs (1 à 5) - correspond exactement au barème demandé.
Syntaxe Python et XML validées sur l'ensemble des fichiers modifiés.
Comme toujours, le comportement réel dans Odoo (non-répondants,
statistiques par rencontre, reconnaissance des 5 titres signalés) n'a
pas pu être vérifié visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que les 5 titres précédemment signalés sont
maintenant reconnus (la date affichée devrait correspondre à celle du
titre, sans message de diagnostic à leur sujet).

---

## 18.0.1.18.0

**Titre court :** diagnostic visible quand la date du titre n'est pas
reconnue (au lieu d'un repli silencieux vers la date de soumission),
normalisation Unicode du titre avant extraction - corrige un scénario
réel où des accents en forme décomposée empêchaient la reconnaissance
de la date.

**Motif de la demande :** l'utilisateur a signalé que la date
principale affichée dans le rapport ne correspondait pas à celle du
titre du sondage, mais semblait plutôt être la date d'envoi/de
soumission - alors que le code (`_rencontre_date()`) privilégie
pourtant la date du titre depuis plusieurs versions. Cela indique que
l'extraction échoue silencieusement sur au moins certains titres réels,
avec un repli invisible vers la date de soumission.

**Diagnostic et détail des modifications :**
- Un scénario concret a été identifié et corrigé : si le titre du
  sondage contient des caractères accentués sous une forme Unicode
  **décomposée** (ex. la lettre "u" suivie d'un accent circonflexe
  combinant séparé, plutôt que le caractère "û" précomposé habituel -
  cela peut arriver selon l'origine du texte, par exemple un
  copier-coller depuis certains systèmes), le motif de reconnaissance
  ne correspondait pas, faisant silencieusement échouer l'extraction.
  `_extraire_date_titre()` normalise maintenant le titre en forme
  Unicode composée (NFC) avant toute reconnaissance - testé avec succès
  sur un exemple reproduisant exactement ce problème ("août" en forme
  décomposée).
- **Diagnostic visible ajouté** : quand l'extraction échoue malgré tout
  (aucune date reconnaissable dans le titre, pour quelque raison que ce
  soit) et qu'un repli sur la date de soumission est utilisé, un
  message apparaît maintenant dans le bandeau d'avertissement du
  rapport, citant le titre exact concerné et la date de repli utilisée -
  au lieu d'un repli totalement silencieux, indétectable sans relire
  attentivement chaque date affichée. Si ce message apparaît sur vos
  données réelles, le titre exact cité permettra d'identifier
  précisément le format non reconnu et de corriger la reconnaissance en
  conséquence.
- La date déjà extraite pour la rencontre est maintenant réutilisée
  pour la recherche de l'événement correspondant (`_lien_evenement`),
  plutôt que recalculée une seconde fois inutilement.

**Garde-fous et cas limites :**
- Le diagnostic de date non reconnue s'ajoute à la liste des autres
  avertissements (sondages à 0 réponse, questions ignorées) - si
  plusieurs sondages sont concernés, chacun aura sa propre ligne.

**Vérifications effectuées :** la normalisation Unicode testée avec un
exemple reproduisant fidèlement le problème des accents décomposés -
échec de reconnaissance confirmé avant normalisation, succès après.
Motif de date retesté aussi avec espaces insécables et espaces
multiples (déjà fonctionnel, non affecté par ce changement). Syntaxe
Python validée.

**Action requise :** mettre à jour le module et redémarrer le service.
Si la date affichée pour une rencontre ne correspond toujours pas à
celle du titre après cette mise à jour, le nouveau message de
diagnostic dans le rapport devrait maintenant indiquer précisément quel
titre pose problème - partagez-le pour que la reconnaissance soit
corrigée en conséquence.

---

## 18.0.1.17.0

**Titre court :** correction d'un plantage confirmé (méthodes de
notification inexistantes), correction d'un bug limitant à tort la
table des matières des participants à 20, gestion des trois dates
importantes d'un sondage (titre/envoi/expiration, avec repli d'année
et correspondance d'événement par date), sélecteur de thème dans le
rapport généré, tooltips sur tous les champs du formulaire, heure
UTC + locale pour la version, diagnostics « 0 réponse » moins verbeux.

**Motif de la demande :** (1) demande d'afficher l'heure UTC (et
locale) pour la dernière modification du module ; (2) demande de
tooltips sur toutes les options du formulaire ; (3) la liste des
participants de la table des matières était limitée à 20 (2 colonnes
de 10) ; (4) trois dates importantes à gérer (date du titre, date
d'envoi, date d'expiration), avec repli d'année et correspondance à un
événement par date ; (5) demande d'un bouton de changement de thème
directement dans le rapport généré ; (6) les messages « 0 réponse »
répétés pour plusieurs sondages rendaient le bandeau d'avertissement
illisible ; (7) erreur confirmée en production :
`AttributeError: 'res.users' object has no attribute 'notify_warning'` ;
(8) question sur la mise en place de Claude Code pour un accès direct à
l'environnement réel.

**Détail des modifications :**
- **(7, traité en premier - plantage confirmé)** `self.env.user.
  notify_warning()`/`notify_success()` n'existent pas sur cette
  instance (confirmé par les logs). Retour au mécanisme
  `display_notification` (dont on sait qu'il s'affiche réellement,
  déjà observé à l'écran par le passé), avec le rechargement de la
  fiche chaîné via `next` comme avant l'introduction de
  `notify_warning` en 1.15.0. Code mort (un `return` inatteignable)
  retiré au passage.
- **(3) Bug corrigé** : la table des matières des participants (en
  haut à droite) ne listait que les 20 premiers, la limite d'affichage
  détaillé (introduite en 1.16.0) ayant été appliquée AVANT de
  construire cette liste plutôt qu'après. Elle liste maintenant tout
  le monde ; une hauteur maximale (480px) avec défilement a été
  restaurée sur `.liste-individus` pour que la page reste équilibrée
  tout en gardant chacun accessible.
- **(1)** L'heure de dernière mise à jour du module (mode debug)
  affiche maintenant l'heure UTC explicitement étiquetée comme telle,
  suivie de l'heure locale entre parenthèses (fuseau horaire de
  l'utilisateur, via `fields.Datetime.context_timestamp`).
- **(2)** Un texte d'aide (`help=`) a été ajouté à tous les champs du
  formulaire qui n'en avaient pas encore (dates, réponses partielles,
  ventilation, dédoublonnage, thème) - affiché au survol dans
  l'interface d'Odoo.
- **(4)** Plusieurs ajouts liés aux dates :
    - `_extraire_date_titre()` accepte maintenant un titre sans année
      (ex. « 31 juillet »), auquel cas un `annee_repli` fourni par
      l'appelant est utilisé - typiquement l'année de la date d'envoi
      du sondage (`_annee_repli_titre()`, nouvelle méthode). Tous les
      appels (classement par sous-menu, date de la rencontre) en
      bénéficient maintenant.
    - `_dates_envoi_expiration()` (nouvelle méthode) : recherche
      dynamique (par mots-clés dans le nom du champ, comme pour le
      lien événement) d'une date d'envoi et d'une date d'expiration
      sur le sondage. Affichées sous le titre de chaque rencontre,
      sans jour de la semaine (contrairement à la date principale).
    - `_lien_evenement_par_date()` (nouvelle méthode, repli) : à défaut
      de relation directe en base entre le sondage et un événement,
      cherche un `event.event` ou `calendar.event` dont la date de
      début correspond exactement à la date extraite du titre du
      sondage - la vérification du nom de champ réel (parmi quelques
      candidats plausibles) se fait avant toute utilisation, sans
      risque d'erreur si aucun ne correspond.
- **(5)** Un sélecteur de thème (4 boutons) apparaît maintenant en
  tête du rapport généré à l'écran : cliquer change instantanément
  l'attribut `data-theme` du rapport en JavaScript pur, côté client -
  aucun appel au serveur, aucune régénération nécessaire.
- **(6)** Le message par sondage à 0 réponse est maintenant réduit à
  l'essentiel (titre + « 0/N réponse(s) retenue(s) ») ; l'explication
  générale (quoi vérifier) n'apparaît plus qu'une seule fois dans le
  bandeau, quel que soit le nombre de sondages concernés.

**Réponse à la question (8) :** voir la réponse donnée dans la
conversation - en résumé, Claude Code (l'outil en ligne de commande
d'Anthropic) permettrait, une fois pointé sur une copie locale ou un
accès SSH à l'instance réelle, de consulter directement le schéma exact
de la base de données et le code source de vos modules personnalisés
(ERPLibre, débrandisation, etc.), éliminant le besoin de deviner ou de
vérifier des noms de champs via GitHub comme cette conversation l'a
nécessité à plusieurs reprises.

**Garde-fous et cas limites :**
- Si `_dates_envoi_expiration()` ne trouve aucun champ correspondant
  (aucun mot-clé ne correspond à un champ Date/Datetime du modèle),
  aucune ligne n'est ajoutée au rapport - comportement silencieux et
  sans erreur, comme pour le lien événement.
- La correspondance d'événement par date (repli) peut, en théorie,
  trouver un événement sans rapport si un autre événement tombe par
  coïncidence le même jour - un risque jugé acceptable étant donné
  qu'aucune autre piste n'est disponible en l'absence de relation
  directe en base.

**Vérifications effectuées :** extraction de date avec et sans année
(avec et sans repli) testée en isolation - comportement correct dans
les trois cas. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. `report_builder.py` revérifié en isolation (aucune
régression sur les fonctions déjà testées précédemment). Comme
toujours, le comportement réel dans Odoo (absence de plantage,
affichage des trois dates, sélecteur de thème) n'a pas pu être vérifié
visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que le bouton « Générer » ne plante plus, et que
la liste des participants dans la table des matières affiche
maintenant tout le monde.

---

## 18.0.1.16.0

**Titre court :** correction du critère du sondage annuel (basé sur la
date du titre plutôt que la date de soumission), résumé des paramètres
en tête de rapport, limite de 20 participants détaillés (le reste en
liste simple), exclusion de « Je n'étais pas là » de la ventilation des
notes, largeur des cellules du tableau participant limitée à 30
caractères.

**Motif de la demande :** (1) le sous-menu « Sondage annuel » ne
trouvait aucun sondage malgré l'existence d'un sondage annuel connu ;
(2) absence de message visible pendant la génération, demande d'un
indicateur semblable à celui du PDF (écran assombri, animation) ; (3)
absence, en tête de rapport, d'un résumé des options/filtres utilisés
pour le générer ; (4) demande de limiter à 20 le nombre de participants
affichés en détail ; (5) « Je n'étais pas là » ne devrait pas apparaître
dans les listes « Détail des notes » de la synthèse ; (6) les cellules
du tableau par participant deviennent trop larges avec plusieurs
colonnes de dates.

**Détail des modifications :**
- **(1)** `_survey_ids_annuel()` se basait sur `create_date` (date de
  soumission des réponses), alors que les réponses à un sondage annuel
  peuvent être soumises sur plusieurs mois - aucune ne tombant
  nécessairement en septembre même si l'événement, lui, a bien lieu en
  septembre. Reconstruite pour utiliser la date extraite du **titre**
  du sondage (même mécanisme fiable que « Premier mardi du mois »),
  combinée à un simple décompte du nombre total de réponses.
- **(2)** Reproduire l'animation plein écran d'Odoo pour la génération
  de PDF nécessiterait d'appeler directement les services internes du
  framework web (`ui.block()`/`unblock()`), avec un risque réel de
  laisser l'écran bloqué en permanence si l'API exacte de cette version
  s'avérait différente de ce qui est documenté - un risque jugé
  disproportionné par rapport au bénéfice, donc non tenté. À la place,
  le message d'attente déjà présent (mais discret) est maintenant un
  encadré bleu bien visible (`alert alert-info`) plutôt qu'un simple
  texte grisé.
- **(3)** `_resume_parametres()` (nouvelle méthode) : liste dépliable
  (ouverte par défaut) en tête du rapport indiquant le nombre de
  sondages inclus, la plage de dates, l'inclusion ou non des réponses
  partielles, les participants/étiquettes exclus, le mot-clé
  d'exclusion de titre, et les options d'affichage (ventilation,
  dédoublonnage, thème) - affiché aussi bien dans le cas normal que
  dans le cas « aucune réponse trouvée ».
- **(4)** Les participants sont maintenant triés alphabétiquement puis
  coupés à 20 : seuls les 20 premiers reçoivent une fiche détaillée
  complète (informations de contact, tableau par date) ; les suivants
  apparaissent dans une simple liste de noms en fin de section
  Participants, sans fiche ni tableau.
- **(5)** Dans la ventilation « Détail des notes » (synthèse et détail
  par rencontre), seules les réponses numériques (1 à 5) sont
  désormais retenues - une réponse non numérique comme
  « Je n'étais pas là » n'y apparaît plus (elle reste par contre visible
  dans le tableau propre au participant qui a répondu ainsi, où
  l'information garde son sens).
- **(6)** Les cellules de valeur du tableau par participant (hors
  colonne des questions/volets) sont maintenant limitées à 30 caractères
  de large (`max-width: 30ch`) avec retour à la ligne du texte trop
  long, plutôt que d'élargir indéfiniment le tableau au fil des
  colonnes de dates.

**Garde-fous et cas limites :**
- Le regroupement par étiquette (ajouté en 1.14.0) continue de
  considérer TOUS les participants du rapport pour les décomptes,
  même ceux au-delà de la limite de 20 : seul l'affichage de LEUR
  propre fiche détaillée est omis. Un clic sur leur nom depuis la
  liste d'une étiquette n'aura simplement aucun effet (aucune section
  à cette ancre), sans erreur.
- Le résumé des paramètres affiche les noms des participants/étiquettes
  exclus tels qu'enregistrés dans Odoo - échappés avant insertion dans
  le HTML, comme partout ailleurs dans le rapport.

**Vérifications effectuées :** syntaxe Python et XML validées sur
l'ensemble des fichiers modifiés. CSS revérifié pour la présence de la
règle des 30 caractères et l'absence de conflit avec les colonnes
d'étiquettes (volontairement exclues de cette limite). Comme toujours,
le comportement réel dans Odoo (sondage annuel retrouvé, résumé des
paramètres, limite des 20 participants) n'a pas pu être vérifié
visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez en priorité que le sous-menu « Sondage annuel » retrouve
maintenant le sondage attendu.

---

## 18.0.1.15.0

**Titre court :** liste des participants non tronquée, notification de
génération remplacée par le service standard d'Odoo (disparition
fiable), colonnes « Taux de réussite »/« Note moyenne » retirées,
durée moyenne restreinte aux sondages terminés et masquée par défaut,
fiabilisation de l'affichage de la version en mode debug, informations
du participant sur des lignes distinctes, audit complet de sécurité et
de performance.

**Motif de la demande :** (1) la liste des participants était limitée
à environ 11 lignes visibles ; (2) la notification « Rapport généré
avec N avertissement(s) » restait affichée indéfiniment ; (3) demande
d'un audit de sécurité et de performance ; (4) « Taux de réussite » et
« Note moyenne » jugées non pertinentes, « Durée moyenne » à masquer
et à corriger pour ne considérer que les sondages terminés ; (5) la
version en mode debug n'apparaissait qu'après avoir cliqué sur
« Générer » plutôt que dès l'ouverture ; (6) confusion sur un chiffre
entre parenthèses apparaissant près de « Sondages remplis », qui
menait en fait à une liste de participants liés à l'étiquette
précédente.

**Détail des modifications :**
- **(1)** Retrait de `max-height: 280px` et `overflow-y: auto` sur
  `.liste-individus` : la liste s'étend maintenant sur autant de lignes
  que nécessaire, comme la liste des rencontres à côté.
- **(2)** Le mécanisme de notification a été entièrement revu :
  plutôt que de chaîner une notification à l'action de rechargement
  (paramètre `next`, dont le comportement combiné avec `sticky`
  semblait empêcher la disparition automatique), la notification est
  maintenant émise via le service découplé standard d'Odoo
  (`self.env.user.notify_warning()` / `notify_success()`), et l'action
  de rechargement de la fiche est retournée séparément. Ce mécanisme
  applique le délai de disparition automatique standard d'Odoo,
  indépendamment de toute action retournée. Protégé par un
  `try/except` : un problème de notification ne peut plus faire
  échouer la génération elle-même.
- **(3) Audit sécurité** : vérification systématique (recherche
  automatisée puis relecture manuelle) que toute valeur provenant d'un
  sondage ou d'une fiche contact (titres, noms, courriels, étiquettes,
  coordonnées...) passe par `echapper()`/`echapper_attr()` avant
  insertion dans le HTML du rapport - aucune faille trouvée. Un point de
  robustesse a néanmoins été ajouté par prudence : `lien_ancre()`
  assainit désormais explicitement l'identifiant d'ancre avant de
  l'insérer dans un attribut HTML et une chaîne JavaScript (ces
  identifiants étaient déjà toujours sans danger en pratique, puisque
  systématiquement produits par `slug()`, mais cette défense
  supplémentaire ne coûte rien). Un point à surveiller a été identifié
  et documenté (non corrigé automatiquement) : les pièces jointes
  créées par le téléchargement HTML contiennent des données
  personnelles et ne sont pas nettoyées automatiquement - voir
  NOTES_VALIDATION.md, section 5bis.
- **(3) Audit performance** : deux boucles interrogeant la base de
  données de façon répétée (« N+1 ») corrigées. `_survey_ids_annuel()`
  (sous-menu « Sondage annuel ») interrogeait individuellement tous les
  sondages du système avec une recherche imbriquée par sondage -
  remplacé par une seule requête SQL agrégée (paramétrée, sans risque
  d'injection). Le calcul de « Sondages remplis (total) » et
  « Événements inscrits » par participant, qui faisait une requête par
  personne, est maintenant calculé par lot pour tous les participants
  du rapport en une seule requête groupée chacun.
- **(4)** Les colonnes « Taux de réussite » (`success_ratio`) et
  « Note moyenne » (`answer_score_avg`) ont été retirées de la liste de
  sélection des sondages. « Durée moyenne (s) » passe en colonne
  masquée par défaut (`optional="hide"`, toujours accessible via le
  menu d'options de colonnes). Son calcul (`survey_survey.py`) ne
  dépend plus du champ natif `answer_duration_avg` (dont le périmètre
  exact n'avait pas pu être confirmé) : la durée moyenne est maintenant
  calculée directement à partir de `start_datetime`/`end_datetime`,
  explicitement restreinte aux réponses au statut Terminé
  (`state='done'`).
- **(5)** `debug_info` était un champ `compute` sans dépendances
  déclarées, qui ne semblait pas se calculer de façon fiable avant le
  premier enregistrement de la fiche. Remplacé par un champ avec une
  valeur par défaut (`default=`), un mécanisme garanti être appliqué
  dès l'ouverture d'un nouvel enregistrement (`default_get`), plutôt
  qu'un recalcul à la demande dont le déclenchement exact dépend du
  parcours emprunté par le client web.
- **(6)** La cause de la confusion : toutes les informations du
  participant (téléphone, étiquettes, sondages remplis...) étaient
  jointes sur une seule ligne séparées par un point médian, rendant
  ambigu à quel élément appartenait quel repère visuel. Chaque
  information s'affiche maintenant sur sa propre ligne - le chiffre en
  question était bien celui de l'étiquette précédente (nombre de
  personnes la partageant, ajouté en 1.14.0), pas lié à « Sondages
  remplis ».

**Garde-fous et cas limites :**
- La requête SQL agrégée de `_survey_ids_annuel()` utilise `%s` avec un
  tuple de paramètres (jamais de concaténation de chaînes) : aucun
  risque d'injection SQL, conformément aux pratiques standards d'Odoo
  pour les requêtes directes.
- Si `notify_warning`/`notify_success` ne sont pas disponibles sur
  cette instance (méthodes ajoutées par le module `mail`, déjà une
  dépendance), l'échec est intercepté et journalisé sans interrompre la
  génération - le rapport reste accessible même sans notification.

**Vérifications effectuées :** recherche automatisée (script Python) de
toute variable insérée dans du HTML sans passer par une fonction
d'échappement connue - aucun résultat suspect. `lien_ancre()` retestée
en isolation après l'ajout de l'assainissement : aucune régression sur
le cas normal. Syntaxe Python et XML validées sur l'ensemble des
fichiers modifiés. Comme toujours, le comportement réel dans Odoo
(temps de génération sur un gros sondage, disparition de la
notification, affichage de la version en mode debug dès l'ouverture)
n'a pas pu être vérifié faute d'accès à une instance.

**Action requise :** mettre à jour le module et redémarrer le service.
Si vous avez déjà téléchargé des rapports en HTML contenant des données
de participants, pensez à nettoyer les pièces jointes correspondantes
(voir NOTES_VALIDATION.md, section 5bis) si leur conservation n'est pas
souhaitée.

---

## 18.0.1.14.0

**Titre court :** étiquettes des participants rendues cliquables (liste
de ceux qui les partagent, parmi les répondants du rapport), jour de la
semaine affiché à côté de chaque date de rencontre.

**Motif de la demande :** (1) l'utilisateur veut pouvoir cliquer sur
une étiquette d'un participant pour voir qui d'autre, parmi les
répondants des sondages inclus, porte la même étiquette ; (2) afficher
le jour de la semaine (mardi, vendredi...) à côté de chaque date de
rencontre.

**Détail des modifications :**
- `liste_personnes_simple()` (nouvelle fonction dans
  report_builder.py) : comme les listes de noms déjà utilisées ailleurs
  dans le rapport, mais sans date associée (une étiquette n'a pas de
  date) - infobulle si une seule personne, liste dépliable avec liens
  cliquables vers chaque fiche individuelle sinon.
- Un dictionnaire étiquette → liste de participants est construit une
  fois pour tous les participants du rapport (limité à ceux ayant
  effectivement répondu à au moins un sondage inclus - pas l'ensemble
  des contacts portant cette étiquette dans tout Odoo). Chaque étiquette
  affichée dans la fiche d'un participant devient ainsi cliquable,
  montrant le nombre de personnes la partageant (elle-même incluse) et
  la liste complète au clic.
- `jour_semaine()` (nouvelle fonction) : convertit une date AAAA-MM-JJ
  en son jour de la semaine en français. Affiché à côté de la date dans
  l'en-tête de chaque section de rencontre (ex. « 2026-08-04 (mardi) »)
  et dans la table des matières.

**Garde-fous et cas limites :**
- Le regroupement par étiquette ne considère que les participants
  présents dans CE rapport (donc dépendant des sondages sélectionnés et
  des exclusions actives) - pas une recherche dans l'ensemble des
  contacts Odoo portant l'étiquette.
- `jour_semaine()` retourne `None` (aucun affichage) si la date n'est
  pas au format attendu (ex. si `_extraire_date_titre` n'a rien trouvé
  et que le titre du sondage est utilisé comme repli à la place d'une
  vraie date).

**Vérifications effectuées :** les deux fonctions testées en isolation.
`jour_semaine("2026-08-04")` retourne bien « mardi » et
`jour_semaine("2026-09-04")` retourne bien « vendredi », cohérent avec
les jours déjà confirmés précédemment pour les rencontres du club.
`liste_personnes_simple()` vérifiée pour 1 personne (infobulle) et 3
personnes (liste dépliable avec liens). Syntaxe Python validée.

**Action requise :** mettre à jour le module et redémarrer le service.
Vérifiez que les étiquettes des participants sont cliquables et que le
jour de la semaine apparaît bien à côté des dates de rencontre.

---

## 18.0.1.13.0

**Titre court :** copyright réellement visible (champ Auteur), lien
événement bidirectionnel, colonnes Inscrit/Terminé/Débuté sans
terminer/Durée moyenne, optimisation pour les sondages à plus de 100
réponses, PDF en 8x14 po paysage avec saut de page par rencontre.

**Motif de la demande :** plusieurs points signalés comme non visibles
malgré la version précédente : (1) copyright toujours invisible ; (2)
lien événement toujours absent ; (3) changelog pas visible dans les
détails du module ; (4) version en mode debug toujours non visible ; et
trois nouvelles demandes : (5) colonnes supplémentaires (Inscrit,
Terminé, Débuté sans terminer, durée moyenne) dans la liste des
sondages ; (6) un sondage à plus de 100 inscriptions ne fonctionne pas ;
(7) dates/participants en haut de page dans le PDF, format 8x14 po
paysage.

**Diagnostic et détail des modifications :**

- **(1)** Le champ manifeste `maintainer` que j'avais utilisé pour le
  copyright **n'est pas affiché** dans l'interface Apps d'Odoo -
  seul le champ `author` l'est. Corrigé : le copyright est maintenant
  dans `author` (« Rencontres Linux au Québec (Martial@Bigras.ca) »),
  visible directement dans la fiche du module.
- **(2)** `_lien_evenement()` ne cherchait que dans un seul sens (un
  champ sur survey.survey pointant vers event.event). Étendue pour
  chercher aussi dans le sens inverse (un champ sur event.event ou
  calendar.event pointant vers le sondage), et pour couvrir
  `calendar.event` en plus de `event.event` - toujours sans supposer de
  nom de champ précis. Si le lien reste introuvable après cette
  version, la relation utilisée sur votre instance n'est probablement
  ni l'un ni l'autre de ces schémas : dites-moi comment elle est faite
  (nom du modèle et du champ, si vous les connaissez) pour que je
  l'ajoute explicitement.
- **(3)** Plutôt qu'un simple pointeur vers CHANGELOG.md, la
  description du module (visible dans Apps > cliquer sur le module)
  contient maintenant un résumé des dernières versions directement.
  L'ajout d'un onglet séparé dans la fiche technique reste écarté (voir
  version précédente) - le risque d'altérer une vue utilisée par tous
  les modules de l'instance est disproportionné par rapport au
  bénéfice.
- **(4)** Le champ `debug_info` était placé à l'intérieur de
  `<div class="oe_title">`, une zone stylée spécifiquement pour le nom
  de l'enregistrement - il a été sorti dans son propre paragraphe
  (`<p groups="base.group_no_one">`) pour un affichage plus fiable.
  Pour le voir, le **mode développeur doit être activé** (Paramètres >
  faire défiler jusqu'en bas > Activer le mode développeur, ou ajouter
  `?debug=1` à l'URL) : c'est le comportement normal et voulu de
  `base.group_no_one`, le mécanisme standard d'Odoo pour ce genre
  d'information technique.
- **(5)** Nouveau fichier `models/survey_survey.py` : extension de
  `survey.survey` (aucune vue du module Sondage d'origine n'est
  touchée, seulement deux nouveaux champs calculés) ajoutant
  `rlq_answer_in_progress_count` (réponses commencées mais non
  terminées) et `rlq_answer_duration_avg_seconds` (durée moyenne en
  secondes, calculée à partir du champ natif `answer_duration_avg`,
  exprimé en heures). La liste de sondages affiche maintenant : Titre,
  **Inscrit** (`answer_count`), **Terminé** (`answer_done_count` -
  malgré son nom anglais « Attempts », ce champ compte en réalité les
  réponses au statut terminé), **Débuté sans terminer**, **Durée
  moyenne (s)**, puis Responsable/Taux de réussite/Note moyenne
  (masqués par défaut, comme avant).
- **(6)** Cause probable identifiée et corrigée : `_get_input_lines()`
  était appelée une fois **par question**, et recalculait à chaque fois
  l'ensemble des lignes de réponse de la rencontre au complet
  (`user_inputs.mapped(...)` puis `.filtered(...)`) avant d'en extraire
  la portion utile. Pour une rencontre à 11 questions et 100+ réponses,
  cela répétait un balayage complet 11 fois. Toutes les lignes sont
  maintenant chargées **une seule fois par rencontre**, puis réparties
  par question dans un dictionnaire - chaque question y accède
  ensuite directement, sans nouveau balayage. Si un problème persiste
  avec un gros sondage après cette optimisation, le symptôme exact
  (message d'erreur, ou simplement une fenêtre qui ne répond plus)
  m'aiderait à cibler la suite.
- **(7)** Nouveau format de page personnalisé (203 x 356 mm, soit 8 x 14
  po, en paysage) remplaçant le A4 paysage précédent. Chaque section de
  rencontre démarre maintenant sur une nouvelle page
  (`page-break-before: always`, sauf la toute première after la
  synthèse) : sa date et sa liste de participants apparaissent donc
  toujours en haut d'une page plutôt qu'au milieu de la précédente.

**Garde-fous et cas limites :**
- `rlq_answer_duration_avg_seconds` vaut 0 si aucune réponse n'a de
  durée mesurable (champ natif `answer_duration_avg` à 0 ou absent).
- Le saut de page systématique par rencontre peut laisser une page
  partiellement vide en fin de section courte - compromis assumé pour
  garantir que chaque rencontre démarre proprement en haut de page.

**Vérifications effectuées :** syntaxe Python et XML validées sur
l'ensemble des fichiers, y compris le nouveau fichier
`models/survey_survey.py`. Comme toujours, le rendu réel dans Odoo
(colonnes, mode debug, PDF, lien événement, comportement sur un gros
sondage) n'a pas pu être vérifié visuellement faute d'accès à une
instance.

**Action requise :** mettre à jour le module ET redémarrer complètement
le service Odoo. Vérifiez en particulier : (a) le champ Auteur du
module affiche-t-il le copyright dans Apps ? (b) les colonnes Inscrit/
Terminé/Débuté sans terminer/Durée moyenne apparaissent-elles dans la
liste des sondages ? (c) un gros sondage (>100 réponses) génère-t-il
maintenant son rapport ? (d) le PDF est-il en 8x14 paysage avec un saut
de page par rencontre ? (e) en mode développeur actif, la version
apparaît-elle sous le titre de la fenêtre ?

---

## 18.0.1.12.0

**Titre court :** noms de champs vérifiés directement sur GitHub
(Odoo 18 CE), copyright, lien vers l'événement (détection dynamique),
version affichée en mode debug, exclusion par mot-clé dès la liste de
sélection, code couleur uniforme des notes (1-5) partout dans le
rapport, coloration des % restreinte à « Note moyenne », tooltips
corrigés, rendu PDF corrigé (histogrammes et listes dépliables enfin
visibles).

**Motif de la demande :** lot de 14 demandes, incluant la suggestion de
vérifier les noms de champs directement sur le code source d'Odoo 18 CE
sur GitHub plutôt que de deviner.

**Détail des modifications :**

1. **Copyright** : ajouté au manifeste (`maintainer`, `website`,
   mention dans la description) et en pied de chaque rapport généré
   (« © Rencontres Linux au Québec — Martial@Bigras.ca »).
2. **Lien vers l'événement** : `_lien_evenement()` (nouvelle méthode)
   détecte dynamiquement, sur `survey.survey`, un champ Many2one vers
   `event.event` (absent du module Sondage d'origine - donc
   probablement ajouté spécifiquement chez vous) et affiche un lien
   sous le titre du sondage s'il en trouve un. Approche sans risque :
   si aucun champ de ce type n'existe, rien ne s'affiche, sans erreur.
3. Non traité de façon exhaustive dans cette version - la vérification
   des noms de champs (point 4) et l'uniformisation des couleurs
   (points 9-11) réduisent les écarts les plus visibles entre les deux
   programmes, mais un audit complet ligne à ligne n'a pas été fait.
4. **Vérification sur GitHub** : le code source réel d'Odoo 18 CE
   (`addons/survey/models/survey_survey.py`) a été consulté
   directement. Cela a permis de découvrir qu'ERPLibre est un
   « soft-fork » utilisant le cœur Odoo standard, avec des modules OCA
   additionnels (dont un de « débrandisation » du module Sondage) -
   ce qui explique la divergence trouvée précédemment sur le modèle
   des lignes de réponse. Les champs de `survey.survey` eux-mêmes sont
   ceux du cœur standard.
5. **Changelog dans Apps** : après recherche, la structure exacte de la
   fiche technique d'un module (pour y ajouter un onglet dédié) n'a pas
   pu être confirmée avec un niveau de certitude suffisant - le risque
   d'y toucher (une fiche utilisée par TOUS les modules, pas seulement
   celui-ci) était disproportionné par rapport au bénéfice. Un pointeur
   vers CHANGELOG.md a plutôt été ajouté à la description du module,
   déjà visible dans Apps.
6. **Version en mode debug** : nouveau champ `debug_info`, affiché sous
   le titre de la fenêtre uniquement quand le mode développeur est
   actif (`groups="base.group_no_one"`, le mécanisme standard d'Odoo
   pour ce genre d'information technique) - indique la version
   installée et la date de dernière mise à jour du module.
7. **Correction des noms de champs de la liste de sondages** (la
   demande précédente n'avait pas été suivie correctement) : le nom
   vérifié pour « Tentatives » est `answer_done_count` (« Attempts »),
   pas `answer_count` (qui signifie « Registered »/Inscrits - un
   concept différent). « Responsable » (`user_id`) et « Taux de
   réussite » (`success_ratio`) étaient déjà corrects. **Nouveau** :
   « Note moyenne » (`answer_score_avg`, « Avg Score (%) ») ajoutée,
   son nom étant maintenant confirmé via le code source.
8. **Exclusion par mot-clé dès la liste** : ajout d'un `domain="[('title',
   'not ilike', 'test')]"` directement sur le champ de sélection des
   sondages - un sondage de test n'apparaît plus du tout dans la liste
   à choisir, en plus de l'exclusion (avec avertissement) déjà en place
   à la génération.
9. **Code couleur uniforme (1-5) partout** : `colorer_par_valeur()`
   déduit maintenant automatiquement la note d'un texte quand elle
   n'est pas fournie explicitement (ex. dans le tableau par
   participant, qui ne la calculait pas avant) - vert si ≥ 5, rouge si
   ≤ 2, **jaune si 3 ou 4** (nouvelle nuance, auparavant ni verte ni
   rouge mais sans couleur).
10. **Coloration des % restreinte à « Note moyenne »** : nouveau
    paramètre `colorer_seuils` sur `barre()`, activé uniquement pour la
    barre de note moyenne des questions matricielles - les barres
    « % Oui » et « Proportion » (choix) ne sont plus colorées par
    seuil.
11. **Statistiques colorées** : Min, Moy, Max et P95 (colonne
    « Statistiques ») utilisent maintenant le même code couleur 1-5
    qu'ailleurs (l'écart-type reste non coloré, ce n'est pas une note).
    **Tooltip** : largeur maximale augmentée (260px → 380px) pour que
    nom et courriel restent sur une seule ligne visuelle. **Seuil**
    changé : une infobulle n'apparaît plus que si une seule ligne est à
    afficher (auparavant jusqu'à 2) ; 2 personnes ou plus affichent
    désormais toujours la liste dépliable.
13. **Rendu PDF corrigé** : deux problèmes distincts identifiés. (a)
    Les histogrammes étaient invisibles car leurs couleurs reposaient
    sur des variables CSS (`var(--xxx)`) que wkhtmltopdf ne garantit
    pas de résoudre - des couleurs figées (valeurs fixes, thème bleu
    uniquement) ont été ajoutées en repli pour le PDF. (b) « Détail des
    notes » et les autres listes dépliables restaient invisibles malgré
    le CSS les forçant ouvertes - nouvelle méthode `_html_pour_pdf()`
    qui convertit chaque `<details>/<summary>` en une structure
    toujours visible (non repliable) avant l'impression, plutôt que de
    compter sur un comportement CSS incertain.

**Garde-fous et cas limites :**
- `_lien_evenement()` ne suppose aucun nom de champ précis : elle
  parcourt tous les champs de `survey.survey` à la recherche d'un
  Many2one vers `event.event`, ce qui la rend sans risque même si le
  nom exact diffère de ce à quoi on pourrait s'attendre.
- La conversion PDF des listes dépliables (`_html_pour_pdf`) est basée
  sur une expression régulière ciblant précisément la structure produite
  par `construire_detail_personnes()` - un changement de structure HTML
  future devra mettre à jour cette méthode en parallèle.

**Vérifications effectuées :** transformation `_html_pour_pdf` testée
en isolation sur un exemple représentatif - conversion correcte.
Coloration des statistiques et de la barre « Note moyenne » testée en
isolation avec des valeurs couvrant les 3 couleurs. Syntaxe Python et
XML validées sur l'ensemble des fichiers modifiés. Comme toujours, le
rendu réel dans Odoo (PDF, mode debug, lien événement) n'a pas pu être
vérifié visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module ET redémarrer complètement
le service Odoo. Vérifiez en particulier : (a) le PDF affiche-t-il
enfin les histogrammes et le détail des notes ? (b) la colonne
« Note moyenne » apparaît-elle dans les options de colonnes de la liste
de sondages ? (c) un sondage contenant « test » est-il absent de la
liste de sélection ?

---

## 18.0.1.11.0

**Titre court :** liste de sondages personnalisée (titre lisible +
colonne Tentatives), fenêtre plus large, indication de progression,
ordre chronologique inversé dans la table des matières, titre du
sondage sous la date, nom de fichier PDF aligné sur le HTML, mise en
page PDF rapprochée du HTML, tableau par participant reproduisant la
disposition « une colonne par rencontre » de la version autonome,
informations de contact enrichies, exclusions par étiquette et par
mot-clé du titre, coloration des pourcentages par seuil.

**Motif de la demande :** lot de 12 demandes en une seule fois - voir
le détail ci-dessous, organisé dans le même ordre que la demande
originale.

**Détail des modifications :**

1. **Liste de sondages personnalisée** : la vue liste par défaut du
   modèle Sondage affichait plusieurs colonnes (Responsable, Taux de
   réussite, Note moyenne) qui laissaient trop peu de place au titre.
   Une liste inline dédiée au champ `survey_ids` affiche maintenant en
   premier le titre (sans contrainte de largeur), suivi de
   « Tentatives » (`answer_count`) visible par défaut, puis
   « Responsable » (`user_id`) et « Taux de réussite »
   (`success_ratio`) disponibles mais masqués par défaut (menu
   d'options de colonnes). **« Note moyenne » n'a pas été ajoutée** :
   son nom de champ technique reste inconnu - dites-le-moi si vous le
   connaissez. **Risque à surveiller** : `answer_count` et
   `success_ratio` sont des noms de champs standards du module Sondage
   d'Odoo, non vérifiés sur cette instance ERPLibre précise (qui a déjà
   montré au moins une divergence par le passé). Si l'installation
   échoue en nommant l'un de ces champs introuvable, supprimez
   uniquement la ligne `<field>` correspondante (voir
   NOTES_VALIDATION.md, qui documente cette procédure) - le reste du
   module n'est pas affecté.
2. Ajout d'un contexte `dialog_size: extra-large` sur l'action
   d'ouverture du wizard (XML) et sur les deux actions retournées
   dynamiquement en Python (rechargement après génération, ouverture
   depuis un sous-menu de raccourci), dans l'espoir d'obtenir une
   fenêtre plus large. Sans risque si cette clé n'est pas reconnue par
   cette version d'Odoo (simplement ignorée).
3. Un texte d'avertissement (« ⏳ La génération peut prendre quelques
   secondes... ») apparaît maintenant sous les paramètres, tant que le
   rapport n'a pas encore été généré.
4. Les rencontres sont maintenant triées par ordre chronologique
   inversé (la plus récente en premier), autant dans la table des
   matières que dans le corps du rapport global - les libellés de date
   étant au format AAAA-MM-JJ, un tri lexicographique inversé équivaut
   à un tri chronologique inversé.
5. Le titre complet du sondage apparaît maintenant sous la date, dans
   l'en-tête de chaque section de rencontre.
6. Le nom du fichier PDF suit maintenant le même schéma que le HTML
   (`RapportSondage-RLQ-AAAAMMJJ.HHMMSS`), basé sur la date de
   dernière modification de l'enregistrement plutôt que sur son id.
7. Retrait de la réduction de taille de police du gabarit PDF (10.5px),
   qui n'avait pas de justification fonctionnelle et éloignait
   inutilement le rendu PDF de celui du HTML. Les seules surcharges CSS
   restantes en PDF sont celles strictement nécessaires (forcer
   l'affichage des listes dépliables, puisque l'interactivité n'existe
   pas à l'impression).
8. **Tableau par participant entièrement reconstruit** pour retrouver
   la disposition de la version autonome : une colonne par rencontre
   (au lieu d'une ligne par question × par rencontre), avec les
   questions matricielles ventilées en une ligne d'en-tête suivie d'une
   ligne par volet. Nécessite un nouveau format de stockage interne des
   réponses (dict par volet pour les questions matricielles, au lieu
   d'un texte concaténé) - `_traiter_question()` et
   `tableau_reponses_personne()` (nouvelle fonction dans
   report_builder.py) adaptés en conséquence. Corrige au passage un
   bug latent sur les questions à choix multiples, dont les valeurs
   s'écrasaient au lieu de s'accumuler.
9. Nouveau bloc d'informations sous le nom de chaque participant, tiré
   de sa fiche contact (res.partner) quand elle est liée : téléphone,
   mobile, ville, pays, étiquettes, nombre de sondages remplis (total,
   tous temps - pas seulement ceux inclus dans ce rapport), et nombre
   d'événements inscrits si le module `event` est installé (vérifié
   dynamiquement, aucune nouvelle dépendance forcée).
10. Nouveau champ « Exclure par étiquette » (`exclude_tag_ids`,
    Many2many res.partner.category), pré-rempli par défaut avec
    l'étiquette « Collaborateurs-2026 » si elle existe sur l'instance
    (recherche exacte insensible à la casse ; n'échoue pas si absente).
11. Nouveau champ « Exclure les sondages dont le titre contient »
    (`exclude_title_keywords`, texte, défaut : « test »). Un sondage
    sélectionné dont le titre contient un des mots listés (séparés par
    virgule) est ignoré à la génération, avec un avertissement dans le
    rapport plutôt qu'une exclusion silencieuse.
12. Coloration du pourcentage affiché dans tous les histogrammes du
    rapport : vert (≥ 90 %), jaune (70-89 %), orange (60-69 %), rouge
    (< 60 %).

**Garde-fous et cas limites :**
- Le format « une colonne par volet » ne s'applique qu'aux questions de
  type `matrix` ; les autres types (choix, texte) gardent une seule
  ligne par question, comme avant.
- L'exclusion par mot-clé du titre s'applique uniquement à la
  génération du rapport (`_compute_report`), pas aux 4 raccourcis de
  sélection rapide (qui s'exécutent avant que les champs du formulaire
  ne soient renseignés) - un sondage de test resterait donc
  sélectionnable via un raccourci, mais serait exclu (avec
  avertissement) au moment de générer.
- `_default_exclude_tag_ids()` et le bloc d'informations participant
  n'échouent jamais si l'étiquette ou le module `event` sont absents :
  ils s'omettent simplement plutôt que de lever une erreur.

**Vérifications effectuées :** `tableau_reponses_personne()` testé en
isolation avec un participant simulé sur 2 rencontres (une question
matricielle avec volets différents par date) - la structure (ligne
d'en-tête + une ligne par volet + valeurs alignées par colonne de date)
correspond bien à celle de la version autonome. Coloration des
pourcentages testée sur les 4 seuils. Syntaxe Python et XML validées
sur l'ensemble des fichiers. Comme toujours, le rendu réel dans Odoo
(largeur de fenêtre obtenue, liste de sondages, informations de
contact) n'a pas pu être vérifié visuellement faute d'accès à
l'instance.

**Action requise :** mettre à jour le module ET redémarrer complètement
le service Odoo (voir la note à ce sujet dans NOTES_VALIDATION.md).
Vérifiez ensuite dans l'ordre : (a) le titre des sondages est-il
maintenant lisible en entier dans la liste de sélection ? (installation
réussie malgré les nouveaux champs `answer_count`/`success_ratio` ?) ;
(b) la fenêtre est-elle plus large ; (c) le tableau d'un participant
ayant assisté à plusieurs rencontres affiche-t-il bien une colonne par
date ; (d) les informations de contact apparaissent-elles ; (e) les
exclusions par défaut (étiquette, mot « test ») fonctionnent-elles.

---

## 18.0.1.10.0

**Titre court :** retrait du menu racine « Rapports RLQ », classement
« Premier mardi » limité à la date du titre (plus de faux positifs),
affichage complet des titres de sondages sélectionnés, hyperliens
internes fonctionnels à l'écran, correction des accents et passage en
paysage pour le PDF.

**Motif de la demande :** (1) le menu racine indépendant « Rapports
RLQ » devait être retiré, ne conservant que « Rapport détaillé » sous
Sondage ; (2) un sondage mentionnant « 31 juillet » sans année a été
classé à tort dans « Premier mardi du mois » ; (3) le titre des
sondages sélectionnés restait tronqué malgré l'élargissement précédent,
un exemple concret étant fourni ; (4) cliquer sur le nom d'un
participant, à l'écran dans Odoo, ouvre une mauvaise URL au lieu de
faire défiler vers la section correspondante ; (5) les accents ne
s'affichent pas bien dans le PDF ; (6) le PDF devrait être en format
paysage ; (7) le sous-menu « Pause café » provoque une erreur
`AttributeError` en évaluant `action_menu_pause_cafe`.

**Détail des modifications :**
- **(1)** Retrait complet du menu racine « Rapports RLQ » et de ses 5
  entrées ; seul le menu conteneur « Rapport détaillé » (sous Sondage)
  subsiste, avec ses 5 mêmes entrées.
- **(2)** `_extraire_date_titre()` rejette maintenant une année hors de
  la plage 2015-2035 (garde-fou). Surtout : `_survey_ids_premier_mardi()`
  n'utilise plus le repli sur la date de soumission des réponses
  (fonction `_date_survey()`, retirée) - seule une date complète
  (jour + mois + année) trouvée dans le titre compte désormais. Un
  sondage sans date de titre reconnaissable n'est plus jamais classé
  ici par accident via sa date de soumission.
- **(3)** Le widget `many2many_tags` du champ « Sondages » tronque
  chaque étiquette indépendamment de la largeur du champ - la vraie
  cause du titre tronqué persistant malgré l'élargissement précédent.
  Remplacé par le widget par défaut (liste), qui affiche le titre
  complet de chaque sondage sélectionné, avec sa date. Vérifié sur
  l'exemple fourni (titre avec emoji et date entre parenthèses) : la
  date y est bien extraite correctement par la regex.
- **(4)** Nouvelle fonction `lien_ancre()` (remplace la construction
  directe de `<a href='#...'>`) : ajoute un gestionnaire `onclick` qui
  empêche le comportement par défaut et fait défiler manuellement
  jusqu'à l'élément visé. Nécessaire car le routeur de l'application
  Odoo intercepte les liens `href='#id'` et tente d'en faire un
  changement de page plutôt que de laisser le navigateur faire défiler
  la page jusqu'à l'ancre - d'où l'atterrissage sur une mauvaise URL
  observé. `lien_date()`, `lien_personne()` et tous les liens de la
  table des matières utilisent maintenant cette fonction. Le
  `href='#id'` reste présent en repli (utile si le rapport est ouvert
  hors d'Odoo, via le fichier HTML téléchargé, où ce problème ne se
  pose pas).
- **(5)** Ajout d'une balise `<meta charset="utf-8"/>` explicite dans
  le gabarit PDF, juste avant le contenu du rapport - garde-fou pour
  wkhtmltopdf, qui peut mal interpréter les caractères accentués sans
  cette déclaration explicite même quand le conteneur englobant est
  censé la fournir.
- **(6)** Nouveau `report.paperformat` dédié (A4 paysage), référencé
  par l'action de rapport PDF.
- **(7)** Ce n'est pas un bug de code : voir la nouvelle section
  ajoutée à NOTES_VALIDATION.md. Le message d'erreur confirme que le
  code stocké dans l'action serveur a bien été mis à jour (il
  référence correctement `action_menu_pause_cafe`), mais la classe
  Python du modèle, encore chargée en mémoire par le processus Odoo en
  cours d'exécution, ne connaît pas encore cette méthode - signe qu'un
  **redémarrage complet du service** (pas seulement `-u`) est
  nécessaire après le déploiement de nouveaux fichiers Python.

**Garde-fous et cas limites :**
- Le retrait de `_date_survey()` signifie qu'un sondage sans date
  reconnaissable dans son titre n'apparaîtra plus jamais dans
  « Premier mardi du mois », même s'il s'agit réellement d'une
  rencontre du premier mardi - il resterait toutefois disponible via
  « Sélection manuelle » ou finirait dans « Tous les autres ».
- Le format paysage ne s'applique qu'au PDF ; l'affichage à l'écran et
  le fichier HTML ne sont pas concernés par cette notion de page.

**Vérifications effectuées :** regex de date retestée sur l'exemple
exact fourni par l'utilisateur (titre avec emoji, texte long, date
entre parenthèses) - extraction réussie. Fonction `lien_ancre()`
testée en isolation : gestionnaire onclick correctement généré. Syntaxe
Python et XML validées. Comme toujours, le rendu PDF réel (accents,
orientation) et le comportement exact du clic à l'écran dans le client
Odoo n'ont pas pu être vérifiés visuellement faute d'accès à une
instance.

**Action requise :** mettre à jour le module ET **redémarrer
complètement le service Odoo** (pas seulement `-u`), pour garantir que
le nouveau code Python est bien chargé. Vérifiez ensuite : (a) le menu
« Rapports RLQ » a disparu ; (b) « Premier mardi du mois » ne contient
plus de faux positif ; (c) le titre complet des sondages sélectionnés
est visible ; (d) cliquer sur un participant fait défiler vers sa
section ; (e) les accents s'affichent bien dans le PDF ; (f) le PDF est
en paysage ; (g) « Pause café » fonctionne sans erreur.

---

## 18.0.1.9.0

**Titre court :** diminutifs de mois français, remplacement du critère
« Vendredi midi » par « Pause café », élargissement du champ des
sondages sélectionnés, nouvelle tentative de correction du PDF,
version du module en pied de rapport, synthèse déplacée en tête.

**Motif de la demande :** (1) des dates de titre comme « 4 nov 2025 »
ou « 2 déc » n'étaient pas reconnues (diminutifs de mois non
supportés) ; (2) le sous-menu « Vendredi midi » doit être remplacé par
une recherche de « pause café »/« pause-café » dans le titre ; (3) le
champ affichant les sondages sélectionnés devrait être aussi large que
le permet la fenêtre ; (4) le PDF échouait toujours avec la même erreur
`IndexError` malgré la correction précédente ; (5) demande d'afficher
la version du module en bas du rapport ; (6) demande de replacer la
section Synthèse en tête du rapport global plutôt qu'à la fin.

**Détail des modifications :**
- `MOIS_FR` étendu avec les diminutifs courants (janv/jan, févr/fev/fév,
  mar, avr, juil, aoû/aou, sept/sep, oct, nov, déc/dec), et le motif de
  reconnaissance tolère un point final (ex. « fév. »). Testé avec
  succès sur « 4 nov 2025 », « 2 déc 2025 », « 3 fév. 2026 », etc.
- `_survey_ids_vendredi_midi()` → `_survey_ids_pause_cafe()` : recherche
  maintenant « pause café », « pause-café », « pause cafe » et
  « pause-cafe » (accents et casse ignorés) dans le titre, plutôt que
  le jour de la semaine. Renommage cohérent des actions serveur et
  sous-menus (« Vendredi midi » → « Pause café », aux deux
  emplacements : « Rapports RLQ » et « Sondage > Rapport détaillé »).
- Vue formulaire : le champ « Sondages » occupe maintenant toute la
  largeur du formulaire (`colspan="2"`, sorti des deux colonnes),
  plutôt que la moitié gauche seulement.
- Gabarit PDF : nouvelle tentative pour corriger l'erreur récurrente
  `IndexError: list index out of range` sur `root.xpath('//main')[0]`
  - au lieu de compter sur `web.internal_layout` pour fournir cet
    élément (ce qui n'a pas fonctionné), le gabarit inclut maintenant
    directement une balise `<main>` explicite autour du contenu.
- `_version_module()` (nouvelle méthode) : lit la version installée du
  module via `ir.module.module`, affichée en pied de chaque rapport
  généré (« Généré par le module rlq_survey_report vX.Y.Z.A.B ») -
  utile pour savoir quelle version exacte a produit un rapport donné
  lors d'un dépannage ultérieur.
- La section Synthèse est désormais assemblée en premier dans le
  rapport global (avant le détail de chaque rencontre), et son lien
  apparaît en tête de la colonne « Rapport global » de la table des
  matières plutôt qu'à la fin.

**Garde-fous et cas limites :**
- Les diminutifs de mois sont triés du plus long au plus court avant
  d'être assemblés dans le motif de reconnaissance, pour éviter qu'une
  forme courte (ex. « mar ») n'empêche la reconnaissance d'une forme
  plus longue démarrant par les mêmes lettres (ex. « mars ») - le
  moteur d'expressions régulières revient de toute façon en arrière si
  besoin, mais cet ordre reste plus clair et légèrement plus efficace.
- La recherche « pause café » utilise ILIKE (insensible à la casse),
  mais reste sensible à l'orthographe exacte des espaces/tirets : les
  4 variantes couvertes (avec/sans accent, espace/tiret) devraient
  couvrir les cas réalistes.

**Vérifications effectuées :** logique d'extraction de date re-testée
avec des diminutifs (« 4 nov 2025 », « 2 déc 2025 », « 3 fév. 2026 »,
« 7 avr 2026 ») - toutes correctement reconnues comme des mardis.
Syntaxe Python et XML validées. Comme pour la tentative précédente, le
rendu PDF réel n'a pas pu être vérifié faute d'accès à une instance -
si l'erreur `//main` persiste malgré cette balise explicite, le
problème serait alors probablement ailleurs dans la chaîne de
préparation du document (à investiguer avec le prochain message
d'erreur complet).

**Action requise :** mettre à jour le module (`-u rlq_survey_report`),
puis revérifier : (a) le sous-menu « Premier mardi du mois »
présélectionne-t-il maintenant les 11 sondages ? (b) le nouveau
sous-menu « Pause café » sélectionne-t-il les bons sondages ? (c) le
PDF se génère-t-il enfin sans erreur ? (d) la version du module
apparaît-elle en bas du rapport ? (e) la Synthèse apparaît-elle
maintenant en premier ?

---

## 18.0.1.8.0

**Titre court :** correction du classement incomplet des sondages
« Premier mardi »/« Vendredi midi », de l'échec de génération PDF, de
l'action « Générer » cassée en format écran (erreur JS), ajout de la
liste des participants dans la table des matières, correction d'un
saut de ligne indésirable dans les dates.

**Motif de la demande :** (1) seulement 2 sondages sur 11 attendus
étaient classés « Premier mardi du mois » ; (2) le format PDF
provoquait une erreur serveur `IndexError: list index out of range`
sur `root.xpath('//main')[0]` ; (3) le format écran provoquait une
erreur JavaScript `Cannot read properties of undefined (reading
'map')` ; (4) le fichier HTML exporté ne montre plus la liste des
participants (avec hyperliens) visible auparavant ; (5) dans le
tableau d'un participant, une date se coupait sur deux lignes
(« 2026-08- » puis « 03 »).

**Diagnostic et corrections :**
- **(1)** Vérification faite : les 11 dates connues du club sont
  toutes effectivement des mardis dans les 7 premiers jours du mois -
  la logique de classement elle-même était correcte. Le problème
  venait de l'extraction de la date depuis le *titre* du sondage, qui
  échouait pour la plupart d'entre eux (format de titre variable).
  Nouvelle méthode `_date_survey()` : utilise la date du titre si
  trouvée, sinon retombe sur la date de soumission des réponses (comme
  le fait déjà `_rencontre_date()` pour le reste du rapport) - les 4
  méthodes de classement l'utilisent maintenant, ce qui devrait couvrir
  la totalité des 11 sondages.
- **(2)** Le gabarit QWeb du PDF ne produisait pas la balise `<main>`
  attendue par le moteur de rendu PDF standard d'Odoo (qui l'utilise
  pour fusionner en-tête/pied de page). Le contenu est maintenant
  enveloppé avec `t-call="web.html_container"` puis
  `t-call="web.internal_layout"`, qui fournissent cette structure.
  Effet de bord possible : `web.internal_layout` peut ajouter un léger
  habillage (logo/adresse de la société) selon la configuration - à
  vérifier visuellement.
- **(3)** Les actions `ir.actions.act_window` construites à la main en
  Python (rechargement de la fiche après génération, ouverture depuis
  les sous-menus de raccourci) ne précisaient pas la clé `views`,
  requise par le client web pour certains traitements internes -
  d'où l'erreur `.map()` sur une valeur `undefined`. Ajout de
  `"views": [[False, "form"]]` aux deux endroits concernés.
- **(4)** La table des matières du module Odoo n'a jamais inclus la
  liste des participants (contrairement à la version autonome du
  programme) : uniquement un oubli lors du portage. Ajoutée
  maintenant, en deux colonnes (rencontres à gauche, participants à
  droite, triés alphabétiquement, avec le nombre de participations
  entre parenthèses) - avec les classes CSS correspondantes
  (`table-matieres`, `colonnes-tm`, `liste-individus`), elles aussi
  absentes du CSS du module jusqu'ici.
- **(5)** La cellule de date du tableau par question d'un participant
  ne précisait pas `white-space: nowrap`, permettant au navigateur de
  couper la date au niveau du tiret. Corrigé, et appliqué aussi à la
  classe `.date-oui` utilisée ailleurs dans le rapport par cohérence.

**Garde-fous et cas limites :**
- `_date_survey()` peut retourner `None` si un sondage n'a ni date
  dans son titre ni aucune réponse : il est alors simplement absent des
  4 catégories du classement rapide (mais reste sélectionnable via
  « Sélection manuelle »).

**Vérifications effectuées :** logique de classement re-testée sur les
11 dates connues (toutes des mardis, confirmé). Syntaxe Python/XML
validée. CSS du module vérifié pour la présence des nouvelles classes.
Comme toujours, le rendu PDF réel et le comportement exact du client
web après une action retournée dynamiquement n'ont pas pu être
vérifiés visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`),
puis revérifier successivement : (a) le sous-menu « Premier mardi du
mois » présélectionne-t-il maintenant les 11 sondages ? (b) le format
PDF se télécharge-t-il sans erreur ? (c) le format écran affiche-t-il
le rapport sans erreur JavaScript ? (d) la liste des participants
apparaît-elle en haut à droite de la table des matières ?

---

## 18.0.1.7.0

**Titre court :** classement des sondages par jour de semaine extrait
de la date dans le titre (au lieu de mots-clés absents), champ
explicite « Format de sortie », rechargement forcé après génération.

**Motif de la demande :** (1) le titre des sondages ne contient pas
« premier mardi » ni « vendredi midi », mais contient toujours une
date (ex. « 4 août 2026 ») ; (2) l'utilisateur ne trouvait pas où
indiquer le format de sortie souhaité (HTML/PDF/écran) ; (3) après
avoir choisi un sondage et cliqué sur « Générer », rien ne s'affichait
à l'écran - seules les requêtes réseau apparaissaient dans les logs,
sans erreur ni résultat visible.

**Détail des modifications :**
- `_extraire_date_titre()` (nouvelle méthode) : extrait une date d'un
  titre de sondage contenant un texte français du type « 4 août 2026 »
  ou « 1er septembre 2026 » (tous les mois, avec ou sans accent,
  insensible à la casse).
- `_rencontre_date()` : utilise maintenant cette date extraite du titre
  en priorité (plus fiable que la date de soumission des réponses, qui
  peut suivre l'événement de quelques jours - même principe déjà
  appliqué dans la version autonome du programme pour les noms de
  fichiers).
- `_survey_ids_premier_mardi()` / `_survey_ids_vendredi_midi()` :
  classent maintenant les sondages selon le **jour de la semaine** de
  la date extraite du titre (mardi tombant dans les 7 premiers jours du
  mois ; vendredi, n'importe lequel), plutôt que par mots-clés absents
  du titre. Validé sur les dates réelles déjà connues du club (4 août,
  1er septembre, 7 avril 2026 : toutes correctement reconnues comme des
  mardis).
- Nouveau champ `output_format` (Sélection : « À l'écran, dans Odoo »,
  « Fichier HTML », « Fichier PDF »), affiché en radio-bouton dans les
  paramètres du rapport, à côté du choix du thème. Le bouton
  « Générer » (renommé, il ne dit plus « à l'écran » spécifiquement)
  déclenche directement le format choisi.
- `action_generate()` : ne se fie plus au rechargement implicite de la
  fiche après un bouton (comportement qui s'est avéré peu fiable sur
  cette instance - rien ne s'affichait malgré une génération réussie
  côté serveur, sans erreur). Retourne maintenant explicitement une
  action de rechargement (`ir.actions.act_window` sur ce même
  enregistrement), chaînée après une notification qui s'affiche
  **systématiquement** - succès (verte, discrète) ou avertissement
  (orange, persistante) - via le mécanisme standard `next` d'Odoo.

**Garde-fous et cas limites :**
- Si le titre d'un sondage ne contient aucune date reconnaissable,
  `_extraire_date_titre()` retourne `None` et ce sondage n'est classé
  dans aucune des catégories « Premier mardi »/« Vendredi midi » (il
  se retrouve dans « Tous les autres »).
- En format HTML ou PDF, le téléchargement se déclenche immédiatement
  au clic sur « Générer », sans passer par l'affichage à l'écran ; les
  boutons de téléchargement du pied de page restent disponibles
  séparément une fois un rapport affiché à l'écran.

**Vérifications effectuées :** logique d'extraction de date testée en
isolation (indépendante d'Odoo) sur des titres réalistes - toutes les
dates connues du club sont correctement reconnues et classées. Syntaxe
Python et XML validées. Le mécanisme de rechargement forcé et le
chaînage de notification (`next`) suivent un patron standard d'Odoo,
mais n'ont pas pu être vérifiés visuellement faute d'accès à une
instance.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`).
Après ouverture du wizard, vérifiez la présence du nouveau champ
« Format de sortie », puis testez chaque sous-menu de raccourci pour
confirmer que les bons sondages sont désormais présélectionnés.

---

## 18.0.1.6.0

**Titre court :** notification Odoo visible à l'écran en cas de
problème pendant la génération, en plus du bandeau dans le rapport et
des logs serveur.

**Motif de la demande :** les avertissements (questions ignorées,
sondages sans réponse) n'étaient visibles que dans les logs serveur ou
noyés dans un encadré discret en haut du rapport HTML - aucune
indication claire à l'écran qu'un problème était survenu.

**Détail des modifications :**
- `_compute_report()` retourne maintenant la liste des diagnostics
  (auparavant, la valeur de retour était ignorée).
- `action_generate()` : lorsque des diagnostics existent, une
  **notification Odoo native** (bandeau qui apparaît à l'écran, orange,
  persistant jusqu'à fermeture manuelle) résume le nombre de problèmes
  et en liste jusqu'à 8, en plus du rapport lui-même. Sans problème,
  comportement inchangé (rechargement silencieux de la fiche).
- L'encadré dans le rapport HTML lui-même est aussi rendu plus visible
  (bordure rouge plus épaisse, titre en gras coloré) et généralisé -
  il couvre maintenant aussi bien les sondages sans réponse que les
  questions individuellement ignorées, plutôt qu'un libellé qui ne
  mentionnait que le premier cas.

**Garde-fous et cas limites :**
- La notification liste au maximum 8 diagnostics avant de renvoyer au
  détail complet en haut du rapport, pour éviter une notification
  démesurément longue si de nombreuses questions échouent en même
  temps (comme dans le cas rapporté, où toutes échouaient à cause du
  même bug, corrigé en 1.5.0).

**Vérifications effectuées :** syntaxe Python validée. Le mécanisme de
notification (`ir.actions.client` / `display_notification`) est
l'approche standard d'Odoo pour ce type d'avertissement, utilisée dans
de nombreux modules du cœur d'Odoo - mais son comportement exact
combiné au rechargement de la fiche n'a pas pu être vérifié
visuellement faute d'accès à une instance.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`).
Si un problème survient à nouveau, un bandeau devrait apparaître
immédiatement à l'écran plutôt que de nécessiter une consultation des
logs pour le découvrir.

---

## 18.0.1.5.0

**Titre court :** correction d'un bug bloquant (cache invalide sur un
recordset Odoo), retrait des boutons dupliqués, sous-menus déplacés
sous « Rapport détaillé » dans le menu Sondage.

**Motif de la demande :** (1) deux boutons identiques « Générer le
rapport (à l'écran) » apparaissaient l'un au-dessus de l'autre ; (2) les
4 nouveaux sous-menus n'étaient pas visibles sous « Rapports RLQ »,
seul un nouveau menu « Rapport détaillé » apparaissait en haut ; (3) le
journal serveur montrait une erreur `AttributeError:
'rlq.survey.report.wizard' object has no attribute
'_lines_field_name_cache'` sur chaque question.

**Diagnostic (point 3, le plus important) :** la version précédente
tentait de mémoriser le résultat de la détection automatique du modèle
des réponses individuelles en écrivant
`self._lines_field_name_cache = ...` directement sur le recordset.
Contrairement à un objet Python ordinaire, les enregistrements Odoo
n'autorisent pas l'assignation d'attributs arbitraires de cette façon -
d'où l'échec systématique, sur **chaque question**, malgré une
détection elle-même réussie (l'erreur survenait au moment d'essayer de
la mettre en cache, pas de la calculer).

**Détail des modifications :**
- `_detecter_champ_et_modele_lignes()` (remplace l'ancien mécanisme de
  cache) : recalcule la détection à chaque appel plutôt que de tenter
  de la mémoriser sur `self` - le coût est négligeable (simple lecture
  des champs déjà en mémoire). `_lines_field_name()` et
  `_answer_model_name()` délèguent maintenant à cette fonction.
- Vue formulaire : retrait des boutons dupliqués dans le corps de la
  fiche, ajoutés par précaution dans une version précédente. Le pied de
  page (`<footer>`) suffit maintenant que la fiche s'ouvre correctement
  en fenêtre modale.
- Menus : les 5 entrées (sélection manuelle + les 4 raccourcis par
  catégorie) sont déplacées sous un nouveau menu conteneur
  « Rapport détaillé », lui-même sous le menu Sondage
  (`survey.menu_surveys`) - à l'endroit où l'utilisateur regardait déjà.
  Le menu racine indépendant « Rapports RLQ » conserve aussi ses 5
  entrées, en secours.

**Garde-fous et cas limites :**
- Le menu « Rapport détaillé » étant maintenant un simple conteneur
  (sans action propre), cliquer dessus directement n'ouvre rien : il
  faut choisir une de ses 5 entrées.

**Vérifications effectuées :** syntaxe Python et XML validées. Le
scénario précis rapporté par l'utilisateur (AttributeError sur
`_lines_field_name_cache`) est corrigé par construction : la nouvelle
version ne tente plus jamais d'assigner d'attribut sur `self`. Comme
toujours, la confirmation définitive attend un test sur l'instance
réelle.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`),
relancer la génération. Les questions qui échouaient uniquement à cause
de ce bug de cache devraient maintenant s'afficher correctement - si
une question échoue encore, ce sera pour une raison différente
(nom de champ réellement absent), visible dans le nouveau message
d'erreur qui l'accompagne.

---

## 18.0.1.4.0

**Titre court :** ajout de 4 sous-menus de sélection rapide des
sondages par catégorie, sous « Rapports RLQ ».

**Motif de la demande :** sélectionner manuellement les sondages à
chaque génération de rapport est lent lorsqu'on veut systématiquement
tous les sondages d'un même type. L'utilisateur a demandé 4 raccourcis :
« Premier mardi du mois », « Vendredi midi », le sondage annuel
(identifié par plus de 100 inscriptions un mois de septembre, toutes
années confondues), et « Tous les autres sondages ».

**Détail des modifications :**
- `_survey_ids_premier_mardi()` / `_survey_ids_vendredi_midi()` :
  recherchent les `survey.survey` dont le titre contient respectivement
  « premier mardi » ou « vendredi midi » (recherche insensible à la
  casse). **Hypothèse à valider** : ces mots doivent effectivement
  apparaître dans le titre des sondages correspondants sur votre
  instance.
- `_survey_ids_annuel()` : parcourt tous les sondages et retient ceux
  ayant reçu, une année donnée, plus de 100 réponses (`survey.user_input`)
  créées en septembre (`create_date.month == 9`) - le critère exact
  fourni par l'utilisateur, plutôt qu'une recherche par titre.
- `_survey_ids_autres()` : tous les sondages ne correspondant à aucune
  des trois catégories précédentes.
- `action_menu_premier_mardi()`, `action_menu_vendredi_midi()`,
  `action_menu_annuel()`, `action_menu_autres()` : calculent la
  catégorie correspondante et ouvrent le wizard avec `survey_ids` déjà
  rempli (`context: default_survey_ids`), prêt pour un clic sur
  « Générer ».
- 4 nouvelles actions serveur (`ir.actions.server`) et 4 nouveaux
  sous-menus sous « Rapports RLQ », à côté de l'entrée existante
  (renommée « Sélection manuelle des sondages » pour la distinguer des
  4 raccourcis).

**Garde-fous et cas limites :**
- Un sondage pourrait théoriquement correspondre à plusieurs critères à
  la fois (ex. un titre contenant à la fois « premier mardi » et ayant
  reçu plus de 100 réponses en septembre) : il apparaîtrait alors dans
  plusieurs catégories, `_survey_ids_autres()` l'excluant seulement de
  la catégorie « Tous les autres ». Pas de dé-doublonnage global entre
  catégories dans cette version.
- Le calcul du sondage annuel parcourt tous les `survey.user_input` de
  tous les sondages à chaque appel (pas de mise en cache) : sans impact
  perceptible pour le volume de données d'un club, mais à revoir si le
  nombre de sondages/réponses devenait très important.

**Vérifications effectuées :** syntaxe Python et XML validées. Comme
pour les versions précédentes, aucun test sur une instance Odoo réelle
n'a pu être effectué - la correspondance des sondages à chaque
catégorie doit être vérifiée visuellement après mise à jour.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`),
puis vérifier que chaque sous-menu sélectionne bien les sondages
attendus (ouvrir le wizard via chaque raccourci et regarder les
sondages déjà cochés dans le champ, avant même de cliquer sur
« Générer »). Si le classement est incorrect, dites-moi quel critère
utiliser à la place (mot-clé différent dans le titre, catégorie sur le
sondage, autre champ...).

---

## 18.0.1.3.0

**Titre court :** détection dynamique du modèle des réponses
individuelles (au lieu du nom supposé "survey.user_input_line"), et
tolérance aux erreurs par question plutôt que pour tout le rapport.

**Motif de la demande :** en cliquant sur « Générer », l'utilisateur a
obtenu l'erreur « La génération du rapport a échoué :
'survey.user_input_line' ». Le journal serveur a révélé la cause
exacte : `KeyError: 'survey.user_input_line'` - ce modèle n'existe
tout simplement pas sur son instance ERPLibre (Odoo 18).

**Diagnostic :** le module supposait que les réponses individuelles
(ligne par ligne) étaient stockées dans un modèle nommé
`survey.user_input_line`, référencé directement par son nom technique.
Cette hypothèse, bien que correspondant à la structure standard
d'Odoo CE, ne tient pas sur cette instance - probablement une
personnalisation ou un renommage propre à ERPLibre.

**Détail des modifications :**
- `_lines_field_name()` / `_answer_model_name()` / `_get_input_lines()`
  (nouvelles méthodes) : au lieu de référencer `survey.user_input_line`
  par son nom, le module inspecte maintenant les champs One2many réels
  de `survey.user_input` pour trouver dynamiquement celui qui mène aux
  réponses individuelles (en cherchant "line" dans le nom du champ,
  avec un repli sur tout champ One2many pointant vers un modèle
  "survey.*"). Le nom du modèle réel est déduit de ce champ plutôt que
  supposé.
- Si cette détection automatique échoue malgré tout, le message
  d'erreur liste désormais tous les champs One2many disponibles sur
  `survey.user_input`, pour identifier immédiatement le bon champ sans
  avoir à fouiller manuellement.
- `_traiter_question()` (nouvelle méthode, logique extraite de
  `_compute_report()`) : le traitement de chaque question est
  maintenant isolé et enveloppé dans son propre `try/except`. Une
  question dont un champ ne correspond pas à cette instance est
  désormais **ignorée individuellement** (avec un avertissement visible
  dans le rapport et le détail dans les logs), plutôt que de faire
  échouer la génération de tout le rapport.

**Garde-fous et cas limites :**
- La détection dynamique suppose qu'un seul champ One2many de
  `survey.user_input` contient "line" dans son nom ; si plusieurs
  correspondent, c'est arbitrairement le premier qui est retenu. En cas
  de résultat inattendu, le nom retenu peut être vérifié via le shell
  Odoo (voir NOTES_VALIDATION.md, section 0).
- Les questions ignorées individuellement apparaissent quand même dans
  le rapport, sous forme d'un message d'avertissement à leur
  emplacement, pour qu'aucune question ne disparaisse silencieusement.

**Vérifications effectuées :** syntaxe Python validée après la
restructuration du code (extraction de `_traiter_question`). Comme pour
les versions précédentes, aucun test sur une instance Odoo réelle n'a
pu être effectué directement par moi - seul le retour de l'utilisateur
sur staging permet de le confirmer.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`)
et relancer la génération. Si une erreur persiste, elle devrait
maintenant identifier précisément quel champ pose encore problème
(message affiché à l'écran + logs serveur) plutôt qu'un simple
`KeyError` sur un nom de modèle.

---

## 18.0.1.2.0

**Titre court :** correction de l'absence de bouton d'action (le
formulaire s'ouvrait en page complète plutôt qu'en fenêtre modale).

**Motif de la demande :** après avoir choisi un sondage, l'utilisateur
ne voyait aucun bouton pour lancer la génération - seulement un bouton
« Nouveau » et le nom technique de l'enregistrement
(« rlq.survey.report.wizard,1 ») dans le coin supérieur droit. Aucune
erreur serveur ne s'affichait.

**Diagnostic :** l'action `action_rlq_survey_report_wizard` utilisait
`target="current"` (page complète), qui affiche le chrome standard
d'une fiche Odoo classique (bouton Nouveau, pagination, nom technique
de l'enregistrement en l'absence de champ `name` sur ce modèle). Le
bloc `<footer>` contenant les boutons d'action est conçu par Odoo pour
s'afficher correctement uniquement lorsque la fiche s'ouvre en fenêtre
modale (`target="new"`), comme le fait tout assistant standard (import,
envoi de courriel, etc.). En page complète, ce chrome technique
masquait effectivement l'absence de bouton utilisable.

**Détail des modifications :**
- `action_rlq_survey_report_wizard` : `target` changé de `current` à
  `new` - la fiche s'ouvre maintenant en fenêtre modale, comme les
  autres assistants d'Odoo.
- Vue formulaire : un titre (« Rapport de sondage RLQ ») et les mêmes
  boutons que le pied de page sont désormais **aussi** présents dans le
  corps de la fiche, par mesure de robustesse - au cas où la fiche
  serait un jour rouverte en page complète (ex. lien direct, favori),
  l'action resterait accessible même sans le rendu spécial du pied de
  page modal.

**Garde-fous et cas limites :**
- Les boutons apparaissent maintenant deux fois dans le code de la vue
  (corps de fiche + pied de page) mais ne s'affichent jamais deux fois
  en même temps à l'écran : chacun est conditionné par le même champ
  `state`, et le pied de page seul est visible en mode modal (le rendu
  standard d'Odoo n'affiche pas le contenu du corps de fiche en double).

**Vérifications effectuées :** syntaxe XML validée. Comme précédemment,
aucun test sur une instance Odoo réelle n'a pu être effectué - à
confirmer visuellement en priorité lors de votre prochain essai.

**Action requise :** mettre à jour le module (`-u rlq_survey_report`)
puis rouvrir le menu « Rapport de sondage mensuel » ou « Rapport
détaillé » : il devrait maintenant s'ouvrir en fenêtre modale avec le
bouton « Générer le rapport (à l'écran) » visible immédiatement.

---

## 18.0.1.1.0

**Titre court :** correction de l'affichage vide après génération, ajout
du menu « Rapport détaillé » dans Sondage, trois sorties (écran/HTML/PDF).

**Motif de la demande :** après une première installation sans erreur,
aucun résultat ne s'affichait à l'écran après avoir choisi un sondage.
L'utilisateur a aussi demandé une entrée « Rapport détaillé » dans le
menu Sondage existant, et trois modes de sortie (HTML, PDF, écran).

**Détail des modifications :**
- `action_generate()` : au lieu de reconstruire et retourner une
  nouvelle action `ir.actions.act_window` (source probable du problème
  d'affichage), la méthode se contente maintenant d'écrire les champs
  et de retourner `True`, laissant le client Odoo recharger le
  formulaire déjà ouvert - le comportement standard et le plus fiable
  pour un bouton de type `object` sur un enregistrement déjà affiché.
- Diagnostic explicite : si aucune réponse ne correspond aux critères
  (statut, plage de dates, exclusions), le rapport affiche maintenant
  un message clair listant, pour chaque sondage sélectionné, le nombre
  total de réponses tous statuts confondus - au lieu d'un résultat vide
  sans explication.
- `action_generate()` capture désormais toute exception inattendue et
  la transforme en message d'erreur lisible (plutôt qu'une trace brute
  ou un échec silencieux), tout en consignant la trace complète dans
  les logs serveur (`_logger.exception`).
- Nouveau menu « Rapport détaillé » sous le menu Sondage existant
  (`survey.menu_surveys`), en plus du menu racine « Rapports RLQ » déjà
  présent.
- Nouvelles actions `action_download_html()` (fichier .html autonome
  via une pièce jointe temporaire) et `action_download_pdf()` (gabarit
  QWeb dédié, listes dépliables forcées ouvertes en impression), avec
  leurs boutons correspondants dans le formulaire.
- Nouveau fichier `views/report_templates.xml` (gabarit QWeb + action
  `ir.actions.report` pour le PDF).

**Garde-fous et cas limites :**
- Le menu imbriqué dans Sondage dépend de l'external ID
  `survey.menu_surveys`, non vérifié sur une instance réelle : voir
  NOTES_VALIDATION.md pour la procédure de repli si l'installation
  échoue sur cette entrée précise.
- Le rendu PDF (wkhtmltopdf) n'a pas pu être vérifié visuellement,
  faute d'accès à une instance Odoo.

**Vérifications effectuées :** syntaxe Python/XML de tous les fichiers
modifiés ; tests unitaires manuels de `report_builder.py` en isolation
(inchangé dans cette version, toujours fonctionnel). Aucun test dans un
Odoo réel n'a pu être effectué (voir avertissement du module).

**Action requise :** réinstaller/mettre à jour le module
(`-u rlq_survey_report`) sur l'instance de dev/staging, puis reprendre
la procédure de validation de NOTES_VALIDATION.md, en commençant par un
seul sondage récent avec au moins une réponse au statut Terminé.

---

## 18.0.1.0.0

Version initiale : assistant backend (menu « Rapports RLQ ») générant
un rapport HTML (synthèse toutes rencontres confondues + fiche par
participant) directement à partir de `survey.user_input` /
`survey.user_input_line`, sans export Excel. Voir le message de
livraison initial pour le détail complet.
