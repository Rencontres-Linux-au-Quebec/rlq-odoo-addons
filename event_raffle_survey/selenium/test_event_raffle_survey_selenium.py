#!/usr/bin/env python3
# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""End-to-end Selenium scenarios for the ``event_raffle_survey`` module.

Runs against a *live* Odoo instance where the module is installed. The data
is created through the external XML-RPC API, under names carrying a suffix
of their own, so that runs can repeat on one database. The web UI is then
driven through the "Start a Raffle" wizard of an event:

1. an event user without the Surveys: User right is not offered the survey
   strategy;
2. the survey fields appear in their order, the question dialog offers the
   chosen survey's questions only and creates none, and the counts follow
   the required questions and the Each / At least one choice;
3. Start creates exactly the participants the counts announced;
4. picking another survey empties the required questions.

Elements are found by technical attributes, never by their labels, so the
scenarios run in any interface language. Firefox drives the browser.
Screenshots are written to ``--screenshot-dir``.

Example::

    ./run.sh -d test_event_raffle_survey --db-filter test_event_raffle_survey \\
        --http-port 8069 --workers 0 &
    .venv.erplibre/bin/python \\
        odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle_survey/selenium/\\
test_event_raffle_survey_selenium.py \\
        --url http://localhost:8069 --db test_event_raffle_survey --headless
