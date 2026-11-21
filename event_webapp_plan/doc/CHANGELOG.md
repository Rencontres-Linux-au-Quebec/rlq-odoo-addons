# Changelog - event_webapp_plan

## 18.0.1.12.0

**Short title:** raffles of the day pre-filled from the planned date of each raffle or the dates of its event.

**Reason for the request:** adding an event to a day did not add its raffles, each one was listed by hand. Listing every raffle of the event instead would bring the raffles of the other days of a multi-day event, and their winners, into the web app.

**Changes:**

- `models/event_webapp.py`: `raffle_fits_day()`: a non-test raffle of a listed event fits a day when its planned date (`event_raffle`, `date_planned`) falls inside the window, bounds included, or, without planned date, when its event begins and ends inside the window. `create()` and `write()` (on `event_ids`, `date_start`, `date_end`) add, as the current user, the raffles that start to fit, found as superuser and kept when the user may read them; a raffle the same write takes off stays off. `copy()` keeps the raffle list of the original (context key `ewp_no_raffle_fill`). Onchange `_onchange_ewp_raffle_ids()` shows the additions before saving; the non-stored field `ewp_raffle_proposed_ids` remembers them in the form, so a raffle removed by hand is neither proposed again in the same edit nor added back on save. Help of `raffle_ids`.
- `models/event_raffle.py` (new): `create()` and `write()` (on `date_planned`, `event_id`, `is_test`) link the raffle, as superuser, to the days, archived ones included, that it starts to fit.
- `views/event_webapp_views.xml`: hint above the raffle list of the day form, column **Planned Date** in the raffle lists of the day and of the selection dialog.
- `i18n/fr.po`, `i18n/event_webapp_plan.pot`: the new texts.
- `README.md`: Configuration, raffles of the day.
- Tests: `test_raffle_fill.py` (new).

**Safeguards and edge cases:**

- Additions only: nothing leaves a day automatically. A raffle removed by hand comes back only when it stops fitting and fits again (a new event, a new window, a new planned date on another day).
- A test raffle never joins; a test raffle turned real joins the days it fits.
- A change of the dates of an event adds nothing: the pre-fill follows the day and the raffle only.
- The raffle side writes as superuser because the user who saves a raffle seldom may write the days; it only adds that raffle to days that already list its event.

**Checks:** full suite of event_webapp_plan, event_webapp_plan_raffle, event_webapp_plan_track, rlq_event_webapp_plan and event_raffle on a fresh database (browser tests skipped without selenium); each new test fails without the pre-fill; `msgfmt -c` on the catalogues.

**Action required:** update `event_raffle` and the module (`-u event_raffle,event_webapp_plan`). The raffle lists of the existing days do not change: the pre-fill runs at the next change of a day or of a raffle.

## 18.0.1.11.0

**Short title:** short address `/w` of the web app.

**Reason for the request:** `/webapp_event` is long to type and to say on a poster or out loud; a short address leads to the same pages.

**Changes:**

- `controllers/main.py`: `SHORT_ROOT` and the route `webapp_short()`: `/w` and `/w/<day>` (GET, `auth="public"`) answer a 302 redirect to `/webapp_event` and `/webapp_event/<day>`, the query string kept as is; module docstring.
- `README.md`: the short address.
- Tests: `test_controllers.py` (`test_short_address_redirects_to_the_web_app`).

**Bugs fixed:** none.

**Safeguards and edge cases:** the route reads nothing and checks nothing: the target route sends an anonymous visitor to the login page and back to `/webapp_event`, and checks the day (404, closed page). No route of Odoo 18 or of the addons of the checkout uses `/w`.

**Checks:** full suite of event_webapp_plan, event_webapp_plan_raffle, event_webapp_plan_track and rlq_event_webapp_plan on a fresh database (browser tests skipped without selenium); the new test fails without the route.

**Action required:** restart the server; nothing to update in the database.

## 18.0.1.10.0

**Short title:** "Automatic updates" section: the refresh timers of the blocks at the bottom of the home and room pages.

**Reason for the request:** the blocks of the pages refresh by themselves at different rates (raffles, live rooms, conference), and nothing told the visitor when the data on screen was fetched or when it would be fetched again.

**Changes:**

- `views/webapp_templates.xml`: template `webapp_refresh`, the section `#o_ewp_refresh` ("Automatic updates", `h2`) called by the layout of the home and room pages just above the display options, hidden with its rows; rows `raffles`, `live` and `conference`; template `webapp_refresh_row` (one row: label, `time.o_ewp_refresh_last`, `.o_ewp_refresh_next`); slot `webapp_slot_refresh` for the rows of other modules; header comment.
- `controllers/main.py`: `_ewp_refresh_texts()`, the translated patterns of the rows, in `refresh_texts_json` of every page.
- `static/src/webapp/webapp.js`: the event `ewp:refresh` `{id, state, last, next}`, listened to as soon as the script is evaluated; `setupRefreshBoard()` writes the rows every 500 ms while the tab is visible, "paused" while it is hidden; the raffle, live room and conference refreshers report when they plan, send and get a request (the conference reports the doubled interval of a failing server); delays written with no-break spaces, so "1 min 19 s" never splits; header comment.
- `static/src/webapp/webapp.scss`: the section, a grid of cells with tabular digits that keep one line each, empty or not: below 640 px the label, the last answer and the next request on three lines of the full width, from 640 px on one line, so neither the first answer nor the countdown moves the row or the display options below it; a failed or stopped refresh in the warm colour beside its words.
- `README.md`: the section, the slot `webapp_slot_refresh` and the event `ewp:refresh` in Theming.
- `i18n/fr.po`, `i18n/event_webapp_plan.pot`: the new texts.
- Tests: `test_controllers.py` (`test_automatic_updates_section`, `test_automatic_updates_in_french`), `test_bbb.py` (`test_automatic_updates_rows_of_the_conference`), `test_browser.py` (`test_automatic_updates_count_down`, `test_automatic_updates_keep_their_lines`).

**Bugs fixed:** none.

**Safeguards and edge cases:** no interval, request or pause changes: the refreshers only report their times; the label "Updated ... ago" of the raffle card stays. Without script, or for a block that does not poll (a running meeting in the frame), no row shows. The section is not a live region: the countdown is never announced. A row whose id has no element in the page is ignored, a report of an unknown state keeps the previous one.

**Checks:** suites of `event_webapp_plan`, `event_webapp_plan_raffle`, `event_webapp_plan_track` and `rlq_event_webapp_plan` on a fresh database, 187 tests, 0 failed, axe-core included (the Selenium classes skip without selenium in the Odoo environment); the 10 new tests fail without the change; pages checked in a browser in French, light and dark, at 1280 px and 390 px, rows measured from 320 to 1280 px (no horizontal scroll).

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.9.0

**Short title:** security: BBB secret and meeting choice reserved to the Settings group, room channel access locked, room groups taken back from former moderators.

**Reason for the request:** a security review of the module found four ways around its access design: any logged-in user could forget the BBB secret through RPC, an event Administrator could point a room at any meeting of the BBB server and join it as moderator, a room visitor could open the room channel to anonymous visitors, and a former moderator kept every room chat.

**Changes:**

