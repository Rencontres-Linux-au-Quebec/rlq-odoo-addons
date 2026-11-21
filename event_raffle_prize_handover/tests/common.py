# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import io

from PIL import Image

from odoo import Command
from odoo.tests import new_test_user

from odoo.addons.event_raffle_prize_claim.tests.common import ClaimDataMixin


class HandoverDataMixin(ClaimDataMixin):
    """Prizes, winners and users for the hand-over tests.

    The raffle has a pick-up location. Every value is invented.
    """

    @classmethod
    def _handover_setup(cls):
        cls._claim_setup()
        cls.raffle.prize_pickup_location = "Table 7, hall B"
        cls.organizer = new_test_user(
            cls.env,
            login="handover_organizer",
            groups="base.group_user,event.group_event_user",
            email="handover.organizer@example.com",
            name="Handover Organizer",
        )
        cls.mug = cls._prize("Handover Mug", price=20.0, qty=20)
        cls.ebook = cls._prize(
            "Handover Ebook",
            price=10.0,
            qty=2,
            raffle_virtual_prize=True,
            raffle_virtual_instructions="<p>Open the reading app.</p>",
        )

    @classmethod
    def _cart(cls, participant, draw, product):
        """A claim cart of `draw` holding `product`, on the website."""
        draw._claim_link_issue()
        return cls.env["sale.order"].create(
            {
                "partner_id": participant.partner_id.id,
                "raffle_draw_id": draw.id,
                "website_id": cls.env["website"].browse(1).id,
                "order_line": [Command.create({"product_id": product.id})],
            }
        )

    def _mails(self, order, text):
        return order.message_ids.filtered(lambda m: text in (m.subject or ""))

    @staticmethod
    def _image(width, height, fmt="PNG"):
        buffer = io.BytesIO()
        Image.new("RGB", (width, height), (200, 30, 30)).save(buffer, fmt)
        return buffer.getvalue()
