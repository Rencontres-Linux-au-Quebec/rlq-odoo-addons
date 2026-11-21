# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import Command, api, models

SPONSORSHIP_GROUP = (
    "event_raffle_prize_sponsor.group_raffle_sponsorship_manager"
)


class ResUsers(models.Model):
    """Membership of the sponsorship manager group.

    The group holds the internal users listed in the sponsorship managers
    (event.event.raffle_sponsor_manager_ids) of at least one event,
    archived events included. The events call _raffle_sponsor_sync_group()
    on the users they add or remove; a portal user never gets the group.
    The group grants menus and read access only: approving a prize or
    thanking the sponsors checks the events of the record.
    """

    _inherit = "res.users"

    def _raffle_sponsor_sync_group(self):
        """Add these users to the sponsorship manager group, or remove
        them from it, from the events that list them now."""
        users = self.sudo().with_context(active_test=False).exists()
        if not users:
            return
        group = self.env.ref(SPONSORSHIP_GROUP).sudo()
        events = (
            self.env["event.event"]
            .sudo()
            .with_context(active_test=False)
            .search([("raffle_sponsor_manager_ids", "in", users.ids)])
        )
        listed = events.raffle_sponsor_manager_ids
        commands = []
        for user in users:
            wanted = user in listed and not user.share
            if wanted and group not in user.groups_id:
                commands.append(Command.link(user.id))
            elif not wanted and group in user.groups_id:
                commands.append(Command.unlink(user.id))
        if commands:
            group.write({"users": commands})

    @api.model
    def _raffle_sponsor_sync_all_groups(self):
        """Sync every user listed on an event or in the group."""
        group = self.env.ref(SPONSORSHIP_GROUP).sudo()
        events = (
            self.env["event.event"]
            .sudo()
            .with_context(active_test=False)
            .search([("raffle_sponsor_manager_ids", "!=", False)])
        )
        (
            group.users | events.raffle_sponsor_manager_ids
        )._raffle_sponsor_sync_group()
        return True
