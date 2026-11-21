# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import pytz

from odoo import api, fields, models
from odoo.tools import format_date, format_time

from .event_raffle_draw import PUBLIC_CHOSEN_STATES


class EventEvent(models.Model):
    """Public winners page of an event.

    The page lists the draws of the event's raffles that have a winner,
    whatever their claim state, newest first, grouped by the hour of the
    draw in the event's time zone. Each line holds public fields only: the
    winner's public name (see event.raffle.draw._prize_public_name()), the
    prize or what became of it (see _prize_public_status(): to choose,
    declined, not chosen), the sponsor of a chosen prize with a link, and
    the token category.
    """

    _inherit = "event.event"

    raffle_winners_published = fields.Boolean(
        string="Publish the winners page",
        help="Anyone may read the page of the event's raffle winners, by "
        "hour: their public name, the prize or that it is still to choose, "
        "declined or not chosen, its sponsor and the token category.",
    )
    raffle_winners_url = fields.Char(
        string="Winners page",
        compute="_compute_raffle_winners_url",
    )

    @api.depends("raffle_winners_published")
    def _compute_raffle_winners_url(self):
        for event in self:
            event.raffle_winners_url = (
                f"{event.get_base_url()}{event._raffle_winners_path()}"
                if event.id and event.raffle_winners_published
                else False
            )

    def _raffle_winners_path(self):
        self.ensure_one()
        slug = self.env["ir.http"]._slug(self)
        return f"/raffle/winners/{slug}"

    def _raffle_winners_draws(self):
        """Draws the winners page lists, newest first, as superuser.

        The draws of the event's raffles that name a winner, whatever the
        claim state; a draw whose prize is reserved, shipped or handed
        over stays listed when its winner's name is gone. A draw marked
        absent is left out: the draw went to someone else. A test raffle
        lists its chosen prizes only. An event of a company lists the
        raffles of that company and those without one.
        """
        self.ensure_one()
        domain = [
            ("raffle_id.event_id", "=", self.id),
            ("is_absent", "=", False),
            "|",
            ("claim_state", "in", PUBLIC_CHOSEN_STATES),
            "&",
            ("raffle_id.is_test", "=", False),
            "|",
            ("winner_participant_id", "!=", False),
            ("winner_name", "!=", False),
        ]
        if self.company_id:
            domain.append(
                ("raffle_id.company_id", "in", [False, self.company_id.id])
            )
        return (
            self.env["event.raffle.draw"]
            .sudo()
            .search(domain, order="date desc, id desc")
        )

    def _raffle_winners_data(self):
        """Public content of the winners page, in the current language.

        Returns {"groups": [{"key", "label", "winners": [...]}], "count",
        "updated", "updated_label"}. A group holds the draws of one hour
        of the event's time zone; its key is the start of that hour in ISO
        8601 with the zone offset, and its label the time, preceded by the
        date when the draws span several days. A winner is {"id", "name",
        "prize", "status", "sponsor", "sponsor_url", "category"} (see
        event.raffle.draw._prize_public_line()): the JSON endpoint sends
        this dict as it is, so it holds nothing else.
        """
        self.ensure_one()
        tz_name = self.date_tz or "UTC"
        tz = pytz.timezone(tz_name)
        groups = {}
        for draw in self._raffle_winners_draws():
            local = pytz.utc.localize(draw.date).astimezone(tz)
            hour = local.replace(minute=0, second=0, microsecond=0)
            group = groups.setdefault(
                hour, {"key": hour.isoformat(), "winners": []}
            )
            group["winners"].append(draw._prize_public_line())
        several_days = len({hour.date() for hour in groups}) > 1
        for hour, group in groups.items():
            label = format_time(self.env, hour.time(), time_format="short")
            if several_days:
                label = f"{format_date(self.env, hour.date())}, {label}"
            group["label"] = label
        now = pytz.utc.localize(fields.Datetime.now()).astimezone(tz)
        return {
            "groups": list(groups.values()),
            "count": sum(len(g["winners"]) for g in groups.values()),
            "updated": now.isoformat(),
            "updated_label": format_time(
                self.env, now.time(), time_format="short"
            ),
        }
