# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EventRafflePrizeBand(models.Model):
    """A token category of sponsored prizes, such as "Prize Group B".

    A winner earns one token of the category of their draw: one token is
    one prize link and one prize, and a prize of that category costs
    exactly that token. A prize product falls in the first active
    category, in sequence order, whose [value_min, value_max] range holds
    its sales price. The draw names its category, and only the prizes of
    that category are offered to its winner, during the category's link
    validity.
    """

    _name = "event.raffle.prize.band"
    _description = "Raffle Token Category"
    _order = "sequence, value_min, id"

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)
    value_min = fields.Float(
        string="Minimum Value",
        digits="Product Price",
        help="Lowest sales price of a prize in this token category, "
        "included.",
    )
    value_max = fields.Float(
        string="Maximum Value",
        digits="Product Price",
        help="Highest sales price of a prize in this token category, "
        "included.",
    )
    claim_delay_minutes = fields.Integer(
        string="Link Validity (minutes)",
        default=45,
        required=True,
        help="Minutes during which the prize link of a token of this "
        "category lets its winner choose a prize.",
    )

    _sql_constraints = [  # noqa: RUF012
        (
            "claim_delay_minutes_positive",
            "CHECK(claim_delay_minutes > 0)",
            "A token category's link lasts at least one minute.",
        ),
    ]

    @api.constrains("value_min", "value_max")
    def _check_values(self):
        for band in self:
            if band.value_min > band.value_max:
                raise ValidationError(
                    _(
                        "The minimum value of the token category %s is "
                        "above its maximum value.",
                        band.name,
                    )
                )

    @api.model
    def _band_for_value(self, value):
        """The first active category whose range holds `value`, or none."""
        for band in self.search([]):
            if band.value_min <= value <= band.value_max:
                return band
        return self.browse()

    def _token_label(self):
        """One token of this category, as a winner reads its cost: the
        category name alone, or "1 token" without a category."""
        if not self:
            return _("1 token")
        self.ensure_one()
        return self.name
