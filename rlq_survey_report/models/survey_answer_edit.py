# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
survey_answer_edit.py
=====================

Manual changes to the answers of a survey participation (v1.127.0).

  - « Edit the answers » (button of a participation, menu Surveys > Detailed reports > Edit answers): the wizard
    rlq.survey.answer.edit lists every question of the survey with the current answer; a click on a question opens its
    new answer, with the field that fits its type (text, number, scale, date, date and time, one choice, several
    choices, comment). Matrix questions are shown but cannot be changed here.
  - The answer is saved with survey.user_input._save_lines(), the method Odoo itself uses when a person answers: the
    statistics, scores and « save as e-mail » of Odoo stay consistent.
  - Every question changed writes one line in the history rlq.survey.answer.change (who, when, question, answer before,
    answer after, reason). The history has its own menu (Surveys > Detailed reports > Manual changes of answers); it
    cannot be modified, only deleted by an administrator (right to erasure).
  - « Send the update by e-mail »: in the wizard (box), or from the history (button, for the selected changes): the
    person receives the list of the changes not yet sent, then all their answers as they are now. The changes are then
    marked as sent (date and user).

Rights: only « Surveys: Administrator » can change answers (Odoo gives the right to write answer lines to that group
only); the history can be read by every survey user.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import report_builder as rb

_logger = logging.getLogger(__name__)

EDITABLE_TYPES = ("char_box", "text_box", "numerical_box", "scale", "date", "datetime", "simple_choice", "multiple_choice")
CHOICE_TYPES = ("simple_choice", "multiple_choice")
MANAGER_GROUP = "survey.group_survey_manager"
CHANGE_IDS_KEY = "rlq_change_ids"          # context key: the changes put in the update e-mail


def _number_text(value):
    return ("%f" % value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


class RlqSurveyAnswerChange(models.Model):
    _name = "rlq.survey.answer.change"
    _description = "Manual change of a survey answer"
    _order = "change_date desc, id desc"
    _rec_name = "question_title"

    change_date = fields.Datetime(string="Changed on", required=True, readonly=True, default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", string="Changed by", required=True, readonly=True, ondelete="restrict",
                              default=lambda self: self.env.user)
    user_input_id = fields.Many2one("survey.user_input", string="Participation", required=True, readonly=True, index=True,
                                    ondelete="cascade",
                                    help="Deleting the participation deletes its history too (personal data).")
    survey_id = fields.Many2one("survey.survey", string="Survey", related="user_input_id.survey_id", store=True, readonly=True)
    respondent = fields.Char(string="Person", readonly=True, help="Name (or e-mail address) of the person, at the time of the change.")
    email = fields.Char(string="E-mail address", readonly=True)
    question_id = fields.Many2one("survey.question", string="Question", readonly=True, ondelete="set null")
    question_title = fields.Char(string="Question title", readonly=True,
                                 help="Title of the question at the time of the change, kept if the question is deleted.")
    old_value = fields.Text(string="Answer before", readonly=True)
    new_value = fields.Text(string="Answer after", readonly=True)
    reason = fields.Char(string="Reason", readonly=True)
    sent_date = fields.Datetime(string="Sent to the person on", readonly=True, copy=False)
    sent_by = fields.Many2one("res.users", string="Sent by", readonly=True, copy=False, ondelete="set null")

    def write(self, vals):
        """The history is not modified: only the « sent » information is written (by the e-mail of the update)."""
        if set(vals) - {"sent_date", "sent_by"} and not self.env.su:
            raise UserError(_("The history of the manual changes cannot be modified."))
        return super().write(vals)

    def action_send_update(self):
        """Button of the history: e-mails to each person concerned the selected changes not yet sent."""
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_("Only a survey administrator can send the update of the answers."))
        unsent = self.filtered(lambda change: not change.sent_date)
        if not unsent:
            raise UserError(_("The selected changes have already been sent."))
        sent, without_email = 0, []
        for user_input in unsent.mapped("user_input_id"):
            changes = unsent.filtered(lambda change, user_input=user_input: change.user_input_id == user_input)
            if user_input._rlq_send_answer_update(changes):
                sent += 1
            else:
                without_email.append(changes[0].respondent or str(user_input.id))
        message = _("Update sent to %(count)s person(s).", count=sent)
        if without_email:
            message += " " + _("Not sent (no e-mail address): %(names)s.", names=", ".join(without_email))
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Update of the answers"), "message": message, "sticky": bool(without_email),
                           "type": "warning" if without_email else "success",
                           "next": {"type": "ir.actions.client", "tag": "soft_reload"}}}


