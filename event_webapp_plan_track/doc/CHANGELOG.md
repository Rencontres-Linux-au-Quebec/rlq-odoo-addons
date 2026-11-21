# Changelog - event_webapp_plan_track

## 18.0.1.1.0

**Short title:** a session that starts plays a "speak" cameo near the agenda.

**Reason for the request:** the animated actors of the pages reacted to a raffle, a conference and the opening, not to the program: a talk that starts now shows the speaker at the microphone.

**Changes:**

- `static/src/webapp/agenda.js`: when a session starts while the page is open (on a room page, a session of that room), `window.ewpCameo.play("speak", {near})` runs once, 400 ms after the states are painted, near the room block or the agenda card; several starts at the same moment play one cameo; header comment.
- `tests/test_selenium_agenda.py`: `test_session_start_is_announced_in_the_room` also expects the "speak" cameo of the start.
- `README.md`: the cameo of a session start.

**Bugs fixed:** none.

**Safeguards and edge cases:** without the cameo engine nothing plays; the engine plays nothing while the animations are paused, in text-only mode or with no free spot; the states found when the page loads play nothing.

**Checks:** full suite of the three modules on a fresh database, Selenium and axe-core included.

**Action required:** update the module (`-u event_webapp_plan_track`).

## 18.0.1.0.1

**Short title:** the filter by room hides the sessions of a shared slot; no filter with a single busy room.

**Reason for the request:** review of the module: a session outside the chosen room stayed on screen when another session of the same start was shown, and a choice kept in the address could hide sessions with no way to show them again.

**Changes:**

- `static/src/webapp/agenda.scss`: `.ewp_track_session[hidden]` gets `display: none`.
- `controllers/main.py`: `_ewp_agenda_values()` reads the choice of the address only when the filter is offered (two busy rooms or more).
- `tests/test_controllers.py`: `test_filter_kept_in_address_with_one_busy_room`.
- `tests/test_selenium_agenda.py`: `test_filter_hides_a_session_that_shares_its_slot`; `test_session_start_is_announced_in_the_room` moves the session later once it runs, so it starts again, and checks the second start is sent but not said.
- `README.md`: filter and tests.

**Bugs fixed:**

- Symptom: with two sessions of one start in two rooms, choosing one room left both on screen while the live region said "sessions shown: 1", with or without script. Diagnosis: the author rule `display: flex` of `.ewp_track_session` beats the `[hidden]` rule of the browser, so only the slots left empty disappeared; the hidden session also stayed in the accessibility tree and in the Tab order. Fix: `&[hidden] { display: none; }`.
- Symptom: `?agenda_room=<id>` (bookmark, installed app, display options) with a single busy room hid every session without room, and no "All rooms" button was shown, the form being offered only from two busy rooms. Fix: the choice is ignored when no form is offered.
- The de-duplication of the announcement of a start was not covered: the tab shown again never reaches it. The test now goes through now, later and now again.

**Safeguards and edge cases:** the slot rule is unchanged (hidden when all its sessions are); the JSON route, unfiltered, is unchanged.

**Checks:** combined run (`event_webapp_plan`, `event_webapp_plan_track`, `rlq_event_webapp_plan`) on a database with demo data and generic module alone, Selenium and axe-core included.

**Action required:** update the module (`-u event_webapp_plan_track`).

## 18.0.1.0.0

**Short title:** agenda of the event day web app from the event tracks, rooms tied to track locations.

**Reason for the request:** the program of an event day is published as event tracks on the website (`website_event_track`: tracks with location, speaker and tags). The web app must show that agenda, tied to its rooms, without a second entry of the program, while `event_webapp_plan` stays free of any website dependency.

**Changes:**

- New module, depends on `event_webapp_plan` and `website_event_track`.
- `models/event_webapp_room.py`: `track_location_id` (Many2one `event.track.location`, `ondelete="set null"`) and the constraint `_check_track_location_unique()`: one room per location and per day.
- `models/event_webapp.py`: `track_ids`, computed, never stored: published tracks of the events of the day that overlap its window, not in a cancelled stage, with a start date; `_ewp_track_domain()`, `_ewp_sort_tracks()` (start, then location sequence, then id).
- `controllers/main.py`: `EventWebappTrackController._ewp_page_values()` hands the home and room pages the plain values of the agenda (`agenda_*`): sessions, groups by start, filter by room (`agenda_room`), room lines, room block, JSON data and translated messages of the script; route `/webapp_event/<day>/agenda` (JSON: `signature`, `sessions`, `html`, `room_html`).
- `views/webapp_templates.xml`: home card (slot `webapp_slot_home_cards`), room line (slot `webapp_slot_room_item`), room block (slot `webapp_slot_room_main`), session and block bodies rendered again by the JSON route.
- `views/event_webapp_views.xml`: track location in the room list of the day form, read-only "Agenda" tab.
- `security/ir.model.access.csv`: read access on `event.track.location` for the Event Web App Moderator group.
- `static/src/webapp/agenda.js`: states from the clock (at each start or end, at least every minute, tab shown again), badges and room lines, plan dot, `ewp:session`, announcement of a session that starts in the room of the page, filter in place, program refresh every 5 minutes.
- `static/src/webapp/agenda.scss`: style of the blocks on the custom properties of the pages, text-only mode, no animation.
- `i18n/`: `.pot` and French `fr.po`.
- `README.md`: setup, what the visitor sees, times and states, accessibility, access, theming, tests.

**Bugs fixed:** none (new module).

**Safeguards and edge cases:**

- A track not published, in a cancelled stage (even published again by hand), archived, without date, of an event outside the day, or outside the window never reaches a page nor the JSON route; the description is sanitised again; tags without colour stay internal.
- A location without room shows its name as plain text; a room without location gets no block and no line.
- The JSON route applies the checks of the raffle route: 404 for an unknown or archived day and for a room of another day, 403 outside the window for a visitor, login for an anonymous visitor.
- The states found at load send no event and say nothing; a session that starts in the room of the page is said once; a refresh never replaces a block that holds the focus.
- The filter ignores an unknown room or a room without session; it is shown from two rooms with sessions.
- Times carry their offset to the second, so a short session starts and ends on time in the page.

**Checks:** fresh test database with `event_webapp_plan`, `event_webapp_plan_track` and `rlq_event_webapp_plan`, `EWP_AXE_JS` set, Selenium tests run: model tests (window overlap, publication, cancelled stage, order, one room per location), HTTP tests (card, states, room links, filter without script, room lines, room block, sanitised description, text-only mode, time zone and French times, JSON route access and content), Selenium tests ("Now" and "Next", filter by mouse and keyboard, keyboard way to a room and a description, a short track said once when it starts, `ewp:session` start and end, axe-core on home and room pages, light, dark and text-only); `event_webapp_plan` alone passes its own tests. black, isort, ruff, prettier, comment hygiene check; `.pot` exported, `msgfmt -c` on `fr.po`.

**Action required:** install the module (`-i event_webapp_plan_track`), then give each room its track location (see README.md).
