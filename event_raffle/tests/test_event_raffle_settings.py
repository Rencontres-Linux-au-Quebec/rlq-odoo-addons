# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from lxml import etree

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools.safe_eval import safe_eval

# One value per raffle default, none of them the shipped default.
SETTINGS_VALUES = {
    "raffle_default_theme": "rave",
    "raffle_default_remove_winner": False,
    "raffle_default_spin_duration": 9.5,
    "raffle_default_spin_turns": 8,
    "raffle_default_pointer_angle": "90",
    "raffle_default_winner_celebration": "trumpet",
    "raffle_default_show_fireworks": False,
    "raffle_default_show_tux": True,
    "raffle_default_belly_logo": "fleur_de_lys",
    "raffle_default_tux_animation": "dance",
    "raffle_default_flag_text": "Libre comme l'air",
    "raffle_default_notify_winner_auto": True,
    "raffle_default_notify_winner_message": "Bravo {gagnant} ! {lien}",
    "raffle_default_announce_channel_auto": True,
    "raffle_default_announce_channel_message": "Tir {numéro} : {gagnant}",
}
# Raffle field filled by each default above.
RAFFLE_FIELDS = {
    "raffle_default_theme": "theme",
    "raffle_default_remove_winner": "remove_winner",
    "raffle_default_spin_duration": "spin_duration",
    "raffle_default_spin_turns": "spin_turns",
    "raffle_default_pointer_angle": "pointer_angle",
    "raffle_default_winner_celebration": "winner_celebration",
    "raffle_default_show_fireworks": "show_fireworks",
    "raffle_default_show_tux": "show_tux",
    "raffle_default_belly_logo": "belly_logo",
    "raffle_default_tux_animation": "tux_animation",
    "raffle_default_flag_text": "flag_text",
    "raffle_default_notify_winner_auto": "notify_winner_auto",
    "raffle_default_notify_winner_message": "notify_winner_message",
    "raffle_default_announce_channel_auto": "announce_channel_auto",
    "raffle_default_announce_channel_message": "announce_channel_message",
}


