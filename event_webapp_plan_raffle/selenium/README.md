# End-to-end Selenium scenario: raffle prizes in the event day web app

*[English](#english) · [Français](#français)*

## English

`e2e_webapp_raffle_prize.py` checks, in a real browser (Chrome, headless by
default), that the raffle prizes reach the web app of
`event_webapp_plan_raffle` (`/webapp_event/<day>`). It plays the sponsored
prize scenario of `event_raffle_prize_sponsor`
(`selenium/e2e_raffle_sponsor_prize.py`, see
[its README](../../event_raffle_prize_sponsor/selenium/README.md): sponsor portal,
event, raffle, approval, draws, Discuss, token checkout, winners page) and
inserts three steps:

| Step | How | What it does and checks |
| --- | --- | --- |
| webapp_day (after the raffle) | setup | An event day of the web app, open from one hour ago to eight hours ahead, listing the event and the raffle |
| webapp_drawn (after the Discuss check) | UI | The first winner signs in on the home page: the raffle block lists the 3 winners, each with the token category and "prize to choose" (`data-ewp-prize-status="to_choose"`); the **My prize** card (*Mon prix*) holds the draw, open, and its **Choose my prize** button is that winner's prize link. The attendee who won nothing has no card |
| webapp_claimed (after the results) | UI | Once the winners took their prizes: the raffle block gives each chosen prize (`chosen`), and the first winner's card shows the prize reserved, without the button |

The checks read the texts from the records, never a translation: the
scenario runs in the language of the organizer, English or French.

### Run

Same server and database as the base scenario, with
`event_webapp_plan_raffle` installed too (and `event_webapp_plan_track`
or `rlq_event_webapp_plan` if the day should look as on site):

```bash
.venv.erplibre/bin/python odoo18.0/addons/addons/event_webapp_plan_raffle/selenium/e2e_webapp_raffle_prize.py \
    --url http://127.0.0.1:8471 --db ewp_sel_demo \
    --evidence-dir /tmp/webapp_e2e --video
```

- `--raffle-e2e-dir` (or `RAFFLE_E2E_DIR`) names the folder of
  `e2e_raffle_sponsor_prize.py`; by default, the `selenium` folder of
  `event_raffle_prize_sponsor`.
- `--version`, `--changelog` (this program's changes, `CHANGELOG.md`).
- Configuration: `/etc/default/e2e_webapp_raffle_prize.conf`, then
  `~/.e2e_webapp_raffle_prize.conf`, `option = value` lines (the last
  read wins, the command line wins over both). They cannot set `url`,
  `db` nor `allow-non-neutralized-database`: the target is given on the
  command line every time. Nor `raffle-e2e-dir`, which is read before
  them: the option or `RAFFLE_E2E_DIR` sets it. The run log says which
  files were read.
- Every other option is the base scenario's: `--help`.

### Guards, records, exit code

The base scenario's: `--url` and `--db` required, a server that lists
`--db` only, a neutralized database (unless the dangerous
`--allow-non-neutralized-database`), passwords from the environment only
(`RAFFLE_E2E_ADMIN_PASSWORD`, else `admin` for a scratch database), no
database created nor dropped. The run adds one event day (`event.webapp`)
to what the base scenario leaves, named with the same unique suffix.
Exit code: `0` every step passes, `1` a step fails (screenshot and page
in the evidence folder), `2` the tool fails or a guard refuses.

## Français

`e2e_webapp_raffle_prize.py` vérifie, dans un vrai navigateur (Chrome, sans
fenêtre par défaut), que les prix de tirage arrivent dans l'app web de
`event_webapp_plan_raffle` (`/webapp_event/<journée>`). Il joue le
scénario des prix commandités de `event_raffle_prize_sponsor`
(`selenium/e2e_raffle_sponsor_prize.py`, voir
[son README](../../event_raffle_prize_sponsor/selenium/README.md) : portail du commanditaire,
événement, tirage, approbation, tirs, Discussion, achat au jeton, page des
gagnants) et y insère trois étapes :

| Étape | Comment | Ce qu'elle fait et vérifie |
| --- | --- | --- |
| webapp_day (après le tirage) | préparation | Une journée de l'app web, ouverte d'une heure avant à huit heures après, qui liste l'événement et le tirage |
| webapp_drawn (après Discussion) | interface | Le premier gagnant se connecte à l'accueil : le bloc des tirages liste les 3 gagnants avec leur catégorie de jeton et « prix à choisir » ; la carte **Mon prix** porte le tir, ouvert, et son bouton **Choisir mon prix** est le lien de prix de ce gagnant. Le participant qui n'a rien gagné n'a pas de carte |
| webapp_claimed (après les résultats) | interface | Une fois les prix pris : le bloc donne chaque prix choisi, et la carte du premier gagnant montre le prix réservé, sans le bouton |

Les vérifications lisent les textes dans les enregistrements, jamais une
traduction : le scénario tourne dans la langue de l'organisateur, en
français comme en anglais.

Lancement, options, configuration, garde-fous et codes de sortie : voir
la partie anglaise ci-dessus, et
[le README du scénario de base](../../event_raffle_prize_sponsor/selenium/README.md).
