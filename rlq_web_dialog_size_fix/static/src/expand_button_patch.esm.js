// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
//
// OCA web_dialog_size 18.0 (static/src/js/web_dialog_size.esm.js): ExpandButton.setup() sends
// ir.config_parameter.get_web_dialog_size_config at once and stores the promise in this.config, but attaches its .catch()
// only in onMounted(). With an expired session the RPC fails before the dialog is mounted: the rejection is unhandled,
// rpcErrorHandler opens SessionExpiredDialog, whose header holds an ExpandButton, which sends the RPC again... (2026-11-20:
// hundreds of requests within one second, until nginx answered 429). Handling the rejection right after setup() breaks the loop.

import {ExpandButton} from "@web_dialog_size/js/web_dialog_size.esm";
import {patch} from "@web/core/utils/patch";

patch(ExpandButton.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.config && typeof this.config.catch === "function") {
            // Same tick as the RPC: the rejection is never "unhandled". onMounted() still uses this.config as before.
            this.config.catch(() => {});
        }
    },
});
