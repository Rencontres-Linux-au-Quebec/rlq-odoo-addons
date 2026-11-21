// @odoo-module ignore
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
//
// Cameo engine of the event web app pages: small decorative actors that
// come in at the edge of the page, play an action for a few seconds (drink
// a coffee, type on a keyboard, speak in a microphone, wave, celebrate) and
// go away. A plain script, loaded after webapp.js in the bundle.
//
// - Layer: one fixed element, .o_ewp_cameo_layer, child of the body,
//   aria-hidden, without pointer events, above the page and under the skip
//   links (z-index 900). Each cameo is a .o_ewp_cameo element in it, with
//   the classes o_ewp_cameo_from_<side> (bottom, left, right: the edge of
//   the window it slides from; pop: it grows in place) and o_ewp_cameo_do_<action>, the data attributes
//   data-ewp-actor, data-ewp-action and data-ewp-phase ("enter", "act",
//   "exit"), and the node of its actor inside .o_ewp_cameo_actor.
// - Actors: window.ewpCameo.register({name, actions, render, weight,
//   fallback}). `render(action, context)` returns a Node or an HTML string
//   (context: {size, side, phone}); `actions` lists the actions it plays;
//   `weight` (default 1) weighs the random choice. An actor with `fallback`
//   plays only while no other actor is registered: the neutral actor of
//   this file is one, so a theme that registers its own replaces it.
// - Spots: a cameo never covers a control (link, button, field, frame,
//   element with a tab stop), a picture (img, svg, video, canvas of 32 px
//   or more) or a text of the page (the box of every text node shown,
//   aria-hidden ones included: an age label, a number in a badge), nor an
//   element marked data-ewp-cameo-avoid (a theme marks so a decoration
//   without text that no cameo may cover), nor another cameo, with GAP_PX
//   around. The
//   candidates are the bottom corners of the window, the bottom edge of
//   the header bar, the side margins beside the content and the corners of
//   the cards, inside and outside them; on a phone the bottom corners and the header edge come
//   first. A cameo that the page brings over a control or a text leaves at
//   once: the check runs SCROLL_CHECK_MS after a scroll, a resize, a focus,
//   a change of the size of the content or a change of the DOM outside the
//   layer (a live refresh that swaps a block, an attribute that shows a
//   button). Without a free spot no cameo plays.
// - Schedule: the first cameo enters firstMinDelay to firstMaxDelay ms
//   (2 to 3 s) after the schedule starts (page ready, tab shown again,
//   animations resumed), then one every minDelay to maxDelay ms (4 to
//   8 s), at most maxActivePhone (1) under phoneWidth px, maxActive (2)
//   above. configure() restarts the schedule on the regular delay.
//   Each lasts enterMs + a random actionMs + exitMs, under 7 s. The
//   schedule stops while the tab is hidden (the cameos leave) and while the
//   animations are paused: ewp:motion with paused true, the text-only mode,
//   or data-ewp-motion other than "running" removes every cameo at once.
// - Events: ewp:raffle-drawn plays "celebrate" near the raffle card,
//   ewp:bbb-state "running" plays "speak" near the conference, ewp:day-state
//   "before" plays "coffee"; such a cameo makes room by sending the oldest
//   one away. Each cameo sends ewp:cameo on document, detail {phase:
//   "enter" or "exit", actor, action, trigger ("schedule", "raffle",
//   "bbb", "day", "play"), reason (exit: "done", "stop", "hidden",
//   "overlap", "replaced"), rect {left, top, width, height}}.
// - API: window.ewpCameo.register(), unregister(name), configure(options)
//   (any key of DEFAULTS; restarts the schedule), play(action, {near})
//   (one cameo now; returns whether it entered), state() ({running,
//   active: [{actor, action, phase, rect}], actors: [names], options,
//   history: the details of the last 50 ewp:cameo events}).
(function () {
    "use strict";

    const DEFAULTS = {
        firstMinDelay: 2000,
        firstMaxDelay: 3000,
        minDelay: 4000,
        maxDelay: 8000,
        enterMs: 700,
        actionMs: [3200, 4800],
        exitMs: 600,
        // Delay between a page event and its cameo: the layout settles.
        eventDelay: 400,
        maxActive: 2,
        maxActivePhone: 1,
        phoneWidth: 640,
        size: 88,
        sizePhone: 64,
    };
    const GAP_PX = 8;
    // Smallest picture (width and height, px) a cameo keeps clear of.
    const MIN_PICTURE_PX = 32;
    const SCROLL_CHECK_MS = 150;
    const CONTROLS =
        "a[href], button, input, select, textarea, iframe, summary, label, [role='button'], [role='link'], " +
        "[tabindex]:not([tabindex='-1']), [contenteditable='true']";
    const PICTURES = "img, svg, video, canvas, object";
    const AVOID = "[data-ewp-cameo-avoid]";
    const HEADER = ".o_ewp_appbar, .o_ewp_topbar, header";
    const CARDS = ".o_ewp_card, .o_ewp_closed, .o_ewp_bbb, main > section";
    const CONTENT = "main, .o_ewp_closed";
    const EVENT_SPOTS = {
        raffle: ".o_ewp_raffles_card",
        bbb: ".o_ewp_bbb",
        day: ".o_ewp_closed, .o_ewp_dayhead",
    };

    // Entries of the last ewp:cameo events, for state().
    const HISTORY_SIZE = 50;
    const actors = new Map();
    const active = new Set();
    const history = [];
    let options = {...DEFAULTS};
    let layer = null;
    let timer = null;
    let scrollTimer = null;
    let started = false;
    let running = false;

    function emit(phase, cameo, reason) {
        const detail = {
            phase,
            actor: cameo.actor.name,
            action: cameo.action,
            trigger: cameo.trigger,
            reason: reason || "",
            rect: {...cameo.rect},
        };
        history.push(detail);
        history.splice(0, history.length - HISTORY_SIZE);
        document.dispatchEvent(new CustomEvent("ewp:cameo", {bubbles: true, detail: {...detail}}));
    }

    function random(min, max) {
        return min + Math.random() * (max - min);
    }

    function shuffle(list) {
        for (let i = list.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [list[i], list[j]] = [list[j], list[i]];
        }
        return list;
    }

    function isPhone() {
        return document.documentElement.clientWidth < options.phoneWidth;
    }

    // Whether cameos may play now: page script started, animations
    // running, not text-only, tab visible.
    function allowed() {
        const body = document.body;
        return Boolean(
            body &&
                body.classList.contains("o_ewp_webapp") &&
                !body.classList.contains("o_ewp_text_only") &&
                body.dataset.ewpMotion === "running" &&
                !document.hidden
        );
    }

    // ---- Actors ------------------------------------------------------------
    function register(spec) {
        if (!spec || !spec.name || typeof spec.render !== "function") {
            throw new Error("ewpCameo.register: name and render() are required");
        }
        const list = Array.isArray(spec.actions) ? spec.actions.filter(Boolean).map(String) : [];
        if (!list.length) {
            throw new Error("ewpCameo.register: actions must list at least one action");
        }
        actors.set(String(spec.name), {
            name: String(spec.name),
            actions: list,
            render: spec.render,
            weight: spec.weight > 0 ? Number(spec.weight) : 1,
            fallback: Boolean(spec.fallback),
        });
    }

    function unregister(name) {
        actors.delete(String(name));
    }

    // The actors that play: the registered ones, else the fallbacks;
    // those that play `action` when given.
    function cast(action) {
        let list = [...actors.values()].filter((actor) => !actor.fallback);
        if (!list.length) {
            list = [...actors.values()];
        }
        return action ? list.filter((actor) => actor.actions.includes(action)) : list;
    }

    function pickActor(action) {
        const list = cast(action);
        const total = list.reduce((sum, actor) => sum + actor.weight, 0);
        let draw = Math.random() * total;
        for (const actor of list) {
            draw -= actor.weight;
            if (draw <= 0) {
                return actor;
            }
        }
        return list[list.length - 1] || null;
    }

    // ---- Geometry ----------------------------------------------------------
    function visibleBox(el) {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) {
            return null;
        }
        if (rect.bottom < 0 || rect.top > window.innerHeight || rect.right < 0 || rect.left > window.innerWidth) {
            return null;
        }
        return rect;
    }

    function inLayer(node) {
        return Boolean(layer && layer.contains(node));
    }

    // Boxes, in viewport pixels, that a cameo must not cover: the
    // controls, the marked elements, the pictures and the texts in view.
    function obstacles() {
        const boxes = [];
        for (const el of document.body.querySelectorAll(CONTROLS)) {
            const rect = !inLayer(el) && visibleBox(el);
            if (rect) {
                boxes.push(rect);
            }
        }
        for (const el of document.body.querySelectorAll(AVOID)) {
            const rect = !inLayer(el) && visibleBox(el);
            if (rect) {
                boxes.push(rect);
            }
        }
        for (const el of document.body.querySelectorAll(PICTURES)) {
            const rect = !inLayer(el) && visibleBox(el);
            if (rect && rect.width >= MIN_PICTURE_PX && rect.height >= MIN_PICTURE_PX) {
                boxes.push(rect);
            }
        }
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                if (!node.nodeValue.trim()) {
                    return NodeFilter.FILTER_REJECT;
                }
                const parent = node.parentElement;
                // aria-hidden text is shown all the same: it counts.
                if (!parent || inLayer(parent) || parent.closest("script, style, template")) {
                    return NodeFilter.FILTER_REJECT;
                }
                return NodeFilter.FILTER_ACCEPT;
            },
        });
        const range = document.createRange();
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            range.selectNodeContents(node);
            for (const rect of range.getClientRects()) {
                if (rect.width > 1 && rect.height > 1 && rect.bottom >= 0 && rect.top <= window.innerHeight) {
                    boxes.push(rect);
                }
            }
        }
        return boxes;
    }

    function overlaps(a, b, gap) {
        return (
            a.left < b.right + gap &&
            a.left + a.width > b.left - gap &&
            a.top < b.bottom + gap &&
            a.top + a.height > b.top - gap
        );
    }

    function rectOf(left, top, size) {
        return {
            left: Math.round(left),
            top: Math.round(top),
            width: size,
            height: size,
        };
    }

    // Candidate spots {rect, side}, most wanted first.
    function candidates(size, near) {
        const vw = document.documentElement.clientWidth;
        const vh = window.innerHeight;
        const corners = [
            {rect: rectOf(GAP_PX, vh - size, size), side: "bottom"},
            {rect: rectOf(vw - size - GAP_PX, vh - size, size), side: "bottom"},
        ];
        const header = [];
        const bar = [...document.querySelectorAll(HEADER)].map(visibleBox).find(Boolean);
        if (bar && bar.bottom > 0 && bar.bottom < vh / 2) {
            for (const share of [0.04, 0.3, 0.62, 0.96]) {
                header.push({
                    rect: rectOf(share * (vw - size), bar.bottom + GAP_PX, size),
                    side: "pop",
                });
            }
        }
        const margins = [];
        const content = [...document.querySelectorAll(CONTENT)].map(visibleBox).find(Boolean);
        if (content) {
            for (const share of [0.25, 0.5, 0.75]) {
                const top = share * (vh - size);
                if (content.left >= size + 2 * GAP_PX) {
                    margins.push({
                        rect: rectOf((content.left - size) / 2, top, size),
                        side: "left",
                    });
                }
                if (vw - content.right >= size + 2 * GAP_PX) {
                    margins.push({
                        rect: rectOf(content.right + (vw - content.right - size) / 2, top, size),
                        side: "right",
                    });
                }
            }
        }
        const cards = [];
        for (const el of document.querySelectorAll(CARDS)) {
            const box = inLayer(el) ? null : visibleBox(el);
            if (!box) {
                continue;
            }
            const inset = Math.min(16, box.width / 8);
            // A cameo on a card grows in place: sliding, it would cross
            // the text of the card.
            for (const [left, top] of [
                [box.right - size - inset, box.top + inset],
                [box.right - size - inset, box.bottom - size - inset],
                [box.right - size - inset, box.top - size + 4],
                [box.left + inset, box.top - size + 4],
                [box.right - size - inset, box.bottom - 4],
                [box.left + inset, box.bottom - 4],
                [box.right - size / 2, box.top + inset],
                [box.left - size / 2, box.top + inset],
            ]) {
                cards.push({rect: rectOf(left, top, size), side: "pop"});
            }
        }
        let list = isPhone()
            ? [...shuffle(corners), ...shuffle(header), ...shuffle([...cards, ...margins])]
            : shuffle([...corners, ...header, ...margins, ...cards]);
        const target = near && [...document.querySelectorAll(near)].map(visibleBox).find(Boolean);
        if (target) {
            const cx = target.left + target.width / 2;
            const cy = target.top + target.height / 2;
            const distance = (spot) => Math.hypot(spot.rect.left + size / 2 - cx, spot.rect.top + size / 2 - cy);
            list = list.sort((a, b) => distance(a) - distance(b));
        }
        return list;
    }

    function fits(rect, boxes) {
        const vw = document.documentElement.clientWidth;
        const vh = window.innerHeight;
        if (rect.left < 0 || rect.top < 0 || rect.left + rect.width > vw || rect.top + rect.height > vh) {
            return false;
        }
        if (boxes.some((box) => overlaps(rect, box, GAP_PX))) {
            return false;
        }
        return ![...active].some((cameo) => overlaps(rect, cameo.rect, GAP_PX));
    }

    function findSpot(size, near) {
        const boxes = obstacles();
        return candidates(size, near).find((spot) => fits(spot.rect, boxes)) || null;
    }

    // ---- Cameos ------------------------------------------------------------
    function ensureLayer() {
        if (!layer || !layer.isConnected) {
            layer = document.createElement("div");
            layer.className = "o_ewp_cameo_layer";
            layer.setAttribute("aria-hidden", "true");
            document.body.appendChild(layer);
        }
        return layer;
    }

    function renderActor(actor, action, context) {
        const out = actor.render(action, context);
        if (out instanceof Node) {
            return out;
        }
        const template = document.createElement("template");
        template.innerHTML = String(out || "");
        return template.content;
    }

    function setPhase(cameo, phase) {
        cameo.phase = phase;
        cameo.el.dataset.ewpPhase = phase;
    }

    function remove(cameo, reason) {
        if (!active.has(cameo)) {
            return;
        }
        active.delete(cameo);
        for (const id of cameo.timers) {
            clearTimeout(id);
        }
        cameo.el.remove();
        emit("exit", cameo, reason);
    }

    // Sends `cameo` away: its exit animation, then removal.
    function leave(cameo, reason) {
        if (!active.has(cameo) || cameo.phase === "exit") {
            return;
        }
        for (const id of cameo.timers) {
            clearTimeout(id);
        }
        setPhase(cameo, "exit");
        cameo.timers = [setTimeout(() => remove(cameo, reason), options.exitMs)];
    }

    function spawn(action, near, trigger) {
        if (!started || !allowed()) {
            return false;
        }
        const phone = isPhone();
        const limit = phone ? options.maxActivePhone : options.maxActive;
        const present = [...active].filter((cameo) => cameo.phase !== "exit");
        if (present.length >= limit) {
            if (trigger === "schedule") {
                return false;
            }
            // A cameo of a page event makes room at once.
            for (const cameo of present.slice(0, present.length - limit + 1)) {
                remove(cameo, "replaced");
            }
        }
        const actor = pickActor(action);
        if (!actor) {
            return false;
        }
        const play = action || actor.actions[Math.floor(Math.random() * actor.actions.length)];
        const size = phone ? options.sizePhone : options.size;
        const spot = findSpot(size, near);
        if (!spot) {
            return false;
        }
        const el = document.createElement("div");
        el.className = `o_ewp_cameo o_ewp_cameo_from_${spot.side} o_ewp_cameo_do_${play}`;
        el.dataset.ewpActor = actor.name;
        el.dataset.ewpAction = play;
        el.style.left = `${spot.rect.left}px`;
        el.style.top = `${spot.rect.top}px`;
        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.setProperty("--ewp-cameo-enter", `${options.enterMs}ms`);
        el.style.setProperty("--ewp-cameo-exit", `${options.exitMs}ms`);
        const body = document.createElement("div");
        body.className = "o_ewp_cameo_actor";
        body.appendChild(renderActor(actor, play, {size, side: spot.side, phone}));
        el.appendChild(body);
        for (const node of el.querySelectorAll("svg")) {
            node.setAttribute("focusable", "false");
        }
        const cameo = {
            el,
            actor,
            action: play,
            trigger,
            rect: spot.rect,
            phase: "enter",
            timers: [],
        };
        setPhase(cameo, "enter");
        active.add(cameo);
        ensureLayer().appendChild(el);
        emit("enter", cameo);
        const [low, high] = options.actionMs;
        const actFor = random(low, high);
        cameo.timers.push(
            setTimeout(() => setPhase(cameo, "act"), options.enterMs),
            setTimeout(() => leave(cameo, "done"), options.enterMs + actFor)
        );
        return true;
    }

    function clearAll(reason) {
        for (const cameo of [...active]) {
            remove(cameo, reason);
        }
    }

    // ---- Schedule ----------------------------------------------------------
    // Sets the timer of the next scheduled cameo; `first` takes the short
    // delay of a schedule that starts.
    function schedule(first) {
        clearTimeout(timer);
        timer = null;
        if (!running) {
            return;
        }
        const delay = first
            ? random(options.firstMinDelay, options.firstMaxDelay)
            : random(options.minDelay, options.maxDelay);
        timer = setTimeout(() => {
            spawn(null, null, "schedule");
            schedule(false);
        }, delay);
    }

    // Starts or stops the schedule after a change of motion or visibility.
    function sync(reason) {
        const next = started && allowed();
        if (next === running) {
            return;
        }
        running = next;
        if (running) {
            schedule(true);
        } else {
            clearTimeout(timer);
            timer = null;
            clearAll(reason);
        }
    }

    // A cameo that the page brought over a control or a text leaves.
    function checkOverlap() {
        scrollTimer = null;
        if (!active.size) {
            return;
        }
        const boxes = obstacles();
        for (const cameo of [...active]) {
            if (cameo.phase !== "exit" && boxes.some((box) => overlaps(cameo.rect, box, 0))) {
                remove(cameo, "overlap");
            }
        }
    }

    // Runs checkOverlap() once, SCROLL_CHECK_MS later, while a cameo is
    // on screen.
    function recheck() {
        if (active.size && !scrollTimer) {
            scrollTimer = setTimeout(checkOverlap, SCROLL_CHECK_MS);
        }
    }

    // Whether a mutation record changes the page rather than the layer
    // (its cameos, or the layer added to the body).
    function outsideLayer(record) {
        if (inLayer(record.target)) {
            return false;
        }
        if (record.type !== "childList") {
            return true;
        }
        const nodes = [...record.addedNodes, ...record.removedNodes];
        return !nodes.length || nodes.some((node) => node !== layer);
    }

    // Layout changes that come with no scroll or resize event: the DOM
    // of the page and the size of its content.
    function watchPage() {
        if (window.MutationObserver) {
            new MutationObserver((records) => {
                if (records.some(outsideLayer)) {
                    recheck();
                }
            }).observe(document.body, {
                attributes: true,
                characterData: true,
                childList: true,
                subtree: true,
            });
        }
        if (window.ResizeObserver) {
            const sizes = new ResizeObserver(recheck);
            for (const el of document.querySelectorAll(CONTENT)) {
                sizes.observe(el);
            }
        }
    }

    function onEvent(trigger, action) {
        setTimeout(() => spawn(action, EVENT_SPOTS[trigger], trigger), options.eventDelay);
    }

    function configure(values) {
        for (const [key, value] of Object.entries(values || {})) {
            if (Object.prototype.hasOwnProperty.call(DEFAULTS, key)) {
                options[key] = key === "actionMs" ? [Number(value[0]), Number(value[1])] : Number(value);
            }
        }
        if (running) {
            schedule(false);
        }
    }

    function start() {
        if (started || !document.body || !document.body.classList.contains("o_ewp_webapp")) {
            return;
        }
        started = true;
        watchPage();
        sync("stop");
    }

    document.addEventListener("ewp:ready", start);
    document.addEventListener("ewp:motion", (ev) => {
        if (ev.detail && ev.detail.paused) {
            // At once, before the next frame: no cameo outlives the pause.
            running = false;
            clearTimeout(timer);
            timer = null;
            clearAll("stop");
            return;
        }
        sync("stop");
    });
    document.addEventListener("visibilitychange", () => sync("hidden"));
    window.addEventListener("scroll", recheck, {passive: true});
    window.addEventListener("resize", recheck, {passive: true});
    document.addEventListener("focusin", recheck);
    document.addEventListener("ewp:raffle-drawn", () => onEvent("raffle", "celebrate"));
    document.addEventListener("ewp:bbb-state", (ev) => {
        if (ev.detail && ev.detail.state === "running") {
            onEvent("bbb", "speak");
        }
    });
    document.addEventListener("ewp:day-state", (ev) => {
        if (ev.detail && ev.detail.state === "before") {
            onEvent("day", "coffee");
        }
    });

    // ---- Neutral actor -----------------------------------------------------
    // A round figure in the accent colour of the page, with the prop of
    // its action; the theme modules bring their own actors.
    const PROPS = {
        wave: '<path class="o_ewp_cameo_arm" d="M74 58 q14 -10 16 -26" />',
        coffee:
            '<g class="o_ewp_cameo_prop"><path class="o_ewp_cameo_cup" d="M66 60 h18 v12 a9 9 0 0 1 -18 0 z" />' +
            '<path class="o_ewp_cameo_handle" d="M84 63 a5 5 0 0 1 0 9" />' +
            '<path class="o_ewp_cameo_steam" d="M71 54 q-3 -5 0 -10 q3 -5 0 -10" />' +
            '<path class="o_ewp_cameo_steam o_ewp_cameo_steam_2" d="M79 54 q-3 -5 0 -10 q3 -5 0 -10" /></g>',
        code:
            '<g class="o_ewp_cameo_prop"><rect class="o_ewp_cameo_board" x="18" y="74" width="64" height="16" rx="3" />' +
            '<rect class="o_ewp_cameo_key" x="24" y="78" width="8" height="4" />' +
            '<rect class="o_ewp_cameo_key o_ewp_cameo_key_2" x="38" y="78" width="8" height="4" />' +
            '<rect class="o_ewp_cameo_key o_ewp_cameo_key_3" x="52" y="78" width="8" height="4" />' +
            '<rect class="o_ewp_cameo_key o_ewp_cameo_key_4" x="66" y="78" width="10" height="4" /></g>',
        speak:
            '<g class="o_ewp_cameo_prop"><rect class="o_ewp_cameo_mic" x="70" y="40" width="10" height="18" rx="5" />' +
            '<path class="o_ewp_cameo_stand" d="M75 58 v14 M68 72 h14" />' +
            '<path class="o_ewp_cameo_wave" d="M86 42 q5 7 0 14" />' +
            '<path class="o_ewp_cameo_wave o_ewp_cameo_wave_2" d="M91 38 q8 11 0 22" /></g>',
        celebrate:
            '<g class="o_ewp_cameo_prop"><circle class="o_ewp_cameo_confetti" cx="20" cy="22" r="3" />' +
            '<circle class="o_ewp_cameo_confetti o_ewp_cameo_confetti_2" cx="80" cy="18" r="3" />' +
            '<rect class="o_ewp_cameo_confetti o_ewp_cameo_confetti_3" x="48" y="6" width="5" height="5" /></g>',
    };

    register({
        name: "ewp-neutral",
        actions: Object.keys(PROPS),
        fallback: true,
        render(action) {
            return (
                '<svg class="o_ewp_cameo_neutral" viewBox="0 0 100 100" width="100%" height="100%" ' +
                'aria-hidden="true" focusable="false">' +
                '<g class="o_ewp_cameo_figure"><ellipse class="o_ewp_cameo_body" cx="46" cy="60" rx="28" ry="30" />' +
                '<circle class="o_ewp_cameo_eye" cx="37" cy="52" r="4" />' +
                '<circle class="o_ewp_cameo_eye" cx="55" cy="52" r="4" />' +
                '<path class="o_ewp_cameo_mouth" d="M39 66 q7 6 14 0" /></g>' +
                (PROPS[action] || "") +
                "</svg>"
            );
        },
    });

    window.ewpCameo = {
        register,
        unregister,
        configure,
        play(action, settings = {}) {
            return spawn(action ? String(action) : null, settings.near || null, "play");
        },
        state() {
            return {
                running,
                active: [...active].map((cameo) => ({
                    actor: cameo.actor.name,
                    action: cameo.action,
                    phase: cameo.phase,
                    rect: {...cameo.rect},
                })),
                actors: [...actors.keys()],
                options: {...options, actionMs: [...options.actionMs]},
                history: history.map((entry) => ({...entry})),
            };
        },
    };
})();
