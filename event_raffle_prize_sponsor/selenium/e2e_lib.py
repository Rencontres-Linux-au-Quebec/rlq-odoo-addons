# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Shared helpers of the end-to-end Selenium scenarios of the raffle modules.

A scenario is a list of steps played in order against a running Odoo 18,
through a real browser opened by script/selenium/selenium_lib.py of
ERPLibre. Each step either passes, and leaves one screenshot, or stops the
scenario: a failed check gives exit code 1 with a screenshot and the HTML
of the page, an error of the tool (browser, server, RPC, guard) gives 2.

Guards, all checked before the browser starts:

- --url and --db have no default;
- the server runs Odoo 18 and lists exactly --db, so that the anonymous
  pages, which carry no database, are served by that database;
- that database is neutralized (ir.config_parameter
  database.is_neutralized), unless --allow-non-neutralized-database, which
  the help marks as dangerous;
- passwords come from environment variables only (the admin password
  falls back to "admin", the password of a scratch database), and never
  reach the output, the logs nor the summary.

No database is ever created nor dropped here.
"""

import argparse
import datetime
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import xmlrpc.client
from pathlib import Path

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

EXIT_PASS = 0
EXIT_STEP_FAILED = 1
EXIT_TOOL_ERROR = 2

ADMIN_PASSWORD_ENV = "RAFFLE_E2E_ADMIN_PASSWORD"
ADMIN_PASSWORD_SCRATCH = "admin"
ERPLIBRE_ROOT_ENV = "ERPLIBRE_ROOT"

# Exceptions that mean the page did not do what the step expects: the
# step fails (exit 1). Any other exception is an error of the tool (2).
STEP_FAILURES = (
    AssertionError,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)


class StepFailed(AssertionError):
    """A check of a step does not hold."""


class ToolError(Exception):
    """The tool cannot run the scenario: guard, server, browser, RPC."""


def check(condition, message):
    """Raise StepFailed with `message` unless `condition` holds."""
    if not condition:
        raise StepFailed(message)


def run_suffix():
    """A suffix unique to this run, put in every name the scenario creates,
    so that a second run on the same database never meets the first."""
    stamp = datetime.datetime.now().strftime("%m%d%H%M%S")
    return f"{stamp}{secrets.token_hex(2)}"


def new_password():
    """A random password for an account created by the scenario. It stays
    in memory: nothing prints nor saves it."""
    return secrets.token_urlsafe(18)


def number_in(text):
    """The first whole number of `text`, or None."""
    match = re.search(r"\d+", text or "")
    return int(match.group(0)) if match else None


def squash(text):
    """`text` with its runs of white space made one space, stripped."""
    return re.sub(r"\s+", " ", text or "").strip()


# ----------------------------------------------------------------------
# Command line
# ----------------------------------------------------------------------
class SortedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Help that lists the options in alphabetical order, whatever the
    order in which the shared and the scenario options were added."""

    def add_arguments(self, actions):
        super().add_arguments(
            sorted(actions, key=lambda a: (a.option_strings or [""])[-1])
        )


def build_parser(description):
    """The options every scenario shares; a scenario adds its own."""
    options = {
        "description": description,
        "formatter_class": SortedHelpFormatter,
        "allow_abbrev": False,
    }
    if sys.version_info >= (3, 14):
        # Coloured help on a terminal, plain when redirected.
        options["color"] = True
    parser = argparse.ArgumentParser(**options)
    parser.add_argument(
        "--admin-login",
        default="admin",
        help="Login of the organizer, an event manager and system user"
        " (default: admin). Its password is read from the environment"
        f" variable {ADMIN_PASSWORD_ENV}, else it is"
        f" '{ADMIN_PASSWORD_SCRATCH}', the password of a scratch database.",
    )
    parser.add_argument(
        "--allow-non-neutralized-database",
        action="store_true",
        help="DANGEROUS: run on a database that is not neutralized. The"
        " scenario creates users, events, prizes and orders, and may send"
        " emails and chat messages to the addresses it invents.",
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Database to drive. The server must list this one only.",
    )
    parser.add_argument(
        "--evidence-dir",
        default=None,
        help="Folder of the log, the screenshots, the video and the"
        " summary (default: ./raffle_e2e_<date>_<time>).",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Show the browser window (headless by default).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Seconds a step waits for a page condition (default: 30).",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Base URL of the Odoo server, such as http://127.0.0.1:8069.",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Record the browser into video.webm in the evidence folder"
        " (needs ffmpeg).",
    )
    parser.add_argument(
        "--window-size",
        default="1400,1000",
        type=window_size,
        help="Browser window size, width,height (default: 1400,1000).",
    )
    return parser


