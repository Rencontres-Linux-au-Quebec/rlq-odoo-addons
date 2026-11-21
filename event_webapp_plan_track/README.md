# Event Web App Plan - Agenda (`event_webapp_plan_track`)

Odoo 18.0 module. It shows the agenda of an event day in the web app of
`event_webapp_plan` (`/webapp_event`), from the tracks of the events
(`website_event_track`). The program is typed once, as event tracks, with
their location, speaker and tags; the web app reads it. The generic module
`event_webapp_plan` keeps no dependency on the website: only this bridge
brings `website_event_track`.

## Setup

1. In **Events > Configuration > Track Locations**, create one location
   per place of the program (a room, a hall, a stand).
2. Give each track of the events of the day its date, duration and
   location, publish it (**Published** on the track, or a stage that
   publishes), and add its speaker (name and job position) and tags.
3. In **Event Web App > Event days**, open the day: its **Events** tab
   lists the events of the tracks; in the **Plan & Rooms** tab, choose the
   **Track location** of each room in the room list under the plan editor.
   A location serves one room per day; a room without location shows no
   agenda of its own, and its tracks stay in the agenda of the home page.
4. The **Agenda** tab of the day lists, read only, the tracks the web app
   shows.

The day shows the tracks of its events that:

- overlap its opening window (they start before it closes and end after
  it opens);
- are published (`is_published`);
- are not in a cancelled stage (`is_cancel`);
- have a start date, and are not archived.

The Event Web App Moderator group reads the track locations (needed by the
room list); creating them stays in the Events application.

## What the visitor sees

- **Home page**: an **Agenda** card, first of the main column (the slot
  `webapp_slot_home_cards`), after the announcement and the links on a
  phone. The sessions are grouped by start time: an ordered list of time
  slots, each with a heading (the time), holding the list of its sessions.
  Each session shows its title (a heading), its time range, its room (a
  link to the room page when a room follows the location, the name of the
  location otherwise), its speaker and job position, and its tags as text
  badges (tags without colour are internal, as on the website, and never
  shown). The session in progress carries the badge **Now**, the sessions
  of the next start the badge **Next**.
- **Filter by room**: under the heading, toggle buttons **All rooms** and
  one per room that has sessions (shown from two such rooms). The pressed
  one has `aria-pressed="true"` and the check mark of the toggle buttons of
  the display options. Without script, the buttons send a GET form
  (`?agenda_room=<room id>#ewp_track_agenda`) and the server marks the
  other sessions `hidden`; with script, the page filters in place, keeps
  the choice in the address and says in the live region how many sessions
  it shows. A hidden session leaves the screen and the accessibility tree,
  even beside a shown session of the same start. With a single busy room
  no filter is offered, and a choice still in the address hides nothing.
- **Room list** (home page, under the plan): under each room that has
  sessions, "Now: <title>" or "Next at <time>: <title>", hidden once the
  room has nothing left for the day. On the plan, the area of a room with
  a session in progress gets a still dot in its corner (the area is
  hidden from assistive technologies: the room list says it in words).
- **Room page**: a block **In this room**, last of the page (the slot
  `webapp_slot_room_main`), under the conference and the chat (across
  both columns on a wide screen): the state of the room ("Now: ...",
  "Next at ...: ..." or "No more session in this room today.") and the
  list of the sessions of the room, each with its description in a
  `details` element, collapsed.

## Times and states

