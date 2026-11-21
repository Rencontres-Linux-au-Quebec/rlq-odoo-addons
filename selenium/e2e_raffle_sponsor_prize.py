#!/usr/bin/env python3
# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""End-to-end scenario of the sponsored raffle prizes, in a real browser.

From the sponsor's portal to the winner's token checkout, on a running
Odoo 18 with event_raffle_prize_sponsor installed (and the raffle modules
under it). Every step that the organizer, the sponsor or a winner does
goes through the browser; the accounts, the attendees, the discussion
channel and the stock are prepared through XML-RPC (see README.md).

Steps:

 1. setup     accounts, channel, token category ranges (RPC)
 2. event     organizer: event managed with sponsors, winners page
              published, sponsor registration (UI); 4 attendees (RPC)
 3. portal    sponsor: 6 prizes from /my, 2 per token category A, B, C
 4. raffle    organizer: raffle from the event, announcement in the
              channel and winner notification on, short spin
 5. approve   organizer: approves the 6 prizes in "Sponsored Prizes to
              Review" (UI); records their stock (RPC); the shop lists
              them in the Sponsored category (UI, anonymous visitor)
 6. draws     organizer: 3 draws on the wheel, groups A, B, C
 7. discuss   organizer: the channel shows exactly one OdooBot message
              per draw, as the raffle's template renders it, with the
              prize link; each winner was notified (RPC)
 8-10. claim  each winner signs in (through the prize link, or straight
              to /shop), takes the second, the first, then the second
              prize of their group with the token, checks out
11. results   the shop stock went down by one per prize taken, the
              winners page shows each winner with the chosen prize