class SurveyUserInputAnswerEdit(models.Model):
    _inherit = "survey.user_input"

    rlq_change_ids = fields.One2many("rlq.survey.answer.change", "user_input_id", string="Manual changes", readonly=True)
    rlq_change_count = fields.Integer(string="Number of manual changes", compute="_compute_rlq_change_count")
    rlq_changes_html = fields.Html(
        string="Changes (e-mail)", compute="_compute_rlq_changes_html", sanitize=False,
        help="The manual changes put in the update e-mail sent to the person (question, answer before, answer after).")

    def _compute_rlq_change_count(self):
        counts = {}
        if self.ids:
            for user_input, count in self.env["rlq.survey.answer.change"].sudo()._read_group(
                    [("user_input_id", "in", self.ids)], ["user_input_id"], ["__count"]):
                counts[user_input.id] = count
        for user_input in self:
            user_input.rlq_change_count = counts.get(user_input.id, 0)

    def _rlq_changes_for_email(self):
        """The changes of the e-mail: the ones given in the context, otherwise every change not yet sent."""
        self.ensure_one()
        changes = self.env["rlq.survey.answer.change"].sudo()
        ids = self.env.context.get(CHANGE_IDS_KEY)
        if ids:
            return changes.browse(ids).filtered(lambda change: change.user_input_id == self).sorted("id")
        return changes.search([("user_input_id", "=", self.id), ("sent_date", "=", False)], order="id")

    @api.depends("rlq_change_ids")
    @api.depends_context(CHANGE_IDS_KEY)
    def _compute_rlq_changes_html(self):
        for user_input in self:
            changes = user_input._rlq_changes_for_email() if user_input.id else []
            user_input.rlq_changes_html = rb.html_changements_courriel(
                [(change.question_title, change.old_value, change.new_value) for change in changes])

    def _rlq_update_template(self):
        return self.env.ref("rlq_survey_report.mail_template_mise_a_jour_reponses", raise_if_not_found=False)

    def _rlq_send_answer_update(self, changes=None):
        """E-mails to the person the changes (default: every change not yet sent) and all the answers as they are now,
        then marks the changes as sent. Returns False (nothing sent) without an e-mail address or without change."""
        self.ensure_one()
        changes = (changes or self._rlq_changes_for_email()).filtered(lambda change: not change.sent_date)
        recipient = self._rlq_destinataire()
        template = self._rlq_update_template()
        if not changes or not recipient or not template:
            return False
        template.sudo().with_context(**{CHANGE_IDS_KEY: changes.ids}).send_mail(
            self.id, force_send=False, email_values={"email_to": recipient, "recipient_ids": [(5,)], "auto_delete": True})
        changes.sudo().write({"sent_date": fields.Datetime.now(), "sent_by": self.env.user.id})
        _logger.info("rlq_survey_report: update of %d answer(s) of survey.user_input %s e-mailed by user %s",
                     len(changes), self.id, self.env.uid)
        return True

    def action_rlq_edit_answers(self):
        """Button « Edit the answers » of a participation."""
        self.ensure_one()
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_("Only a survey administrator can change the answers of a participation."))
        wizard = self.env["rlq.survey.answer.edit"].create({"user_input_id": self.id})
        return {"type": "ir.actions.act_window", "name": _("Edit the answers"), "res_model": "rlq.survey.answer.edit",
                "res_id": wizard.id, "view_mode": "form", "target": "new", "context": {"dialog_size": "extra-large"}}

    def action_rlq_open_changes(self):
        """Smart button: the manual changes of this participation."""
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": _("Manual changes of answers"), "res_model": "rlq.survey.answer.change",
                "view_mode": "list,form", "domain": [("user_input_id", "=", self.id)], "context": {"create": False}}


