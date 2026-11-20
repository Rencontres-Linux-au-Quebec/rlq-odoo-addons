# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
audience_topics.py
==================

« Sujets d'intérêt » (Events / Surveys > Rapports RLQ, v1.138.0): the topics that could interest the audience, from the
survey questions checked « Show in Topics of interest » (survey.question.rlq_audience_topics), for example « Quels sujets
aimeriez-vous voir lors d'une prochaine rencontre ? ».

Two menus open the same page: « Sujets d'intérêt de l'audience » (every ticket) and « Sujets d'intérêt des visiteurs »
(the tickets whose name says « visiteur » / « visitor »); the field « Tickets » switches between the two. The expected survey of
each registration is read (the survey of its ticket, otherwise the survey of the event), with the same participation as the
registration desk. Only numbers are shown (no name, no e-mail): no confirmation about personal information is needed.
"""
from odoo import _, api, fields, models

from . import registration_desk_report as rd
from .event_registration_desk import LIST_STATES, guide_action, program_stamp
from .volunteer_coordinator import CHOICE_TYPES


class SurveyQuestionAudienceTopics(models.Model):
    _inherit = "survey.question"

    rlq_audience_topics = fields.Boolean(
        string="Show in « Topics of interest »", default=False,
        help="If checked, the answers to this question are counted in the page « Topics of interest » (Rapports RLQ): each "
             "topic chosen or written, with the number of people and the percentage of the respondents, per ticket. Useful for "
             "questions such as « Which topics would you like at a next meeting? ». No name or e-mail address is shown.",
    )


class RlqAudienceTopics(models.TransientModel):
    _name = "rlq.audience.topics"
    _inherit = ["rlq.last.event.mixin"]                                   # v1.139.0
    _description = "Topics of interest"

    @api.model
    def _default_event_id(self):
        return self.env["rlq.registration.desk"]._default_event_id()

    event_id = fields.Many2one("event.event", string="Event", required=True, default=_default_event_id,
                               help="By default: the event in progress, otherwise the next one.")
    scope = fields.Selection(
        [("all", "Every ticket"), ("visitors", "Visitor tickets"), ("volunteers", "Volunteer tickets"),
         ("sponsors", "Sponsor tickets"), ("tickets", "Tickets chosen one by one")],
        string="Tickets", default="all", required=True,
        help="Which registrations are counted, by the name of their ticket (case and accents ignored): « visiteur » / "
             "« visitor », « bénévole », « commanditaire » / « sponsor » / « partenaire », or the tickets chosen below.")
    # v1.139.0: the volunteers, the sponsors, or any ticket chosen one by one.
    ticket_ids = fields.Many2many("event.event.ticket", string="Tickets chosen",
                                  domain="[('event_id', '=', event_id)]",
                                  help="With « Tickets chosen one by one »: only the registrations to these tickets.")
    # v1.145.0: on site or online (event.registration._rlq_attendance_map()); literal here, for scripts/build_fr_po.py.
    attendance_filter = fields.Selection(
        [("all", "All"), ("on_site", "On site"), ("online", "Online"), ("unknown", "Not specified")],
        string="On site or online", default="all", required=True,
        help="Lists only the people who will be on site (« Présentiel », « Sur place », « Hybride », or « Oui » to « Serez-vous "
             "présent à l'ÉTS ? »), only the people online, or only the people whose answers say neither. Read in this order: "
             "the answer to the on site or online question of their survey, the roles questions « (en présentiel) » / « (en "
             "virtuel) » they answered, then the name of their ticket.")
    table_html = fields.Html(string="Topics of interest", compute="_compute_table", sanitize=False)

    @api.depends("event_id", "scope")
    def _compute_display_name(self):
        titles = {"visitors": _("Topics of interest of the visitors"), "volunteers": _("Topics of interest of the volunteers"),
                  "sponsors": _("Topics of interest of the sponsors")}
        for page in self:
            title = titles.get(page.scope) or _("Topics of interest of the audience")
            page.display_name = "%s: %s" % (title, page.event_id.name) if page.event_id else title

    @api.onchange("event_id")
    def _onchange_event_id(self):
        self.ticket_ids = self.ticket_ids.filtered(lambda ticket: ticket.event_id == self.event_id)

    @api.depends("event_id", "scope", "ticket_ids", "attendance_filter")
    def _compute_table(self):
        for page in self:
            breakdown, tickets, notes = page._rlq_topics_data()
            page.table_html = program_stamp(self.env, page.event_id) + rd.topics_html(
                breakdown, tickets, self.env.lang or rd.DEFAULT_LANG, page.scope, notes)

    def _rlq_registrations(self):
        """The registrations (confirmed or present) of the event, limited to the tickets of the scope."""
        self.ensure_one()
        registrations = self.env["event.registration"].sudo()
        if not self.event_id:
            return registrations
        registrations = registrations.search([("event_id", "=", self.event_id.id), ("state", "in", list(LIST_STATES))])
        if self.scope == "tickets":
            return registrations.filtered(lambda r: r.event_ticket_id in self.ticket_ids._origin)
        if self.scope in ("visitors", "volunteers", "sponsors"):
            registrations = registrations.filtered(
                lambda r: r.event_ticket_id and rd.ticket_in_scope(r.event_ticket_id.name, self.scope))
        return registrations

    def _rlq_topics_data(self):
        """(breakdown, tickets, notes) for rd.topics_html(); breakdown is None when there is no registration."""
        self.ensure_one()
        registrations = self._rlq_registrations()
        if not registrations:
            return None, [], []
        status = registrations._rlq_survey_status_map()
        participations = registrations._rlq_desk_participations(status)
        _inputs, _answered, values, chosen = participations
        if self.attendance_filter and self.attendance_filter != "all":                  # v1.145.0
            attendance = registrations._rlq_attendance_map(status, participations)
            registrations = registrations.filtered(lambda r: rd.attendance_matches(attendance.get(r.id), self.attendance_filter))
            if not registrations:
                return None, [], []
        questions, question_index, by_survey, notes = [], {}, {}, []
        model = self.env["survey.question"].sudo()
        for survey in {status[r.id][0] for r in registrations if status[r.id][0]}:
            domain = [("survey_id", "=", survey.id), ("rlq_audience_topics", "=", True)]
            if "is_page" in model._fields:
                domain.append(("is_page", "=", False))
            found = by_survey[survey.id] = []
            for question in model.search(domain, order="sequence, id"):
                title = question.rlq_desk_label or question.title or ""
                key = rd.sort_key(title)
                if key not in question_index:
                    question_index[key] = len(questions)
                    questions.append({"title": title, "choices": []})
                entry = questions[question_index[key]]
                if question.question_type in CHOICE_TYPES:
                    known = {rd.sort_key(c) for c in entry["choices"]}
                    entry["choices"] += [a.value for a in question.suggested_answer_ids if a.value and rd.sort_key(a.value) not in known]
                found.append((question.id, question_index[key]))
            if not found:
                notes.append(_("No question checked « Show in Topics of interest » in the survey « %(survey)s ».", survey=survey.title))
        if not questions:
            return [], [], notes
        people, tickets = [], set()
        for registration in registrations:
            survey = status[registration.id][0]
            if not survey:
                continue
            ticket = registration.event_ticket_id.name if "event_ticket_id" in registration._fields and registration.event_ticket_id \
                else _("(no ticket)")
            tickets.add(ticket)
            input_id = chosen.get(registration.id)
            answers = {}
            for qid, index in by_survey.get(survey.id, ()):
                if input_id:
                    answers[index] = answers.get(index, []) + list(values.get((input_id, qid), []))
            people.append({"ticket": ticket, "questions": {index for _qid, index in by_survey.get(survey.id, ())},
                           "answers": answers})
        return rd.topics_breakdown(people, questions), sorted(tickets, key=rd.sort_key), notes

    def action_refresh(self):
        return True

    def action_open_guide(self):
        return guide_action(self.env, "sujets-interet")
