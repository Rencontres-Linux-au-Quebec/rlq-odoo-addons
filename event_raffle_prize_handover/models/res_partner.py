# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models

PUBLIC_NAME_MAX_LENGTH = 64


class ResPartner(models.Model):
    """Public name of a raffle winner.

    The public pages of the raffle (the winners page, the web app) show a
    contact by its public name when it has one, else by its full name. The
    winner sets it from the prize pages or from /my/account, an event user
    from the draw or the contact.
    """

    _inherit = "res.partner"

    raffle_public_name = fields.Char(
        string="Public name",
        size=PUBLIC_NAME_MAX_LENGTH,
        help="Nickname shown instead of the full name on the public pages "
        "of the raffle, such as the winners page. Empty shows the full "
        "name.",
    )

    @api.model
    def _raffle_clean_public_name(self, value):
        """`value` with its blanks collapsed, cut to the maximum length.

        Returns False for an empty or blank value, which clears the public
        name.
        """
        if not isinstance(value, str):
            return False
        value = " ".join(value.split())[:PUBLIC_NAME_MAX_LENGTH].strip()
        return value or False

    def _raffle_public_display_name(self):
        """The name the public pages show: the public name, else the full
        name."""
        self.ensure_one()
        partner = self.sudo()
        return (partner.raffle_public_name or "").strip() or partner.name or ""

    def _raffle_set_public_name(self, value):
        """Write the cleaned `value` as the public name, as superuser.

        The caller decides who may change this contact's public name: the
        winner's prize pages, the portal account form and the draw form
        each check it before calling.
        """
        self.ensure_one()
        self.sudo().write(
            {"raffle_public_name": self._raffle_clean_public_name(value)}
        )
        return True
