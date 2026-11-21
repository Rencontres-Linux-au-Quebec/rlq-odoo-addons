# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api

# For each message field: the default method of event.raffle that gives the
# current text, and the previous defaults by language. The previous
# defaults are the texts of this module before the {link} placeholder.
MESSAGES = {
    "notify_winner_message": (
        "_default_notify_winner_message",
        {
            "en_US": "You won a prize, come and claim it!",
            "fr_CA": "Vous avez reçu un prix, venez le réclamer!",
        },
    ),
    "announce_channel_message": (
        "_default_announce_channel_message",
        {
            "en_US": "Draw #{number}: {winner} won! ({prize})",
            "fr_CA": "Tir #{numéro} : {gagnant} a gagné ! ({prix})",
        },
    ),
}

# Language of each raffle: its creator's, else its company's, else en_US.
RAFFLE_LANG_QUERY = """
    SELECT COALESCE(creator.lang, company_partner.lang, 'en_US') AS lang,
           array_agg(raffle.id)
      FROM event_raffle raffle
      LEFT JOIN res_users creator_user ON creator_user.id = raffle.create_uid
      LEFT JOIN res_partner creator ON creator.id = creator_user.partner_id
      LEFT JOIN res_company company ON company.id = raffle.company_id
      LEFT JOIN res_partner company_partner
             ON company_partner.id = company.partner_id
     WHERE raffle.{field} = %s
     GROUP BY 1
"""


def _rewrite(cr, field, message, raffle_ids):
    cr.execute(
        f"UPDATE event_raffle SET {field} = %s WHERE id = ANY(%s)",
        [message, raffle_ids],
    )


def migrate(cr, version):
    """Give the existing raffles the default messages that end with {link}.

    A message still holding a previous default, in English or in French,
    becomes the current default in that same language; an edited message
    stays as it is. A message holding the current en_US source came from
    an upgrade that added its column after this version's code was in
    place, from the field default evaluated without a language: it gets the
    language of the raffle creator, or of its company when the creator is
    gone, as the earlier migrations do. A language without a translation
    keeps the en_US source.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Raffle = env["event.raffle"]
    for field, (method, previous) in MESSAGES.items():
        # The current source first: the rows rewritten below in en_US hold
        # it too, and keep their language.
        source = getattr(Raffle, method)()
        cr.execute(RAFFLE_LANG_QUERY.format(field=field), [source])
        for lang, raffle_ids in cr.fetchall():
            message = getattr(Raffle.with_context(lang=lang), method)()
            if message != source:
                _rewrite(cr, field, message, raffle_ids)
        for lang, text in previous.items():
            cr.execute(
                f"SELECT array_agg(id) FROM event_raffle WHERE {field} = %s",
                [text],
            )
            raffle_ids = cr.fetchone()[0]
            if raffle_ids:
                current = getattr(Raffle.with_context(lang=lang), method)()
                _rewrite(cr, field, current, raffle_ids)
    Raffle.invalidate_model(list(MESSAGES))