- `models/res_config_settings.py`: `action_ewp_bbb_forget_secret()` refuses every caller who is not an administrator (`env.is_admin()`, the check of `execute()`), with AccessError. RPC reached it on an empty settings recordset, which no access right covers, and it wrote the parameter with sudo.
- `models/event_webapp_room.py`: `_ewp_bbb_check_meeting_rights()` (Settings group or superuser) and `_ewp_check_bbb_meeting_vals()`, called by `create()` and `write()` after cleaning: outside the Settings group, `bbb_meeting_id` may only be emptied or set to a meeting ID that a room already carries (copied room or day). Help of the field.
- `models/event_webapp_room.py`: `_prepare_create_values()` cleans and checks the values of `create()` once the ORM has added the defaults, so `access_group_id` and `bbb_meeting_id` from a context key `default_<field>` or from a personal `ir.default` pass the same checks as given values.
- `models/event_webapp.py`: `action_open_bbb_meetings()` checks the write right on the day and the Settings group BEFORE calling the server; `action_create_missing_channels()` checks the write right on the day before its sudo work.
- `models/event_webapp_bbb_meetings.py`: `action_assign()` checks the Settings group.
- `views/event_webapp_views.xml`: button **Running BBB meetings** for the Settings group; column `BBB meeting ID` read-only outside it.
- `models/discuss_channel.py` (new): `write()` refuses `group_public_id`, `group_ids` and `active` on a room channel (linked to a room, or restricted to a room group) outside superuser mode and the Settings group.
- `models/res_users.py`: field `ewp_room_visit_group_ids` ("Event web app: rooms entered", Settings group, relation `res_users_ewp_room_visit_rel`); `write()` with `groups_id` or a reified group field calls `_ewp_drop_role_room_groups()` for the users who leave the Moderator group: they lose every room group but their recorded visits. `backfill_room_visits(cr)`.
- `models/res_groups.py`: `write()` with `users` does the same for the users removed from the Moderator group.
- `models/event_webapp_room.py`: `_ewp_grant_access()` records the visit of a user outside the Moderator role.
- `migrations/18.0.1.9.0/post-migrate.py`: `backfill_room_visits()`.
- `i18n/fr.po`, `i18n/event_webapp_plan.pot`: the new texts.
- `README.md`: Access (leaving the Moderator role, locked room channels, Settings group), BigBlueButton (who chooses the meeting).
- Tests: `test_bbb.py` (`test_forget_secret_is_reserved_to_the_administrators`, `test_meeting_id_is_chosen_by_the_settings_group`, `test_meeting_id_from_a_default_is_checked`; the wizard tests run as a Settings user and event Administrator), `test_models.py` (`test_access_group_is_set_by_the_module_only` with defaults, `test_room_channel_access_is_locked`, `test_former_moderator_keeps_only_the_rooms_entered`, `test_room_visits_are_recorded_for_existing_holders`, `test_create_missing_channels_needs_the_write_right`).

**Bugs fixed:**

- Symptom: a portal user wipes the BBB secret, every room loses its API join. Diagnosis: public method, sudo write, no caller check. Fix: `env.is_admin()` check.
- Symptom: an event Administrator without the Settings group joins and controls any meeting of the BBB server. Diagnosis: free meeting ID, join URL signed with the secret, role MODERATOR. Fix: meeting list and new meeting IDs reserved to the Settings group.
- Symptom: an event Administrator creates a room with a foreign meeting ID, or with the group of a deleted room, through a default value. Diagnosis: `create()` checked the caller's values before the ORM added the defaults. Fix: the checks run in `_prepare_create_values()`, on the completed values.
- Symptom: a room visitor (internal user) makes the room chat public, hides it from everybody, or subscribes all employees. Diagnosis: `base.group_user` writes the channels it reads, and `discuss.channel.write()` does not protect these fields. Fix: `discuss.channel.write()` refuses them on room channels.
- Symptom: a former moderator keeps reading every room chat, future days included. Diagnosis: Odoo never removes an implied group. Fix: room groups taken back when the Moderator role goes, visits kept.

**Safeguards and edge cases:**

- The module's own flows run with sudo and keep working: room creation, access group setup, renaming, linking a channel.
- Odoo already refuses a change of `channel_type` or `parent_channel_id` to everybody.
- A room group that another group of the user implies comes back with it.
- A moderator who visited rooms before 18.0.1.9.0 cannot be told apart from the role: leaving the role takes those rooms back too; the backfill records only the users outside the role.
- Meeting IDs set before this version by an Administrator stay; a Settings user should review them.

**Checks:** full suite of event_webapp_plan, event_webapp_plan_raffle, event_webapp_plan_track and rlq_event_webapp_plan on a fresh database (browser tests skipped without selenium); each new test fails without its fix, except `test_create_missing_channels_needs_the_write_right` (hardening: without the check, the moderator was already stopped later by the write right on the room, and the transaction rolled back the sudo work); `msgfmt -c` on the catalogues.

**Action required:** update the module (`-u event_webapp_plan`). A Settings user now assigns the BBB meetings of the rooms.

## 18.0.1.8.0

**Short title:** plan editor: move, resize and rotate the room areas; turned areas on the public plan.

**Reason for the request:** the rooms of a site plan are not all square to the image; the editor could only draw an upright rectangle, and redraw it from scratch to change it.

**Changes:**

- `models/event_webapp_room.py`: field `pos_rotation` ("Rotation (deg)", default 0), angle in degrees, clockwise around the centre of the area; `_ewp_normalize_rotation()` brings it into (-180, 180] with two decimals on create and write (270 gives -90, -180 gives 180, 360 gives 0) and refuses a value that is not a finite number; `_ewp_clean_area_vals()`. The constraint `_check_area()` still reads the box before it turns. A copied day or room keeps the angle.
- `static/src/backend/room_plan_editor.{js,xml,scss}`: the selected area carries a frame with eight resize handles and a rotation knob, turned with the area; a drag inside it moves the area, a handle resizes it in the frame of the area (the opposite corner or side stays on screen), the knob turns it by steps of 15 degrees, 1 degree with Shift, with the angle shown during the drag; a drag elsewhere draws a new area with the angle back to 0. Buttons "Rotate left", "Rotate right" (15 degrees, 1 with Shift), field "Angle" and "Straighten" under the selected room, disabled without area. A moved area is shifted back inside the image, a resized one stops at the edge (its size is capped, the anchor never moves); the layer of the areas clips the turned corners; labels stay level at the centre of their area, as wide as the level line across the turned shape; a click selects the room whose turned shape contains it, and a click inside the selected area selects the topmost other room under the pointer, so a room drawn inside or under the selected one stays reachable. Read-only: areas turned, no handle and no control. Pure helpers exported: `normalizeAngle`, `clampBox`, `boxFrame`, `handlePoint`, `resizeBox`.
- `views/event_webapp_views.xml`: optional column "Rotation (deg)" in the room list, hidden by default.
- `controllers/main.py`: `_ewp_rotate_style()`; the style of a turned area ends with `--ewp-room-rotate:<angle>deg`; the position words still read the centre.
- `static/src/webapp/webapp.scss`: `.o_ewp_hotspot` turns by `--ewp-room-rotate` around its centre (hit test, rings and the corner dot of event_webapp_plan_track follow the turned shape), its number and label turn back and never take the pointer; at rest the label of a turned area is capped to the level line across its centre (container units and `sin()`, `max-width: 100%` without them); `.o_ewp_plan` already clips the corners.
- `i18n/fr.po`, `i18n/event_webapp_plan.pot`: the new texts.
- `README.md`: the editor (draw, move, resize, rotate, keyboard), the stored angle, `--ewp-room-rotate` for themes, the new Selenium tests.
- Tests: `test_models.py` (normalisation, non-finite values refused, constraint on the box before it turns, copy keeps the angle), `test_controllers.py` (style of a turned area, position words unchanged), `test_accessibility.py` (a turned area on the pages audited by axe-core), new `test_selenium_plan.py` (the editor driven with real pointer moves, from the draw to the saved record: a click on the knob writes nothing, a draw over a turned area is upright, handles dragged past the edges stop there, a click selects a room by its turned shape and inside the selected area; the home page draws the area turned, opens the room on a click inside the turned shape only, and its label stays inside that shape without taking the pointer).

