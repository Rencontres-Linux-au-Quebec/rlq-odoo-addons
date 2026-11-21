// @odoo-module ignore
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
//
// Raffle prize blocks of the event web app home page, a plain script of the
// bundle event_webapp_plan.assets_webapp, loaded after webapp.js.
//
// - "My prize": the box carrying data-ewp-prize-url (#ewp_prize_box, empty
//   and hidden while the user won nothing) asks that JSON route every
//   minute while the tab is visible, when the tab shows again, two seconds
//   after webapp.js sends ewp:raffle-drawn (a draw got a winner, maybe
//   this user), and at the deadline of an open prize link
//   (data-ewp-prize-deadline), so the button "Choose my prize" goes away
//   with the link. A new signature replaces the content of the box with
//   the HTML of the answer (the card, already escaped and translated) and
//   shows or hides the box from its count, unless the focus is inside the
//   box: the answer then waits until the focus leaves it. Each item whose state is new is said in the shared
//   live region (ewp:announce of webapp.js) with its data-ewp-prize-say;
//   the focus never moves. Polling stops for good on a 403, a 404 or a
//   redirect (day closed, session expired).
// - Forms (form[data-ewp-prize-form]: the public name, "I am on site"):
//   posted with fetch and an Accept header for JSON, with the value of the
//   button that sent them. The answer replaces the card, or the body of
//   the "On site" block, the
//   focus goes back to the same field or button, and its message is said
//   in the live region. Without fetch, or on an answer that is not JSON,
//   the form is posted as is and the server redirects back to the page.
(function () {
    "use strict";

    const REFRESH_MS = 60000;
    const DRAWN_DELAY_MS = 2000;
    const DEADLINE_MARGIN_MS = 1500;
    const MAX_TIMEOUT_MS = 2147483647;

    function say(text) {
        if (text) {
            document.dispatchEvent(new CustomEvent("ewp:announce", {bubbles: true, detail: {text}}));
        }
    }

    function readStates(body) {
        const states = new Map();
        for (const item of body.querySelectorAll("[data-ewp-prize-draw]")) {
            states.set(item.dataset.ewpPrizeDraw, item.dataset.ewpPrizeState);
        }
        return states;
    }

    function setupCard(root) {
        const card = root.querySelector("[data-ewp-prize-url]");
        if (!card) {
            return null;
        }
        const body = card;
        let signature = card.dataset.ewpSignature || "";
        let states = readStates(body);
        let pending = null;
        let stopped = false;
        let deadlineTimer = null;

        function focusInside() {
            const active = document.activeElement;
            return Boolean(active && active !== document.body && card.contains(active));
        }

        function scheduleDeadline() {
            clearTimeout(deadlineTimer);
            const now = Date.now();
            const moments = [...body.querySelectorAll("[data-ewp-prize-deadline]")]
                .map((item) => Date.parse(item.dataset.ewpPrizeDeadline))
                .filter((moment) => !Number.isNaN(moment) && moment > now);
            if (moments.length) {
                const delay = Math.min(Math.min(...moments) - now + DEADLINE_MARGIN_MS, MAX_TIMEOUT_MS);
                deadlineTimer = setTimeout(refresh, delay);
            }
        }

        // Writes the answer `data` ({signature, count, html}) in the card
        // and says the items whose state is new, unless `quiet`.
        function apply(data, quiet = false) {
            pending = null;
            body.innerHTML = data.html || "";
            signature = data.signature || "";
            card.dataset.ewpSignature = signature;
            card.hidden = !data.count;
            const before = states;
            states = readStates(body);
            if (!quiet) {
                for (const item of body.querySelectorAll("[data-ewp-prize-draw]")) {
                    if (before.get(item.dataset.ewpPrizeDraw) !== item.dataset.ewpPrizeState) {
                        say(item.dataset.ewpPrizeSay);
                    }
                }
            }
            scheduleDeadline();
        }

        function offer(data) {
            if (!data || data.signature === signature) {
                pending = null;
                return;
            }
            if (focusInside()) {
                pending = data;
                return;
            }
            apply(data);
        }

        async function refresh() {
            if (stopped || document.hidden || !window.fetch) {
                return;
            }
            let response = null;
            try {
                response = await fetch(card.dataset.ewpPrizeUrl, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                    redirect: "manual",
                });
            } catch {
                return;
            }
            if (response.type === "opaqueredirect" || response.status === 403 || response.status === 404) {
                stopped = true;
                return;
            }
            if (!response.ok) {
                return;
            }
            try {
                offer(await response.json());
            } catch {
                // An answer that is not JSON changes nothing.
            }
        }

        card.addEventListener("focusout", () => {
            setTimeout(() => {
                if (pending && !focusInside()) {
                    apply(pending);
                }
            }, 0);
        });
        document.addEventListener("ewp:raffle-drawn", () => setTimeout(refresh, DRAWN_DELAY_MS));
        document.addEventListener("visibilitychange", () => {
            if (!document.hidden) {
                refresh();
            }
        });
        setInterval(refresh, REFRESH_MS);
        scheduleDeadline();
        return {apply};
    }

    function setupForms(root, prizeCard) {
        root.addEventListener("submit", async (ev) => {
            const form = ev.target.closest && ev.target.closest("form[data-ewp-prize-form]");
            if (!form || !window.fetch || !window.FormData) {
                return;
            }
            ev.preventDefault();
            const submitter = ev.submitter || null;
            const data = new FormData(form);
            if (submitter && submitter.name) {
                data.set(submitter.name, submitter.value);
            }
            const focusId = (document.activeElement && document.activeElement.id) || (submitter && submitter.id) || "";
            const fallback = () => {
                if (submitter && submitter.name) {
                    const input = document.createElement("input");
                    input.type = "hidden";
                    input.name = submitter.name;
                    input.value = submitter.value;
                    form.appendChild(input);
                }
                HTMLFormElement.prototype.submit.call(form);
            };
            let answer = null;
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: data,
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                answer = response.ok ? await response.json() : null;
            } catch {
                answer = null;
            }
            if (!answer) {
                fallback();
                return;
            }
            if (form.dataset.ewpPrizeForm === "prize" && prizeCard) {
                prizeCard.apply(answer, true);
            } else {
                const body = form.closest(".ewp_presence_body");
                if (body) {
                    body.innerHTML = answer.html || "";
                }
            }
            // The field or the button by its id; else, in the card, its
            // heading (tabindex="-1"), so the focus never falls on <body>.
            const target =
                (focusId && document.getElementById(focusId)) ||
                (form.dataset.ewpPrizeForm === "prize" && document.getElementById("ewp_prize_h_card"));
            if (target) {
                target.focus();
            }
            say(answer.message);
        });
    }

    function start() {
        const root = document.body;
        if (!root || !root.classList.contains("o_ewp_webapp")) {
            return;
        }
        setupForms(root, setupCard(root));
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
