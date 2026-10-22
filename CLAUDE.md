# Instructions for Claude - rlq-admin-tools
 
(English translation of `CLAUDE.md`. The French file is the reference.)
 
## Pull requests
 
Create them and give the link; never merge or approve them - the user validates them.
 
## Tests: as few tokens as possible
 
- To run or check the tests, delegate to the **`testeur`** agent (`.claude/agents/testeur.md`: Claude Haiku 5.5, low effort). It runs
  `nginx-tools-tests/run-all.sh` (or only the named modules) and reports only the verdict, the failures and the statistics. Never re-read the
  full output of run-all.sh in the main conversation.
- Fixing a failure: in the main conversation; a simple, well-localized failure may be handed to Claude Sonnet 5.5, medium effort.
- Only one run of run-all.sh at a time on a machine (each run deletes the temporary `test-rlq-*` folders created while it runs).
- The user may also run run-all.sh themselves and paste only the `[ÉCHEC]` and `FAIL` lines.
## Conventions
 
Those of `doc/CONTEXTE.md` (section 3): version MAJOR.MINOR.YYYYMMDD.HHMMSS (local time), CHANGELOG.md lists the most recent entry first,
`--version`, `--changelog`, sorted options, configuration `/etc/default/<program>.conf` then `~/.<program>.conf`, archives `name.MAJOR.MINOR.zip`.
 
## Public repository: no personal data
 
Never a real name, email address, username or IP address of a person in the repository (code, tests, changelogs, docs). Examples: invented
names, `exemple.org`, documentation addresses (RFC 5737) or `11.x` blocks when a public address is needed.

