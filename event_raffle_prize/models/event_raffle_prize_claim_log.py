# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models

CLAIM_LOG_KIND_SELECTION = [
    ("declined", "Declined"),
    ("expired", "Expired"),
]


class EventRafflePrizeClaimLog(models.Model):
    """A claim of a draw that ended without a prize: declined or expired.

    The draw keeps its current claim state only; a draw that declines,
    then claims again, keeps the earlier decline here. One line is written
    by event.raffle.draw.write() each time the claim state of a draw
    changes to declined or expired, with sudo: the access rights grant
    read only, so no line names a decline or an expiry that did not
    happen. The line names the prize the claim held or the winner had put
    in the cart, or no prize when none was chosen.

    A line outlives its draw: deleting the draw empties `draw_id` and
    keeps the line. The line therefore stores, when it is written, what
    the sponsor report reads of the draw: its name, date and token
    category, its raffle, the raffle's event and the company of the
    raffle, else of the event. Each of those links is emptied when its
    record is deleted, and the line stays: once its event is gone, it
    counts for its prize with no event.
    """

    _name = "event.raffle.prize.claim.log"
    _description = "Raffle Prize Claim Log"
    _order = "date desc, id desc"
    _rec_name = "draw_name"

    draw_id = fields.Many2one(
        "event.raffle.draw",
        string="Draw",
        ondelete="set null",
        index=True,
        readonly=True,
        help="Empty once the draw is deleted: the line stays.",
    )
    draw_name = fields.Char(
        string="Winning Draw",
        readonly=True,
        help="Name of the draw when the line was written, its number and "
        "its winner.",
    )
    draw_date = fields.Datetime(
        string="Draw Date",
        readonly=True,
        help="Date of the draw, which dates the line in the sponsor report.",
    )
    raffle_id = fields.Many2one(
        "event.raffle",
        string="Raffle",
        ondelete="set null",
        index=True,
        readonly=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string="Event",
        ondelete="set null",
        index=True,
        readonly=True,
    )
    band_id = fields.Many2one(
        "event.raffle.prize.band",
        string="Token Category",
        ondelete="set null",
        readonly=True,
        help="Token category of the draw when the line was written.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        ondelete="set null",
        readonly=True,
        help="Company of the raffle, else of the event.",
    )
    kind = fields.Selection(
        CLAIM_LOG_KIND_SELECTION,
        string="End",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Prize",
        ondelete="restrict",
        readonly=True,
        help="Prize the claim held, else the prize of the winner's last "
        "cart. Empty when the winner chose no prize.",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Order",
        ondelete="set null",
        readonly=True,
        help="Prize order or cart that held the prize.",
    )
    comment = fields.Text(string="Reason", readonly=True)
    date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="By",
        ondelete="set null",
        readonly=True,
    )
