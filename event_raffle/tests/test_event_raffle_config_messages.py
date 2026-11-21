# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import etree

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase, new_test_user

NOTIFY_EN = "You won a prize, come and claim it! {link}"
NOTIFY_FR = "Vous avez gagné un prix, venez le réclamer ! {lien}"
ANNOUNCE_EN = "Draw #{number}: {winner} won! ({prize}) {link}"
ANNOUNCE_FR = "Tir #{numéro} : {gagnant} a gagné ! ({prix}) {lien}"
NOTIFY_CUSTOM = "Bravo {gagnant}, passez au kiosque ! {lien}"
ANNOUNCE_CUSTOM = "{gagnant} remporte le tir {numéro}"


class TestRaffleConfigMessages(TransactionCase):
    """Messages section of the raffle default settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                mail_create_nolog=True,
                mail_notrack=True,
                no_reset_password=True,
            )
        )
        cls.config = cls.env.ref("event_raffle.raffle_config_singleton")
        cls.channel = cls.env["discuss.channel"].create(
            {"name": "tirages-soiree", "channel_type": "channel"}
        )
        cls.other_channel = cls.env["discuss.channel"].create(
            {"name": "tirages-autre", "channel_type": "channel"}
        )
        cls.organizer = new_test_user(
            cls.env,
            login="raffle_config_messages_organizer",
            groups="base.group_user,event.group_event_user",
            name="Config Organizer",
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Soirée test",
                "date_begin": "2026-01-01 09:00:00",
                "date_end": "2026-01-01 18:00:00",
            }
        )

    def _set_all(self):
        self.config.write(
            {
                "default_notify_winner_auto": True,
                "default_notify_winner_message": NOTIFY_CUSTOM,
                "default_announce_channel_auto": True,
                "default_announce_channel_id": self.channel.id,
                "default_announce_channel_message": ANNOUNCE_CUSTOM,
            }
        )

    def _assert_takes_all(self, raffle):
        self.assertTrue(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, NOTIFY_CUSTOM)
        self.assertTrue(raffle.announce_channel_auto)
        self.assertEqual(raffle.announce_channel_id, self.channel)
        self.assertEqual(raffle.announce_channel_message, ANNOUNCE_CUSTOM)

    def _env_in(self, lang):
        self.env["res.lang"]._activate_lang(lang)
        return self.env(context=dict(self.env.context, lang=lang))

    # Defaults of a new raffle

    def test_settings_are_off_and_empty_by_default(self):
        self.assertFalse(self.config.default_notify_winner_auto)
        self.assertFalse(self.config.default_notify_winner_message)
        self.assertFalse(self.config.default_announce_channel_auto)
        self.assertFalse(self.config.default_announce_channel_id)
        self.assertFalse(self.config.default_announce_channel_message)
        raffle = self.env["event.raffle"].create({"name": "Plain"})
        self.assertFalse(raffle.notify_winner_auto)
        self.assertFalse(raffle.announce_channel_auto)
        self.assertFalse(raffle.announce_channel_id)

    def test_new_raffle_takes_each_value(self):
        self._set_all()
        raffle = (
            self.env["event.raffle"]
            .with_user(self.organizer)
            .create({"name": "Code"})
        )
        self._assert_takes_all(raffle)

    def test_each_value_applies_alone(self):
        Raffle = self.env["event.raffle"]
        self.config.default_notify_winner_auto = True
        raffle = Raffle.create({"name": "Notify only"})
        self.assertTrue(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, NOTIFY_EN)
        self.assertFalse(raffle.announce_channel_auto)
        self.config.default_announce_channel_id = self.channel
        raffle = Raffle.create({"name": "Channel only"})
        self.assertEqual(raffle.announce_channel_id, self.channel)
        self.assertFalse(raffle.announce_channel_auto)
        self.config.write(
            {
                "default_notify_winner_message": NOTIFY_CUSTOM,
                "default_announce_channel_message": ANNOUNCE_CUSTOM,
            }
        )
        raffle = Raffle.create({"name": "Messages"})
        self.assertEqual(raffle.notify_winner_message, NOTIFY_CUSTOM)
        self.assertEqual(raffle.announce_channel_message, ANNOUNCE_CUSTOM)

    def test_backend_form_shows_the_values(self):
        self._set_all()
        form = Form(self.env["event.raffle"].with_user(self.organizer))
        self.assertTrue(form.notify_winner_auto)
        self.assertEqual(form.notify_winner_message, NOTIFY_CUSTOM)
        self.assertTrue(form.announce_channel_auto)
        self.assertEqual(form.announce_channel_id, self.channel)
        self.assertEqual(form.announce_channel_message, ANNOUNCE_CUSTOM)
        form.name = "Form"
        self._assert_takes_all(form.save())

    def test_raffle_started_from_the_event_takes_the_values(self):
        self._set_all()
        action = self.event.with_user(self.organizer).action_start_raffle()
        wizard = (
            self.env["event.raffle.start.wizard"]
            .with_user(self.organizer)
            .with_context(**action["context"])
            .create({})
        )
        result = wizard.action_start()
        self._assert_takes_all(
            self.env["event.raffle"].browse(result["res_id"])
        )

    def test_explicit_values_and_context_defaults_win(self):
        self._set_all()
        Raffle = self.env["event.raffle"]
        raffle = Raffle.create(
            {
                "name": "Explicit",
                "notify_winner_auto": False,
                "notify_winner_message": "Message choisi",
                "announce_channel_auto": True,
                "announce_channel_id": self.other_channel.id,
                "announce_channel_message": "Annonce choisie",
            }
        )
        self.assertFalse(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, "Message choisi")
        self.assertEqual(raffle.announce_channel_id, self.other_channel)
        self.assertEqual(raffle.announce_channel_message, "Annonce choisie")
        raffle = Raffle.with_context(
            default_notify_winner_auto=False,
            default_notify_winner_message="Contexte",
            default_announce_channel_auto=False,
            default_announce_channel_id=self.other_channel.id,
            default_announce_channel_message="Annonce contexte",
        ).create({"name": "Context"})
        self.assertFalse(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, "Contexte")
        self.assertFalse(raffle.announce_channel_auto)
        self.assertEqual(raffle.announce_channel_id, self.other_channel)
        self.assertEqual(raffle.announce_channel_message, "Annonce contexte")

    def test_empty_message_gives_the_standard_one(self):
        self._set_all()
        for empty in (False, "", "  \n "):
            self.config.write(
                {
                    "default_notify_winner_message": empty,
                    "default_announce_channel_message": empty,
                }
            )
            for lang, notify, announce in (
                ("en_US", NOTIFY_EN, ANNOUNCE_EN),
                ("fr_CA", NOTIFY_FR, ANNOUNCE_FR),
            ):
                raffle = self._env_in(lang)["event.raffle"].create(
                    {"name": "Standard"}
                )
                self.assertTrue(raffle.notify_winner_auto)
                self.assertEqual(raffle.notify_winner_message, notify)
                self.assertEqual(raffle.announce_channel_message, announce)

    def test_existing_raffles_keep_their_values(self):
        raffle = self.env["event.raffle"].create({"name": "Before"})
        self._set_all()
        raffle.invalidate_recordset()
        self.assertFalse(raffle.notify_winner_auto)
        self.assertEqual(raffle.notify_winner_message, NOTIFY_EN)
        self.assertFalse(raffle.announce_channel_auto)
        self.assertFalse(raffle.announce_channel_id)
        self.assertEqual(raffle.announce_channel_message, ANNOUNCE_EN)
        taken = self.env["event.raffle"].create({"name": "Taken"})
        self.config.write(
            {
                "default_notify_winner_auto": False,
                "default_notify_winner_message": "Autre",
                "default_announce_channel_id": self.other_channel.id,
            }
        )
        taken.invalidate_recordset()
        self._assert_takes_all(taken)

    # The channel and its announcement

    def test_archived_channel_is_not_applied(self):
        self._set_all()
        self.channel.action_archive()
        raffle = self.env["event.raffle"].create({"name": "Archived"})
        self.assertFalse(raffle.announce_channel_id)
        # No channel to post in: the announcement stays off.
        self.assertFalse(raffle.announce_channel_auto)
        self.assertEqual(raffle.announce_channel_message, ANNOUNCE_CUSTOM)
        self.assertTrue(raffle.notify_winner_auto)

    def test_deleted_channel_is_not_applied(self):
        self._set_all()
        self.channel.unlink()
        self.config.invalidate_recordset()
        self.assertFalse(self.config.default_announce_channel_id)
        raffle = self.env["event.raffle"].create({"name": "Deleted"})
        self.assertFalse(raffle.announce_channel_id)
        self.assertFalse(raffle.announce_channel_auto)

    def test_group_chat_of_a_member_is_applied(self):
        """A group chat is the default channel of the raffles that its
        members create (a user who cannot read it gets none, see
        TestRaffleAnnounce)."""
        group = self.env["discuss.channel"].create(
            {"name": "tirages-prive", "channel_type": "group"}
        )
        group.add_members(partner_ids=self.organizer.partner_id.ids)
        self.config.write(
            {
                "default_announce_channel_auto": True,
                "default_announce_channel_id": group.id,
            }
        )
        raffle = (
            self.env["event.raffle"]
            .with_user(self.organizer)
            .create({"name": "Private"})
        )
        self.assertEqual(raffle.announce_channel_id, group)
        self.assertTrue(raffle.announce_channel_auto)

    def test_announcing_by_default_needs_a_channel(self):
        with self.assertRaises(ValidationError):
            self.config.default_announce_channel_auto = True
        self.config.write(
            {
                "default_announce_channel_auto": True,
                "default_announce_channel_id": self.channel.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.config.default_announce_channel_id = False

    def test_draws_use_the_raffle_values(self):
        self._set_all()
        raffle = self.env["event.raffle"].create(
            {"name": "Soirée", "notify_winner_auto": False}
        )
        # Later settings changes do not reach the raffle's draws.
        self.config.write(
            {
                "default_announce_channel_id": self.other_channel.id,
                "default_announce_channel_message": "Autre {gagnant}",
            }
        )
        self.env["event.raffle.participant"].create(
            {"raffle_id": raffle.id, "name": "Alice"}
        )
        raffle.with_user(self.organizer).action_draw_next()
        posts = self.channel.message_ids.filtered(
            lambda m: m.message_type == "comment"
        )
        self.assertEqual(len(posts), 1)
        self.assertIn("Alice remporte le tir 1", str(posts.body))
        self.assertFalse(
            self.other_channel.message_ids.filtered(
                lambda m: m.message_type == "comment"
            )
        )

    # Form and labels

    def test_settings_form_has_the_messages_section(self):
        Config = self.env["event.raffle.config"]
        arch = etree.fromstring(Config.get_view(False, "form")["arch"])
        (section,) = arch.xpath("//group[@name='messages']")
        names = section.xpath(".//field/@name")
        self.assertEqual(
            names,
            [
                "default_notify_winner_auto",
                "default_notify_winner_message",
                "default_announce_channel_auto",
                "default_announce_channel_id",
                "default_announce_channel_message",
            ],
        )
        (channel,) = section.xpath(
            ".//field[@name='default_announce_channel_id']"
        )
        self.assertEqual(
            channel.get("required"), "default_announce_channel_auto"
        )

    def test_settings_form_requires_the_channel_when_announcing(self):
        form = Form(self.config)
        form.default_announce_channel_auto = True
        with self.assertRaises(AssertionError):
            form.save()

    def test_labels_in_french(self):
        fr = self._env_in("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle"], ["fr_CA"], overwrite=True
        )
        labels = {
            "default_notify_winner_auto": "Notifier le gagnant automatiquement",
            "default_notify_winner_message": "Message notification",
            "default_announce_channel_auto": (
                "Annoncer chaque tir dans un canal de discussion"
            ),
            "default_announce_channel_id": "Canal de discussion",
            "default_announce_channel_message": "Message canal",
        }
        described = fr["event.raffle.config"].fields_get(list(labels))
        for name, label in labels.items():
            self.assertEqual(described[name]["string"], label)
            self.assertIn("nouveau", described[name]["help"])
        arch = fr["event.raffle.config"].get_view(False, "form")["arch"]
        self.assertIn('string="Messages"', arch)
        self.assertIn(NOTIFY_FR, arch)
        self.assertIn(ANNOUNCE_FR, arch)
