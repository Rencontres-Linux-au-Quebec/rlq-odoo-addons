// @odoo-module ignore
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
//
// Agenda of the event web app pages, a plain script of the bundle
// event_webapp_plan.assets_webapp, loaded after webapp.js.
//
// - Data: the element carrying data-ewp-agenda-url (the home card, or the
//   room block of a room page, with data-ewp-agenda-room) holds the sessions
//   of the day as JSON (data-ewp-agenda-sessions: id, title, start, end as
//   ISO 8601 with offset, start_label, end_label, room_id, room_name), the
//   translated patterns of the messages (data-ewp-agenda-messages,
//   "%(name)s" filled in here) and the signature of the program.
// - Clock: the state of each session ("past", "now", "later", and "next"
//   for every session of the earliest start still to come) is computed
//   from the clock of the device, at start, at each start or end of a
//   session (a timer set on the nearest one), at least every minute, and
//   when the tab shows again. It writes data-ewp-state on the items
//   .ewp_track_session, shows their badge "Now" or "Next" (attribute
//   hidden), writes the line of each room ([data-ewp-track-room]: "Now:
//   ..." or "Next at ...: ...", hidden when the room has nothing left,
//   else the "none" message when the line carries data-ewp-track-none) and
//   marks the area of a room with a session in progress on the plan
//   (data-ewp-session="now"). Nothing moves: the states are text.
// - Events: a session that starts or ends while the page is open sends
//   ewp:session {room: {id, name} or null, track: {id, title, start, end},
//   state: "start" or "end"} on document; the states found at start send
//   nothing. On a room page, a session of that room that starts is said
//   once in the shared live region (ewp:announce of webapp.js).
// - Cameo: when a session starts (on a room page, a session of that
//   room), one "speak" cameo of window.ewpCameo plays near the agenda
//   block, CAMEO_DELAY_MS after the states are painted; several starts
//   at the same moment play one cameo. Without the engine, or while the
//   animations are paused, nothing plays.
// - Program: the JSON route of data-ewp-agenda-url is asked every 5
//   minutes while the tab is visible, and when it shows again. A new
//   signature replaces the sessions and the blocks .ewp_track_agenda_body
//   and .ewp_track_room_body (open descriptions stay open), unless the
//   focus is inside one of them: the next answer applies it then. Polling
//   stops for good on a 403, a 404 or a redirect (day closed, session
//   expired).
// - Filter by room: the toggle buttons of form.ewp_track_filter filter
//   the home card in place (items and empty slots hidden), press the
//   chosen button, keep the choice in the address (agenda_room, so a
//   reload or the display options keep it) and say the number of sessions
//   shown. Without script the form loads the filtered page.
(function () {
    "use strict";

    // Longest wait between two checks of the clock.
    const TICK_MS = 60000;
    // Delay after a start or an end, so the check sees the moment passed.
    const BOUNDARY_MARGIN_MS = 250;
    const REFRESH_MS = 300000;
    const MAX_TIMEOUT_MS = 2147483647;
    // Delay between a start and its cameo: the layout settles.
    const CAMEO_DELAY_MS = 400;
    const CAMEO_NEAR = "#ewp_track_room, #ewp_track_agenda";

    function parseJson(raw, fallback) {
        try {
            const value = JSON.parse(raw || "");
            return value === null || value === undefined ? fallback : value;
        } catch {
            return fallback;
        }
    }

    function fill(pattern, params) {
        return (pattern || "").replace(/%\((\w+)\)s/g, (match, name) =>
            Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : match
        );
    }

    function emit(name, detail) {
        document.dispatchEvent(new CustomEvent(name, {bubbles: true, detail}));
    }

    function start() {
        const root = document.body;
        if (!root || !root.classList.contains("o_ewp_webapp")) {
            return;
        }
        const box = root.querySelector("[data-ewp-agenda-url]");
        if (!box) {
            return;
        }
        const messages = parseJson(box.dataset.ewpAgendaMessages, {});
        const pageRoom = Number(box.dataset.ewpAgendaRoom || 0);
        let signature = box.dataset.ewpSignature || "";
        let sessions = [];
        // Clock state of each session id at the last check: past, now or
        // later.
        const states = new Map();
        const announced = new Set();
        let timer = null;

        function load(list) {
            sessions = (Array.isArray(list) ? list : [])
                .map((session) => ({
                    ...session,
                    startMs: Date.parse(session.start),
                    endMs: Date.parse(session.end),
                }))
                .filter((session) => !Number.isNaN(session.startMs) && !Number.isNaN(session.endMs));
        }

        function clockState(session, now) {
            if (now >= session.endMs) {
                return "past";
            }
            return now >= session.startMs ? "now" : "later";
        }

        // State of each session at `now`, "next" for the sessions of the
        // earliest start still to come.
        function stateMap(now) {
            const map = new Map();
            let nextStart = Infinity;
            for (const session of sessions) {
                const state = clockState(session, now);
                map.set(session.id, state);
                if (state === "later") {
                    nextStart = Math.min(nextStart, session.startMs);
                }
            }
            for (const session of sessions) {
                if (map.get(session.id) === "later" && session.startMs === nextStart) {
                    map.set(session.id, "next");
                }
            }
            return map;
        }

        function roomStatus(roomId, map) {
            const mine = sessions.filter((session) => session.room_id === roomId);
            const current = mine.find((session) => map.get(session.id) === "now");
            if (current) {
                return {state: "now", text: fill(messages.room_now, {title: current.title})};
            }
            const coming = mine
                .filter((session) => ["next", "later"].includes(map.get(session.id)))
                .sort((a, b) => a.startMs - b.startMs)[0];
            if (coming) {
                return {
                    state: "next",
                    text: fill(messages.room_next, {time: coming.start_label, title: coming.title}),
                };
            }
            return {state: "", text: ""};
        }

        function paint(map) {
            for (const item of root.querySelectorAll(".ewp_track_session[data-ewp-track-id]")) {
                const state = map.get(Number(item.dataset.ewpTrackId));
                if (!state) {
                    continue;
                }
                item.dataset.ewpState = state;
                const nowBadge = item.querySelector(".ewp_track_badge_now");
                const nextBadge = item.querySelector(".ewp_track_badge_next");
                if (nowBadge) {
                    nowBadge.hidden = state !== "now";
                }
                if (nextBadge) {
                    nextBadge.hidden = state !== "next";
                }
            }
            for (const line of root.querySelectorAll("[data-ewp-track-room]")) {
                const status = roomStatus(Number(line.dataset.ewpTrackRoom), map);
                const text = status.text || (line.dataset.ewpTrackNone ? messages.room_none || "" : "");
                if (line.textContent !== text) {
                    line.textContent = text;
                }
                if (status.state) {
                    line.dataset.ewpState = status.state;
                } else {
                    delete line.dataset.ewpState;
                }
                line.hidden = !text;
            }
            for (const spot of root.querySelectorAll(".o_ewp_hotspot[data-ewp-room-id]")) {
                const roomId = Number(spot.dataset.ewpRoomId);
                const busy = sessions.some((session) => session.room_id === roomId && map.get(session.id) === "now");
                if (busy) {
                    spot.dataset.ewpSession = "now";
                } else {
                    delete spot.dataset.ewpSession;
                }
            }
        }

        function schedule(now) {
            clearTimeout(timer);
            let delay = TICK_MS;
            for (const session of sessions) {
                for (const moment of [session.startMs, session.endMs]) {
                    if (moment > now) {
                        delay = Math.min(delay, moment - now + BOUNDARY_MARGIN_MS);
                    }
                }
            }
            timer = setTimeout(() => tick(false), Math.min(delay, MAX_TIMEOUT_MS));
        }

        // Checks the clock; `initial` records the states without sending
        // events.
        function tick(initial) {
            const now = Date.now();
            const map = stateMap(now);
            let speak = false;
            for (const session of sessions) {
                const state = map.get(session.id) === "next" ? "later" : map.get(session.id);
                const previous = states.get(session.id);
                states.set(session.id, state);
                if (initial || previous === undefined || previous === state) {
                    continue;
                }
                const detail = {
                    room: session.room_id ? {id: session.room_id, name: session.room_name} : null,
                    track: {id: session.id, title: session.title, start: session.start, end: session.end},
                };
                if (state === "now") {
                    emit("ewp:session", {...detail, state: "start"});
                    speak = speak || !pageRoom || session.room_id === pageRoom;
                    if (pageRoom && session.room_id === pageRoom && !announced.has(session.id)) {
                        announced.add(session.id);
                        emit("ewp:announce", {text: fill(messages.session_started, {title: session.title})});
                    }
                } else if (previous === "now") {
                    emit("ewp:session", {...detail, state: "end"});
                }
            }
            paint(map);
            schedule(now);
            if (speak && window.ewpCameo) {
                setTimeout(() => window.ewpCameo.play("speak", {near: CAMEO_NEAR}), CAMEO_DELAY_MS);
            }
        }

        // ---- Filter by room ------------------------------------------
        const filterForm = root.querySelector("form.ewp_track_filter");
        const choices = filterForm ? [...filterForm.querySelectorAll(".ewp_track_filter_choice")] : [];
        const filterParam = choices.length ? choices[0].name : "";
        let selected = "";
        const pressed = choices.find((choice) => choice.getAttribute("aria-pressed") === "true");
        if (pressed) {
            selected = pressed.value;
        }

        // Hides the sessions outside the chosen room, and the slots left
        // empty; returns the number of sessions shown.
        function applyFilter() {
            const body = root.querySelector(".ewp_track_agenda_body");
            if (!body || !filterForm) {
                return 0;
            }
            let count = 0;
            for (const slot of body.querySelectorAll(".ewp_track_slot")) {
                let shown = 0;
                for (const item of slot.querySelectorAll(".ewp_track_session")) {
                    const show = !selected || item.dataset.ewpRoomId === selected;
                    item.hidden = !show;
                    shown += show ? 1 : 0;
                }
                slot.hidden = shown === 0;
                count += shown;
            }
            return count;
        }

        // Keeps the choice in the address, and in the return path of the
        // display options, which load the page again.
        function keepChoice() {
            try {
                const url = new URL(window.location.href);
                if (selected) {
                    url.searchParams.set(filterParam, selected);
                } else {
                    url.searchParams.delete(filterParam);
                }
                window.history.replaceState(window.history.state, "", url.href);
                for (const field of root.querySelectorAll("form.o_ewp_pref_form input[name='redirect']")) {
                    field.value = url.pathname + url.search;
                }
            } catch {
                // An address the browser refuses to change: the filter
                // still applies to the page.
            }
        }

        if (filterForm) {
            filterForm.addEventListener("click", (ev) => {
                const button = ev.target instanceof Element ? ev.target.closest(".ewp_track_filter_choice") : null;
                if (!button || !filterForm.contains(button)) {
                    return;
                }
                ev.preventDefault();
                selected = button.value;
                for (const choice of choices) {
                    choice.setAttribute("aria-pressed", choice === button ? "true" : "false");
                }
                const count = applyFilter();
                keepChoice();
                const key = selected ? "filter_room" : "filter_all";
                emit("ewp:announce", {text: fill(messages[key], {room: button.textContent.trim(), count})});
            });
            filterForm.addEventListener("submit", (ev) => ev.preventDefault());
        }

        // ---- Program refresh -----------------------------------------
        let stopped = false;
        let busy = false;
        let refreshTimer = null;

        // Replaces the content of `selector` with `html`, keeping the
        // descriptions that were open.
        function swap(selector, html) {
            const target = root.querySelector(selector);
            if (!target || typeof html !== "string") {
                return;
            }
            const open = new Set(
                [...target.querySelectorAll(".ewp_track_session[data-ewp-track-id] details[open]")].map(
                    (details) => details.closest(".ewp_track_session").dataset.ewpTrackId
                )
            );
            target.innerHTML = html;
            for (const item of target.querySelectorAll(".ewp_track_session[data-ewp-track-id]")) {
                const details = item.querySelector("details");
                if (details && open.has(item.dataset.ewpTrackId)) {
                    details.open = true;
                }
            }
        }

        function focusInside() {
            const active = document.activeElement;
            return [".ewp_track_agenda_body", ".ewp_track_room_body"].some((selector) => {
                const block = root.querySelector(selector);
                return Boolean(block && active && block.contains(active));
            });
        }

        async function refresh() {
            if (stopped || busy || !window.fetch) {
                return;
            }
            busy = true;
            try {
                const response = await fetch(box.dataset.ewpAgendaUrl, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                if (response.redirected || response.status === 403 || response.status === 404) {
                    stopped = true;
                    return;
                }
                const type = response.headers.get("Content-Type") || "";
                if (!response.ok || !type.includes("application/json")) {
                    return;
                }
                const data = await response.json();
                if (!data || data.signature === signature || focusInside()) {
                    return;
                }
                signature = data.signature;
                load(data.sessions);
                swap(".ewp_track_agenda_body", data.html);
                swap(".ewp_track_room_body", data.room_html);
                applyFilter();
                tick(false);
            } catch {
                // Network error: the next refresh tries again.
            } finally {
                busy = false;
            }
        }

        function scheduleRefresh() {
            clearTimeout(refreshTimer);
            if (stopped || document.hidden) {
                return;
            }
            refreshTimer = setTimeout(async () => {
                await refresh();
                scheduleRefresh();
            }, REFRESH_MS);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.hidden) {
                clearTimeout(refreshTimer);
                return;
            }
            tick(false);
            refresh().then(scheduleRefresh);
        });

        load(parseJson(box.dataset.ewpAgendaSessions, []));
        applyFilter();
        tick(true);
        scheduleRefresh();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