**Safeguards and edge cases:**

- The editor writes nothing the server constraint refuses: positions and sizes are rounded to two decimals, the box before it turns stays inside 0..100, and a resize never goes below 1 % of the image.
- A press on a handle that does not move writes nothing; a move or a turn shorter than 4 pixels is a click, so a click on the knob never snaps an angle that is not a multiple of 15.
- The knob may sit above the image for an area at its top edge: the editor leaves room for it above the plan, and the handles live outside the clipped layer of the areas.
- The angle field shows the normalised angle even when the record keeps its value (typing 360 on an upright area shows 0).

**Checks:** full suite of event_webapp_plan, event_webapp_plan_track and rlq_event_webapp_plan on a fresh database, Selenium and axe-core included, and event_webapp_plan alone; `msgfmt -c` on the catalogues.

**Action required:** update the module (`-u event_webapp_plan`). Existing areas get the angle 0 and look as before, except the label of an area in the editor, now centred.

## 18.0.1.7.0

**Short title:** video conference display mode: embedded only on the same site, else a new tab button.

**Reason for the request:** a room whose BigBlueButton server is on another site than the web app showed "Oops, something went wrong" in its frame (401 in the console), while the same join worked in a tab of its own.

**Changes:**

- `models/bbb_client.py`: `same_site(url_a, url_b)` (same scheme, ports ignored, same host or same registrable domain) and `registrable_domain(host)`, on the public suffix list of `tldextract` when installed (bundled copy, no download), else a built-in rule; module docstring.
- `models/event_webapp_room.py`: config parameter `event_webapp_plan.bbb_display` (`auto`, `frame`, `tab`), `_ewp_bbb_display()`, `_ewp_bbb_embed()`; `_ewp_bbb_target()` takes `page_url` and `max_age`, and gives "button" instead of "frame" when the mode refuses the frame, for a running meeting (still `live`, with its join URL) and for a framed conference URL.
- `models/res_config_settings.py`, `views/res_config_settings_views.xml`: selection "Video conference display" next to the server, with its explanation; an unset or unknown parameter reads "Automatic".
- `controllers/main.py`: the room page, `bbb_status` and `bbb_join` pass the origin of the request; `bbb_status` answers `state`, the `data-ewp-bbb-state` the page would render; the join URL of the frame names `bbb_left?frame=1`, any other join `bbb_left`; `bbb_left` without `frame` answers a 303 redirect to the room page with `left=1` after the usual checks; with that marker, a room page that embeds a running meeting renders the block left (`data-ewp-bbb-state` `left`, frame without src, notice and "Join again" shown); announcement `bbb_ended`.
- `views/webapp_templates.xml`: a running meeting behind the button shows "The video conference is live.", a large "Join the video conference" button (new tab) and the hint that the room page and its discussion stay open; the conference URL button gets the same hint; `data-ewp-bbb-live` on the block; the frame block rendered left; the block polls the status route while the meeting runs or the server fails.
- `static/src/webapp/webapp.js`: the status poll reloads the page when the state or the error differs from the rendered one, and says "The conference has ended." when a running meeting stops; `ewp:bbb-state` carries `live`; a block rendered left starts with the focus on "Join again" (held against the chat frame) and the announcement of the leave, and "Join again" drops `left=1` from the address.
- `static/src/webapp/webapp.scss`: styles of the new tab block, larger for a running meeting; no animation.
- `rlq_event_webapp_plan`: see its own changelog (18.0.1.3.2).
- `i18n/fr.po`, `i18n/event_webapp_plan.pot`: the new texts.
- `README.md`: display modes, the same-site rule and why (Lax by default in Chromium, partitioned cookies, Safari), what a server of another site needs for "Always embedded".
- Tests: `test_bbb.py` (same-site rule with both implementations, target per mode for a meeting ID and a conference URL, settings written by the Settings group only, room page behind the button and its status, conference URL per mode, `bbb_left` with and without `frame`, the room page after the redirect of `bbb_left` per display mode and in text-only mode, access checks of both forms), `test_selenium_webapp.py` (running meeting behind the button, then ended; a tab that leaves an embedded meeting stays out of it until "Join again"); the frame tests force "Always embedded", since the fake server is on another site than the test server.

**Bugs fixed:**

- Symptom: the frame of a room shows "Oops, something went wrong" and the console a 401, when the BigBlueButton server is on another site than the web app.
- Diagnosis: the join URL sets the session cookie of the client without `SameSite`; Chromium-based browsers treat it as `Lax` and do not send it in a frame of a page from another site, browsers that block third-party cookies refuse it there unless it is partitioned, and Safari refuses it in any case, so the client loses its session.
- Fix: in the default mode, a server on another site gets the new tab button, where the cookie is first-party.

**Safeguards and edge cases:**

- The rule errs toward "another site": an IP address or a single-label host matches itself only, `http` and `https` are two sites, and the built-in rule takes a short label under a two-letter country code for a public suffix.
- A meeting that ends behind the button brings the waiting notice back; one that starts brings the button or the frame, as the page renders it.
- A tab opened outside the frame comes back to the room page when the visitor leaves the meeting; if that page embeds the meeting, it shows the leave and waits for "Join again" instead of joining again; an outsider or a closed day gets the same answer as before.

**Checks:** full suite of event_webapp_plan, event_webapp_plan_track and rlq_event_webapp_plan on a fresh database, Selenium and axe-core included, and event_webapp_plan alone; `msgfmt -c` on the catalogues.

**Action required:** update the module (`-u event_webapp_plan`). A server on another site now opens in a new tab; to keep the frame, set "Always embedded" and make the BigBlueButton server send its session cookie with `SameSite=None; Secure` (see README.md).

## 18.0.1.6.0

**Short title:** livelier cameo schedule: a first cameo after 2 to 3 s, then one every 4 to 8 s.

**Reason for the request:** with one cameo every 6 to 15 s, a visitor could read a page for a long while without seeing any; the requested rhythm is a first cameo soon after the page opens, then a livelier pace.

**Changes:**

- `static/src/webapp/webapp_cameo.js`: options `firstMinDelay` (2000) and `firstMaxDelay` (3000) for the first cameo of a schedule that starts (page ready, tab shown again, animations resumed); `minDelay` 4000 and `maxDelay` 8000 instead of 6000 and 15000; `configure()` restarts the schedule on the regular delay; header comment.
- `tests/test_selenium_cameo.py`: `test_default_schedule_first_cameo_comes_soon` (default options, first scheduled cameo less than 4.5 s after the tab shows again).
- `README.md`: the schedule and the two new options of `configure()`.

**Bugs fixed:** none.

**Safeguards and edge cases:** the limits are unchanged: one cameo at a time under 640 px, two above, never over a control, a picture or a text, none while the animations are paused or the tab is hidden.

**Checks:** full suite of event_webapp_plan, event_webapp_plan_track and rlq_event_webapp_plan on a fresh database, Selenium and axe-core included.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.5.0

**Short title:** hooks for a module that adds a block: page values, room list and room page slots, announcements from another script.

**Reason for the request:** the agenda of the event tracks (new module `event_webapp_plan_track`) shows a line under each room of the room list, a block on the room page, and announces in the live region the session that starts; the pages offered no place and no way for it.

**Changes:**

