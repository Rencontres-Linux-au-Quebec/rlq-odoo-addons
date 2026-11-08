# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""Guard for the wiki (OCA document_page): keeps the content of pages small enough to be opened.

1. Every content written to a page or to its history is cleaned: the attribute `data-last-history-steps` keeps only its
   last step id(s) (parameter rlq_document_page_guard.keep_history_steps, 1 by default).
2. Validation: a new version whose content is still larger than rlq_document_page_guard.max_content_mb (5 MB by
   default, 0 = no limit) is refused, unless it is not larger than the current version (so that a heavy page can
   always be made lighter).
"""
import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError

from ..lib.html_steps import steps_size, trim_history_steps

_logger = logging.getLogger(__name__)

PARAM_KEEP = "rlq_document_page_guard.keep_history_steps"
PARAM_MAX_MB = "rlq_document_page_guard.max_content_mb"
DEFAULT_KEEP = 1
DEFAULT_MAX_MB = 5.0
# Log a line only when the cleaning removes a significant amount (avoids noise on every save).
LOG_THRESHOLD = 100_000


def _get_keep(env):
    try:
        return int(env["ir.config_parameter"].sudo().get_param(PARAM_KEEP, DEFAULT_KEEP))
    except (TypeError, ValueError):
        return DEFAULT_KEEP


def _get_max_bytes(env):
    try:
        max_mb = float(env["ir.config_parameter"].sudo().get_param(PARAM_MAX_MB, DEFAULT_MAX_MB))
    except (TypeError, ValueError):
        max_mb = DEFAULT_MAX_MB
    return int(max_mb * 1024 * 1024) if max_mb > 0 else 0


def _clean_vals(env, vals, label):
    """Clean vals["content"] in place. Returns vals."""
    content = vals.get("content")
    if content and isinstance(content, str):
        cleaned = trim_history_steps(content, keep=_get_keep(env))
        removed = len(content) - len(cleaned)
        if removed >= LOG_THRESHOLD:
            _logger.info("rlq_document_page_guard: %s: %d characters of data-last-history-steps removed", label, removed)
        vals["content"] = cleaned
    return vals


def _content_bytes(content):
    return len(content.encode("utf-8")) if content and isinstance(content, str) else 0


class DocumentPage(models.Model):
    _inherit = "document.page"

    # Cleaning at the page level too: document.page compares the new content with the current version before creating a
    # history line. Cleaned on both sides, a save without real change does not create a new (heavy) version.
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _clean_vals(self.env, vals, "new page")
        return super().create(vals_list)

    def write(self, vals):
        if "content" in vals:
            vals = _clean_vals(self.env, dict(vals), "pages %s" % self.ids)
        return super().write(vals)


class DocumentPageHistory(models.Model):
    _inherit = "document.page.history"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _clean_vals(self.env, vals, "history of page %s" % vals.get("page_id"))
            self._rlq_check_content_size(vals.get("content"), vals.get("page_id"))
        return super().create(vals_list)

    def write(self, vals):
        if "content" in vals:
            vals = _clean_vals(self.env, dict(vals), "history %s" % self.ids)
            for record in self:
                self._rlq_check_content_size(vals.get("content"), record.page_id.id, current=record.content)
        return super().write(vals)

    @api.model
    def _rlq_check_content_size(self, content, page_id, current=None):
        """Refuse a content above the limit, unless it is not larger than the current version of the page."""
        max_bytes = _get_max_bytes(self.env)
        size = _content_bytes(content)
        if not max_bytes or size <= max_bytes:
            return
        if current is None and page_id:
            # Current version = the most recent history line of the page (read in SQL: only its size, never its content).
            self.env.cr.execute(
                "SELECT octet_length(content) FROM document_page_history WHERE page_id = %s ORDER BY id DESC LIMIT 1",
                (page_id,),
            )
            row = self.env.cr.fetchone()
            current_size = row[0] if row and row[0] else 0
        else:
            current_size = _content_bytes(current)
        if current_size and size <= current_size:
            _logger.warning(
                "rlq_document_page_guard: page %s still above the limit (%d bytes > %d) but not larger than before: accepted",
                page_id, size, max_bytes,
            )
            return
        raise ValidationError(_(
            "This wiki page is too large to be saved: %(size)s MB, the limit is %(limit)s MB.\n"
            "Large pages can no longer be opened. Insert images with the image button (upload) instead of pasting them, "
            "or split the page into several linked pages.",
            size=round(size / 1024 / 1024, 1),
            limit=round(max_bytes / 1024 / 1024, 1),
        ))

    @api.model
    def _rlq_trim_existing_history(self, min_bytes=100_000):
        """Clean the versions already stored (one at a time, in SQL, so that memory stays low). Returns the number cleaned.

        Used by the post_init_hook and callable again from a shell:
            env["document.page.history"]._rlq_trim_existing_history()
        """
        keep = _get_keep(self.env)
        cr = self.env.cr
        cr.execute(
            "SELECT id FROM document_page_history WHERE octet_length(content) > %s AND content ILIKE %s ORDER BY id",
            (min_bytes, "%data-last-history-steps%"),
        )
        ids = [row[0] for row in cr.fetchall()]
        cleaned = 0
        for history_id in ids:
            cr.execute("SELECT content FROM document_page_history WHERE id = %s", (history_id,))
            content = cr.fetchone()[0]
            new_content = trim_history_steps(content, keep=keep)
            if new_content != content:
                cr.execute("UPDATE document_page_history SET content = %s WHERE id = %s", (new_content, history_id))
                _logger.info(
                    "rlq_document_page_guard: history %s cleaned: %d -> %d characters (steps: %d -> %d)",
                    history_id, len(content), len(new_content), steps_size(content), steps_size(new_content),
                )
                cleaned += 1
        if cleaned:
            self.invalidate_model(["content"])
        _logger.info("rlq_document_page_guard: %d version(s) of wiki pages cleaned", cleaned)
        return cleaned
