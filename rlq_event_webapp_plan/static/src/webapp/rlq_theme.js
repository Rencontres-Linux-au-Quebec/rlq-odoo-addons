// @odoo-module ignore
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
//
// Script of the Rencontres Linux theme, loaded after webapp.js and
// webapp_cameo.js in the bundle event_webapp_plan.assets_webapp. A plain
// script, like them.
//
// - Vector Tux of the page: every svg.o_rlq_tux outside the cameos carries
//   its pose in data-rlq-tux, drawn and animated by rlq_theme.scss. The
//   pose follows the events of webapp.js: the day state ("before":
//   sipping, "after": sleeping), the room conference (meeting running,
//   in the frame or behind the new tab button, the `live` of the event:
//   speak, into the microphone; "waiting": coffee; "left": wave for
//   WAVE_MS), a
//   raffle winner (celebrate, CELEBRATE_MS, then back), a wave on the
//   first page of the tab (greeting, GREETING_MS) and on the "conference
//   left" page (wave, WAVE_MS). Without script the server-side pose stays.
//   While the animations are paused (ewp:motion), the greeting and the
//   waves are skipped; the other poses are still, drawn without motion.
// - Tux cameos: two actors of the cameo engine (window.ewpCameo), drawn
//   from the copy of the vector Tux in template.o_rlq_tux_source (mascot
//   slot; absent in text-only mode, where no cameo plays). "rlq-tux"
//   plays the actions of the schedule (coffee, code, wave, peek, walk);
//   "rlq-tux-moments" the actions of the page events (celebrate for a
//   raffle winner, speak while a conference runs, sleep after the day),
//   with a weight so small that the schedule practically never draws it.
//   Each cameo is a .o_rlq_cameo_stage.o_rlq_cameo_<action> holding the
//   drawing in the pose of the action (ACTION_POSES). The engine places,
//   times and removes them; the theme sets their size (CAMEO_SIZE) and
//   plays "sleep" when the day is over.
// - Ribbon: the button .o_rlq_marquee_toggle pauses the ribbon of its band
//   (class o_rlq_marquee_paused) and tells it with aria-pressed.
(function () {
    "use strict";

    const CELEBRATE_MS = 4500;
    const GREETING_MS = 3000;
    const WAVE_MS = 4000;
    const GREETED_KEY = "rlq:greeted";
    const PAGE_TUX = "svg.o_rlq_tux:not(.o_rlq_tux_cameo)";
    // Side of the square of a cameo, px: phones (engine phoneWidth), and
    // wider screens.
    const CAMEO_SIZE = {sizePhone: 60, size: 88};
    const IDLE_ACTIONS = ["coffee", "code", "wave", "peek", "walk"];
    const MOMENT_ACTIONS = ["celebrate", "speak", "sleep"];
    // Weight of the actor of the page events in the random draw of the
    // schedule, against 1 for the idle actor.
    const MOMENT_WEIGHT = 1e-6;
    const ACTION_POSES = {
        coffee: "coffee",
        code: "code",
        wave: "wave",
        peek: "peek",
        walk: "walk",
        celebrate: "celebrate",
        speak: "speak",
        sleep: "sleeping",
    };

    let dayState = "none";
    let bbb = "";
    // The meeting runs, in the frame or behind the new tab button.
    let bbbLive = false;
    let page = "";
    let paused = false;
    let flash = null;
    let flashTimer = null;

    function basePose() {
        if (dayState === "before") {
            return "sipping";
        }
        if (dayState === "after") {
            return "sleeping";
        }
        if (bbbLive) {
            return "speak";
        }
        return bbb === "waiting" ? "coffee" : "idle";
    }

    function render() {
        const pose = flash || basePose();
        for (const tux of document.querySelectorAll(PAGE_TUX)) {
            tux.dataset.rlqTux = pose;
        }
    }

    // Shows `pose` for `duration` ms, then the pose of the page again.
    function showFor(pose, duration) {
        flash = pose;
        clearTimeout(flashTimer);
        render();
        flashTimer = setTimeout(() => {
            flash = null;
            render();
        }, duration);
    }

    // A wave of `duration` ms, skipped while the animations are paused.
    function waveFor(pose, duration) {
        if (!paused && document.querySelector(PAGE_TUX)) {
            showFor(pose, duration);
        }
    }

    // Waves once per tab, on a page whose Tux is awake.
    function greetOnce() {
        if (paused || !document.querySelector(PAGE_TUX)) {
            return;
        }
        if (!["idle", "speak"].includes(basePose())) {
            return;
        }
        try {
            if (sessionStorage.getItem(GREETED_KEY)) {
                return;
            }
            sessionStorage.setItem(GREETED_KEY, "1");
        } catch {
            // Storage refused: the wave comes on every page.
        }
        showFor("greeting", GREETING_MS);
    }

    function setupRibbons() {
        for (const button of document.querySelectorAll(".o_rlq_marquee_toggle")) {
            const band = button.closest(".o_rlq_band");
            button.addEventListener("click", () => {
                const pausedNow = button.getAttribute("aria-pressed") !== "true";
                button.setAttribute("aria-pressed", pausedNow ? "true" : "false");
                if (band) {
                    band.classList.toggle("o_rlq_marquee_paused", pausedNow);
                }
            });
        }
    }

    // ---- Tux cameos --------------------------------------------------------
    // A stage holding a copy of the vector Tux in the pose of `action`, or
    // an empty string without the drawing.
    function renderCameo(action) {
        const source = document.querySelector("template.o_rlq_tux_source");
        const drawing = source && source.content.querySelector("svg.o_rlq_tux");
        if (!drawing) {
            return "";
        }
        const tux = drawing.cloneNode(true);
        tux.dataset.rlqTux = ACTION_POSES[action] || "idle";
        const stage = document.createElement("div");
        stage.className = `o_rlq_cameo_stage o_rlq_cameo_${action}`;
        stage.appendChild(tux);
        return stage;
    }

    function setupCameos() {
        const engine = window.ewpCameo;
        if (!engine || !document.querySelector("template.o_rlq_tux_source")) {
            return;
        }
        engine.configure(CAMEO_SIZE);
        engine.register({name: "rlq-tux", actions: IDLE_ACTIONS, render: renderCameo});
        engine.register({
            name: "rlq-tux-moments",
            actions: MOMENT_ACTIONS,
            weight: MOMENT_WEIGHT,
            render: renderCameo,
        });
    }

    // Tux falls asleep near the closed page once the day is over, after
    // the delay the engine gives its own page events.
    function playSleep() {
        const engine = window.ewpCameo;
        if (!engine) {
            return;
        }
        setTimeout(() => engine.play("sleep", {near: ".o_ewp_closed"}), engine.state().options.eventDelay);
    }

    document.addEventListener("ewp:day-state", (ev) => {
        dayState = ev.detail.state;
        render();
        if (dayState === "after") {
            playSleep();
        }
    });
    document.addEventListener("ewp:bbb-state", (ev) => {
        bbb = ev.detail.state || "";
        bbbLive = "live" in ev.detail ? Boolean(ev.detail.live) : bbb === "running";
        render();
        if (bbb === "left") {
            waveFor("wave", WAVE_MS);
        }
    });
    document.addEventListener("ewp:motion", (ev) => {
        paused = Boolean(ev.detail.paused);
        if (paused && ["greeting", "wave"].includes(flash)) {
            clearTimeout(flashTimer);
            flash = null;
            render();
        }
    });
    document.addEventListener("ewp:raffle-drawn", () => {
        showFor("celebrate", CELEBRATE_MS);
    });
    // ewp:ready comes before the initial ewp:day-state, ewp:motion and
    // ewp:bbb-state of the same start: the waves wait for them.
    document.addEventListener("ewp:ready", (ev) => {
        dayState = ev.detail.dayState || "none";
        page = ev.detail.page || document.body.dataset.ewpPage || "";
        paused = Boolean(ev.detail.motionPaused);
        setTimeout(() => {
            if (page === "bbb_left") {
                waveFor("wave", WAVE_MS);
            } else {
                greetOnce();
            }
        }, 0);
    });

    function start() {
        setupRibbons();
        setupCameos();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