Exit code: 0 every step passes, 1 a step fails (its screenshot and its
page are in the evidence folder), 2 the tool fails or a guard refuses.
"""

import datetime
import re
import sys
import types
from pathlib import Path
from urllib.parse import urlsplit

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select

sys.path.insert(0, str(Path(__file__).resolve().parent))

import e2e_lib as lib
from e2e_lib import check

# Token categories of event_raffle_prize, A to C, and the ranges this
# scenario gives them when their range is still [0, 0], the module's
# default. A range already set is kept and the prices follow it.
BANDS = (
    ("A", "event_raffle_prize.token_category_gold", 100.0, 1000.0),
    ("B", "event_raffle_prize.token_category_silver", 25.0, 99.99),
    ("C", "event_raffle_prize.token_category_bronze", 0.01, 24.99),
)
# Prize price at these fractions of the category's range: two prizes per
# category, two different prices.
PRICE_FRACTIONS = (0.3, 0.6)
# Units offered by the sponsor, and recorded in stock by the organizer.
PRIZE_QTY = 3
ATTENDEES = ("Alix", "Bastien", "Camille", "Dominique")
# How each winner reaches the shop, and which prize of their group they
# take (0: the first, 1: the second), in the order of the draws A, B, C.
WINNER_PLANS = (("link", 1), ("shop", 0), ("link", 1))
# Short wheel: the step waits for the end of the spin, never a fixed time.
SPIN_SECONDS = "2"
SPIN_TURNS = "1"
# Placeholders of the raffle messages (event_raffle_draw.py), with the
# value key each one stands for.
PLACEHOLDERS = {
    "winner": "winner",
    "gagnant": "winner",
    "number": "number",
    "numéro": "number",
    "numero": "number",
    "raffle": "raffle",
    "tirage": "raffle",
    "prize": "prize",
    "prix": "prize",
    "link": "link",
    "lien": "link",
}


def render_message(template, values):
    """`template` with each known {placeholder} replaced from `values`,
    all non-empty; an unknown word in braces stays as typed."""

    def replace(match):
        key = PLACEHOLDERS.get(match.group(1).lower())
        return values[key] if key else match.group(0)

    return re.sub(r"\{(\w+)\}", replace, template or "")


def link_path(url):
    """Path of an absolute link of the server, to open it on --url."""
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


# ----------------------------------------------------------------------
# 1. Setup
# ----------------------------------------------------------------------
def _lang_formats(rpc, lang):
    rows = rpc.call(
        "res.lang",
        "search_read",
        [("code", "=", lang)],
        fields=["date_format", "time_format"],
        limit=1,
    )
    if not rows:
        return "%Y-%m-%d", "%H:%M:%S"
    return rows[0]["date_format"], rows[0]["time_format"]


def _bands(ctx):
    """Read the categories A, B, C; make an archived one active again and
    give a range to those without one (README.md lists both changes);
    return [{letter, id, name, prices}] with two prices per category."""
    rpc = ctx.rpc
    bands = []
    for letter, xmlid, low, high in BANDS:
        band_id = rpc.ref(xmlid)
        band = rpc.call(
            "event.raffle.prize.band",
            "read",
            [band_id],
            ["name", "value_min", "value_max", "active"],
            context={"lang": ctx.lang},
        )[0]
        values = {}
        if not band["active"]:
            values["active"] = True
        if not band["value_min"] and not band["value_max"]:
            values.update(value_min=low, value_max=high)
            band.update(value_min=low, value_max=high)
        if values:
            rpc.call("event.raffle.prize.band", "write", [band_id], values)
            ctx.notes.append(f"category {letter} set to {values}")
        span = band["value_max"] - band["value_min"]
        prices = [
            round(band["value_min"] + span * fraction, 2)
            for fraction in PRICE_FRACTIONS
        ]
        bands.append(
            {
                "letter": letter,
                "id": band_id,
                "name": band["name"],
                "prices": prices,
            }
        )
    return bands


def _band_of_price(rpc, price):
    """The category a prize of `price` gets: the first active category,
    in sequence order, whose range holds the price."""
    rows = rpc.call(
        "event.raffle.prize.band",
        "search_read",
        [("value_min", "<=", price), ("value_max", ">=", price)],
        fields=["id"],
        order="sequence, id",
        limit=1,
    )
    return rows[0]["id"] if rows else False


def _portal_user(ctx, name, email, partner_id=None):
    """A portal user with a random password, kept in ctx.passwords."""
    rpc = ctx.rpc
    values = {
        "name": name,
        "login": email,
        "email": email,
        "lang": ctx.lang,
        "groups_id": [(6, 0, [rpc.ref("base.group_portal")])],
        "password": lib.new_password(),
    }
    if partner_id:
        values["partner_id"] = partner_id
    password = values["password"]
    user_id = rpc.call("res.users", "create", values)
    ctx.passwords[email] = password
    partner = rpc.read_one("res.users", user_id, ["partner_id"])
    return {
        "user_id": user_id,
        "partner_id": partner["partner_id"][0],
        "login": email,
        "name": name,
    }


def step_setup(ctx):
    rpc = ctx.rpc
    sfx = ctx.suffix
    admin = rpc.read_one(
        "res.users", rpc.uid, ["lang", "partner_id", "name", "tz"]
    )
    ctx.lang = admin["lang"] or "en_US"
    ctx.admin_name = admin["name"]
    ctx.admin_partner_id = admin["partner_id"][0]
    ctx.date_formats = _lang_formats(rpc, ctx.lang)
    ctx.bands = _bands(ctx)
    for band in ctx.bands:
        for price in band["prices"]:
            if _band_of_price(rpc, price) != band["id"]:
                raise lib.ToolError(
                    f"a price of {price} does not fall in category"
                    f" {band['letter']}: the category ranges overlap"
                )
    config_id = rpc.ref("event_raffle.raffle_config_singleton")
    config = rpc.read_one(
        "event.raffle.config",
        config_id,
        ["sponsored_shop_open", "sponsored_shop_close_date"],
    )
    if (
        not config["sponsored_shop_open"]
        or config["sponsored_shop_close_date"]
    ):
        rpc.call(
            "event.raffle.config",
            "write",
            [config_id],
            {"sponsored_shop_open": True, "sponsored_shop_close_date": False},
        )
        ctx.notes.append("sponsored shop opened")
    ctx.channel_name = f"tirage-e2e-{sfx}"
    ctx.channel_id = rpc.call(
        "discuss.channel",
        "create",
        {
            "name": ctx.channel_name,
            "channel_type": "channel",
            "channel_member_ids": [
                (0, 0, {"partner_id": ctx.admin_partner_id})
            ],
        },
    )
    company_id = rpc.call(
        "res.partner",
        "create",
        {
            "name": f"Commanditaire Exemple {sfx}",
            "is_company": True,
            "website": f"https://sponsor-{sfx}.example.com",
        },
    )
    contact_id = rpc.call(
        "res.partner",
        "create",
        {
            "name": f"Sasha Exemple {sfx}",
            "email": f"sasha.{sfx}@example.com",
            "parent_id": company_id,
            "lang": ctx.lang,
        },
    )
    ctx.sponsor = _portal_user(
        ctx, f"Sasha Exemple {sfx}", f"sasha.{sfx}@example.com", contact_id
    )
    ctx.sponsor["company_id"] = company_id
    ctx.sponsor["company_name"] = f"Commanditaire Exemple {sfx}"
    ctx.attendees = [
        _portal_user(
            ctx,
            f"{first} Exemple {sfx}",
            f"{first.lower()}.{sfx}@example.com",
        )
        for first in ATTENDEES
    ]
    ctx.records.update(
        suffix=sfx,
        lang=ctx.lang,
        channel_id=ctx.channel_id,
        sponsor_company_id=company_id,
        sponsor_login=ctx.sponsor["login"],
        attendee_logins=[a["login"] for a in ctx.attendees],
        bands={b["letter"]: b["id"] for b in ctx.bands},
    )
    notes = "; ".join(ctx.notes) or "categories and shop already set"
    return (
        f"language {ctx.lang}, sponsor and {len(ctx.attendees)} attendee"
        f" portal accounts, channel {ctx.channel_name}, {notes}"
    )


# ----------------------------------------------------------------------
# 2. Event
# ----------------------------------------------------------------------
def _type_datetime(browser, css, value, formats):
    date_format, time_format = formats
    text = value.strftime(f"{date_format} {time_format}")
    field = browser.type_into(css, text)
    field.send_keys(Keys.ENTER)


def _create_sponsor_registration(ctx, event_id):
    """From the event's Attendees button: a registration of the sponsor
    contact, marked as the sponsor."""
    browser = ctx.browser
    action = ctx.rpc.ref("event.act_event_registration_from_event")
    browser.click(f".o_form_view button[name='{action}']")
    browser.click(
        ".o_control_panel_main_buttons button.o-kanban-button-new,"
        " .o_control_panel_main_buttons button.o_list_button_add"
    )
    browser.find(".o_form_view .o_form_sheet")
    sponsor = ctx.sponsor
    browser.set_field("name", sponsor["name"])
    browser.set_field("email", sponsor["login"])
    browser.set_many2one("partner_id", sponsor["name"])
    browser.set_checkbox("is_raffle_sponsor", True)
    browser.save_form()
    shown = browser.form_field("raffle_sponsor_partner_id", "*")
    check(
        sponsor["name"] in browser.text(shown),
        f"the sponsor contact shows {browser.text(shown)!r}",
    )
    check(
        not browser.visible(".o_raffle_sponsor_no_account"),
        "the form says that the sponsor has no account",
    )
    rows = ctx.rpc.call(
        "event.registration",
        "search_read",
        [("event_id", "=", event_id), ("is_raffle_sponsor", "=", True)],
        fields=["raffle_sponsor_partner_id"],
    )
    check(
        len(rows) == 1
        and rows[0]["raffle_sponsor_partner_id"][0] == sponsor["partner_id"],
        f"sponsor registrations of the event: {rows}",
    )


def _add_attendees(ctx, event_id):
    """Setup: one registration per attendee, checked in, so that the
    raffle takes them and the physical prizes are offered to them."""
    rpc = ctx.rpc
    for attendee in ctx.attendees:
        registration_id = rpc.call(
            "event.registration",
            "create",
            {
                "event_id": event_id,
                "partner_id": attendee["partner_id"],
                "name": attendee["name"],
                "email": attendee["login"],
            },
        )
        # action_set_done() returns None, which XML-RPC cannot carry: the
        # state it writes is written here.
        rpc.call(
            "event.registration", "write", [registration_id], {"state": "done"}
        )


def step_event(ctx):
    browser = ctx.browser
    browser.login(ctx.args.admin_login, lib.admin_password())
    browser.get("/odoo/action-event.action_event_view/new")
    browser.find(".o_form_view .o_form_sheet")
    ctx.event_name = f"Rencontre Exemple {ctx.suffix}"
    browser.set_field("name", ctx.event_name, css="textarea")
    now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
    begin = now - datetime.timedelta(hours=1)
    end = now + datetime.timedelta(days=2)
    _type_datetime(
        browser,
        ".o_field_widget[name='date_begin'] input[data-field='date_begin']",
        begin,
        ctx.date_formats,
    )
    _type_datetime(
        browser,
        ".o_field_widget[name='date_begin'] input[data-field='date_end']",
        end,
        ctx.date_formats,
    )
    browser.set_checkbox("raffle_sponsor_managed", True)
    browser.set_many2one("raffle_sponsor_manager_ids", ctx.admin_name)
    browser.set_checkbox("raffle_winners_published", True)
    browser.save_form()
    event_id = browser.record_id()
    check(event_id, f"no event id in {browser.driver.current_url}")
    event = ctx.rpc.read_one(
        "event.event",
        event_id,
        ["name", "raffle_sponsor_managed", "raffle_winners_published"],
    )
    check(
        event["name"] == ctx.event_name
        and event["raffle_sponsor_managed"]
        and event["raffle_winners_published"],
        f"the event is saved as {event}",
    )
    ctx.event_id = event_id
    _create_sponsor_registration(ctx, event_id)
    _add_attendees(ctx, event_id)
    ctx.records["event_id"] = event_id
    return (
        f"event {event_id} managed with sponsors, winners page published,"
        f" sponsor registration (UI); {len(ctx.attendees)} attendees"
        " checked in (setup)"
    )


# ----------------------------------------------------------------------
# 3. Sponsor portal
# ----------------------------------------------------------------------
def _prize_plan(ctx):
    """The 6 prizes: name, price and category, 2 per category."""
    plan = []
    for band in ctx.bands:
        for index, price in enumerate(band["prices"], start=1):
            plan.append(
                {
                    "name": f"Lot {band['letter']}{index} {ctx.suffix}",
                    "price": price,
                    "band": band,
                }
            )
    return plan


def _submit_prize(ctx, prize):
    browser = ctx.browser
    browser.click(f"a.o_raffle_sponsor_add[href*='event_id={ctx.event_id}']")
    browser.find("form.o_raffle_sponsor_form")
    choices = browser.visible("#o_raffle_sponsor_event_id")
    if choices:
        Select(choices[0]).select_by_value(str(ctx.event_id))
    browser.type_into("#o_raffle_sponsor_name", prize["name"])
    browser.type_into(
        "#o_raffle_sponsor_description",
        f"Prix offert par le commanditaire, groupe {prize['band']['letter']}.",
    )
    browser.type_into("#o_raffle_sponsor_value", f"{prize['price']:.2f}")
    browser.type_into("#o_raffle_sponsor_quantity", str(PRIZE_QTY))
    browser.click("#o_raffle_sponsor_mode")
    browser.click("button.o_raffle_sponsor_submit")
    browser.find(".o_raffle_sponsor_message")
    browser.find_text(".o_raffle_sponsor_prize h3", prize["name"])


def step_portal(ctx):
    browser = ctx.browser
    browser.logout()
    sponsor = ctx.sponsor
    browser.login(sponsor["login"], ctx.passwords[sponsor["login"]], "/my")
    browser.click("a[href='/my/raffle-prizes']")
    shown = browser.text(browser.find(".o_raffle_sponsor_name strong"))
    check(
        shown == sponsor["company_name"],
        f"the portal names the sponsor {shown!r}",
    )
    ctx.prizes = _prize_plan(ctx)
    for prize in ctx.prizes:
        _submit_prize(ctx, prize)
    section = browser.find(
        f"section[aria-labelledby='o_raffle_sponsor_event_{ctx.event_id}']"
    )
    cards = browser.visible(".o_raffle_sponsor_prize", root=section)
    check(len(cards) == len(ctx.prizes), f"{len(cards)} prizes listed")
    names = [p["name"] for p in ctx.prizes]
    rows = ctx.rpc.call(
        "product.template",
        "search_read",
        [("name", "in", names), ("active", "in", (True, False))],
        fields=[
            "name",
            "raffle_sponsor_state",
            "raffle_sponsor_id",
            "raffle_band_id",
            "active",
            "list_price",
        ],
    )
    by_name = {row["name"]: row for row in rows}
    for prize in ctx.prizes:
        row = by_name.get(prize["name"])
        check(row, f"{prize['name']} is not saved")
        check(
            row["raffle_sponsor_state"] == "submitted" and not row["active"],
            f"{prize['name']} is {row['raffle_sponsor_state']},"
            f" active={row['active']}",
        )
        check(
            row["raffle_sponsor_id"]
            and row["raffle_sponsor_id"][0] == sponsor["company_id"],
            f"{prize['name']} has the sponsor {row['raffle_sponsor_id']}",
        )
        check(
            row["raffle_band_id"]
            and row["raffle_band_id"][0] == prize["band"]["id"],
            f"{prize['name']} at {row['list_price']} has the category"
            f" {row['raffle_band_id']}, {prize['band']['letter']} expected",
        )
        prize["template_id"] = row["id"]
        # A submitted prize is archived, and so is its variant.
        prize["product_id"] = ctx.rpc.call(
            "product.product",
            "search",
            [
                ("product_tmpl_id", "=", row["id"]),
                ("active", "in", (True, False)),
            ],
            limit=1,
        )[0]
    ctx.records["prizes"] = {
        p["name"]: {
            "template_id": p["template_id"],
            "price": p["price"],
            "band": p["band"]["letter"],
        }
        for p in ctx.prizes
    }
    return (
        f"{len(ctx.prizes)} prizes submitted from /my/raffle-prizes,"
        " each Submitted, archived, in its category A, B or C"
    )


# ----------------------------------------------------------------------
# 4. Raffle
# ----------------------------------------------------------------------
def _select_option(browser, css, value):
    """Pick the option of a selection field whose value is `value`; the
    form's options hold JSON values, such as "present_only" in quotes."""
    select = Select(browser.find(css))
    for option in select.options:
        if option.get_attribute("value").strip('"') == value:
            select.select_by_value(option.get_attribute("value"))
            return
    raise lib.StepFailed(f"no option {value} in {css}")


