# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, fields, models
from odoo.exceptions import AccessError

# Claim states of the winners a sponsor is thanked for.
THANKS_CLAIM_STATES = ("reserved", "shipped", "delivered")


class EventEvent(models.Model):
    """Events whose sponsors add their prizes in the portal.

    A sponsor-managed event lets the contacts of its sponsor registrations
    (event.registration.is_raffle_sponsor) submit prizes from /my until
    the event ends. The sponsorship managers are notified of each prize
    submitted; the event's responsible user is notified when the list is
    empty. They approve and refuse the prizes of the events they manage,
    and each change of the list updates their group (see
    res.users._raffle_sponsor_sync_group()).

    Thank the Sponsors emails each sponsor of the event the list of its
    winners (see event.raffle.sponsor.thanks), for the event users and the
    event's sponsorship managers.
    """

    _inherit = "event.event"

    raffle_sponsor_managed = fields.Boolean(
        string="Manage with sponsors",
        help="The sponsors of this event, marked on their registration, "
        "submit their prizes in the portal until the event ends. Each "
        "prize waits for the approval of the organization.",
    )
    raffle_sponsor_manager_ids = fields.Many2many(
        "res.users",
        "event_event_raffle_sponsor_manager_rel",
        "event_id",
        "user_id",
        string="Sponsorship managers",
        domain=[("share", "=", False)],
        help="Internal users notified of each prize a sponsor submits for "
        "this event. Empty notifies the event's responsible user.",
    )
    raffle_sponsor_thanks_count = fields.Integer(
        string="Winners of sponsored prizes",
        compute="_compute_raffle_sponsor_thanks_count",
        help="Winners holding a sponsored prize (reserved, shipped or "
        "handed over): Thank the Sponsors is offered once there is one.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events.sudo().raffle_sponsor_manager_ids._raffle_sponsor_sync_group()
        return events

    def write(self, vals):
        if "raffle_sponsor_manager_ids" not in vals:
            return super().write(vals)
        before = self.sudo().raffle_sponsor_manager_ids
        result = super().write(vals)
        (
            before | self.sudo().raffle_sponsor_manager_ids
        )._raffle_sponsor_sync_group()
        return result

    def unlink(self):
        users = self.sudo().raffle_sponsor_manager_ids
        result = super().unlink()
        users._raffle_sponsor_sync_group()
        return result

    def _compute_raffle_sponsor_thanks_count(self):
        for event in self:
            event.raffle_sponsor_thanks_count = (
                len(event._raffle_sponsor_thanks_draws()) if event.id else 0
            )

    def _raffle_sponsor_managed_by(self, user):
        """Whether `user` is a sponsorship manager of every event of self.

        False for an empty recordset: a prize offered to any event has no
        sponsorship manager.
        """
        events = self.sudo()
        return bool(events) and all(
            user in event.raffle_sponsor_manager_ids for event in events
        )

    @api.model
    def _raffle_sponsor_events(self, partner):
        """Events where `partner` may submit prizes, as superuser.

        The events that are sponsor-managed and not ended, with a sponsor
        registration that is not cancelled whose sponsor contact is
        `partner` or another contact of its commercial entity. The sponsor
        contact is the one the organization set on the registration, never
        a contact matched by its email alone (see
        event.registration._raffle_sponsor_contact()).
        """
        if not partner:
            return self.sudo().browse()
        commercial = partner.commercial_partner_id
        registrations = (
            self.env["event.registration"]
            .sudo()
            .search(
                [
                    ("is_raffle_sponsor", "=", True),
                    ("state", "!=", "cancel"),
                    ("raffle_sponsor_partner_id", "child_of", commercial.id),
                    ("event_id.raffle_sponsor_managed", "=", True),
                    ("event_id.date_end", ">", fields.Datetime.now()),
                ]
            )
        )
        return registrations.event_id.sorted(lambda e: (e.date_begin, e.id))

    def _raffle_sponsor_recipients(self):
        """Contacts notified of a prize submitted for this event: the
        sponsorship managers, else the responsible user."""
        self.ensure_one()
        event = self.sudo()
        users = event.raffle_sponsor_manager_ids or event.user_id
        return users.filtered("active").partner_id

    # ------------------------------------------------------------------
    # Thank the sponsors
    # ------------------------------------------------------------------

    def _raffle_sponsor_check_thanks(self):
        """Raise AccessError unless the current user may thank the sponsors
        of these events: an event user, or a sponsorship manager of each
        event."""
        if self.env.su:
            return
        user = self.env.user
        if user.has_group("event.group_event_user"):
            self.check_access("read")
            return
        for event in self:
            if not event._raffle_sponsor_managed_by(user):
                raise AccessError(
                    _(
                        "Only the event users and the sponsorship managers "
                        "of %s thank its sponsors.",
                        event.sudo().name,
                    )
                )

    def _raffle_sponsor_thanks_draws(self, sponsor=None):
        """Draws of this event's raffles whose winner holds a sponsored
        prize (reserved, shipped or handed over), as superuser, in the
        order of the draws. With `sponsor`, the prizes of its commercial
        entity only; without it, the prizes that have a sponsor."""
        self.ensure_one()
        domain = [
            ("raffle_id.event_id", "=", self.id),
            ("claim_state", "in", THANKS_CLAIM_STATES),
            ("prize_product_id", "!=", False),
        ]
        if sponsor:
            domain.append(
                (
                    "prize_product_id.product_tmpl_id.raffle_sponsor_id",
                    "child_of",
                    sponsor.commercial_partner_id.id,
                )
            )
        else:
            domain.append(
                (
                    "prize_product_id.product_tmpl_id.raffle_sponsor_id",
                    "!=",
                    False,
                )
            )
        return (
            self.env["event.raffle.draw"]
            .sudo()
            .with_context(active_test=False)
            .search(domain, order="date, sequence, id")
        )

    def action_open_raffle_sponsor_thank_wizard(self):
        """Open Thank the Sponsors on this event, with one line per
        sponsor whose prizes have a winner."""
        self.ensure_one()
        self._raffle_sponsor_check_thanks()
        wizard = self.env["event.raffle.sponsor.thank.wizard"].create(
            {"event_id": self.id}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Thank the Sponsors"),
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }
