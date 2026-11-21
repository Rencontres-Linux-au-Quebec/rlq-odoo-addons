# End-to-end Selenium scenario: sponsored raffle prizes

`e2e_raffle_sponsor_prize.py` plays the whole life of a sponsored raffle
prize in a real browser (Chrome, headless by default), against a
**running** Odoo 18 that has `event_raffle_prize_sponsor` installed (with
`event_raffle_prize_handover`, `event_raffle_prize_claim`,
`event_raffle_prize` and `event_raffle` under it). `e2e_lib.py` holds what
a scenario shares: guards, XML-RPC, browser, steps, evidence. The browser
comes from `script/selenium/selenium_lib.py` of the ERPLibre checkout
around this repository (or the one `ERPLIBRE_ROOT` names).

These scripts are not Odoo tests: the module test suites do not run them.

## Run

```bash
# A scratch database, neutralized, served alone by its server.
./odoo_bin.sh db create ewp_sel_demo
./run.sh -d ewp_sel_demo --db-filter '^ewp_sel_demo$' --stop-after-init \
    -i event_raffle_prize_sponsor,website_sale_collect,payment_demo
./odoo_bin.sh neutralize -d ewp_sel_demo
./run.sh -d ewp_sel_demo --db-filter '^ewp_sel_demo$' \
    --http-port 8471 --gevent-port 8472 &

.venv.erplibre/bin/python \
    odoo18.0/addons/ERPLibre_erplibre_addons/selenium/e2e_raffle_sponsor_prize.py \
    --url http://127.0.0.1:8471 --db ewp_sel_demo \
    --evidence-dir /tmp/raffle_e2e --video
```

Options: `--no-headless` shows the window, `--video` writes
`video.webm` (needs `ffmpeg`), `--timeout` sets the seconds each wait
allows (30), `--window-size` the window (1400,1000), `--admin-login` the
organizer (`admin`). `--help` lists them all.

The checks read the texts from the records (names, token categories, the
raffle's message template), never a translation: the scenario runs in the
language of the organizer, English or French alike.

## Steps

| # | Step | How | What it does and checks |
| --- | --- | --- | --- |
| 1 | setup | setup | Portal accounts of a sponsor contact (under a sponsor company) and of 4 attendees, a Discuss channel, the value ranges of token categories A, B, C when still [0, 0], the sponsored shop opened if closed |
| 2 | event | UI + setup | The organizer creates the event (**Manage with sponsors**, sponsorship manager, **Publish the winners page**) and the sponsor's registration (**Is a sponsor**) from the Attendees button. Setup: the 4 attendees' registrations, checked in |
| 3 | portal | UI | The sponsor signs in, opens **Prizes for raffle** from `/my` and submits 6 physical prizes, 2 per category A, B, C, at different values; each is Submitted, archived, in its category |
| 4 | raffle | UI | The organizer starts the raffle from the event (present attendees), and in its Settings: spin of 2 s and 1 turn, no fireworks, **Notify the Winner Automatically** and **Announce each draw in a discussion channel** on, the channel chosen, the default messages kept |
| 5 | approve | UI + setup | The organizer approves the 6 prizes in **Sponsored Prizes to Review**; each becomes approved, active, published, in the Sponsored category. Setup: 3 units of each in stock (the product's quantity wizard). UI, signed out: the Sponsored category of `/shop` lists the 6 prizes with "3 left" |
| 6 | draws | UI | The organizer draws on the wheel with the category set to A, then B, then C: 3 different winners, each draw in its category |
| 7 | discuss | UI | The channel in Discuss shows exactly one message per draw, written by OdooBot, equal to the raffle's channel template rendered for that draw (number, winner, category, prize link), the link as an anchor. RPC: the channel holds exactly one post per draw, all by OdooBot; each winner was notified and each link is open |
| 8-10 | claim_A, claim_B, claim_C | UI | Each winner signs in (A and C open the prize link signed out and sign in through it; B signs in and goes to `/shop`), sees the banner with the token and only the prizes of their category, "3 left" on the chosen one, takes the second A, the first B, the second C prize, and checks out with the token; the draw's claim is reserved with that prize |
| 11 | results | UI | Signed out, the Sponsored category shows "2 left" for the 3 prizes taken and "3 left" for the others; `/raffle/winners/<event>` shows each winner with the chosen prize |

## What it leaves on the database

Every name carries a suffix unique to the run (`<monthdayhourminsec><hex>`),
so a second run on the same database never meets the first: 5 portal users
(`*.<suffix>@example.com`, random passwords kept in memory only), the
sponsor company and its contact, a Discuss channel, an event with 5 registrations, a
raffle with 3 draws, 6 approved prizes with their stock, and 3 confirmed
prize orders. The run also changes shared configuration when it has to,
and the setup step's line names each change:

- the ranges of token categories A (100 to 1000), B (25 to 99.99) and C
  (0.01 to 24.99), when they are still [0, 0];
- an archived token category A, B or C is **made active again**, and its
  prizes become claimable by the winners of that category;
- the sponsored shop is opened, and its closing date cleared.

Nothing is deleted. Each draw queues emails to the winner (prize link,
notification), and the event may queue its registration emails: a
neutralized database does not send them.

## Guards

- `--url` and `--db` are required, with no default.
- The server must run Odoo 18 and list `--db` only (start it with
  `--db-filter '^<db>$'`): the anonymous pages, which carry no database,
  are then served by that database. The browser session is checked to be
  on `--db` after each sign-in.
- The database must be neutralized (`database.is_neutralized`, set by
  `odoo-bin neutralize`). `--allow-non-neutralized-database` runs anyway:
  **dangerous**, the scenario then writes into a database that may be in
  production and its emails may leave.
- The organizer's password comes from `RAFFLE_E2E_ADMIN_PASSWORD`, else
  `admin`, the password of a scratch database. No password is printed,
  logged nor saved.
- The scripts never create nor drop a database.

## Exit code and evidence

`0` every step passes, `1` a step fails, `2` the tool fails (server,
browser, RPC, an unexpected exception, an interruption) or a guard
refuses. The `RESULT:` line and `summary.json` always give the same code
as the process. Each step prints `[STEP]` then `[PASS]`, `[FAIL]` or
`[ERROR]` with its duration and what it checked; a last `RESULT:` line
gives the verdict.

The evidence folder (`--evidence-dir`, default
`./raffle_e2e_<date>_<time>`) holds `run.log`, one screenshot per step
(`NN_<step>.png`, plus a few within steps), for a failed step its
screenshot and its page (`NN_<step>_FAILED.png` and `.html`),
`summary.json` (steps, durations, ids of the records created) and, with
`--video`, `video.webm`.

## Builds on it

`odoo18.0/addons/addons/selenium/e2e_webapp_raffle_prize.py` (event day
web app) imports this scenario and inserts its own steps.