Each time shows in the time zone of the event of the track (`date_tz`),
else in the time zone of the page, in the short time format of the
language of the user (babel, through `format_time`; "9:00 AM" in English,
"09 h 00" in French of Canada). Every time is a `<time datetime="...">`
with its offset, so a screen reader or a script reads the exact moment.
The card says the time zone ("Times in the time zone of the event:
America/Montreal.").

The server renders the states once; the script of the page
(`static/src/webapp/agenda.js`) recomputes them from the clock of the
device at each start or end of a session, at least every minute, and when
the tab shows again, without reloading the page. Every 5 minutes while the
tab is visible, it asks the program again
(`/webapp_event/<day>/agenda`): when the organisers changed it, the
agenda blocks are replaced (open descriptions stay open; never while the
focus is inside a block, the next answer applies it then).

## Accessibility

- Headings: the card `h2`, a time slot `h3`, a session `h4` (on the room
  page: the block `h2`, a session `h3`); lists for the slots and the
  sessions.
- The badges **Now** and **Next** are words, not colours; the bar beside a
  session and the dot of a room only repeat them. Nothing moves: no
  animation, no transition, so the animation settings have nothing to
  stop.
- The room link of a session, the filter buttons and the summary of a
  description are at least 44 px tall or inline links, with the focus
  ring of the pages.
- **Text-only mode**: every block renders as linear text in one column,
  without the bars, dots and plan.
- **Live region**: on a room page, a session of that room that starts
  while the page is open is said once in the shared live region ("Now in
  this room: <title>."); the filter says the number of sessions shown.
  The states found when the page loads are not said.

## Access

The tracks are read through the sudo day, once `event_webapp_plan`
allowed the user (opening window, or the Moderator group), and only the
fields shown leave the server: no e-mail, no phone, no contact of the
speaker. A track that is not published, in a cancelled stage, of another
event, or outside the window never reaches a page nor the JSON route. The
description is sanitised again before it is shown.

**JSON route** `/webapp_event/<day>/agenda` (GET, logged-in users): the
same checks as the raffle route of the web app, an archived or unknown
day gives 404, a day outside its window gives 403 to a visitor; with
`?room=<id>`, a room of that day only (404 otherwise). It answers
`signature` (changes with the program, not with the clock), `sessions`
(the fields the script reads), `html` (the agenda block of the home page)
and, with a room, `room_html` (the list of that room).

## Theming

The blocks take the custom properties of the pages (`--ewp-*`) and the
classes `ewp_track_*`; a theme restyles them as the rest of the web app.
`webapp.js` of `event_webapp_plan` says the messages of `ewp:announce`;
the agenda adds one DOM event, sent on `document` (bubbling):

| Event | `detail` | Sent |
| --- | --- | --- |
| `ewp:session` | `room` (`{id, name}`, or `null` for a location without room), `track` (`{id, title, start, end}`, ISO 8601 with offset), `state` (`start` or `end`) | when a session of the page starts or ends while the page is open (never for the states found at load) |

```javascript
document.addEventListener("ewp:session", (ev) => {
    if (ev.detail.state === "start") {
        console.log(ev.detail.track.title, ev.detail.room && ev.detail.room.name);
    }
});
```

The items `.ewp_track_session` carry `data-ewp-track-id`,
`data-ewp-room-id` and `data-ewp-state` (`past`, `now`, `next`, `later`),
the room lines `data-ewp-track-room` and `data-ewp-state` (`now`,
`next`), and an area of the plan `data-ewp-session="now"`.

A session that starts while the page is open (on a room page, a session
of that room) also plays one `speak` cameo of the cameo engine of
`event_webapp_plan` (`window.ewpCameo.play`) near the room block or the
agenda card: the actor of the theme speaks in a microphone. Several
starts at the same moment play one cameo; the engine plays nothing while
the animations are paused or in text-only mode.

## Tests

```bash
odoo-bin -d TEST_DB -i event_webapp_plan_track --test-enable \
    --http-port 8369 --gevent-port 8372 \
    --test-tags /event_webapp_plan_track --stop-after-init
```

Use a disposable database and free ports. `tests/test_models.py` covers
the tracks of a day (window overlap, publication, cancelled stage, events
of the day, order) and the one-room-per-location rule;
`tests/test_controllers.py` the pages (card, states, room links, speaker,
tags, filter without script, a choice in the address with a single busy
room, room lines, room block, sanitised
description, text-only mode, time zone and language) and the JSON route
(anonymous, closed day, room of another day, no unpublished track);
`tests/test_selenium_agenda.py`, on the `SeleniumCase` of
`event_webapp_plan`, a real browser: "Now" and "Next", the filter by
mouse and by keyboard, with and without script a session hidden beside a
shown one of the same start, the way from a session to its room and to a
description by keyboard, a short track that starts and ends while the room
page is open, then moved and started again (said once in the live region,
`ewp:session` sent at each start and end), and
axe-core on the home and room pages with the agenda, in the light and dark
schemes and in text-only mode, when `EWP_AXE_JS` names a copy of
`axe.min.js` (see the README of `event_webapp_plan`).

## License

AGPL-3.0 or later. Copyright (C) 2026 Services-Conseils Linux Inc.,
Rencontres Linux au Québec contributors.
