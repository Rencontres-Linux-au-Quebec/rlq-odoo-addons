# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (HttpCase) of the registration confirmation page.

NOT RUN while writing (no Odoo instance). On a DISPOSABLE database, never production:
    odoo-bin -d TEST_DB -i rlq_website_event_success --test-enable --test-tags rlq_website_event_success --stop-after-init
"""
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestRegistrationSuccess(HttpCase):

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
        cls.url = "/event/%s/registration/success" % cls.event.id

    def test_without_parameter_no_error_500(self):
        response = self.url_open(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("o_rlq_registration_not_found", response.text)

    def test_garbage_parameter(self):
        response = self.url_open(self.url + "?registration_ids=abc,99999999999")
        self.assertEqual(response.status_code, 200)
        self.assertIn("o_rlq_registration_not_found", response.text)

    def test_unknown_visitor_no_404_and_no_personal_data(self):
        response = self.url_open(self.url + "?registration_ids=%s" % self.registration.id)
        self.assertEqual(response.status_code, 200)
        self.assertIn("o_rlq_tickets_in_email", response.text)
        self.assertNotIn("personne.test@example.com", response.text)
        self.assertNotIn("Personne Test", response.text)

    def test_registration_of_another_event(self):
        other = self.env["event.event"].create({
            "name": "Autre événement", "date_begin": "2030-11-24 13:00:00", "date_end": "2030-11-24 21:00:00",
            "website_published": True,
        })
        response = self.url_open("/event/%s/registration/success?registration_ids=%s" % (other.id, self.registration.id))
        self.assertEqual(response.status_code, 200)
        self.assertIn("o_rlq_registration_not_found", response.text)
