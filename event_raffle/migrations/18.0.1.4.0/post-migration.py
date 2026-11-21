# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api

# The en_US source of the default notification message.
SOURCE = "You won a prize, come and claim it!"


def migrate(cr, version):
    """Translate the default notification message of the existing raffles.

    The upgrade fills the new notify_winner_message column of the existing
    rows from the field default, evaluated in an env without a language: each
    row holds the en_US source. A row still holding it gets the message in
    the language of the raffle creator, or of its company when the creator is
    gone, as a raffle created in that language would. A row whose language
    has no translation keeps the source.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        SELECT COALESCE(creator.lang, company_partner.lang, 'en_US') AS lang,
               array_agg(raffle.id)
          FROM event_raffle raffle
          LEFT JOIN res_users creator_user ON creator_user.id = raffle.create_uid
          LEFT JOIN res_partner creator
                 ON creator.id = creator_user.partner_id
          LEFT JOIN res_company company ON company.id = raffle.company_id
          LEFT JOIN res_partner company_partner
                 ON company_partner.id = company.partner_id
         WHERE raffle.notify_winner_message = %s
         GROUP BY 1
        """,
        [SOURCE],
    )
    Raffle = env["event.raffle"]
    for lang, raffle_ids in cr.fetchall():
        message = Raffle.with_context(
            lang=lang
        )._default_notify_winner_message()
        if message != SOURCE:
            cr.execute(
                "UPDATE event_raffle SET notify_winner_message = %s"
                " WHERE id = ANY(%s)",
                [message, raffle_ids],
            )
    Raffle.invalidate_model(["notify_winner_message"])
