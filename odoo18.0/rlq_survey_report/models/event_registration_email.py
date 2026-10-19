# -*- coding: utf-8 -*-
"""
event_registration_email.py
===========================

Invalid e-mail addresses of event registrations (v1.109.0).

  - Every registration gets `rlq_email_issue` (invalid / typo / disposable, stored, computed from `email`) and `rlq_email_suggestion` (the corrected
    address when it can be guessed: "mariebc33@gmail'com" -> "mariebc33@gmail.com", "gmial.com" -> "gmail.com"). Rules: models/email_check.py
    (pure Python, the same as apps/_email_check.py of nginx-tools).
  - At registration time (website or back-office), a PUNCTUATION / SPACE mistake that changes no letter ("gmail'com", "gmail..com", "x @gmail.com")
    is corrected BEFORE the registration is created, so the confirmation e-mail leaves to the right address; a note is posted on the registration.
    System parameter `rlq_survey_report.registration_email_autofix`: "syntax" (default), "off" (never), "typos" (also a misspelled popular domain).
    The registration is NEVER refused or blocked.
  - Menu Events > Invalid e-mails (and Surveys > Detailed reports): the registrations with an issue, and the button « Fix and resend » (wizard
    rlq.registration.email.fix): the corrected address is written on the registration and on its contact (only if the contact holds the same wrong
    address), the failed e-mails of the registration are re-addressed and put back in the queue, and the confirmation e-mail is sent again
    (templates of the event's « after each registration » schedulers, otherwise event.event_subscription).
  - Menu « Failed e-mails »: the outgoing e-mails in « Delivery failed » (mail.mail, state exception), to see the bounces of wrong addresses.

The login of an Odoo account (res.users) is never changed here: the person may log in with it.

© Services-Linux Conseils Inc — Martial@Bigras.ca, Martial.Bigras@Services-Conseils-Linux.com
License: AGPL-3
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import email_check

_logger = logging.getLogger(__name__)

AUTOFIX_PARAM = "rlq_survey_report.registration_email_autofix"
ISSUES = [("invalid", "Invalid address"), ("typo", "Probable typo"), ("disposable", "Disposable address")]


def autofix_mode(env):
    mode = (env["ir.config_parameter"].sudo().get_param(AUTOFIX_PARAM, "syntax") or "syntax").strip().lower()
    return mode if mode in ("syntax", "off", "typos") else "syntax"


def automatic_correction(address, mode):
    """Correction applied at registration time according to the mode, or None."""
    if mode == "off" or not address:
        return None
    fixed = email_check.syntax_fix(address)
    if fixed or mode != "typos":
        return fixed
    code, suggestion = email_check.issue(address)
    return suggestion if code in ("invalid", "typo") else None


class EventRegistrationEmail(models.Model):
    _inherit = "event.registration"

    rlq_email_issue = fields.Selection(
        ISSUES, string="E-mail issue", compute="_compute_rlq_email_issue", store=True, index=True,
        help="Invalid: the address cannot receive mail as written. Probable typo: a popular domain misspelled (gmial.com). "
             "Disposable: a throw-away mailbox.")
    rlq_email_suggestion = fields.Char(string="Suggested e-mail", compute="_compute_rlq_email_issue", store=True,
                                       help="Corrected address when it can be guessed without asking the person.")
    rlq_failed_mail_count = fields.Integer(string="Failed e-mails", compute="_compute_rlq_failed_mail_count",
                                           help="Outgoing e-mails of this registration (or to its address) in « Delivery failed ».")

    @api.depends("email")
    def _compute_rlq_email_issue(self):
        for registration in self:
            code, suggestion = email_check.issue(registration.email)
            registration.rlq_email_issue = code
            registration.rlq_email_suggestion = suggestion or False

    def _rlq_failed_mails(self):
        """mail.mail in failure linked to the registration (model / res_id) or addressed to its e-mail address (email_to or recipient contact)."""
        self.ensure_one()
        mails = self.env["mail.mail"].sudo()
        domain = [("state", "=", "exception"), ("model", "=", "event.registration"), ("res_id", "=", self.id)]
        found = mails.search(domain)
        if self.email:
            found |= mails.search([("state", "=", "exception"), "|", ("email_to", "ilike", self.email), ("recipient_ids.email", "=ilike", self.email)])
        return found

    def _compute_rlq_failed_mail_count(self):
        for registration in self:
            try:
                registration.rlq_failed_mail_count = len(registration._rlq_failed_mails())
            except Exception:  # noqa: BLE001 - a counter must never break a form
                registration.rlq_failed_mail_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        mode = autofix_mode(self.env)
        corrections = {}
        for i, vals in enumerate(vals_list):
            fixed = automatic_correction(vals.get("email"), mode)
            if fixed:
                corrections[i] = (vals["email"], fixed)
                vals["email"] = fixed
        registrations = super().create(vals_list)
        for i, (old, new) in corrections.items():
            registration = registrations[i]
            _logger.info("registration %s: e-mail address corrected automatically (%s mode)", registration.id, mode)
            try:
                registration.message_post(body=_("E-mail address corrected automatically: %(old)s → %(new)s", old=old, new=new),
                                          subtype_xmlid="mail.mt_note")
            except Exception:  # noqa: BLE001 - the note is only a comfort
                _logger.info("note not posted on registration %s", registration.id, exc_info=True)
            partner = registration.partner_id
            if partner and partner.email == old:
                partner.sudo().write({"email": new})
        return registrations

    def action_rlq_fix_email(self):
        """Opens the correction wizard for the selected registrations (all of them, or those with an issue when called from the list)."""
        registrations = self.filtered("rlq_email_issue") or self
        wizard = self.env["rlq.registration.email.fix"].create({
            "line_ids": [(0, 0, {"registration_id": r.id, "new_email": r.rlq_email_suggestion or r.email}) for r in registrations],
        })
        return {
            "type": "ir.actions.act_window", "name": _("Fix and resend"), "res_model": "rlq.registration.email.fix", "res_id": wizard.id,
            "view_mode": "form", "target": "new",
        }

    def _rlq_resend_confirmation(self):
        """Sends the registration confirmation again: templates of the event's « after each registration » schedulers, otherwise
        event.event_subscription. Returns the number of e-mails queued."""
        self.ensure_one()
        templates = self.env["mail.template"]
        for scheduler in getattr(self.event_id, "event_mail_ids", self.env["event.mail"].browse()):
            template = getattr(scheduler, "template_ref", False)
            if getattr(scheduler, "interval_type", "") == "after_sub" and template and template._name == "mail.template":
                templates |= template
        if not templates:
            fallback = self.env.ref("event.event_subscription", raise_if_not_found=False)
            if fallback:
                templates = fallback
        for template in templates:
            template.sudo().send_mail(self.id, force_send=False)
        return len(templates)


class RlqRegistrationEmailFix(models.TransientModel):
    _name = "rlq.registration.email.fix"
    _description = "Fix the e-mail address of registrations and resend"

    line_ids = fields.One2many("rlq.registration.email.fix.line", "wizard_id", string="Registrations")
    update_partner = fields.Boolean(string="Also fix the contact", default=True,
                                    help="Writes the corrected address on the registration's contact too, only when the contact holds the same wrong address.")
    resend = fields.Boolean(string="Resend the e-mails", default=True,
                            help="Failed e-mails of the registration re-addressed and put back in the queue, and the confirmation e-mail sent again.")

    def action_apply(self):
        self.ensure_one()
        done, messages = 0, []
        for line in self.line_ids.filtered("registration_id"):
            registration = line.registration_id.sudo()
            old, new = registration.email or "", (line.new_email or "").strip()
            if not new or new == old:
                continue
            check = email_check.check(new)
            if not check["valid"]:
                raise UserError(_("« %(email)s » (registration of %(name)s) is not a valid address either: %(reason)s.",
                                  email=new, name=registration.name or registration.id, reason=check["reason"]))
            failed = registration._rlq_failed_mails() if self.resend else self.env["mail.mail"]
            registration.write({"email": new})
            partner = registration.partner_id
            if self.update_partner and partner and partner.email == old:
                partner.sudo().write({"email": new})
            resent = 0
            if self.resend:
                for mail in failed:
                    if mail.email_to and old and old in mail.email_to:
                        mail.email_to = mail.email_to.replace(old, new)
                    mail.mark_outgoing()
                    resent += 1
                try:
                    resent += registration._rlq_resend_confirmation()
                except Exception:  # noqa: BLE001 - the correction stays; the operator is told
                    _logger.warning("confirmation not resent for registration %s", registration.id, exc_info=True)
                    messages.append(_("Registration of %(name)s: address fixed, but the confirmation could not be resent (see the server log).",
                                      name=registration.name or registration.id))
            registration.message_post(body=_("E-mail address corrected: %(old)s → %(new)s (%(n)d e-mail(s) resent).", old=old, new=new, n=resent),
                                      subtype_xmlid="mail.mt_note")
            done += 1
        message = _("%(n)d registration(s) fixed.", n=done) + ("\n" + "\n".join(messages) if messages else "")
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Invalid e-mails"), "message": message, "type": "warning" if messages else "success", "sticky": bool(messages),
                       "next": {"type": "ir.actions.act_window_close"}},
        }


class RlqRegistrationEmailFixLine(models.TransientModel):
    _name = "rlq.registration.email.fix.line"
    _description = "Registration whose e-mail address is fixed"

    wizard_id = fields.Many2one("rlq.registration.email.fix", required=True, ondelete="cascade")
    registration_id = fields.Many2one("event.registration", string="Registration", required=True, ondelete="cascade")
    event_id = fields.Many2one(related="registration_id.event_id", string="Event")
    name = fields.Char(related="registration_id.name", string="Name")
    old_email = fields.Char(related="registration_id.email", string="Current e-mail")
    issue = fields.Selection(related="registration_id.rlq_email_issue", string="Issue")
    new_email = fields.Char(string="Corrected e-mail", required=True)
