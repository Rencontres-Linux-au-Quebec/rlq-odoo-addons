# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from datetime import timedelta

from odoo import fields
from odoo.tests import new_test_user

from odoo.addons.event_raffle_prize_handover.tests.common import (
    HandoverDataMixin,
)


class SponsorDataMixin(HandoverDataMixin):
    """Sponsor-managed events, sponsors and their portal users.

    Two companies sponsor the open event: the sponsor of the prize link
    tests, with two contacts that have a portal user, and a second one
    with one contact. Every value is invented.
    """

    @classmethod
    def _sponsor_setup(cls):
        cls._handover_setup()
        env = cls.env
        now = fields.Datetime.now()
        cls.manager = new_test_user(
            env,
            login="sponsorship_manager",
            groups="base.group_user,event.group_event_manager",
            email="sponsorship.manager@example.com",
            name="Sam Sponsorship",
        )
        cls.responsible = new_test_user(
            env,
            login="event_responsible",
            groups="base.group_user,event.group_event_user",
            email="event.responsible@example.com",
            name="Remy Responsible",
        )
        cls.open_event = cls._event(
            "Open Fair",
            now + timedelta(days=20),
            raffle_sponsor_managed=True,
            raffle_sponsor_manager_ids=[(6, 0, cls.manager.ids)],
            user_id=cls.responsible.id,
        )
        cls.second_event = cls._event(
            "Second Fair",
            now + timedelta(days=40),
            raffle_sponsor_managed=True,
        )
        cls.alice = cls._portal_user("sponsor_alice", "Alice Sponsor")
        cls.bob = cls._portal_user("sponsor_bob", "Bob Sponsor")
        cls.rival = env["res.partner"].create(
            {"name": "Rival Example", "is_company": True}
        )
        cls.carol = cls._portal_user(
            "sponsor_carol", "Carol Rival", company=cls.rival
        )
        cls.visitor = cls._portal_user(
            "plain_visitor", "Vic Visitor", company=False
        )
        cls.alice_registration = cls._sponsor_registration(
            cls.alice, cls.open_event
        )
        cls.carol_registration = cls._sponsor_registration(
            cls.carol, cls.open_event
        )

    @classmethod
    def _event(cls, name, date_end, **vals):
        return cls.env["event.event"].create(
            dict(
                {
                    "name": name,
                    "date_begin": date_end - timedelta(hours=8),
                    "date_end": date_end,
                    "date_tz": "America/Toronto",
                },
                **vals,
            )
        )

    @classmethod
    def _portal_user(cls, login, name, company=None):
        user = new_test_user(
            cls.env,
            login=login,
            groups="base.group_portal",
            email=f"{login.replace('_', '.')}@example.com",
            name=name,
        )
        company = cls.sponsor if company is None else company
        if company:
            user.partner_id.parent_id = company
        return user

    @classmethod
    def _sponsor_registration(cls, user, event, **vals):
        partner = user.partner_id
        return cls.env["event.registration"].create(
            dict(
                {
                    "event_id": event.id,
                    "partner_id": partner.id,
                    "name": partner.name,
                    "email": partner.email,
                    "is_raffle_sponsor": True,
                },
                **vals,
            )
        )

    def _fair_draw(self, name):
        """A draw of a raffle of the open event, won by a new attendee
        checked in on site."""
        if not getattr(self, "fair_raffle", None):
            self.fair_raffle = self.env["event.raffle"].create(
                {
                    "name": "Fair raffle",
                    "event_id": self.open_event.id,
                    "claim_auto_send": False,
                }
            )
        email = f"{name.lower().replace(' ', '.')}@example.com"
        partner = self.env["res.partner"].create(
            {"name": name, "email": email}
        )
        registration = self.env["event.registration"].create(
            {
                "event_id": self.open_event.id,
                "partner_id": partner.id,
                "name": name,
                "email": email,
            }
        )
        registration.action_set_done()
        participant = self.env["event.raffle.participant"].create(
            {
                "raffle_id": self.fair_raffle.id,
                "name": name,
                "email": email,
                "partner_id": partner.id,
                "registration_id": registration.id,
                "source": "registration",
            }
        )
        return self._draw(participant)

    def _portal_values(self, name="Sponsor Lamp", **values):
        return dict(
            {
                "name": name,
                "description_sale": "A lamp for the desk.",
                "list_price": 30.0,
                "raffle_initial_qty": 2,
                "raffle_virtual_prize": False,
                "raffle_attendance": "onsite",
            },
            **values,
        )

    def _submit(self, user=None, event=None, **values):
        """A prize submitted in the portal by `user` for `event`."""
        user = user or self.alice
        return self.env["product.template"]._raffle_sponsor_portal_create(
            user.partner_id,
            event or self.open_event,
            self._portal_values(**values),
        )

    def _notifications(self, template):
        return self.env["mail.message"].search(
            [
                ("model", "=", "product.template"),
                ("res_id", "=", template.id),
                ("message_type", "=", "user_notification"),
            ]
        )