- `controllers/main.py`: `_ewp_page_values(page, webapp, tz, room=None)`, empty here, merged last into the values of the home page and of the room page; the `room` value of the room page carries its `id`; module docstring.
- `views/webapp_templates.xml`: slots `webapp_slot_room_item` (inside each link of the room list, after the description) and `webapp_slot_room_main` (last item of the room page, after the chat).
- `static/src/webapp/webapp.scss`: on a wide room page, a block of the room slot spans both columns.
- `static/src/webapp/webapp.js`: listens to `ewp:announce` `{text}` and says it in the shared live region; header comment.
- `tests/test_controllers.py`: the slot test covers the two new slots, one room item per room link, the room block last of the main content.
- `README.md`: the slots, `_ewp_page_values()`, `ewp:announce`.

**Bugs fixed:** none.

**Safeguards and edge cases:**

- Without a module that fills them, the slots render nothing and the hook returns nothing: the pages are unchanged.
- `ewp:announce` goes through the rule of the region against a message repeated within 3 seconds; an event without text says nothing.

**Checks:** see the 18.0.1.0.0 entry of event_webapp_plan_track; the module alone passes its own tests. The `.pot` exported again is unchanged (no new text).

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.4.2

**Short title:** cameos recheck their place on any page change, count shown aria-hidden text, play their exit; motion choice without `submitter`.

**Reason for the request:** a review of 18.0.1.4.1 found four defects in the cameo engine and the motion form, and two weaknesses in the Selenium tests.

**Changes:**

- `static/src/webapp/webapp_cameo.js`: `recheck()` (was `onScroll()`) also runs on `focusin`, on a `MutationObserver` of the body that ignores the changes of the cameo layer (`outsideLayer()`), and on a `ResizeObserver` of the content (`watchPage()`, started with the engine); the text of `aria-hidden` parts counts as an obstacle when it is shown; header comment.
- `static/src/webapp/webapp_cameo.scss`: exit keyframes of their own, `ewp-cameo-rise-out`, `ewp-cameo-slide-left-out`, `ewp-cameo-slide-right-out`, `ewp-cameo-pop-out`.
- `static/src/webapp/webapp.js`: the preference forms keep the submit button last clicked and use it when the submit event has no `submitter`.
- `tests/test_selenium_cameo.py`: `JS_LONG`; the coverage helper counts shown `aria-hidden` text; the scroll check uses cameos that stay and checks that the page moved; four new tests, see "Checks"; the day created while a room page is open is written under `server_paused()`.
- `tests/test_selenium_webapp.py`: `_conference()` and the raffle draw read write under `server_paused()`.
- `README.md`: cameo spots, rechecks, exit, tests.

**Bugs fixed:**

- A cameo could stay over a control or a text brought under it by a live refresh (raffle block swapped, Join button shown by an attribute) for up to about 5 s: the overlap was rechecked only on scroll and resize. Now any change of the page outside the layer, a resize of the content or a focus triggers the check.
- A cameo could cover text that is shown but `aria-hidden`, such as the "Updated N s ago" label of the raffles: the engine skipped that text. It now counts.
- The exit animation never played: the exit reused the enter keyframe with `reverse`, which updates the finished enter animation in place, so the cameo vanished at once. The exit has its own keyframes.
- On a browser whose submit event has no `submitter` (iOS Safari before 15.4), every animation choice sent "auto", so "Off" could not be set. The clicked button is now known from its click.

**Safeguards and edge cases:**

- The page check runs only while a cameo is on screen, at most once per 150 ms; the mutations of the cameo layer itself do not trigger it.
- `data-ewp-cameo-avoid` keeps its meaning, for decorations without text.
- A submit without a click (Enter in a field) still uses the first button of the form.

**Checks:** fresh test database with both modules and `EWP_AXE_JS` set, Selenium tests run; new tests: a cameo leaves when an attribute shows a button under it and when a block swapped by `innerHTML` (as the raffle refresh does) puts a line under it, with no scroll; a shown `aria-hidden` text over the window sends the cameo away and leaves no spot, and raffle cameos never land on the age label; the exit runs an `ewp-cameo-*-out` animation; "Off" then "On" are stored and applied with `submitter` removed. black, isort, ruff, prettier, comment hygiene check; `.pot` exported again, `msgfmt -c` on `fr.po`.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.4.1

**Short title:** themes can mark an element that the cameos keep clear of.

**Reason for the request:** the Tux cameos of rlq_event_webapp_plan 18.0.1.2.0 could cover the ribbon of words: its moving copies are `aria-hidden`, and the engine skips the text of `aria-hidden` parts when it looks for a free spot.

**Changes:**

- `static/src/webapp/webapp_cameo.js`: an element marked `data-ewp-cameo-avoid` is an obstacle, like a control; header comment.
- `tests/test_selenium_cameo.py`: the cameo of the mode "On" may come from any registered actor, not only the neutral one, so the test passes with a theme that registers its own.
- `README.md`: the attribute, under Theming.

**Bugs fixed:**

- A cameo could enter over text that a theme shows but hides from assistive technologies (the ribbon of the Rencontres Linux theme, from a card corner).

**Safeguards and edge cases:**

- Without the attribute nothing changes; a marked element out of view or not displayed blocks no spot.

**Checks:** see the 18.0.1.2.0 entry of rlq_event_webapp_plan.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.4.0

**Short title:** animation mode "Follow the device", "On", "Off" on the user, and a cameo engine of decorative actors that themes fill.

**Reason for the request:** the animations were not seen on a desktop whose browser reports `prefers-reduced-motion`, with no way to turn them on in the page; themes need small figures that come in, move and go away (drink a coffee, type on a keyboard, speak in a microphone) without covering anything the visitor needs.

**Changes:**

- `models/res_users.py`: the boolean `ewp_reduce_motion` becomes the selection `ewp_motion` (`auto`, `on`, `off`, default `auto`), still restricted to the Settings group and self readable and writeable; `_ewp_motion_mode()`; `migrate_reduce_motion(cr)` copies the old column (true gives `off`, false `auto`).
- `migrations/18.0.1.4.0/pre-migrate.py` (new): runs `migrate_reduce_motion()` before the models load, so the ORM does not fill the new column with its default.
- `controllers/main.py`: the preferences route takes `motion=auto|on|off` (the `reduce_motion` parameter is gone); its JSON answer gives `motion`; the pages receive `motion` (mode in force, `off` in text-only mode), `motion_choice` and `motion_paused`; two new announcements for the mode "Follow the device".
- `views/webapp_templates.xml`: the body carries `o_ewp_motion_auto`, `o_ewp_motion_on` or `o_ewp_motion_off`, plus `o_ewp_motion_paused` under "Off" and in text-only mode; the footer holds the group **Animations** (three buttons, `aria-pressed`, labelled group) and the hint "Your device asks for less motion, animations are off." with **Turn them on**, shown by the CSS under "Follow the device" with reduced motion.
- `views/res_users_views.xml`: **My Preferences** shows the mode as radio buttons.
- `static/src/webapp/webapp.js`: the motion state follows the mode classes (`on` plays whatever the device says); the preference forms send the value of the button pressed (`submitter`); a new mode updates the classes, the pressed button and the announcement in place, and gives the focus to the pressed button when the hint button disappears; `ewp:motion` and `ewp:ready` carry the mode.
- `static/src/webapp/webapp.scss`: mixin `ewp-motion-allowed` (the rule set of "animations may run"); the stop rules apply under `o_ewp_motion_off` and `o_ewp_motion_paused`, and under reduced motion only with `o_ewp_motion_auto`; styles of the group (radio dot) and of the hint.
- `static/src/webapp/webapp_cameo.js` (new): cameo engine, `window.ewpCameo` (`register`, `unregister`, `configure`, `play`, `state`), a fixed `aria-hidden` layer without pointer events, spots that cover no control, picture or text, a schedule of 6 to 15 s (1 cameo under 640 px, 2 above), cameos of page events (`celebrate` on a raffle winner, `speak` on a running conference, `coffee` before the opening), `ewp:cameo` events, a neutral actor used while no theme actor is registered.
- `static/src/webapp/webapp_cameo.scss` (new): the layer, the neutral actor, the entries (rise, slide, pop) and actions, inside `ewp-motion-allowed`.
- `tests/test_accessibility.py`: the selection on the route and through the ORM (unknown values refused), privacy of `ewp_motion`, the body classes and pressed buttons of each mode, the migration of the old column, the mode "On" under reduced motion in the browser. `tests/test_selenium_webapp.py`: the shared records move to the base class `WebappSeleniumCase`; the motion tests use the new buttons. `tests/test_selenium_cameo.py` (new, 6 tests): "On" with reduced motion, "Follow the device" with reduced motion and its hint, "Off" and text-only mode, no overlap of a control or a text at 390 and 1280 px and after a scroll, actions of the page events, hidden tab. `tests/selenium_common.py`: `set_page_hidden()`.
- `README.md`: Accessibility (animation mode, hint, cameos), Theming (`ewp-motion-allowed`, body classes, cameo API, `ewp:cameo`), Tests.
- `i18n/`: new terms, translated to French.

