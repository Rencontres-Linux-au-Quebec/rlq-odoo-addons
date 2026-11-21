#!/usr/bin/env python3
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. (http://www.gnu.org/licenses/agpl)
"""End-to-end scenario of the raffle prizes in the event day web app.

It plays the sponsored prize scenario of event_raffle_prize_sponsor
(selenium/e2e_raffle_sponsor_prize.py: sponsor portal, event, raffle,
approval, draws, Discuss, token checkout, winners page) and adds the
checks of event_webapp_plan_raffle at the two moments that matter:

- webapp_day (setup, after the raffle): an event day of the web app,
  open now, with the event and the raffle listed on it;
- webapp_drawn (UI, after the Discuss check): the raffle block of
  /webapp_event/<day> lists the 3 winners with their token category and
  "prize to choose"; a winner's "My prize" card ("Mon prix" in French)
  holds "Choose my prize" with that winner's prize link; the attendee
  who won nothing has no card;
- webapp_claimed (UI, after the results): the raffle block gives each
  winner's chosen prize, and the winner's card shows the reserved prize,
  without the button.

Exit code: 0 every step passes, 1 a step fails (its screenshot and its
page are in the evidence folder), 2 the tool fails or a guard refuses.
"""

import datetime
import importlib
import os
import sys
from pathlib import Path

__version__ = "1.2.20261121.021753"

# Folder of the sponsored prize scenario: the selenium folder of the
# event_raffle_prize_sponsor module beside this one, unless the
# environment variable or --raffle-e2e-dir names another.
RAFFLE_E2E_DIR_ENV = "RAFFLE_E2E_DIR"
CHANGELOG = Path(__file__).resolve().parent / "CHANGELOG.md"
PROGRAM = "e2e_webapp_raffle_prize"
# Configuration files, read in this order: the last one read wins, and
# the command line wins over both.
CONFIG_FILES = (
    Path("/etc/default") / f"{PROGRAM}.conf",
    Path.home() / f".{PROGRAM}.conf",
)
# Options a configuration file may not set: the target must be given on
# the command line, every time, and the scenario folder is imported
# before the files are read.
CONFIG_REFUSED = {
    "url",
    "db",
    "allow_non_neutralized_database",
    "raffle_e2e_dir",
}


def default_raffle_dir():
    return os.environ.get(RAFFLE_E2E_DIR_ENV) or str(
        Path(__file__).resolve().parents[2]
        / "event_raffle_prize_sponsor"
        / "selenium"
    )


def load_raffle_scenario(folder):
    """Import e2e_raffle_sponsor_prize from `folder`; None when absent."""
    folder = str(Path(folder).resolve())
    if not os.path.isfile(os.path.join(folder, "e2e_raffle_sponsor_prize.py")):
        return None
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module("e2e_raffle_sponsor_prize")


def print_changelog():
    """Print CHANGELOG.md, version headings in colour on a terminal."""
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    try:
        text = CHANGELOG.read_text(encoding="utf-8")
    except OSError as error:
        print(f"no changelog: {error}", file=sys.stderr)
        return 2
    try:
        for line in text.splitlines():
            if color and line.startswith("### "):
                line = f"\033[1;36m{line}\033[0m"
            print(line)
    except BrokenPipeError:
        # The reader closed the pipe (head, less): stop quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    return 0


def read_config(parser, files=CONFIG_FILES):
    """Defaults of `parser` from the `name = value` lines of `files`,
    where name is an option without its dashes (window-size or
    window_size). Returns (files read, {name: value} applied). A target
    option (CONFIG_REFUSED) or an unknown name is an error."""
    known = {
        action.dest: action
        for action in parser._actions
        if action.option_strings and action.dest != "help"
    }
    read, values = [], {}
    for path in files:
        if not path.is_file():
            continue
        read.append(str(path))
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name, _sep, value = (part.strip() for part in line.partition("="))
            dest = name.replace("-", "_")
            if dest in CONFIG_REFUSED or dest not in known or not _sep:
                parser.error(f"{path}:{number}: {name!r} cannot be set here")
            if known[dest].nargs == 0:
                values[dest] = value.lower() in ("1", "true", "yes", "on")
            else:
                values[dest] = (
                    known[dest].type(value) if known[dest].type else value
                )
    parser.set_defaults(**values)
    return read, values


# ----------------------------------------------------------------------
# Steps
# ----------------------------------------------------------------------
def step_webapp_day(ctx):
    """Setup: an event day open now, listing the event and the raffle."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    fmt = "%Y-%m-%d %H:%M:%S"
    ctx.webapp_id = ctx.rpc.call(
        "event.webapp",
        "create",
        {
            "name": f"Journée Exemple {ctx.suffix}",
            "date_start": (now - datetime.timedelta(hours=1)).strftime(fmt),
            "date_end": (now + datetime.timedelta(hours=8)).strftime(fmt),
            "event_ids": [(6, 0, [ctx.event_id])],
            "raffle_ids": [(6, 0, [ctx.raffle_id])],
        },
    )
    ctx.records["webapp_id"] = ctx.webapp_id
    return f"event day {ctx.webapp_id} open now, with the event and the raffle"


def _home(ctx, attendee):
    """Sign `attendee` in and open the home page of the day."""
    browser = ctx.browser
    browser.logout()
    home = f"/webapp_event/{ctx.webapp_id}"
    browser.login(attendee["login"], ctx.passwords[attendee["login"]], home)
    browser.find(".o_ewp_raffles_card .o_ewp_raffles")
    return home


def _raffle_draws(ctx):
    """{draw id: (winner text, prize text, prize status)} of the raffle
    block, for the drawn draws."""
    browser = ctx.browser
    lib = ctx.lib
    found = {}
    for item in browser.visible(
        ".o_ewp_raffles li.o_ewp_draw.o_ewp_draw_done"
    ):
        draw_id = int(item.get_attribute("data-ewp-draw-id"))
        prize = item.find_element(lib.By.CSS_SELECTOR, ".o_ewp_draw_prize")
        winner = item.find_element(lib.By.CSS_SELECTOR, ".o_ewp_winner_name")
        found[draw_id] = (
            browser.text(winner),
            browser.text(prize),
            prize.get_attribute("data-ewp-prize-status"),
        )
    return found


def _check_block(ctx, status):
    """The raffle block shows every draw of ctx.draws with `status`."""
    lib = ctx.lib
    browser = ctx.browser

    def expected_prize(item):
        if status == "chosen":
            return item["prize"]["name"]
        return item["band"]["name"]

    def complete(_driver):
        found = _raffle_draws(ctx)
        for item in ctx.draws:
            row = found.get(item["draw"]["id"])
            if not row or row[2] != status:
                return False
        return found

    try:
        found = browser.wait(complete, f"the raffle block is not {status}")
    except lib.TimeoutException:
        raise lib.StepFailed(
            f"raffle block {_raffle_draws(ctx)}, every draw {status} expected"
        ) from None
    for item in ctx.draws:
        winner, prize, _status = found[item["draw"]["id"]]
        lib.check(
            winner == item["winner"]["name"],
            f"the raffle block names {winner!r}",
        )
        lib.check(
            expected_prize(item) in prize,
            f"the raffle block gives {prize!r} for {winner}",
        )


def _card_item(ctx, item):
    css = (
        "#ewp_prize_box:not([hidden]) #ewp_prize_card"
        f" .ewp_prize_item[data-ewp-prize-draw='{item['draw']['id']}']"
    )
    return ctx.browser.find(css)


def step_webapp_drawn(ctx):
    lib = ctx.lib
    browser = ctx.browser
    item = ctx.draws[0]
    _home(ctx, item["winner"])
    _check_block(ctx, "to_choose")
    card = _card_item(ctx, item)
    lib.check(
        card.get_attribute("data-ewp-prize-state") == "open",
        f"the card is {card.get_attribute('data-ewp-prize-state')}",
    )
    button = card.find_element(lib.By.CSS_SELECTOR, "a.ewp_prize_choose")
    lib.check(
        button.get_attribute("href") == item["link"],
        "the card's button is not the winner's prize link",
    )
    browser.shot_extra("winner")
    winners = {d["winner"]["login"] for d in ctx.draws}
    loser = next(a for a in ctx.attendees if a["login"] not in winners)
    _home(ctx, loser)
    lib.check(
        browser.js(
            "const box = document.getElementById('ewp_prize_box');"
            "return !box || box.hidden;"
        ),
        f"{loser['name']}, who won nothing, has a prize card",
    )
    return (
        f"raffle block: {len(ctx.draws)} winners, category and prize to"
        f" choose; {item['winner']['name']}'s card links the prize link;"
        f" {loser['name']} has no card"
    )


def step_webapp_claimed(ctx):
    lib = ctx.lib
    item = ctx.draws[0]
    _home(ctx, item["winner"])
    _check_block(ctx, "chosen")
    card = _card_item(ctx, item)
    lib.check(
        card.get_attribute("data-ewp-prize-state") == "reserved",
        f"the card is {card.get_attribute('data-ewp-prize-state')}",
    )
    name = card.find_element(lib.By.CSS_SELECTOR, ".ewp_prize_name")
    lib.check(
        item["prize"]["name"] in ctx.browser.text(name),
        f"the card gives {ctx.browser.text(name)!r}",
    )
    lib.check(
        not card.find_elements(lib.By.CSS_SELECTOR, "a.ewp_prize_choose"),
        "the card still offers to choose the prize",
    )
    return (
        "raffle block: each winner with the chosen prize;"
        f" {item['winner']['name']}'s card shows {item['prize']['name']}"
        " reserved"
    )


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--changelog" in argv:
        return print_changelog()
    raffle_dir = default_raffle_dir()
    for index, arg in enumerate(argv):
        if arg == "--raffle-e2e-dir" and index + 1 < len(argv):
            raffle_dir = argv[index + 1]
        elif arg.startswith("--raffle-e2e-dir="):
            raffle_dir = arg.split("=", 1)[1]
    base = load_raffle_scenario(raffle_dir)
    if base is None:
        print(
            f"e2e_raffle_sponsor_prize.py not found in {raffle_dir}: give"
            f" --raffle-e2e-dir or {RAFFLE_E2E_DIR_ENV}",
            file=sys.stderr,
        )
        return 2
    lib = base.lib
    parser = lib.build_parser(__doc__)
    parser.add_argument(
        "--changelog",
        action="store_true",
        help="Print the changes of this program and exit.",
    )
    parser.add_argument(
        "--raffle-e2e-dir",
        default=raffle_dir,
        help="Folder of e2e_raffle_sponsor_prize.py (default: the selenium"
        " folder of event_raffle_prize_sponsor, or"
        f" {RAFFLE_E2E_DIR_ENV}).",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    read, values = read_config(parser)
    args = parser.parse_args(argv)
    scenario, ctx = base.build_scenario(args)
    ctx.evidence.log(
        f"{PROGRAM} {__version__}; configuration read: "
        + (", ".join(read) if read else "none")
        + (f" ({', '.join(sorted(values))})" if values else "")
    )
    ctx.evidence.log(
        f"Options: --url {args.url} --db {args.db} timeout {args.timeout} s,"
        f" {'window' if args.no_headless else 'headless'},"
        f" video {'on' if args.video else 'off'}"
    )
    scenario.name = "raffle prizes in the event day web app"
    ctx.lib = lib
    steps = (
        (
            "raffle",
            "webapp_day",
            "event day of the web app",
            "setup",
            step_webapp_day,
        ),
        (
            "discuss",
            "webapp_drawn",
            "winners in the web app, prize to choose",
            "UI",
            step_webapp_drawn,
        ),
        (
            "results",
            "webapp_claimed",
            "winners in the web app, prize chosen",
            "UI",
            step_webapp_claimed,
        ),
    )
    for after, key, title, kind, func in steps:
        scenario.insert_after(after, lib.Step(key, title, kind, func))
    try:
        return scenario.run(ctx)
    finally:
        ctx.evidence.close()


if __name__ == "__main__":
    sys.exit(main())