def step_raffle(ctx):
    browser = ctx.browser
    browser.logout()
    browser.login(ctx.args.admin_login, lib.admin_password())
    browser.get(f"/odoo/action-event.action_event_view/{ctx.event_id}")
    browser.click_button("action_start_raffle")
    dialog = ".modal .o_form_view"
    browser.find(dialog)
    ctx.raffle_name = f"Tirage Exemple {ctx.suffix}"
    browser.type_into(
        f"{dialog} .o_field_widget[name='name'] input", ctx.raffle_name
    )
    _select_option(
        browser,
        f"{dialog} .o_field_widget[name='copy_strategy'] select",
        "present_only",
    )
    browser.click(".modal button[name='action_start']")
    browser.wait(
        lambda _d: not browser.visible(".modal .o_form_view"),
        "the wizard stays open",
    )
    browser.find(".o_form_view .o_raffle_wheel")
    ctx.raffle_id = browser.record_id()
    check(ctx.raffle_id, f"no raffle id in {browser.driver.current_url}")
    browser.open_tab("settings")
    browser.set_field("spin_duration", SPIN_SECONDS)
    browser.set_field("spin_turns", SPIN_TURNS)
    browser.set_checkbox("show_fireworks", False)
    browser.set_checkbox("notify_winner_auto", True)
    browser.set_checkbox("announce_channel_auto", True)
    browser.set_many2one("announce_channel_id", ctx.channel_name)
    message = browser.form_field("announce_channel_message", "textarea")
    check(message.get_attribute("value"), "the channel message is empty")
    browser.save_form()
    raffle = ctx.rpc.read_one(
        "event.raffle",
        ctx.raffle_id,
        [
            "event_id",
            "participant_count",
            "announce_channel_auto",
            "announce_channel_id",
            "announce_channel_message",
            "notify_winner_auto",
            "claim_auto_send",
            "spin_duration",
        ],
    )
    check(
        raffle["event_id"][0] == ctx.event_id
        and raffle["participant_count"] == len(ctx.attendees),
        f"the raffle has {raffle['participant_count']} participants",
    )
    check(
        raffle["announce_channel_auto"]
        and raffle["announce_channel_id"][0] == ctx.channel_id
        and raffle["notify_winner_auto"]
        and raffle["claim_auto_send"],
        f"the raffle settings are {raffle}",
    )
    ctx.records["raffle_id"] = ctx.raffle_id
    return (
        f"raffle {ctx.raffle_id} with {raffle['participant_count']}"
        f" participants, announced in {ctx.channel_name}, winner notified,"
        f" prize link sent, spin {raffle['spin_duration']} s"
    )


