// @odoo-module ignore
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
//
// Script of the event web app pages. The "@odoo-module ignore" header keeps it
// a plain script: the pages do not load the Odoo module loader.
//
// - Announcements: one polite live region, #o_ewp_announcer, carries every
//   message, built from the translated patterns of its data-ewp-messages
//   attribute ("%(name)s" placeholders filled in here), so the script holds
//   no text of its own. A message equal to the one said less than 3 s before
//   is dropped. A message that must outlive a page load (text-only mode
//   switched, conference started) goes to sessionStorage and is said, with
//   the focus given back, once the next page is ready; a frame that grabs
//   the focus as it loads (the chat composer) gives it back.
// - Display options: the forms .o_ewp_pref_form post to the preferences
//   route with fetch (JSON answer), with the value of the button that sent
//   them. A new animation mode updates the page in place (body classes,
//   pressed button; the focus goes to the pressed button when the button
//   used disappears, as the "Turn them on" of the hint does); the text-only
//   mode loads the page again, as the server renders it. Without fetch, or
//   on an answer that is not JSON, the form is posted as is and the server
//   redirects back.
// - Motion: the body carries one of o_ewp_motion_auto, o_ewp_motion_on and
//   o_ewp_motion_off (the mode in force, "off" in text-only mode). The
//   animations are paused under "off", under o_ewp_motion_paused, and
//   under "auto" while the system asks for reduced motion; "on" shows them
//   whatever the system says. The script writes data-ewp-motion ("paused"
//   or "running") on the body, pauses the SMIL animations of every inline
//   SVG, and sends ewp:motion on a change.
// - Raffles: the block carrying data-ewp-raffles-url is refreshed every 30 s
//   from the JSON route. The server sends the rendered HTML (already escaped
//   and translated) and a signature; the block is replaced only when the
//   signature changes. The block is not a live region: the shared region
//   announces the draws that got a winner since the last answer (each one,
//   or their count beyond three), else the drawn count of the raffles.
//   While the body has o_ewp_motion_paused, the block is not replaced on
//   its own: the button .o_ewp_raffles_apply appears and replaces it on
//   demand (WCAG 2.2.2). Polling pauses while the tab is hidden and stops
//   for good on a 403 or a redirect (day closed, session expired). The
//   shared region then says that the results are no longer updated; it
//   says it too after MAX_RAFFLE_FAILURES failed answers in a row
//   (network error, server error), once until an answer succeeds. The
//   element carrying data-ewp-label-seconds shows the age of the last
//   answer, from the two translated patterns the server writes in its data
//   attributes ("%(seconds)s" and "%(minutes)s" are replaced here), updated
//   every 5 s while the tab is visible.
// - Plan: a room hovered or focused in the list highlights its zone on the
//   plan, and the other way round (pairs share data-ewp-room-id).
// - Live rooms: the room list carrying data-ewp-live-url asks that JSON
//   route at start, then every 30 s while the tab is visible, which rooms
//   have a running meeting. Their area and link get data-ewp-live, the
//   link shows its hidden "Live" pill, and the shared region names a room
//   that goes live after the first answer. Polling stops for good on a 403
//   or a redirect.
// - Conference: while the page may change (meeting not started, running
//   meeting behind the new tab button, server failing), the element carrying
//   data-ewp-bbb-status-url polls that JSON route every 20 s, paused while the
//   tab is hidden. It loads the page again when the "state" of the answer
//   differs from the data-ewp-bbb-state the page was rendered with (the
//   meeting starts or ends), or when its "error" differs from
//   data-ewp-bbb-error, so the notice "does not answer" appears and goes
//   away with the server. While the server fails, the interval doubles up to
//   2 minutes. Polling stops for good on a 403 or a redirect (day closed,
//   session expired). The message kept for the next page gives the focus
//   to the heading of the conference block (#o_ewp_h_bbb), so a reload
//   does not send the user back to the top of the page.
// - "Open in a new tab" next to the conference frame empties and removes the
//   frame, and shows the hidden notice .o_ewp_bbb_moved in its place: the
//   user is then in the meeting once, from the new tab.
// - Leaving the meeting (meeting ID mode, where the page holds the hidden
//   notice .o_ewp_bbb_left): the first load of the frame is the client. The
//   frame has left the meeting when a load shows the path
//   data-ewp-bbb-left-path (the logoutURL of the join URL, same origin, so
//   readable), or when any later load happens (a server that ignores the
//   logoutURL of join sends the client to the logout page of the meeting,
//   on another host). Loads of about:blank do not count. The frame is then
//   emptied and hidden, the notice shown and the focus moved to its "Join
//   again" button. That button asks data-ewp-bbb-check-url: while the
//   meeting runs, or when the server cannot be asked, the frame loads its
//   first src again (a fresh join URL) and counts from zero; otherwise the
//   page loads again and shows the state the server renders (waiting,
//   closed day, login), with the focus on the heading of the conference
//   block. A room page that ships the notice shown (the redirect of
//   bbb_left, data-ewp-bbb-state "left") starts in that state, the frame
//   without src, the focus on "Join again".
// - Text-only mode: the conference frame ships without src; the button
//   .o_ewp_bbb_show gives it its data-ewp-src and shows it.
// - Skip links: they move the focus to their target (the main content, or
//   the text-only toggle for the display options), not only the scroll.
// - Service worker: registered on secure origins only, for installability.
// - Theme hooks: the script copies data-ewp-page and data-ewp-day-state of
//   .o_ewp_app to the body (data-ewp-page, data-ewp-day-state), and
//   dispatches DOM CustomEvents on document (bubbling, detail below):
//     ewp:ready         {page, dayState, textOnly, motionPaused,
//                       motionMode}
//     ewp:day-state     {state, previous, initial}: before, open, after or
//                       none; sent at start, then when the clock reaches
//                       data-ewp-day-start or data-ewp-day-end
//     ewp:bbb-state     {state, previous, initial, live}: running, frame,
//                       waiting, unavailable, button, left (rendered state),
//                       then left, moved, or running again after "Join
//                       again"; also written to data-ewp-bbb-state. live
//                       is true for "running", and for "button" when the
//                       meeting runs (data-ewp-bbb-live)
//     ewp:raffle-drawn  {drawId, raffle, prize, winner}: one event per draw
//                       that got a winner since the last answer
//     ewp:rooms-live    {ids, initial}: the ids of the live rooms, on each
//                       answer of the live route that changes them
//     ewp:motion        {paused, mode, initial}: sent at start, then when
//                       the mode or the system setting changes the state
//   The events of the start are sent after a zero delay, so a script loaded
//   after this one in the same bundle receives them.
//   The script listens to one event: ewp:announce {text}, dispatched on
//   document by another script of the bundle, says `text` in the shared
//   live region, with the same rule against repeats as its own messages.
(function () {
    "use strict";

    const POLL_INTERVAL_MS = 30000;
    const AGE_INTERVAL_MS = 5000;
    const BBB_POLL_INTERVAL_MS = 20000;
    const BBB_POLL_MAX_MS = 120000;
    // Longest delay setTimeout accepts; a later moment is checked again.
    const MAX_TIMEOUT_MS = 2147483647;
    const DAY_STATES = ["before", "open", "after", "none"];
    const STORAGE_KEY = "ewp:announce";
    const REPEAT_MS = 3000;
    // Delay before a message is written in the emptied region, and before
    // a stored message is said on a new page (after its title is read).
    const SAY_DELAY_MS = 100;
    const REPLAY_DELAY_MS = 600;
    const MAX_WINNER_LINES = 3;
    // After a page load that gives the focus back, time during which a
    // frame that takes the focus on its own gives it back (see holdFocus).
    const HOLD_FOCUS_MS = 10000;
    const MAX_RAFFLE_FAILURES = 3;
    const LIVE_POLL_INTERVAL_MS = 30000;
    // Element focused on the page loaded again by the conference block.
    const BBB_FOCUS_ID = "o_ewp_h_bbb";
    const MOTION_MODES = ["auto", "on", "off"];

    function emit(name, detail) {
        document.dispatchEvent(new CustomEvent(name, {bubbles: true, detail}));
    }

    // Loads the page again from the server. The address loses its fragment
    // (set by a skip link), else the navigation would only scroll; a new
    // load, not reload(): on a reload, Firefox gives each iframe of the new
    // page the address of the iframe at the same position in the old one.
    function reloadPage() {
        const url = new URL(window.location.href);
        url.hash = "";
        window.location.replace(url.href);
    }

    function createAnnouncer(root) {
        const region = root.querySelector("#o_ewp_announcer");
        let messages = {};
        try {
            messages = JSON.parse((region && region.dataset.ewpMessages) || "{}");
        } catch {
            messages = {};
        }
        let last = "";
        let lastAt = 0;
        let timer = null;

        function text(key, params = {}) {
            const pattern = messages[key] || "";
            return pattern.replace(/%\((\w+)\)s/g, (match, name) =>
                Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
            );
        }

        function say(message) {
            if (!region || !message) {
                return;
            }
            const now = Date.now();
            if (message === last && now - lastAt < REPEAT_MS) {
                return;
            }
            last = message;
            lastAt = now;
            clearTimeout(timer);
            // Emptied first: a screen reader then says a text equal to the
            // one the region held.
            region.textContent = "";
            timer = setTimeout(() => {
                region.textContent = message;
            }, SAY_DELAY_MS);
        }

        // Keeps `key` (and the id of the element to focus) for the next
        // page of this tab.
        function later(key, params = {}, focusId = "") {
            try {
                sessionStorage.setItem(STORAGE_KEY, JSON.stringify({text: text(key, params), focus: focusId}));
            } catch {
                // Storage refused: the next page loads without the message.
            }
        }

        // The chat frame focuses its composer once it has loaded, which
        // would undo the focus given back after a page load. Until the
        // user presses a key or a pointer in the page or in a frame of the
        // same origin, and for HOLD_FOCUS_MS at most, a frame that takes the
        // focus gives it back to `target`.
        function holdFocus(target) {
            let touched = false;
            const touch = () => {
                touched = true;
            };
            const watch = (win) => {
                for (const type of ["keydown", "pointerdown"]) {
                    win.addEventListener(type, touch, true);
                }
            };
            watch(window);
            for (const frame of document.querySelectorAll("iframe")) {
                const hook = () => {
                    try {
                        watch(frame.contentWindow);
                    } catch {
                        // Frame of another origin: its events stay unseen.
                    }
                };
                hook();
                frame.addEventListener("load", hook);
            }
            const onBlur = () => {
                setTimeout(() => {
                    const active = document.activeElement;
                    if (!touched && active && active.tagName === "IFRAME" && active !== target) {
                        target.focus();
                    }
                }, 0);
            };
            window.addEventListener("blur", onBlur);
            setTimeout(() => window.removeEventListener("blur", onBlur), HOLD_FOCUS_MS);
        }

        function replayStored() {
            let stored = null;
            try {
                stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
                sessionStorage.removeItem(STORAGE_KEY);
            } catch {
                stored = null;
            }
            if (!stored || typeof stored !== "object") {
                return;
            }
            const target = stored.focus && document.getElementById(String(stored.focus));
            if (target) {
                target.focus();
                holdFocus(target);
            }
            if (stored.text) {
                setTimeout(() => say(String(stored.text)), REPLAY_DELAY_MS);
            }
        }

        return {
            text,
            say,
            sayKey: (key, params) => say(text(key, params)),
            later,
            holdFocus,
            replayStored,
        };
    }

    function setupMotion(root) {
        const media = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
        const mode = () => {
            if (root.classList.contains("o_ewp_motion_off") || root.classList.contains("o_ewp_text_only")) {
                return "off";
            }
            return root.classList.contains("o_ewp_motion_on") ? "on" : "auto";
        };
        const isPaused = () => {
            const current = mode();
            if (current === "off" || root.classList.contains("o_ewp_motion_paused")) {
                return true;
            }
            return current === "auto" && Boolean(media && media.matches);
        };
        let paused = isPaused();

        function apply() {
            root.dataset.ewpMotion = paused ? "paused" : "running";
            for (const svg of root.querySelectorAll("svg")) {
                if (typeof svg.pauseAnimations === "function") {
                    if (paused) {
                        svg.pauseAnimations();
                    } else {
                        svg.unpauseAnimations();
                    }
                }
            }
        }

        function update() {
            const next = isPaused();
            if (next !== paused) {
                paused = next;
                apply();
                emit("ewp:motion", {paused, mode: mode(), initial: false});
            }
        }

        // Body classes of the mode `next` (one of MOTION_MODES).
        function setMode(next) {
            for (const name of MOTION_MODES) {
                root.classList.toggle(`o_ewp_motion_${name}`, name === next);
            }
            root.classList.toggle("o_ewp_motion_paused", next === "off");
            update();
        }

        apply();
        if (media && media.addEventListener) {
            media.addEventListener("change", update);
        }
        return {
            paused: () => paused,
            mode,
            deviceReduced: () => Boolean(media && media.matches),
            setMode,
            update,
        };
    }

    function setupPreferences(root, announcer, motion) {
        if (!window.fetch || !window.FormData) {
            return;
        }
        for (const form of root.querySelectorAll("form.o_ewp_pref_form")) {
            const fallback = form.querySelector(".o_ewp_pref_toggle");
            if (!fallback) {
                continue;
            }
            let busy = false;
            // The submit button last pressed, for browsers whose submit
            // event has no `submitter`: the click (mouse, Enter or Space)
            // comes before the submit.
            let pressedButton = null;
            form.addEventListener("click", (ev) => {
                const target = ev.target instanceof Element ? ev.target.closest("button[name]") : null;
                if (target && form.contains(target) && target.type === "submit") {
                    pressedButton = target;
                }
            });

            // The plain post of the form, with the value of `button`.
            function postForm(button) {
                const field = document.createElement("input");
                field.type = "hidden";
                field.name = button.name;
                field.value = button.value;
                form.appendChild(field);
                HTMLFormElement.prototype.submit.call(form);
            }

            form.addEventListener("submit", async (ev) => {
                ev.preventDefault();
                const button =
                    (ev.submitter && form.contains(ev.submitter) && ev.submitter) || pressedButton || fallback;
                pressedButton = null;
                if (busy) {
                    return;
                }
                busy = true;
                const data = new FormData(form);
                data.set(button.name, button.value);
                let prefs = null;
                try {
                    const response = await fetch(form.action, {
                        method: "POST",
                        body: data,
                        credentials: "same-origin",
                        headers: {Accept: "application/json"},
                    });
                    const type = response.headers.get("Content-Type") || "";
                    if (response.ok && type.includes("application/json")) {
                        prefs = await response.json();
                    }
                } catch {
                    prefs = null;
                }
                busy = false;
                if (!prefs) {
                    postForm(button);
                    return;
                }
                if (form.dataset.ewpPref === "text_only") {
                    announcer.later(prefs.text_only ? "text_only_on" : "text_only_off", {}, button.id);
                    reloadPage();
                    return;
                }
                const next = MOTION_MODES.includes(prefs.motion) ? prefs.motion : "auto";
                let pressed = null;
                for (const choice of form.querySelectorAll(".o_ewp_motion_choice")) {
                    const on = choice.value === next;
                    choice.setAttribute("aria-pressed", on ? "true" : "false");
                    if (on) {
                        pressed = choice;
                    }
                }
                motion.setMode(next);
                // The hint button hides with its hint: the focus goes to
                // the pressed button rather than to the body.
                if (pressed && (button.offsetParent === null || !button.isConnected)) {
                    pressed.focus();
                }
                let key = motion.paused() ? "motion_paused" : "motion_running";
                if (next === "auto") {
                    key = motion.paused() ? "motion_auto_paused" : "motion_auto_running";
                }
                announcer.sayKey(key);
            });
        }
    }

    function setupSkipLinks(root) {
        for (const link of root.querySelectorAll("a.o_ewp_skip")) {
            link.addEventListener("click", (ev) => {
                const id = (link.getAttribute("href") || "").slice(1);
                const target =
                    (id === "o_ewp_prefs" && document.getElementById("o_ewp_text_only_toggle")) ||
                    document.getElementById(id);
                if (!target) {
                    return;
                }
                ev.preventDefault();
                target.focus();
            });
        }
    }

    function setupDayState(root) {
        const app = root.querySelector(".o_ewp_app");
        if (!app) {
            return null;
        }
        const page = app.dataset.ewpPage || "";
        let state = DAY_STATES.includes(app.dataset.ewpDayState) ? app.dataset.ewpDayState : "none";
        const start = Date.parse(app.dataset.ewpDayStart || "");
        const end = Date.parse(app.dataset.ewpDayEnd || "");
        root.dataset.ewpPage = page;
        root.dataset.ewpDayState = state;

        // The state the clock gives, or the rendered one without bounds.
        function clockState(now) {
            if (Number.isNaN(start) || Number.isNaN(end)) {
                return state;
            }
            if (now < start) {
                return "before";
            }
            return now < end ? "open" : "after";
        }

        function nextBoundary(now) {
            for (const moment of [start, end]) {
                if (!Number.isNaN(moment) && moment > now) {
                    return moment;
                }
            }
            return null;
        }

        function tick() {
            const now = Date.now();
            const next = clockState(now);
            if (next !== state) {
                const previous = state;
                state = next;
                root.dataset.ewpDayState = state;
                app.dataset.ewpDayState = state;
                emit("ewp:day-state", {state, previous, initial: false});
            }
            const boundary = nextBoundary(now);
            if (boundary !== null) {
                setTimeout(tick, Math.min(boundary - now + 500, MAX_TIMEOUT_MS));
            }
        }

        const boundary = nextBoundary(Date.now());
        if (boundary !== null) {
            setTimeout(tick, Math.min(boundary - Date.now() + 500, MAX_TIMEOUT_MS));
        }
        return {
            page,
            current: () => state,
        };
    }

    // Holder of the state of the conference block, or null without one.
    function conferenceState(root) {
        const section = root.querySelector(".o_ewp_bbb[data-ewp-bbb-state]");
        if (!section) {
            return null;
        }
        // The state and the liveness the server rendered, before any change.
        const rendered = section.dataset.ewpBbbState;
        const renderedLive = section.dataset.ewpBbbLive === "1";

        function live(state) {
            return state === "running" || (state === "button" && renderedLive);
        }

        return {
            rendered,
            renderedLive,
            live,
            current: () => section.dataset.ewpBbbState,
            set(state) {
                const previous = section.dataset.ewpBbbState;
                if (previous === state) {
                    return;
                }
                section.dataset.ewpBbbState = state;
                emit("ewp:bbb-state", {state, previous, initial: false, live: live(state)});
            },
        };
    }

    function setupRaffles(root, announcer) {
        const box = root.querySelector("[data-ewp-raffles-url]");
        if (!box || !window.fetch) {
            return;
        }
        const url = box.dataset.ewpRafflesUrl;
        const apply = root.querySelector(".o_ewp_raffles_apply");
        const heading = root.querySelector("#o_ewp_h_raffles");
        let signature = box.dataset.ewpSignature || "";
        // HTML of an answer kept while the animations are paused.
        let pendingHtml = null;
        // Ids of the draws that already have a winner, as rendered first.
        let drawnIds = new Set(
            [...box.querySelectorAll(".o_ewp_draw_done[data-ewp-draw-id]")].map((el) => el.dataset.ewpDrawId)
        );
        let timer = null;
        let stopped = false;
        let busy = false;
        // Failed answers in a row, and whether the region said so.
        let failures = 0;
        let staleSaid = false;
        const age = root.querySelector("[data-ewp-label-seconds]");
        let updatedAt = Date.now();
        let ageTimer = null;

        function showAge() {
            if (!age) {
                return;
            }
            const seconds = Math.max(0, Math.round((Date.now() - updatedAt) / 1000));
            age.textContent =
                seconds < 60
                    ? age.dataset.ewpLabelSeconds.replace("%(seconds)s", String(seconds))
                    : age.dataset.ewpLabelMinutes.replace("%(minutes)s", String(Math.floor(seconds / 60)));
        }

        function tickAge() {
            clearInterval(ageTimer);
            if (!age || document.hidden) {
                return;
            }
            showAge();
            ageTimer = setInterval(showAge, AGE_INTERVAL_MS);
        }

        // Message of an answer that changed the block: the new winners,
        // their count beyond MAX_WINNER_LINES, else the drawn count.
        function announceChanges(raffles, pending) {
            const nextIds = new Set();
            const lines = [];
            let drawn = 0;
            let total = 0;
            for (const raffle of raffles || []) {
                for (const draw of raffle.draws || []) {
                    total += 1;
                    if (!draw.drawn) {
                        continue;
                    }
                    drawn += 1;
                    const id = String(draw.id);
                    nextIds.add(id);
                    if (!drawnIds.has(id)) {
                        const params = {
                            raffle: raffle.name,
                            prize: draw.prize || "",
                            winner: draw.winner_name || "",
                        };
                        lines.push(announcer.text(draw.prize ? "raffle_winner" : "raffle_winner_no_prize", params));
                        emit("ewp:raffle-drawn", {
                            drawId: draw.id,
                            raffle: raffle.name,
                            prize: draw.prize || "",
                            winner: draw.winner_name || "",
                        });
                    }
                }
            }
            drawnIds = nextIds;
            let message = "";
            if (lines.length > MAX_WINNER_LINES) {
                message = announcer.text("raffle_winners", {count: lines.length});
            } else if (lines.length) {
                message = lines.join(" ");
            } else {
                message = announcer.text("raffle_updated", {drawn, total});
            }
            if (pending) {
                message = `${message} ${announcer.text("raffle_pending")}`;
            }
            announcer.say(message);
        }

        function swap(html) {
            box.innerHTML = html;
            pendingHtml = null;
            if (apply) {
                apply.hidden = true;
            }
        }

        if (apply) {
            apply.addEventListener("click", () => {
                if (pendingHtml !== null) {
                    swap(pendingHtml);
                }
                if (heading) {
                    heading.focus();
                }
            });
        }

        // Tells the user once that the block no longer follows the draws.
        function sayStale() {
            if (!staleSaid) {
                staleSaid = true;
                announcer.sayKey("raffle_stopped");
            }
        }

        function failed() {
            failures += 1;
            if (failures >= MAX_RAFFLE_FAILURES) {
                sayStale();
            }
        }

        async function refresh() {
            if (busy || stopped) {
                return;
            }
            busy = true;
            try {
                const response = await fetch(url, {
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {Accept: "application/json"},
                });
                const type = response.headers.get("Content-Type") || "";
                if (!response.ok || !type.includes("application/json")) {
                    // 403 (day closed) or a redirect to the login page.
                    if (response.status === 403 || response.redirected) {
                        stopped = true;
                        clearTimeout(timer);
                        sayStale();
                    } else {
                        failed();
                    }
                    return;
                }
                const data = await response.json();
                failures = 0;
                staleSaid = false;
                updatedAt = Date.now();
                showAge();
                if (data && typeof data.html === "string" && data.signature !== signature) {
                    signature = data.signature;
                    box.dataset.ewpSignature = signature;
                    const hold = Boolean(apply) && root.classList.contains("o_ewp_motion_paused");
                    if (hold) {
                        pendingHtml = data.html;
                        apply.hidden = false;
                    } else {
                        swap(data.html);
                    }
                    announceChanges(data.raffles, hold);
                }
            } catch {
                // Network error: the next tick tries again.
                failed();
            } finally {
                busy = false;
            }
        }

        function schedule() {
            clearTimeout(timer);
            if (stopped || document.hidden) {
                return;
            }
            timer = setTimeout(async () => {
                await refresh();
                schedule();
            }, POLL_INTERVAL_MS);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                clearTimeout(timer);
                clearInterval(ageTimer);
            } else {
                tickAge();
                refresh().then(schedule);
            }
        });
        tickAge();
        schedule();
    }

    function setupConference(root, bbbState, announcer) {
        const box = root.querySelector("[data-ewp-bbb-status-url]");
        if (!box || !bbbState || !window.fetch) {
            return;
        }
        const url = box.dataset.ewpBbbStatusUrl;
        const renderedError = box.dataset.ewpBbbError === "1";
        let timer = null;
        let stopped = false;
        let interval = BBB_POLL_INTERVAL_MS;

        function backOff(failed) {
            interval = failed ? Math.min(interval * 2, BBB_POLL_MAX_MS) : BBB_POLL_INTERVAL_MS;
        }

        async function check() {
            if (stopped) {
                return;
            }
            try {
                const response = await fetch(url, {
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {Accept: "application/json"},
                });
                const type = response.headers.get("Content-Type") || "";
                if (!response.ok || !type.includes("application/json")) {
                    if (response.status === 403 || response.redirected) {
                        stopped = true;
                    }
                    return;
                }
                const data = (await response.json()) || {};
                const failed = Boolean(data.error);
                const state = typeof data.state === "string" ? data.state : "";
                if (state !== bbbState.rendered || failed !== renderedError) {
                    stopped = true;
                    let key = "bbb_waiting";
                    if (data.running) {
                        key = "bbb_started";
                    } else if (failed) {
                        key = "bbb_unavailable";
                    } else if (bbbState.renderedLive) {
                        key = "bbb_ended";
                    }
                    announcer.later(key, {}, BBB_FOCUS_ID);
                    // The conference frame is inserted before the chat:
                    // see reloadPage() for why it is not reload().
                    reloadPage();
                    return;
                }
                backOff(failed);
            } catch {
                // Network error: the next tick tries again, later.
                backOff(true);
            }
        }

        function schedule() {
            clearTimeout(timer);
            if (stopped || document.hidden) {
                return;
            }
            timer = setTimeout(async () => {
                await check();
                schedule();
            }, interval);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                clearTimeout(timer);
            } else {
                check().then(schedule);
            }
        });
        schedule();
    }

    function setupNewTab(root, bbbState, announcer) {
        const link = root.querySelector(".o_ewp_bbb_newtab");
        const frame = root.querySelector(".o_ewp_bbb_frame");
        const moved = root.querySelector(".o_ewp_bbb_moved");
        if (!link || !frame) {
            return;
        }
        link.addEventListener("click", () => {
            // The default action still opens the new tab.
            frame.src = "about:blank";
            frame.remove();
            const ondemand = root.querySelector(".o_ewp_bbb_ondemand");
            if (ondemand) {
                ondemand.hidden = true;
            }
            const video = root.querySelector(".o_ewp_video");
            if (video) {
                video.hidden = false;
            }
            announcer.sayKey("bbb_moved");
            const left = root.querySelector(".o_ewp_bbb_left");
            if (left) {
                left.hidden = true;
            }
            if (moved) {
                moved.hidden = false;
            }
            if (bbbState) {
                bbbState.set("moved");
            }
        });
    }

    function setupLeave(root, bbbState, announcer) {
        const frame = root.querySelector(".o_ewp_bbb_frame");
        const notice = root.querySelector(".o_ewp_bbb_left");
        const button = notice && notice.querySelector(".o_ewp_bbb_rejoin");
        if (!frame || !button) {
            return;
        }
        // In text-only mode the frame ships without src (data-ewp-src).
        const frameUrl = frame.dataset.ewpSrc || frame.getAttribute("src");
        const leftPath = notice.dataset.ewpBbbLeftPath || "";
        const checkUrl = notice.dataset.ewpBbbCheckUrl || "";
        let loads = 0;
        let left = false;
        let busy = false;

        // Address of the document in the frame, or null when it belongs to
        // another origin (the client, a logout page on another host).
        function frameHref() {
            try {
                return frame.contentWindow.location.href;
            } catch {
                return null;
            }
        }

        function isLeftPage(href) {
            if (!href || !leftPath) {
                return false;
            }
            try {
                return new URL(href).pathname === leftPath;
            } catch {
                return false;
            }
        }

        function showLeft() {
            left = true;
            frame.src = "about:blank";
            frame.hidden = true;
            notice.hidden = false;
            button.focus();
            announcer.sayKey("bbb_left");
            if (bbbState) {
                bbbState.set("left");
            }
        }

        function onLoad() {
            const href = frameHref();
            if (left || !frame.isConnected || href === "about:blank") {
                return;
            }
            loads += 1;
            if (loads > 1 || isLeftPage(href)) {
                showLeft();
            }
        }

        async function meetingRuns() {
            if (!checkUrl || !window.fetch) {
                return true;
            }
            try {
                const response = await fetch(checkUrl, {
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {Accept: "application/json"},
                });
                const type = response.headers.get("Content-Type") || "";
                if (!response.ok || !type.includes("application/json")) {
                    // 403 (day closed) or a redirect to the login page.
                    return false;
                }
                const data = await response.json();
                // A server that does not answer: bbb_join decides.
                return Boolean(data && (data.running || data.error));
            } catch {
                return true;
            }
        }

        // The address of a page rendered after a leave carries left=1:
        // once the user joins again, a reload must show the meeting.
        function dropLeftMarker() {
            const url = new URL(window.location.href);
            if (url.searchParams.has("left")) {
                url.searchParams.delete("left");
                window.history.replaceState(window.history.state, "", url.href);
            }
        }

        async function rejoin() {
            if (busy || !left) {
                return;
            }
            busy = true;
            const runs = await meetingRuns();
            busy = false;
            if (!runs) {
                announcer.later("bbb_waiting", {}, BBB_FOCUS_ID);
                reloadPage();
                return;
            }
            left = false;
            loads = 0;
            dropLeftMarker();
            notice.hidden = true;
            frame.hidden = false;
            frame.src = frameUrl;
            frame.focus();
            if (bbbState) {
                bbbState.set("running");
            }
        }

        // The script runs once the page is parsed, before the client, two
        // redirects away, has loaded. A load missed all the same only
        // delays the count by one: a later load from another host then
        // goes unnoticed, the left page never does.
        if (!notice.hidden) {
            // Rendered after a leave (the redirect of bbb_left): the frame
            // ships hidden and without src, "Join again" loads it.
            left = true;
            button.focus();
            announcer.holdFocus(button);
            announcer.sayKey("bbb_left");
        } else if (isLeftPage(frameHref())) {
            showLeft();
        }
        frame.addEventListener("load", onLoad);
        button.addEventListener("click", rejoin);
    }

    function setupShowVideo(root) {
        const button = root.querySelector(".o_ewp_bbb_show");
        const video = root.querySelector(".o_ewp_video");
        const frame = video && video.querySelector(".o_ewp_bbb_frame");
        if (!button || !frame) {
            return;
        }
        button.addEventListener("click", () => {
            if (!frame.getAttribute("src") && frame.dataset.ewpSrc) {
                frame.src = frame.dataset.ewpSrc;
            }
            video.hidden = false;
            button.setAttribute("aria-expanded", "true");
            const box = button.closest(".o_ewp_bbb_ondemand");
            if (box) {
                box.hidden = true;
            }
            frame.focus();
        });
    }

    function setupPlan(root) {
        const elements = root.querySelectorAll("[data-ewp-room-id]");
        if (!elements.length) {
            return;
        }
        function toggle(roomId, active) {
            for (const el of root.querySelectorAll(`[data-ewp-room-id="${roomId}"]`)) {
                const cls = el.classList.contains("o_ewp_hotspot") ? "o_ewp_hotspot_active" : "o_ewp_room_active";
                el.classList.toggle(cls, active);
            }
        }
        for (const el of elements) {
            const roomId = el.dataset.ewpRoomId;
            el.addEventListener("mouseenter", () => toggle(roomId, true));
            el.addEventListener("mouseleave", () => toggle(roomId, false));
            el.addEventListener("focus", () => toggle(roomId, true));
            el.addEventListener("blur", () => toggle(roomId, false));
        }
    }

    function setupLiveRooms(root, announcer) {
        const list = root.querySelector("[data-ewp-live-url]");
        if (!list || !window.fetch) {
            return;
        }
        const url = list.dataset.ewpLiveUrl;
        let live = null;
        let timer = null;
        let stopped = false;

        function mark(ids) {
            for (const el of root.querySelectorAll(
                ".o_ewp_hotspot[data-ewp-room-id], .o_ewp_room_link[data-ewp-room-id]"
            )) {
                const on = ids.has(el.dataset.ewpRoomId);
                if (on) {
                    el.dataset.ewpLive = "true";
                } else {
                    delete el.dataset.ewpLive;
                }
                const pill = el.querySelector(".o_ewp_pill_live");
                if (pill) {
                    pill.hidden = !on;
                }
            }
        }

        function announceNew(ids) {
            for (const link of root.querySelectorAll(".o_ewp_room_link[data-ewp-room-id]")) {
                const id = link.dataset.ewpRoomId;
                if (ids.has(id) && !live.has(id)) {
                    const name = link.querySelector(".o_ewp_room_name");
                    announcer.sayKey("room_live", {
                        room: name ? name.textContent.trim() : "",
                    });
                }
            }
        }

        async function check() {
            if (stopped) {
                return;
            }
            try {
                const response = await fetch(url, {
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {Accept: "application/json"},
                });
                const type = response.headers.get("Content-Type") || "";
                if (!response.ok || !type.includes("application/json")) {
                    if (response.status === 403 || response.redirected) {
                        stopped = true;
                    }
                    return;
                }
                const data = await response.json();
                const ids = new Set(((data && data.live) || []).map(String));
                const initial = live === null;
                if (!initial && ids.size === live.size && [...ids].every((id) => live.has(id))) {
                    return;
                }
                if (!initial) {
                    announceNew(ids);
                }
                live = ids;
                mark(ids);
                emit("ewp:rooms-live", {ids: [...ids], initial});
            } catch {
                // Network error: the next tick tries again.
            }
        }

        function schedule() {
            clearTimeout(timer);
            if (stopped || document.hidden) {
                return;
            }
            timer = setTimeout(async () => {
                await check();
                schedule();
            }, LIVE_POLL_INTERVAL_MS);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                clearTimeout(timer);
            } else {
                check().then(schedule);
            }
        });
        check().then(schedule);
    }

    function registerServiceWorker(root) {
        const app = root.querySelector("[data-ewp-sw-url]");
        if (!app || !("serviceWorker" in navigator) || !window.isSecureContext) {
            return;
        }
        navigator.serviceWorker.register(app.dataset.ewpSwUrl, {scope: app.dataset.ewpSwScope}).catch(() => {
            // Without a service worker the pages work the same; only
            // installation on the home screen may be offered less often.
        });
    }

    function start() {
        const root = document.body;
        if (!root || !root.classList.contains("o_ewp_webapp")) {
            return;
        }
        const announcer = createAnnouncer(root);
        const motion = setupMotion(root);
        const day = setupDayState(root);
        const bbbState = conferenceState(root);
        setupPreferences(root, announcer, motion);
        setupSkipLinks(root);
        setupRaffles(root, announcer);
        setupConference(root, bbbState, announcer);
        setupNewTab(root, bbbState, announcer);
        setupLeave(root, bbbState, announcer);
        setupShowVideo(root);
        setupPlan(root);
        setupLiveRooms(root, announcer);
        document.addEventListener("ewp:announce", (ev) => {
            const text = ev.detail && ev.detail.text;
            if (text) {
                announcer.say(String(text));
            }
        });
        registerServiceWorker(root);
        announcer.replayStored();
        // The states of that moment: a change made before the delay (a
        // frame already on the left page) is part of them.
        setTimeout(() => {
            const dayState = day ? day.current() : "none";
            emit("ewp:ready", {
                page: day ? day.page : "",
                dayState,
                textOnly: root.classList.contains("o_ewp_text_only"),
                motionPaused: motion.paused(),
                motionMode: motion.mode(),
            });
            emit("ewp:day-state", {state: dayState, previous: null, initial: true});
            emit("ewp:motion", {
                paused: motion.paused(),
                mode: motion.mode(),
                initial: true,
            });
            if (bbbState) {
                emit("ewp:bbb-state", {
                    state: bbbState.current(),
                    previous: null,
                    initial: true,
                    live: bbbState.live(bbbState.current()),
                });
            }
        }, 0);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
