# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

# The copy_strategy help before 18.0.1.2.0. Its French source served as its
# own translation, so a language loaded from fr_CA.po holds this exact text.
OLD_HELP = (
    "Qui entre dans le tirage. Les deux choix « sondage » ne gardent que les "
    "inscrits ayant répondu au questionnaire d'inscription de l'événement."
)


def migrate(cr, version):
    """Drop the translations of the copy_strategy help still holding the old
    text.

    An upgrade replaces the en_US value only, and loading the .po files then
    fills a language only where it holds no value yet, so a stale translation
    would stay. Once dropped, that loading, which runs after this script,
    writes the new text. A translation edited by hand differs from the old
    text and is kept.
    """
    cr.execute(
        """
        UPDATE ir_model_fields
           SET help = (
               SELECT jsonb_object_agg(lang, text)
                 FROM jsonb_each(help) AS translation(lang, text)
                WHERE lang = 'en_US' OR text <> to_jsonb(%s::text)
           )
         WHERE model = 'event.raffle.start.wizard'
           AND name = 'copy_strategy'
        """,
        [OLD_HELP],
    )