# ----------------------------------------------------------------------
# 5. Approval
# ----------------------------------------------------------------------
def _record_stock(ctx):
    """Setup: the organizer records the units received, through the
    "Update Quantity" wizard of the product (stock.change.product.qty),
    which sets the stock of the company's warehouse."""
    rpc = ctx.rpc
    for prize in ctx.prizes:
        wizard_id = rpc.call(
            "stock.change.product.qty",
            "create",
            {
                "product_id": prize["product_id"],
                "product_tmpl_id": prize["template_id"],
                "new_quantity": PRIZE_QTY,
            },
        )
        rpc.call("stock.change.product.qty", "change_product_qty", [wizard_id])


def _shop_cards(browser, names):
    """{name: stock badge number} of the shop cards of `names` shown."""
    cards = {}
    for card in browser.visible(".oe_product, .oe_product_cart"):
        titles = card.find_elements(
            By.CSS_SELECTOR, ".o_wsale_products_item_title"
        )
        if not titles:
            continue
        title = browser.text(titles[0])
        if title not in names:
            continue
        badges = card.find_elements(By.CSS_SELECTOR, ".o_raffle_shop_stock")
        cards[title] = (
            lib.number_in(browser.text(badges[0])) if badges else None
        )
    return cards


def _open_sponsored_category(ctx):
    """In the shop, click the Sponsored category."""
    browser = ctx.browser
    browser.get("/shop")
    category = ctx.sponsored_category_id
    link = browser.find(
        f"a[href*='/shop/category/'][href$='-{category}'],"
        f" a[href$='/shop/category/{category}']",
        visible=False,
    )
    browser.click(link)
    browser.wait(
        lambda d: f"-{category}" in d.current_url
        or f"category={category}" in d.current_url,
        "the shop does not open the Sponsored category",
    )
    # The category keeps the prizes of every run: the search of the shop
    # narrows it to this run's, which a first page always holds.
    search = browser.find(
        "form.o_wsale_products_searchbar_form input[name=search]"
    )
    browser.type_into(search, ctx.suffix)
    search.send_keys(Keys.ENTER)
    browser.wait(
        lambda d: "search=" in d.current_url,
        "the shop search does not apply",
    )


