# -*- coding: utf-8 -*-
# Copyright (C) 2026 Rencontres Linux au Québec contributors
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
"""
post-migrate.py (18.0.1.143.0) - recompute the stored link « Lien du sondage (type de billet) » of the existing registrations,
so that it carries « email=<address of the registration> » (event_ticket_survey.avec_courriel). Odoo does not recompute a
stored field when only its dependencies change. Never blocks the update: a failure is logged.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    try:
        env = api.Environment(cr, SUPERUSER_ID, {})
        registrations = env["event.registration"].with_context(active_test=False).search(
            [("event_ticket_id.rlq_survey_id", "!=", False)])
        if registrations:
            env.add_to_compute(registrations._fields["rlq_lien_sondage_billet"], registrations)
            env.flush_all()
        _logger.info("rlq_survey_report 18.0.1.143.0: survey link recomputed for %d registrations", len(registrations))
    except Exception:  # noqa: BLE001 - the update must not fail for this
        _logger.warning("rlq_survey_report 18.0.1.143.0: survey links not recomputed", exc_info=True)
