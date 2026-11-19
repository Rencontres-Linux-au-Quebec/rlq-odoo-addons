# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (HttpCase) of the ticket page /event/<id>/my_tickets.

NOT RUN while writing (no Odoo instance). On a DISPOSABLE database, never production:
    odoo-bin -d TEST_DB -i rlq_website_event_success --test-enable --test-tags rlq_website_event_success --stop-after-init
"""
import json

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestMyTickets(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create({
            "name": "Journée de test RLQ", "date_begin": "2030-10-24 13:00:00", "date_end": "2030-10-24 21:00:00",
            "website_published": True,
        })
        cls.registration = cls.env["event.registration"].create({
            "event_id": cls.event.id, "name": "Personne Test", "email": "personne.test@example.com",
        })
        cls.url = "/event/%s/my_tickets" % cls.event.id
        cls.ids_param = json.dumps([cls.registration.id])
        cls.hash = cls.event._get_tickets_access_hash([cls.registration.id])

    def test_without_parameter_404(self):
        self.assertEqual(self.url_open(self.url).status_code, 404)

    def test_scrambled_parameter_name_404(self):
        # Replayed by the link scanner of an e-mail provider on 2026-11-19 (error 500 before this module).
        self.assertEqual(self.url_open(self.url + "?eftvfgebgvba_vef=").status_code, 404)

    def test_unreadable_registration_ids_404(self):
        response = self.url_open(self.url + "?registration_ids=abc&tickets_hash=%s" % self.hash)
        self.assertEqual(response.status_code, 404)

    def test_missing_hash_404(self):
        self.assertEqual(self.url_open(self.url + "?registration_ids=%s" % self.ids_param).status_code, 404)

    def test_wrong_hash_404(self):
        response = self.url_open(self.url + "?registration_ids=%s&tickets_hash=0000" % self.ids_param)
        self.assertEqual(response.status_code, 404)

    def test_valid_link_unchanged(self):
        response = self.url_open(
            self.url + "?registration_ids=%s&tickets_hash=%s&responsive_html=1" % (self.ids_param, self.hash))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Personne Test", response.text)