def step_approve(ctx):
    browser = ctx.browser
    browser.get(
        "/odoo/action-event_raffle_prize_sponsor"
        ".action_event_raffle_prize_to_review"
    )
    search = browser.find(".o_searchview_input")
    browser.type_into(search, ctx.suffix)
    search.send_keys(Keys.ENTER)
    browser.wait(
        lambda _d: len(browser.visible(".o_list_view .o_data_row"))
        == len(ctx.prizes),
        f"the review list does not show the {len(ctx.prizes)} prizes",
    )
    browser.shot_extra("to_review")
    for remaining in range(len(ctx.prizes), 0, -1):
        rows = browser.visible(".o_list_view .o_data_row")
        check(len(rows) == remaining, f"{len(rows)} prizes left to review")
        browser.click(rows[0].find_element(By.CSS_SELECTOR, "td.o_data_cell"))
        browser.click_button("action_raffle_sponsor_approve")
        browser.wait(
            lambda _d: not browser.visible(
                "button[name='action_raffle_sponsor_approve']"
            ),
            "the prize stays to approve",
        )
        browser.click(".o_breadcrumb .breadcrumb-item a")
        browser.wait(
            lambda _d, n=remaining - 1: len(
                browser.visible(".o_list_view .o_data_row")
            )
            == n,
            "the approved prize stays in the review list",
        )
    ctx.sponsored_category_id = ctx.rpc.ref(
        "event_raffle_prize_sponsor.public_category_sponsored"
    )
    rows = ctx.rpc.call(
        "product.template",
        "read",
        [p["template_id"] for p in ctx.prizes],
        [
            "name",
            "raffle_sponsor_state",
            "active",
            "is_published",
            "public_categ_ids",
        ],
    )
    for row in rows:
        check(
            row["raffle_sponsor_state"] == "approved"
            and row["active"]
            and row["is_published"]
            and ctx.sponsored_category_id in row["public_categ_ids"],
            f"after the approval, {row}",
        )
    _record_stock(ctx)
    browser.logout()
    _open_sponsored_category(ctx)
    names = {p["name"] for p in ctx.prizes}

    def listed(_driver):
        found = _shop_cards(browser, names)
        return found if set(found) == names else False

    cards = browser.wait(
        listed, "the Sponsored category does not list the 6 prizes"
    )
    check(
        all(stock == PRIZE_QTY for stock in cards.values()),
        f"stock badges of the prizes: {cards}",
    )
    browser.shot_extra("shop_sponsored")
    ctx.records["sponsored_category_id"] = ctx.sponsored_category_id
    return (
        f"{len(rows)} prizes approved (UI), {PRIZE_QTY} units each in stock"
        " (setup); the Sponsored category of /shop lists them with"
        f" {PRIZE_QTY} left (UI)"
    )


