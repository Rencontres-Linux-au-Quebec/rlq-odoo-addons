# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from markupsafe import escape

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import email_normalize

# The email that portal.wizard.user sends to a new portal user.
INVITATION_TEMPLATE = "portal.mail_template_data_portal_welcome"
# Groups that may edit email templates, as mail's own access rule says.
TEMPLATE_EDITOR_GROUPS = "mail.group_mail_template_editor,base.group_system"

ACCOUNT_STATE_SELECTION = [
    ("none", "No account"),
    ("invited", "Invitation not accepted yet"),
    ("active", "Has an account"),
]


class EventRegistration(models.Model):
    """Sponsor registrations and their portal account.

    The sponsor contact of a registration is the person who attends and
    signs in to the portal, never a booker. Only the organization sets it:
    marking the registration as a sponsor takes the registration's contact
    when its email is the attendee's, and Send Invitation finds or creates
    a contact without an account for the attendee's email otherwise. An
    email match alone never binds a contact that already has a user, as
    Odoo does not verify the email of a user's contact. The contact is
    stored and kept when an email changes later; it is the one that
    event.event._raffle_sponsor_events() grants the portal pages to.
    Send Invitation grants portal access and sends Odoo's portal
    invitation through portal.wizard.user.
    """

    _inherit = "event.registration"

    is_raffle_sponsor = fields.Boolean(
        string="Is a sponsor",
        tracking=True,
        help="This attendee represents a sponsor of the event: once they "
        "have an account, they add their prizes in the portal.",
    )
    raffle_sponsor_managed = fields.Boolean(
        related="event_id.raffle_sponsor_managed",
    )
    raffle_sponsor_partner_id = fields.Many2one(
        "res.partner",
        string="Sponsor contact",
        compute="_compute_raffle_sponsor_partner_id",
        store=True,
        readonly=False,
        index="btree_not_null",
        help="Contact of the sponsor who signs in to the portal: the "
        "registration's contact when its email is the attendee's, else the "
        "contact that Send invitation finds or creates. A later change of "
        "an email does not change it.",
    )
    raffle_sponsor_account_state = fields.Selection(
        ACCOUNT_STATE_SELECTION,
        string="Sponsor account",
        compute="_compute_raffle_sponsor_account_state",
        compute_sudo=True,
    )

    @api.depends("is_raffle_sponsor", "partner_id")
    def _compute_raffle_sponsor_partner_id(self):
        """The registration's own contact when it is the attendee, read
        when the organization marks the sponsor or changes the contact.

        The emails are not dependencies: a contact edits its own email in
        the portal, and that must not move the sponsor contact.
        """
        for registration in self:
            if registration._raffle_sponsor_own_contact():
                registration.raffle_sponsor_partner_id = (
                    registration.partner_id
                )
            else:
                registration.raffle_sponsor_partner_id = False

    def _raffle_sponsor_own_contact(self):
        """True when the registration is a sponsor's and its contact has
        the attendee's email."""
        self.ensure_one()
        email = email_normalize(self.email or "")
        return bool(
            self.is_raffle_sponsor
            and email
            and self.partner_id
            and self.partner_id.email_normalized == email
        )

    @api.depends("raffle_sponsor_partner_id")
    def _compute_raffle_sponsor_account_state(self):
        """none: no active portal or internal user; invited: a portal user
        who has not signed in yet; active: a portal user who has signed in,
        or an internal user, who needs no invitation."""
        for registration in self:
            users = registration.raffle_sponsor_partner_id.user_ids.filtered(
                lambda u: u.active and (u._is_internal() or u._is_portal())
            )
            if not users:
                registration.raffle_sponsor_account_state = "none"
            elif users.filtered(lambda u: u._is_internal() or u.login_date):
                registration.raffle_sponsor_account_state = "active"
            else:
                registration.raffle_sponsor_account_state = "invited"

    def _raffle_sponsor_contact(self):
        """The sponsor contact, found or created for the invitation.

        The stored sponsor contact when it has an email. Else the
        registration's contact when it is the attendee; else the oldest
        contact with the attendee's email, active ones first, when none of
        them has a user; else a new contact from the attendee's name and
        email.

        Raises UserError when the attendee has no valid email, as the
        portal account signs in with it, and when a contact with that
        email already has a user: the organization then sets that contact
        as the registration's contact if it is the attendee.
        """
        self.ensure_one()
        partner = self.raffle_sponsor_partner_id
        if partner and email_normalize(partner.email or ""):
            return partner
        email = email_normalize(self.email or "")
        if not email:
            raise UserError(
                _(
                    "%s has no valid email address: add the attendee's email "
                    "to the registration first.",
                    self.name or _("This attendee"),
                )
            )
        if self._raffle_sponsor_own_contact():
            partner = self.partner_id
        else:
            # sudo: event users may not read every contact; active_test
            # lists the archived contacts and users too.
            partners = (
                self.env["res.partner"]
                .sudo()
                .with_context(active_test=False)
                .search(
                    [("email_normalized", "=", email)], order="active desc, id"
                )
            )
            if partners.user_ids:
                raise UserError(
                    _(
                        "An account already uses %(email)s, the email of "
                        "%(attendee)s: if that account is the attendee's, "
                        "set its contact as the registration's contact.",
                        email=email,
                        attendee=self.name or email,
                    )
                )
            partner = partners[:1]
        if not partner:
            # sudo: event users may not create contacts.
            partner = (
                self.env["res.partner"]
                .sudo()
                .create(
                    {
                        "name": self.name or email,
                        "email": email,
                        "phone": self.phone or False,
                    }
                )
            )
        # sudo: the field is written by this method once the access to the
        # registration is checked.
        self.sudo().raffle_sponsor_partner_id = partner
        return partner

    def action_raffle_sponsor_invite(self):
        """Grant portal access to the sponsor contact and send Odoo's
        portal invitation, or send it again while it is not accepted.

        Uses portal.wizard.user as the Contacts app does, as superuser
        once the user is checked: an event user (the group of the button)
        with the write access to the registration. The registration desk
        writes registrations too, but creates no account.
        """
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            "event.group_event_user"
        ):
            raise AccessError(
                _("Only the event users send the sponsor invitations.")
            )
        self.check_access("write")
        if not self.is_raffle_sponsor:
            raise UserError(
                _("Only a sponsor registration sends invitations.")
            )
        partner = self._raffle_sponsor_contact()
        wizard = (
            self.env["portal.wizard"]
            .sudo()
            .create({"partner_ids": [Command.set(partner.ids)]})
        )
        wizard_user = wizard.user_ids.filtered(
            lambda w: w.partner_id == partner
        )
        if wizard_user.is_internal:
            raise UserError(
                _(
                    "%s is an internal user: they sign in with their own "
                    "account, no invitation is needed.",
                    partner.display_name,
                )
            )
        if wizard_user.is_portal:
            wizard_user.action_invite_again()
        else:
            wizard_user.action_grant_access()
        self._message_log(
            body=escape(_("Portal invitation sent to %s.", partner.email))
        )
        return True

    def action_open_raffle_sponsor_invitation_template(self):
        """Open the email template of the portal invitation, for the users
        who may edit email templates."""
        if not self.env.user.has_groups(TEMPLATE_EDITOR_GROUPS):
            raise AccessError(
                _("Only the email template editors change this template.")
            )
        template = self.env.ref(INVITATION_TEMPLATE)
        return {
            "type": "ir.actions.act_window",
            "name": _("Invitation Email"),
            "res_model": "mail.template",
            "res_id": template.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "current",
        }