def window_size(text):
    """`text` as width,height in pixels, for argparse: the same text when
    it holds two positive whole numbers, else an argparse error."""
    match = re.fullmatch(r"\s*(\d+)\s*,\s*(\d+)\s*", text or "")
    if not match or not all(int(v) for v in match.groups()):
        raise argparse.ArgumentTypeError(
            f"{text!r} is not width,height, such as 1400,1000"
        )
    return f"{match.group(1)},{match.group(2)}"


# ----------------------------------------------------------------------
# Log and evidence
# ----------------------------------------------------------------------
class Evidence:
    """The evidence folder: run.log, one screenshot per step, the HTML of
    a failed page, summary.json and video.webm."""

    def __init__(self, path):
        if not path:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"raffle_e2e_{stamp}"
        self.dir = Path(path).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)

    def log(self, line=""):
        """Print `line` and append it to run.log."""
        print(line, flush=True)
        with open(self.dir / "run.log", "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def path(self, name):
        return self.dir / name

    def write_json(self, name, data):
        with open(self.dir / name, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)

    def close(self):
        """Nothing stays open between two lines of the log."""


# ----------------------------------------------------------------------
# Server and RPC
# ----------------------------------------------------------------------
def _jsonrpc(url, params, timeout=30):
    """Result of a JSON-RPC call to `url`, or raise ToolError."""
    body = json.dumps(
        {"jsonrpc": "2.0", "method": "call", "params": params}
    ).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise ToolError(f"{url} does not answer: {error}") from error
    if data.get("error"):
        error = data["error"]
        message = (error.get("data") or {}).get("message") or error
        raise ToolError(f"{url}: {message}")
    return data.get("result")


class Rpc:
    """XML-RPC client of one account on one database."""

    def __init__(self, url, db, login, password):
        self.url = url.rstrip("/")
        self.db = db
        self._password = password
        common = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/common", allow_none=True
        )
        try:
            self.uid = common.authenticate(db, login, password, {})
        except (xmlrpc.client.Error, OSError) as error:
            raise ToolError(
                f"XML-RPC authentication failed: {error}"
            ) from error
        if not self.uid:
            raise ToolError(f"the server refuses the login {login!r}")
        self._object = xmlrpc.client.ServerProxy(
            f"{self.url}/xmlrpc/2/object", allow_none=True
        )

    def call(self, model, method, *args, **kwargs):
        return self._object.execute_kw(
            self.db,
            self.uid,
            self._password,
            model,
            method,
            list(args),
            kwargs,
        )

    def ref(self, xmlid):
        """Database id of the record of `xmlid`, module.name."""
        module, name = xmlid.split(".", 1)
        rows = self.call(
            "ir.model.data",
            "search_read",
            [("module", "=", module), ("name", "=", name)],
            fields=["res_id"],
            limit=1,
        )
        if not rows:
            raise ToolError(f"no record {xmlid} on the database")
        return rows[0]["res_id"]

    def read_one(self, model, record_id, fields):
        rows = self.call(model, "read", [record_id], fields)
        if not rows:
            raise StepFailed(f"{model} {record_id} does not exist")
        return rows[0]


