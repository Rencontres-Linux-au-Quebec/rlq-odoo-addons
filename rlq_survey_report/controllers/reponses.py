# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
reponses.py - links of the e-mail « Vos réponses au sondage » (v1.128.0)
=========================================================================

Two links at the bottom of the e-mail that sends their answers to a person (and of the update e-mail):

  /rlq_survey_report/reponses/<answer token>/modifier  « Modifier mes réponses »: the participation goes back to « in progress »,
      from the first page, and the person is sent to the survey of Odoo, which shows the answers already given. When the person
      submits again, a new copy of the answers is e-mailed (if the survey sends them).
  /rlq_survey_report/reponses/<answer token>/annuler   « Je ne peux plus venir »: the registration that goes with this
      participation (same e-mail address, survey of the ticket) is cancelled, and a note is written in its history.

The token is the secret token of the participation, the one Odoo already puts in the link of the survey. Opening a link
(GET) only shows a confirmation page: nothing changes until the person clicks the button (POST, CSRF-protected), so a mail
scanner that opens every link of an e-mail cannot reopen a survey or cancel a registration. Pages in French and English, no
dependency on the Website application.
"""
import logging

from odoo import fields, http
from odoo.http import request

from ..models import report_builder as rb

_logger = logging.getLogger(__name__)

BASE = "/rlq_survey_report/reponses/<string:token>"


class RlqSurveyReponsesLiens(http.Controller):

    def _participation(self, token):
        """The participation of this token (sudo), or an empty recordset. Test entries are never touched."""
        if not token or len(token) > 64:
            return request.env["survey.user_input"].sudo()
        participation = request.env["survey.user_input"].sudo().search([("access_token", "=", token)], limit=1)
        return participation.filtered(lambda p: not p.test_entry)

    def _page(self, titre, texte, bouton=None, action=None):
        html = rb.page_lien_courriel(titre, texte, bouton, action, request.csrf_token() if action else None)
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"),
                                                    ("X-Robots-Tag", "noindex, nofollow")])

    def _introuvable(self):
        return self._page(rb.TEXTES_LIENS["introuvable_titre"], rb.TEXTES_LIENS["introuvable_texte"])

    # ---------------------------------------------------------------- modifier mes réponses

    @http.route(BASE + "/modifier", type="http", auth="public", methods=["GET"], sitemap=False)
    def modifier_confirmer(self, token, **kwargs):
        participation = self._participation(token)
        if not participation or not participation._rlq_peut_modifier():
            return self._introuvable()
        textes = rb.TEXTES_LIENS
        return self._page(textes["modifier_titre"], textes["modifier_texte"] % {"sondage": participation.survey_id.title or ""},
                          textes["modifier_bouton"], "/rlq_survey_report/reponses/%s/modifier" % token)

    @http.route(BASE + "/modifier", type="http", auth="public", methods=["POST"], sitemap=False)
    def modifier(self, token, **kwargs):
        participation = self._participation(token)
        if not participation or not participation._rlq_peut_modifier():
            return self._introuvable()
        participation.write({"state": "in_progress", "last_displayed_page_id": False, "rlq_courriel_reponses_envoye": False})
        _logger.info("rlq_survey_report: survey.user_input %s reopened by the person (link of the e-mail of answers)", participation.id)
        return request.redirect("/survey/start/%s?answer_token=%s" % (participation.survey_id.access_token, participation.access_token))

    # ---------------------------------------------------------------- je ne peux plus venir

    @http.route(BASE + "/annuler", type="http", auth="public", methods=["GET"], sitemap=False)
    def annuler_confirmer(self, token, **kwargs):
        participation = self._participation(token)
        inscription = participation._rlq_inscription_annulable() if participation else None
        if not inscription:
            return self._introuvable()
        textes = rb.TEXTES_LIENS
        return self._page(textes["annuler_titre"], textes["annuler_texte"] % {"evenement": inscription.event_id.name or ""},
                          textes["annuler_bouton"], "/rlq_survey_report/reponses/%s/annuler" % token)

    @http.route(BASE + "/annuler", type="http", auth="public", methods=["POST"], sitemap=False)
    def annuler(self, token, **kwargs):
        participation = self._participation(token)
        inscription = participation._rlq_inscription_annulable() if participation else None
        if not inscription:
            return self._introuvable()
        inscription.action_cancel()
        if hasattr(inscription, "message_post"):
            inscription.message_post(body=rb.TEXTES_LIENS["note_annulation"] % {
                "date": fields.Datetime.to_string(fields.Datetime.now())})
        _logger.info("rlq_survey_report: event.registration %s cancelled by the person (link of the e-mail of answers)", inscription.id)
        textes = rb.TEXTES_LIENS
        return self._page(textes["annule_titre"], textes["annule_texte"] % {"evenement": inscription.event_id.name or ""})
