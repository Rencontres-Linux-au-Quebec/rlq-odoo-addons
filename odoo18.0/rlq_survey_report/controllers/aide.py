# -*- coding: utf-8 -*-
"""
aide.py — page d'aide du module DANS Odoo (v1.106.0)
====================================================

Sert le guide utilisateur (doc/Guide-utilisateur-rlq_survey_report.html) à l'adresse /rlq_survey_report/aide, pour les utilisateurs internes connectés
seulement (auth="user" + groupe « Sondage : Utilisateur »). Le menu Sondages > Rapports détaillés > « Guide d'utilisation » l'ouvre dans un nouvel onglet.
Une seule source : le guide du dossier doc/ (aucune copie à tenir à jour). Aucune dépendance au module « Site web ».
"""
import logging

from odoo import http
from odoo.http import request
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

CHEMIN_GUIDE = "rlq_survey_report/doc/Guide-utilisateur-rlq_survey_report.html"


class RlqSurveyReportAide(http.Controller):

    @http.route("/rlq_survey_report/aide", type="http", auth="user", methods=["GET"])
    def aide(self, **kwargs):
        if not request.env.user.has_group("survey.group_survey_user"):
            return request.not_found()
        try:
            with file_open(CHEMIN_GUIDE, "rb") as f:
                contenu = f.read()
        except OSError:
            _logger.warning("guide utilisateur introuvable : %s", CHEMIN_GUIDE, exc_info=True)
            return request.not_found()
        return request.make_response(contenu, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Cache-Control", "no-cache"),
            ("X-Content-Type-Options", "nosniff"),
        ])
