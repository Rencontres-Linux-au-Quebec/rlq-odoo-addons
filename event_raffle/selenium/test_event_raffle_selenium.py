#!/usr/bin/env python3
# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""End-to-end Selenium scenarios for the ``event_raffle`` module.

Runs against a *live* Odoo instance (the module must be installed on the
target database). Data is created through the external XML-RPC API, then the
raffle wheel is driven through the web UI: it opens the raffle form, checks
that Tux's height stays within 25%-40% of the wheel height, runs several
draws in fullscreen (exercising the four Tux animations: peace, jump, flag,
dance), marks a winner absent and checks the event "Winners" smart button.

Screenshots are written to ``--screenshot-dir`` for visual inspection.

Example::

    ./run.sh -d test_event_raffle --db-filter test_event_raffle \\
        --http-port 8069 --workers 0 &
    MODULE=odoo18.0/addons/ERPLibre_erplibre_addons/event_raffle
    .venv.erplibre/bin/python \\
        "$MODULE"/selenium/test_event_raffle_selenium.py \\
        --url http://localhost:8069 --db test_event_raffle \\
        --login admin --password admin --headless
"""
import argparse
import os
import sys
import time
import xmlrpc.client

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

TUX_RATIO_MIN = 0.25
TUX_RATIO_MAX = 0.40
# The rotation order is defined by RaffleScene.ANIMATIONS in three_scene.js.
ANIMATION_ORDER = ["peace", "jump", "flag", "dance"]


# --------------------------------------------------------------------------- #
# XML-RPC data setup
# --------------------------------------------------------------------------- #
class Rpc:
    def __init__(self, url, db, user, password):
        self.db = db
        self.password = password
        common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
        self.uid = common.authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError("XML-RPC authentication failed")
        self.models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def exe(self, model, method, *params, **kw):
        return self.models.execute_kw(
            self.db,
            self.uid,
            self.password,
            model,
            method,
            list(params),
            kw,
        )


def setup_data(rpc):
    """Create an event with attendees and a raffle; return useful ids."""
    event_id = rpc.exe(
        "event.event",
        "create",
        [
            {
                "name": "Selenium Tirage",
                "date_begin": "2026-08-01 09:00:00",
                "date_end": "2026-08-01 18:00:00",
            }
        ],
    )[0]
    partner_id = rpc.exe(
        "res.partner",
        "create",
        [
            {
                "name": "Alice Libre",
                "email": "alice@example.com",
            }
        ],
    )[0]
    # 4 present attendees (one via a partner, plus a duplicate of that partner
    # to exercise dedupe), 1 merely registered (excluded by "present only").
    attendees = [
        {"name": "Alice Libre", "state": "done", "partner_id": partner_id},
        {"name": "Alice Libre", "state": "done", "partner_id": partner_id},
        {"name": "Bob", "state": "done", "email": "bob@example.com"},
        {"name": "Carol", "state": "done", "email": "carol@example.com"},
        {"name": "Dave", "state": "done", "email": "dave@example.com"},
        {"name": "Eve", "state": "open", "email": "eve@example.com"},
    ]
    for vals in attendees:
        vals["event_id"] = event_id
        rpc.exe("event.registration", "create", [vals])

    wizard_id = rpc.exe(
        "event.raffle.start.wizard",
        "create",
        [
            {
                "event_id": event_id,
                "copy_strategy": "present_only",
                "name": "Selenium Raffle",
            }
        ],
    )[0]
    rpc.exe("event.raffle.start.wizard", "action_start", [wizard_id])
    raffle_id = rpc.exe(
        "event.raffle", "search", [["event_id", "=", event_id]], limit=1
    )[0]
    # Speed the animation up for the test run.
    rpc.exe(
        "event.raffle",
        "write",
        [raffle_id],
        {
            "spin_duration": 1.2,
            "spin_turns": 2,
            "tux_animation": "rotate",
        },
    )
    raffle_action = rpc.exe(
        "ir.model.data",
        "search_read",
        [
            ["module", "=", "event_raffle"],
            ["name", "=", "action_event_raffle"],
        ],
        fields=["res_id"],
    )[0]["res_id"]
    event_action = rpc.exe(
        "ir.actions.act_window",
        "search",
        [["res_model", "=", "event.event"]],
        limit=1,
    )[0]
    return {
        "event_id": event_id,
        "raffle_id": raffle_id,
        "raffle_action": raffle_action,
        "event_action": event_action,
    }


# --------------------------------------------------------------------------- #
# Selenium harness
# --------------------------------------------------------------------------- #
class RaffleUi:
    def __init__(self, driver, url, screenshot_dir):
        self.d = driver
        self.url = url
        self.shot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)
        self._shot_n = 0

    def shot(self, name):
        self._shot_n += 1
        path = os.path.join(self.shot_dir, f"{self._shot_n:02d}_{name}.png")
        self.d.save_screenshot(path)
        print(f"  screenshot -> {path}")
        return path

    def login(self, user, password):
        self.d.get(f"{self.url}/web/login")
        el = WebDriverWait(self.d, 30).until(
            EC.visibility_of_element_located((By.NAME, "login"))
        )
        time.sleep(1.0)
        el.click()
        el.send_keys(user)
        self.d.find_element(By.NAME, "password").send_keys(password)
        self.d.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        WebDriverWait(self.d, 30).until(
            lambda d: "/odoo" in d.current_url or "/web" in d.current_url
        )

    def open_action(self, action_id, res_id, wait_css):
        for cand in [
            f"{self.url}/odoo/action-{action_id}/{res_id}",
            f"{self.url}/web#action={action_id}&view_type=form&id={res_id}",
        ]:
            self.d.get(cand)
            try:
                WebDriverWait(self.d, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_css))
                )
                return cand
            except TimeoutException:
                continue
        raise RuntimeError(f"could not open action {action_id}/{res_id}")

    def wait_tux_ratio(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            canvas = self.d.find_element(
                By.CSS_SELECTOR, ".o_raffle_wheel canvas"
            )
            ratio = canvas.get_attribute("data-tux-wheel-ratio")
            if ratio:
                return float(ratio)
            time.sleep(0.5)
        raise RuntimeError("Tux ratio attribute never set")

    def canvas_box_vs_buffer(self):
        """Check that the drawing buffer does not drive the layout.

        Writes an absurd ratio into the canvas attributes and reads back its
        laid-out height. If the height follows, the
        ResizeObserver -> setSize -> layout loop is open again and the canvas
        can grow without end (only its height, since its width is definite).
        """
        return self.d.execute_script(
            "const c = document.querySelector('.o_raffle_wheel canvas');"
            "const w0 = c.width, h0 = c.height, before = c.clientHeight;"
            "c.width = 100; c.height = 4000;"
            "const after = c.clientHeight;"
            "c.width = w0; c.height = h0;"
            "return [before, after];"
        )

    def eligible_count(self):
        txt = self.d.find_element(
            By.CSS_SELECTOR, ".o_raffle_wheel .o_raffle_count"
        ).text
        return int("".join(ch for ch in txt if ch.isdigit()) or 0)

    def wait_spin_done(self, timeout=25):
        # After a draw, Tux celebrates (spinning stays true); wait for the
        # spin button to be clickable again before the next step.
        WebDriverWait(self.d, timeout).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    ".o_raffle_wheel .o_raffle_toolbar button.btn-primary",
                )
            )
        )

    def click_spin(self):
        WebDriverWait(self.d, 15).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    ".o_raffle_wheel .o_raffle_toolbar button.btn-primary",
                )
            )
        ).click()

    def wait_winner(self, timeout=30):
        WebDriverWait(self.d, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".o_raffle_winner")
            )
        )
        return self.d.find_element(By.CSS_SELECTOR, ".o_raffle_winner").text

    def click_button_name(self, name, timeout=20):
        WebDriverWait(self.d, timeout).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, f"button[name='{name}']")
            )
        ).click()


def make_driver(chromium, chromedriver, headless, window):
    opts = Options()
    if chromium:
        opts.binary_location = chromium
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Software WebGL so the three.js canvas renders without a GPU.
    opts.add_argument("--enable-unsafe-swiftshader")
    opts.add_argument("--use-gl=angle")
    opts.add_argument("--use-angle=swiftshader")
    opts.add_argument(f"--window-size={window}")
    service = Service(chromedriver) if chromedriver else Service()
    driver = webdriver.Chrome(service=service, options=opts)
    w, h = window.split(",")
    driver.set_window_size(int(w), int(h))
    return driver


def resolve_chromedriver(explicit):
    if explicit:
        return explicit
    home = os.path.expanduser("~")
    candidates = []
    for root in (
        os.path.join(home, ".wdm", "drivers", "chromedriver"),
        os.path.join(home, ".cache", "selenium", "chromedriver"),
    ):
        for dirpath, _dirs, files in os.walk(root):
            if "chromedriver" in files:
                candidates.append(os.path.join(dirpath, "chromedriver"))
    # newest path wins (paths carry the version number)
    return sorted(candidates)[-1] if candidates else None


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def run(args):
    rpc = Rpc(args.url, args.db, args.login, args.password)
    ids = setup_data(rpc)
    print(
        f"Data ready: raffle_id={ids['raffle_id']} event_id={ids['event_id']}"
    )

    chromedriver = resolve_chromedriver(args.chromedriver)
    driver = make_driver(
        args.chromium, chromedriver, args.headless, args.window
    )
    failures = []
    try:
        ui = RaffleUi(driver, args.url, args.screenshot_dir)
        ui.login(args.login, args.password)
        print("Logged in.")

        # Scenario 1 - open the raffle form, check Tux size.
        ui.open_action(
            ids["raffle_action"], ids["raffle_id"], ".o_raffle_wheel canvas"
        )
        ratio = ui.wait_tux_ratio()
        ui.shot("raffle_form")
        print(f"Scenario 1: Tux/wheel height ratio = {ratio:.3f}")
        if not (TUX_RATIO_MIN <= ratio <= TUX_RATIO_MAX):
            failures.append(
                f"Tux ratio {ratio:.3f} outside "
                f"[{TUX_RATIO_MIN}, {TUX_RATIO_MAX}]"
            )

        # Scenario 1b - the canvas must be sized by the layout, never by its
        # own drawing buffer (embedded form view, where no ancestor supplies
        # a height).
        before, after = ui.canvas_box_vs_buffer()
        print(f"Scenario 1b: canvas height {before} -> {after} px")
        if before != after:
            failures.append(
                f"canvas height follows its drawing buffer "
                f"({before} -> {after} px): resize loop is open"
            )
        # The probe writes into the live drawing buffer; when the loop IS open
        # it also leaves a runaway growing. Reopen the form so what follows
        # starts from a clean canvas instead of reporting the fallout twice.
        ui.open_action(
            ids["raffle_action"], ids["raffle_id"], ".o_raffle_wheel canvas"
        )

        # Scenario 2 - go fullscreen (Tux visible) and run four draws,
        # one per animation in the rotation.
        driver.find_element(
            By.CSS_SELECTOR, ".o_raffle_wheel .o_raffle_fullscreen"
        ).click()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".o_raffle_wheel canvas")
            )
        )
        fs_ratio = ui.wait_tux_ratio()
        ui.shot("fullscreen_initial")
        print(f"Scenario 2: fullscreen ratio = {fs_ratio:.3f}")
        if not (TUX_RATIO_MIN <= fs_ratio <= TUX_RATIO_MAX):
            failures.append(f"Fullscreen Tux ratio {fs_ratio:.3f} out of band")

        start_eligible = ui.eligible_count()
        print(f"  eligible before draws: {start_eligible}")
        winners = []
        for i in range(min(start_eligible, len(ANIMATION_ORDER))):
            anim = ANIMATION_ORDER[i % len(ANIMATION_ORDER)]
            ui.click_spin()
            time.sleep(0.9)  # mid-animation
            ui.shot(f"anim_{anim}")
            winner = ui.wait_winner()
            winners.append(winner)
            ui.shot(f"winner_{i + 1}_{anim}")
            # wait for the spin + celebration to finish before the next draw
            ui.wait_spin_done()
            print(f"  draw {i + 1} ({anim}) -> {winner}")
        end_eligible = ui.eligible_count()
        print(f"  eligible after draws: {end_eligible}")
        # deferred removal: every winner but the last is removed from the pool
        expected = start_eligible - max(0, len(winners) - 1)
        if end_eligible != expected:
            failures.append(
                f"eligible went {start_eligible} -> {end_eligible} "
                f"after {len(winners)} draws (expected {expected})"
            )

        # Scenario 3 - draws were persisted server side.
        draw_ids = rpc.exe(
            "event.raffle.draw",
            "search",
            [["raffle_id", "=", ids["raffle_id"]]],
        )
        print(f"Scenario 3: {len(draw_ids)} draw record(s) persisted")
        if len(draw_ids) != len(winners):
            failures.append(
                f"{len(draw_ids)} draw records for {len(winners)} draws"
            )

        # Scenario 4 - "Winners" smart button on the event.
        ui.open_action(
            ids["event_action"],
            ids["event_id"],
            "button[name='action_view_raffle_winners']",
        )
        ui.click_button_name("action_view_raffle_winners")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".o_list_view, .o_data_row")
            )
        )
        time.sleep(1.0)
        ui.shot("winners_list")
        rows = driver.find_elements(By.CSS_SELECTOR, ".o_data_row")
        print(f"Scenario 4: winners list shows {len(rows)} row(s)")
        if len(rows) != len(winners):
            failures.append(
                f"winners list has {len(rows)} rows for {len(winners)} draws"
            )

        # Scenario 5 - mark the first winner absent.
        if draw_ids:
            rpc.exe("event.raffle.draw", "action_mark_absent", [draw_ids[0]])
            absent = rpc.exe(
                "event.raffle.draw", "read", [draw_ids[0]], ["is_absent"]
            )[0]["is_absent"]
            print(f"Scenario 5: draw {draw_ids[0]} is_absent={absent}")
            if not absent:
                failures.append("mark absent did not set is_absent")
            # the absent winner must NOT be back in the pool
            data = rpc.exe(
                "event.raffle", "read", [ids["raffle_id"]], ["eligible_count"]
            )[0]
            if data["eligible_count"] != end_eligible:
                failures.append(
                    "absent winner returned to the pool "
                    f"({data['eligible_count']} != {end_eligible})"
                )

        # collect browser console errors
        try:
            for entry in driver.get_log("browser"):
                if entry["level"] == "SEVERE":
                    print("CONSOLE SEVERE:", entry["message"][:300])
        except Exception:
            pass
    finally:
        driver.quit()

    print("\n" + "=" * 60)
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: PASS - all scenarios succeeded")
    return 0


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://localhost:8069")
    p.add_argument("--db", default="test_event_raffle")
    p.add_argument("--login", default="admin")
    p.add_argument("--password", default="admin")
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run Chromium without a visible window.",
    )
    p.add_argument(
        "--chromium",
        default="/usr/bin/chromium",
        help="Path to the Chromium/Chrome binary.",
    )
    p.add_argument(
        "--chromedriver",
        default=None,
        help="Path to chromedriver (auto-detected if omitted).",
    )
    p.add_argument("--window", default="1400,900")
    p.add_argument(
        "--screenshot-dir",
        default=os.path.join(os.path.dirname(__file__), "screenshots"),
    )
    return p


if __name__ == "__main__":
    sys.exit(run(build_parser().parse_args()))