**Bugs fixed:**

- A browser that reports `prefers-reduced-motion` (a system setting, sometimes on without the user knowing) showed no animation, and the page neither said why nor let the user turn them on: the mode "Follow the device" now shows a hint with **Turn them on**, and the mode "On" plays them whatever the device says.

**Safeguards and edge cases:**

- Text-only mode forces the mode "off" whatever is stored: no animation, no cameo, no animation form.
- A cameo never covers a control, a picture of 32 px or more, or a text (8 px around); a cameo that a scroll brings over one leaves at once; without a free spot none plays.
- The cameos leave at once when the animations pause and when the tab hides; none lasts more than 7 s; the moves are transforms and fades of 0.6 s or more (no flashing).
- An unknown `motion` value on the route, or the old `reduce_motion` parameter, changes nothing; an unknown value through the ORM is refused.
- Without script the three buttons still post the form; the hint needs no script.

**Checks:** fresh test database with the theme module installed, the tests of both modules with `EWP_AXE_JS` set: 0 failed, 0 error of 132 tests, no test skipped (Selenium on Chromium 155, axe-core audit included); this module alone: 0 failed, 0 error of 115 tests; the Selenium tests of this module also pass on Firefox 157 (18 of 18). black and isort (line length 79), ruff, prettier (JS, SCSS), comment hygiene check; `.pot` exported again, `fr.po` completed, `msgfmt -c`.

**Action required:** update the module (`-u event_webapp_plan`): the migration keeps the choice of each user ("Pause animations" becomes "Off").

## 18.0.1.3.0

**Short title:** end-to-end tests in a real browser through Selenium, and a base class for the tests of the features to come.

**Reason for the request:** validate in a real browser, as a visitor uses it, what the web app does today and what will be added to it.

**Changes:**

- `tests/selenium_common.py` (new): base class `SeleniumCase` on `HttpCase`. One WebDriver per test class: headless Chromium (`/usr/bin/chromium`) by default, Firefox with `EWP_SELENIUM_BROWSER=firefox`; `EWP_SELENIUM_BINARY` and `EWP_SELENIUM_DRIVER` override the executables, else the driver comes from the `PATH` or Selenium Manager (usage statistics off unless `SE_AVOID_STATS` is set). Each test starts logged out, on a desktop viewport, with only the test cursor cookie of the running test, so the requests of the browser run in the transaction of the test. Helpers: `open()` (flushes the writes of the test first), `login()` and `submit_login_form()` (the real form of `/web/login`), `logout()`, `set_viewport()` (phone 390 x 844 through the DevTools device metrics on Chromium, desktop 1280 x 900), `emulate_media()` (`prefers-reduced-motion`, `prefers-color-scheme`), `wait_until()`, `wait_js()`, `wait_for()`, `text()`, `press()`, `tab()`, `active_element()`, `announcement()`, `wait_announcement()`, `animations()` (`document.getAnimations()`), `server_paused()` (holds the lock of the shared cursor to read or write records while a page is open), `restart_browser()`. A failing test saves a screenshot, and the console on Chromium, in `EWP_SELENIUM_SCREENSHOTS` (default `<temporary directory>/ewp_selenium`) and logs the path.
- `tests/test_selenium_webapp.py` (new, tags `post_install`, `-at_install`, `selenium`): 12 tests. Anonymous visitor sent to the login form and back; home page on a phone (plan, room areas, room list, events, raffles, one column, no horizontal scroll) and in the dark colour scheme; room entry by a click (room group given, Discuss chat loaded, frame title); preview banner for a moderator and closed page for a portal user before the opening; raffle drawn on the server announced in the live region with `ewp:raffle-drawn`; conference waiting then running (page loaded again with the frame, announcement, focus on the conference heading, no server address nor secret in the page); conference left through `bbb_left` (notice, focus on "Join again") and joined again; text-only mode kept for a new browser session; "Pause animations" and `prefers-reduced-motion` leave `document.getAnimations()` empty; skip links; keyboard-only path to a room and back.
- `tests/__init__.py`: imports the new test module.
- `README.md`: "End-to-end tests with Selenium" in Tests (install, browsers, variables, command).

**Bugs fixed:** none in the module.

**Safeguards and edge cases:**

- The test class skips itself, with the reason in the log, only when the `selenium` package, the browser or its driver is missing; any other failure to start the browser is an error.
- The polls of the page (20 and 30 s) are not waited for: the tests fire `visibilitychange`, on which the page asks the server at once.
- BigBlueButton is the `FakeNetwork` of `tests/test_bbb.py` and the join URL a static file of the module: the browser reaches no other host.
- The pages register no service worker in the test browser: its registration fetch, a public route, may outlive its page and replace the session cookie of the next login form (CSRF failure). The tests of the controllers cover the service worker.
- The browser quits before the class cleanups of Odoo, which terminate any child process left.
- Firefox windows stop at 500 px: its phone viewport is 500 px wide, still under the wide layout.
- Selenium is not a dependency of the module (`pip install 'selenium>=4.20'` in the Odoo environment).

**Checks:** fresh test database with the theme module installed, the tests of both modules with `EWP_AXE_JS` set: 0 failed, 0 error of 125 tests, no test skipped (Chromium 155); the Selenium tests alone also pass with Firefox 157, theme installed. black and isort (line length 79), ruff, comment hygiene check; `.pot` exported again, unchanged (no new term); `msgfmt -c`.

**Action required:** none for production; to run the new tests, install `selenium` in the Python environment of Odoo.

## 18.0.1.2.3

**Short title:** lead slot for the first card of the home page; the banner of a theme inside the header landmark; room pills named with their visible words.

**Reason for the request:** review of the pages with a theme installed: card order on phones, name of the room links (WCAG 2.5.3) and the axe-core "region" rule.

**Changes:**