# ----------------------------------------------------------------------
# 6. Draws
# ----------------------------------------------------------------------
def _spin(ctx, band):
    browser = ctx.browser
    select = browser.find(".o_raffle_wheel select.o_raffle_prize_band")
    Select(select).select_by_value(str(band["id"]))
    before = ctx.rpc.call(
        "event.raffle.draw",
        "search_count",
        [("raffle_id", "=", ctx.raffle_id)],
    )
    browser.click(".o_raffle_wheel .o_raffle_spin")
    # Until the spin starts, the toolbar still shows the previous winner
    # with the band selector enabled. The spin is over once the raffle
    # holds one more draw AND the toolbar, its selector enabled again,
    # shows that draw's winner: the previous state matches neither.
    state = {}

    def spun(_driver):
        draws = ctx.rpc.call(
            "event.raffle.draw",
            "search_read",
            [("raffle_id", "=", ctx.raffle_id)],
            fields=["sequence", "winner_name", "partner_id", "band_id"],
            order="sequence",
        )
        state["draws"] = draws
        if len(draws) != before + 1:
            return False
        if not browser.visible(
            ".o_raffle_wheel select.o_raffle_prize_band:enabled"
        ):
            return False
        shown = browser.visible(".o_raffle_wheel .o_raffle_winner")
        state["shown"] = browser.text(shown[0]) if shown else ""
        return draws[-1]["winner_name"] in state["shown"] and draws[-1]

    try:
        draw = browser.wait(
            spun, "the wheel shows no winner", timeout=ctx.args.timeout + 30
        )
    except TimeoutException:
        draws = state.get("draws") or []
        check(len(draws) == before + 1, f"{len(draws)} draws after a spin")
        raise lib.StepFailed(
            f"the wheel shows {state.get('shown')!r}, the draw holds"
            f" {draws[-1]['winner_name']!r}"
        ) from None
    check(
        draw["band_id"] and draw["band_id"][0] == band["id"],
        f"draw {draw['sequence']} has the category {draw['band_id']}",
    )
    return draw


def step_draws(ctx):
    browser = ctx.browser
    browser.login(ctx.args.admin_login, lib.admin_password())
    browser.get(
        f"/odoo/action-event_raffle.action_event_raffle/{ctx.raffle_id}"
    )
    browser.find(".o_raffle_wheel canvas")
    ctx.draws = []
    attendees = {a["partner_id"]: a for a in ctx.attendees}
    for band in ctx.bands:
        draw = _spin(ctx, band)
        winner = attendees.get(draw["partner_id"] and draw["partner_id"][0])
        check(winner, f"draw {draw['sequence']} went to {draw['partner_id']}")
        ctx.draws.append({"draw": draw, "band": band, "winner": winner})
    winners = {d["winner"]["login"] for d in ctx.draws}
    check(len(winners) == len(ctx.draws), "a winner was drawn twice")
    ctx.records["draws"] = [
        {
            "id": d["draw"]["id"],
            "band": d["band"]["letter"],
            "winner_login": d["winner"]["login"],
        }
        for d in ctx.draws
    ]
    return ", ".join(
        f"#{d['draw']['sequence']} {d['band']['letter']}:"
        f" {d['draw']['winner_name']}"
        for d in ctx.draws
    )


# ----------------------------------------------------------------------
# 7. Discuss
# ----------------------------------------------------------------------
def _expected_messages(ctx):
    rpc = ctx.rpc
    raffle = rpc.read_one(
        "event.raffle", ctx.raffle_id, ["name", "announce_channel_message"]
    )
    expected = []
    for item in ctx.draws:
        draw = rpc.call(
            "event.raffle.draw",
            "read",
            [item["draw"]["id"]],
            [
                "sequence",
                "winner_name",
                "claim_link_url",
                "claim_link_state",
                "notified",
                "notification_count",
            ],
            context={"lang": ctx.lang},
        )[0]
        check(
            draw["claim_link_state"] == "open" and draw["claim_link_url"],
            f"draw {draw['sequence']} has its link {draw['claim_link_state']}",
        )
        check(
            draw["notified"] and draw["notification_count"] >= 1,
            f"the winner of draw {draw['sequence']} was not notified",
        )
        item["link"] = draw["claim_link_url"]
        values = {
            "winner": draw["winner_name"],
            "number": str(draw["sequence"]),
            "raffle": raffle["name"],
            "prize": item["band"]["name"],
            "link": draw["claim_link_url"],
        }
        text = render_message(raffle["announce_channel_message"], values)
        expected.append((lib.squash(text), draw["claim_link_url"]))
    return expected


