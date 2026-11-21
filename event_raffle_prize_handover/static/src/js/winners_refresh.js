/** @odoo-module **/
// Copyright 2026 TechnoLibre - Mathieu Benoit
// License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * Refresh of the public winners page, in place.
 *
 * Every `data-refresh-seconds`, the widget reads the JSON data of the page
 * (`data-url`) and rebuilds the list with the markup of the QWeb template
 * winners_item, text through textContent only. The winners listed before
 * are read from the list itself, by their `data-winner`. Focus stays: a
 * focused sponsor link is found again by its `data-focus-key` and focused
 * back. The number of winners not shown before is announced in the polite
 * live region; the time of the update replaces the previous one. The page
 * reloads itself without JavaScript (meta refresh in a noscript). The
 * prize line carries the status of the prize in `data-status`. The
 * event `o-raffle-winners-refresh` on the root element refreshes at once.
 * Translated labels come in data attributes.
 */
publicWidget.registry.RaffleWinnersRefresh = publicWidget.Widget.extend({
    selector: ".o_raffle_winners",

    start() {
        this.list = this.el.querySelector(".o_raffle_winners_list");
        this.live = this.el.querySelector(".o_raffle_winners_live");
        this.updated = this.el.querySelector(".o_raffle_winners_updated time");
        this.onRefresh = () => this.refresh();
        this.el.addEventListener("o-raffle-winners-refresh", this.onRefresh);
        const seconds = parseInt(this.el.dataset.refreshSeconds, 10);
        if (this.list && seconds > 0) {
            this.timer = setInterval(this.onRefresh, seconds * 1000);
        }
        // Tells a script, such as a test, that the refresh event is heard.
        this.el.dataset.refreshReady = "1";
        return this._super(...arguments);
    },

    destroy() {
        clearInterval(this.timer);
        this.el.removeEventListener("o-raffle-winners-refresh", this.onRefresh);
        this._super(...arguments);
    },

    async refresh() {
        let data = null;
        try {
            const response = await fetch(this.el.dataset.url, {
                headers: {Accept: "application/json"},
                credentials: "same-origin",
                cache: "no-store",
            });
            if (response.ok) {
                data = await response.json();
            }
        } catch {
            data = null;
        }
        if (data && Array.isArray(data.groups)) {
            this.render(data);
        }
        this.el.dispatchEvent(new CustomEvent("o-raffle-winners-refreshed"));
    },

    render(data) {
        const known = new Set(
            [...this.list.querySelectorAll("[data-winner]")].map((li) => li.dataset.winner)
        );
        const active = document.activeElement;
        const focusKey =
            active && this.list.contains(active) ? active.dataset.focusKey : null;
        const ids = [];
        const nodes = data.groups.map((group, index) => {
            group.winners.forEach((winner) => ids.push(String(winner.id)));
            return this.buildGroup(group, index);
        });
        if (!nodes.length) {
            nodes.push(this.make("p", "o_raffle_winners_empty", this.el.dataset.labelEmpty));
        }
        this.list.replaceChildren(...nodes);
        if (focusKey) {
            const again = this.list.querySelector(
                `[data-focus-key="${CSS.escape(focusKey)}"]`
            );
            if (again) {
                again.focus();
            }
        }
        if (this.updated) {
            this.updated.textContent = data.updated_label;
            this.updated.setAttribute("datetime", data.updated);
        }
        const fresh = ids.filter((id) => !known.has(id)).length;
        if (fresh > 0 && this.live) {
            const labels = this.el.dataset;
            this.live.textContent =
                fresh === 1 ? labels.labelNewOne : labels.labelNewMany.replace("%s", fresh);
        }
    },

    make(tag, className, text) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (text !== undefined) {
            node.textContent = text;
        }
        return node;
    },

    buildGroup(group, index) {
        const section = this.make("section", "o_raffle_winners_group mb-4");
        const headingId = `o_raffle_winners_hour_${index}`;
        section.setAttribute("aria-labelledby", headingId);
        const heading = this.make("h2", "h4");
        heading.id = headingId;
        const time = this.make("time", "", group.label);
        time.setAttribute("datetime", group.key);
        heading.append(time);
        const list = this.make("ul", "list-unstyled row g-3");
        list.append(...group.winners.map((winner) => this.buildWinner(winner)));
        section.append(heading, list);
        return section;
    },

    buildWinner(winner) {
        const labels = this.el.dataset;
        const item = this.make("li", "o_raffle_winner col-12 col-md-6 col-lg-4");
        item.dataset.winner = String(winner.id);
        const card = this.make("div", "card h-100");
        const body = this.make("div", "card-body");
        const prize = this.make("p", "o_raffle_winner_prize mb-1", winner.prize);
        prize.dataset.status = winner.status;
        body.append(this.make("p", "o_raffle_winner_name h5 mb-1", winner.name), prize);
        if (winner.sponsor) {
            const sponsor = this.make("p", "o_raffle_winner_sponsor small mb-1");
            sponsor.append(`${labels.labelOffered} `);
            if (winner.sponsor_url) {
                const link = this.make("a", "", winner.sponsor);
                link.href = winner.sponsor_url;
                link.target = "_blank";
                link.rel = "noopener noreferrer";
                link.dataset.focusKey = `sponsor-${winner.id}`;
                link.append(this.make("span", "visually-hidden", ` ${labels.labelNewTab}`));
                sponsor.append(link);
            } else {
                sponsor.append(winner.sponsor);
            }
            body.append(sponsor);
        }
        if (winner.category) {
            body.append(
                this.make(
                    "p",
                    "o_raffle_winner_category small mb-0",
                    `${labels.labelCategory} ${winner.category}`
                )
            );
        }
        card.append(body);
        item.append(card);
        return item;
    },
});

export default publicWidget.registry.RaffleWinnersRefresh;
