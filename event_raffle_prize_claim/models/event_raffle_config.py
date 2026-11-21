# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class EventRaffleConfig(models.Model):
    """Window during which the website shop lists the sponsored prizes.

    The window is open while the switch is on and the close date, when
    set, is still ahead. Open, every visitor sees the published sponsored
    prizes: members buy those sold to them, and the others read as prizes
    only. Closed, the sponsored prizes are left out for everyone but a
    winner with an open prize link.
    """

    _inherit = "event.raffle.config"

    sponsored_shop_open = fields.Boolean(
        string="Sponsored prizes in the shop",
        default=True,
        help="Lists the published sponsored prizes in the website shop to "
        "every visitor. Unticked, only the winners' prize links show them.",
    )
    sponsored_shop_close_date = fields.Datetime(
        string="Close sales on",
        help="From this time on, the shop leaves the sponsored prizes out "
        "as if the switch were off. Empty keeps them listed while the "
        "switch is on.",
    )

    @api.model
    def _sponsored_shop_is_open(self):
        """Whether the shop lists the sponsored prizes to every visitor."""
        # sudo: website visitors do not read the raffle settings.
        config = self.env.ref(
            "event_raffle.raffle_config_singleton", raise_if_not_found=False
        )
        if not config:
            return False
        config = config.sudo()
        if not config.sponsored_shop_open:
            return False
        close = config.sponsored_shop_close_date
        return not close or fields.Datetime.now() < close
