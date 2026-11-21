# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from markupsafe import escape

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import format_datetime

from odoo.addons.event_raffle_prize_sponsor.models.event_registration import (
    TEMPLATE_EDITOR_GROUPS,
)

THANKS_TEMPLATE = "event_raffle_prize_sponsor.mail_template_sponsor_thanks"
# Layout of the email: the company and the message, without a link to the
# record, which the sponsor cannot open.
THANKS_LAYOUT = "event_raffle_prize_claim.mail_layout_prize"


class EventRaffleSponsorThankWizard(models.TransientModel):
    """Thank the sponsors of an event, one email per sponsor.

    Created by event.event.action_open_raffle_sponsor_thank_wizard(),
    which fills one line per sponsor whose prizes have a winner. The
    preview renders the email of the chosen line as its recipients read
    it. Sending checks the user and the event again, then sends the
    template THANKS_TEMPLATE as superuser to the recipients computed from
    the event at that moment: a line written by hand never chooses an
    address.
    """

    _name = "event.raffle.sponsor.thank.wizard"
    _description = "Thank the Sponsors"

    event_id = fields.Many2one(
        "event.event",
        string="Event",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    line_ids = fields.One2many(
        "event.raffle.sponsor.thank.wizard.line",
        "wizard_id",
        string="Sponsors",
    )
    preview_line_id = fields.Many2one(
        "event.raffle.sponsor.thank.wizard.line",
        string="Preview the email of",
        domain="[('wizard_id', '=', id)]",
    )
    preview_subject = fields.Char(string="Subject", compute="_compute_preview")
    preview_body = fields.Html(
        string="Email",
        compute="_compute_preview",
        sanitize=False,
    )
    template_id = fields.Many2one(
        "mail.template",
        string="Email template",
        compute="_compute_template_id",
    )
    can_edit_template = fields.Boolean(compute="_compute_template_id")

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            wizard._raffle_fill_lines()
        return wizards

    def _raffle_fill_lines(self):
        """One line per sponsor of the event's winning prizes, by name."""
        self.ensure_one()
        event = self.event_id
        event._raffle_sponsor_check_thanks()
        draws = event._raffle_sponsor_thanks_draws()
        sponsors = draws.prize_product_id.product_tmpl_id.raffle_sponsor_id
        Thanks = self.env["event.raffle.sponsor.thanks"]
        commands = []
        for sponsor in sponsors.commercial_partner_id.sorted(
            lambda p: ((p.name or "").lower(), p.id)
        ):
            thanks = Thanks._raffle_get(event, sponsor)
            recipients = thanks._raffle_recipients()
            commands.append(
                Command.create(
                    {
                        "thanks_id": thanks.id,
                        "recipient_ids": [Command.set(recipients.ids)],
                        "winner_count": len(thanks._raffle_draws()),
                        "include": bool(recipients) and not thanks.sent_date,
                    }
                )
            )
        self.line_ids = commands
        self.preview_line_id = (
            self.line_ids.filtered("recipient_ids")[:1] or self.line_ids[:1]
        )

    def _compute_template_id(self):
        template = self.env.ref(THANKS_TEMPLATE, raise_if_not_found=False)
        editor = self.env.user.has_groups(TEMPLATE_EDITOR_GROUPS)
        for wizard in self:
            wizard.template_id = template
            wizard.can_edit_template = editor

    @api.depends("preview_line_id")
    def _compute_preview(self):
        for wizard in self:
            thanks = wizard.preview_line_id.thanks_id.sudo()
            if not thanks or thanks.event_id != wizard.event_id.sudo():
                wizard.preview_subject = False
                wizard.preview_body = False
                continue
            subject, body = wizard._raffle_render(thanks)
            wizard.preview_subject = subject
            wizard.preview_body = body

    def _raffle_render(self, thanks):
        """(subject, body) of the email of `thanks`, in its language."""
        self.event_id._raffle_sponsor_check_thanks()
        template = self.env.ref(THANKS_TEMPLATE).sudo()
        thanks_id = thanks.id
        subject = template._render_field(
            "subject", [thanks_id], compute_lang=True
        )[thanks_id]
        body = template._render_field(
            "body_html",
            [thanks_id],
            compute_lang=True,
            options={"post_process": True},
        )[thanks_id]
        return subject, body

    def action_open_template(self):
        """Open the email template, for the users who may edit it."""
        if not self.env.user.has_groups(TEMPLATE_EDITOR_GROUPS):
            raise AccessError(
                _("Only the email template editors change this template.")
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Thank-you Email"),
            "res_model": "mail.template",
            "res_id": self.env.ref(THANKS_TEMPLATE).id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }

    def action_send(self):
        """Queue one email per ticked sponsor, log it on the event and on
        the sponsor, and keep the date on the sponsor's thanks record."""
        self.ensure_one()
        event = self.event_id
        event._raffle_sponsor_check_thanks()
        if not self.line_ids:
            raise UserError(
                _("No sponsored prize of this event has a winner yet.")
            )
        lines = self.line_ids.filtered("include")
        if not lines:
            raise UserError(_("Tick at least one sponsor to thank."))
        template = self.env.ref(THANKS_TEMPLATE).sudo()
        now = fields.Datetime.now()
        for line in lines:
            thanks = line.thanks_id.sudo()
            if thanks.event_id != event:
                raise AccessError(_("This sponsor is not one of the event."))
            recipients = thanks._raffle_recipients()
            if not recipients:
                raise UserError(line.no_email_reason)
            if not thanks._raffle_thanks_email_from():
                raise UserError(
                    _(
                        "Set the email of the company first: it sends the "
                        "thank-you emails."
                    )
                )
            count = len(thanks._raffle_draws())
            template.send_mail(
                thanks.id,
                force_send=False,
                email_values={
                    "recipient_ids": [Command.set(recipients.ids)],
                },
                email_layout_xmlid=THANKS_LAYOUT,
            )
            thanks.write(
                {
                    "sent_date": now,
                    "sent_by_id": self.env.uid,
                    "sent_winner_count": count,
                }
            )
            emails = ", ".join(recipients.mapped("email"))
            event.sudo()._message_log(
                body=escape(
                    _(
                        "Thank-you email sent to the sponsor %(sponsor)s for "
                        "%(count)s winner(s), to %(emails)s.",
                        sponsor=thanks.sponsor_id.name,
                        count=count,
                        emails=emails,
                    )
                )
            )
            thanks.sponsor_id._message_log(
                body=escape(
                    _(
                        "Thank-you email for %(event)s sent for %(count)s "
                        "winner(s), to %(emails)s.",
                        event=event.sudo().name,
                        count=count,
                        emails=emails,
                    )
                )
            )
        return {"type": "ir.actions.act_window_close"}


class EventRaffleSponsorThankWizardLine(models.TransientModel):
    _name = "event.raffle.sponsor.thank.wizard.line"
    _description = "Sponsor to Thank"
    _rec_name = "sponsor_id"
    _order = "id"

    wizard_id = fields.Many2one(
        "event.raffle.sponsor.thank.wizard",
        required=True,
        ondelete="cascade",
    )
    thanks_id = fields.Many2one(
        "event.raffle.sponsor.thanks",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    sponsor_id = fields.Many2one(
        related="thanks_id.sponsor_id", string="Sponsor"
    )
    recipient_ids = fields.Many2many(
        "res.partner", string="Recipients", readonly=True
    )
    # Text rather than Char: the list wraps a text cell instead of cutting
    # it, so every address and the whole status stay readable.
    recipient_emails = fields.Text(
        string="Emails", compute="_compute_recipient_emails"
    )
    winner_count = fields.Integer(string="Winners", readonly=True)
    include = fields.Boolean(string="Send")
    can_include = fields.Boolean(compute="_compute_recipient_emails")
    no_email_reason = fields.Char(
        string="Reason", compute="_compute_recipient_emails"
    )
    thanked_date = fields.Datetime(related="thanks_id.sent_date")
    thanked_label = fields.Char(
        string="Already thanked", compute="_compute_thanked_label"
    )
    status = fields.Text(
        compute="_compute_status",
        help="Why the line cannot be ticked, and the date of the last "
        "thank-you email sent to this sponsor for the event.",
    )

    @api.depends("recipient_ids")
    def _compute_recipient_emails(self):
        for line in self:
            partners = line.recipient_ids.sudo()
            line.recipient_emails = ", ".join(
                p.email for p in partners if p.email
            )
            line.can_include = bool(partners)
            line.no_email_reason = (
                False
                if partners
                else _(
                    "No email: add one to the sponsor or to the sponsor "
                    "contact of its registration."
                )
            )

    @api.depends("thanked_date")
    def _compute_thanked_label(self):
        for line in self:
            line.thanked_label = (
                _(
                    "Already thanked on %s",
                    format_datetime(
                        self.env, line.thanked_date, dt_format="short"
                    ),
                )
                if line.thanked_date
                else False
            )

    @api.depends("no_email_reason", "thanked_label")
    def _compute_status(self):
        for line in self:
            line.status = (
                "\n".join(
                    text
                    for text in (line.no_email_reason, line.thanked_label)
                    if text
                )
                or False
            )

    @api.constrains("include", "recipient_ids")
    def _check_include(self):
        for line in self:
            if line.include and not line.recipient_ids:
                raise ValidationError(line.no_email_reason)
