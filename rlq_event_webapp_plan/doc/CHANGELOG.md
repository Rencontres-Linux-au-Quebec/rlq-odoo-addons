# Changelog - rlq_event_webapp_plan

## 18.0.1.3.2

**Short title:** Tux speaks and the block has its frame for a running meeting behind the new tab button.

**Reason for the request:** event_webapp_plan 18.0.1.7.0 shows a running meeting of another site behind a new tab button (state `button`) instead of the frame (state `running`).

**Changes:**

- `static/src/webapp/rlq_theme.js`: the bar Tux speaks when `ewp:bbb-state` carries `live`, in the frame or behind the button; header comment.
- `views/webapp_templates.xml`: the bar Tux waves on a room page rendered after a leave (`left=1`), as on the "conference left" page.
- `static/src/webapp/rlq_theme.scss`: the navy border of the conference frame also frames the new tab block of a running meeting (4 px, 8 px on wide screens); no animation.
- `tests/test_theme.py`, `tests/test_selenium_tux.py`: the "conference left" page is `bbb_left?frame=1`; the frame tests force "Always embedded"; a browser test of a running meeting behind the new tab button (Tux keeps speaking after the first `ewp:bbb-state`, navy border of the block); the pose of a room page rendered after a leave.
- `README.md`: the `speak` pose.

**Bugs fixed:** none.

**Safeguards and edge cases:** an event without `live` (older event_webapp_plan) keeps the former rule, speak for `running` only.

**Checks:** see the 18.0.1.7.0 entry of event_webapp_plan.

**Action required:** update the module (`-u rlq_event_webapp_plan`).

## 18.0.1.3.1

**Short title:** speakers of the example day renamed outright, no detail from a real speaker.

**Reason for the request:** review of the demo data: each name changed one syllable of a real one and sat beside the job, organisation or biography of that person, while the module said the people were invented.

**Changes:**

- `demo/event_webapp_demo.xml`: eight speaker names replaced by names with no link to the real ones; job positions without organisation; track 08 gets a description of its subject instead of a biography; the opening track no longer gives the founding year; header comment.
- `README.md`: what "invented" covers.

**Bugs fixed:** none in the code.

**Safeguards and edge cases:** the times, places, tags and titles of the tracks are unchanged, and so are the tests of the example day. The file is `noupdate`: a database that already holds the example keeps the old texts until the records are deleted and the module updated.

**Checks:** grep of the former names and organisations over the modules; combined run on a database with demo data.

**Action required:** none for a new database; for an existing demo database, delete the example tracks and update the module to reload them.

## 18.0.1.3.0

**Short title:** example event day as demo data, with its agenda in the rooms.

**Reason for the request:** see the agenda of the event in the app, in link with the rooms, on an example taken from the open house on Linux, while the module is still a prototype. The example is delivered as demo data, with invented names for the people and organisations.

**Changes:**

- `__manifest__.py`: depends on `event_webapp_plan_track` (which pulls `website_event_track`); new `demo` entry; description.
- `demo/event_webapp_demo.xml` (new, `noupdate`): the event of 21 November 2026 (8:00 to 18:00, `America/Montreal`, stored in UTC) with three free tickets; five track locations; the tag category "Formule" and four coloured tags; 21 published tracks in the stage "Published" with place, tags, speaker, job position and description; the raffle "Prix de présence" with 7 draws on the times of the draw tracks, placeholder prizes, no winner; the event day (7:30 to 21:00) with the event, the raffle, a French announcement, the Pause Café Linux card, one relative link `/event`, the plan and five rooms, each following one location.
- `demo/event_plan.png` (new): generic plan, five numbered rectangles, drawn with Pillow.
- `tests/test_demo.py` (new, 5 tests): see "Checks".
- `README.md`: dependency, example day, tests, image origin.

**Bugs fixed:** none.

**Safeguards and edge cases:**