def admin_password():
    return os.environ.get(ADMIN_PASSWORD_ENV) or ADMIN_PASSWORD_SCRATCH


def guard_target(args, evidence):
    """Check the server and the database before anything is written, and
    return the organizer's Rpc. Raise ToolError when a guard refuses."""
    base = args.url.rstrip("/")
    version = _jsonrpc(f"{base}/web/webclient/version_info", {})
    if not isinstance(version, dict):
        raise ToolError(f"{base} is not an Odoo server: {version!r}")
    serie = str(version.get("server_serie", ""))
    if not serie.startswith("18"):
        raise ToolError(f"{base} runs Odoo {serie or '?'}, 18.0 expected")
    try:
        databases = _jsonrpc(f"{base}/web/database/list", {})
    except ToolError as error:
        raise ToolError(
            f"cannot list the databases of {base} ({error}): start Odoo"
            f" with --db-filter '^{args.db}$' and list_db on"
        ) from error
    if databases != [args.db]:
        raise ToolError(
            f"{base} serves {databases}; it must serve {args.db!r} only"
            f" (start Odoo with --db-filter '^{args.db}$')"
        )
    rpc = Rpc(base, args.db, args.admin_login, admin_password())
    try:
        neutralized = rpc.call(
            "ir.config_parameter", "get_param", "database.is_neutralized"
        )
    except xmlrpc.client.Fault as error:
        # get_param needs read access to the parameters: system users only.
        raise ToolError(
            f"{args.admin_login!r} cannot read database.is_neutralized"
            " (the organizer must be a system user)"
        ) from error
    except (xmlrpc.client.Error, OSError) as error:
        raise ToolError(f"XML-RPC call failed: {error}") from error
    if str(neutralized).lower() != "true":
        if not args.allow_non_neutralized_database:
            raise ToolError(
                f"{args.db!r} is not neutralized: refusing to write into a"
                " database that may be in production (neutralize it with"
                " odoo-bin neutralize, or pass the dangerous"
                " --allow-non-neutralized-database)"
            )
        evidence.log(
            "WARNING: the database is NOT neutralized, as"
            " --allow-non-neutralized-database asked"
        )
    return rpc


# ----------------------------------------------------------------------
# Browser
# ----------------------------------------------------------------------
def erplibre_root():
    """Root of the ERPLibre checkout that holds script/selenium: the
    ERPLIBRE_ROOT environment variable, else the first parent folder of
    this file that has it."""
    candidates = []
    if os.environ.get(ERPLIBRE_ROOT_ENV):
        candidates.append(Path(os.environ[ERPLIBRE_ROOT_ENV]))
    candidates.extend(Path(__file__).resolve().parents)
    for folder in candidates:
        if (folder / "script" / "selenium" / "selenium_lib.py").is_file():
            return folder
    raise ToolError(
        "script/selenium/selenium_lib.py of ERPLibre not found: set"
        f" {ERPLIBRE_ROOT_ENV} to the root of the ERPLibre checkout"
    )


