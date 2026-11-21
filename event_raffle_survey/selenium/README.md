# Selenium end-to-end tests — event_raffle_survey

`test_event_raffle_survey_selenium.py` drives the **Start a Raffle** wizard of
an event against a **running** Odoo instance, in Firefox. It is a standalone
script: Odoo's test runner does not run it.

## What it covers

1. **Hidden strategy** — an event user without the *Surveys: User* right is
   not offered *Survey filled only*, and the form view sent to them (read
   over XML-RPC as that user) holds no survey field.
2. **Survey fields** — the required questions appear once a survey is
   picked; their dialog offers that survey's questions only (no section) and
   no creation; the *Each / At least one* choice appears with the first
   question.
3. **Counts** — *Respondents Entering* and *Anonymous Among Them* follow the
   required questions and the match choice: 5 and 1 with no question, 1 and 0
   with *Each*, 4 and 1 with *At least one*.
4. **Start** — the raffle holds exactly the 4 people announced; the answer
   given through a contact and the one without a contact, giving the same
   address, make a single participant, linked to the contact.
5. **Another survey** — picking it empties the required questions.

The data comes from the external XML-RPC API, under names carrying a suffix
of their own, so runs can repeat on one database. Elements are found by
technical attributes, never by labels, so any interface language works. A
screenshot is saved at each step (see `--screenshot-dir`).

## Requirements

- `selenium` (in `.venv.erplibre`), Firefox and `geckodriver` (found on
  `PATH`, in Selenium's cache `~/.cache/selenium/geckodriver/`, or passed with
  `--geckodriver`).
- The `event_raffle_survey` module installed on the target database.

## Run

```bash
# 1. start Odoo with the module installed
./odoo_bin.sh db --drop --database test_event_raffle_survey
./run.sh -d test_event_raffle_survey --db-filter test_event_raffle_survey \
    --stop-after-init -i event_raffle_survey
./run.sh -d test_event_raffle_survey --db-filter test_event_raffle_survey \
    --http-port 8069 --workers 0 &

# 2. run the scenarios (headless)
.venv.erplibre/bin/python \
    odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_survey/selenium/test_event_raffle_survey_selenium.py \
    --url http://localhost:8069 --db test_event_raffle_survey --headless
```

Exit code `0` = every check passed, `1` = at least one failed (each check is
printed as `PASS` or `FAIL`).

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--url` | `http://localhost:8069` | Odoo base URL |
| `--db` | `test_event_raffle_survey` | Target database |
| `--login` / `--password` | `admin` / `admin` | An administrator: the account creates the test data and a test user over XML-RPC, then drives the wizard |
| `--headless` | off | Run Firefox without a window |
| `--firefox` | system default | Firefox binary |
| `--geckodriver` | auto | geckodriver path |
| `--window` | `1400,1000` | Browser window size |
| `--screenshot-dir` | `selenium/screenshots` | Where screenshots go |

## Note on the data

`survey.question.create` carries no API decorator in Odoo 18, so XML-RPC
cannot call it; the script creates the questions through the survey's
`question_and_page_ids` instead.
