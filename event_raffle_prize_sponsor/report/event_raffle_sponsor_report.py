# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

LINE_TYPE_SELECTION = [
    ("offer", "Offered"),
    ("purchase", "Bought by a member"),
    ("reserved", "Reserved"),
    ("shipped", "Shipped"),
    ("delivered", "Handed over"),
    ("declined", "Declined"),
    ("declined_unchosen", "Declined, no choice"),
    ("expired", "Expired"),
    ("expired_unchosen", "Expired link, no choice"),
]


class EventRaffleSponsorReport(models.Model):
    """What each sponsor offered and what became of it, read only.

    The rows come from a SQL query (_table_query), evaluated at each read,
    over the approved sponsored prizes. A row is one fact, and each measure
    is a sum over the rows:

    - one "offer" row per prize: the offered quantity (raffle_initial_qty),
      its value at the prize's sales price, and the remaining stock, the
      quantity minus the reserved quantity of the prize's quants in the
      internal locations. Done moves have changed the quants and reserved
      moves their reserved quantity, so a partial delivery or reception
      counts what moved only;
    - one row per draw whose claim holds the prize now: reserved,
      shipped or handed over (a virtual prize sent counts as handed over).
      Each one is one unit won; the claim's stored prize value gives the
      value reserved, and the value distributed for a shipped or
      handed-over one;
    - one row per line of the claim log (event.raffle.prize.claim.log):
      each decline and each expiry of a claim, so that a draw that
      declines, then claims again, counts both. The line names the prize
      the claim held or the winner had put in the cart: an expiry counts
      for that prize as the winner's interest, no unit having left. A line
      that names no prize is a "declined_unchosen" or "expired_unchosen"
      row, with no prize and no sponsor, in the token category of its
      draw. A line whose prize is not an approved sponsored prize is left
      out, as the other rows of that prize. The line reads the copies of
      its draw that it stores (date, token category, event, company), so
      it keeps counting once the draw, its raffle or its event is
      deleted: with no event once the event is gone;
    - one "purchase" row per line of a confirmed order (state sale) that a
      member bought the prize with, its quantity in the prize's unit and
      its untaxed amount converted at the order's rate. A cancelled order
      leaves the report.

    The rows of a draw and of its claim log belong to the event of the
    draw's raffle, none for a raffle with no event, and carry the draw's
    date. The offer and purchase rows belong to the prize's event when it
    has exactly one, else to no event, so that a prize of several events
    is counted once. The sponsor is the commercial entity of the prize's
    sponsor, and the amounts are in the currency of the row's company,
    else of the first company: the raffle's, the event's or the prize's
    for a draw or log row; the prize's, else the one company of the
    prize's events, for an offer row; the order's for a purchase row. A
    row's token category is its prize's, else, for a row with no prize,
    its draw's.

    Every row has a date, so that the Date filter keeps the offer next to
    what became of it: the draw's date, the order's date, and for an offer
    row the start of the prize's first event, else the prize's creation.
    """

    _name = "event.raffle.sponsor.report"
    _description = "Sponsor Report"
    _auto = False
    _rec_name = "product_tmpl_id"
    _order = "event_id, sponsor_id, product_tmpl_id, id"
    _depends = {  # noqa: RUF012
        "event.raffle": ["event_id", "company_id"],
        "event.raffle.draw": [
            "raffle_id",
            "band_id",
            "claim_state",
            "prize_product_id",
            "prize_value",
            "date",
        ],
        "event.raffle.prize.claim.log": [
            "kind",
            "product_id",
            "band_id",
            "event_id",
            "company_id",
            "draw_date",
        ],
        "event.event": ["company_id", "date_begin"],
        "product.template": [
            "is_raffle_prize",
            "raffle_sponsor_state",
            "raffle_sponsor_id",
            "raffle_band_id",
            "raffle_initial_qty",
            "raffle_event_ids",
            "list_price",
            "company_id",
            "uom_id",
            "create_date",
        ],
        "product.product": ["product_tmpl_id"],
        "res.partner": ["commercial_partner_id"],
        "sale.order": [
            "state",
            "currency_rate",
            "date_order",
        ],
        "sale.order.line": [
            "order_id",
            "product_id",
            "product_uom",
            "product_uom_qty",
            "price_subtotal",
            "raffle_prize_sale_type",
        ],
        "stock.quant": [
            "product_id",
            "location_id",
            "quantity",
            "reserved_quantity",
        ],
        "stock.location": ["usage"],
        "uom.uom": ["factor"],
    }

    line_type = fields.Selection(
        LINE_TYPE_SELECTION, string="State", readonly=True
    )
    event_id = fields.Many2one("event.event", string="Event", readonly=True)
    sponsor_id = fields.Many2one(
        "res.partner",
        string="Sponsor",
        readonly=True,
        help="Empty on a line of a claim that ended with no prize chosen.",
    )
    product_tmpl_id = fields.Many2one(
        "product.template", string="Prize", readonly=True
    )
    band_id = fields.Many2one(
        "event.raffle.prize.band", string="Token Category", readonly=True
    )
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    date = fields.Datetime(
        readonly=True,
        help="Date of the draw, for its claim and the declines and expiries "
        "of its claim, or of the member order. The offered "
        "quantity and the stock are dated at the start of the prize's first "
        "event, else at the creation of the prize.",
    )
    qty_offered = fields.Float(
        string="Offered",
        digits="Product Unit of Measure",
        readonly=True,
        help="Quantity the sponsor gave (Initial Quantity of the prize).",
    )
    value_offered = fields.Monetary(
        string="Value Offered",
        readonly=True,
        help="Offered quantity times the value of the prize.",
    )
    qty_won = fields.Float(
        string="Won",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units reserved, shipped or handed over to a winner.",
    )
    qty_reserved = fields.Float(
        string="Reserved",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units reserved for a winner, not handed over yet.",
    )
    value_reserved = fields.Monetary(string="Value Reserved", readonly=True)
    qty_shipped = fields.Float(
        string="Shipped",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units shipped to a winner, not received yet.",
    )
    qty_delivered = fields.Float(
        string="Handed Over",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units handed over on site, sent by email (virtual prizes) or "
        "received after shipping.",
    )
    qty_declined = fields.Float(
        string="Declined",
        digits="Product Unit of Measure",
        readonly=True,
        help="Claims declined, after the prize was reserved or through the "
        "prize link, each decline of a draw counted. A reserved unit is "
        "back in stock. A link declined with no prize in the cart counts "
        'on a "Declined, no choice" line, with no prize and no sponsor.',
    )
    qty_expired = fields.Float(
        string="Expired",
        digits="Product Unit of Measure",
        readonly=True,
        help="Prize links that ran out. A link whose cart held this prize "
        "counts for it as the winner's interest: no unit went out and nothing "
        "was spent. A link with no prize in the cart counts on an "
        '"Expired link, no choice" line, with no prize and no sponsor.',
    )
    qty_purchased = fields.Float(
        string="Bought by Members",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units on confirmed member orders.",
    )
    amount_purchased = fields.Monetary(
        string="Member Sales",
        readonly=True,
        help="Untaxed amount of the confirmed member orders.",
    )
    value_distributed = fields.Monetary(
        string="Value Distributed",
        readonly=True,
        help="Value of the units shipped or handed over to a winner.",
    )
    qty_remaining = fields.Float(
        string="Remaining Stock",
        digits="Product Unit of Measure",
        readonly=True,
        help="Units in the internal locations that no move has reserved.",
    )

    @property
    def _table_query(self):
        return SQL("""
WITH prize AS (
    SELECT pt.id AS product_tmpl_id,
           COALESCE(sponsor.commercial_partner_id, sponsor.id) AS sponsor_id,
           pt.raffle_band_id AS band_id,
           pt.company_id AS company_id,
           COALESCE(pt.list_price, 0) AS list_price,
           COALESCE(pt.raffle_initial_qty, 0) AS initial_qty,
           pt.uom_id AS uom_id,
           events.event_id,
           COALESCE(pt.company_id, events.company_id) AS offer_company_id,
           COALESCE(events.date_begin, pt.create_date) AS offer_date
      FROM product_template pt
 LEFT JOIN res_partner sponsor ON sponsor.id = pt.raffle_sponsor_id
 LEFT JOIN LATERAL (
           SELECT CASE WHEN COUNT(*) = 1
                       THEN MIN(rel.event_id) END AS event_id,
                  CASE WHEN COUNT(DISTINCT ev.company_id) = 1
                        AND COUNT(ev.company_id) = COUNT(*)
                       THEN MIN(ev.company_id) END AS company_id,
                  MIN(ev.date_begin) AS date_begin
             FROM product_template_raffle_event_rel rel
             JOIN event_event ev ON ev.id = rel.event_id
            WHERE rel.product_tmpl_id = pt.id
       ) events ON TRUE
     WHERE pt.is_raffle_prize
       AND pt.raffle_sponsor_state = 'approved'
),
fact AS (
    SELECT prize.product_tmpl_id * 4 + 1 AS id,
           'offer' AS line_type,
           NULL::integer AS band_id,
           prize.event_id,
           prize.offer_company_id AS company_id,
           prize.offer_date AS date,
           prize.product_tmpl_id,
           prize.initial_qty AS qty_offered,
           prize.initial_qty * prize.list_price AS value_offered,
           0.0 AS qty_won,
           0.0 AS qty_reserved,
           0.0 AS value_reserved,
           0.0 AS qty_shipped,
           0.0 AS qty_delivered,
           0.0 AS qty_declined,
           0.0 AS qty_expired,
           0.0 AS qty_purchased,
           0.0 AS amount_purchased,
           0.0 AS value_distributed,
           COALESCE((
               SELECT SUM(quant.quantity - quant.reserved_quantity)
                 FROM stock_quant quant
                 JOIN stock_location location
                   ON location.id = quant.location_id
                 JOIN product_product variant
                   ON variant.id = quant.product_id
                WHERE variant.product_tmpl_id = prize.product_tmpl_id
                  AND location.usage = 'internal'
           ), 0.0) AS qty_remaining
      FROM prize
    UNION ALL
    SELECT draw.id * 4 + 2,
           draw.claim_state,
           draw.band_id,
           raffle.event_id,
           COALESCE(raffle.company_id, event.company_id, prize.company_id),
           draw.date,
           prize.product_tmpl_id,
           0.0,
           0.0,
           1.0,
           CASE WHEN draw.claim_state = 'reserved' THEN 1.0 ELSE 0.0 END,
           CASE WHEN draw.claim_state = 'reserved'
                THEN COALESCE(draw.prize_value, 0.0) ELSE 0.0 END,
           CASE WHEN draw.claim_state = 'shipped' THEN 1.0 ELSE 0.0 END,
           CASE WHEN draw.claim_state = 'delivered' THEN 1.0 ELSE 0.0 END,
           0.0,
           0.0,
           0.0,
           0.0,
           CASE WHEN draw.claim_state IN ('shipped', 'delivered')
                THEN COALESCE(draw.prize_value, 0.0) ELSE 0.0 END,
           0.0
      FROM event_raffle_draw draw
      JOIN event_raffle raffle ON raffle.id = draw.raffle_id
 LEFT JOIN event_event event ON event.id = raffle.event_id
      JOIN product_product variant ON variant.id = draw.prize_product_id
      JOIN prize ON prize.product_tmpl_id = variant.product_tmpl_id
     WHERE draw.claim_state IN ('reserved', 'shipped', 'delivered')
    UNION ALL
    SELECT log.id * 4,
           CASE WHEN log.product_id IS NULL
                THEN log.kind || '_unchosen' ELSE log.kind END,
           log.band_id,
           log.event_id,
           COALESCE(log.company_id, prize.company_id),
           log.draw_date,
           prize.product_tmpl_id,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           CASE WHEN log.kind = 'declined' THEN 1.0 ELSE 0.0 END,
           CASE WHEN log.kind = 'expired' THEN 1.0 ELSE 0.0 END,
           0.0,
           0.0,
           0.0,
           0.0
      FROM event_raffle_prize_claim_log log
 LEFT JOIN product_product variant ON variant.id = log.product_id
 LEFT JOIN prize ON prize.product_tmpl_id = variant.product_tmpl_id
     WHERE log.product_id IS NULL OR prize.product_tmpl_id IS NOT NULL
    UNION ALL
    SELECT line.id * 4 + 3,
           'purchase',
           NULL,
           prize.event_id,
           sale.company_id,
           sale.date_order,
           prize.product_tmpl_id,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           0.0,
           line.product_uom_qty / line_uom.factor * prize_uom.factor,
           line.price_subtotal
               / CASE COALESCE(sale.currency_rate, 0.0)
                     WHEN 0.0 THEN 1.0 ELSE sale.currency_rate END,
           0.0,
           0.0
      FROM sale_order_line line
      JOIN sale_order sale ON sale.id = line.order_id
      JOIN product_product variant ON variant.id = line.product_id
      JOIN prize ON prize.product_tmpl_id = variant.product_tmpl_id
      JOIN uom_uom line_uom ON line_uom.id = line.product_uom
      JOIN uom_uom prize_uom ON prize_uom.id = prize.uom_id
     WHERE line.raffle_prize_sale_type = 'purchase'
       AND sale.state = 'sale'
)
SELECT fact.id,
       fact.line_type,
       fact.event_id,
       prize.sponsor_id,
       fact.product_tmpl_id,
       COALESCE(prize.band_id, fact.band_id) AS band_id,
       company.id AS company_id,
       company.currency_id,
       fact.date,
       fact.qty_offered,
       fact.value_offered,
       fact.qty_won,
       fact.qty_reserved,
       fact.value_reserved,
       fact.qty_shipped,
       fact.qty_delivered,
       fact.qty_declined,
       fact.qty_expired,
       fact.qty_purchased,
       fact.amount_purchased,
       fact.value_distributed,
       fact.qty_remaining
  FROM fact
  LEFT JOIN prize ON prize.product_tmpl_id = fact.product_tmpl_id
  JOIN res_company company ON company.id = COALESCE(
           fact.company_id,
           (SELECT first.id FROM res_company first
             ORDER BY first.sequence, first.id LIMIT 1))
""")

    def action_open_raffle_sponsor_thank_wizard(self):
        """Thank the sponsors of the event of the selected lines."""
        events = self.event_id
        if len(events) != 1:
            raise UserError(
                _("Select the lines of one event to thank its sponsors.")
            )
        return events.action_open_raffle_sponsor_thank_wizard()
