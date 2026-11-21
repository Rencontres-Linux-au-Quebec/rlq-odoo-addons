# Event Web App Plan (`event_webapp_plan`)

Odoo 18.0 module. A mobile, installable web app for one event day at
`/webapp_event`, reserved to logged-in users (portal or internal).
Anonymous visitors are sent to the login page and come back after login.
The short address `/w` (and `/w/<day>`) redirects to `/webapp_event` (and
`/webapp_event/<day>`) with the same query string, easier to type or to
print on a poster.

## What the visitor sees

- the general announcement and the links of the day;
- the events of the day;
- the site plan: each room is a clickable area; the room page embeds the
  room's Discuss channel, which the visitor joins automatically so they
  can write at once, and keeps reading once the day is over; a room whose
  meeting runs is marked "Live" on the plan and in the room list;
- the BigBlueButton conference of the room, beside the chat (see
  BigBlueButton);
- the raffle draws of the day (module `event_raffle`), refreshed live.

**Automatic updates.** Above the display options, the home and room pages
list the blocks that refresh by themselves (raffles, live rooms,
conference, and the rows other modules add: "My prize", "Agenda"), each
with the age of its last answer and a countdown to its next request,
"Failed, retrying in ..." after a failed answer (the next try of the
conference doubles while its server fails), "Paused while the page is
hidden" while the tab is hidden, "Stopped, reload the page" once the
session or the day ends. The section shows with the first refresher that
reports, never without script; it is not a live region, so a screen
reader reads the countdown only on demand. The intervals do not change:
30 s for the raffles and the live rooms, 20 s for a conference that has
not started (up to 2 minutes while its server fails).

## Configuration

Application **Event Web App > Event days** (groups below). One record per
day:

| Tab | Content |
| --- | --- |
| (header) | name, opening and closing moments |
| Announcement | rich text shown at the top of the page |
| Links | label, URL, description, ordered by drag and drop |
| Events | `event.event` records of the day |
| Raffles | `event.raffle` records of the day, pre-filled (see below) |
| Plan & Rooms | plan image, visual room editor, list of rooms |

**Visual room editor**: select a room in the side list (or click its area),
then work on the plan with the mouse, a pen or a finger:

- **draw**: drag on the plan outside the selected area to draw a new
  rectangle for the room (its angle goes back to 0). A press shorter than
  1 % of the image along either axis is a click: it selects the topmost
  room under the pointer, so a drag that starts on the area of another room
  draws the selected room, and a click there selects the other room;
- **move**: drag inside the selected area. A click inside it, without a
  move, selects the topmost other room under the pointer (a booth drawn
  inside a hall, or the hall under a booth), so every room stays reachable
  from the plan; with no other room there, the selection stays;
- **resize**: drag one of its eight handles (corners and sides). On a
  turned area the handles work along the sides of the area: the opposite
  corner or side stays where it is on screen. A handle dragged past the
  edge of the image stops the area at that edge;
- **rotate**: drag the round knob above its top edge; the area turns around
  its centre by steps of 15°, by steps of 1° while Shift is held, and the
  angle shows next to the knob during the drag. A move or a turn starts
  after 4 pixels: a click on the knob or inside the area changes nothing.

Under the selected room, **Rotate left** and **Rotate right** turn the area
by 15° (1° with Shift), the field **Angle (°)** takes any angle (decimals
accepted, 270 becomes -90) once it loses the focus, and **Straighten**
brings it back to 0°. These controls are reached with Tab and work with the
keyboard; they are disabled for a room without area. **Remove from the
plan** clears the area.

Areas are stored in percent of the image, so they follow the image at any
displayed size, with an angle in degrees, clockwise, from -180 (excluded)
to 180; the server brings any other angle into that range. The rectangle
before it turns always stays inside the image (the editor shifts a moved
area back inside, and stops a resized one at the edge); the corners of a
turned area may go past the edges, and the editor and the public plan clip
them. On the public plan, a turned area turns around its centre, a click
answers in its turned shape, its number and label stay level, and the
position words of the room list, read from the centre, do not change. At
rest, the label of a turned area is as wide as the level line across its
centre (the short side of an upright corridor), and neither the label nor
the number takes the pointer, so a click beside a turned area never opens
it. In a read-only form the areas show
turned, without handles or controls.

The list below the editor edits the name, colour, description and chat
channel; the numerical position columns, the angle among them, are
available through the optional columns.

Each new room gets its own access group, named "<day> - <room>" in the
category **Event Web App Rooms**, and a Discuss channel of type "channel"
whose authorized group is that room group (see Access). Both are renamed
with the day or the room. A room accepts only a top-level channel of type
"channel" that serves no other room, never a private conversation or a
thread. A channel linked by hand must be open to everybody (no authorized
group) or already restricted to the room group, and then gets the room
group as its authorized group; only the Settings group may link a channel
restricted to another group, since its whole history then goes to the room
visitors. The access group itself is managed by the room: it cannot be
chosen by hand, through the form, an import or the API, nor through a
default value (context or user default). A duplicated day gets new groups and new channels for its
rooms: the visitors of the original do not enter the copy. The button
**Create missing chat channels** recreates the group and the channel of a
room that lost them. The optional column **Access group** of the room list
shows the group.

**Raffles of the day**: the raffle block of the web app shows the raffles
listed on the day, and only those. The list is pre-filled, then edited by
hand. A raffle of an event listed on the day joins the day when:

- its **Planned Date** (field of `event_raffle`) falls inside the opening
  window, bounds included; a raffle of an event held over several days
  thus joins the day of its draw only;