- `views/webapp_templates.xml`: slot `webapp_slot_home_lead`, rendered first in the home page (before the announcement) inside a column `o_ewp_column_lead`, which exists, with the class `o_ewp_home_lead` of `main`, only when the slot renders something; on the home and room pages the `header` element (banner landmark) now holds the bar (a `div` with the same classes) and the banner slot; the "Video" pill of a room link shows "Video" and adds "conference" for screen readers, instead of a visible word hidden from them and another hidden text.
- `static/src/webapp/webapp.scss`: from 1024 px, `o_ewp_home_lead` gives the lead cards a row of their own over the main column (grid areas `lead`, `main`, `side-top`, `side-bottom`); the main column starts 24 px under them; without announcement and links the raffles span every row.
- `tests/test_accessibility.py`: the lead cards open the reading order (normal and text-only) and their column is absent without them; the axe-core audit also runs the "region" rule. `tests/test_controllers.py`: the lead slot, and the banner slot inside the header. `tests/test_browser.py`: geometry of a lead card at 390 and 1280 px. `tests/test_bbb.py`: the words shown by the pills of a room link are part of its name, in English and in French.
- `README.md`: Look, Accessibility (header landmark, label in name), Theming (lead slot, banner slot), Tests.
- `i18n/`: the pill term, translated to French ("Vidéo (visioconférence)").

**Bugs fixed:**

- In French, a room link showed "Vidéo" but screen readers named it "Visioconférence": a speech input user who says the visible word could not reach it (WCAG 2.5.3, Label in Name).
- The banner of a theme, rendered between the header and `main`, lay outside any landmark (axe-core "region").
- A theme could not put a card before the announcement on phones without breaking the match between the visual order and the reading order.

**Safeguards and edge cases:**

- Without a lead card the home page is unchanged: no column, no class, the grid of 18.0.1.2.2.
- On a wide screen the raffles start under whichever of the lead cards and the announcement and links ends lower.
- A theme `xpath` that targeted `//header[hasclass('o_ewp_topbar')]` now targets the `div` of that class inside the header.

**Checks:** fresh test database with a theme module installed, the tests of this module and of the theme, with `EWP_AXE_JS` set: 0 failed, 0 error of 113 tests (axe-core audit included). black and isort (line length 79), ruff, prettier (JS, SCSS), comment hygiene check, `msgfmt -c`.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.2.2

**Short title:** "Join again" asks the server instead of the cached meeting state.

**Reason for the request:** end-to-end check in real browsers with a fake BigBlueButton server.

**Changes:**

- `models/bbb_client.py`: `cached_meeting_info()` takes `max_age` (seconds): a cached meeting state older than that is asked again, and the answer replaces the entry for every reader; constant `FRESH_TTL` (2 s). A cached server failure still answers at once.
- `models/event_webapp_room.py`: `_ewp_bbb_meeting()` and `_ewp_bbb_running()` pass `max_age` on.
- `controllers/main.py`: `bbb_status` takes `fresh=1`, read with `max_age=FRESH_TTL`; room value `check_url`.
- `views/webapp_templates.xml`: the "You left the conference." notice carries `check_url` in `data-ewp-bbb-check-url`.
- `tests/test_bbb.py`: a read with `max_age` and the `fresh=1` check of the status route skip a state cached before the meeting ended; the check URL of the notice.
- `README.md`: BigBlueButton (leaving the meeting).

**Bugs fixed:**

- When the host ended the meeting, every client landed on the "You left the conference." notice; a click on **Join again** within the 10 s of the meeting cache got "running" from the state cached before the end, so the frame loaded a join URL that the server refused (an error answer, a black frame with no way back but a reload), while the page still said the conference was live.

**Safeguards and edge cases:**

- Repeated clicks on **Join again** cost one call to the server per 2 s, per meeting and per worker, at most.
- The status poll of the waiting page and the live route keep the 10 s cache.

**Checks:** fresh test database with a theme module installed, the tests of this module and of the theme, with `EWP_AXE_JS` set; end-to-end run in headless Chromium against a fake BigBlueButton server (end of the meeting, then **Join again** at once: the waiting notice comes back). black and isort (line length 79), ruff, prettier, comment hygiene check.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.2.1

**Short title:** display preferences private to their user; focus rings and focus after a page load; announcements of the end of the raffle refresh; live rooms on the home page; tests of the live region.

**Reason for the request:** review of the accessibility work (version 18.0.1.1.0) and of the pages with a theme installed.

**Changes:**

- `models/res_users.py`: `ewp_text_only` and `ewp_reduce_motion` restricted to the Settings group (`groups="base.group_system"`). The user still reads and writes them on their own record through `SELF_READABLE_FIELDS` and `SELF_WRITEABLE_FIELDS` (and in **My Preferences**, which Odoo opens for these fields); nobody else reads them or searches on them.
- `controllers/main.py`: route `/webapp_event/<day>/live` (GET, `auth="user"`, same access as the raffles), JSON `{"live": [room ids]}` of the rooms whose meeting runs, through the cache of `bbb_client`; room value `meeting`; page value `rooms_live_url`; announcements `raffle_stopped` and `room_live`.
- `views/webapp_templates.xml`: the room list carries `data-ewp-live-url`, and each room with a meeting ID a hidden "Live" pill (`o_ewp_pill_live`); the "(opens in a new tab)" text gets the class `o_ewp_external_text`; the heading of the conference block is focusable by script (`tabindex="-1"`).
- `static/src/webapp/webapp.js`: the raffle refresh says "The raffle results are no longer updated. Reload the page to see the latest draws." when it stops (403, redirect) and after 3 failed answers in a row (once until an answer succeeds); the page loaded again by the conference poll and by **Join again** on a meeting that no longer runs puts the focus on the heading of the conference block; live rooms: the home page asks the live route at start and every 30 s, marks the area and the link of each live room (`data-ewp-live`), shows its pill, announces a room that goes live, and sends `ewp:rooms-live`.
- `static/src/webapp/webapp.scss`: from 1024 px the conference block takes the focus ring of the page (`--ewp-focus: inherit`); a ring goes around the box of the conference frame while the focus is in the frame (`.o_ewp_video:focus-within`); in text-only mode the new tab text shows in place of the icon (not beside **Open in a new tab**, which says it already); live room: still ring of the live colour around its area, "Live" pill in place of "Video".
- `tests/test_accessibility.py`: reading and searching the preferences of another user (ORM and JSON-RPC) raise `AccessError`; an anonymous post to the preferences route is sent to the login page and writes no user, the public one included; browser tests: the announcements of the raffle refresh (new winner, past winner not repeated, count beyond three, drawn count, results held while the animations are paused, end of the refresh), the text-only toggle across its page load (announcement and focus given back, new tab text shown), every animation stopped by **Pause animations** and by reduce motion (CSS and SMIL). `tests/test_browser.py`: focus ring of the conference block on a wide screen, **Show the video conference** in text-only mode, focus ring of the frame after **Join again**, focus and announcement after the reloads of the conference block, live rooms of the home page; helpers `JS_CHECK`, `JS_FRAME` (page opened in a frame of a static page, to follow a page load) and `emulated_media()` (DevTools media emulation). `tests/test_bbb.py`: the live route and its markup.
- `README.md`: Accessibility, BigBlueButton (live rooms), Theming (`data-ewp-live`, `ewp:rooms-live`), Tests.
- `i18n/`: new terms, translated to French.

**Bugs fixed:**

