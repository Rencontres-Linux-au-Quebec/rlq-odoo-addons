# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""End-to-end tests of the raffle prize blocks in a real browser, through
Selenium (SeleniumCase of event_webapp_plan, tests/selenium_common.py).

The "My prize" card shows up without a reload when the user wins a draw
while the home page is open, says it once in the live region and leaves
the focus where it was; the public name form and the "On site" toggle
work by keyboard with the page script, which keeps the focus on the field
or the button and says the result (the class ticks the setting
"On-site card"). axe-core (WCAG 2.2 A and AA, plus
"region") runs on the home page with both blocks, at desktop and phone
widths, in the dark scheme and in text-only mode, once the entrance
animations of the cards have ended, when EWP_AXE_JS is set: the test
skips without the variable and fails when the file it names is missing.
Every name below is invented for the tests."""

import os

from odoo.tests import tagged

from odoo.addons.event_webapp_plan.tests.selenium_common import (
    PHONE,
    By,
    Keys,
    SeleniumCase,
)

from ..models.res_config_settings import PARAM_ONSITE_CARD
from .common import PrizeWebappMixin

# axe-core run on the document, WCAG 2.0/2.1/2.2 A and AA rules and the
# "region" rule, once the animations that end have ended: the entrance of
# the cards of a theme starts from opacity 0, and a card read on its way
# in blends its text and buttons with the page behind, a contrast the
# page never keeps. The animations that loop stay running.
JS_AXE_RUN = """
const done = arguments[arguments.length - 1];
const ending = document.getAnimations().filter((animation) => {
    const timing = animation.effect && animation.effect.getComputedTiming();
    return timing && Number.isFinite(timing.endTime);
});
Promise.all(ending.map((animation) => animation.finished.catch(() => null)))
    .then(() => window.axe.run(document, {
        iframes: false,
        runOnly: {
            type: "tag",
            values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
        },
        rules: {region: {enabled: true}},
    }))
    .then(
        (result) => done(result.violations.map(
            (v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`
        )),
        (error) => done(["axe error: " + error.message]),
    );
"""


@tagged("post_install", "-at_install", "selenium")
class TestSeleniumPrize(PrizeWebappMixin, SeleniumCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._webapp_setup("ewp_prize_se")
        cls.winner = cls._participant_of(cls.winner_user)
        cls.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, True)

    def _card_shown(self):
        return self.js(
            "const box = document.getElementById('ewp_prize_box');"
            "return Boolean(box && !box.hidden"
            " && box.querySelector('#ewp_prize_card .ewp_prize_item'));"
        )

    def _axe(self, label):
        with open(os.environ["EWP_AXE_JS"], encoding="utf-8") as handle:
            self.js(handle.read() + "\n;return true;")
        self.driver.set_script_timeout(120)
        violations = self.driver.execute_async_script(JS_AXE_RUN)
        self.assertEqual(violations, [], f"axe on {label}")

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_card_comes_in_when_the_user_wins(self):
        self.login(self.winner_user.login, redirect=self.home)
        self.wait_page_ready()
        self.assertFalse(self._card_shown())
        self.assertFalse(
            self.driver.find_element(By.ID, "ewp_prize_box").is_displayed()
        )
        self.js("document.getElementById('o_ewp_main').focus();")
        with self.server_paused():
            draw = self._draw(self.winner)
            draw._claim_link_issue()
            link = draw.sudo().claim_link_url
        # webapp.js sends it when its raffle refresh sees a new winner.
        self.js(
            "document.dispatchEvent(new CustomEvent('ewp:raffle-drawn',"
            " {bubbles: true, detail: {}}));"
        )
        self.wait_until(self._card_shown, "the card never came in")
        choose = self.wait_for("#ewp_prize_card .ewp_prize_choose")
        self.assertEqual(choose.get_attribute("href"), link)
        self.wait_until(
            lambda: (self.announcement() or "").startswith("Your prize, "),
            f"the new prize was not said (last: {self.announcement()!r})",
        )
        self.assertIn("Choose your prize before", self.announcement())
        self.assertEqual(self.active_element()["id"], "o_ewp_main")

    def test_public_name_form_by_keyboard(self):
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        self.login(self.winner_user.login, redirect=self.home)
        self.wait_page_ready()
        field = self.wait_for("#ewp_prize_name_input")
        field.click()
        field.send_keys("Tux Rider")
        self.press(Keys.ENTER)
        self.wait_announcement("Your public name is saved.")
        self.assertEqual(self.active_element()["id"], "ewp_prize_name_input")
        self.assertEqual(
            self.text(self.wait_for(".ewp_prize_shown_name")), "Tux Rider"
        )
        # Still the same page: the form went through the script.
        self.assertEqual(self.path(), self.home)
        with self.server_paused():
            self.assertEqual(
                self.winner_user.partner_id.raffle_public_name, "Tux Rider"
            )

    def test_public_name_save_button_keeps_the_focus(self):
        draw = self._draw(self.winner)
        draw._prize_claim(self.mug)
        self.login(self.winner_user.login, redirect=self.home)
        self.wait_page_ready()
        field = self.wait_for("#ewp_prize_name_input")
        field.click()
        field.send_keys("Tux Rider")
        # By keyboard: Tab to the button, then Enter.
        self.tab()
        self.assertEqual(self.active_element()["id"], "ewp_prize_save")
        self.press(Keys.ENTER)
        self.wait_announcement("Your public name is saved.")
        self.wait_until(
            lambda: self.text(self.wait_for(".ewp_prize_shown_name"))
            == "Tux Rider",
            "the card did not show the new name",
        )
        self.assertEqual(self.active_element()["id"], "ewp_prize_save")
        # A tap that leaves the focus on the page, as on a phone: the
        # focus goes to the button that sent the form. The live region
        # does not say the same message twice within 3 s, so the card
        # tells when the answer is in.
        self.js(
            "document.getElementById('ewp_prize_name_input').value ="
            " 'Ice Floe';"
            "document.activeElement.blur();"
            "const button = document.getElementById('ewp_prize_save');"
            "button.closest('form').requestSubmit(button);"
        )
        self.wait_until(
            lambda: self.text(self.wait_for(".ewp_prize_shown_name"))
            == "Ice Floe",
            "the card did not show the second name",
        )
        self.assertEqual(self.active_element()["id"], "ewp_prize_save")
        self.assertEqual(self.path(), self.home)
        with self.server_paused():
            self.assertEqual(
                self.winner_user.partner_id.raffle_public_name, "Ice Floe"
            )

    def test_presence_toggle_by_keyboard(self):
        self.login(self.winner_user.login, redirect=self.home)
        self.wait_page_ready()
        self.js("document.getElementById('ewp_presence_toggle').focus();")
        self.press(Keys.ENTER)
        self.wait_announcement("You are marked on site.")
        self.wait_until(
            lambda: self.driver.find_element(
                By.ID, "ewp_presence_toggle"
            ).get_attribute("aria-pressed")
            == "true",
            "the toggle is not pressed",
        )
        self.assertEqual(self.active_element()["id"], "ewp_presence_toggle")
        with self.server_paused():
            registration = self.winner.registration_id
            self.assertTrue(registration.attendance_declared)
            self.assertEqual(self.winner.attendance_mode, "onsite")

    def test_axe_on_the_home_page_with_the_prize_blocks(self):
        if not os.environ.get("EWP_AXE_JS"):
            self.skipTest("EWP_AXE_JS is not set")
        self.assertTrue(
            os.path.isfile(os.environ["EWP_AXE_JS"]),
            "EWP_AXE_JS names no file: {}".format(os.environ["EWP_AXE_JS"]),
        )
        reserved = self._draw(self.winner)
        reserved._prize_claim(self.mug)
        self._draw(self.winner)._claim_link_issue()
        self.login(self.winner_user.login, redirect=self.home)
        self.wait_page_ready()
        self.wait_for("#ewp_prize_card .ewp_prize_choose")
        self._axe("home")
        self.set_viewport(*PHONE)
        self.open(self.home)
        self.assertLessEqual(
            self.js("return document.documentElement.scrollWidth;"),
            PHONE[0],
        )
        self._axe("home, phone")
        self.emulate_media(color_scheme="dark")
        self.open(self.home)
        self._axe("home, dark scheme")
        self.emulate_media()
        with self.server_paused():
            self.winner_user.ewp_text_only = True
        self.open(self.home)
        self._axe("home, text-only mode")