- A database without demo data gets nothing; `tests/test_demo.py` skips itself there.
- The other tests set every day inactive before creating their own: they pass with or without the example day.
- The example holds no conference URL, address, e-mail, phone or host name; its descriptions were rewritten where the source text named third parties.
- The announcement and descriptions use no inline markup, so the XML formatter cannot split a sentence.

**Checks:** combined run and generic module alone, on a database with demo data and on one without (`--without-demo=all`), Selenium and axe-core included; demo install log without error; screenshots of the home agenda and of a room page at 390 and 1280 px.

**Action required:** update the module (`-u rlq_event_webapp_plan`); `event_webapp_plan_track` and `website_event_track` get installed. The example day appears only in a database with demo data.

## 18.0.1.2.1

**Short title:** Tux tests write records under the lock of the shared cursor.

**Reason for the request:** a review found that a Selenium test created a conference day while a room page with its chat was open, without `server_paused()`; a request closing meanwhile could roll back the new records and make the test fail at random.

**Changes:**

- `tests/test_selenium_tux.py`: the raffle draw read and write under `server_paused()` (the conference day goes through `_conference()` of event_webapp_plan, now locked); `JS_LONG` imported from the tests of the engine.

**Bugs fixed:**

- Possible intermittent failure of `test_room_tux_speaks_drinks_coffee_and_waves`: records written on the shared test cursor while the page sent requests.

**Safeguards and edge cases:** none, tests only.

**Checks:** see the 18.0.1.4.2 entry of event_webapp_plan.

**Action required:** update both modules (`-u event_webapp_plan,rlq_event_webapp_plan`), with event_webapp_plan 18.0.1.4.2.

## 18.0.1.2.0

**Short title:** livelier Tux: stronger motion, new actions (coffee, code, speak, walk, peek), Tux cameos a little everywhere.

**Reason for the request:** the animations were not seen: the motion was too subtle (a 6 px bob, pale flakes). The request asks for penguins a little everywhere that move and disappear, drink coffee, pull out a keyboard to code and speak into a microphone.

**Changes:**

- `views/webapp_templates.xml`: the vector Tux (`tux_svg`) gets a face group (eyes and beak), two feet groups, a laptop with a lys sticker and its screen glow, four code glyphs drawn as strokes (`{ }`, `</>`, `$_`, `git`), a hand microphone, sound waves and a speech bubble; the headset is gone. New poses `coffee`, `code`, `speak`, `wave`, `walk`, `peek`; `speak` replaces `live`. `tux_for_page`: speak while the room meeting runs, coffee while it waits, wave on the "conference left" page. The mascot slot holds an inert `<template class="o_rlq_tux_source">` with the drawing for the cameos, and nine flakes instead of six. The ribbon words and the ornament words carry `data-ewp-cameo-avoid`.
- `static/src/webapp/rlq_theme.js`: room poses from `ewp:bbb-state` (running: speak, waiting: coffee, left: wave for 4 s), wave on the "conference left" page; two cameo actors registered with the engine of event_webapp_plan, `rlq-tux` (coffee, code, wave, peek, walk) and `rlq-tux-moments` (celebrate, speak, sleep, weight 10^-6 in the schedule draw), at 60 px on phones and 88 px above; `sleep` played once the day is over.
- `static/src/webapp/rlq_theme.scss`: the raster Tux rocks 7 px and 4 degrees (was 6 px and 1.5), with larger steam; bulbs dim to a fifth and glow brighter; flakes of 14 to 24 px at 95 % opacity; the idle Tux sways and flaps; the sip tips the head and the mug; keyframes and still poses of the new actions; cameo stages for walk (paces across its box) and peek (rises from its bottom edge, clipped); glyph and wave halos; dark scheme halo for the cameos.
- `tests/test_selenium_tux.py` (new, 6 Selenium tests), `tests/test_theme.py`: see "Checks".
- `__manifest__.py`, `README.md`: Tux, cameos, motion, tests.

**Bugs fixed:**

- The motion of the theme was hard to see: amplitudes and contrast raised, see above.