class RlqSurveyAnswerEdit(models.TransientModel):
    _name = "rlq.survey.answer.edit"
    _description = "Edit the answers of a participation"

    user_input_id = fields.Many2one("survey.user_input", string="Participation", required=True, readonly=True, ondelete="cascade")
    survey_id = fields.Many2one(related="user_input_id.survey_id", string="Survey")
    respondent = fields.Char(string="Person", compute="_compute_respondent")
    recipient = fields.Char(string="E-mail address", compute="_compute_respondent")
    line_ids = fields.One2many("rlq.survey.answer.edit.line", "wizard_id", string="Questions")
    reason = fields.Char(string="Reason of the change", help="Written in the history with each question changed (optional).")
    send_email = fields.Boolean(
        string="Send the update by e-mail to the person", default=False,
        help="After saving, the person receives the list of the changes, then all their answers as they are now.")

    @api.depends("user_input_id")
    def _compute_respondent(self):
        for wizard in self:
            user_input = wizard.user_input_id
            wizard.respondent = (user_input.partner_id.name or user_input.email or "") if user_input else ""
            wizard.recipient = user_input._rlq_destinataire() if user_input else ""

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards.filtered(lambda w: not w.line_ids):
            wizard._rlq_build_lines()
        return wizards

    def _rlq_build_lines(self):
        """One line per question of the survey (pages excluded), filled with the current answer."""
        self.ensure_one()
        user_input = self.user_input_id.sudo()
        questions = user_input.survey_id.question_ids.filtered(lambda q: not getattr(q, "is_page", False))
        commands = []
        for sequence, question in enumerate(questions.sorted(lambda q: (q.sequence, q.id))):
            answers = user_input.user_input_line_ids.filtered(
                lambda line, question=question: line.question_id == question and not line.skipped)
            vals = {"sequence": sequence, "question_id": question.id}
            kind = question.question_type
            if kind in CHOICE_TYPES:
                choices = answers.filtered("suggested_answer_id").mapped("suggested_answer_id")
                comment = answers.filtered(lambda line: not line.suggested_answer_id and line.answer_type == "char_box")
                if kind == "simple_choice":
                    vals["new_choice_id"] = choices[:1].id
                else:
                    vals["new_choice_ids"] = [(6, 0, choices.ids)]
                vals["new_comment"] = comment[:1].value_char_box or False
            elif kind in ("char_box", "text_box"):
                vals["new_text"] = answers[:1]["value_%s" % kind] or False
            elif kind == "numerical_box":
                vals.update(new_number=answers[:1].value_numerical_box, erase=not answers)
            elif kind == "scale":
                vals.update(new_scale=getattr(answers[:1], "value_scale", 0) or 0, erase=not answers)
            elif kind == "date":
                vals["new_date"] = answers[:1].value_date or False
            elif kind == "datetime":
                vals["new_datetime"] = answers[:1].value_datetime or False
            elif answers:                                                 # matrix and any other type: shown, not editable
                vals["readonly_text"] = "\n".join(t for t in (user_input._rlq_texte_ligne(line) for line in answers) if t)
            commands.append((0, 0, vals))
        self.line_ids = commands
        for line in self.line_ids:
            line.current_text = line.new_display                        # the starting point: « changed » is computed from it

    def action_apply(self):
        """Button « Save the changes »: saves every changed question, writes the history, sends the e-mail if asked."""
        self.ensure_one()
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_("Only a survey administrator can change the answers of a participation."))
        changed = self.line_ids.filtered(lambda line: line.editable and line.changed)
        if not changed:
            raise UserError(_("No answer was changed."))
        user_input = self.user_input_id.sudo()
        history = self.env["rlq.survey.answer.change"].sudo()
        respondent, email = self.respondent, self.recipient
        for line in changed:
            question = line.question_id.sudo()
            answer, comment = line._rlq_answer_to_save()
            user_input._save_lines(question, answer, comment=comment)
            history |= history.create({
                "user_input_id": user_input.id, "respondent": respondent, "email": email, "question_id": question.id,
                "question_title": question.title or "", "old_value": line.current_text or "", "new_value": line.new_display or "",
                "reason": self.reason or False, "user_id": self.env.user.id,
            })
        _logger.info("rlq_survey_report: %d answer(s) of survey.user_input %s changed manually by user %s",
                     len(changed), user_input.id, self.env.uid)
        message = _("%(count)s answer(s) changed; the changes are in the history.", count=len(changed))
        kind = "success"
        if self.send_email:
            if user_input._rlq_send_answer_update(history):
                message += " " + _("The update was sent to %(email)s.", email=email)
            else:
                message += " " + _("No e-mail sent: the person has no e-mail address.")
                kind = "warning"
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Answers saved"), "message": message, "type": kind, "sticky": kind == "warning",
                           "next": {"type": "ir.actions.act_window_close"}}}


