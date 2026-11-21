# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.tools import SQL


class ProductProduct(models.Model):
    """Prize inventory figures on the product variants.

    Each prize claim holds one unit: a reserved claim has its delivery
    reserved, a delivered claim has it done. The free quantity is the stock
    of the company's default warehouse that no move has reserved yet.

    The free quantity is not stored, since every stock move changes it. Its
    SQL form (_field_to_sql) lets the list groups and the pivot sum it, as
    they sum the initial quantity read from the template.
    """

    _inherit = "product.product"

    raffle_claim_ids = fields.One2many(
        "event.raffle.draw",
        "prize_product_id",
        string="Prize Claims",
    )
    raffle_qty_reserved = fields.Float(
        string="Reserved",
        compute="_compute_raffle_qty_claims",
        store=True,
        digits="Product Unit of Measure",
        help="Units held by a prize claim that is not handed over yet.",
    )
    raffle_qty_delivered = fields.Float(
        string="Delivered",
        compute="_compute_raffle_qty_claims",
        store=True,
        digits="Product Unit of Measure",
        help="Units handed over to a winner.",
    )
    raffle_qty_free = fields.Float(
        string="Remaining",
        compute="_compute_raffle_qty_free",
        digits="Product Unit of Measure",
        help="Units in stock at the default warehouse that no claim or "
        "other move has reserved: what can still be given.",
    )

    @api.depends("raffle_claim_ids.claim_state")
    def _compute_raffle_qty_claims(self):
        for product in self:
            states = product.raffle_claim_ids.mapped("claim_state")
            product.raffle_qty_reserved = states.count("reserved")
            product.raffle_qty_delivered = states.count("delivered")

    def _compute_raffle_qty_free(self):
        warehouse = self.env["event.raffle"]._prize_warehouse(self.env.company)
        # sudo: stock quants are restricted to the inventory users, and an
        # event user reads this figure in the prize choice and inventory.
        products = self.sudo().with_context(warehouse_id=warehouse.id)
        for product, product_sudo in zip(self, products, strict=True):
            product.raffle_qty_free = (
                product_sudo.free_qty if warehouse else 0.0
            )

    def _raffle_prize_lock_rows(self):
        """Lock the rows of these products, in ascending id order.

        Every claim and every confirmation of an order that holds a
        sponsored prize goes through this lock, so a claim and a member
        purchase of the last unit run one after the other. The rows are
        also updated in place, which turns a waiter's stale snapshot into
        a serialization error that the RPC layer retries (see
        event.raffle.draw._prize_lock()).
        """
        if not self:
            return
        ids = tuple(sorted(set(self.ids)))
        cr = self.env.cr
        cr.execute(
            "SELECT id FROM product_product WHERE id IN %s ORDER BY id "
            "FOR UPDATE",
            (ids,),
        )
        cr.execute(
            "UPDATE product_product SET write_date = write_date "
            "WHERE id IN %s",
            (ids,),
        )

    def _field_to_sql(self, alias, fname, query=None, flush=True):
        """SQL of raffle_qty_free, the free quantity at the warehouse.

        Sums the quantity minus the reserved quantity of the product's
        quants in the locations under the warehouse's view location, as
        free_qty does with a warehouse in context.
        """
        if fname != "raffle_qty_free":
            return super()._field_to_sql(alias, fname, query, flush)
        warehouse = self.env["event.raffle"]._prize_warehouse(self.env.company)
        if not warehouse:
            return SQL("0.0")
        sql = SQL(
            "(SELECT COALESCE(SUM(quant.quantity - quant.reserved_quantity), 0)"
            " FROM stock_quant quant"
            " JOIN stock_location location ON location.id = quant.location_id"
            " WHERE quant.product_id = %s AND location.parent_path LIKE %s)",
            SQL.identifier(alias, "id"),
            # sudo: see _compute_raffle_qty_free().
            warehouse.sudo().view_location_id.parent_path + "%",
        )
        if flush:
            # Each wrapper names one field that the query flushes first.
            quant_fields = self.env["stock.quant"]._fields
            location_fields = self.env["stock.location"]._fields
            for field in (
                quant_fields["product_id"],
                quant_fields["location_id"],
                quant_fields["quantity"],
                quant_fields["reserved_quantity"],
                location_fields["parent_path"],
            ):
                sql = SQL("%s", sql, to_flush=field)
        return sql
