# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Base class of the tests that drive a real browser through Selenium.

SeleniumCase is an HttpCase whose test class shares one WebDriver. The
browser talks to the test server of the HttpCase (base_url()); every
request it sends carries the test cursor cookie of the running test, so the
server answers inside the transaction of the test and sees its records.

Browser: EWP_SELENIUM_BROWSER picks "chromium" (default) or "firefox";
EWP_SELENIUM_BINARY overrides the browser executable and
EWP_SELENIUM_DRIVER the driver (chromedriver, geckodriver). Without a
driver path, Selenium looks in PATH, then lets Selenium Manager resolve
one (it may download it once into its cache; its usage statistics are
turned off unless SE_AVOID_STATS is already set). The test class skips
itself (unittest.SkipTest, with the reason) only when the selenium package,
the browser or its driver is missing; any other failure to start the
browser is an error.

Shared cursor: the requests of the browser run in server threads, on the
cursor of the test, one at a time under registry.test_lock. Code of the
test that reads or writes records while a page is open goes through
`with self.server_paused():`, which holds that lock, so no request runs on
the cursor meanwhile, and empties the cache of the test environment, so it
reads what the requests wrote. open() flushes the pending writes of the
test, under the same lock, before it loads a page.

Screenshots: a test that fails or errors saves a screenshot, and on
Chromium the console messages of the page, into EWP_SELENIUM_SCREENSHOTS
(default: <temporary directory>/ewp_selenium); the log names the file.
"""

import logging
import os
import re
import shutil
import tempfile
import time
import unittest
from contextlib import contextmanager
from urllib.parse import quote, urlsplit

from odoo.tests import HttpCase
from odoo.tests.common import TEST_CURSOR_COOKIE_NAME

try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        JavascriptException,
        NoSuchDriverException,
        NoSuchElementException,
        StaleElementReferenceException,
        TimeoutException,
    )
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    # The test modules import these names; without selenium their classes
    # skip in setUpClass, so none of them is ever called.
    webdriver = ActionChains = By = Keys = WebDriverWait = None
    ChromeService = FirefoxService = None
    JavascriptException = NoSuchDriverException = None
    NoSuchElementException = StaleElementReferenceException = None
    TimeoutException = None

_logger = logging.getLogger(__name__)

BROWSER_ENV = "EWP_SELENIUM_BROWSER"
BINARY_ENV = "EWP_SELENIUM_BINARY"
DRIVER_ENV = "EWP_SELENIUM_DRIVER"
SCREENSHOTS_ENV = "EWP_SELENIUM_SCREENSHOTS"
# Executables tried in order for each browser, and the name of its driver.
BROWSERS = {
    "chromium": (
        (
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
        ),
        "chromedriver",
    ),
    "firefox": (
        ("/usr/lib/firefox/firefox", "/usr/bin/firefox"),
        "geckodriver",
    ),
}
# Viewports (width, height) in CSS pixels. Browser windows do not shrink
# below about MIN_WINDOW_WIDTH px: see set_viewport() for a phone.
MIN_WINDOW_WIDTH = 500
PHONE = (390, 844)
DESKTOP = (1280, 900)
WAIT_S = 30
# Static file served without a database: the browser loads it to reach
# the origin of the server before it sets its cookies.
STATIC_PATH = "/event_webapp_plan/static/description/icon.png"
# The service worker of the pages stays out of the browser: its
# registration fetches sw.js, a public route that opens a session when the
# request has none, and that fetch can outlive the page that started it. In
# flight while the next test loads the login form, it replaces the session
# cookie of the form, whose CSRF token then fails. Chromium runs this
# script before the scripts of every page, Firefox gets a preference. The
# tests of the controllers cover the service worker itself.
NO_SERVICE_WORKER_JS = "delete Navigator.prototype.serviceWorker;"
# Firefox preferences of the emulated media: ui.prefersReducedMotion
# (1 reduce, 0 no-preference) and the colour scheme override (0 dark,
# 1 light, 2 follow the system).
FIREFOX_MOTION = {"reduce": 1, "no-preference": 0}
FIREFOX_SCHEME = {"dark": 0, "light": 1}


class SeleniumCase(HttpCase):
    """HttpCase with a WebDriver shared by the tests of the class.

    Each test starts logged out, with a desktop viewport and no emulated
    media, on an empty page of the server origin whose only cookie is the
    test cursor cookie. Helpers: open(), login(), logout(), set_viewport(),
    emulate_media(), wait_until(), wait_js(), wait_for(), js(), press(),
    announcement(), wait_announcement(), active_element(), animations(),
    set_page_hidden(), server_paused() and restart_browser().
    """

    driver = None
    browser_name = None

    # ------------------------------------------------------------------
    # Browser life cycle
    # ------------------------------------------------------------------
    @classmethod
    def setUpClass(cls):
        # The browser starts first: without one, the class skips before
        # the HttpCase enters its test mode. It quits before the class
        # cleanups of BaseCase, which terminate any child process left.
        cls.browser_name = cls._browser_choice()
        cls._media = {}
        cls.driver = cls._start_driver()
        try:
            super().setUpClass()
        except Exception:
            cls._quit_driver()
            raise
        cls.addClassCleanup(cls._quit_driver)

    @classmethod
    def _browser_choice(cls):
        if webdriver is None:
            raise unittest.SkipTest(
                "selenium is not installed in the Python environment of "
                "Odoo (pip install 'selenium>=4.20')"
            )
        name = (os.environ.get(BROWSER_ENV) or "chromium").strip().lower()
        if name not in BROWSERS:
            raise ValueError(
                "%s=%r: expected one of %s"
                % (BROWSER_ENV, name, ", ".join(sorted(BROWSERS)))
            )
        return name

    @classmethod
    def _start_driver(cls):
        """New WebDriver for cls.browser_name with the media of cls._media
        (Firefox reads them at start only). Raises SkipTest when the
        browser or its driver is missing."""
        candidates, driver_name = BROWSERS[cls.browser_name]
        binary = os.environ.get(BINARY_ENV) or next(
            (path for path in candidates if os.access(path, os.X_OK)), None
        )
        if not binary or not os.access(binary, os.X_OK):
            raise unittest.SkipTest(
                "no %s executable (tried %s; set %s)"
                % (
                    cls.browser_name,
                    binary or ", ".join(candidates),
                    BINARY_ENV,
                )
            )
        driver_path = os.environ.get(DRIVER_ENV) or shutil.which(driver_name)
        os.environ.setdefault("SE_AVOID_STATS", "true")
        try:
            if cls.browser_name == "chromium":
                driver = cls._start_chromium(binary, driver_path)
            else:
                driver = cls._start_firefox(binary, driver_path)
        except NoSuchDriverException as error:
            raise unittest.SkipTest(
                "no %s for %s (set %s, or let Selenium Manager fetch it): %s"
                % (driver_name, binary, DRIVER_ENV, error.msg)
            ) from error
        if cls.browser_name == "chromium":
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": NO_SERVICE_WORKER_JS},
            )
        driver.set_script_timeout(WAIT_S)
        driver.set_page_load_timeout(120)
        _logger.info(
            "Selenium: %s %s through %s",
            cls.browser_name,
            driver.capabilities.get("browserVersion", "?"),
            driver_path or "Selenium Manager",
        )
        return driver

    @classmethod
    def _start_chromium(cls, binary, driver_path):
        options = webdriver.ChromeOptions()
        options.binary_location = binary
        cls._profile = tempfile.mkdtemp(prefix="ewp_selenium_profile_")
        for argument in (
            "--headless=new",
            "--user-data-dir=%s" % cls._profile,
            "--window-size=%d,%d" % DESKTOP,
            "--lang=en-US",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-features=Translate,MediaRouter,OptimizationHints",
        ):
            options.add_argument(argument)
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        service = ChromeService(executable_path=driver_path)
        return webdriver.Chrome(options=options, service=service)

    @classmethod
    def _start_firefox(cls, binary, driver_path):
        cls._profile = None
        options = webdriver.FirefoxOptions()
        options.binary_location = binary
        options.add_argument("-headless")
        options.add_argument("--width=%d" % DESKTOP[0])
        options.add_argument("--height=%d" % DESKTOP[1])
        for name, value in (
            ("intl.accept_languages", "en-US"),
            ("browser.shell.checkDefaultBrowser", False),
            ("datareporting.policy.dataSubmissionEnabled", False),
            ("toolkit.telemetry.enabled", False),
            ("app.update.enabled", False),
            ("dom.serviceWorkers.enabled", False),
            (
                "ui.prefersReducedMotion",
                FIREFOX_MOTION.get(
                    cls._media.get("prefers-reduced-motion"), 0
                ),
            ),
            (
                "layout.css.prefers-color-scheme.content-override",
                FIREFOX_SCHEME.get(cls._media.get("prefers-color-scheme"), 1),
            ),
        ):
            options.set_preference(name, value)
        service = FirefoxService(executable_path=driver_path)
        return webdriver.Firefox(options=options, service=service)

    @classmethod
    def _quit_driver(cls):
        if cls.driver is not None:
            try:
                cls.driver.quit()
            finally:
                cls.driver = None
                if getattr(cls, "_profile", None):
                    shutil.rmtree(cls._profile, ignore_errors=True)
                    cls._profile = None

    def restart_browser(self):
        """Quit the browser and start a new one: a new browser session,
        without cookies or storage. The test is logged out after it."""
        type(self)._quit_driver()
        type(self).driver = self._start_driver()
        self._reset_page()

    # ------------------------------------------------------------------
    # Per test
    # ------------------------------------------------------------------
    def setUp(self):
        super().setUp()
        self._login = None
        self.set_viewport(*DESKTOP)
        if self._media and self.browser_name == "chromium":
            self.emulate_media()
        elif self._media:
            type(self)._media = {}
            self.restart_browser()
        self._reset_page()

    def tearDown(self):
        outcome = getattr(self, "_outcome", None)
        if outcome is not None and not outcome.success:
            self._save_failure()
        if self.driver is not None:
            try:
                # Stops the polls and the chat of the page before the test
                # cursor cookie expires with the test.
                self.driver.get("about:blank")
            except Exception:
                _logger.info("Selenium: blank page refused", exc_info=True)
        super().tearDown()

    def _reset_page(self):
        """Empty page of the server origin, no storage, no cookie but the
        test cursor cookie of the running test. A request that carries the
        cookie of an earlier test is refused by the HttpCase; the web
        manifest, fetched without cookies, still reaches the test cursor."""
        self.driver.get(self.base_url() + STATIC_PATH)
        self.driver.delete_all_cookies()
        self.driver.add_cookie(
            {
                "name": TEST_CURSOR_COOKIE_NAME,
                "value": self.http_request_key,
                "path": "/",
            }
        )
        self.driver.execute_script(
            "sessionStorage.clear(); localStorage.clear();"
        )

    def _save_failure(self):
        if self.driver is None:
            return
        directory = os.environ.get(SCREENSHOTS_ENV) or os.path.join(
            tempfile.gettempdir(), "ewp_selenium"
        )
        os.makedirs(directory, exist_ok=True)
        stem = os.path.join(
            directory,
            "%s_%s" % (time.strftime("%Y%m%d_%H%M%S"), self._testMethodName),
        )
        try:
            self.driver.save_screenshot(stem + ".png")
            _logger.info(
                "Selenium: screenshot of %s at %s (page %s)",
                self._testMethodName,
                stem + ".png",
                self.driver.current_url,
            )
            if self.browser_name == "chromium":
                lines = [
                    "%(level)s %(message)s" % entry
                    for entry in self.driver.get_log("browser")
                ]
                with open(stem + ".console.txt", "w") as file:
                    file.write("\n".join(lines))
        except Exception:
            _logger.info("Selenium: no screenshot", exc_info=True)

    # ------------------------------------------------------------------
    # Navigation and session
    # ------------------------------------------------------------------
    def url(self, path):
        return path if "://" in path else self.base_url() + path

    def open(self, path, ready=True):
        """Load `path` once the pending writes of the test are flushed;
        with `ready`, wait until the page script has started (it writes
        data-ewp-motion on the body)."""
        with self.registry.test_lock:
            self.env.flush_all()
        self.driver.get(self.url(path))
        if ready:
            self.wait_page_ready()

    def wait_page_ready(self, message="page script not started"):
        return self.wait_js(
            "document.readyState === 'complete' && document.body"
            " && document.body.dataset.ewpMotion",
            message,
        )

    def path(self):
        return urlsplit(self.driver.current_url).path

    def submit_login_form(self, login, password=None):
        """Fill and send the login form of the current page, then wait
        until the browser leaves /web/login."""
        self.wait_for("input#login").clear()
        self.driver.find_element(By.CSS_SELECTOR, "input#login").send_keys(
            login
        )
        field = self.driver.find_element(By.CSS_SELECTOR, "input#password")
        field.clear()
        field.send_keys(password or login)
        self.driver.find_element(
            By.CSS_SELECTOR, "form.oe_login_form button[type='submit']"
        ).click()
        self.wait_until(
            lambda: self.path() != "/web/login",
            "login of %s refused" % login,
        )
        self._login = (login, password or login)

    def login(self, login, password=None, redirect=None):
        """Log in through the login form of /web/login, then land on
        `redirect` (a path) when given."""
        path = "/web/login"
        if redirect:
            path += "?redirect=" + quote(redirect, safe="")
        self.open(path, ready=False)
        self.submit_login_form(login, password)
        if redirect:
            self.wait_until(
                lambda: self.path() == urlsplit(redirect).path,
                "login did not lead to %s" % redirect,
            )

    def logout(self):
        """Forget the session: the browser keeps only the test cookie."""
        self._login = None
        self._reset_page()

    # ------------------------------------------------------------------
    # Viewport and media
    # ------------------------------------------------------------------
    def set_viewport(self, width, height):
        """Viewport of `width` x `height` CSS pixels, a phone under
        MIN_WINDOW_WIDTH; returns the width obtained. Chromium takes mobile
        metrics through DevTools and gives any width. Firefox windows stop
        at MIN_WINDOW_WIDTH, whatever the scale of the CSS pixel: a
        narrower request gets that width, still under the wide layout."""
        if self.browser_name == "chromium":
            self.driver.execute_cdp_cmd(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": width,
                    "height": height,
                    "deviceScaleFactor": 1,
                    "mobile": width < MIN_WINDOW_WIDTH,
                },
            )
        else:
            self.driver.set_window_size(width, height)
        return self.js("return window.innerWidth;")

    def emulate_media(self, reduced_motion=None, color_scheme=None):
        """Emulate prefers-reduced-motion ("reduce" or "no-preference")
        and prefers-color-scheme ("light" or "dark"); None leaves the
        default of the browser. Chromium applies them at once, through
        DevTools, and the open page reacts; Firefox reads them at start
        only: the browser restarts, logs in again as the same user and
        shows a blank page."""
        media = {}
        if reduced_motion:
            media["prefers-reduced-motion"] = reduced_motion
        if color_scheme:
            media["prefers-color-scheme"] = color_scheme
        type(self)._media = media
        if self.browser_name == "chromium":
            self.driver.execute_cdp_cmd(
                "Emulation.setEmulatedMedia",
                {
                    "media": "",
                    "features": [
                        {"name": name, "value": value}
                        for name, value in media.items()
                    ],
                },
            )
            return
        self._restart_logged_in()

    def _restart_logged_in(self):
        login = self._login
        self.restart_browser()
        if login:
            self.login(*login)

    # ------------------------------------------------------------------
    # Waiting and reading
    # ------------------------------------------------------------------
    def wait_until(self, predicate, message, timeout=WAIT_S):
        """Value of `predicate()` once truthy; fails with `message` after
        `timeout` seconds. Stale or missing elements count as falsy."""
        try:
            return WebDriverWait(
                self.driver,
                timeout,
                poll_frequency=0.1,
                ignored_exceptions=(
                    NoSuchElementException,
                    StaleElementReferenceException,
                    JavascriptException,
                ),
            ).until(lambda _driver: predicate())
        except TimeoutException:
            self.fail(
                "%s (after %s s, on %s)" % (message, timeout, self.path())
            )

    def js(self, script, *args):
        """Result of the body of a JavaScript function (`return ...`)."""
        return self.driver.execute_script(script, *args)

    def wait_js(self, expression, message, *args, timeout=WAIT_S):
        """Value of the JavaScript `expression` once truthy."""
        return self.wait_until(
            lambda: self.js("return (%s);" % expression, *args),
            message,
            timeout=timeout,
        )

    def wait_for(self, selector, message=None, visible=True):
        """First element matching the CSS `selector`, once present and,
        with `visible`, displayed."""

        def find():
            element = self.driver.find_element(By.CSS_SELECTOR, selector)
            return element if not visible or element.is_displayed() else None

        return self.wait_until(find, message or "no element %s" % selector)

    def find_all(self, selector):
        return self.driver.find_elements(By.CSS_SELECTOR, selector)

    def press(self, *keys):
        """Send `keys` to the focused element, as a keyboard would."""
        ActionChains(self.driver).send_keys(*keys).perform()

    def tab(self, count=1):
        for _index in range(count):
            self.press(Keys.TAB)

    def active_element(self):
        """Id, tag, classes and text of the focused element."""
        return self.js(
            "const el = document.activeElement;"
            "return el ? {id: el.id, tag: el.tagName.toLowerCase(),"
            " className: String(el.className || ''),"
            " text: (el.textContent || '').trim().replace(/\\s+/g, ' ')}"
            " : null;"
        )

    def announcement(self):
        """Text of the live region of the page."""
        return self.js(
            "const region = document.getElementById('o_ewp_announcer');"
            "return region ? region.textContent : null;"
        )

    def wait_announcement(self, text, timeout=WAIT_S):
        self.wait_until(
            lambda: self.announcement() == text,
            "live region never said %r (last: %r)"
            % (text, self.announcement()),
            timeout=timeout,
        )

    def animations(self, running_only=False):
        """Names of the animations and transitions of the document (Web
        Animations API): CSS animation name, else transition property."""
        return self.js(
            "return document.getAnimations()"
            ".filter((a) => !arguments[0] || a.playState === 'running')"
            ".map((a) => a.animationName || a.transitionProperty"
            " || a.id || 'animation');",
            running_only,
        )

    def set_page_hidden(self, hidden):
        """Make the open page see its tab hidden (`hidden` true) or shown
        again: document.hidden and document.visibilityState answer so,
        and visibilitychange fires. A headless browser keeps its only tab
        visible and offers no command to hide it, so the page is told in
        place, as both browsers would tell it."""
        self.js(
            "const hidden = arguments[0];"
            "Object.defineProperty(document, 'hidden',"
            " {configurable: true, get: () => hidden});"
            "Object.defineProperty(document, 'visibilityState',"
            " {configurable: true, get: () => hidden ? 'hidden' : 'visible'});"
            "document.dispatchEvent(new Event('visibilitychange'));",
            bool(hidden),
        )

    def text(self, element):
        """Text content of `element`, white space squashed. Unlike the
        text of Selenium, it does not depend on the element being shown:
        the entrance animation of a theme starts from opacity 0."""
        return self.squash(element.get_attribute("textContent"))

    @staticmethod
    def squash(text):
        return re.sub(r"\s+", " ", text or "").strip()

    # ------------------------------------------------------------------
    # Records while a page is open
    # ------------------------------------------------------------------
    @contextmanager
    def server_paused(self):
        """Hold the lock of the shared test cursor: no request of the
        browser runs meanwhile. The cache of the test environment is
        emptied first, so reads see what the requests wrote, and the
        writes of the block are flushed before the lock is released."""
        with self.registry.test_lock:
            self.env.invalidate_all()
            yield
            self.env.flush_all()
