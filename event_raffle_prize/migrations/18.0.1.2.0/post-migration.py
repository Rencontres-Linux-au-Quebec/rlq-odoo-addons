# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from psycopg2.extras import Json

# xml id, old and new name by language, old and new sequence.
RENAMES = (
    (
        "token_category_gold",
        {
            "en_US": ("Tux Token Gold", "Prize Group A"),
            "fr_CA": ("Jeton Tux or", "Groupe de prix A"),
        },
        (3, 1),
    ),
    (
        "token_category_silver",
        {
            "en_US": ("Tux Token Silver", "Prize Group B"),
            "fr_CA": ("Jeton Tux argent", "Groupe de prix B"),
        },
        (2, 2),
    ),
    (
        "token_category_bronze",
        {
            "en_US": ("Tux Token Bronze", "Prize Group C"),
            "fr_CA": ("Jeton Tux bronze", "Groupe de prix C"),
        },
        (1, 3),
    ),
)


def migrate(cr, version):
    """Rename the default token categories and order them A to F.

    The categories are noupdate data: an upgrade creates the missing ones
    (D, E, F) but never rewrites A, B and C. A category whose en_US name,
    and fr_CA name when it has one, are both still the old default gets
    the new name in each of these languages; a name changed in either
    language marks a category as edited, and it keeps all its names. The
    sequence follows the same rule on its own: only an old default
    sequence is replaced. The translations loaded after this script do not
    overwrite a name already present in a language.
    """
    for xmlid, names, (old_sequence, new_sequence) in RENAMES:
        cr.execute(
            "SELECT res_id FROM ir_model_data"
            " WHERE module = 'event_raffle_prize' AND name = %s"
            " AND model = 'event.raffle.prize.band'",
            [xmlid],
        )
        row = cr.fetchone()
        if not row:
            continue
        band_id = row[0]
        (old_en, new_en), (old_fr, new_fr) = names["en_US"], names["fr_CA"]
        cr.execute(
            """
            UPDATE event_raffle_prize_band
               SET name = name || %s::jsonb
                   || CASE WHEN name ? 'fr_CA' THEN %s::jsonb
                           ELSE '{}'::jsonb END
             WHERE id = %s
               AND name->>'en_US' = %s
               AND COALESCE(name->>'fr_CA', %s) = %s
            """,
            [
                Json({"en_US": new_en}),
                Json({"fr_CA": new_fr}),
                band_id,
                old_en,
                old_fr,
                old_fr,
            ],
        )
        cr.execute(
            "UPDATE event_raffle_prize_band SET sequence = %s"
            " WHERE id = %s AND sequence = %s",
            [new_sequence, band_id, old_sequence],
        )
