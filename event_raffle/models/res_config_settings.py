# Copyright 2026 TechnoLibre - Mathieu Benoit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models

# First step of the related path of every raffle default in the settings.
RAFFLE_CONFIG_FIELD = "raffle_config_id"


class ResConfigSettings(models.TransientModel):
    """Raffle defaults in the general settings, app block "Raffle".

    Each value is a field related to the default-settings singleton
    (event.raffle.config), which stays their only storage: event.raffle
    reads its defaults there. The labels, help texts and selections come
    from the singleton's fields.

    Saving writes every changed value in ONE write of the singleton, as the
    user who saves (see create()), so the singleton's checks see the whole
    change at once.
    """

    _inherit = "res.config.settings"

    raffle_config_id = fields.Many2one(
        "event.raffle.config",
        string="Raffle Default Settings",
        default=lambda self: self.env.ref(
            "event_raffle.raffle_config_singleton", raise_if_not_found=False
        ),
    )
    # Wheel
    raffle_default_theme = fields.Selection(
        related="raffle_config_id.default_theme", readonly=False
    )
    raffle_default_remove_winner = fields.Boolean(
        related="raffle_config_id.default_remove_winner", readonly=False
    )
    raffle_default_spin_duration = fields.Float(
        related="raffle_config_id.default_spin_duration", readonly=False
    )
    raffle_default_spin_turns = fields.Integer(
        related="raffle_config_id.default_spin_turns", readonly=False
    )
    raffle_default_pointer_angle = fields.Selection(
        related="raffle_config_id.default_pointer_angle", readonly=False
    )
    # Celebration and animation
    raffle_default_winner_celebration = fields.Selection(
        related="raffle_config_id.default_winner_celebration", readonly=False
    )
    raffle_default_show_fireworks = fields.Boolean(
        related="raffle_config_id.default_show_fireworks", readonly=False
    )
    raffle_default_show_tux = fields.Boolean(
        related="raffle_config_id.default_show_tux", readonly=False
    )
    raffle_default_belly_logo = fields.Selection(
        related="raffle_config_id.default_belly_logo", readonly=False
    )
    raffle_default_tux_animation = fields.Selection(
        related="raffle_config_id.default_tux_animation", readonly=False
    )
    raffle_default_flag_text = fields.Text(
        related="raffle_config_id.default_flag_text", readonly=False
    )
    # Messages
    raffle_default_notify_winner_auto = fields.Boolean(
        related="raffle_config_id.default_notify_winner_auto", readonly=False
    )
    raffle_default_notify_winner_message = fields.Text(
        related="raffle_config_id.default_notify_winner_message",
        readonly=False,
    )
    raffle_default_announce_channel_auto = fields.Boolean(
        related="raffle_config_id.default_announce_channel_auto",
        readonly=False,
    )
    # A related field does not take a domain written as a string: the
    # choice is narrowed here as on the singleton.
    raffle_default_announce_channel_id = fields.Many2one(
        related="raffle_config_id.default_announce_channel_id",
        readonly=False,
        domain="[('channel_type', 'in', ('channel', 'group'))]",
    )
    raffle_default_announce_channel_message = fields.Text(
        related="raffle_config_id.default_announce_channel_message",
        readonly=False,
    )

    @api.model
    def _raffle_config_fields(self):
        """Map each editable field related to the singleton to the
        singleton field it shows: {settings field: config field}.

        A module adding a raffle default declares it the same way, a field
        related to raffle_config_id with readonly=False, and create()
        writes it with the others.
        """
        prefix = RAFFLE_CONFIG_FIELD + "."
        return {
            name: field.related[len(prefix) :]
            for name, field in self._fields.items()
            if field.related
            and field.related.startswith(prefix)
            and "." not in field.related[len(prefix) :]
            and not field.readonly
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Write the raffle defaults of `vals_list` in one write of the
        singleton, after creating the settings records.

        The ORM inverts each related field in a write of its own, in the
        order of the values: the singleton's constraint would then see
        "announce" ticked before the channel arrives, and refuse a valid
        form. The values are taken out of `vals_list`, compared with the
        singleton, and the changed ones go in a single write, as the user
        who saves, so the singleton's access rights, channel checks and
        constraints apply. The form sends every field: an unchanged value
        is left out, so that saving one setting never checks again the
        values left as they are. Without the singleton, the raffle values
        are dropped.
        """
        linked = self._raffle_config_fields()
        config_vals_list = [
            {
                linked[name]: vals.pop(name)
                for name in list(vals)
                if name in linked
            }
            for vals in vals_list
        ]
        records = super().create(vals_list)
        for settings, config_vals in zip(
            records, config_vals_list, strict=True
        ):
            config = settings.raffle_config_id
            if not config:
                continue
            changed = {
                name: value
                for name, value in config_vals.items()
                if _differs(config, name, value)
            }
            if changed:
                config.write(changed)
        return records


def _differs(record, name, value):
    """Return whether `value`, as a client or create() sends it, differs
    from field `name` of `record`."""
    field = record._fields[name]
    new = field.convert_to_record(
        field.convert_to_cache(value, record), record
    )
    return record[name] != new
