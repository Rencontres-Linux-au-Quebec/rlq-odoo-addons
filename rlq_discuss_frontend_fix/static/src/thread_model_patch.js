/** @odoo-module **/
// Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
// Copyright (C) 2026 Rencontres Linux au Québec contributors
// GNU Affero General Public License v3 or later (http://www.gnu.org/licenses/agpl)
//
// Odoo 18: _handleNotificationChannelDelete() (mail/static/src/discuss/core/common/discuss_core_common_service.js) calls
// thread.closeChatWindow(), defined only in mail/static/src/core/web/thread_model_patch.js, which is part of the back-office
// bundle. The website (im_livechat.assets_embed_core inside web.assets_frontend) and the public pages (mail.assets_public)
// load the handler without the function: "TypeError: thread.closeChatWindow is not a function" on every "discuss.channel/delete"
// notification. This file is loaded only in those two bundles, never in web.assets_backend.

import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    closeChatWindow() {
        // A future Odoo that defines it in a common file keeps its own behaviour.
        if (typeof super.closeChatWindow === "function") {
            return super.closeChatWindow(...arguments);
        }
        // Same body as Odoo's back-office version (core/web/thread_model_patch.js).
        const chatWindow = this.store.ChatWindow?.get({ thread: this });
        chatWindow?.close({ notifyState: false });
    },
});
