# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.safe_eval import safe_eval

from .common import SponsorDataMixin

GROUP = "event_raffle_prize_sponsor.group_raffle_sponsorship_manager"


@tagged("post_install", "-at_install")
class TestSponsorReview(SponsorDataMixin, TransactionCase):
    """Who approves and refuses the sponsored prizes.

    `listed` is an event user listed as sponsorship manager of the open
    event only; the organizer is an event user listed nowhere.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sponsor_setup()
        cls.listed = new_test_user(
            cls.env,
            login="listed_reviewer",
            groups="base.group_user,event.group_event_user",
            email="listed.reviewer@example.com",
            name="Lee Listed",
        )
        cls.open_event.raffle_sponsor_manager_ids = [
            Command.link(cls.listed.id)
        ]
        cls.group = cls.env.ref(GROUP)

    def _sponsor_mails(self):
        """Emails and notifications that reach a contact of the sponsor."""
        partners = self.env["res.partner"].search(
            [("commercial_partner_id", "=", self.sponsor.id)]
        )
        mails = self.env["mail.mail"].search(
            [("recipient_ids", "in", partners.ids)]
        )
        notifications = self.env["mail.notification"].search(
            [("res_partner_id", "in", partners.ids)]
        )
        return mails, notifications

    def test_group_follows_the_event_lists(self):
        self.assertIn(self.group, self.listed.groups_id)
        self.assertIn(self.group, self.manager.groups_id)
        self.assertNotIn(self.group, self.organizer.groups_id)
        # Listed on two events, removed from one: still a manager.
        self.second_event.raffle_sponsor_manager_ids = [
            Command.link(self.listed.id)
        ]
        self.open_event.raffle_sponsor_manager_ids = [
            Command.unlink(self.listed.id)
        ]
        self.assertIn(self.group, self.listed.groups_id)
        self.second_event.raffle_sponsor_manager_ids = [Command.clear()]
        self.assertNotIn(self.group, self.listed.groups_id)
        # A new event that lists the user, then its deletion.
        event = self._event(
            "Third Fair",
            self.open_event.date_end,
            raffle_sponsor_manager_ids=[Command.set(self.listed.ids)],
        )
        self.assertIn(self.group, self.listed.groups_id)
        event.unlink()
        self.assertNotIn(self.group, self.listed.groups_id)
        # A portal user listed by mistake never gets the group.
        self.second_event.raffle_sponsor_manager_ids = [
            Command.link(self.alice.id)
        ]
        self.assertNotIn(self.group, self.alice.groups_id)

    def test_listed_manager_approves_the_prizes_of_their_event(self):
        prize = self._submit()
        other = self._submit(name="Second Fair Lamp", event=self.second_event)
        mails, notifications = self._sponsor_mails()
        as_listed = prize.with_user(self.listed)
        self.assertTrue(as_listed.raffle_sponsor_can_review)
        self.assertFalse(
            other.with_user(self.listed).raffle_sponsor_can_review
        )
        as_listed.action_raffle_sponsor_approve()
        self.assertEqual(prize.raffle_sponsor_state, "approved")
        self.assertTrue(prize.active)
        self.assertTrue(prize.is_published)
        with self.assertRaises(AccessError):
            other.with_user(self.listed).action_raffle_sponsor_approve()
        self.assertEqual(other.raffle_sponsor_state, "submitted")
        # The sponsorship manager still writes no product.
        with self.assertRaises(AccessError):
            prize.with_user(self.listed).write({"list_price": 1.0})
        # Nothing is sent to the sponsor: the portal shows the state.
        self.assertEqual(self._sponsor_mails(), (mails, notifications))

    def test_a_prize_of_several_events_needs_all_of_them(self):
        prize = self._submit()
        prize.raffle_event_ids = [Command.link(self.second_event.id)]
        as_listed = prize.with_user(self.listed)
        self.assertFalse(as_listed.raffle_sponsor_can_review)
        with self.assertRaises(AccessError):
            as_listed.action_raffle_sponsor_approve()
        with self.assertRaises(AccessError):
            as_listed.action_open_raffle_sponsor_refuse_wizard()
        self.second_event.raffle_sponsor_manager_ids = [
            Command.link(self.listed.id)
        ]
        prize.invalidate_recordset(["raffle_sponsor_can_review"])
        self.assertTrue(as_listed.raffle_sponsor_can_review)
        as_listed.action_raffle_sponsor_approve()
        self.assertEqual(prize.raffle_sponsor_state, "approved")
        # A prize of any event (no event) is left to the event managers.
        prize.raffle_event_ids = [Command.clear()]
        prize.invalidate_recordset(["raffle_sponsor_can_review"])
        self.assertFalse(as_listed.raffle_sponsor_can_review)
        self.assertTrue(
            prize.with_user(self.manager).raffle_sponsor_can_review
        )

    def test_listed_manager_refuses_with_a_reason(self):
        prize = self._submit()
        other = self._submit(name="Second Fair Lamp", event=self.second_event)
        mails, notifications = self._sponsor_mails()
        action = prize.with_user(
            self.listed
        ).action_open_raffle_sponsor_refuse_wizard()
        wizard = (
            self.env[action["res_model"]]
            .with_user(self.listed)
            .with_context(action["context"])
            .create({"reason": "Add the size of the lamp."})
        )
        wizard.action_refuse()
        self.assertEqual(prize.raffle_sponsor_state, "refused")
        self.assertEqual(
            prize.raffle_sponsor_refusal_reason, "Add the size of the lamp."
        )
        wizard = (
            self.env["event.raffle.prize.refuse.wizard"]
            .with_user(self.listed)
            .create({"product_tmpl_id": other.id, "reason": "No."})
        )
        with self.assertRaises(AccessError):
            wizard.action_refuse()
        with self.assertRaises(AccessError):
            other.with_user(self.listed)._raffle_sponsor_refuse("No.")
        self.assertEqual(other.raffle_sponsor_state, "submitted")
        self.assertEqual(self._sponsor_mails(), (mails, notifications))

    def test_unlisted_and_plain_users_are_refused(self):
        prize = self._submit()
        plain = new_test_user(
            self.env,
            login="plain_employee",
            groups="base.group_user",
            email="plain.employee@example.com",
        )
        for user in (self.organizer, plain):
            as_user = prize.with_user(user)
            self.assertFalse(as_user.raffle_sponsor_can_review)
            with self.assertRaises(AccessError):
                as_user.action_raffle_sponsor_approve()
            with self.assertRaises(AccessError):
                as_user._raffle_sponsor_refuse("No.")
            with self.assertRaises(AccessError):
                as_user.action_open_raffle_sponsor_refuse_wizard()
        with self.assertRaises(AccessError):
            self.env["event.raffle.prize.refuse.wizard"].with_user(
                self.organizer
            ).create({"product_tmpl_id": prize.id, "reason": "No."})
        self.assertEqual(prize.raffle_sponsor_state, "submitted")

    def test_internal_user_listed_without_event_rights(self):
        """A sponsorship manager who is not an event user reads the prizes
        of their events and approves them."""
        reviewer = new_test_user(
            self.env,
            login="listed_employee",
            groups="base.group_user",
            email="listed.employee@example.com",
        )
        self.open_event.raffle_sponsor_manager_ids = [
            Command.link(reviewer.id)
        ]
        prize = self._submit().with_user(reviewer)
        prize.read(
            [
                "name",
                "list_price",
                "raffle_sponsor_id",
                "raffle_band_id",
                "raffle_event_ids",
                "raffle_sponsor_state",
                "raffle_sponsor_can_review",
            ]
        )
        prize.action_raffle_sponsor_approve()
        self.assertEqual(prize.raffle_sponsor_state, "approved")

    def test_menu_filter_and_list_follow_the_reviewer(self):
        menu = self.env.ref(
            "event_raffle_prize_sponsor.menu_event_raffle_prize_to_review"
        )
        search = self.env.ref(
            "event_raffle_prize.product_template_view_search_raffle_prize"
        )
        Menu = self.env["ir.ui.menu"]
        for user, visible in (
            (self.listed, True),
            (self.manager, True),
            (self.organizer, False),
        ):
            self.assertEqual(
                menu.id in Menu.with_user(user)._visible_menu_ids(),
                visible,
                user.login,
            )
            arch = (
                self.env["product.template"]
                .with_user(user)
                .get_views([(search.id, "search")])["views"]["search"]["arch"]
            )
            self.assertEqual(
                'name="raffle_to_review"' in arch, visible, user.login
            )
        # The menu opens the window action itself, so that the web client
        # finds the Raffle menu of the list and of its records.
        action = self.env.ref(
            "event_raffle_prize_sponsor.action_event_raffle_prize_to_review"
        )
        self.assertEqual(menu.action, action)
        prize = self._submit()
        other = self._submit(name="Second Fair Lamp", event=self.second_event)
        both = self._submit(name="Both Fairs Lamp")
        both.raffle_event_ids = [Command.link(self.second_event.id)]
        Template = self.env["product.template"].with_context(active_test=False)
        plain = new_test_user(
            self.env,
            login="plain_lister",
            groups="base.group_user",
            email="plain.lister@example.com",
        )

        def listed_by(user):
            domain = safe_eval(action.domain)
            return Template.with_user(user).search(domain)

        listed = listed_by(self.listed)
        self.assertIn(prize, listed)
        self.assertNotIn(other, listed)
        self.assertNotIn(both, listed)
        self.assertTrue(
            {prize, other, both} <= set(listed_by(self.manager)),
        )
        self.assertFalse(listed_by(self.organizer) & (prize | other | both))
        self.assertFalse(listed_by(plain) & (prize | other | both))
        # The opposite search lists the rest.
        not_listed = Template.with_user(self.listed).search(
            [
                ("id", "in", (prize | other | both).ids),
                ("raffle_sponsor_can_review", "=", False),
            ]
        )
        self.assertEqual(not_listed, other | both)

    def test_approval_restores_only_a_prize_waiting_for_review(self):
        """Approve never restores nor publishes an approved prize that an
        event manager archived or unpublished, nor a prize without a
        sponsor."""
        prize = self._submit()
        as_listed = prize.with_user(self.listed)
        as_listed.action_raffle_sponsor_approve()
        prize.write({"active": False, "is_published": False})
        with self.assertRaisesRegex(UserError, "submitted or refused"):
            as_listed.action_raffle_sponsor_approve()
        self.assertFalse(prize.active)
        self.assertFalse(prize.is_published)
        with self.assertRaises(UserError):
            prize.with_user(self.manager).action_raffle_sponsor_approve()
        self.assertFalse(prize.active)
        # A prize created in the backend for the event, without a sponsor,
        # archived by an event manager: not a sponsored prize to review.
        staff = self._prize(
            "Staff Lamp",
            raffle_sponsor_id=False,
            raffle_band_id=self.band_a.id,
            raffle_event_ids=[Command.set(self.open_event.ids)],
        ).product_tmpl_id
        staff.write({"active": False, "is_published": False})
        as_listed = staff.with_user(self.listed)
        self.assertFalse(as_listed.raffle_sponsor_can_review)
        with self.assertRaises(AccessError):
            as_listed.action_raffle_sponsor_approve()
        # Even a submitted prize without a sponsor is left to the event
        # managers.
        staff.sudo().raffle_sponsor_state = "submitted"
        staff.invalidate_recordset(["raffle_sponsor_can_review"])
        self.assertFalse(as_listed.raffle_sponsor_can_review)
        with self.assertRaises(AccessError):
            as_listed.action_raffle_sponsor_approve()
        with self.assertRaises(AccessError):
            as_listed._raffle_sponsor_refuse("No.")
        self.assertFalse(staff.active)