"""
import argparse
import glob
import os
import shutil
import sys
import time
import xmlrpc.client

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

DIALOG = ".o_dialog"
QUESTION_TITLES = ["Distribution?", "Desktop?", "Editor?"]


class Rpc:
    def __init__(self, url, db, login, password):
        self.db = db
        self.password = password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(db, login, password, {})
        if not self.uid:
            raise RuntimeError("XML-RPC authentication failed")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def exe(self, model, method, *params, **kw):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, list(params), kw
        )

    def xmlid(self, module, name):
        rows = self.exe(
            "ir.model.data",
            "search_read",
            [("module", "=", module), ("name", "=", name)],
            fields=["res_id"],
        )
        return rows[0]["res_id"]


def setup_data(rpc, suffix):
    """Create an event, a survey of three questions and its answers.

    Without required questions five people enter, one of them anonymous:
    Ann answers once through her contact and once without it, giving her
    address, which makes one person. With "Distribution?" and "Desktop?"
    required, Each keeps Ann alone; At least one keeps Ann, First, Second
    and the anonymous respondent.
    """
    event_id = rpc.exe(
        "event.event",
        "create",
        [
            {
                "name": f"Selenium survey raffle {suffix}",
                "date_begin": "2026-08-01 09:00:00",
                "date_end": "2026-08-01 18:00:00",
            }
        ],
    )[0]
    survey_title = f"Selenium survey {suffix}"
    other_title = f"Selenium other survey {suffix}"
    # survey.question.create carries no api decorator in Odoo 18, so XML-RPC
    # cannot call it: the questions come in through the survey's one2many.
    pages_and_questions = [
        (0, 0, {"title": "Section", "is_page": True, "sequence": 1})
    ] + [
        (
            0,
            0,
            {"title": title, "question_type": "char_box", "sequence": 2 + i},
        )
        for i, title in enumerate(QUESTION_TITLES)
    ]
    survey_id, _other_id = rpc.exe(
        "survey.survey",
        "create",
        [
            {
                "title": survey_title,
                "question_and_page_ids": pages_and_questions,
            },
            {"title": other_title},
        ],
    )
    by_title = {
        q["title"]: q["id"]
        for q in rpc.exe(
            "survey.question",
            "search_read",
            [("survey_id", "=", survey_id), ("is_page", "=", False)],
            fields=["title"],
        )
    }
    q1, q2, q3 = (by_title[title] for title in QUESTION_TITLES)
    ann = rpc.exe(
        "res.partner",
        "create",
        [{"name": f"Ann {suffix}", "email": f"ann.{suffix}@example.com"}],
    )[0]

    def answer(answered=(), skipped=(), state="done", **vals):
        answer_id = rpc.exe(
            "survey.user_input",
            "create",
            [dict(vals, survey_id=survey_id, state=state)],
        )[0]
        lines = [
            {
                "user_input_id": answer_id,
                "question_id": q,
                "answer_type": "char_box",
                "value_char_box": "Debian",
            }
            for q in answered
        ] + [
            {"user_input_id": answer_id, "question_id": q, "skipped": True}
            for q in skipped
        ]
        rpc.exe("survey.user_input.line", "create", lines)

    answer((q1, q2), partner_id=ann, email=f"ann.{suffix}@example.com")
    answer((q1,), email=f"ANN.{suffix}@example.com")
    answer((q1,), (q2,), nickname="First")
    answer((q2,), nickname="Second")
    answer((q3,), (q1, q2), nickname="Third")
    answer((q1,))
    answer((q1, q2), nickname="Unfinished", state="in_progress")

    event_user = f"raffle_selenium_{suffix}"
    rpc.exe(
        "res.users",
        "create",
        [
            {
                "name": f"Event user {suffix}",
                "login": event_user,
                "password": event_user,
                "groups_id": [
                    (6, 0, [rpc.xmlid("event", "group_event_user")])
                ],
            }
        ],
    )
    return {
        "event_id": event_id,
        "survey_title": survey_title,
        "other_title": other_title,
        "ann": ann,
        "event_user": event_user,
    }


class SurveyRaffleUi:
    def __init__(self, driver, url, db, screenshot_dir):
        self.d = driver
        self.url = url
        self.db = db
        self.shot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)
        self.wait = WebDriverWait(driver, 30)
        # Counts disappear when they reach zero, which can stale an element
        # between finding it and reading it.
        self.count_wait = WebDriverWait(
            driver, 30, ignored_exceptions=(StaleElementReferenceException,)
        )

    shots_taken = 0  # shared by the browser sessions of a run

    def shot(self, name):
        SurveyRaffleUi.shots_taken += 1
        number = SurveyRaffleUi.shots_taken
        path = os.path.join(self.shot_dir, f"{number:02d}_{name}.png")
        self.d.save_screenshot(path)
        print(f"  screenshot -> {path}")

    def present(self, css):
        return bool(self.d.find_elements(By.CSS_SELECTOR, css))

    def login(self, login, password):
        self.d.get(f"{self.url}/web/login?db={self.db}")
        field = self.wait.until(
            EC.visibility_of_element_located((By.NAME, "login"))
        )
        field.send_keys(login)
        self.d.find_element(By.NAME, "password").send_keys(password)
        self.d.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        self.wait.until(lambda d: "/odoo" in d.current_url)

    def open_wizard(self, event_id):
        self.d.get(
            f"{self.url}/odoo/action-event.action_event_view/{event_id}"
        )
        self.wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[name='action_start_raffle']")
            )
        ).click()
        self.wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"{DIALOG} div[name='copy_strategy'] select")
            )
        )

    def strategy_values(self):
        select = self.d.find_element(
            By.CSS_SELECTOR, f"{DIALOG} div[name='copy_strategy'] select"
        )
        return [o.get_attribute("value") for o in Select(select).options]

    def choose_survey_strategy(self):
        select = self.d.find_element(
            By.CSS_SELECTOR, f"{DIALOG} div[name='copy_strategy'] select"
        )
        value = next(v for v in self.strategy_values() if "survey_only" in v)
        Select(select).select_by_value(value)
        self.wait.until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, f"{DIALOG} div[name='survey_id'] input")
            )
        )

    def pick_survey(self, title):
        field = self.d.find_element(
            By.CSS_SELECTOR, f"{DIALOG} div[name='survey_id'] input"
        )
        field.click()
        field.send_keys(Keys.CONTROL, "a")
        field.send_keys(Keys.BACKSPACE)
        field.send_keys(title)
        self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//ul[contains(@class,'o-autocomplete--dropdown-menu')]"
                    f"//a[normalize-space()='{title}']",
                )
            )
        ).click()
        self.wait.until(lambda d: field.get_attribute("value") == title)

    def question_rows(self):
        return self.d.find_elements(
            By.CSS_SELECTOR,
            f"{DIALOG} div[name='survey_question_ids'] .o_data_row",
        )

    def add_questions(self, titles):
        """Add questions through the selection dialog; return the titles it
        offered and whether it offered to create one."""
        self.d.find_element(
            By.CSS_SELECTOR,
            f"{DIALOG} div[name='survey_question_ids']"
            " .o_field_x2many_list_row_add a",
        ).click()
        self.wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, DIALOG)) >= 2
        )
        dialog = self.d.find_elements(By.CSS_SELECTOR, DIALOG)[-1]
        self.wait.until(
            lambda d: dialog.find_elements(By.CSS_SELECTOR, ".o_data_row")
        )
        rows = dialog.find_elements(By.CSS_SELECTOR, ".o_data_row")
        offered = [
            r.find_element(By.CSS_SELECTOR, "td[name='title']").text
            for r in rows
        ]
        can_create = bool(
            dialog.find_elements(By.CSS_SELECTOR, ".o_create_button")
        )
        self.shot("question_dialog")
        for row, title in zip(rows, offered):
            if title in titles:
                row.find_element(
                    By.CSS_SELECTOR, ".o_list_record_selector input"
                ).click()
        dialog.find_element(By.CSS_SELECTOR, ".o_select_button").click()
        self.wait.until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, DIALOG)) == 1
        )
        self.wait.until(lambda d: len(self.question_rows()) == len(titles))
        return offered, can_create

    def choose_match(self, value):
        self.d.find_element(
            By.CSS_SELECTOR,
            f"{DIALOG} div[name='survey_question_match']"
            f" input[data-value='{value}']",
        ).click()

    def count(self, field):
        css = f"{DIALOG} div[name='{field}']"
        if not self.present(css):
            return None
        return int(self.d.find_element(By.CSS_SELECTOR, css).text.strip())

    def wait_counts(self, respondents, anonymous):
        self.count_wait.until(
            lambda d: (
                self.count("survey_respondent_count"),
                self.count("survey_anonymous_count") or 0,
            )
            == (respondents, anonymous)
        )

    def start(self, rpc, event_id):
        before = set(
            rpc.exe("event.raffle", "search", [("event_id", "=", event_id)])
        )
        self.d.find_element(
            By.CSS_SELECTOR, f"{DIALOG} button[name='action_start']"
        ).click()
        self.wait.until(
            lambda d: set(
                rpc.exe(
                    "event.raffle", "search", [("event_id", "=", event_id)]
                )
            )
            - before
        )
        raffle_id = max(
            set(
                rpc.exe(
                    "event.raffle", "search", [("event_id", "=", event_id)]
                )
            )
            - before
        )
        self.wait.until(
            lambda d: self.present("div[name='participant_ids'] .o_data_row")
        )
        return rpc.exe(
            "event.raffle.participant",
            "search_read",
            [("raffle_id", "=", raffle_id)],
            fields=["name", "email", "partner_id"],
        )


def find_geckodriver(explicit):
    if explicit:
        return explicit
    on_path = shutil.which("geckodriver")
    if on_path:
        return on_path
    cached = sorted(
        glob.glob(
            os.path.expanduser("~/.cache/selenium/geckodriver/*/*/geckodriver")
        )
    )
    return cached[-1] if cached else None


def build_driver(args):
    opts = Options()
    if args.headless:
        opts.add_argument("-headless")
    if args.firefox:
        opts.binary_location = args.firefox
    driver_path = find_geckodriver(args.geckodriver)
    service = (
        Service(executable_path=driver_path) if driver_path else Service()
    )
    driver = webdriver.Firefox(service=service, options=opts)
    width, height = (int(v) for v in args.window.split(","))
    driver.set_window_size(width, height)
    return driver


def run(args):
    rpc = Rpc(args.url, args.db, args.login, args.password)
    suffix = str(int(time.time()))
    data = setup_data(rpc, suffix)
    results = []

    def check(label, ok, detail=""):
        results.append((label, ok))
        print(
            ("PASS " if ok else "FAIL ")
            + label
            + (f" -- {detail}" if detail else "")
        )

    # Each user gets a browser of their own: logging out and in again in the
    # same one races the web client's service worker for the session cookie.
    driver = build_driver(args)
    ui = SurveyRaffleUi(driver, args.url, args.db, args.screenshot_dir)
    try:
        print("[1] event user without survey rights")
        ui.login(data["event_user"], data["event_user"])
        ui.open_wizard(data["event_id"])
        values = ui.strategy_values()
        check(
            "survey strategy not offered",
            not any("survey_only" in v for v in values),
            str(values),
        )
        ui.shot("event_user_wizard")
        # The form hides the survey field until the survey strategy is picked,
        # which this user cannot do: the view sent to them tells the truth.
        event_rpc = Rpc(
            args.url, args.db, data["event_user"], data["event_user"]
        )
        views = event_rpc.exe(
            "event.raffle.start.wizard", "get_views", [[False, "form"]]
        )
        check(
            "survey fields left out of the form sent to them",
            'name="survey_id"' not in views["views"]["form"]["arch"],
        )
    except Exception as exc:
        check("scenario 1 ran to the end", False, repr(exc))
        ui.shot("failure")
    finally:
        driver.quit()

    driver = build_driver(args)
    ui = SurveyRaffleUi(driver, args.url, args.db, args.screenshot_dir)
    try:
        print("[2] survey fields, dialog and counts")
        ui.login(args.login, args.password)
        ui.open_wizard(data["event_id"])
        ui.choose_survey_strategy()
        check(
            "questions hidden until a survey is picked",
            not ui.present(f"{DIALOG} div[name='survey_question_ids']"),
        )
        ui.pick_survey(data["survey_title"])
        ui.wait.until(
            lambda d: ui.present(f"{DIALOG} div[name='survey_question_ids']")
        )
        ui.wait_counts(5, 1)
        check("counts without required questions: 5, 1 anonymous", True)
        check(
            "match choice hidden while no question is required",
            not ui.present(f"{DIALOG} div[name='survey_question_match']"),
        )
        ui.shot("survey_picked")
        offered, can_create = ui.add_questions(QUESTION_TITLES[:2])
        check(
            "dialog offers the survey's questions only, no section",
            sorted(offered) == sorted(QUESTION_TITLES),
            str(offered),
        )
        check("dialog offers no creation", not can_create)
        ui.wait_counts(1, 0)
        check("counts with Each: 1, no anonymous", True)
        ui.choose_match("any")
        ui.wait_counts(4, 1)
        check("counts with At least one: 4, 1 anonymous", True)
        ui.shot("at_least_one")

        print("[3] Start creates what the counts announced")
        participants = ui.start(rpc, data["event_id"])
        check(
            "4 participants",
            len(participants) == 4,
            str([p["name"] for p in participants]),
        )
        check(
            "Ann enters once, through her contact",
            [p["partner_id"][0] for p in participants if p["partner_id"]]
            == [data["ann"]],
        )
        others = sorted(p["name"] for p in participants if not p["partner_id"])
        check(
            "First, Second and one anonymous guest",
            len(others) == 3 and {"First", "Second"} <= set(others),
            str(others),
        )
        ui.shot("raffle")

        print("[4] another survey empties the required questions")
        ui.open_wizard(data["event_id"])
        ui.choose_survey_strategy()
        ui.pick_survey(data["survey_title"])
        ui.wait.until(
            lambda d: ui.present(f"{DIALOG} div[name='survey_question_ids']")
        )
        ui.add_questions(QUESTION_TITLES[:1])
        ui.pick_survey(data["other_title"])
        ui.wait.until(lambda d: not ui.question_rows())
        check("list emptied", not ui.question_rows())
        check(
            "match choice hidden again",
            not ui.present(f"{DIALOG} div[name='survey_question_match']"),
        )
        ui.shot("other_survey")
    except Exception as exc:
        check("scenario ran to the end", False, repr(exc))
        ui.shot("failure")
    finally:
        driver.quit()
    failed = [label for label, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", default="http://localhost:8069")
    p.add_argument("--db", default="test_event_raffle_survey")
    p.add_argument("--login", default="admin")
    p.add_argument("--password", default="admin")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--firefox", help="Firefox binary, if not the default one")
    p.add_argument(
        "--geckodriver",
        help="geckodriver path; found on PATH or in Selenium's cache otherwise",
    )
    p.add_argument("--window", default="1400,1000")
    p.add_argument(
        "--screenshot-dir",
        default=os.path.join(os.path.dirname(__file__), "screenshots"),
    )
    return p


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