def _channel_posts(ctx):
    """Authors of the messages posted in the channel, over RPC, oldest
    first: the channel is new to the run, so it holds the draws' only."""
    rows = ctx.rpc.call(
        "mail.message",
        "search_read",
        [
            ("model", "=", "discuss.channel"),
            ("res_id", "=", ctx.channel_id),
            ("message_type", "=", "comment"),
        ],
        fields=["author_id"],
        order="id",
    )
    return [row["author_id"] and row["author_id"][0] for row in rows]


def step_discuss(ctx):
    browser = ctx.browser
    expected = _expected_messages(ctx)
    bot = ctx.rpc.read_one(
        "res.partner", ctx.rpc.ref("base.partner_root"), ["name"]
    )
    authors = _channel_posts(ctx)
    check(
        len(authors) == len(expected),
        f"the channel holds {len(authors)} posts for {len(expected)} draws",
    )
    check(
        all(author == bot["id"] for author in authors),
        f"posts of the channel written by {authors}, not {bot['name']}",
    )
    browser.get(f"/odoo/discuss?active_id=discuss.channel_{ctx.channel_id}")

    def shown(_driver):
        """[(text, [href], author)] of the messages of the thread; the
        author is None on a message the thread groups under the one
        above it, which shows no author of its own."""
        messages = []
        for message in browser.visible(".o-mail-Thread .o-mail-Message"):
            bodies = message.find_elements(
                By.CSS_SELECTOR, ".o-mail-Message-body"
            )
            if not bodies:
                continue
            links = bodies[0].find_elements(By.CSS_SELECTOR, "a[href]")
            names = message.find_elements(
                By.CSS_SELECTOR, ".o-mail-Message-author"
            )
            messages.append(
                (
                    browser.text(bodies[0]),
                    [a.get_attribute("href") for a in links],
                    browser.text(names[0]) if names else None,
                )
            )
        texts = [text for text, _links, _author in messages]
        if all(texts.count(text) == 1 for text, _link in expected):
            return messages
        return False

    try:
        messages = browser.wait(shown, "the channel misses a draw message")
    except TimeoutException:
        texts = [
            browser.text(b)
            for b in browser.visible(".o-mail-Thread .o-mail-Message-body")
        ]
        raise lib.StepFailed(
            f"messages expected once each {[t for t, _l in expected]},"
            f" shown {texts}"
        ) from None
    check(
        len(messages) == len(expected),
        f"the thread shows {len(messages)} messages for {len(expected)}"
        f" draws: {[text for text, _links, _author in messages]}",
    )
    authors_shown = [a for _t, _l, a in messages if a is not None]
    check(
        authors_shown and all(a == bot["name"] for a in authors_shown),
        f"the thread shows the authors {authors_shown}, not {bot['name']}",
    )
    links = {text: hrefs for text, hrefs, _author in messages}
    for text, link in expected:
        check(link in links[text], f"the message {text!r} links {links[text]}")
    return (
        f"{len(expected)} messages in {ctx.channel_name}, one per draw, each"
        f" by {bot['name']} (UI and RPC) as the raffle's template renders"
        " it, with the prize link; each winner notified (RPC)"
    )


# ----------------------------------------------------------------------
# 8-10. Claims
# ----------------------------------------------------------------------
def _sign_in_through_link(ctx, winner, link):
    """Open the prize link signed out: it asks to sign in, then comes
    back to the link, which opens the shop."""
    browser = ctx.browser
    browser.get(link_path(link))
    browser.find("form.oe_login_form input[name=login]")
    check(
        "/web/login" in browser.driver.current_url,
        f"the link opens {browser.path()} before the sign-in",
    )
    browser.type_into("form.oe_login_form input[name=login]", winner["login"])
    browser.type_into(
        "form.oe_login_form input[name=password]",
        ctx.passwords[winner["login"]],
    )
    browser.click("form.oe_login_form button[type=submit]")
    browser.wait(
        lambda _d: browser.path().startswith("/shop"),
        "the prize link does not lead to the shop after the sign-in",
    )
    browser.check_session_db()


def _checkout(ctx, prize):
    browser = ctx.browser
    title = browser.find_text(".o_wsale_products_item_title a", prize["name"])
    browser.click(title)
    browser.click("#add_to_cart")
    browser.find_text(".toast-body", prize["name"])
    browser.get("/shop/cart")
    browser.find_text("#cart_products", prize["name"])
    browser.click("a[href^='/shop/checkout']")
    browser.find("#o_delivery_methods input[name='o_delivery_radio']:checked")
    browser.click("a[href^='/shop/confirm_order']")
    browser.click(
        "form[name='o_wsale_confirm_order']"
        " button[name='o_payment_submit_button']"
    )
    browser.wait(
        lambda _d: browser.path().startswith("/raffle/prize/done"),
        "the checkout does not end on the confirmation page",
    )
    browser.find_text(".o_raffle_claim_done_prize", prize["name"])