class RlqSurveyAnswerEditLine(models.TransientModel):
    _name = "rlq.survey.answer.edit.line"
    _description = "Answer to edit"
    _order = "sequence, id"

    wizard_id = fields.Many2one("rlq.survey.answer.edit", string="Edit", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Sequence")
    question_id = fields.Many2one("survey.question", string="Question", required=True, readonly=True)
    question_type = fields.Selection(related="question_id.question_type", string="Type of question")
    # v1.130.0: COMPUTED, not related: survey.question.title is a Char field, and a related field must have the type of its
    # target; « fields.Text(related="question_id.title") » made Odoo refuse to load the database (TypeError, site down).
    question_text = fields.Text(string="Question", compute="_compute_question_text",
                                help="Title of the question, on several lines when it is long.")
    question_type_label = fields.Char(string="Type of question", compute="_compute_question_type_label",
                                      help="Label of the type, as translated by the Surveys application.")
    comments_allowed = fields.Boolean(related="question_id.comments_allowed", string="Comment allowed")
    editable = fields.Boolean(string="Can be changed", compute="_compute_editable")
    current_text = fields.Text(string="Current answer", readonly=True)
    readonly_text = fields.Text(string="Answer (cannot be changed here)", readonly=True)
    new_text = fields.Text(string="New answer")
    new_number = fields.Float(string="New number")
    new_scale = fields.Integer(string="New value of the scale")
    new_date = fields.Date(string="New date")
    new_datetime = fields.Datetime(string="New date and time")
    new_choice_id = fields.Many2one("survey.question.answer", string="New choice", domain="[('question_id', '=', question_id)]")
    new_choice_ids = fields.Many2many("survey.question.answer", "rlq_answer_edit_line_choice_rel", "line_id", "answer_id",
                                      string="New choices", domain="[('question_id', '=', question_id)]")
    new_comment = fields.Char(string="Comment or « Other » answer")
    erase = fields.Boolean(string="No answer", help="Removes the answer to this question: the question becomes « skipped ».")
    new_display = fields.Text(string="Answer after the change", compute="_compute_new_display")
    change_display = fields.Text(string="New answer (text)", compute="_compute_new_display",
                                 help="The new answer, only for the questions changed; empty when the answer is unchanged.")
    changed = fields.Boolean(string="Changed", compute="_compute_new_display")

    @api.depends("question_id.title")
    def _compute_question_text(self):
        for line in self:
            line.question_text = line.question_id.title or ""

    @api.depends("question_id")
    def _compute_question_type_label(self):
        # v1.128.0: the related selection showed the English labels (its values are not translated for this model);
        # the labels of survey.question are translated by the Surveys application.
        labels = dict(self.env["survey.question"]._fields["question_type"]._description_selection(self.env))
        for line in self:
            line.question_type_label = labels.get(line.question_type, line.question_type or "")

    @api.depends("question_type")
    def _compute_editable(self):
        for line in self:
            line.editable = line.question_type in EDITABLE_TYPES

    @api.depends("question_type", "new_text", "new_number", "new_scale", "new_date", "new_datetime", "new_choice_id",
                 "new_choice_ids", "new_comment", "erase", "readonly_text", "current_text")
    def _compute_new_display(self):
        for line in self:
            line.new_display = line._rlq_display()
            line.changed = line.editable and (line.new_display or "") != (line.current_text or "")
            line.change_display = line.new_display if line.changed else False

    def _rlq_display(self):
        """The answer of the line as one text (the same formatting for « before » and « after »)."""
        self.ensure_one()
        kind = self.question_type
        if not self.editable:
            return self.readonly_text or ""
        if self.erase and kind in ("numerical_box", "scale"):
            return ""
        if kind in ("char_box", "text_box"):
            return (self.new_text or "").strip()
        if kind == "numerical_box":
            return _number_text(self.new_number)
        if kind == "scale":
            return str(self.new_scale)
        if kind == "date":
            return fields.Date.to_string(self.new_date) if self.new_date else ""
        if kind == "datetime":
            if not self.new_datetime:
                return ""
            return fields.Datetime.context_timestamp(self, self.new_datetime).strftime("%Y-%m-%d %H:%M")
        choices = self.new_choice_id if kind == "simple_choice" else self.new_choice_ids.sorted(lambda a: (a.sequence, a.id))
        parts = [choice.value or "" for choice in choices]
        if (self.new_comment or "").strip():
            parts.append(self.new_comment.strip())
        return ", ".join(part for part in parts if part)

    def _rlq_answer_to_save(self):
        """(answer, comment) in the form expected by survey.user_input._save_lines(); a False answer means « skipped »."""
        self.ensure_one()
        kind = self.question_type
        comment = (self.new_comment or "").strip() or None
        if kind in ("char_box", "text_box"):
            return (self.new_text or "").strip() or False, None
        # Numbers are given as TEXT, like the web form of Odoo does: _save_lines() treats a false value as « skipped »,
        # so the number 0 given as a number would be lost.
        if kind == "numerical_box":
            return (False if self.erase else _number_text(self.new_number)), None
        if kind == "scale":
            return (False if self.erase else str(self.new_scale)), None
        if kind == "date":
            return (fields.Date.to_string(self.new_date) if self.new_date else False), None
        if kind == "datetime":
            return (fields.Datetime.to_string(self.new_datetime) if self.new_datetime else False), None
        if kind == "simple_choice":
            return self.new_choice_id.id or False, comment
        return self.new_choice_ids.ids, comment