- without planned date, its event begins and ends inside the window: a
  one-day event brings its raffles, an event held over several days waits
  for their planned dates.

A test raffle never joins. The pre-fill runs when a raffle starts to fit a
day: the day gains the raffle's event, the window of the day moves, or the
raffle is created or gets a new planned date, event or test flag. In the
form, adding an event or moving the window shows the raffles at once,
before saving. Nothing is ever removed automatically: a raffle removed by
hand stays off through any later write that leaves its fit unchanged,
such as adding another event, renaming the day, or a new planned date
inside the same day. A change of the event's own dates adds nothing. A
duplicated day keeps the raffle list of the original as it is.

The day side searches the candidate raffles as superuser, then adds only
those the user who saves the day may read (company rules). The raffle
side adds the saved raffle as superuser, to the days that already list its
event: the user who saves a raffle seldom may write the days.

**Default day**: `/webapp_event` shows the active day that is open now,
else the next one to open, else the one that closed most recently.

## Access

| Group | Rights |
| --- | --- |
| Event Web App / Moderator | reads the days; sees the web app outside its opening window; reads every room chat while in the group |
| Event Web App / Administrator | creates and edits the days (implies Moderator) |
| Event Web App Rooms / "<day> - <room>" | one group per room: reads and writes in that room's chat; given on entering the room page, never withdrawn (see below for the moderators) |
| Settings | the BigBlueButton server, its secret and the display mode; the list of the meetings of the server and the meeting of each room |
| Portal and internal users | see the web app during its opening window only |

Portal and internal users have no access right on the models: the
controller reads them with sudo and renders only the fields of the page.

**Room chats.** Odoo serves `/discuss/channel/<id>` to anyone who can read
the channel, anonymous visitors included, so each room channel is
restricted to the group of its room. A logged-in user who may see the day
(during the opening window, or a moderator at any time) and opens the room
page receives that room's group and joins the channel. Nothing withdraws
the group: the chat stays in the user's Discuss and readable at
`/discuss/channel/<id>` once the day is over. Anonymous visitors, guests of
an invitation link, and users who never entered that room get a 404. The
Moderator group implies every room group, so moderators and administrators
read every room chat without entering the rooms. The room groups are
visible in the user form in debug mode only.

**Leaving the Moderator role.** Odoo never takes an implied group back
from a user who leaves the implying group. The module does: a user who
leaves the Moderator group (user form, group form or API) loses every room
group except the rooms they entered while outside the role, recorded on
the user at each such visit (field "Event web app: rooms entered",
Settings group only). A moderator's own visits record nothing: their access
came from the role. Update 18.0.1.9.0 records as visits the room groups
already held by the users outside the role.

**Room channel access is locked.** Odoo lets every internal user write a
channel they can read, so a room visitor could empty its authorized group
(the chat would then be readable by anonymous visitors), set another one,
archive the channel or subscribe whole groups to it. On a channel linked
to a room, or restricted to a room group (the channel of a deleted room
too), the authorized group, the auto-subscribed groups and the archiving
are reserved to the Settings group and to the module itself; the name and
the description stay editable.

**Deleting.** Deleting a room, or a whole day, keeps the room's group and
channel linked together: the channel never loses its authorized group, so
it never becomes public, and the people who took part keep its history.
Odoo refuses to delete a room group while a room or a channel still uses
it.

## Room chat embedding

The room page embeds `/discuss/channel/<id>` in a same-origin iframe. Odoo
sends no `X-Frame-Options` header on that route; a reverse proxy that adds
`X-Frame-Options: DENY` to every response breaks the embedding
(`SAMEORIGIN` keeps it working).

## BigBlueButton

A room can show a BigBlueButton conference: above the chat on a phone, on
the left of the chat (a column of 380 px) on a wide screen. The room page
picks, in this order:

1. **Meeting ID** (`BBB meeting ID` of the room), when the server URL and
   its shared secret are set in **Event Web App > Configuration >
   Settings** (group Settings). The page asks the server whether the
   meeting runs (`getMeetingInfo`). If it runs, the page shows the meeting
   in an iframe or behind a button that opens it in a new tab (see
   **Display mode** below), through a fresh join URL: the visitor's name,
   the role
   `MODERATOR` for the Moderator and Administrator groups and `VIEWER` for
   everyone else, `odoo-<user id>` as user ID, and the `createTime` of the
   running session, so a copied join URL stops working when the session
   ends. If it does not run yet, the page says "The conference has not
   started yet", asks again every 20 seconds (paused while the tab is
   hidden) and reloads itself once it runs, or once the server stops or
   starts answering. The web app never creates a meeting: the host starts
   it, from Greenlight for instance.
2. **Conference URL** (`Conference URL` of the room, http or https only),
   when the meeting ID cannot be used or the server does not answer. The
   URL is shown in an iframe when its headers allow it (`Shown in the
   page`) and the display mode accepts it, else behind a large **Join the
   conference** button that opens it in a new tab.
3. Nothing: the room page shows its chat only.

**Display mode.** BigBlueButton keeps the session of its client in a
cookie (`JSESSIONID`), set by the join URL without a `SameSite`
attribute. Chromium-based browsers (Chrome, Edge) treat such a cookie as
`SameSite=Lax`: inside an iframe of a page from another site, they do
not send it, the client is refused (401) and shows "Oops, something went
wrong". The same join opened in a tab of its own works. A browser that
blocks third-party cookies refuses the cookie in such an iframe unless
it is `Partitioned`, where it supports partitioned cookies. Safari
refuses it in any case. The setting **Video conference display** (Settings group,
next to the server; config parameter `event_webapp_plan.bbb_display`)
offers three modes:

