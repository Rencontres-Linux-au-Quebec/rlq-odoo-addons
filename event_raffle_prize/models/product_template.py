# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ATTENDANCE_SELECTION = [
    ("onsite", "On site"),
    ("virtual", "Virtual"),
    ("both", "On site and virtual"),
]


class ProductTemplate(models.Model):
    """Sponsored prize catalogue on the products.

    A sponsored prize (technical name `is_raffle_prize`) is a storable
    good: its stock is what the prize claims reserve and deliver, and what
    the member purchases take when the prize is also sold. Its sales price
    is the value of the prize, which places it in a token category and
    stays on the claim for the sponsor reports.
    """

    _inherit = "product.template"

    is_raffle_prize = fields.Boolean(
        string="Sponsored Prize",
        help="This product can be given to the winner of a raffle draw, "
        "for one token of its category.",
    )
    raffle_member_sale_ok = fields.Boolean(
        string="Sold to members",
        help="Besides the winners' tokens, members may buy this prize at "
        "its sales price. The purchases share the stock with the claims "
        "and never count toward a raffle quota.",
    )
    raffle_sponsor_id = fields.Many2one(
        "res.partner",
        string="Sponsor",
        help="Contact that gave this prize.",
    )
    raffle_sponsor_website = fields.Char(
        string="Sponsor Website",
        related="raffle_sponsor_id.website",
    )
    raffle_band_id = fields.Many2one(
        "event.raffle.prize.band",
        string="Token Category",
        compute="_compute_raffle_band_id",
        store=True,
        readonly=False,
        help="A winner takes this prize for one token of this category. Set "
        "from the sales price when it changes, and editable by hand "
        "afterwards.",
    )
    raffle_attendance = fields.Selection(
        ATTENDANCE_SELECTION,
        string="Winner Attendance",
        default="both",
        required=True,
        help="Which winners may take this prize: those checked in at the "
        "event (on site), the others (virtual), or both.",
    )
    raffle_country_ids = fields.Many2many(
        "res.country",
        "product_template_raffle_country_rel",
        "product_tmpl_id",
        "country_id",
        string="Countries",
        help="Virtual winners must live in one of these countries. Empty "
        "means anywhere. On-site winners pick the prize up at the event.",
    )
    raffle_state_ids = fields.Many2many(
        "res.country.state",
        "product_template_raffle_state_rel",
        "product_tmpl_id",
        "state_id",
        string="States",
        help="Virtual winners must live in one of these states. A country "
        "listed under Countries without any of its states listed here "
        "stays open as a whole.",
    )
    raffle_closing_prize = fields.Boolean(
        string="Closing Prize",
        help="Only a closing draw may give this prize.",
    )
    raffle_event_ids = fields.Many2many(
        "event.event",
        "product_template_raffle_event_rel",
        "product_tmpl_id",
        "event_id",
        string="Events",
        help="Raffles of these events only. Empty means any event.",
    )
    raffle_initial_qty = fields.Float(
        string="Initial Quantity",
        digits="Product Unit of Measure",
        help="Quantity the sponsor gave, shown in the prize inventory. The "
        "stock itself comes from the Inventory app.",
    )

    @api.depends("list_price", "is_raffle_prize")
    def _compute_raffle_band_id(self):
        Band = self.env["event.raffle.prize.band"]
        for template in self:
            if template.is_raffle_prize:
                template.raffle_band_id = Band._band_for_value(
                    template.list_price
                )
            else:
                template.raffle_band_id = False

    @api.onchange("is_raffle_prize")
    def _onchange_is_raffle_prize(self):
        if self.is_raffle_prize:
            self.type = "consu"
            self.is_storable = True

    @api.constrains("is_raffle_prize", "type", "is_storable")
    def _check_raffle_prize_storable(self):
        for template in self:
            if template.is_raffle_prize and not (
                template.type == "consu" and template.is_storable
            ):
                raise ValidationError(
                    _(
                        "The sponsored prize %s must be a good that tracks "
                        "its inventory: a claim reserves one unit of its "
                        "stock.",
                        template.display_name,
                    )
                )
