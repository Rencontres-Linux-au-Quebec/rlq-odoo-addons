# Event Web App Plan - Rencontres Linux theme (`rlq_event_webapp_plan`)

Odoo 18.0 module. The look of the event day web app (`/webapp_event`,
module [`event_webapp_plan`](../event_webapp_plan/README.md)) for
Rencontres Linux au Québec: design version 3, "Pause café animée". It adds
no page and no route; it restyles the pages of `event_webapp_plan` through
its theme hooks (template slots, CSS custom properties, DOM events) and
changes the name, colours and icons of the installable app.

Install it beside `event_webapp_plan`; uninstall it to get the plain look
back. It depends on
[`event_webapp_plan_track`](../event_webapp_plan_track/README.md), the
agenda of the web app, which pulls `website_event_track` (and with it the
website and `website_event`) into the database.

## Example event day (demo data)

In a database created with demo data, the module loads an example day,
"Journée portes ouvertes sur Linux 2026" (`demo/event_webapp_demo.xml`,
`noupdate`), so the agenda can be seen in the app without typing anything.
A database without demo data gets none of it. The people of the example
are invented: no surname, organisation or biography comes from a real
speaker.

- **Event** (`event.event`): Saturday 21 November 2026, 8:00 to 18:00 in
  `America/Montreal`, three free tickets (Visiteur, Bénévole,
  Commanditaire), no address. The dates are stored in UTC, the event
  being in standard time (UTC-5) on that day.
- **Agenda**: five track locations, in the order of the agenda; four
  coloured tags (Présentiel, Virtuel, Démo_Débutant, Démo_Avancé) in the
  category "Formule"; 21 published tracks from 7:30 to 21:00, each with
  its place, its tags, a speaker and a job position when it has one, and
  a description.
- **Raffle** "Prix de présence": 7 draws, one per draw track of the agenda
  (11:00 to 17:00), placeholder prizes "Prix de présence 1" to "7", no
  winner.
- **Event day** (`event.webapp`): open from 7:30 to 21:00, the event and
  the raffle, an announcement in French, the Pause Café Linux card, one
  link to the events of the website (`/event`), a generic plan
  (`demo/event_plan.png`, five numbered rectangles) and five rooms whose
  areas match the rectangles, each following one track location. No
  conference is set.

To see the states "Now" and "Next" before the day, open the day as a
moderator: the agenda lists the sessions, all to come; on the day, they
follow the clock.

## Look

- **Colours**: blue bars `#1F4E9E` (navy `#163B78`) under a fleur-de-lys
  motif, a yellow rule and accents `#FFCB2E`, a cream background `#FFF7DB`,
  white cards with a golden border. The dark colour scheme of the device
  gets a night blue variant; the bars stay blue in both.
- **Fonts**: Bree Serif for the headings, Inter (from `event_webapp_plan`)
  for the text.
- **Home page**: string lights over the header (phone), the Tux avatar and
  the app label, the tagline "GNU/Linux · Québec", the day and its state,
  and Tux with his coffee on the right (phone) or on the left (wide
  screen); the yellow band with the ribbon of words "Convivial,
  Informatif, Amusant, Discussions sympas, Trucs et astuces, Questions et
  débats"; a lys before the headings of the links, plan and events; the
  area of a live room glowing on the plan, beside its pulsing "Live" pill
  in the room list; the raffle winners on a shimmering yellow; an ornament
  under the content. In the dark scheme, the vector Tux of the raffle card
  has a light halo, so its black outline stays visible on the night blue;
  so do the Tux cameos.
- **Pause Café Linux card**: when **Pause Café Linux card** is ticked on
  the event day (tab header, group "Web app"), the home page shows the
  card of the weekly Pause Café Linux, with its poster: on a phone, the
  first card, before the announcement, poster on top; on a wide screen, at
  the top of the main column, poster on the left. It fills the lead slot
  of `event_webapp_plan`, so the reading order follows the same order.
- **Room page**: the blue bar with a lys before the room name and the
  vector Tux, the ribbon, the conference frame framed in navy, which glows
  while the meeting runs.
- **Rising lys**: nine yellow and white lys of 14 to 24 px rise in every
  bar and over the whole closed page, over the blue of the bar but behind
  its texts and controls.
- **String lights**: each bulb dims and glows again, a third of the
  string at a time.
- **Closed pages**: the whole page under the lys motif. Before the
  opening, Tux with his coffee and "Le café infuse…"; after the closing,
  the vector Tux asleep; the opening and closing moments in a navy box.

Every text pair meets WCAG 2.2 AA contrast (4.5:1, 3:1 for icons and
large text); the values are noted beside the colours in
`static/src/webapp/rlq_theme.scss`.

## Tux

**Tux with a coffee** (picture `tux-cafe.jpg`) stands in the home header
and on the "not open yet" page. It rocks on its feet (7 px up, 4 degrees
each way, every 3 s) and three wisps of steam rise from the mug. Its
alternative text describes it.

