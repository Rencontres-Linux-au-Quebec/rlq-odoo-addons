# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Window of the sponsored prizes in the shop, in the raffle settings.

    Both fields are related to the raffle default-settings singleton, which
    keeps them (see event.raffle.config._sponsored_shop_is_open()), and
    event_raffle writes them with the other raffle defaults on save.
    """

    _inherit = "res.config.settings"

    raffle_sponsored_shop_open = fields.Boolean(
        related="raffle_config_id.sponsored_shop_open", readonly=False
    )
    raffle_sponsored_shop_close_date = fields.Datetime(
        related="raffle_config_id.sponsored_shop_close_date", readonly=False
    )