**Safeguards and edge cases:**

- Every new part is decorative: `aria-hidden`, `focusable="false"`, no id, no text, no link; the cameos live in the `aria-hidden` layer of the engine, without pointer events, never over a control, a picture, a text or a marked element.
- Every animation sits in `ewp-motion-allowed`: none under "Off", in text-only mode (no drawing, no Tux actor) or under reduced motion with "Follow the device"; "On" plays them. A paused page keeps the still pose. The waves stop by themselves after 3 or 4 s; the long poses (speak, coffee) play on the room page, whose footer pauses them.
- No flashing: one dim and glow per bulb in 1.8 s; every other move is a transform or a fade.
- A cameo box of 96 px found no free spot on the room page at 1280 x 900; 88 px does.

**Checks:** fresh test database with both modules and `EWP_AXE_JS` set; black, isort, ruff, prettier, comment hygiene check; `.pot` exported again, `msgfmt -c` on `fr.po`. Frame sequences of each action at 1280 px and two at 390 px, from a scratch server, reviewed as GIFs.

**Action required:** update both modules (`-u event_webapp_plan,rlq_event_webapp_plan`), with event_webapp_plan 18.0.1.4.1.

## 18.0.1.1.0

**Short title:** the theme animations follow the animation mode of event_webapp_plan 18.0.1.4.0.

**Reason for the request:** the animations were not seen on a desktop whose browser reports `prefers-reduced-motion`; event_webapp_plan now offers the mode "On", which must play them even then.

**Changes:**

- `static/src/webapp/rlq_theme.scss`: the animation block moves from `@media (prefers-reduced-motion: no-preference)` to `@include ewp-motion-allowed` (mode "On", or "Follow the device" without reduced motion); the still ribbon of reduced motion applies only under `o_ewp_motion_auto`.
- `tests/test_theme.py`: the motion tests press the new "Off" button and read `ewp_motion`; the mode "On" plays the Tux, the steam, the flakes and the ribbon with reduced motion emulated, and keeps the ribbon button.
- `__manifest__.py`, `README.md`: motion text.

**Bugs fixed:** none in the theme; see event_webapp_plan 18.0.1.4.0.

**Safeguards and edge cases:**

- "Off" and the text-only mode still stop every animation; reduced motion under "Follow the device" still shows the ribbon still, wrapped, without its button.

**Checks:** fresh test database, the tests of both modules with `EWP_AXE_JS` set: 0 failed, 0 error of 132 tests, no test skipped. prettier (SCSS), comment hygiene check; no new term to translate.

**Action required:** update the module (`-u rlq_event_webapp_plan`), with event_webapp_plan 18.0.1.4.0.

## 18.0.1.0.2

**Short title:** Pause Café Linux card before the announcement on phones; ribbon inside the header landmark.

**Reason for the request:** review of the theme against design version 3 (phone home page) and of its accessibility (axe-core "region" rule).

**Changes:**

- `views/webapp_templates.xml`: the Pause Café Linux card fills the new lead slot of `event_webapp_plan` (`webapp_slot_home_lead`, template `webapp_slot_home_lead`) instead of the home cards slot (template `webapp_slot_home_cards` removed), so it comes first on phones, before the announcement, and still tops the main column on wide screens.
- `controllers/main.py`: docstring (lead slot).
- `tests/test_theme.py`: the poster card is the first card of the page, before the announcement, also in text-only mode; the ribbon is inside the header, after the bar; browser test of the card order at 390 px and of its place at 1280 px.
- `README.md`: Pause Café Linux card, ribbon.
- `i18n/`: template exported again (new template id of the card).

**Bugs fixed:**

- On phones the Pause Café Linux card came after the announcement and the links, while design version 3 puts it first.
- The sentence that screen readers read for the ribbon lay outside any landmark (axe-core "region", moderate): the banner slot of `event_webapp_plan` is now inside the header.

**Safeguards and edge cases:**