# After the install: an upgrade removes the records of the former form,
# menu and access rights only once every module is loaded.
@tagged("post_install", "-at_install")
class TestRaffleSettings(TransactionCase):
    """Raffle defaults in the general settings, app block "Raffle"."""

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
            {"name": "tirages-reglages", "channel_type": "channel"}
        )
        # A settings administrator without any event right.
        cls.admin = new_test_user(
            cls.env,
            login="raffle_settings_admin",
            groups="base.group_user,base.group_system",
            name="Settings Admin",
        )
        cls.manager = new_test_user(
            cls.env,
            login="raffle_settings_manager",
            groups="base.group_user,event.group_event_manager",
            name="Settings Event Manager",
        )
        cls.organizer = new_test_user(
            cls.env,
            login="raffle_settings_organizer",
            groups="base.group_user,event.group_event_user",
            name="Settings Organizer",
        )

    def _save(self, values, user=None):
        """Save the settings form with `values`, as `user`."""
        Settings = self.env["res.config.settings"]
        if user:
            Settings = Settings.with_user(user)
        settings = Settings.create(values)
        settings.execute()
        return settings

    # Values

    def test_settings_show_the_singleton_values(self):
        self.config.write(
            {
                "default_theme": "theatre",
                "default_spin_turns": 7,
                "default_announce_channel_id": self.channel.id,
                "default_flag_text": "Drapeau du jour",
            }
        )
        settings = self.env["res.config.settings"].create({})
        self.assertEqual(settings.raffle_config_id, self.config)
        self.assertEqual(settings.raffle_default_theme, "theatre")
        self.assertEqual(settings.raffle_default_spin_turns, 7)
        self.assertEqual(
            settings.raffle_default_announce_channel_id, self.channel
        )
        self.assertEqual(settings.raffle_default_flag_text, "Drapeau du jour")

    def test_settings_save_each_value_into_the_singleton(self):
        values = dict(
            SETTINGS_VALUES, raffle_default_announce_channel_id=self.channel.id
        )
        self._save(values, user=self.admin)
        for name, value in SETTINGS_VALUES.items():
            self.assertEqual(self.config[name[len("raffle_") :]], value, name)
        self.assertEqual(self.config.default_announce_channel_id, self.channel)
        raffle = (
            self.env["event.raffle"]
            .with_user(self.organizer)
            .create({"name": "Après réglages"})
        )
        for name, field in RAFFLE_FIELDS.items():
            self.assertEqual(raffle[field], SETTINGS_VALUES[name], name)
        self.assertEqual(raffle.announce_channel_id, self.channel)

    def test_settings_form_saves_like_the_web_client(self):
        # The form sends every field of the view, changed or not.
        with Form(self.env["res.config.settings"].with_user(self.admin)) as f:
            f.raffle_default_theme = "linux"
            f.raffle_default_announce_channel_auto = True
            f.raffle_default_announce_channel_id = self.channel
        self.assertEqual(self.config.default_theme, "linux")
        self.assertTrue(self.config.default_announce_channel_auto)
        self.assertEqual(self.config.default_announce_channel_id, self.channel)

    def test_unchanged_values_are_not_written_again(self):
        # A value the singleton's checks would refuse today, left as it is,
        # does not block the saving of the other settings.
        chat = self.env["discuss.channel"].create(
            {"name": "tete-a-tete", "channel_type": "chat"}
        )
        self.env.cr.execute(
            "UPDATE event_raffle_config SET default_announce_channel_id = %s"
            " WHERE id = %s",
            (chat.id, self.config.id),
        )
        self.config.invalidate_recordset(["default_announce_channel_id"])
        with Form(self.env["res.config.settings"].with_user(self.admin)) as f:
            f.raffle_default_spin_turns = 4
        self.assertEqual(self.config.default_spin_turns, 4)
        self.assertEqual(self.config.default_announce_channel_id, chat)

    def test_a_deleted_channel_does_not_block_the_other_settings(self):
        # Deleting the channel empties it at the SQL level and leaves
        # "announce" ticked. The settings of every app share one form, which
        # still saves a setting of another app.
        self.config.write(
            {
                "default_announce_channel_auto": True,
                "default_announce_channel_id": self.channel.id,
            }
        )
        self.channel.unlink()
        self.config.invalidate_recordset()
        self.assertTrue(self.config.default_announce_channel_auto)
        self.assertFalse(self.config.default_announce_channel_id)
        Settings = self.env["res.config.settings"]
        restrict = Settings.create({}).restrict_template_rendering
        form = Form(Settings.with_user(self.admin))
        form.restrict_template_rendering = not restrict
        form.save().execute()
        self.assertEqual(
            Settings.create({}).restrict_template_rendering, not restrict
        )
        self.assertTrue(self.config.default_announce_channel_auto)

    # Checks of the singleton, from the settings

    def test_announce_and_channel_are_saved_together(self):
        self._save(
            {
                "raffle_default_announce_channel_auto": True,
                "raffle_default_announce_channel_id": self.channel.id,
            },
            user=self.admin,
        )
        self.assertTrue(self.config.default_announce_channel_auto)
        self.assertEqual(self.config.default_announce_channel_id, self.channel)

    def test_announcing_without_a_channel_is_refused(self):
        with self.assertRaises(ValidationError) as caught:
            self._save(
                {"raffle_default_announce_channel_auto": True},
                user=self.admin,
            )
        self.assertIn("discussion channel", str(caught.exception))
        self.assertFalse(self.config.default_announce_channel_auto)

    def test_a_direct_chat_is_refused(self):
        chat = self.env["discuss.channel"].create(
            {"name": "tete-a-tete", "channel_type": "chat"}
        )
        with self.assertRaises(ValidationError) as caught:
            self._save(
                {"raffle_default_announce_channel_id": chat.id},
                user=self.admin,
            )
        self.assertIn("not a channel", str(caught.exception))
        self.assertFalse(self.config.default_announce_channel_id)

    # Access

    def test_only_settings_administrators_write_the_defaults(self):
        for user in (self.manager, self.organizer):
            with self.assertRaises(AccessError):
                self._save({"raffle_default_spin_turns": 3}, user=user)
            with self.assertRaises(AccessError):
                self.config.with_user(user).default_spin_turns = 3
        self._save({"raffle_default_spin_turns": 3}, user=self.admin)
        self.assertEqual(self.config.default_spin_turns, 3)
        # Event users still read the defaults when they create a raffle.
        self.assertEqual(
            self.config.with_user(self.organizer).default_spin_turns, 3
        )

    def test_the_menu_opens_the_raffle_settings(self):
        menu = self.env.ref("event_raffle.menu_event_raffle_settings")
        action = self.env.ref("event_raffle.action_event_raffle_settings")
        self.assertEqual(menu.action, action)
        self.assertEqual(menu.groups_id, self.env.ref("base.group_system"))
        self.assertEqual(action.res_model, "res.config.settings")
        self.assertEqual(action.target, "inline")
        self.assertEqual(safe_eval(action.context)["module"], "event_raffle")
        # Only the settings administrators see the menu.
        self.assertTrue(self.admin.has_group("base.group_system"))
        for user in (self.manager, self.organizer):
            self.assertFalse(user.has_group("base.group_system"))
        # The form of the singleton and its action are gone.
        for xmlid in (
            "event_raffle.event_raffle_config_view_form",
            "event_raffle.action_event_raffle_config",
            "event_raffle.menu_event_raffle_config",
        ):
            self.assertFalse(self.env.ref(xmlid, raise_if_not_found=False))

    def test_the_app_block_lists_the_defaults(self):
        Settings = self.env["res.config.settings"]
        arch = etree.fromstring(Settings.get_view(False, "form")["arch"])
        (app,) = arch.xpath("//app[@name='event_raffle']")
        self.assertEqual(app.get("string"), "Raffle")
        blocks = app.xpath("./block/@name")
        self.assertEqual(
            blocks[:3],
            [
                "raffle_wheel_setting_container",
                "raffle_celebration_setting_container",
                "raffle_messages_setting_container",
            ],
        )
        names = set(app.xpath(".//field/@name"))
        self.assertEqual(
            {n for n in names if n.startswith("raffle_default_")},
            set(SETTINGS_VALUES) | {"raffle_default_announce_channel_id"},
        )

    def test_labels_in_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(
            ["event_raffle"], ["fr_CA"], overwrite=True
        )
        fr = self.env(context=dict(self.env.context, lang="fr_CA"))
        described = fr["res.config.settings"].fields_get(
            ["raffle_default_notify_winner_auto", "raffle_default_theme"]
        )
        self.assertEqual(
            described["raffle_default_notify_winner_auto"]["string"],
            "Notifier le gagnant automatiquement",
        )
        self.assertIn(
            "nouveau", described["raffle_default_notify_winner_auto"]["help"]
        )
        self.assertIn(
            ("light", "Clair"),
            described["raffle_default_theme"]["selection"],
        )
        arch = fr["res.config.settings"].get_view(False, "form")["arch"]
        self.assertIn('string="Tirage"', arch)
        self.assertIn('title="Roue"', arch)