- Any logged-in user could read or search the text-only preference of other users (for instance `search_read([("ewp_text_only", "=", True)])` through `/web/dataset/call_kw`), which tells who is blind or partially sighted: the fields had no `groups`, and `res.users` is readable by portal users.
- In the dark scheme on a wide screen, the focus ring of the controls of the conference block (**Open in a new tab**, **Show the video conference**) took the accent colour, 2.9:1 on the page ground (2.2:1 with the theme), under the 3:1 of WCAG 1.4.11.
- After **Join again** or **Show the video conference** on a wide screen, the focus went to the conference frame without any visible ring: a frame passes the focus to its document and matches neither `:focus` nor `:focus-visible`, and the ring meant for it lay outside the frame, in the area its box clips.
- In text-only mode, a link that opens a new tab lost its cue: the icon is hidden there, and the text was for screen readers only.
- A screen reader user was never told that the raffle refresh had stopped (session expired, day closed): only the hidden age of the results said it.
- The automatic reloads of the room page (conference started, ended) sent the focus back to the top of the page.

**Safeguards and edge cases:**

- The live route answers `{"live": []}` when the server is not set or does not answer; a room with a conference URL only is never live. The home page itself still never calls the server.
- The "Live" pill and the ring stay still: the signal never depends on motion; a theme may animate it.
- The stale message is said once, until an answer succeeds again; a 403 or a redirect stops the refresh for good.
- A message kept for the next page whose focus target is missing (closed day, login page) is said without moving the focus.

**Checks:** fresh test database with a theme module installed, the tests of this module and of the theme, with `EWP_AXE_JS` set: 0 failed, 0 error of 107 tests (axe-core audit included). The new browser tests fail on the code of 18.0.1.2.0 (16 failed, 2 errors). black and isort (line length 79), ruff, prettier (JS, SCSS), comment hygiene check, `msgfmt -c` (0 untranslated).

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.2.0

**Short title:** hook for the name, colours and icons of the installable app; conference frame kept inside a phone screen in Firefox.

**Reason for the request:** a theme module gives the installable app its own name, colours and icons, and the tests of this module run with it installed.

**Changes:**

- `controllers/main.py`: `_ewp_pwa_values()` returns the name, short name, theme and background colours, page icon and manifest icons; the web manifest and the page values (`theme_color`, `icon_url`) read it, so a theme overrides it in a subclass of the controller.
- `static/src/webapp/webapp.scss`: `max-width: 100%` on the conference frame box; on wide screens, the explanation beside **Show the video conference** (text-only mode) in the muted text colour of the page.
- `tests/test_controllers.py`, `tests/test_accessibility.py`: the font check counts the 4 files of this module among those of the bundle, the manifest check accepts any hex colour, the display options check reads the buttons of the footer only, so the tests pass with a theme module installed.
- `README.md`: `_ewp_pwa_values()` in "Theming" and "Installable app".

**Bugs fixed:** on a phone in Firefox, the conference frame was 796 px wide: Firefox turns the minimum height of the box (`min(60dvh, 28rem)`) into a minimum width through its 16:9 `aspect-ratio`, so the room page scrolled sideways. `max-width: 100%` keeps the box at the width of the screen; the minimum height still applies. In text-only mode on a wide screen, the explanation beside **Show the video conference** kept the light text colour of the dark band on the light page ground (contrast below 1.5:1); it now takes the muted colour of the page.

**Safeguards and edge cases:** without a theme, the manifest and the pages keep the name "Event day", the colour `#15191E` and the icons of this module.

**Checks:** the tests of this module and of a theme module, on a fresh database with the theme installed.

**Action required:** update the module (`-u event_webapp_plan`).

## 18.0.1.1.0

**Short title:** accessibility for blind and partially sighted visitors: WCAG 2.2 AA pages, screen reader announcements, text-only mode and pause of the animations stored on the user.

**Reason for the request:** the web app must be usable with a screen reader and without the visual plan, and every animation a theme adds must stop on demand.

**Changes:**

- `models/res_users.py`: fields `ewp_text_only` and `ewp_reduce_motion` on `res.users`, added to `SELF_READABLE_FIELDS` and `SELF_WRITEABLE_FIELDS` (a user, portal included, reads and writes them on their own record only). `views/res_users_views.xml`: both in **My Preferences**.
- `controllers/main.py`: route `/webapp_event/preferences` (POST, `auth="user"`, CSRF): writes the two preferences on the current user, answers JSON to a request that accepts it, else a 303 redirect to a path under `/webapp_event`. New page values `text_only`, `reduce_motion`, `motion_paused`, `preferences_url`, `return_path`, `messages_json` (translated texts of the announcements), `chat_title`; titles that name the page ("Home - <day>", "Not open yet - <day>", "Over - <day>", "No event day", "Conference left - <room> - <day>"); `_ewp_plan_position()` and the room value `position` ("Area 1 on the plan, in the top left corner."). The offline page of the service worker gets a `lang`.
- `views/webapp_templates.xml`: skip links, `main#o_ewp_main` on every page, footer `#o_ewp_prefs` with the toggle buttons **Text-only mode** and **Pause animations** (`aria-pressed`, plain forms), one live region `#o_ewp_announcer` (the preview banner, the raffle status, the server notice and the leave notice are no longer live regions). Plan image alternative text pointing to the room list, plan areas `aria-hidden` and out of the tab order, room list with the position words and "Video conference", `role="list"` on the styled lists, "(opens in a new tab)" for the links that open one, state of the day spelled out, draw numbers hidden (the list numbers them). Home page in reading order (announcement and links, main column, raffles). Room page: chat in a section with a heading and the frame title "Discussion: <room>". Text-only mode: no plan image, logo, closed page icon, room badge, mascot or banner slot; the conference frame ships without `src` behind **Show the video conference**. Button **Show the latest results** of the raffle card.
- `static/src/webapp/webapp.js`: announcer of the shared region (texts from `data-ewp-messages`, repeat filter of 3 s, message kept in `sessionStorage` across a page load with the focus given back); display options sent with `fetch` (animations switched in place, text-only mode by a new load); motion state (`data-ewp-motion` on the body, SMIL animations of the inline SVG paused, event `ewp:motion`); raffles announced as the new winners or the drawn count, and held behind **Show the latest results** while the animations are paused; conference start, server state, leave and move announced; **Show the video conference**; skip links that move the focus. `ewp:ready` also gives `textOnly` and `motionPaused`. Page loads drop the address fragment.
- `static/src/webapp/webapp.scss`: skip links shown on focus, focus ring on any `[tabindex]`, no animation nor transition under `o_ewp_motion_paused` or `prefers-reduced-motion`, display options footer (box and check mark, not colour alone), text-only layout (one column, icons swapped for their labels), home grid that keeps the DOM order, closed pages that keep the footer on screen.
- `tests/test_accessibility.py`: preferences route (CSRF, anonymous, own user only, portal user, JSON, redirect kept local), self-writeable fields, skip links, landmarks, one `h1`, titles and `lang` on every page, one live region, frame titles, room list for screen readers, text-only rendering, paused animations; browser tests of both toggles; axe-core audit (WCAG 2.2 A and AA) when `EWP_AXE_JS` names `axe.min.js`. `tests/test_bbb.py`: text-only conference on demand, leave notice through the shared region.
- `README.md`: section "Accessibility", theming hooks `text_only`, `motion_paused`, `ewp:motion`.
- `i18n/`: new terms, translated to French.

**Bugs fixed:** on a phone, the home cards were reordered with CSS `order`, so the keyboard and screen reader order differed from the visual one (WCAG 1.3.2, 2.4.3); the DOM now follows the reading order. The plan areas repeated each room link in the tab order and to screen readers.

**Safeguards and edge cases:**

