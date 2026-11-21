# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.modules.migration import load_script
from odoo.tests.common import TransactionCase, new_test_user

NOTIFY = "notify_winner_message"
ANNOUNCE = "announce_channel_message"
# Per field: the previous defaults, then the current ones.
TEXTS = {
    NOTIFY: {
        "old_en": "You won a prize, come and claim it!",
        "old_fr": "Vous avez reçu un prix, venez le réclamer!",
        "en": "You won a prize, come and claim it! {link}",
        "fr": "Vous avez gagné un prix, venez le réclamer ! {lien}",
    },
    ANNOUNCE: {
        "old_en": "Draw #{number}: {winner} won! ({prize})",
        "old_fr": "Tir #{numéro} : {gagnant} a gagné ! ({prix})",
        "en": "Draw #{number}: {winner} won! ({prize}) {link}",
        "fr": "Tir #{numéro} : {gagnant} a gagné ! ({prix}) {lien}",
    },
}


class TestRaffleMessageMigration(TransactionCase):
    """Upgrade to 18.0.1.6.0: the default messages end with the link."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_CA")
        cls.french = new_test_user(
            cls.env,
            login="raffle_migration_french",
            groups="base.group_user,event.group_event_user",
            name="Migration French",
            lang="fr_CA",
        )
        cls.french_company = cls.env["res.company"].create(
            {"name": "Migration French Company"}
        )
        cls.french_company.partner_id.lang = "fr_CA"

    def _raffle(self, field, text, user=None, **vals):
        Raffle = self.env["event.raffle"]
        if user:
            Raffle = Raffle.with_user(user)
        raffle = Raffle.create(dict({"name": text[:20]}, **vals))
        self.env.flush_all()
        self.env.cr.execute(
            f"UPDATE event_raffle SET {field} = %s WHERE id = %s",
            [text, raffle.id],
        )
        return raffle

    def _migrate(self):
        script = load_script(
            "event_raffle/migrations/18.0.1.6.0/post-migration.py",
            "event_raffle_post_migration_18_0_1_6_0",
        )
        script.migrate(self.env.cr, "18.0.1.5.0")

    def test_the_column_default_of_an_upgrade_is_the_en_us_source(self):
        Raffle = self.env["event.raffle"]
        upgrade_env = self.env(user=self.env.ref("base.user_root"), context={})
        for field, texts in TEXTS.items():
            default = (
                Raffle.with_env(upgrade_env)
                ._fields[field]
                .default(Raffle.with_env(upgrade_env))
            )
            self.assertEqual(default, texts["en"], field)

    def test_previous_defaults_get_the_link_in_their_language(self):
        for field, texts in TEXTS.items():
            old_en = self._raffle(field, texts["old_en"])
            old_fr = self._raffle(field, texts["old_fr"], user=self.french)
            # Written in English by a user now in French: stays English.
            old_en_by_french = self._raffle(
                field, texts["old_en"], user=self.french
            )
            # Written in French by a user now in English: stays French.
            old_fr_by_english = self._raffle(field, texts["old_fr"])
            # Column added by this upgrade: the en_US source, translated.
            added_french = self._raffle(field, texts["en"], user=self.french)
            added_orphan = self._raffle(
                field, texts["en"], company_id=self.french_company.id
            )
            self.env.cr.execute(
                "UPDATE event_raffle SET create_uid = NULL WHERE id = %s",
                [added_orphan.id],
            )
            added_english = self._raffle(field, texts["en"])
            edited = self._raffle(field, texts["old_fr"] + " Merci.")
            current_fr = self._raffle(field, texts["fr"], user=self.french)
            self.env.invalidate_all()

            self._migrate()

            expected = {
                old_en: texts["en"],
                old_fr: texts["fr"],
                old_en_by_french: texts["en"],
                old_fr_by_english: texts["fr"],
                added_french: texts["fr"],
                added_orphan: texts["fr"],
                added_english: texts["en"],
                edited: texts["old_fr"] + " Merci.",
                current_fr: texts["fr"],
            }
            for raffle, text in expected.items():
                self.assertEqual(raffle[field], text, (field, raffle.name))

    def test_the_migrated_defaults_render_without_a_link(self):
        raffle = self._raffle(NOTIFY, TEXTS[NOTIFY]["old_fr"])
        self._raffle(ANNOUNCE, TEXTS[ANNOUNCE]["old_fr"])
        self.env.invalidate_all()
        self._migrate()
        draw = self.env["event.raffle.draw"].create(
            {"raffle_id": raffle.id, "sequence": 3, "winner_name": "Zoé"}
        )
        self.assertEqual(
            draw._message_render(raffle[NOTIFY]),
            "Vous avez gagné un prix, venez le réclamer !",
        )
        self.assertEqual(
            draw._message_render(TEXTS[ANNOUNCE]["fr"]),
            "Tir #3 : Zoé a gagné !",
        )
