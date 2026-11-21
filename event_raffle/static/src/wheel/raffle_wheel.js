/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    onWillUpdateProps,
    useRef,
    useState,
} from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { browser } from "@web/core/browser/browser";
import { standardActionServiceProps }
    from "@web/webclient/actions/action_service";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { RaffleScene } from "@event_raffle/wheel/three_scene";

export class RaffleWheel extends Component {
    static template = "event_raffle.RaffleWheel";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.canvasRef = useRef("canvas");
        this.state = useState({
            eligibleCount: 0,
            canDrawNext: true,
            spinning: false,
            winner: false,
            drawCount: 0,
            prize: "",
            theme: "light",
            history: [],
            expandedId: false,
            historyCollapsed: true,
            terminal: [],
        });
        this.scene = null;
        this.data = null;
        this.isUnmounted = false;
        this._loadedId = null;
        this._reloadTimer = null;
        this._sig = null;
        // fullscreen client action carries `action`; the embedded widget a
        // `record`. Used to show the "exit fullscreen" button.
        this.isFullscreen = !!(this.props.action && this.props.action.params);
        // Tooltip of the spin button while too few participants are left.
        this.noDrawLeftTitle = _t("Not enough participants left for a draw");

        onWillStart(async () => {
            await loadBundle("event_raffle.assets_three");
        });
        onMounted(async () => {
            this.scene = new RaffleScene(this.canvasRef.el, {});
            // Expose the Tux/wheel height ratio for automated tests.
            if (this.canvasRef.el && this.scene.tuxWheelRatio) {
                this.canvasRef.el.dataset.tuxWheelRatio =
                    this.scene.tuxWheelRatio.toFixed(4);
            }
            await this.reload();
        });
        onWillUnmount(() => {
            this.isUnmounted = true;
            if (this._reloadTimer) browser.clearTimeout(this._reloadTimer);
            if (this.scene) this.scene.dispose();
        });
        onWillUpdateProps((nextProps) => {
            const nextId =
                nextProps.action && nextProps.action.params
                    ? nextProps.action.params.raffle_id
                    : nextProps.record
                    ? nextProps.record.resId
                    : undefined;
            // Not mid-spin: retargeting the scene under a running spin stops
            // the wheel on the wrong name (see reload()).
            if (nextId && nextId !== this._loadedId && !this.state.spinning) {
                this.reload();
            }
        });
        // Embedded widget: reload from the DB whenever the record is saved so
        // newly added eligible participants show up without a manual refresh.
        if (this.props.record) {
            useRecordObserver((record) => {
                // `record.data` is reassigned on every change and after a
                // save; reading it here makes the observer re-fire so the
                // wheel reloads from the DB (idempotent via the signature).
                void record.data;
                void record.resId;
                this._scheduleReload();
            });
        }
    }

    // Debounced reload to coalesce rapid form re-renders.
    _scheduleReload() {
        if (this._reloadTimer) browser.clearTimeout(this._reloadTimer);
        this._reloadTimer = browser.setTimeout(() => {
            if (!this.isUnmounted && !this.state.spinning) {
                this.reload();
            }
        }, 400);
    }

    // Open the wheel as a fullscreen client action (embedded widget only).
    openFullscreen() {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "event_raffle.wheel",
            target: "fullscreen",
            params: { raffle_id: this.raffleId },
        });
    }

    // Leave the fullscreen client action, back to the previous view.
    exitFullscreen() {
        browser.history.back();
    }

    toggleHistoryCollapsed() {
        this.state.historyCollapsed = !this.state.historyCollapsed;
    }

    get raffleId() {
        // fullscreen client action -> props.action.params
        if (this.props.action && this.props.action.params) {
            return this.props.action.params.raffle_id;
        }
        // embedded view widget -> current record
        if (this.props.record) {
            return this.props.record.resId;
        }
        return this.props.raffleId;
    }

    async reload() {
        if (!this.raffleId) {
            // Unsaved record (no resId yet) or no target action param:
            // do not call the ORM with a falsy id, just show empty state.
            this.state.eligibleCount = 0;
            this.state.canDrawNext = false;
            this.state.drawCount = 0;
            this.state.history = [];
            this.data = null;
            this._sig = null;
            return;
        }
        const data = await this.orm.call(
            "event.raffle", "get_wheel_data", [this.raffleId]
        );
        this.data = data;
        this._loadedId = this.raffleId;
        // A spin that started while the call above was in flight has already
        // frozen where it will stop, for the pointer as it stood then. Moving
        // the pointer (or the names) now would leave the wheel resting on one
        // name while the banner announces another. Drop the signature so the
        // reload at the end of spin() applies what is skipped here.
        if (this.state.spinning) {
            this._sig = null;
            return;
        }
        // Skip visible updates when nothing changed (avoids needless redraws
        // when the observer fires on unrelated form edits).
        const sig = JSON.stringify([
            data.eligible.map((p) => p.id),
            data.draw_count,
            data.theme,
            data.can_draw_next,
            data.show_tux,
            data.belly_logo,
            data.pointer_angle,
            (data.history || []).map((h) => [h.id, h.is_absent]),
        ]);
        if (sig === this._sig) {
            return;
        }
        this._sig = sig;
        this.state.theme = data.theme || "light";
        this.state.eligibleCount = data.eligible.length;
        this.state.canDrawNext = data.can_draw_next;
        this.state.drawCount = data.draw_count;
        this.state.history = data.history || [];
        if (this.scene) {
            // Before setTuxVisible/_placeTux: the pointer angle decides how
            // much room Tux needs beside the wheel.
            this.scene.setPointerAngle(data.pointer_angle);
            this.scene.setTuxVisible(data.show_tux);
            this.scene.setBellyLogo(data.belly_logo);
            this.scene.setTheme(data.theme);
            this.scene.setSegments(data.eligible.map((p) => p.name));
        }
        // Linux theme: seed the idle terminal banner (only when not spinning,
        // so a running spin's live transcript is never wiped). Other themes
        // drop the backlog so switching back always starts fresh.
        if (this._isLinux) {
            if (!this.state.spinning) {
                this._termWelcome();
            }
        } else if (this.state.terminal.length) {
            this._termClear();
        }
    }

    toggleHistory(id) {
        this.state.expandedId = this.state.expandedId === id ? false : id;
    }

    _pickAnimation() {
        const pref = (this.data && this.data.tux_animation) || "rotate";
        if (pref !== "rotate") {
            return pref;
        }
        // Cycle through all animations based on how many draws happened.
        const anims = RaffleScene.ANIMATIONS;
        return anims[this.state.drawCount % anims.length];
    }

    _pickCelebration() {
        const pref =
            (this.data && this.data.winner_celebration) || "candles";
        if (pref !== "random") {
            return pref;
        }
        const opts = ["candles", "confetti", "fireworks", "trumpet", "diabolo"];
        return opts[Math.floor(Math.random() * opts.length)];
    }

    _pickFlagLine() {
        const raw =
            (this.data && this.data.flag_text) || "Vive le logiciel libre";
        const lines = raw
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean);
        if (!lines.length) {
            return "Vive le logiciel libre";
        }
        return lines[Math.floor(Math.random() * lines.length)];
    }

    // ---- Linux-theme background terminal ----------------------------------
    // The terminal is a purely cosmetic backdrop shown for both Linux themes
    // (dark and light). It "types" the commands that drive each spin so the
    // projection reads like a live shell session.

    get _isLinux() {
        return (
            this.state.theme === "linux" ||
            this.state.theme === "linux_light"
        );
    }

    // The shell prompt printed instantly in front of every command.
    get _termPS() {
        return "raffle@tux:~$ ";
    }

    _termClear() {
        this.state.terminal = [];
    }

    _termPush(line) {
        this.state.terminal.push(line);
        // Keep the backlog bounded so long sessions do not grow unbounded.
        const max = 40;
        if (this.state.terminal.length > max) {
            this.state.terminal.splice(0, this.state.terminal.length - max);
        }
    }

    // Output line (no shell prompt, not typed).
    _termLine(text, cls) {
        this._termPush({ prompt: "", text, cls: cls || "out" });
    }

    // A completed command line: prompt shown instantly + the command (static).
    _termCmd(command, cls) {
        this._termPush({ prompt: this._termPS, text: command, cls: cls || "cmd" });
    }

    // Idle prompt line ending the transcript (the blinking cursor sits here).
    _termPrompt() {
        this._termPush({ prompt: this._termPS, text: "", cls: "prompt" });
    }

    // A command being typed: the shell prompt appears instantly, then the
    // command is typed character by character after it.
    _termType(command, cls, delay = 22) {
        return new Promise((resolve) => {
            this._termPush({ prompt: this._termPS, text: "", cls: cls || "cmd" });
            // Mutate through the reactive array element (not the raw object we
            // pushed) so each typed character triggers a re-render.
            const line = this.state.terminal[this.state.terminal.length - 1];
            let i = 0;
            const step = () => {
                if (this.isUnmounted) {
                    resolve();
                    return;
                }
                line.text = command.slice(0, (i += 1));
                if (i < command.length) {
                    browser.setTimeout(step, delay);
                } else {
                    resolve();
                }
            };
            browser.setTimeout(step, delay);
        });
    }

    // Idle banner shown when the linux theme first appears (between spins).
    _termWelcome() {
        this._termClear();
        this._termCmd("./raffle --init");
        this._termLine("[ ok ] three.js wheel engine loaded", "ok");
        this._termLine(
            `[ ok ] ${this.state.eligibleCount} participant(s) in the pool`,
            "ok"
        );
        this._termLine("[*] waiting for operator…", "dim");
        this._termPrompt();
    }

    async spin() {
        if (!this.raffleId) return;
        if (this.state.spinning || !this.data) return;
        if (!this.state.canDrawNext) return;
        this.state.spinning = true;
        this.state.winner = false;
        const linux = this._isLinux;
        try {
            // Tux plays an animation, then spins the wheel.
            const anim = this._pickAnimation();
            const opts =
                anim === "flag" ? { flagText: this._pickFlagLine() } : {};
            if (linux) {
                // Tux pulls out a keyboard and types the commands.
                this.scene.startTyping();
                this._termClear();
                await this._termType("clear", "cmd");
                this._termClear();
                await this._termType(
                    `tux_animation --type ${anim}` +
                        (opts.flagText ? ` --flag "${opts.flagText}"` : ""),
                    "cmd"
                );
                await this._termType("run", "cmd");
                this._termLine(`[run] playing '${anim}' choreography…`, "dim");
            } else {
                // Other themes: Tux plays a physical animation.
                await this.scene.playTuxAnimation(anim, opts);
            }
            if (this.isUnmounted) return;
            const res = await this.orm.call(
                "event.raffle", "action_draw_next",
                [this.raffleId, this.state.prize || false]
            );
            if (linux && !this.isUnmounted) {
                // Output the wheel information before spinning.
                await this._termType(
                    `wheel --spin --entries ${res.wheel.length}`,
                    "cmd"
                );
                const names = res.wheel.map((w) => w.name).join(", ");
                this._termLine(`[wheel] ${res.wheel.length} names: ${names}`, "dim");
                if (this.state.prize) {
                    this._termLine(`[wheel] prize: ${this.state.prize}`, "dim");
                }
                this._termLine("[wheel] spinning… ▀▄▀▄▀▄", "out");
                // put the keyboard away; Tux watches the wheel spin.
                this.scene.stopTyping();
            }
            this.scene.setSegments(res.wheel.map((p) => p.name));
            await this.scene.spinTo(res.winner_index, res.wheel.length, {
                durationS: this.data.spin_duration,
                turns: this.data.spin_turns,
            });
            if (this.isUnmounted) return;
            this.state.winner = res.winner.name;
            if (linux) {
                // Output the winner.
                this._termLine(`>>> WINNER: ${res.winner.name}`, "win");
                this._termCmd(`echo "🎉 ${res.winner.name}" | festival`);
                this._termPrompt();
            }
            if (this.data.show_fireworks) this.scene.fireworks();
            // Tux plays the configured winner celebration.
            await this.scene.celebrate(this._pickCelebration());
        } finally {
            if (this.scene) this.scene.stopTyping();
            if (!this.isUnmounted) {
                this.state.spinning = false;
                await this.reload();
            }
        }
    }
}

// Fullscreen client action
export class RaffleWheelAction extends RaffleWheel {
    static props = { ...standardActionServiceProps };
}
registry.category("actions").add("event_raffle.wheel", RaffleWheelAction);

// Embedded form view widget
export const raffleWheelWidget = {
    component: RaffleWheel,
    extractProps: () => ({}),
};
RaffleWheel.props = { ...standardWidgetProps, "*": true };
registry.category("view_widgets").add("raffle_wheel", raffleWheelWidget);
