## User conventions (to be followed for every program)

### Language
- Program code (comments, program names, options, arguments, messages, CHANGELOG file) follows the language rules of the repository:
  see the note below.
- Everything visible to a user is multilingual, mainly French and English.
- No characters typical of language models in the documentation: no em dash, en dash, ellipsis character, curly quotes,
  arrow characters, check marks (ok/x symbols) or decorative symbols.
  Use `-`, `...`, `"`, `->`, `[OK]`, `[FAIL]`, `[ATTN]` instead. Accents and French guillemets are kept.

### Versions
- Format: `MAJOR.MINOR.YYYYMMDD.HHMMSS`, local date and time.
- MINOR +0.1 for EACH requested change, even a small one.
- MAJOR only when explicitly requested, or in case of a breaking compatibility change.
- `__version__` (or `SCRIPT_VERSION`) kept up to date; the `--version` option displays it dynamically, never a hard-coded string.

### Files and publication
- After each change, update the GitHub repository, then produce a `.zip` archive named without the date: `program.MAJOR.MINOR.zip`.
- CHANGELOG.md: most recent version FIRST. For each version: short title, reason for the request,
  details of the changes (functions, options, files), bugs fixed (symptom, diagnosis, fix), safeguards and edge cases,
  checks performed, action required from the user (or "none").
- `--changelog` option on every program: displays only the program's changes, read from CHANGELOG.md;
  version numbers in colour; colours disabled when the output is redirected; a closed pipe is handled cleanly.

### Configuration
- Read `/etc/default/program.conf`, then `~/.program.conf` if it exists; the last one read wins.
- Command-line options take priority.
- The program states which files were read, with a summary of one or two lines of the important options.
- The derived name (`program`) does not contain the version suffix.

### Options
- Always in English, sorted alphabetically in the help output.
- Options are displayed in colour.

## Pull requests

Create them and give the link. Never merge or approve them: the user validates them.

## Tests: as few tokens as possible

- To run or check the tests, delegate to the `testeur` agent (`.claude/agents/testeur.md`: Claude Haiku 5.5, effort low). It runs
  `nginx-tools-tests/run-all.sh` (or only the named modules) and reports only the verdict, the failures and the statistics. Never re-read the
  full output of run-all.sh in the main conversation.
- To fix a failure: do it in the main conversation. A simple, well-localized failure may be handed to Claude Sonnet 5.5, effort medium.
- Only one run of run-all.sh at a time on a given machine (each run deletes the `test-rlq-*` temporary folders created while it runs).
- The user may also run run-all.sh themselves and paste only the lines `[ÉCHEC]` and `FAIL`.