def _selenium_config(args):
    """The configuration selenium_lib.SeleniumLib reads: its own defaults,
    then Chrome, headless unless --no-headless, no dark mode extension."""
    root = str(erplibre_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from script.selenium import selenium_lib

    parser = argparse.ArgumentParser(add_help=False)
    selenium_lib.fill_parser(parser)
    config = parser.parse_args([])
    config.url = args.url.rstrip("/")
    config.use_chrome_driver = True
    config.use_firefox_driver = False
    config.headless = not args.no_headless
    config.no_dark_mode = True
    config.window_size = args.window_size
    # configure() reads config.debug, which fill_parser does not declare.
    config.debug = None
    return selenium_lib, config


class FrameRecorder:
    """Video of the browser: a thread saves a screenshot every `period`
    seconds, and stop() joins them into video.webm with ffmpeg.

    selenium_lib records through selenium_video, which needs the
    GStreamer bindings of PyGObject; this recorder needs ffmpeg only. The
    driver's commands go through one lock, as selenium_video does, so
    that a screenshot never interleaves with a command of the scenario.
    """

    def __init__(self, driver, folder, period=0.5):
        self.driver = driver
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.period = period
        self._stop = threading.Event()
        self._count = 0
        lock = threading.Lock()
        execute = driver.execute

        def execute_locked(command, params=None):
            with lock:
                return execute(command, params)

        driver.execute = execute_locked
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(self.period):
            try:
                png = self.driver.get_screenshot_as_png()
            except WebDriverException:
                continue
            self._count += 1
            frame = self.folder / f"frame_{self._count:05d}.png"
            frame.write_bytes(png)

    def stop(self, output):
        """Join the frames into `output`; return its path, or None."""
        self._stop.set()
        self._thread.join(timeout=10)
        if not self._count or not shutil.which("ffmpeg"):
            return None
        command = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(round(1 / self.period)),
            "-i",
            str(self.folder / "frame_%05d.png"),
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libvpx",
            "-b:v",
            "1M",
            str(output),
        ]
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode:
            return None
        shutil.rmtree(self.folder, ignore_errors=True)
        return output