def _claim(ctx, index):
    item = ctx.draws[index]
    mode, choice = WINNER_PLANS[index]
    band = item["band"]
    winner = item["winner"]
    group = [p for p in ctx.prizes if p["band"]["id"] == band["id"]]
    prize = group[choice]
    browser = ctx.browser
    browser.logout()
    if mode == "link":
        _sign_in_through_link(ctx, winner, item["link"])
    else:
        browser.login(winner["login"], ctx.passwords[winner["login"]], "/shop")
    banner = browser.find(".o_raffle_claim_banner")
    check(
        band["name"] in browser.text(banner),
        f"the banner reads {browser.text(banner)!r}",
    )
    names = {p["name"] for p in ctx.prizes}
    cards = _shop_cards(browser, names)
    check(
        set(cards) == {p["name"] for p in group},
        f"the winner of {band['letter']} sees {sorted(cards)}",
    )
    check(
        cards[prize["name"]] == PRIZE_QTY,
        f"{prize['name']} shows {cards[prize['name']]} left",
    )
    browser.shot_extra("shop")
    _checkout(ctx, prize)
    draw = ctx.rpc.read_one(
        "event.raffle.draw",
        item["draw"]["id"],
        ["claim_state", "prize_product_id", "claim_link_state"],
    )
    check(
        draw["claim_state"] == "reserved"
        and draw["prize_product_id"]
        and draw["prize_product_id"][0] == prize["product_id"],
        f"after the checkout, the draw holds {draw}",
    )
    item["prize"] = prize
    return (
        f"{winner['name']} ({band['letter']}, through"
        f" {'the prize link' if mode == 'link' else '/shop'}) took"
        f" {prize['name']}: claim reserved, link {draw['claim_link_state']}"
    )


def make_claim_step(index):
    def step(ctx):
        return _claim(ctx, index)

    return step


# ----------------------------------------------------------------------
# 11. Results
# ----------------------------------------------------------------------
def step_results(ctx):
    browser = ctx.browser
    browser.logout()
    _open_sponsored_category(ctx)
    names = {p["name"] for p in ctx.prizes}
    taken = {item["prize"]["name"] for item in ctx.draws}
    expected = {
        name: PRIZE_QTY - 1 if name in taken else PRIZE_QTY for name in names
    }
    try:
        browser.wait(
            lambda _d: _shop_cards(browser, names) == expected,
            "stock badges",
        )
    except TimeoutException:
        raise lib.StepFailed(
            f"stock badges {_shop_cards(browser, names)}, expected {expected}"
        ) from None
    browser.shot_extra("shop_stock")
    browser.get(f"/raffle/winners/{ctx.event_id}")
    browser.find(".o_raffle_winners_list")
    for item in ctx.draws:
        winner_card = browser.find(
            f"li.o_raffle_winner[data-winner='{item['draw']['id']}']"
        )
        name = browser.text(
            winner_card.find_element(By.CSS_SELECTOR, ".o_raffle_winner_name")
        )
        prize = winner_card.find_element(
            By.CSS_SELECTOR, ".o_raffle_winner_prize"
        )
        check(
            name == item["winner"]["name"],
            f"the winners page names {name!r}",
        )
        check(
            prize.get_attribute("data-status") == "chosen"
            and item["prize"]["name"] in browser.text(prize),
            f"the winners page gives {browser.text(prize)!r}"
            f" ({prize.get_attribute('data-status')})",
        )
    return (
        "stock badges went down by one for the 3 prizes taken;"
        f" /raffle/winners/{ctx.event_id} shows each winner with the"
        " chosen prize"
    )


# ----------------------------------------------------------------------
# Scenario
# ----------------------------------------------------------------------
def build_scenario(args):
    """The scenario and its shared state, ready for run()."""
    scenario = lib.Scenario("raffle sponsored prizes", args)
    steps = (
        ("setup", "accounts, channel, token categories", "setup", step_setup),
        (
            "event",
            "organizer creates the event with its sponsor",
            "UI+setup",
            step_event,
        ),
        ("portal", "sponsor adds 6 prizes from the portal", "UI", step_portal),
        ("raffle", "organizer adds the raffle", "UI", step_raffle),
        (
            "approve",
            "organizer approves the portal prizes",
            "UI+setup",
            step_approve,
        ),
        ("draws", "organizer draws A, B and C on the wheel", "UI", step_draws),
        (
            "discuss",
            "draw messages in the Discuss channel",
            "UI",
            step_discuss,
        ),
    )
    for key, title, kind, func in steps:
        scenario.step(key, title, kind)(func)
    for index, letter in enumerate("ABC"):
        scenario.step(
            f"claim_{letter}",
            f"winner of group {letter} takes a prize with the token",
        )(make_claim_step(index))
    scenario.step("results", "stock badges and winners page")(step_results)
    ctx = types.SimpleNamespace(
        args=args,
        evidence=lib.Evidence(args.evidence_dir),
        suffix=lib.run_suffix(),
        passwords={},
        records={},
        notes=[],
    )
    return scenario, ctx


def main(argv=None):
    parser = lib.build_parser(__doc__)
    args = parser.parse_args(argv)
    scenario, ctx = build_scenario(args)
    try:
        return scenario.run(ctx)
    finally:
        ctx.evidence.close()


if __name__ == "__main__":
    sys.exit(main())