**Vector Tux** (template `rlq_event_webapp_plan.tux_svg`) is an original
drawing in the classic Tux shape, with a fleur-de-lys on the belly and a
lys mug. It stands in the room bar, in the raffle card of the home page
and on the "over", "no event day" and "conference left" pages. Its pose
follows the page (`data-rlq-tux`, set by the server, then by
`rlq_theme.js` from the events of `event_webapp_plan`):

| Pose | When | Motion |
| --- | --- | --- |
| `idle` | day open | blinks, breathes with a sway, steam over the mug, flaps a flipper every 5 s |
| `greeting` | first page of the browser tab, Tux awake | waves a flipper for 3 s, then idle |
| `sipping` | before the opening (`ewp:day-state` `before`) | lifts the lys mug, tips his head back for the sip, puts it down, every 5 s |
| `celebrate` | a raffle winner is drawn (`ewp:raffle-drawn`) | flippers up, jumps, confetti, for 4.5 s |
| `sleeping` | day over (`ewp:day-state` `after`) | eyes shut, Zzz |
| `speak` | the room meeting runs, in the frame or behind the new tab button (`ewp:bbb-state` with `live`) | holds a microphone at his beak, which opens and closes, sound waves, a speech bubble with dots, a pulsing live dot |
| `coffee` | the room meeting waits (`ewp:bbb-state` `waiting`) | the sip of `sipping`, every 3.6 s |
| `wave` | the conference is left (`ewp:bbb-state` `left`, also on a room page rendered after a leave), the "conference left" page | waves a flipper for 4 s |
| `code` | cameos | slides a laptop onto his lap, types with both flippers, eyes on the screen, whose glow pulses; code glyphs `{ }`, `</>`, `$_` and `git` float up and fade |
| `walk`, `peek` | cameos | waddles on alternate feet; looks left and right |

Each pose is readable while still: a paused page keeps the pose of the
moment without its motion. The waves stop by themselves after 3 or 4 s.

The vector Tux is decorative (`aria-hidden`, `focusable="false"`, no id,
no text inside, the code glyphs being strokes): the live region of
`event_webapp_plan` already announces the winners and the conference.

**Tux cameos.** `rlq_theme.js` registers two actors with the cameo engine
of `event_webapp_plan` (`window.ewpCameo`), drawn from a copy of the
vector Tux kept in an inert `<template class="o_rlq_tux_source">` of the
mascot slot (absent in text-only mode):

- `rlq-tux` plays the actions of the schedule: `coffee`, `code`, `wave`,
  `peek` (rises from the bottom edge of its box, looks around, hides) and
  `walk` (paces across its box and turns back);
- `rlq-tux-moments` plays the actions of the page events: `celebrate`
  near the raffle card for a winner, `speak` near the conference when it
  runs, `sleep` near the closed page once the day is over. Its weight in
  the random draw of the schedule is 10^-6, so the schedule practically
  never plays them.

The engine decides when and where: a first cameo 2 to 3 s after the page
is ready, then one every 4 to 8 s, at most one
on a phone and two above, each one under 7 s, never over a control, a
picture or a text. Tux measures 60 px on a phone and 88 px above (a
larger box finds no free spot on the room page at 1280 x 900). The moving
words of the ribbon and of the ornament carry `data-ewp-cameo-avoid`:
they are hidden from assistive technologies but shown, and no cameo
covers them. A cameo is a `.o_ewp_cameo` of the engine holding
`.o_rlq_cameo_stage.o_rlq_cameo_<action>` and the drawing in the pose of
the action.

## Motion and accessibility

- Every animation (lights, rising lys, Tux and its cameos, ribbon, card
  entrance, live pulses, winner shimmer, conference glow) is declared
  inside
  `@include ewp-motion-allowed` of `event_webapp_plan`: it plays under the
  animation mode **On**, and under **Follow the device** unless the device
  asks for reduced motion. It stops with the mode **Off** and in text-only
  mode (body classes `o_ewp_motion_off`, `o_ewp_motion_paused`), as the
  rules of `event_webapp_plan` set every animation to `none` there. A
  paused Tux keeps the still pose of the moment; the waves are skipped
  and the cameo engine removes every cameo at once. No animation flashes:
  the bulbs dim and glow again once in 1.8 s, and every move is a
  transform or a fade.
- **Ribbon**: screen readers read its words once, as a sentence, inside
  the header (banner landmark) of the page; the moving copies are hidden
  from them (no `role="marquee"`). Its track
  holds six copies of the words, enough to fill a band of about 3600 px at
  every moment of the loop. The button at its end (**Pause the scrolling
  words**, `aria-pressed`) stops it alone; it also holds while hovered or
  focused. A ribbon that stands still (its button, the mode **Off**,
  reduce motion under **Follow the device**) shows its six words once, wrapped on several lines, so
  none stays out of the band. The button is hidden when every animation
  is paused.
- **Live rooms**: the glow of a live room on the plan is motion on top of
  the still ring and the "Live" pill of `event_webapp_plan`; design
  version 3 says "the rooms that pulse are live", the pages do not, as
  that sentence would be wrong while the animations are paused.
- **Text-only mode**: no mascot, no ribbon, no lights, no ornament, no lys
  icon, no bar motif (the slots are not rendered); the Pause Café Linux
  card keeps its heading and text, without the poster.

