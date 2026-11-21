# Changelog - event_webapp_plan_raffle

## 18.0.1.1.0

**Short title:** the "My prize" card reports its refresh times to the automatic updates of the web app.

**Reason for the request:** event_webapp_plan 18.0.1.10.0 lists the refresh timers of the blocks at the bottom of the pages.

**Changes:**

- `views/webapp_templates.xml`: template `prize_refresh_row`, the row "My prize" (`my_prize`) in the slot `webapp_slot_refresh`, wherever the card polls (also while it is empty and hidden).
- `static/src/webapp/prize.js`: `ewp:refresh` when a request is sent or answered; the next one is the earliest of the next tick of the minute, counted from the moment the interval last fired (a suspended device or a clock change moves its phase away from the page load), a request pending after `ewp:raffle-drawn` and the deadline of an open link; header comment.
- `README.md`: the row.
- `i18n/`: the new place of "My prize".
- `tests/test_controllers.py`: `test_automatic_updates_row`, `test_automatic_updates_count_to_the_link_deadline`, `test_automatic_updates_follow_the_minute_tick` (browser).

**Bugs fixed:** none.

**Safeguards and edge cases:** the requests, their interval and the pause of a hidden tab do not change; without fetch no row shows.

**Checks:** see the 18.0.1.10.0 entry of event_webapp_plan.

**Action required:** update the module (`-u event_webapp_plan_raffle`).

## 18.0.1.0.0

**Short title:** "My prize" card, public name and self-declared attendance in the event web app.

**Reason for the request:** phase 3 of the raffle prizes: a winner who uses the web app on the day sees their prize link, then how the prize reaches them, sets the name the winners page shows, and may say they are on site.

**Changes:**

- `controllers/main.py`: the home page values of the card (`prize_*`) and of the toggle (`presence`); the JSON route `/webapp_event/<day>/my_prize`; the POST routes `public_name` and `presence` (CSRF, JSON or 303 redirect); the raffle block names a winner by their public name.
- `models/event_webapp.py`: `_ewp_prize_draws()` and `_ewp_partner_registrations()`, the draws and registrations of a contact for a day.
- `models/event_registration.py`, `models/event_raffle_draw.py`: `attendance_declared` and its time on the registration, shown on the draw.
- `views/webapp_templates.xml`, `static/src/webapp/prize.js`, `static/src/webapp/prize.scss`: the two blocks, their live refresh and their forms.
- `views/event_registration_views.xml`, `views/event_raffle_draw_views.xml`: the declared attendance in the backend, read only.
- `i18n/`: template and French catalogue.
- `tests/`: models, HTTP and Selenium tests, axe-core.

**Bugs fixed:** none (first version).

**Safeguards and edge cases:** the card reads the draws of the current user's contact only; the prize link reaches its own winner only; the public name form never changes the contact of another account; the declared attendance never changes the attendance mode, the eligibility or the quotas; a block is not replaced while the focus is inside it.

**Checks:** suites of `event_webapp_plan_raffle`, `event_webapp_plan` and `event_webapp_plan_track` on a fresh database, Selenium and axe-core included.

**Action required:** install the module (`-i event_webapp_plan_raffle`).