class Browser:
    """One Chrome session, through selenium_lib, with the waits and the
    Odoo gestures the scenarios use. Every wait polls a condition: none
    sleeps for a fixed time."""

    def __init__(self, args, evidence):
        self.args = args
        self.base = args.url.rstrip("/")
        self.evidence = evidence
        self.timeout = args.timeout
        self.driver = None
        self.recorder = None
        # "<number>_<key>" of the step being played, set by the scenario.
        self.prefix = "00_start"

    # -- life cycle ----------------------------------------------------
    def start(self):
        try:
            selenium_lib, config = _selenium_config(self.args)
            tool = selenium_lib.SeleniumLib(config)
            tool.configure(ignore_open_web=True)
            self.driver = tool.driver
            width, height = (int(v) for v in self.args.window_size.split(","))
            self.driver.set_window_size(width, height)
            if self.args.video:
                self.recorder = FrameRecorder(
                    self.driver, self.evidence.path("video_frames")
                )
                self.recorder.start()
        except ToolError:
            raise
        except Exception as error:
            raise ToolError(f"the browser does not start: {error}") from error

    def stop(self):
        video = None
        if self.recorder:
            video = self.recorder.stop(self.evidence.path("video.webm"))
            self.evidence.log(
                f"Video: {video}" if video else "Video: not written"
            )
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
        return video

    # -- pages ---------------------------------------------------------
    def get(self, path):
        self.driver.get(self.base + path)

    def path(self):
        """Path and query of the current page, without the base URL."""
        url = self.driver.current_url
        return url.removeprefix(self.base)

    def js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def wait(self, condition, message, timeout=None):
        """Return the first true value of `condition(driver)`."""
        waiter = WebDriverWait(
            self.driver,
            timeout or self.timeout,
            poll_frequency=0.25,
            ignored_exceptions=(StaleElementReferenceException,),
        )
        return waiter.until(condition, message)

    def visible(self, css, root=None):
        """Visible elements matching `css`, now."""
        root = root or self.driver
        return [
            element
            for element in root.find_elements(By.CSS_SELECTOR, css)
            if element.is_displayed()
        ]

    def find(self, css, timeout=None, visible=True):
        """First element matching `css`, visible unless `visible` is
        false, waited for."""

        def found(driver):
            if visible:
                elements = self.visible(css)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, css)
            return elements[0] if elements else False

        return self.wait(found, f"no element {css!r}", timeout)

    def find_text(self, css, text, timeout=None):
        """First visible element matching `css` whose text holds `text`."""

        def found(_driver):
            for element in self.visible(css):
                if text in element.text:
                    return element
            return False

        return self.wait(found, f"no {css!r} holding {text!r}", timeout)

    def click(self, css_or_element, timeout=None, text=None):
        """Click an element, or the first visible enabled one matching a
        selector (and holding `text` when given), scrolled into the middle
        of the window first. With a selector, an element that the page
        renders again or covers for a moment is looked up and clicked
        again until the timeout."""
        if not isinstance(css_or_element, str):
            self._click_now(css_or_element)
            return css_or_element
        css = css_or_element

        def attempt(_driver):
            for element in self.visible(css):
                if not element.is_enabled():
                    continue
                if text is not None and text not in element.text:
                    continue
                try:
                    self._click_now(element)
                except ElementClickInterceptedException:
                    return False
                return element
            return False

        what = f"{css!r}" + (f" holding {text!r}" if text else "")
        return self.wait(attempt, f"nothing to click at {what}", timeout)

    def _click_now(self, element):
        self.js("arguments[0].scrollIntoView({block: 'center'});", element)
        element.click()

    def type_into(self, css_or_element, text, clear=True):
        element = (
            self.find(css_or_element)
            if isinstance(css_or_element, str)
            else css_or_element
        )
        self.js("arguments[0].scrollIntoView({block: 'center'});", element)
        element.click()
        if clear:
            element.send_keys(Keys.CONTROL, "a")
            element.send_keys(Keys.DELETE)
        element.send_keys(text)
        return element

    def text(self, element):
        return squash(element.get_attribute("textContent"))

    def shot(self, name):
        path = self.evidence.path(f"{name}.png")
        self.driver.save_screenshot(str(path))
        return path

    def shot_extra(self, name):
        """A screenshot within the current step, named after it."""
        return self.shot(f"{self.prefix}_{name}")

    def save_html(self, name):
        path = self.evidence.path(f"{name}.html")
        path.write_text(self.driver.page_source, encoding="utf-8")
        return path

    # -- accounts ------------------------------------------------------
    def login(self, login, password, redirect="/odoo"):
        """Sign in from /web/login and land on `redirect`. A refusal
        fails the step; the password is typed, never logged."""
        query = urllib.parse.urlencode(
            {"db": self.args.db, "redirect": redirect}
        )
        self.get(f"/web/login?{query}")
        self.type_into("form.oe_login_form input[name=login]", login)
        self.type_into("form.oe_login_form input[name=password]", password)
        before = self.driver.find_element(By.TAG_NAME, "html")
        self.click("form.oe_login_form button[type=submit]")

        def outcome(driver):
            # The page of the form is gone once the old <html> element is
            # stale; Chrome may also say that its node left the document.
            try:
                _tag = before.tag_name
                return False
            except (StaleElementReferenceException, WebDriverException):
                pass
            if "/web/login" not in driver.current_url:
                return "in"
            if self.visible(".oe_login_form .alert-danger"):
                return "refused"
            return False

        result = self.wait(outcome, f"no answer to the sign-in of {login}")
        check(result == "in", f"the sign-in of {login} is refused")
        self.check_session_db()

    def logout(self):
        self.get("/web/session/logout?redirect=/web/login")
        self.find("form.oe_login_form input[name=login]")

    def check_session_db(self):
        """The browser session belongs to --db, or raise ToolError."""
        info = self.driver.execute_async_script("""
            const done = arguments[arguments.length - 1];
            fetch("/web/session/get_session_info", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({jsonrpc: "2.0", method: "call",
                                      params: {}}),
            }).then((r) => r.json()).then(
                (d) => done(d.result || {}), () => done({}));
            """)
        if info.get("db") != self.args.db:
            raise ToolError(
                f"the browser session is on {info.get('db')!r},"
                f" not on {self.args.db!r}"
            )

    # -- backend forms -------------------------------------------------
    def form_field(self, name, css="input"):
        """The `css` element of the field `name` of the open form."""
        return self.find(f".o_form_view .o_field_widget[name='{name}'] {css}")

    def set_field(self, name, value, css="input"):
        self.type_into(self.form_field(name, css), value)

    def set_checkbox(self, name, value):
        box = self.form_field(name, "input[type=checkbox]")
        if box.is_selected() != value:
            self.click(box)
        self.wait(
            lambda _d: box.is_selected() == value,
            f"the box {name} does not change",
        )

    def set_many2one(self, name, text):
        """Type `text` in a relational field and pick the suggestion that
        holds it."""
        field = self.form_field(name)
        self.type_into(field, text)
        self.click(".o-autocomplete--dropdown-item", text=text)
        self.wait(
            lambda _d: not self.visible(".o-autocomplete--dropdown-menu"),
            f"the suggestions of {name} stay open",
        )

    def click_button(self, name):
        return self.click(f"button[name='{name}']")

    def open_tab(self, page):
        self.click(f".o_notebook .nav-link[name='{page}']")

    def save_form(self):
        """Save the open form and wait until it holds no change."""
        buttons = self.visible(".o_form_button_save")
        if buttons:
            self.click(buttons[0])
        self.wait(
            lambda _d: not self.visible(".o_form_button_save")
            and not self.visible(".o_form_view .o_field_invalid"),
            "the form is not saved",
        )

    def record_id(self):
        """Id of the record of the open form: the last number of the
        path, as /odoo/<action>/<id> ends an Odoo 18 URL."""
        path = urllib.parse.urlsplit(self.driver.current_url).path
        numbers = re.findall(r"/(\d+)(?=/|$)", path)
        return int(numbers[-1]) if numbers else None


