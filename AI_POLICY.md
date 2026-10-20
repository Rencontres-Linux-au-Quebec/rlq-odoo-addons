# AI Policy / Politique sur l'IA

*[English](#english) · [Français](#français)*

---

## English

### The short version

- Using AI tools to help you is fine.
- Handing over responsibility to them is not.
- Every contribution comes from a human who understands it and answers for it, however it was produced.
- Any AI involvement means an `Assisted-by:` trailer. It is binary: either there was AI involvement or there was not, with no threshold to judge.
- AI tools never go in `Co-authored-by:`.
- Unsupervised agentic tools are not permitted.
- If you cannot explain and defend every line, do not submit it.
- During review, engage with the feedback. Regenerating and resubmitting is not an answer, and neither is "the AI wrote it".
- Do not post AI-generated review comments or summaries you have not fact-checked yourself.

*Inspired by the [OCA AI policy](https://odoo-community.org/).*

### 1. Purpose and scope

This document explains how artificial intelligence (AI) tools are used in the development of **this repository**, part of the Rencontres Linux au Québec projects, and sets the rules that apply to the maintainers and to every contributor. It covers source code, tests, documentation, changelogs, issues and pull requests.

### 2. How AI is used in this project

- Contributors may use AI assistants (currently Anthropic's Claude, including Claude Code) to draft code, tests, documentation and changelog entries.
- AI is a **drafting tool, not an author**. Every AI-assisted change is read, understood and accepted by a human before it is merged.
- **Unsupervised agentic tools are not permitted.** An AI agent may prepare a branch, a commit or a pull request only while a human watches the work and reviews each step before anything is pushed or merged. Instructions for supervised agents are kept in `CLAUDE.md`.
- No AI tool has direct access to the production servers.

### 3. Human responsibility

Whoever submits a change is fully responsible for it, whether it was written by hand or with AI help. Before submitting, you must be able to:

- explain what the change does and why, line by line if asked;
- show that it was tested (see section 5);
- confirm that it does not introduce code you are not allowed to distribute.

Disclosure is expected and welcome, but it does not reduce the contributor's responsibility one bit.

### 4. Disclosure: the `Assisted-by:` trailer

- Any AI involvement in a commit or a pull request is declared with one `Assisted-by:` trailer per model used, in the same shape as `Co-authored-by:`, at the end of the commit message, with **no blank line between the trailers**:

  ```
  Assisted-by: Claude Haiku 5.5 <noreply@anthropic.com>
  ```

- `Co-authored-by:` must **not** name an AI tool: the authorship of a work by a machine is legally undefined. AI tools are never listed there.
- Pull requests with substantial AI-generated content must also say so in the description, for example: `AI-assisted: Claude (code draft), reviewed and tested by <name>`.
- Trivial help (autocompletion, spelling, rephrasing a comment) is still an AI involvement under the rule above: when in doubt, declare it.

### 5. Quality and testing requirements

AI-assisted contributions meet exactly the same bar as any other:

- Shell scripts must pass `shellcheck` without unexplained warnings.
- Python code must run on the oldest version supported by the project.
- The test suite must pass, and changes must be tested on a **development** server (a DEV environment) before any use in production.
- The conventions in `README.md` and `CLAUDE.md` (when present) apply: English identifiers and options, bilingual (French/English) user messages, and the project's own rules for versions and changelogs.
- Invented options, APIs, file paths or configuration directives ("hallucinations") are treated as bugs and must be removed before merge.

### 6. Data protection and confidentiality

This repository is public. Never put the following into an AI tool, a commit, an issue or a pull request:

- passwords, API keys, tokens, private keys, Tailscale or other VPN secrets;
- the team IP list or any file from `/etc/default/*.conf`;
- raw logs (nginx, fail2ban, Odoo, BigBlueButton) containing real IP addresses, e-mail addresses, user names or other personal data;
- a real person's name, e-mail, user name or IP address (code, tests, changelogs, docs);
- private nginx configuration or internal host names.

When an example is needed, use invented names, `example.org` and documentation address ranges (RFC 5737, such as `192.0.2.0/24`).

### 7. Security

- Commands or configuration suggested by an AI are never run directly on a production server. They go through the same review and DEV testing as code.
- Security-sensitive changes (firewall rules, bans, fail2ban/CrowdSec actions, TLS, authentication) require an explicit human review that mentions the risk considered.
- Report suspected vulnerabilities privately through GitHub's *Report a vulnerability* button (Security tab), not in a public issue.

### 8. Copyright and licensing

- This project is licensed under the **GNU Affero General Public License, version 3 or (at your option) any later version** (AGPL-3.0-or-later). See `LICENSE`.
- Contributors must not submit AI output that reproduces third-party code under a license incompatible with the AGPL-3.0.
- By submitting a contribution you confirm you have the right to license it under the AGPL-3.0-or-later.
- Copyright © 2026 Services-Conseils Linux Inc. and the Rencontres Linux au Québec contributors.

### 9. Review and discussions

- During review, engage with the feedback yourself. Regenerating the change and resubmitting it without understanding the comment is not an acceptable answer.
- Do not post AI-generated review comments or summaries you have not fact-checked yourself.
- AI may help you write an issue, but the problem must be real and reproduced by you. Include the name and version of the affected program or module and, when available, the relevant output (anonymised as in section 6). Unverified, AI-generated bug reports may be closed without notice.

### 10. Changes to this policy

This policy may evolve with the tools and the law. Changes are recorded in the project history.

---

## Français

### L'essentiel

- Utiliser des outils d'IA pour vous aider, c'est acceptable.
- Leur confier la responsabilité, non.
- Chaque contribution vient d'une personne qui la comprend et en répond, quelle qu'ait été sa méthode de production.
- Toute participation de l'IA exige une ligne `Assisted-by:`. C'est binaire : il y a eu participation de l'IA ou non, sans seuil à juger.
- Les outils d'IA ne figurent jamais dans `Co-authored-by:`.
- Les outils agentiques non supervisés ne sont pas permis.
- Si vous ne pouvez pas expliquer et défendre chaque ligne, ne la soumettez pas.
- En révision, répondez vous-même aux commentaires. Régénérer et soumettre à nouveau ne suffit pas, et « c'est l'IA qui l'a écrit » non plus.
- Ne publiez pas de commentaires ou de résumés de révision générés par l'IA que vous n'avez pas vérifiés vous-même.

*Inspiré de la [politique IA de l'OCA](https://odoo-community.org/).*

### 1. Objet et portée

Ce document explique comment les outils d'intelligence artificielle (IA) sont utilisés dans le développement de **ce dépôt**, qui fait partie des projets Rencontres Linux au Québec, et fixe les règles qui s'appliquent aux responsables et à toute personne qui contribue. Il couvre le code source, les tests, la documentation, les journaux de modifications, les billets (issues) et les demandes d'intégration (pull requests).

### 2. Utilisation de l'IA dans le projet

- Les contributeurs peuvent utiliser des assistants d'IA (actuellement Claude d'Anthropic, y compris Claude Code) pour rédiger des ébauches de code, de tests, de documentation et d'entrées de journal de modifications.
- L'IA est un **outil de rédaction, pas un auteur**. Chaque modification assistée par l'IA est lue, comprise et acceptée par un humain avant d'être intégrée.
- **Les outils agentiques non supervisés ne sont pas permis.** Un agent d'IA ne peut préparer une branche, un commit ou une demande d'intégration que pendant qu'un humain suit le travail et révise chaque étape avant toute publication ou intégration. Les consignes pour les agents supervisés sont dans `CLAUDE.md`.
- Aucun outil d'IA n'a d'accès direct aux serveurs de production.

### 3. Responsabilité humaine

La personne qui soumet une modification en est entièrement responsable, qu'elle ait été écrite à la main ou avec l'aide de l'IA. Avant de soumettre, vous devez pouvoir :

- expliquer ce que fait la modification et pourquoi, ligne par ligne au besoin ;
- démontrer qu'elle a été testée (voir section 5) ;
- confirmer qu'elle n'introduit pas de code que vous n'avez pas le droit de distribuer.

La divulgation est attendue et bienvenue, mais elle ne réduit en rien la responsabilité de la personne qui contribue.

### 4. Divulgation : la ligne `Assisted-by:`

- Toute participation de l'IA à un commit ou à une demande d'intégration est déclarée par une ligne `Assisted-by:` par modèle utilisé, de même forme que `Co-authored-by:`, à la fin du message de commit, **sans ligne vide entre les mentions** :

  ```
  Assisted-by: Claude Haiku 5.5 <noreply@anthropic.com>
  ```

- `Co-authored-by:` ne doit **pas** nommer un outil d'IA : la paternité d'une œuvre par une machine est juridiquement indéfinie. Les outils d'IA n'y figurent jamais.
- Une demande d'intégration contenant une part importante de contenu généré par l'IA doit l'indiquer dans sa description, par exemple : `AI-assisted: Claude (ébauche du code), révisé et testé par <nom>`.
- L'aide mineure (autocomplétion, orthographe, reformulation d'un commentaire) reste une participation de l'IA au sens de la règle ci-dessus : en cas de doute, déclarez-la.

### 5. Exigences de qualité et de tests

Les contributions assistées par l'IA respectent exactement les mêmes exigences que les autres :

- Les scripts shell doivent passer `shellcheck` sans avertissement non justifié.
- Le code Python doit fonctionner avec la plus ancienne version prise en charge par le projet.
- La suite de tests doit réussir, et les modifications doivent être testées sur un serveur de **développement** (un environnement DEV) avant toute utilisation en production.
- Les conventions de `README.md` et de `CLAUDE.md` (si présent) s'appliquent : identifiants et options en anglais, messages bilingues (français/anglais), `--help` en ordre et les règles du projet pour les versions et les journaux de modifications.
- Les options, API, chemins de fichiers ou directives de configuration inventés (« hallucinations ») sont traités comme des bogues et doivent être retirés avant l'intégration.

### 6. Protection des données et confidentialité

Ce dépôt est public. Ne mettez jamais dans un outil d'IA, un commit, un billet ou une demande d'intégration :

- mots de passe, clés d'API, jetons, clés privées, secrets Tailscale ou d'un autre RPV ;
- la liste des adresses IP de l'équipe ou tout fichier `/etc/default/*.conf` ;
- des journaux bruts (nginx, fail2ban, Odoo, BigBlueButton) contenant de vraies adresses IP, adresses courriel, noms d'utilisateur ou autres renseignements personnels ;
- le vrai nom, courriel, nom d'utilisateur ou adresse IP d'une personne (code, tests, journaux de modifications, documentation) ;
- une configuration nginx privée ou des noms d'hôtes internes.

Pour un exemple, utilisez des noms inventés, `exemple.org` et des plages d'adresses de documentation (RFC 5737, comme `192.0.2.0/24`).

### 7. Sécurité

- Les commandes ou configurations suggérées par une IA ne sont jamais exécutées directement sur un serveur de production. Elles suivent la même révision et les mêmes tests en DEV que le code.
- Les modifications sensibles (règles de pare-feu, bannissements, actions fail2ban/CrowdSec, TLS, authentification) exigent une révision humaine explicite qui mentionne le risque évalué.
- Signalez toute vulnérabilité soupçonnée en privé avec le bouton *Report a vulnerability* de GitHub (onglet Security), et non dans un billet public.

### 8. Droit d'auteur et licences

- Ce projet est distribué sous la **licence publique générale GNU Affero, version 3 ou (à votre choix) toute version ultérieure** (AGPL-3.0-or-later). Voir `LICENSE`.
- Il est interdit de soumettre du contenu généré par l'IA qui reproduit du code tiers sous une licence incompatible avec l'AGPL-3.0.
- En soumettant une contribution, vous confirmez avoir le droit de la placer sous la licence AGPL-3.0-or-later.
- Droit d'auteur © 2026 Services-Conseils Linux Inc. et les contributeurs des Rencontres Linux au Québec.

### 9. Révision et discussions

- En révision, répondez vous-même aux commentaires. Régénérer la modification et la soumettre à nouveau sans comprendre le commentaire n'est pas une réponse acceptable.
- Ne publiez pas de commentaires ou de résumés de révision générés par l'IA que vous n'avez pas vérifiés vous-même.
- L'IA peut vous aider à rédiger un billet, mais le problème doit être réel et reproduit par vous. Indiquez le nom et la version du programme ou du module concerné et, si possible, la sortie pertinente (anonymisée comme à la section 6). Les rapports de bogue générés par l'IA et non vérifiés peuvent être fermés sans préavis.

### 10. Modifications de cette politique

Cette politique peut évoluer avec les outils et la loi. Les modifications sont consignées dans l'historique du projet.