- **Automatic** (`auto`, the default, also for an unset or unknown
  value): the iframe only when the server (or the conference URL) is on
  the same site as the room page, else the button;
- **Always embedded in the room page** (`frame`);
- **Always in a new tab** (`tab`).

The behind-the-button page of a running meeting says "The video
conference is live" above a large **Join the video conference** button,
with the hint that the room page and its discussion stay open. It keeps
asking the status route every 20 seconds and loads itself again when the
meeting ends (it then shows the waiting notice) or the server stops
answering.

**Same site.** Two URLs are on the same site when their schemes match
(`http` and `https` are two sites), whatever their ports, and their
hosts are equal or share their registrable domain: `bbb.example.org` and
`app.example.org` are one site, `bbb.example.org` and `app.example.net`
two. The page URL is the origin of the request (`web.base.url` outside a
request). The registrable domain comes from the public suffix list of
the `tldextract` library when it is installed (its bundled copy; nothing
is downloaded). Without it, a built-in rule keeps the last two labels of
the host, or the last three when the last two look like a two-level
public suffix (a label of 3 characters or fewer under a two-letter
country code: `qc.ca`, `co.uk`, `com.au`). An IP address or a
single-label host (`localhost`) is on the same site as itself only. The
rule errs toward "another site": that only costs the iframe, the button
always works.

**Embedding a server of another site.** An administrator who controls
the BigBlueButton server and wants **Always embedded** must make that
server send its session cookie with `SameSite=None` and `Secure` (and
`Partitioned`, for the browsers that block third-party cookies but
accept partitioned ones). This is a setting of the BigBlueButton server
(its web server or the application behind it), not of Odoo. Safari
refuses the cookie in a frame from another site all the same: its
visitors need the new tab.

The iframe, **Open in a new tab** next to it, and the new tab button
load `/webapp_event/<day>/room/<room>/bbb_join`, which checks access again and
redirects to a fresh join URL (or to the conference URL). The pages
themselves carry no join URL and no server address. When there is nothing
to join any more, the route sends a tab back to the room page and answers
the iframe (`?frame=1`) with an empty 204. After **Open in a new tab**,
the frame of the room page is closed, so the visitor is in the meeting
once, from the new tab; reloading the room page brings it back.

**Live rooms on the home page.** The home page itself never asks the
server. Once loaded, its script asks `/webapp_event/<day>/live` (JSON
`{"live": [room ids]}`), then every 30 seconds while the tab is visible:
the route asks the server about each room with a meeting ID, through the
same cache as the room page, and names neither the server nor a meeting
ID. A room with a conference URL only is never "Live": that URL says
nothing about a running session.