## Installable app

The web manifest and the pages use the name "Journée Rencontres Linux"
(short name "Rencontres Linux"), the blue `#1F4E9E` for the theme and the
splash screen, and icons made from the Tux avatar inside the safe zone of
a maskable icon (`static/src/webapp/img/icon-192.png`, `icon-512.png`).
The module overrides `_ewp_pwa_values()` of the controller of
`event_webapp_plan`.

## Images, fonts and their origin

| File | Content | Origin |
| --- | --- | --- |
| `static/src/webapp/img/tux-cafe.jpg` | Tux with a fleur-de-lys and a lys coffee mug | supplied by the Rencontres Linux au Québec organisers for the event design |
| `static/src/webapp/img/tux-avatar.jpg` | head and shoulders of the same Tux | same |
| `static/src/webapp/img/pause-cafe-linux.jpg` | "Pause Café Linux" poster | same |
| `static/src/webapp/img/lys-motif.svg` | fleur-de-lys motif of the bars | same, rewritten without id or script |
| `static/src/webapp/img/lys.svg` | one fleur-de-lys, used as a CSS mask | drawn from the same motif |
| `static/src/webapp/img/icon-*.png`, `static/description/icon.png` | app icons | made from `tux-avatar.jpg` |
| `static/description/banner.jpg` | module banner | the poster, reduced |
| `demo/event_plan.png` | generic plan of the example day: five numbered rectangles and a corridor | drawn for this module with Pillow |
| vector Tux in `views/webapp_templates.xml` | Tux in eleven poses, with a laptop, a microphone and a speech bubble | original drawing for this module |

The licence of the images supplied by the organisers is to be confirmed by
them. The JPEG files carry no metadata (EXIF, XMP, comment): they were
rewritten pixel by pixel. The poster shows the BigBlueButton logo, a
trademark of its owner.

**Tux**: the penguin mascot of Linux was designed by Larry Ewing with The
GIMP ("Tux by Larry Ewing, created with The GIMP"). Its author allows its
use and modification, provided he and The GIMP are
acknowledged when someone asks. The vector Tux of this
module is a new drawing in that classic shape.

**Bree Serif** (`static/src/webapp/fonts/`): TypeTogether, SIL Open Font
License 1.1 (text in `OFL-BreeSerif.txt`); woff2 files of the latin and
latin-ext subsets from the `@fontsource/bree-serif` npm package 5.3.0. The
pages request nothing from another host.

## Tests

```bash
odoo-bin -d TEST_DB -i rlq_event_webapp_plan --test-enable \
    --test-tags /event_webapp_plan,/event_webapp_plan_track,/rlq_event_webapp_plan \
    --stop-after-init
```

Use a disposable database. `tests/test_selenium_tux.py` (Selenium, on the
base class of `event_webapp_plan`; see its README for the browser) checks
that the Tux actors replace the neutral one, at 60 and 88 px, come in and
leave; that each action (coffee, code, speak, walk, peek, wave,
celebrate, sleep) gets its class, its pose and its own keyframes running
under the mode **On** with reduced motion emulated; that nothing plays
and nothing moves under **Off** or in text-only mode; that the room Tux
drinks while the conference waits, speaks once it runs (with a cameo near
it) and waves when it is left; that a real raffle draw makes Tux
celebrate; and that no Tux cameo covers a control, a text or the marked
words, at 390 and 1280 px. `tests/test_demo.py` checks the example day: five rooms, each following a
location, 21 tracks on 21 November 2026 in the time zone of the event
(first at 7:30, last ending at 21:00), the 7 draws on the times of the
draw tracks, and, with the clock of the server set to 10:30 that day, the
21 sessions of the home agenda in time order, each with a link to its
room, the session in progress marked "Now" and the next ones "Next", and
the room page that says what happens in it. It skips itself in a
database without demo data; the other tests set every day inactive
before creating their own, so they pass with or without the example.
`tests/test_theme.py` checks the theme assets of
the bundle, the images and fonts served by the module (without metadata,
the SVG files without script), that nothing comes from another host, the
vector Tux (decorative, pose of the page, the room poses), its inert
copy for the cameos (no id, text, link or script, every part present),
the poses and keyframes in the stylesheet, the alternative texts, the
text-only mode, the ribbon (inside the header) and its pause button, the
poster card option and its place before the announcement, and the web
manifest. Its browser tests (headless Chrome, skipped without
it) follow the poses through the events of the page and a real raffle
answer, check the geometry of the sipping pose, the halo of the dark
scheme, the ribbon that covers its band and stands still with every word
in view, the poster card first on a phone and at the top of the main
column on a wide screen, the flakes behind the content, and that every theme animation
stops with the mode **Off** and with reduce motion under **Follow the
device**, and plays under **On** even then. The tests
of `event_webapp_plan` run with the theme installed, its axe-core audit
included when `EWP_AXE_JS` is set (see the README of
`event_webapp_plan`).

## License

AGPL-3.0 or later. Copyright (C) 2026 Services-Conseils Linux Inc.,
Rencontres Linux au Québec contributors.