- The preferences route writes on `request.env.user` only and ignores any other parameter; a write on another user is refused by the access rights; a redirect outside `/webapp_event` falls back to `/webapp_event`.
- Without script, the toggles post a form and the server redirects back; the text-only mode then needs no script at all, except **Show the video conference**, beside which **Open in a new tab** works without it.
- In text-only mode the "Pause animations" toggle is not shown: that mode has no animation.
- `sessionStorage` may refuse access: the page then loads without the announcement.
- The live region is never filled at page load (screen readers do not announce it then): a message carried over a page load waits 600 ms.

**Checks:** fresh test database, `-i event_webapp_plan --test-tags /event_webapp_plan`, with `EWP_AXE_JS` set: 83 tests, 0 failed, 0 error (browser tests and the axe-core audit of 6 pages included, no violation). Pages seen in headless Chromium at 390 and 1366 px, normal and text-only: skip link on focus, display options footer, one column in text-only mode. black and isort (line length 79), ruff, prettier (JS, SCSS), comment hygiene check, `msgfmt -c` (0 untranslated).

**Action required:** update the module (`-u event_webapp_plan`). A theme that animates declares its animations so that `o_ewp_motion_paused` and `prefers-reduced-motion` stop them (see README, "Theming").

## 18.0.1.0.0

**Short title:** event day web app at /webapp_event, generic module with theme hooks: site plan with one chat and one BigBlueButton conference per room, raffle draws, installable app.

**Reason for the request:** provide a mobile web app for one event day, reserved to logged-in users, configured from a backend application, and keep it free of any event branding so that a separate theme module carries the look of a given event.

**Changes:**

- `models/event_webapp.py`: model `event.webapp` (one event day, `mail.thread`): name, opening window (`date_start`, `date_end`), announcement, links, events, raffles, plan image, rooms; computed `is_open`, `webapp_url`, `room_count`, `bbb_configured`. Helpers `_ewp_is_moderator()`, `_ewp_find_default()` (open day, else next to open, else last closed; archived days ignored), `_ewp_can_view()`. Actions `action_open_webapp`, `action_create_missing_channels`, `action_open_bbb_meetings`.
- `models/event_webapp_room.py`: model `event.webapp.room`: name, description, colour, area in percent of the plan image, Discuss channel of type "channel", access group of the room (category "Event Web App Rooms", implying nothing, implied by the Moderator group), both created and renamed with the day or the room. The access group is written in superuser mode only; a channel restricted to another group is refused except for the Settings group. `_ewp_grant_access()` gives the room group on entering the room, never to the public user, never withdrawn. BigBlueButton fields `bbb_meeting_id`, `bbb_room_url` (http or https only), `bbb_frameable`, `bbb_frame_checked`, button **Re-check**; `_ewp_bbb_target()` picks the meeting ID mode, the conference URL (in the page or behind a button) or nothing.
- `models/event_webapp_link.py`: model `event.webapp.link`: label, URL, description.
- `models/event_webapp_bbb_meetings.py`: wizard "Running BBB meetings" that lists the meetings of the server and assigns a meeting ID to a room.
- `models/bbb_client.py`: BigBlueButton API client (SHA-256 checksum, `getMeetingInfo`, `getMeetings`, join URL with `createTime` and `logoutURL`, per-worker cache of 10 s, failure cache of 60 s, timeouts of 3 s to connect), frame check of a URL from its `X-Frame-Options` and `Content-Security-Policy` headers. Errors never carry a signed URL.
- `models/res_config_settings.py`: settings block "Event Web App": server URL (`event_webapp_plan.bbb_server_url`) and write-only shared secret (`event_webapp_plan.bbb_secret`), button **Forget the secret**.
- `models/res_groups.py`: room groups hidden outside debug mode; a room group still used by a room or a channel cannot be deleted.
- `controllers/main.py`: routes `/webapp_event`, `/webapp_event/<day>`, `/webapp_event/<day>/room/<room>` (with `bbb_status`, `bbb_join`, `bbb_left`), `/webapp_event/<day>/plan`, `/webapp_event/<day>/raffles` (JSON), all `auth="user"`; `/webapp_event/manifest.webmanifest` and `/webapp_event/sw.js` public. Data read with sudo, only chosen fields reach the pages. New values for the theme hooks: `ewp_page` (from `PAGE_NAMES`), `day_start` and `day_end` (ISO 8601, UTC).
- `views/webapp_templates.xml`: standalone pages on `web.layout`: home (day header, announcement, links, plan with numbered rooms, events, raffles), room (chat iframe, conference frame, "You left the conference." notice and "Join again"), closed, no day, conference left. Theme hooks: template `webapp_brand`, empty slots `webapp_slot_mascot`, `webapp_slot_banner`, `webapp_slot_home_cards`, `webapp_slot_footer`; body classes `o_ewp_page_<page>` and `o_ewp_day_<state>`; `data-ewp-page`, `data-ewp-day-state`, `data-ewp-day-start`, `data-ewp-day-end` on `.o_ewp_app`; `data-ewp-bbb-state` on the conference section.
- `static/src/webapp/webapp.scss`: mobile first, wide layout from 1024 px, dark colour scheme. Every colour, font and radius is a custom property on `.o_ewp_webapp` (`--ewp-*`). Inter and Space Grotesk served by the module (`fonts/`, SIL Open Font License 1.1).
- `static/src/webapp/webapp.js`: raffle refresh every 30 s with a status region for new winners, conference status poll, "Open in a new tab", leave and "Join again", plan highlight, service worker registration. Theme hooks: the page and day state copied to the body; DOM events `ewp:ready`, `ewp:day-state` (also when the clock reaches the opening or the closing moment), `ewp:bbb-state`, `ewp:raffle-drawn`.
- `static/src/backend/`: field widget `ewp_room_plan_editor` that draws each room on the plan image (mouse, pen and touch).
- `security/`: groups Event Web App / Moderator and Administrator, category Event Web App Rooms, access rights.
- `views/event_webapp_views.xml`, `views/event_webapp_bbb_meetings_views.xml`, `views/res_config_settings_views.xml`, `views/menus.xml`: application "Event Web App" (Event days, Configuration > Settings).
- `README.md`: features, access, BigBlueButton, look, PWA, and the "Theming" section.
- `i18n/event_webapp_plan.pot`, `i18n/fr.po`: every term, translated to French.

**Bugs fixed:** none (first version under this name).

**Safeguards and edge cases:**

- Anonymous visitors, guests of an invitation link and users who never entered a room get a 404 on its chat; the chat stays readable for those who entered, once the day is over.
- The BigBlueButton secret never reaches a page, a JSON answer or the logs; the pages carry no join URL and no server address, only the redirect of `bbb_join` names the server.
- A slot renders nothing until a theme fills it: the pages of this module look the same with or without the hooks.
- The events of the start are sent after a zero delay, so a theme script later in the same bundle receives them; the body attributes give the state to a script loaded later.
- `setTimeout` accepts at most about 24 days: a later opening or closing moment is checked again at that delay.

**Checks:** fresh test database, `-i event_webapp_plan --test-tags /event_webapp_plan`: 69 tests, 0 failed, 0 error (browser tests included). Theme hooks checked: body classes and root data attributes on the home, room, closed and conference-left pages; slots filled by an inheriting template shown where they are called; in headless Chromium, day and page state on the body and the `ewp:bbb-state` events `left`, `running`, `left`. black and isort (line length 79), ruff, prettier (JS, SCSS), comment hygiene check, `msgfmt -c` (0 untranslated).

**Action required:** install the module (`-i event_webapp_plan`) and give the Moderator or Administrator group to the people who prepare the day. A reverse proxy must not add `X-Frame-Options: DENY` to `/discuss/channel/`.
