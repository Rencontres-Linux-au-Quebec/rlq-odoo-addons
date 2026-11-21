# Changelog: e2e_webapp_raffle_prize.py

### 1.1.20261121.015248 - Base scenario read from the same folder

- Reason: the sponsored prize scenario (`e2e_raffle_sponsor_prize.py`,
  `e2e_lib.py`) moved into this folder with the raffle modules; the
  default looked for it in another repository.
- Details: `default_raffle_dir()` returns the folder of this program;
  `--raffle-e2e-dir` and `RAFFLE_E2E_DIR` still name another. Help text,
  module docstring and both READMEs updated; the base scenario's README
  is `README.raffle_sponsor_prize.md`.
- Bugs fixed: none.
- Safeguards: unchanged.
- Checks: on a fresh neutralized database, 14 of 14 steps passing with
  the base scenario found in this folder.
- Action required: none, unless a run relied on the old default folder.

### 1.0.20261120.115121 - Scenario folder only from the command line

- Reason: `raffle-e2e-dir` in a configuration file was accepted and
  logged as read, but the scenario was already imported from another
  folder.
- Details: a configuration file can no longer set `raffle-e2e-dir`; the
  option or `RAFFLE_E2E_DIR` sets it.
- Bugs fixed: a configuration value ignored while the log named it.
- Safeguards: unchanged; the base scenario now reports any error outside
  a step as a tool error (exit 2), never as a pass.
- Checks: two runs in a row on a new scratch database, every step
  passing.
- Action required: move a `raffle-e2e-dir` line of a configuration file
  to the command line or to `RAFFLE_E2E_DIR`.

### 1.0.20261120.112606 - First version

- Reason: an end-to-end Selenium check of the raffle prizes in the event
  day web app, after the sponsored prize scenario of
  ERPLibre_erplibre_addons.
- Details: `e2e_webapp_raffle_prize.py` imports
  `e2e_raffle_sponsor_prize.py` (option `--raffle-e2e-dir`, variable
  `RAFFLE_E2E_DIR`) and inserts the steps `webapp_day` (setup: an open
  event day with the event and the raffle), `webapp_drawn` (raffle block
  with "prize to choose", "My prize" card with the winner's prize link, no
  card for the attendee who won nothing) and `webapp_claimed` (raffle
  block with the chosen prizes, card with the reserved prize). Options
  `--version`, `--changelog`; configuration files
  `/etc/default/e2e_webapp_raffle_prize.conf` and
  `~/.e2e_webapp_raffle_prize.conf`.
- Bugs fixed: none.
- Safeguards: the base scenario's guards (Odoo 18 server that lists
  `--db` only, neutralized database unless
  `--allow-non-neutralized-database`, passwords from the environment
  only, no database created nor dropped); a configuration file cannot set
  `url`, `db` nor `allow-non-neutralized-database`.
- Checks: three runs in a row on one scratch database, then one run on a
  new scratch database, every step passing.
- Action required: none.
