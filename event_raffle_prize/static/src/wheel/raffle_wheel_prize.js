/** @odoo-module **/

import {useState} from "@odoo/owl";
import {patch} from "@web/core/utils/patch";
import {RaffleWheel} from "@event_raffle/wheel/raffle_wheel";

// Token category and closing flag of the next draw, next to the prize input.
// They are stored on the raffle (prize_band_id, prize_closing_draw), which
// action_draw_next() copies on the draw it creates: the spin waits for the
// pending write, so the draw always gets what the toolbar shows.
patch(RaffleWheel.prototype, {
    setup() {
        super.setup(...arguments);
        this.prizeState = useState({bands: [], bandId: false, closing: false});
        this._prizeWrite = Promise.resolve();
        this._prizePending = 0;
    },

    async reload() {
        await super.reload(...arguments);
        const data = this.data;
        // A reload that read the raffle before a pending write lands would
        // put the old value back in the toolbar: keep what the user chose.
        if (!data || this.isUnmounted || this._prizePending) {
            return;
        }
        this.prizeState.bands = data.prize_bands || [];
        this.prizeState.bandId = data.prize_band_id || false;
        this.prizeState.closing = !!data.prize_closing_draw;
    },

    _writePrizeOptions(values) {
        const raffleId = this.raffleId;
        this._prizePending += 1;
        const write = this._prizeWrite
            .then(() => this.orm.write("event.raffle", [raffleId], values))
            .finally(() => {
                this._prizePending -= 1;
            });
        // The chain itself never rejects: a failed write shows its error
        // through the returned promise and reloads what the raffle holds,
        // so the toolbar never shows a category the next draw would not get.
        this._prizeWrite = write.catch(() => this.reload());
        return write;
    },

    onPrizeBandChange(ev) {
        const bandId = parseInt(ev.target.value, 10) || false;
        this.prizeState.bandId = bandId;
        return this._writePrizeOptions({prize_band_id: bandId});
    },

    onClosingDrawChange(ev) {
        const closing = ev.target.checked;
        this.prizeState.closing = closing;
        return this._writePrizeOptions({prize_closing_draw: closing});
    },

    async spin() {
        await this._prizeWrite;
        return super.spin(...arguments);
    },
});