- The ribbon is still read once, as a sentence, and its pause button still works; the header now holds it, so landmark navigation reaches it.
- Days without the card keep the home page of `event_webapp_plan` unchanged.

**Checks:** see the 18.0.1.2.3 entry of `event_webapp_plan`: both test suites on a fresh database with the theme installed, axe-core audit included.

**Action required:** update the module (`-u rlq_event_webapp_plan`), after `event_webapp_plan`.

## 18.0.1.0.1

**Short title:** ribbon that fills wide screens and shows every word when still; flakes behind the content; sipping pose that holds its mug; halo of the card Tux in the dark scheme; live rooms that glow on the plan.

**Reason for the request:** review of the theme against design version 3 and of its accessibility.

**Changes:**

- `views/webapp_templates.xml`: the ribbon track holds six copies of the words, each in a `.o_rlq_copy` (two before).
- `static/src/webapp/rlq_theme.scss`: the ribbon slides by one copy per loop (`$rlq-marquee-copies`); a ribbon that stands still (its button, **Pause animations**, reduce motion) shows its first copy only, wrapped, without clipping (mixin `rlq-still-ribbon`); each bar and the closed page are stacking contexts (`isolation: isolate`) and the flakes sit at `z-index: -1`, under the texts and controls; the closed page body is no longer positioned, so the flakes fill the whole closed page; sipping pose (`$rlq-sip-mug`, `$rlq-sip-flipper`, same values in the animation): the left flipper, shortened, turns across the chest so that its tip is under the mug, whose rim tilts against the beak; dark scheme: light halo (`drop-shadow`) around the vector Tux of the raffle card; live room: glow of its area on the plan (`rlq-room-live`), under `prefers-reduced-motion: no-preference`.
- `tests/test_theme.py`: six copies of the words; server-side `live` pose while the meeting runs; browser tests: poses from the page events, a real raffle answer (celebrate) and the running meeting (live); geometry of the sipping pose; halo in the dark scheme only; ribbon that covers its band at the end of the loop up to 2560 px and shows every word when still in a 390 px band; flakes under the texts of the bars and the closed page, filling the closed page; every theme animation stopped by **Pause animations** and by reduce motion.
- `README.md`: look (live rooms, halo, rising lys), sipping pose, ribbon, live rooms, tests.
- `i18n/`: no new term (template exported again, unchanged).

**Bugs fixed:**

- The ribbon went blank on the right of wide screens: two copies of about 780 px slid by half the track, so from about 830 px of width part of the band was empty during each loop (always, on a 1920 px screen).
- With the animations paused or under reduce motion, the ribbon froze at its start and its last three words could not be seen on a phone.
- The rising lys flakes, positioned boxes, painted over the day name, the date, **Log out**, **Back to the plan** and the opening moment of the closed page; on the closed pages they filled the middle block only.
- In the sipping pose the mug floated beside the beak while the flipper swung down onto the belly.
- In the dark scheme the black of the vector Tux in the raffle card melted into the night blue surface (1.1:1): only the eyes, belly and feet showed.

**Safeguards and edge cases:**

- Design version 3 says "the rooms that pulse are live"; the pages do not, as that sentence would be wrong while the animations are paused: the still ring and the "Live" pill of `event_webapp_plan` carry the signal.
- The halo applies in the dark scheme only, to the Tux of the raffle card; the bars stay blue in both schemes.

**Checks:** see the 18.0.1.2.1 entry of `event_webapp_plan`: both test suites on a fresh database with the theme installed.

**Action required:** update the module (`-u rlq_event_webapp_plan`).

## 18.0.1.0.0

**Short title:** Rencontres Linux theme of the event day web app: design version 3 "Pause café animée", Tux with a coffee, animated vector Tux, ribbon of words, installable app in the colours of the event.

**Reason for the request:** the generic module `event_webapp_plan` carries no event branding; the look of Rencontres Linux au Québec (design version 3) and its Tux mascots belong in a separate theme module that depends on it.

**Changes:**

