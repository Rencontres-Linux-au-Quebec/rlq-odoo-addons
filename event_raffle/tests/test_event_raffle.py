# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestEventRaffle(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Test Event",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        cls.raffle = cls.env["event.raffle"].create(
            {"name": "Tirage 1", "event_id": cls.event.id}
        )

    def _add_participant(self, name, **kw):
        vals = {"raffle_id": self.raffle.id, "name": name}
        vals.update(kw)
        return self.env["event.raffle.participant"].create(vals)

    def test_defaults(self):
        self.assertTrue(self.raffle.remove_winner)
        self.assertEqual(self.raffle.state, "draft")
        self.assertEqual(self.raffle.spin_duration, 6.0)
        self.assertEqual(self.raffle.spin_turns, 5)
        self.assertTrue(self.raffle.show_fireworks)
        # The pointer sits at the top unless the raffle says otherwise.
        self.assertEqual(self.raffle.pointer_angle, "0")

    # These labels exist in English and in fr_CA: each test reads both, so a
    # label left untranslated, or translated once and cached, shows up.

    def _env_in(self, lang):
        self.env["res.lang"]._activate_lang(lang)
        return self.env(context=dict(self.env.context, lang=lang))

    def test_default_name_is_translatable(self):
        for lang, name in (("en_US", "Raffle"), ("fr_CA", "Tirage")):
            raffle = self._env_in(lang)["event.raffle"].create({})
            self.assertEqual(raffle.name, name)

    def test_settings_are_named_in_the_reader_language(self):
        # Whatever name the record stores, the label is the reader's own.
        settings = self.env.ref("event_raffle.raffle_config_singleton")
        settings.name = "Stored name"
        for lang, label in (
            ("en_US", "Default Settings"),
            ("fr_CA", "Paramètres par défaut"),
        ):
            labelled = settings.with_env(self._env_in(lang))
            self.assertEqual(labelled.display_name, label)

    def test_participant_eligible_default(self):
        p = self._add_participant("Alice")
        self.assertTrue(p.eligible)
        self.assertEqual(self.raffle.participant_count, 1)
        self.assertEqual(self.raffle.eligible_count, 1)

    def test_excluded_not_eligible(self):
        p = self._add_participant("Bob", excluded=True)
        self.assertFalse(p.eligible)
        self.assertEqual(self.raffle.eligible_count, 0)

    def test_won_not_eligible_when_remove_winner(self):
        p = self._add_participant("Carol", won=True)
        self.assertFalse(p.eligible)

    def test_won_still_eligible_when_remove_winner_off(self):
        self.raffle.remove_winner = False
        p = self._add_participant("Dan", won=True)
        self.assertTrue(p.eligible)

    def test_eligible_recomputes_when_remove_winner_flips(self):
        # remove_winner=True (default): a won participant is ineligible
        p = self._add_participant("Grace", won=True)
        self.assertFalse(p.eligible)
        # flip on the EXISTING record -> eligible must recompute
        self.raffle.remove_winner = False
        self.assertTrue(p.eligible)
        self.raffle.remove_winner = True
        self.assertFalse(p.eligible)

    def test_onchange_partner_fills_name_email(self):
        partner = self.env["res.partner"].create(
            {"name": "Eve", "email": "eve@example.com"}
        )
        p = self.env["event.raffle.participant"].new(
            {"raffle_id": self.raffle.id, "partner_id": partner.id}
        )
        p._onchange_partner_id()
        self.assertEqual(p.name, "Eve")
        self.assertEqual(p.email, "eve@example.com")
        self.assertEqual(p.source, "partner")

    def test_draw_name_computed(self):
        p = self._add_participant("Frank")
        draw = self.env["event.raffle.draw"].create(
            {
                "raffle_id": self.raffle.id,
                "sequence": 1,
                "winner_participant_id": p.id,
                "winner_name": p.name,
            }
        )
        self.assertIn("1", draw.name)

    def test_draw_next_picks_eligible(self):
        self.raffle.remove_winner = True
        p1 = self._add_participant("A")
        self._add_participant("B", excluded=True)
        res = self.raffle.action_draw_next()
        self.assertEqual(res["winner"]["id"], p1.id)
        self.assertEqual([w["id"] for w in res["wheel"]], [p1.id])
        self.assertEqual(res["winner_index"], 0)
        # Deferred removal: the winner stays on the wheel until the next draw.
        self.assertFalse(p1.won)
        self.assertTrue(p1.eligible)
        self.assertEqual(self.raffle.draw_count, 1)
        self.assertEqual(self.raffle.state, "in_progress")

    def test_winner_removed_only_on_next_draw(self):
        self.raffle.remove_winner = True
        for name in ("A", "B", "C"):
            self._add_participant(name)
        res1 = self.raffle.action_draw_next()
        w1 = self.env["event.raffle.participant"].browse(res1["winner"]["id"])
        # after the first draw the winner is still on the wheel
        self.assertFalse(w1.won)
        self.assertTrue(w1.eligible)
        self.assertEqual(self.raffle.eligible_count, 3)
        # the next draw removes the previous winner, then picks another
        res2 = self.raffle.action_draw_next()
        self.assertTrue(w1.won)
        self.assertFalse(w1.eligible)
        self.assertNotEqual(res2["winner"]["id"], w1.id)
        self.assertEqual(self.raffle.eligible_count, 2)

    def test_draw_next_wheel_index_matches_winner_multi(self):
        p1 = self._add_participant("A")
        p2 = self._add_participant("B")
        p3 = self._add_participant("C")
        res = self.raffle.action_draw_next()
        self.assertEqual(len(res["wheel"]), 3)
        self.assertEqual(
            {w["id"] for w in res["wheel"]},
            {p1.id, p2.id, p3.id},
        )
        self.assertEqual(
            res["wheel"][res["winner_index"]]["id"],
            res["winner"]["id"],
        )
        self.assertIn(res["winner"]["id"], {p1.id, p2.id, p3.id})

    def test_draw_next_no_eligible_raises(self):
        from odoo.exceptions import UserError

        self._add_participant("A", excluded=True)
        with self.assertRaises(UserError):
            self.raffle.action_draw_next()

    def test_draw_next_remove_winner_off_keeps_pool(self):
        self.raffle.remove_winner = False
        p1 = self._add_participant("A")
        self.raffle.action_draw_next()
        self.raffle.action_draw_next()
        # remove_winner off: the winner is never removed from the pool.
        self.assertFalse(p1.won)
        self.assertTrue(p1.eligible)
        self.assertEqual(self.raffle.eligible_count, 1)

    def test_draw_sequences_increment(self):
        for name in ("A", "B", "C"):
            self._add_participant(name)
        self.raffle.remove_winner = True
        seqs = []
        for _i in range(3):
            res = self.raffle.action_draw_next()
            seqs.append(
                self.env["event.raffle.draw"].browse(res["draw_id"]).sequence
            )
        self.assertEqual(seqs, [1, 2, 3])

    def test_draw_next_prize_saved(self):
        self._add_participant("A")
        res = self.raffle.action_draw_next(
            prize="Livre", prize_description="Un bon livre"
        )
        draw = self.env["event.raffle.draw"].browse(res["draw_id"])
        self.assertEqual(draw.prize, "Livre")
        self.assertEqual(draw.prize_description, "Un bon livre")

    def test_get_wheel_data(self):
        p1 = self._add_participant("A")
        data = self.raffle.get_wheel_data()
        self.assertEqual(data["raffle_id"], self.raffle.id)
        self.assertEqual(data["eligible"], [{"id": p1.id, "name": "A"}])
        self.assertEqual(data["spin_duration"], 6.0)
        self.assertEqual(data["tux_animation"], "rotate")
        self.assertEqual(data["flag_text"], "Vive le logiciel libre")
        self.assertEqual(data["theme"], "light")
        self.assertEqual(data["winner_celebration"], "candles")
        self.assertEqual(data["pointer_angle"], "0")
        self.assertEqual(data["history"], [])
        self.assertFalse(data["last_winner"])
        # Tux is hidden by default.
        self.assertFalse(data["show_tux"])

    def test_participant_present_default_true(self):
        p1 = self._add_participant("A")
        self.assertTrue(p1.present)

    def test_mark_absent_sets_participant_not_present(self):
        p1 = self._add_participant("A")
        res = self.raffle.action_draw_next()
        draw = self.env["event.raffle.draw"].browse(res["draw_id"])
        draw.action_mark_absent()
        self.assertTrue(draw.is_absent)
        self.assertFalse(p1.present)
        # history exposes the inverted "present" flag
        hist = self.raffle.get_wheel_data()["history"][0]
        self.assertFalse(hist["present"])
        draw.action_mark_present()
        self.assertTrue(p1.present)

    def test_can_draw_next_single_participant(self):
        # With a single participant and deferred removal, a first draw is
        # possible but the next one is not (the only name would be removed).
        self.raffle.remove_winner = True
        self._add_participant("A")
        self.assertTrue(self.raffle.get_wheel_data()["can_draw_next"])
        self.raffle.action_draw_next()
        # winner still on the wheel, but drawing again would empty the pool
        self.assertFalse(self.raffle.get_wheel_data()["can_draw_next"])

    def test_can_draw_next_keeps_pool_when_not_removing(self):
        # remove_winner off: the single participant is never removed, so a
        # next draw is always possible.
        self.raffle.remove_winner = False
        self._add_participant("A")
        self.raffle.action_draw_next()
        self.assertTrue(self.raffle.get_wheel_data()["can_draw_next"])

    def test_get_wheel_data_history_ordered(self):
        self._add_participant("A")
        self._add_participant("B")
        self.raffle.action_draw_next(prize="Livre")
        self.raffle.action_draw_next()
        data = self.raffle.get_wheel_data()
        self.assertEqual(len(data["history"]), 2)
        self.assertEqual([h["sequence"] for h in data["history"]], [1, 2])
        self.assertTrue(data["history"][0]["winner_name"])

    def test_event_raffle_counts(self):
        self.assertEqual(self.event.raffle_count, 1)
        self.assertEqual(self.event.raffle_winner_count, 0)
        self._add_participant("A")
        self.raffle.action_draw_next()
        # No manual invalidate: rely on the @api.depends chain to
        # reactively recompute raffle_winner_count after a draw wins.
        self.assertEqual(self.event.raffle_winner_count, 1)

    def test_action_start_raffle_returns_wizard(self):
        action = self.event.action_start_raffle()
        self.assertEqual(action["res_model"], "event.raffle.start.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_event_id"], self.event.id)

    def test_action_view_winners(self):
        self._add_participant("A")
        self.raffle.action_draw_next()
        action = self.event.action_view_raffle_winners()
        self.assertEqual(action["res_model"], "event.raffle.draw")
        self.assertEqual(
            action["domain"],
            [
                ("raffle_id.event_id", "=", self.event.id),
                ("winner_participant_id", "!=", False),
            ],
        )

    def test_action_view_raffles(self):
        action = self.event.action_view_raffles()
        self.assertEqual(action["res_model"], "event.raffle")
        self.assertEqual(action["domain"], [("event_id", "=", self.event.id)])

    def test_action_open_fullscreen(self):
        action = self.raffle.action_open_fullscreen()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "event_raffle.wheel")
        self.assertEqual(action["target"], "fullscreen")
        self.assertEqual(action["params"]["raffle_id"], self.raffle.id)


class TestRaffleWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "E",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Reg Present", "email": "p@x.com"}
        )
        # présent (done)
        cls.reg_done = cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.partner.id,
                "name": "Reg Present",
                "email": "p@x.com",
                "state": "done",
            }
        )
        # inscrit (open)
        cls.reg_open = cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "name": "Reg Open",
                "email": "o@x.com",
                "state": "open",
            }
        )
        # doublon du présent (même partner)
        cls.reg_dup = cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.partner.id,
                "name": "Reg Present",
                "email": "p@x.com",
                "state": "done",
            }
        )

    def _run_wizard(self, strategy):
        wizard = (
            self.env["event.raffle.start.wizard"]
            .with_context(active_id=self.event.id, active_model="event.event")
            .create({"event_id": self.event.id, "copy_strategy": strategy})
        )
        action = wizard.action_start()
        raffle = self.env["event.raffle"].browse(action["res_id"])
        return raffle

    def test_present_only(self):
        raffle = self._run_wizard("present_only")
        # 2 present regs but same partner -> dedupe -> 1
        self.assertEqual(raffle.participant_count, 1)
        self.assertEqual(raffle.participant_ids.source, "registration")

    def test_registered_and_present(self):
        raffle = self._run_wizard("registered_and_present")
        # present(dedup 1) + open(1) = 2
        self.assertEqual(raffle.participant_count, 2)

    def test_action_start_returns_action(self):
        wizard = (
            self.env["event.raffle.start.wizard"]
            .with_context(active_id=self.event.id)
            .create({"event_id": self.event.id})
        )
        action = wizard.action_start()
        self.assertEqual(action["res_model"], "event.raffle")
        self.assertTrue(action["res_id"])

    def test_unnamed_raffle_is_named_after_the_event(self):
        for lang, prefix in (("en_US", "Raffle"), ("fr_CA", "Tirage")):
            self.env["res.lang"]._activate_lang(lang)
            env = self.env(context=dict(self.env.context, lang=lang))
            wizard = env["event.raffle.start.wizard"].create(
                {"event_id": self.event.id}
            )
            raffle = env["event.raffle"].browse(
                wizard.action_start()["res_id"]
            )
            self.assertEqual(raffle.name, f"{prefix} - {self.event.name}")

    def test_copy_blank_guests_not_deduped(self):
        ev = self.env["event.event"].create(
            {
                "name": "E2",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        self.env["event.registration"].create(
            {"event_id": ev.id, "state": "done"}
        )
        self.env["event.registration"].create(
            {"event_id": ev.id, "state": "done"}
        )
        wizard = (
            self.env["event.raffle.start.wizard"]
            .with_context(active_id=ev.id)
            .create({"event_id": ev.id, "copy_strategy": "present_only"})
        )
        raffle = self.env["event.raffle"].browse(
            wizard.action_start()["res_id"]
        )
        self.assertEqual(raffle.participant_count, 2)

    # ---- identity: the same person enters once ----------------------------
    # A contact identifies a person before an email, and an email before a
    # name; an email or a name matches whatever its case and outer spaces.

    def _present_raffle(self, *registrations):
        """Raffle of a fresh event where every given registration attended."""
        ev = self.env["event.event"].create(
            {
                "name": "E3",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )
        self.env["event.registration"].create(
            [
                dict(vals, event_id=ev.id, state="done")
                for vals in registrations
            ]
        )
        wizard = self.env["event.raffle.start.wizard"].create(
            {"event_id": ev.id, "copy_strategy": "present_only"}
        )
        return self.env["event.raffle"].browse(wizard.action_start()["res_id"])

    def test_copy_dedupes_on_contact_whatever_the_email(self):
        ann = self.env["res.partner"].create({"name": "Ann"})
        raffle = self._present_raffle(
            {"partner_id": ann.id, "name": "Ann", "email": "ann@example.com"},
            {
                "partner_id": ann.id,
                "name": "Ann",
                "email": "ann.b@example.com",
            },
        )
        self.assertEqual(raffle.participant_count, 1)

    def test_copy_dedupes_on_email_whatever_its_case(self):
        raffle = self._present_raffle(
            {"name": "Ann", "email": " Ann@Example.com"},
            {"name": "Ann B.", "email": "ann@example.com "},
        )
        self.assertEqual(raffle.participant_count, 1)

    def test_copy_keeps_homonyms_with_different_emails(self):
        raffle = self._present_raffle(
            {"name": "Ann", "email": "ann@example.com"},
            {"name": "Ann", "email": "ann.b@example.com"},
        )
        self.assertEqual(raffle.participant_count, 2)

    def test_copy_dedupes_on_name_without_contact_or_email(self):
        raffle = self._present_raffle({"name": " Bob"}, {"name": "bob "})
        self.assertEqual(raffle.participant_count, 1)

    # ---- questionnaire strategies -----------------------------------------
    # "Filled the questionnaire" means answering a Selection or a Text Input
    # question. The identification questions (Name, Email, Phone, Company)
    # prove nothing: Odoo puts the first three on every event and the
    # registration form answers them on its own.

    def _add_questionnaire_question(self, title="Distro préférée ?"):
        return self.env["event.question"].create(
            {
                "event_id": self.event.id,
                "title": title,
                "question_type": "text_box",
            }
        )

    def _answer(self, reg, question, text="Debian"):
        return self.env["event.registration.answer"].create(
            {
                "registration_id": reg.id,
                "question_id": question.id,
                "value_text_box": text,
            }
        )

    def test_question_only_keeps_answered_whatever_the_state(self):
        q = self._add_questionnaire_question()
        self._answer(self.reg_open, q)
        self._answer(self.reg_done, q)
        raffle = self._run_wizard("question_only")
        self.assertEqual(
            raffle.participant_ids.mapped("name"),
            ["Reg Open", "Reg Present"],
        )

    def test_question_only_drops_the_unanswered(self):
        q = self._add_questionnaire_question()
        self._answer(self.reg_open, q)
        raffle = self._run_wizard("question_only")
        self.assertEqual(raffle.participant_ids.mapped("name"), ["Reg Open"])

    def test_question_and_present_demands_both(self):
        q = self._add_questionnaire_question()
        # answered, but only registered: out.
        self._answer(self.reg_open, q)
        self.assertEqual(
            self._run_wizard("question_and_present").participant_count, 0
        )
        # the attended one answers too: in.
        self._answer(self.reg_done, q)
        raffle = self._run_wizard("question_and_present")
        self.assertEqual(
            raffle.participant_ids.mapped("name"), ["Reg Present"]
        )

    def test_questionnaire_ignores_the_default_identity_questions(self):
        identity = self.event.question_ids.filtered(
            lambda q: q.question_type in ("name", "email", "phone")
        )
        self.assertTrue(
            identity, "event should carry Odoo's default questions"
        )
        self._add_questionnaire_question()
        self._answer(self.reg_done, identity[0], text="Reg Present")
        self.assertEqual(
            self._run_wizard("question_only").participant_count, 0
        )

    def test_questionnaire_ignores_the_company_question(self):
        # Odoo does not put a Company question on events by default, and the
        # attendee types the answer, but it identifies them all the same.
        company = self.env["event.question"].create(
            {
                "event_id": self.event.id,
                "title": "Company",
                "question_type": "company_name",
            }
        )
        self._add_questionnaire_question()
        self._answer(self.reg_done, company, text="Example Co")
        self.assertEqual(
            self._run_wizard("question_only").participant_count, 0
        )

    def test_question_strategy_without_a_questionnaire_question_raises(self):
        # The event carries only the default identity questions, so the
        # strategy could never match anyone: say so instead of building an
        # empty raffle.
        self.assertFalse(
            self.event.question_ids.filtered(
                lambda q: q.question_type in ("simple_choice", "text_box")
            )
        )
        with self.assertRaises(UserError):
            self._run_wizard("question_only")


class TestRaffleDrawPrize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Winner P"})
        cls.raffle = cls.env["event.raffle"].create({"name": "R"})
        cls.participant = cls.env["event.raffle.participant"].create(
            {
                "raffle_id": cls.raffle.id,
                "name": "Winner P",
                "partner_id": cls.partner.id,
            }
        )

    def _draw(self, **kw):
        vals = {
            "raffle_id": self.raffle.id,
            "winner_participant_id": self.participant.id,
            "winner_name": "Winner P",
        }
        vals.update(kw)
        return self.env["event.raffle.draw"].create(vals)

    def test_partner_is_carried_over_from_the_participant(self):
        self.assertEqual(self._draw().partner_id, self.partner)

    def test_dating_the_hand_over_marks_it_received_on_write(self):
        draw = self._draw()
        self.assertFalse(draw.prize_received)
        draw.write({"prize_received_date": "2026-02-01 12:00:00"})
        self.assertTrue(draw.prize_received)

    def test_dating_the_hand_over_marks_it_received_on_create(self):
        draw = self._draw(prize_received_date="2026-02-01 12:00:00")
        self.assertTrue(draw.prize_received)

    def test_the_flag_stays_hand_editable_without_a_date(self):
        draw = self._draw()
        draw.prize_received = True
        self.assertTrue(draw.prize_received)
        self.assertFalse(draw.prize_received_date)

    def test_onchange_ticks_the_flag_in_the_form(self):
        draw = self._draw()
        draw.prize_received_date = "2026-02-01 12:00:00"
        draw._onchange_prize_received_date()
        self.assertTrue(draw.prize_received)

    def test_partner_counts_and_lists_its_wins(self):
        self.assertEqual(self.partner.raffle_win_count, 0)
        draw = self._draw()
        self.partner.invalidate_recordset(["raffle_win_count"])
        self.assertEqual(self.partner.raffle_win_count, 1)
        self.assertEqual(self.partner.raffle_draw_ids, draw)
        action = self.partner.action_view_raffle_wins()
        self.assertEqual(action["res_model"], "event.raffle.draw")

    def test_the_winner_filter_domain_selects_only_winners(self):
        other = self.env["res.partner"].create({"name": "No Win"})
        self._draw()
        domain = [("raffle_draw_ids.winner_participant_id", "!=", False)]
        found = self.env["res.partner"].search(domain)
        self.assertIn(self.partner, found)
        self.assertNotIn(other, found)
