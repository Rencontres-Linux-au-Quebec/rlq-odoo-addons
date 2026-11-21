# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from datetime import timedelta

from odoo import fields


class ClaimDataMixin:
    """Prizes, a raffle and winners for the prize link tests.

    The demo prizes and token categories are set aside, so that each list
    holds the test's own prizes only. Every prize is published: the shop
    shows it to the winners it is allowed to, and to every visitor while
    the sponsored shop window is open, as it is at the start of each
    test.
    """

    @classmethod
    def _claim_setup(cls):
        env = cls.env
        env["product.template"].search([("is_raffle_prize", "=", True)]).write(
            {"is_raffle_prize": False, "is_published": False}
        )
        env["event.raffle.prize.band"].search([]).write({"active": False})
        cls._set_shop_window(is_open=True)
        cls.band_a = env["event.raffle.prize.band"].create(
            {
                "name": "Group A",
                "sequence": 1,
                "value_min": 0,
                "value_max": 49.99,
            }
        )
        cls.band_b = env["event.raffle.prize.band"].create(
            {
                "name": "Group B",
                "sequence": 2,
                "value_min": 50,
                "value_max": 999,
            }
        )
        cls.event = env["event.event"].create(
            {
                "name": "Claim Event",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
                "date_tz": "America/Toronto",
            }
        )
        cls.channel = env["discuss.channel"].create(
            {"name": "prize-alerts", "channel_type": "channel"}
        )
        cls.raffle = env["event.raffle"].create(
            {
                "name": "Morning",
                "event_id": cls.event.id,
                "claim_auto_send": False,
                "claim_alert_channel_id": cls.channel.id,
            }
        )
        cls.warehouse = env["event.raffle"]._prize_warehouse(env.company)
        cls.sponsor = env["res.partner"].create(
            {
                "name": "Sponsor Example",
                "is_company": True,
                "website": "https://sponsor.example.org",
            }
        )
        cls.odoobot = env.ref("base.partner_root")

    @classmethod
    def _prize(cls, name, price=20.0, qty=3.0, **vals):
        template = cls.env["product.template"].create(
            dict(
                {
                    "name": name,
                    "type": "consu",
                    "is_storable": True,
                    "list_price": price,
                    "is_raffle_prize": True,
                    "is_published": True,
                    "raffle_sponsor_id": cls.sponsor.id,
                },
                **vals,
            )
        )
        product = template.product_variant_id
        if qty:
            cls.env["stock.quant"]._update_available_quantity(
                product, cls.warehouse.lot_stock_id, qty
            )
        return product

    @classmethod
    def _participant(cls, name, attended=True, email=None, **partner_vals):
        email = email or f"{name.lower()}@example.com"
        partner = cls.env["res.partner"].create(
            dict({"name": name, "email": email}, **partner_vals)
        )
        registration = cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": partner.id,
                "name": name,
                "email": email,
            }
        )
        if attended:
            registration.action_set_done()
        return cls.env["event.raffle.participant"].create(
            {
                "raffle_id": cls.raffle.id,
                "name": name,
                "email": email,
                "partner_id": partner.id,
                "registration_id": registration.id,
                "source": "registration",
            }
        )

    @classmethod
    def _draw(cls, participant, **vals):
        raffle = participant.raffle_id
        return cls.env["event.raffle.draw"].create(
            dict(
                {
                    "raffle_id": raffle.id,
                    "sequence": len(raffle.draw_ids) + 1,
                    "winner_participant_id": participant.id,
                    "winner_name": participant.name,
                    "winner_email": participant.email,
                },
                **vals,
            )
        )

    @classmethod
    def _set_shop_window(cls, is_open=True, close_date=False):
        """Set the sponsored shop window of the raffle settings."""
        cls.env.ref("event_raffle.raffle_config_singleton").write(
            {
                "sponsored_shop_open": is_open,
                "sponsored_shop_close_date": close_date,
            }
        )

    def _expire(self, draw):
        """Move the deadline of the draw's link into the past."""
        draw.sudo().write(
            {"claim_deadline": fields.Datetime.now() - timedelta(minutes=1)}
        )

    def _channel_bodies(self):
        messages = self.channel.message_ids.filtered(
            lambda m: m.author_id == self.odoobot
        )
        return [m.body for m in messages]