- `__manifest__.py`: depends on `event_webapp_plan`, joins `rlq_theme.scss` and `rlq_theme.js` to the bundle `event_webapp_plan.assets_webapp`, not an application.
- `views/webapp_templates.xml`: brand with the Tux avatar; mascot slot (rising lys flakes in every bar, string lights, tagline and Tux with a coffee on the home page, Tux with a coffee and "The coffee is brewing..." before the opening, vector Tux in the room bar and on the other closed pages); banner slot (yellow band, ribbon of words read once as a sentence by screen readers, pause button); home cards slot (Pause Café Linux card); home page: vector Tux in the raffle card, ornament under the content. Template `tux_svg`: original vector Tux with moving parts (eyes, flippers, mug and steam, headset, live dot, Zzz, confetti) and six poses.
- `static/src/webapp/rlq_theme.scss`: custom properties of `event_webapp_plan` for the light and dark schemes (contrast noted for each text pair), Bree Serif headings, lys motif of the bars, home header grid (phone and wide screen), pills, band and ribbon, cards, poster card, raffle shimmer, room bar, closed pages, ornament, vector Tux poses; every animation under `prefers-reduced-motion: no-preference`.
- `static/src/webapp/rlq_theme.js`: pose of the vector Tux from `ewp:day-state`, `ewp:bbb-state`, `ewp:raffle-drawn` and `ewp:motion`, wave on the first page of the tab; pause button of the ribbon (`aria-pressed`).
- `controllers/main.py`: subclass of the controller of `event_webapp_plan`; `_ewp_pwa_values()` gives the name "Rencontres Linux event day", the blue `#1F4E9E` and the Tux icons; `_ewp_base_values()` adds `rlq_show_poster`.
- `models/event_webapp.py`, `views/event_webapp_views.xml`: field `rlq_show_poster` ("Pause Café Linux card") on the event day, in the form.
- `static/src/webapp/img/`: Tux with a coffee, Tux avatar, poster, lys motif and lys glyph, app icons 192 and 512 px; `static/src/webapp/fonts/`: Bree Serif (latin, latin-ext) and its OFL licence; `static/description/`: icon, banner, index.html.
- `tests/test_theme.py`: theme assets, module files (no metadata, SVG without script), no other host, decorative vector Tux and its pose, alternative texts, text-only mode, ribbon and pause button, poster card option, web manifest; browser test of the poses and of the ribbon button.
- `README.md`: look, Tux poses, motion and accessibility, installable app, origin of the images and fonts, Tux credit.
- `i18n/`: template and French translation.
- `event_webapp_plan` 18.0.1.2.0 (same change): hook `_ewp_pwa_values()` for the name, colours and icons of the installable app; `max-width` of the conference frame on phones; tests that accept a theme module installed beside it.

**Bugs fixed:** none (new module).

**Safeguards and edge cases:**

- Text-only mode: the slots are not rendered, so no picture, mascot, ribbon or motion; the poster card keeps its heading and text.
- Without script, the server-side pose stays (sipping before the opening, sleeping after, live while the meeting runs, idle otherwise) and the ribbon still moves until "Pause animations" or the system setting stops it.
- `sessionStorage` refused: the wave comes on every page instead of the first one.
- The poster card is off by default on each day.
- The images supplied by the organisers were rewritten without metadata; their licence is still to be confirmed by them (see README).

**Checks:** fresh test database, `-i rlq_event_webapp_plan --test-tags /event_webapp_plan,/rlq_event_webapp_plan` with `EWP_AXE_JS` set (axe-core audit of the themed pages included). Screenshots in headless Chromium at 390 and 1280 px, animated, reduced motion and text-only, compared with the mockups of design version 3. black and isort (line length 79), ruff, prettier (JS, SCSS, XML), comment hygiene check, `msgfmt -c` (0 untranslated).

**Action required:** install the module (`-i rlq_event_webapp_plan`); tick **Pause Café Linux card** on the days that should show it.