# ----------------------------------------------------------------------
# Scenario
# ----------------------------------------------------------------------
class Step:
    """One step: `key` names it in the output and the screenshot, `kind`
    says how it acts: "UI" through the browser, "setup" through RPC, or
    both, "UI+setup"."""

    def __init__(self, key, title, kind, func):
        self.key = key
        self.title = title
        self.kind = kind
        self.func = func


class Scenario:
    """Steps played in order on one browser and one organizer RPC.

    `ctx` is the state the steps share: ctx.args, ctx.rpc, ctx.browser,
    ctx.evidence, ctx.suffix, plus whatever the steps store. run() returns
    the exit code.
    """

    def __init__(self, name, args):
        self.name = name
        self.args = args
        self.steps = []
        self.results = []

    def step(self, key, title, kind="UI"):
        """Decorator that appends a step."""

        def register(func):
            self.steps.append(Step(key, title, kind, func))
            return func

        return register

    def insert_after(self, key, step):
        """Insert `step` after the step `key` (a scenario that builds on
        another adds its checks there)."""
        index = [s.key for s in self.steps].index(key)
        self.steps.insert(index + 1, step)

    def run(self, ctx):
        evidence = ctx.evidence
        evidence.log(f"Scenario {self.name}: {len(self.steps)} steps")
        evidence.log(f"Target: {self.args.url} database {self.args.db}")
        # The verdict is a tool error until every step has passed: an
        # exception that leaves the loop early never reads as a pass.
        code = EXIT_TOOL_ERROR
        started = time.time()
        try:
            ctx.rpc = guard_target(self.args, evidence)
            ctx.browser = Browser(self.args, evidence)
            ctx.browser.start()
            for index, step in enumerate(self.steps, start=1):
                result = self._play(ctx, index, step)
                if result != EXIT_PASS:
                    code = result
                    break
            else:
                code = EXIT_PASS
        except ToolError as error:
            evidence.log(f"[ERROR] tool: {error}")
            code = EXIT_TOOL_ERROR
        except KeyboardInterrupt:
            evidence.log("[ERROR] tool: interrupted")
            code = EXIT_TOOL_ERROR
        except Exception as error:  # noqa: BLE001
            # Outside a step (guard, browser start): the tool's fault.
            evidence.log(traceback.format_exc().rstrip())
            evidence.log(f"[ERROR] tool: {squash(str(error)) or repr(error)}")
            code = EXIT_TOOL_ERROR
        finally:
            video = None
            if getattr(ctx, "browser", None):
                video = ctx.browser.stop()
            self._summary(ctx, code, time.time() - started, video)
        return code

    def _play(self, ctx, index, step):
        evidence = ctx.evidence
        label = f"{index:02d} {step.key}"
        ctx.browser.prefix = f"{index:02d}_{step.key}"
        evidence.log(f"[STEP] {label} ({step.kind}): {step.title}")
        t0 = time.time()
        try:
            detail = step.func(ctx) or ""
        except STEP_FAILURES as error:
            return self._fail(ctx, index, step, t0, error, EXIT_STEP_FAILED)
        except ToolError as error:
            return self._fail(ctx, index, step, t0, error, EXIT_TOOL_ERROR)
        except Exception as error:  # noqa: BLE001
            # Whatever else breaks is the tool's fault: logged, exit 2.
            evidence.log(traceback.format_exc().rstrip())
            return self._fail(ctx, index, step, t0, error, EXIT_TOOL_ERROR)
        try:
            shot = ctx.browser.shot(f"{index:02d}_{step.key}")
        except Exception as error:  # noqa: BLE001
            # The step passed but its evidence is missing: a tool error.
            return self._fail(ctx, index, step, t0, error, EXIT_TOOL_ERROR)
        seconds = time.time() - t0
        evidence.log(f"[PASS] {label} ({seconds:.1f} s): {detail}")
        self.results.append(
            {
                "step": label,
                "kind": step.kind,
                "result": "pass",
                "seconds": round(seconds, 1),
                "detail": detail,
                "screenshot": shot.name,
            }
        )
        return EXIT_PASS

    def _fail(self, ctx, index, step, t0, error, code):
        label = f"{index:02d} {step.key}"
        shot = html = None
        try:
            shot = ctx.browser.shot(f"{index:02d}_{step.key}_FAILED")
            html = ctx.browser.save_html(f"{index:02d}_{step.key}_FAILED")
        except Exception as shot_error:  # noqa: BLE001
            # A dead browser leaves no screenshot; the verdict still goes.
            ctx.evidence.log(f"(no screenshot: {shot_error})")
        message = squash(str(error)) or error.__class__.__name__
        if isinstance(error, xmlrpc.client.Fault):
            lines = [x for x in error.faultString.splitlines() if x.strip()]
            message = f"RPC fault: {lines[-1] if lines else error.faultCode}"
        verdict = "FAIL" if code == EXIT_STEP_FAILED else "ERROR"
        ctx.evidence.log(
            f"[{verdict}] {label} ({time.time() - t0:.1f} s): {message}"
        )
        if shot:
            ctx.evidence.log(f"  screenshot: {shot}")
            ctx.evidence.log(f"  page: {html}")
        self.results.append(
            {
                "step": label,
                "kind": step.kind,
                "result": verdict.lower(),
                "detail": message,
                "screenshot": shot.name if shot else None,
            }
        )
        return code

    def _summary(self, ctx, code, seconds, video):
        verdict = {0: "PASS", 1: "FAIL", 2: "ERROR"}[code]
        ctx.evidence.log(
            f"RESULT: {verdict} (exit {code}), {len(self.results)} of"
            f" {len(self.steps)} steps played in {seconds:.0f} s"
        )
        ctx.evidence.write_json(
            "summary.json",
            {
                "scenario": self.name,
                "url": self.args.url,
                "db": self.args.db,
                "suffix": getattr(ctx, "suffix", None),
                "exit_code": code,
                "seconds": round(seconds, 1),
                "steps": self.results,
                "video": str(video) if video else None,
                "records": getattr(ctx, "records", {}),
            },
        )
