# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Odoo tests (TransactionCase) of the wiki guard.

NOT RUN while writing (no Odoo instance). On a DISPOSABLE database, never production:
    odoo-bin -d TEST_DB -i rlq_document_page_guard --test-enable --test-tags rlq_document_page_guard --stop-after-init
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestDocumentPageGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("rlq_document_page_guard.keep_history_steps", "1")
        cls.env["ir.config_parameter"].sudo().set_param("rlq_document_page_guard.max_content_mb", "1")
        cls.page = cls.env["document.page"].create({"name": "Page de test RLQ", "content": "<p>Départ</p>"})

    def _head(self):
        return self.env["document.page.history"].search([("page_id", "=", self.page.id)], order="id desc", limit=1)

    def test_page_write_trims_steps(self):
        self.page.write({"content": '<p data-last-history-steps="1,2,3">Texte</p>'})
        self.assertEqual(self._head().content, '<p data-last-history-steps="3">Texte</p>')

    def test_history_create_trims_steps(self):
        history = self.env["document.page.history"].create({
            "page_id": self.page.id, "name": "1.0", "content": '<p data-last-history-steps="4,5,6">Texte</p>',
        })
        self.assertEqual(history.content, '<p data-last-history-steps="6">Texte</p>')

    def test_save_without_real_change_adds_no_version(self):
        self.page.write({"content": '<p data-last-history-steps="1,2">Même texte</p>'})
        count = self.env["document.page.history"].search_count([("page_id", "=", self.page.id)])
        # The editor sends the same text with more steps: cleaned, it equals the current version.
        self.page.write({"content": '<p data-last-history-steps="2">Même texte</p>'})
        self.assertEqual(self.env["document.page.history"].search_count([("page_id", "=", self.page.id)]), count)

    def test_too_large_refused(self):
        with self.assertRaises(ValidationError):
            self.page.write({"content": "<p>" + "x" * (2 * 1024 * 1024) + "</p>"})

    def test_steps_do_not_count_in_limit(self):
        ids = ",".join(str(i) for i in range(400_000))  # about 2.6 MB of ids, removed before the size check
        self.page.write({"content": f'<p data-last-history-steps="{ids}">Texte</p>'})
        self.assertEqual(self._head().content, '<p data-last-history-steps="399999">Texte</p>')

    def test_heavy_page_can_be_made_lighter(self):
        self.env["ir.config_parameter"].sudo().set_param("rlq_document_page_guard.max_content_mb", "0")
        self.page.write({"content": "<p>" + "x" * (3 * 1024 * 1024) + "</p>"})
        self.env["ir.config_parameter"].sudo().set_param("rlq_document_page_guard.max_content_mb", "1")
        # Still above 1 MB but lighter than the current version: accepted.
        self.page.write({"content": "<p>" + "x" * (2 * 1024 * 1024) + "</p>"})
        self.assertLess(len(self._head().content), 3 * 1024 * 1024)

    def test_limit_zero_disables_check(self):
        self.env["ir.config_parameter"].sudo().set_param("rlq_document_page_guard.max_content_mb", "0")
        self.page.write({"content": "<p>" + "y" * (2 * 1024 * 1024) + "</p>"})
        self.assertGreater(len(self._head().content), 2 * 1024 * 1024)

    def test_trim_existing_history(self):
        history = self._head()
        ids = ",".join(str(i) for i in range(30_000))
        # Simulates a version swollen before the module was installed (written in SQL, around the ORM).
        self.env.cr.execute("UPDATE document_page_history SET content = %s WHERE id = %s",
                            (f'<p data-last-history-steps="{ids}">Avant</p>', history.id))
        cleaned = self.env["document.page.history"]._rlq_trim_existing_history()
        self.assertGreaterEqual(cleaned, 1)
        history.invalidate_recordset(["content"])
        self.assertEqual(history.content, '<p data-last-history-steps="29999">Avant</p>')
