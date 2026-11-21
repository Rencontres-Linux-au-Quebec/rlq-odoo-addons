# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import pytz

from odoo import api, fields, models
from odoo.tools import email_normalize, format_date


class EventRaffleSponsorThanks(models.Model):
    """The thank-you email of one sponsor for one event.

    One record per event and sponsor (the commercial entity of the prizes'
    sponsor), created when the Thank the Sponsors wizard lists the sponsor.
    It is the record the email template renders, and it keeps the date of
    the last email sent, which the wizard shows as a warning. Its values
    are read as superuser by the methods below, once the wizard has checked
    the user: the email names the winners by their public name only (see
    event.raffle.draw._prize_public_name()), never by their email, phone
    or photo.
    """

    _name = "event.raffle.sponsor.thanks"
    _description = "Thank-you Email of a Sponsor"
    _rec_name = "sponsor_id"
    _order = "event_id, sponsor_id"

    event_id = fields.Many2one(
        "event.event",
        string="Event",
        required=True,
        readonly=True,
        ondelete="cascade",
        index=True,
    )
    sponsor_id = fields.Many2one(
        "res.partner",
        string="Sponsor",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(related="event_id.company_id")
    sent_date = fields.Datetime(string="Thanked on", readonly=True)
    sent_by_id = fields.Many2one(
        "res.users", string="Thanked by", readonly=True
    )
    sent_winner_count = fields.Integer(
        string="Winners in the email", readonly=True
    )

    _sql_constraints = [  # noqa: RUF012
        (
            "event_sponsor_unique",
            "UNIQUE(event_id, sponsor_id)",
            "An event thanks each sponsor through one record.",
        ),
    ]

    @api.model
    def _raffle_get(self, event, sponsor):
        """The record of `event` and the commercial entity of `sponsor`,
        created when missing, as superuser."""
        Thanks = self.sudo()
        sponsor = sponsor.commercial_partner_id
        thanks = Thanks.search(
            [("event_id", "=", event.id), ("sponsor_id", "=", sponsor.id)],
            limit=1,
        )
        return thanks or Thanks.create(
            {"event_id": event.id, "sponsor_id": sponsor.id}
        )

    def _raffle_draws(self):
        """Draws of the event whose winner holds a prize of the sponsor."""
        self.ensure_one()
        thanks = self.sudo()
        return thanks.event_id._raffle_sponsor_thanks_draws(thanks.sponsor_id)

    def _raffle_recipients(self):
        """Who receives the email, as superuser.

        The sponsor contacts of the event (raffle_sponsor_partner_id of
        its sponsor registrations that are not cancelled, under the
        sponsor's commercial entity) that have an email, in registration
        order; else the sponsor itself when it has an email; else nobody.
        """
        self.ensure_one()
        thanks = self.sudo()
        registrations = (
            self.env["event.registration"]
            .sudo()
            .search(
                [
                    ("event_id", "=", thanks.event_id.id),
                    ("is_raffle_sponsor", "=", True),
                    ("state", "!=", "cancel"),
                    (
                        "raffle_sponsor_partner_id",
                        "child_of",
                        thanks.sponsor_id.id,
                    ),
                ],
                order="id",
            )
        )
        partners = registrations.raffle_sponsor_partner_id.filtered(
            lambda p: email_normalize(p.email or "")
        )
        sponsor = thanks.sponsor_id
        if not partners and email_normalize(sponsor.email or ""):
            partners = sponsor
        return partners

    # ------------------------------------------------------------------
    # Values of the email template
    # ------------------------------------------------------------------

    def _raffle_thanks_partner_to(self):
        """Ids of the recipients, as the template's partner_to reads them."""
        self.ensure_one()
        return ",".join(str(pid) for pid in self._raffle_recipients().ids)

    def _raffle_thanks_lang(self):
        """Language of the email: the first recipient's, else the
        sponsor's."""
        self.ensure_one()
        recipients = self._raffle_recipients()
        return recipients[:1].lang or self.sudo().sponsor_id.lang or False

    def _raffle_thanks_email_from(self):
        """Sender of the email: the email of the event's company, else the
        current user's, else the company's catch-all address."""
        self.ensure_one()
        company = self.sudo().event_id.company_id or self.env.company
        return (
            company.email_formatted
            or self.env.user.email_formatted
            or company.catchall_formatted
            or ""
        )

    def _raffle_mode_label(self, draw):
        """How the prize of `draw` reached its winner, in the current
        language."""
        if draw.claim_state == "reserved":
            return self.env._("Reserved")
        if draw.claim_state == "shipped" or draw.prize_shipped_date:
            return self.env._("Shipped")
        if draw.prize_virtual:
            return self.env._("Sent by email")
        return self.env._("Handed over on site")

    def _raffle_thanks_values(self):
        """What the email says, in the current language.

        Returns {"sponsor", "event", "count", "winners"}; a winner is
        {"name", "prize", "category", "date", "mode"}: the public name,
        the prize, its token category, the date of the draw in the event's
        time zone and how the prize reached the winner. Nothing else of
        the winner is read.
        """
        self.ensure_one()
        thanks = self.sudo()
        event = thanks.event_id
        tz = pytz.timezone(event.date_tz or "UTC")
        winners = []
        for draw in thanks._raffle_draws():
            product = draw.prize_product_id.with_context(
                display_default_code=False
            )
            band = product.product_tmpl_id.raffle_band_id or draw.band_id
            date = (
                pytz.utc.localize(draw.date).astimezone(tz).date()
                if draw.date
                else False
            )
            winners.append(
                {
                    "name": draw._prize_public_name(),
                    "prize": product.display_name,
                    "category": band.name or "",
                    "date": format_date(self.env, date) if date else "",
                    "mode": self._raffle_mode_label(draw),
                }
            )
        return {
            "sponsor": thanks.sponsor_id.name,
            "event": event.name,
            "count": len(winners),
            "winners": winners,
        }
