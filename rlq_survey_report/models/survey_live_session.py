# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
survey_live_session.py - participants stuck on the first question by a « live session » (v1.141.0)
====================================================================================================

Symptom (Firefox mobile, then Vivaldi on Linux): the participant cannot go further than the first question; above it, « Nous
avons enregistré votre réponse ! Veuillez attendre que l'hôte passe à la question suivante. »; the arrows near « Généré par
Odoo » do nothing. Not a browser problem: it is the LIVE SESSION mode of the Surveys application.

Diagnosis (Odoo 18, addons/survey/models/survey_survey.py):
  - the button « Create Live Session » (action_start_session) sets session_state = 'ready' and forces questions_layout =
    'page_per_question';
  - while session_state is 'ready' or 'in_progress', _create_answer() creates every NEW participation with
    is_session_answer = True: the participant then waits for the host, question by question, and cannot navigate;
  - the button « End Live Session » (action_end_session) writes state = 'done' on EVERY participation of the survey, also
    the ones that are not finished: they would all count as « completed » at the registration desk and in the reports.

Repair, without that side effect: action_rlq_close_live_session() closes the session and makes the stuck participations
normal again (is_session_answer = False): the participant reloads the page and continues; nothing is marked completed.
Prevention: action_start_session() is refused for a survey used by an event (ticket or event), where a live session makes
no sense; and (v1.142.0) the button « End Live Session » of Odoo, shown on the cards of Surveys > Surveys, does the safe close
for such a survey. A warning is shown on the survey, at the registration desk and in « Sondages non complétés ».
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

SESSION_STATES = ("ready", "in_progress")


class SurveySurveyLiveSession(models.Model):
    _inherit = "survey.survey"

    rlq_stuck_session_count = fields.Integer(
        string="Participations waiting for the host", compute="_compute_rlq_live_session",
        help="Participations not completed that are in « live session » mode: the person sees « wait for the host » and cannot "
             "go to the next question.")
    rlq_live_session_warning = fields.Boolean(string="Live session problem", compute="_compute_rlq_live_session")

    @api.depends("session_state")
    def _compute_rlq_live_session(self):
        inputs = self.env["survey.user_input"].sudo()
        counts = {}
        if self.ids and "is_session_answer" in inputs._fields:
            for survey, count in inputs._read_group([("survey_id", "in", self.ids), ("is_session_answer", "=", True),
                                                     ("state", "!=", "done"), ("test_entry", "=", False)],
                                                    ["survey_id"], ["__count"]):
                counts[survey.id] = count
        for survey in self:
            survey.rlq_stuck_session_count = counts.get(survey.id, 0)
            survey.rlq_live_session_warning = bool(survey.session_state in SESSION_STATES or survey.rlq_stuck_session_count)

    def _rlq_used_by_events(self):
        """True when this survey is the survey of an event ticket or of an event (the surveys of the registrations)."""
        self.ensure_one()
        tickets = self.env["event.event.ticket"].sudo()
        if "rlq_survey_id" in tickets._fields and tickets.search_count([("rlq_survey_id", "=", self.id)], limit=1):
            return True
        events = self.env["event.event"].sudo()
        return "survey_id" in events._fields and bool(events.search_count([("survey_id", "=", self.id)], limit=1))

    def action_start_session(self):
        """Refused for the surveys of the events: every person who registers would then wait for a host (v1.141.0)."""
        for survey in self:
            if not self.env.context.get("rlq_allow_live_session") and survey._rlq_used_by_events():
                raise UserError(_("The survey « %(survey)s » is used by event registrations: a live session would make every "
                                  "person who opens it wait for a host, question by question. Duplicate the survey to run a live "
                                  "session.", survey=survey.title))
        return super().action_start_session()

    def action_end_session(self):
        """v1.141.0+: the button « End Live Session » of Odoo (also on the cards of Surveys > Surveys) marks EVERY participation
        of the survey completed. For a survey used by an event, it now does the safe close instead (the people continue,
        nothing is marked completed); a survey not used by an event (a real quiz) keeps the behaviour of Odoo."""
        events_surveys = self.filtered(lambda s: s._rlq_used_by_events())
        result = None
        if events_surveys:
            result = events_surveys.action_rlq_close_live_session()
        others = self - events_surveys
        if others:
            result = super(SurveySurveyLiveSession, others).action_end_session()
        return result

    def action_rlq_close_live_session(self):
        """Button « Close the live session (keep the answers) »: session closed, stuck participations made normal again.

        Unlike « End Live Session » of Odoo, no participation is marked completed. The layout « one page per question », forced
        by the start of the session, is kept (the previous one is not known): change it in the Options tab if needed."""
        if not self.env.user.has_group("survey.group_survey_user"):
            raise AccessError(_("Only survey users can manage sessions."))
        released = 0
        for survey in self:
            stuck = self.env["survey.user_input"].sudo().search([
                ("survey_id", "=", survey.id), ("is_session_answer", "=", True), ("state", "!=", "done")])
            if stuck:
                stuck.write({"is_session_answer": False})
                released += len(stuck)
            vals = {"session_state": False}
            if "session_question_id" in survey._fields:
                vals["session_question_id"] = False
            survey.sudo().write(vals)
            _logger.info("rlq_survey_report: live session of survey %s closed by user %s, %d participations released",
                         survey.id, self.env.uid, len(stuck))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Live session closed"), "type": "success", "sticky": True,
                           "message": _("%(count)d participations can continue: the people only need to reload the page of the "
                                        "survey. No participation was marked completed.", count=released),
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}


def live_session_warnings(env, surveys):
    """Texts of the warnings for the surveys of a page (desk, « Sondages non complétés »): [« survey: N waiting »]."""
    surveys = surveys.sudo().filtered(lambda s: s.rlq_live_session_warning)
    return [_("Survey « %(survey)s »: live session mode, %(count)d participations wait for a host. Open the survey and click "
              "« Close the live session (keep the answers) ».", survey=s.title, count=s.rlq_stuck_session_count) for s in surveys]
