# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Model tests: the draws of a day won by a contact, the registrations of
a contact, the self-declared attendance, which never changes the
attendance of the raffles, and the setting "On-site card" (off by
default, written by the settings form). Every name below is invented for
the tests."""

from odoo.tests import TransactionCase, tagged

from ..models.res_config_settings import PARAM_ONSITE_CARD
from .common import PrizeWebappMixin


@tagged("post_install", "-at_install")
class TestPrizeWebappModels(PrizeWebappMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._webapp_setup("ewp_prize_models")

    def test_draws_of_the_day_won_by_the_partner(self):
        partner = self.winner_user.partner_id
        mine = self._draw(self._participant_of(self.winner_user))
        other = self._draw(self._participant_of(self.other_user))
        absent = self._draw(
            self.raffle.participant_ids.filtered(
                lambda p: p.partner_id == partner
            ),
            is_absent=True,
        )
        # A raffle of another event, not listed on the day.
        event_b = self.env["event.event"].create(
            {
                "name": "Prize Other Event",
                "date_begin": "2026-02-01 09:00:00",
                "date_end": "2026-02-01 18:00:00",
            }
        )
        raffle_b = self.env["event.raffle"].create(
            {"name": "Elsewhere", "event_id": event_b.id}
        )
        far = self._draw(
            self._participant_of(self.winner_user, raffle=raffle_b)
        )
        draws = self.day._ewp_prize_draws(partner)
        self.assertEqual(draws, mine)
        self.assertNotIn(other, draws)
        self.assertNotIn(absent, draws)
        self.assertNotIn(far, draws)
        # A raffle listed on the day counts, whatever its event.
        self.day.raffle_ids = raffle_b
        self.assertEqual(self.day._ewp_prize_draws(partner), mine | far)
        self.assertFalse(self.day._ewp_prize_draws(self.env["res.partner"]))

    def test_claimed_draw_stays_once_the_participant_is_gone(self):
        participant = self._participant_of(self.winner_user)
        draw = self._draw(participant)
        draw._prize_claim(self.mug)
        participant.unlink()
        self.assertFalse(draw.partner_id)
        partner = self.winner_user.partner_id
        self.assertEqual(self.day._ewp_prize_draws(partner), draw)
        self.assertFalse(self.day._ewp_prize_draws(self.other_user.partner_id))

    def test_registrations_of_the_partner(self):
        partner = self.winner_user.partner_id
        participant = self._participant_of(self.winner_user)
        mine = participant.registration_id
        cancelled = self.env["event.registration"].create(
            {"event_id": self.event.id, "partner_id": partner.id}
        )
        cancelled.action_cancel()
        self._participant_of(self.other_user)
        self.assertEqual(self.day._ewp_partner_registrations(partner), mine)

    def test_declared_attendance_never_changes_the_attendance_mode(self):
        virtual = self._participant_of(self.winner_user, attended=False)
        onsite = self._participant_of(self.other_user, attended=True)
        draw = self._draw(virtual)
        self.assertEqual(virtual.attendance_mode, "virtual")
        self.assertEqual(draw._prize_delivery_mode(self.mug), "shipping")
        state = virtual.registration_id.state
        virtual.registration_id._ewp_declare_attendance(True)
        self.env.invalidate_all()
        self.assertTrue(virtual.registration_id.attendance_declared)
        self.assertTrue(virtual.registration_id.attendance_declared_date)
        self.assertTrue(draw.winner_attendance_declared)
        self.assertTrue(draw.winner_attendance_declared_date)
        self.assertEqual(virtual.registration_id.state, state)
        self.assertEqual(virtual.attendance_mode, "virtual")
        self.assertEqual(draw.attendance_mode, "virtual")
        self.assertEqual(draw._prize_winner_mode(), "virtual")
        self.assertEqual(draw._prize_delivery_mode(self.mug), "shipping")
        # Saying "not on site" leaves a scanned attendee on site.
        onsite.registration_id._ewp_declare_attendance(False)
        self.assertFalse(onsite.registration_id.attendance_declared)
        self.assertFalse(onsite.registration_id.attendance_declared_date)
        self.assertEqual(onsite.attendance_mode, "onsite")

    def test_french_model_names_follow_the_modules_of_the_models(self):
        """The terms of this module load after those of the modules that
        define its models: with overwrite, they keep the names those
        modules give."""
        self.env["res.lang"]._activate_lang("fr_CA")
        modules = ["event", "event_raffle", "event_webapp_plan"]
        models = ("event.raffle.draw", "event.registration", "event.webapp")
        Module = self.env["ir.module.module"]

        def names():
            self.env.invalidate_all()
            return {
                model: self.env["ir.model"]
                ._get(model)
                .with_context(lang="fr_CA")
                .name
                for model in models
            }

        Module._load_module_terms(modules, ["fr_CA"], overwrite=True)
        expected = names()
        self.assertEqual(expected["event.raffle.draw"], "Tir du tirage")
        Module._load_module_terms(
            [*modules, "event_webapp_plan_raffle"], ["fr_CA"], overwrite=True
        )
        self.assertEqual(names(), expected)


@tagged("post_install", "-at_install")
class TestOnsiteCardSetting(TransactionCase):
    def _param(self):
        return (
            self.env["ir.config_parameter"].sudo().get_param(PARAM_ONSITE_CARD)
        )

    def test_onsite_card_is_off_by_default(self):
        # The module ships no value: a new database has no parameter.
        self.assertFalse(self._param())
        self.assertFalse(self.env["event.webapp"]._ewp_onsite_card_enabled())
        self.assertFalse(
            self.env["res.config.settings"].create({}).ewp_onsite_card
        )

    def test_onsite_card_setting_writes_the_parameter(self):
        arch = self.env["res.config.settings"].get_view(view_type="form")[
            "arch"
        ]
        self.assertIn('name="ewp_onsite_card"', arch)
        settings = self.env["res.config.settings"].create(
            {"ewp_onsite_card": True}
        )
        settings.set_values()
        self.assertEqual(self._param(), "True")
        self.assertTrue(self.env["event.webapp"]._ewp_onsite_card_enabled())
        self.assertTrue(
            self.env["res.config.settings"].create({}).ewp_onsite_card
        )
        settings = self.env["res.config.settings"].create(
            {"ewp_onsite_card": False}
        )
        settings.set_values()
        self.assertFalse(self._param())
        self.assertFalse(self.env["event.webapp"]._ewp_onsite_card_enabled())
        # Anything but a true value reads as off.
        self.env["ir.config_parameter"].set_param(PARAM_ONSITE_CARD, "maybe")
        self.assertFalse(self.env["event.webapp"]._ewp_onsite_card_enabled())