**Leaving the meeting** (meeting ID mode). The join URL carries
`logoutURL`, a `join` parameter of BigBlueButton 3.0 and later (see the
[API reference](https://docs.bigbluebutton.org/development/api/#get-join)):
it points to `/webapp_event/<day>/room/<room>/bbb_left?frame=1` on
`web.base.url` for the iframe, and to `bbb_left` without `frame` for a
join outside the iframe, instead of the logout page of the meeting, which
Greenlight sets when it
creates the meeting and which may be blank or refuse framing. Once the
visitor leaves and confirms the end screen of the client, the frame loads
that page. The room page recognises it, empties and hides the frame, and
shows "You left the conference." with a **Join again** button, which
takes the focus. **Join again** asks the server whether the meeting still
runs (`bbb_status?fresh=1`, which accepts a cached state 2 seconds old at
most: when the host ends the meeting, every client lands on `bbb_left` at
once, and a state cached before the end would send the visitor to a join
URL the server refuses): if so, the frame loads `bbb_join?frame=1` again
(a fresh join URL); if not, the page loads again and shows the waiting
notice. The chat is not touched. A server older than 3.0 ignores the parameter and sends the
client to the logout page of the meeting, on another host: the page also
treats any load of the frame after the first one (the client) as a leave.
In a tab opened by **Open in a new tab** or by the new tab button,
`bbb_left` (without `frame`) answers a 303 redirect to the room page with
`left=1`, which that tab then shows. When that room page embeds the
meeting, it renders the frame without src and "You left the
conference." with **Join again** already shown, the focus on that
button: a frame with its src would join the visitor again at once.
Behind the new tab button, the marker changes nothing. `bbb_left`
applies the checks of the room page before either answer. A framed conference URL keeps its frame as is: its pages may load
one another, so a second load does not mean the visitor left.

The waiting page loads itself again with `location.replace()`, not
`location.reload()`: on a reload, Firefox gives each iframe of the new page
the address of the iframe at the same position in the old one, so the
conference frame, inserted before the chat, would show the chat.

The iframe grants camera, microphone, screen sharing, full screen,
autoplay and clipboard to every origin (`allow="camera *; ..."`): the join
URL redirects to the BigBlueButton client, which may live on another host
than the API (a load balancer such as Scalelite, or Greenlight in front of
another server). It only ever loads a URL set by an administrator.

**Load on the server.** Each Odoo worker keeps the state of a meeting 10
seconds, so the page views and status polls of a room share one call.
After a failure to reach the server, it answers "the server does not
answer" for 60 seconds without calling it, and the calls time out after 3
seconds to connect; the waiting page polls less often (up to every 2
minutes) while the server fails.

**Shared secret.** On the BigBlueButton server, run:

```bash
sudo bbb-conf --secret
```

It prints the server URL (`https://<server>/bigbluebutton/`) and the
secret. Type both in the settings. The secret is write-only there: the
field stays empty once saved, "A secret is saved" tells it is stored, and
**Forget the secret** deletes it. The secret only signs the API calls on
the server (SHA-256 checksum, accepted by BigBlueButton 2.6 and later); it
never reaches a page, a JSON answer or the logs.

**Greenlight rooms refuse iframes.** Greenlight pages (`/` and
`/rooms/<code>/...`) answer with `X-Frame-Options: SAMEORIGIN`, so a
Greenlight room URL as conference URL ends behind the button. The
BigBlueButton client (`/html5client/`), reached through a join URL, can be
framed: that is what the meeting ID mode shows.

**Finding the meeting ID of a Greenlight room.** Greenlight shows only the
short code of a room, not the internal meetingID the API needs. Once the
host has started the room, open the event day and click **Running BBB
meetings** (Settings and Administrator groups, visible when the server is set): it lists
the meetings of the server (name, meeting ID, participants). Choose a room
on the line and click **Assign**. The meeting ID of a Greenlight room stays
the same from one session to the next.

**Who chooses the meeting.** The list, signed with the shared secret,
names every meeting of the server, those of other applications included,
and the web app moderators join a room meeting with the role `MODERATOR`.
Choosing the meeting of a room therefore belongs to the group that holds
the secret: **Running BBB meetings**, **Assign** and any new value of
`BBB meeting ID` (form, import or API) need the Settings group; the list
also needs the Administrator group of the application. An Administrator
without the Settings group sees the meeting ID read-only; through the API,
they may only empty it or set a meeting ID that a room already carries, so
a copied room or day keeps its meeting. A default value (context or user
default) passes the same check when a room is created. **Forget the secret** also needs an administrator
(the check of the settings themselves): the server refuses it to anybody
else, even through RPC.

**Frame check.** When the conference URL changes, and with the **Re-check**
button of the room list (Administrator group), the server fetches the URL
(5 s timeout, redirects followed) and reads its headers: `X-Frame-Options` `DENY` or
`ALLOW-FROM` refuse, `SAMEORIGIN` allows only a page on the Odoo domain
(`web.base.url`); a `Content-Security-Policy` `frame-ancestors` directive
takes precedence, as in browsers (`'none'` refuses, `'self'` allows the
same origin, `*` or a source matching the Odoo origin allows). No answer,
or an HTTP error, means not shown in the page.

## Look

Mobile first, then a wide layout from 1024 px:

- **Home**: a dark header (app icon, day name, state of the day, opening
  hours, user and log out), then cards. On a phone they follow one another:
  the cards of a theme (lead slot), announcement, links (two columns of
  buttons), site plan (room numbers on
  the plan, the list of rooms below with the same numbers and a "Video"
  pill for a room that has a conference, "Live" with a ring around its area
  while its meeting runs), events of the day, raffles (winner
  rows in green, an absent winner struck through, draws still to come
  dashed, and the age of the last refresh). On a wide screen the plan and
  the events fill the main column, under the lead cards of a theme, and
  the announcement, links and raffles a 380 px side column.
- **Room**: a dark app bar (back to the plan, room name and description,
  "Live" while the server says the room meeting runs); the video above the
  chat on a phone, on the left of a 380 px chat column on a wide screen.
- **Closed day**: a full-screen dark page with the opening and closing
  dates, the signed-in user and a log out button.

A room badge takes the room colour, with dark or white text, whichever
contrasts most. The pages follow the dark colour scheme of the device; the
app bars stay dark in both.

Fonts: Inter (text) and Space Grotesk (headings), variable woff2 files of
the latin and latin-ext subsets, taken from the `@fontsource-variable` npm
packages and served by the module (`static/src/webapp/fonts/`, SIL Open
Font License 1.1, license texts beside the files). The pages request
nothing from another host.

## Accessibility

The pages aim at WCAG 2.2 level AA, and go further for blind and
partially sighted visitors.

**Structure.** Each page has a language (`lang`, from the language of the
user), a title that says where the visitor is ("Home - <day>", "<room> -
<day>", "Over - <day>"...), one `h1`, `h2` sections, a header (the banner
landmark, which holds the bar and the banner of a theme, so no text lies
outside a landmark), a `main` landmark and a footer. Two skip links open every page: **Skip to main content** and
**Display options: text-only mode**, which moves the focus to the
text-only toggle. The reading order is the DOM order on every width: the
home page shows the lead cards of a theme, the announcement and the
links, then the plan and the events, then the raffles. Links that open a new tab say so to screen
readers, and as text in text-only mode. The frames have a title ("Discussion: <room>", "Video
conference: <room>"). The controls are at least 44 px tall and show a
3 px focus ring with a contrast of 3:1 or more against what lies around it
(the conference frame gets its ring around its box, as long as the focus
is in it: a frame passes the focus to its document and shows none of its
own).

**Site plan.** The plan is a picture for the eyes: its alternative text
says that the rooms are listed after it, and its clickable areas are
hidden from assistive technologies and from the tab order. The room list
is the real navigation: a list of links with the room name, its
description, "Video conference" for a room that has one, and the place of
the room on the plan ("Area 1 on the plan, in the top left corner."),
computed from the centre of its area on a 3 x 3 grid. A room whose meeting
runs shows "Conference: Live" in that list: the ring of its area on the
plan stays still, so the signal never rests on motion. The name of a link
holds the words its pills show ("Video", "Live", in every language), as
WCAG 2.5.3 (Label in Name) asks: the hidden text adds to the visible word
instead of replacing it.

**Announcements.** One polite live region per page (`#o_ewp_announcer`)
says: the new raffle winners (raffle, prize, winner; their count beyond
three), else "The raffles were updated: X drawn of Y."; the end of the
raffle refresh (session expired, day closed, or three failed answers in a
row: "The raffle results are no longer updated. Reload the page to see
the latest draws."); a room of the home page that goes live; the start of
the conference, the server that stops or starts answering, the leave ("You
left the conference.") and the move to another tab; the text-only mode and
the animations switched on or off. The raffle refresh announces only when
the results change, the conference poll only when its state changes, and a
message equal to the one said less than 3 seconds before is dropped. A
message that comes with a page load is said once the new page is ready,
and the focus goes back to where the user was: the toggle that loaded it
(text-only mode), or the heading of the conference block (conference
started or ended, "Join again" on a meeting that no longer runs).

**Display options.** The footer of every page holds the toggle button
**Text-only mode** (`aria-pressed`) and the group **Animations**, three
buttons of which the one in force is pressed: **Follow the device**,
**On** and **Off**. They are stored on the user (`res.users`, fields
`ewp_text_only` and `ewp_motion`, a selection `auto`, `on`, `off`,
default `auto`), so they follow the visitor on every device. A
text-only preference says something about the sight of the person: both
fields are restricted to the Settings group, and a user reads and writes
them on their own record only (`SELF_READABLE_FIELDS`,
`SELF_WRITEABLE_FIELDS`); nobody else reads them or searches on them on
another user's record. Internal users also find them in **My
Preferences**. The buttons post to `/webapp_event/preferences` (POST,
CSRF token, current user only, portal users included; `text_only=1|0`,
`motion=auto|on|off`) and work without script.

- **Animations** chooses when the pages move:
  - **Follow the device** (default) plays the animations unless the
    system setting "reduce motion" (`prefers-reduced-motion`) is on. In
    that case a short hint shows under the buttons, "Your device asks
    for less motion, animations are off.", with a **Turn them on** button
    (it sets **On** and gives the focus to it): a visitor who never
    chose to stop them learns why nothing moves.
  - **On** plays them even when the device asks for less motion, as an
    explicit choice of the visitor.
  - **Off** stops every animation and transition of the pages (and the
    SMIL animations of the inline SVG images) and removes the cameos at
    once. While it is on, the raffle block is no longer replaced on its
    own: a **Show the latest results** button appears and the new winners
    are still announced (WCAG 2.2.2, Pause, Stop, Hide).

  Every moving part is decorative: the cameos (see "Theming") live in an
  `aria-hidden` layer that takes no pointer and never covers a control or
  a text; none lasts more than 7 seconds, and **Off** stops them all
  (WCAG 2.2.2). Nothing flashes: the moves are transforms and fades of
  0.6 s or more. Upgrading from a version before 18.0.1.4.0 keeps the
  choice: the former **Pause animations** becomes **Off**, its absence
  **Follow the device**.
- **Text-only mode** renders the content as linear text in one column: no
  plan image, no logo, no decorative image, no mascot nor banner (theme
  slots), no icon (their labels show as text), no animation and no cameo,
  whatever the animation mode. The room page
  keeps the chat and the conference: the conference frame waits behind a
  **Show the video conference** button (the BigBlueButton client has its
  own keyboard shortcuts and screen reader support), and **Open in a new
  tab** stays.

## Installable app (PWA)

The pages link a web manifest (`/webapp_event/manifest.webmanifest`) and
register a service worker (`/webapp_event/sw.js`, scope `/webapp_event`)
on HTTPS only. The service worker caches nothing: it answers with an
offline page (with the language of the visitor) when the network is down.
The theme and background colours of
the manifest are the colour of the app bar, `#15191E`. A theme module
changes the name, the colours and the icons of the app by overriding
`_ewp_pwa_values()` of the controller (see "Theming").

## Theming

A theme module depends on `event_webapp_plan` and restyles the pages
without copying them. Its files join the bundle of the pages:

```python
"assets": {
    "event_webapp_plan.assets_webapp": [
        "my_theme/static/src/theme.scss",
        "my_theme/static/src/theme.js",
    ],
},
```

**Template slots.** Each is an empty QWeb template; the theme fills it with
`<xpath expr="." position="inside">` in an inheriting template. Every slot
receives the values of the page, among them `ewp_page` and `day_state`
(see below).

| Template | Rendered |
| --- | --- |
| `event_webapp_plan.webapp_brand` | brand of the app bars: logo and app label, two items of the header grid (not empty: replace or extend) |
| `event_webapp_plan.webapp_slot_mascot` | home header (after the day state), room app bar (after the user name), closed, no-day and conference-left pages (first item of `.o_ewp_closed_body`); not rendered in text-only mode |
| `event_webapp_plan.webapp_slot_banner` | below the bar of the home and room pages, inside their header, the banner landmark (a marquee, a ribbon); not rendered in text-only mode |
| `event_webapp_plan.webapp_slot_home_lead` | first item of the home page, before the announcement: the first card on a phone, the top of the main column on a wide screen (its own grid row, the main column right under it); rendered in text-only mode; its column exists only when the slot renders something |
| `event_webapp_plan.webapp_slot_home_cards` | first item of the main column of the home page (an extra card), after the announcement and the links on a phone; rendered in text-only mode, where `text_only` is true |
| `event_webapp_plan.webapp_slot_room_item` | inside each link of the room list of the home page, after the room description (part of the name of the link); receives `room`, the values of that room (`id`, `name`, `url`...); rendered in text-only mode |
| `event_webapp_plan.webapp_slot_room_main` | last item of the main content of a room page, after the chat; on a wide screen it spans both columns, under the conference and the chat; receives `room` (`id`, `name`, `description`, `color`); rendered in text-only mode |
| `event_webapp_plan.webapp_slot_footer` | end of `.o_ewp_app`, on every page |
| `event_webapp_plan.webapp_slot_refresh` | inside the list of the automatic updates (`#o_ewp_refresh`) of the home and room pages, after the rows of this module: rows made with `<t t-call="event_webapp_plan.webapp_refresh_row">`, `refresh_id` set inside the call, the label as its body |

The page templates keep stable ids (`webapp_layout`, `webapp_page_main`,
`webapp_page_room`, `webapp_page_closed`, `webapp_page_none`,
`webapp_page_bbb_left`, `webapp_raffles_content`) and stable classes
(`o_ewp_*`) for any other `xpath`.

**Page state.** `ewp_page` is `home`, `room`, `closed`, `none` (no day) or
`bbb_left`; `day_state` is `before`, `open`, `after` or `none`. The body
carries the classes `o_ewp_page_<page>` and `o_ewp_day_<state>` (server
side, without script), and the script copies them to the body as
`data-ewp-page` and `data-ewp-day-state`. `.o_ewp_app` carries both, plus
`data-ewp-day-start` and `data-ewp-day-end` (ISO 8601, UTC). The
conference section `.o_ewp_bbb` carries `data-ewp-bbb-state`. On the home
page, the area and the link of a room whose meeting runs carry
`data-ewp-live` (set by the script) and the link shows its `.o_ewp_pill_live`
pill.

**CSS custom properties.** Every colour, font and radius of the pages is a
custom property declared on the body (`.o_ewp_webapp`): `--ewp-ground`,
`--ewp-surface*`, `--ewp-ink*`, `--ewp-muted`, `--ewp-accent*`,
`--ewp-warm*`, `--ewp-success*`, `--ewp-preview-*`, `--ewp-bar*` (dark app
bars and closed page), `--ewp-dot-open`, `--ewp-dot-closed`, `--ewp-live*`,
`--ewp-video*`, `--ewp-plan-*`, `--ewp-room-default`, `--ewp-hotspot-ring`,
`--ewp-on-accent`, `--ewp-focus`, `--ewp-font`, `--ewp-font-head` and
`--ewp-radius-*` (`2xs`, `xs`, `sm`, `md`, base, `lg`, `xl`, `pill`). The
dark scheme redefines some of them in `@media (prefers-color-scheme:
dark)`; a theme loaded later in the bundle overrides both, so it declares
its own dark values too.

Each area of the plan (`.o_ewp_hotspot`) also carries, in its own style,
`--ewp-room-color` and, when it is turned, `--ewp-room-rotate` (an angle
such as `-90.00deg`). The area turns by `transform: rotate(var(--ewp-room-rotate, 0deg))`
and its number and label turn back by the same angle: a theme that sets a
`transform` on an area, on hover for instance, keeps that rotation in its
value (`transform: rotate(var(--ewp-room-rotate, 0deg)) scale(1.05)`).

**Accessibility hooks.** The slots and `webapp_brand` receive
`text_only`, `motion` (the mode in force: `auto`, `on`, or `off`, which
the text-only mode forces), `motion_choice` (the stored choice) and
`motion_paused`. The body carries `o_ewp_text_only` in text-only mode,
one of `o_ewp_motion_auto`, `o_ewp_motion_on` and `o_ewp_motion_off`,
and `o_ewp_motion_paused` while the user stopped the animations (mode
**Off** or text-only mode). The script writes `data-ewp-motion`
(`paused` or `running`) on the body, which also follows
`prefers-reduced-motion` under `auto`. Animations may run under
`o_ewp_motion_on`, or under `o_ewp_motion_auto` without reduced motion:
a theme writes that rule set once with the mixin of `webapp.scss`,
directly inside `.o_ewp_webapp` (its files compile after it in the
bundle):

```scss
.o_ewp_webapp {
    @include ewp-motion-allowed {
        .my_theme_mascot {
            animation: my-theme-bob 3s ease-in-out infinite;
        }
    }
}
```

The module also stops them: under `o_ewp_motion_off`,
`o_ewp_motion_paused`, and `prefers-reduced-motion` with
`o_ewp_motion_auto`, every `animation` and `transition` under the body is
set to `none`. A theme script that animates through JavaScript listens to
`ewp:motion`. Its images are decorative (`alt=""` or `aria-hidden`), or
carry a text that adds to the page.

**Cameos.** `webapp_cameo.js` brings small actors in at the edges of the
pages while the animations run: the first one 2 to 3 seconds after the
page is ready (or the tab shows again), then one every 4 to 8 seconds comes in
(rises from the bottom edge, slides in from a side margin, or grows in
place on the header edge or a card corner), plays an action for 3 to 5
seconds and goes away; at most one at a time under 640 px, two above.
The engine picks its spot among the bottom corners of the window, the
edge of the header bar, the side margins and the corners of the cards,
and keeps only a spot that covers no control (link, button, field,
frame, tab stop), no picture of 32 px or more and no text of the page
(the boxes of its text nodes that are shown, `aria-hidden` ones
included, such as the age of the raffle results), nor an element marked
`data-ewp-cameo-avoid`, with 8 px around: a theme marks so a decoration
that no cameo may cover. On a phone the bottom corners and the header
edge come first. A cameo that the page brings over a control or a text
leaves at once: the check runs after a scroll, a resize, a focus, a
change of the size of the content and any change of the page outside the
layer (a live refresh that swaps a block, an attribute that shows a
button). A cameo leaves by an exit animation of its own
(`ewp-cameo-rise-out`, `-slide-left-out`, `-slide-right-out`,
`-pop-out`).
Without a free spot, none plays. The layer (`.o_ewp_cameo_layer`, fixed,
`aria-hidden`, no pointer events, `z-index` 900, under the skip links)
holds the cameos; nothing in it takes the focus. The engine stops, and
removes the cameos at once, when the animations pause (mode **Off**, or
**Follow the device** with reduced motion), never runs in text-only mode,
and pauses while the tab is hidden. Page events play a matching action:
a raffle winner plays `celebrate` near the raffle card, a conference that
runs `speak` near it, a day before its opening `coffee`.

The module ships one neutral actor (a round figure in `--ewp-accent`
with the prop of its action: `wave`, `coffee`, `code`, `speak`,
`celebrate`), used only while no other actor is registered. A theme
registers its own from a script of the bundle:

```javascript
window.ewpCameo.register({
    name: "my-mascot",
    actions: ["coffee", "code", "speak", "wave", "celebrate"],
    weight: 1,
    // A Node or an HTML string; context: {size, side, phone}.
    render: (action, context) => `<svg viewBox="0 0 100 100">...</svg>`,
});
```

| API | Does |
| --- | --- |
| `register({name, actions, render, weight, fallback})` | adds an actor; `fallback: true` plays only while no other actor is registered |
| `unregister(name)` | removes an actor |
| `configure(options)` | `firstMinDelay`, `firstMaxDelay` (ms before the first cameo of a schedule that starts), `minDelay`, `maxDelay` (ms between cameos), `enterMs`, `actionMs` (`[min, max]`), `exitMs`, `eventDelay`, `maxActive`, `maxActivePhone`, `phoneWidth`, `size`, `sizePhone` (px); restarts the schedule |
| `play(action, {near})` | one cameo now, near the element of the CSS selector `near`; returns whether it entered |
| `state()` | `running`, `active` (`actor`, `action`, `phase`, `rect`), `actors`, `options`, `history` (the last 50 `ewp:cameo` details) |

Each cameo is a `.o_ewp_cameo` element with `data-ewp-actor`,
`data-ewp-action`, `data-ewp-phase` (`enter`, `act`, `exit`), the classes
`o_ewp_cameo_from_<side>` (`bottom`, `left`, `right`, `pop`) and
`o_ewp_cameo_do_<action>`; the node of the actor sits in
`.o_ewp_cameo_actor`. A theme animates its actor under
`.o_ewp_cameo[data-ewp-phase="act"]`, inside `ewp-motion-allowed`, and
keeps its moves within the box of the cameo.

**Page values.** `EventWebappController._ewp_page_values(page, webapp,
tz, room=None)` returns a dict merged last into the values of the home page
(`page` is `"home"`) and of a room page (`"room"`, with the sudo record
`room`), so the slots receive them. `webapp` is the sudo day, already
allowed for the user, `tz` the time zone of the page. It returns `{}`; a
module that adds a block overrides it in a subclass of the controller and
reads only the fields it shows (see `event_webapp_plan_track`).

**Installable app.** `EventWebappController._ewp_pwa_values()` returns
the `name`, `short_name`, `theme_color`, `background_color`, `icon_url`
(favicon, touch icon and brand icon of the pages) and `icons` (list of the
web manifest). A theme subclasses the controller and overrides it; Odoo
serves the routes through the most derived class:

```python
from odoo.addons.event_webapp_plan.controllers.main import (
    EventWebappController,
)


class MyThemeController(EventWebappController):
    def _ewp_pwa_values(self):
        values = super()._ewp_pwa_values()
        values.update(theme_color="#123456", background_color="#123456")
        return values
```

**DOM events.** `webapp.js` dispatches `CustomEvent`s on `document`
(bubbling). The events of the start come after a zero delay, so a script
later in the same bundle receives them.

| Event | `detail` | Sent |
| --- | --- | --- |
| `ewp:ready` | `page`, `dayState`, `textOnly`, `motionPaused`, `motionMode` | once, at start |
| `ewp:motion` | `paused`, `mode`, `initial` | at start, then when the animation mode or the system setting changes the state |
| `ewp:day-state` | `state`, `previous`, `initial` | at start, then when the clock reaches the opening or the closing moment |
| `ewp:bbb-state` | `state`, `previous`, `initial`, `live` | room page with a conference: at start (`running`, `frame`, `waiting`, `unavailable`, `button`, or `left` after the redirect of `bbb_left`), then `left`, `moved` (open in a new tab) or `running` after "Join again"; `live` is true for `running`, and for `button` when the meeting runs behind the new tab button |
| `ewp:raffle-drawn` | `drawId`, `raffle`, `prize`, `winner` | for each draw that got a winner since the previous refresh |
| `ewp:rooms-live` | `ids`, `initial` | home page: on the first answer of the live route, then on each answer that changes the live rooms |
| `ewp:refresh` | `id`, `state` (`running`, `busy`, `error`, `stopped`), `last`, `next` (ms since the epoch) | each refresher (`raffles`, `live`, `conference`; `my_prize`, `agenda` of the bridge modules) when it plans, sends or gets a request; a detail carries only the fields that change. `webapp.js` listens to it too: a script of the bundle reports its own refresher this way, and its row `li[data-ewp-refresh="<id>"]` shows; the row carries `data-ewp-refresh-state` (`paused` while the tab is hidden) |
| `ewp:cameo` | `phase` (`enter`, `exit`), `actor`, `action`, `trigger` (`schedule`, `raffle`, `bbb`, `day`, `play`), `reason` (exit: `done`, `stop`, `hidden`, `overlap`, `replaced`), `rect` | `webapp_cameo.js`: each cameo that enters or leaves |

```javascript
document.addEventListener("ewp:raffle-drawn", (ev) => {
    console.log(ev.detail.winner);
});
```

The script also listens to one event: `ewp:announce` with `detail`
`{text}`, dispatched on `document` by another script of the bundle, says
`text` in the shared live region (`#o_ewp_announcer`), with the same rule
against a message repeated within 3 seconds.

```javascript
document.dispatchEvent(new CustomEvent("ewp:announce", {detail: {text: message}}));
```

## Tests

```bash
odoo-bin -d TEST_DB -i event_webapp_plan --test-enable \
    --test-tags /event_webapp_plan --stop-after-init
```

Use a disposable database. `tests/test_browser.py` and the browser tests
of `tests/test_accessibility.py` drive a headless Chrome (embedded chat,
plan page, plan editor, display options, live region announcements, focus
after a page load, live rooms, animations stopped) and are skipped when
Chrome is absent. The accessibility audit runs the WCAG 2.2 A and AA rules of
axe-core, and its "region" rule (no content outside a landmark), on the
home, room and closed pages, normal and text-only, when
the environment variable `EWP_AXE_JS` names a copy of `axe.min.js`; the
module does not ship axe-core, and the test skips itself without it:

```bash
npm pack axe-core@4.10.2 && tar xzf axe-core-4.10.2.tgz
EWP_AXE_JS=$PWD/package/axe.min.js odoo-bin -d TEST_DB ...
```

### End-to-end tests with Selenium

`tests/test_selenium_webapp.py` drives a real browser through Selenium, as
a visitor does: it logs in through the login form, clicks and presses keys,
and reads the page the browser renders. It covers the login redirect, the
home page on a phone and in both colour schemes, the room entry (room
group, chat), the preview banner and the closed page, a raffle drawn while
the page is open and its announcement, the conference that starts, is left
and joined again, a running meeting behind the new tab button, the
text-only mode kept for a new browser session, the
animations stopped by the mode "Off" and by the system setting, the
skip links and a keyboard-only path to a room and back.

`tests/test_selenium_plan.py` drives the plan editor with real pointer
moves (draw, rotate with the buttons, with Shift, through the angle field
and with the knob, move, resize a turned area by a corner, straighten,
save) and checks that the home page draws a turned area turned and opens
the room on a click inside its turned shape.

`tests/test_selenium_cameo.py` checks the animation mode and the cameos:
"On" plays them with `prefers-reduced-motion` emulated; "Follow the
device" with reduced motion plays none and shows the hint, whose button
turns them on; "Off" removes a cameo on screen at once and the text-only
mode plays none; no cameo covers a control or a text, on a phone and on a
wide screen, nor after a scroll (cameos that stay are on screen, the page
moves, each one covers nothing or has left); a cameo leaves when an
attribute shows a button under it or when a block swapped by
`innerHTML`, as the raffle refresh does, puts a line under it; a shown `aria-hidden` text blocks the spots and
the age label of the raffles stays clear; the exit plays its own
animation; the motion choice works on a browser whose submit event has
no `submitter`; a raffle winner, a running conference and
a day before its opening play `celebrate`, `speak` and `coffee`; a hidden
tab sends the cameos away and plays none until it shows again. The tests
shorten the schedule with `window.ewpCameo.configure()`.

`tests/selenium_common.py` holds the base class `SeleniumCase`, for the
tests of the features to come: one browser per test class, login through
the form, phone (390 x 844) and desktop (1280 x 900) viewports, emulated
`prefers-reduced-motion` and `prefers-color-scheme`, a hidden tab
(`set_page_hidden()`, told to the page in place: a headless browser keeps
its only tab visible), waits, the text of the live region,
`document.getAnimations()`, and `server_paused()` to read or
write records while a page is open (the browser requests share the cursor
of the test). A failing test saves a screenshot (and, on Chromium, the
console messages) in `EWP_SELENIUM_SCREENSHOTS`, by default
`<temporary directory>/ewp_selenium`, and logs the path. BigBlueButton is
played by the fake server of `tests/test_bbb.py`: no test reaches another
host.

Selenium is a development tool, not a dependency of the module: install it
in the Python environment that runs Odoo.

```bash
pip install 'selenium>=4.20'
```

The browser is Chromium by default (`/usr/bin/chromium`, headless), or
Firefox with `EWP_SELENIUM_BROWSER=firefox`. `EWP_SELENIUM_BINARY` names
another browser executable and `EWP_SELENIUM_DRIVER` its driver
(chromedriver, geckodriver); without it, Selenium looks in the `PATH`, then
Selenium Manager fetches a matching driver once into its cache (its usage
statistics are turned off unless `SE_AVOID_STATS` is set). Without the
package, the browser or its driver, the test class is skipped and the log
says why. Firefox windows do not go below 500 px wide, so its phone
viewport is 500 px wide.

Run these tests only, on a disposable database and free ports (the test
server of `HttpCase` listens on the HTTP port of the configuration
otherwise):

```bash
odoo-bin -d TEST_DB -i event_webapp_plan --test-enable \
    --http-port 8269 --gevent-port 8272 \
    --test-tags /event_webapp_plan:TestSeleniumWebapp,/event_webapp_plan:TestSeleniumCameo \
    --stop-after-init
```

`--test-tags selenium` runs every test tagged `selenium`, in every module.

## License

AGPL-3.0 or later. Copyright (C) 2026 Services-Conseils Linux Inc.,
Rencontres Linux au Québec contributors.
