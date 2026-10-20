# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux  (contact@exemple.org)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""
email_check.py
==============

Offline check of an e-mail address (v1.109.0): syntax, suggested correction of a typo, disposable domain. Pure Python (no Odoo import):
the same rules as apps/_email_check.py of nginx-tools (keep them identical), testable without Odoo (tests/test_email_check.py).

  check(address)   -> {"valid", "reason", "suggestion", "domain", "disposable"}
  suggest(address) -> corrected address or None ("marieb.essai@gmail'com" -> "marieb.essai@gmail.com")
  syntax_fix(address) -> correction of a PUNCTUATION / SPACE mistake only (never a change of domain name), or None — the only correction applied
                         automatically at registration time (parameter rlq_survey_report.registration_email_autofix = "syntax").
"""
import re

# Popular mailbox domains (Québec first): target of the typo suggestion (distance 1 or 2 from one of these).
POPULAR_DOMAINS = ("gmail.com", "hotmail.com", "hotmail.ca", "outlook.com", "outlook.fr", "live.ca", "live.com", "msn.com", "yahoo.com", "yahoo.ca",
                   "yahoo.fr", "icloud.com", "me.com", "mac.com", "videotron.ca", "sympatico.ca", "bell.net", "cogeco.ca", "cgocable.ca", "globetrotter.net",
                   "telus.net", "shaw.ca", "rogers.com", "protonmail.com", "proton.me", "pm.me", "gmx.com", "gmx.fr", "aol.com", "laposte.net",
                   "orange.fr", "free.fr", "videotron.qc.ca", "umontreal.ca", "ulaval.ca", "etsmtl.ca", "usherbrooke.ca", "uqam.ca", "mcgill.ca", "polymtl.ca")
# Frequent mistakes that a distance cannot guess safely (wrong top-level domain of a known name).
KNOWN_TYPOS = {"gmail.co": "gmail.com", "gmail.con": "gmail.com", "gmail.cm": "gmail.com", "gmail.om": "gmail.com", "gmail.ca": "gmail.com",
               "gmail.fr": "gmail.com", "gmail.comm": "gmail.com", "gmail.cmo": "gmail.com", "gmail.c": "gmail.com", "gmailcom": "gmail.com",
               "hotmail.co": "hotmail.com", "hotmail.con": "hotmail.com", "hotmailcom": "hotmail.com", "hotmail.c": "hotmail.com",
               "outlook.co": "outlook.com", "outlook.con": "outlook.com", "yahoo.co": "yahoo.com", "yahoo.con": "yahoo.com",
               "videotron.com": "videotron.ca", "videotron.qc": "videotron.ca", "videotron.cq": "videotron.ca", "videotron.c": "videotron.ca",
               "sympatico.com": "sympatico.ca", "icloud.co": "icloud.com", "icloud.con": "icloud.com"}
# Disposable (throw-away) mailbox domains: an account created with one of them is a weak sign of bad intent (not a proof).
DISPOSABLE_DOMAINS = {"mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamailblock.com", "sharklasers.com", "grr.la",
                      "10minutemail.com", "10minutemail.net", "20minutemail.com", "temp-mail.org", "tempmail.com", "tempmail.net", "tempmailo.com",
                      "tempr.email", "temp-mail.io", "yopmail.com", "yopmail.fr", "yopmail.net", "trashmail.com", "trashmail.de", "trashmail.net",
                      "getnada.com", "nada.email", "dispostable.com", "maildrop.cc", "throwawaymail.com", "fakeinbox.com", "mintemail.com", "mohmal.com",
                      "emailondeck.com", "discard.email", "mailnesia.com", "spamgourmet.com", "mytemp.email", "burnermail.io", "mailcatch.com",
                      "moakt.com", "mailpoof.com", "inboxkitten.com", "getairmail.com", "spambox.us", "33mail.com", "anonaddy.me", "mail.tm",
                      "emltmp.com", "linshiyouxiang.net", "bccto.me", "chacuo.net", "027168.com", "dropmail.me", "10mail.org", "tmail.ws",
                      "luxusmail.org", "tmpmail.org", "tmpmail.net", "1secmail.com", "1secmail.org", "1secmail.net", "spam4.me", "incognitomail.com",
                      "mailforspam.com", "jetable.org", "trash-mail.com", "wegwerfmail.de", "einrot.com", "cuvox.de", "armyspy.com", "dayrep.com",
                      "fleckens.hu", "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us"}

LOCAL_RE = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$")
LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")
TLD_RE = re.compile(r"^(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]{2,59})$")


def is_disposable(domain):
    d = (domain or "").lower().rstrip(".")
    return any(d == x or d.endswith("." + x) for x in DISPOSABLE_DOMAINS)


def _distance(a, b, limit=3):
    """Damerau-Levenshtein distance (adjacent transposition counts 1), stopped at `limit`."""
    if abs(len(a) - len(b)) >= limit:
        return limit
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) >= limit:
            return limit
        prev2, prev = prev, cur
    return min(prev[-1], limit)


def _syntax_error(address):
    """None if the address is syntactically valid (practical rules of RFC 5321/5322, not the exotic quoted forms), otherwise the reason (English)."""
    if not address:
        return "empty address"
    if any(c.isspace() for c in address):
        return "space in the address"
    if address.count("@") != 1:
        return "no @ sign" if "@" not in address else "several @ signs"
    local, domain = address.split("@")
    if not local:
        return "nothing before the @ sign"
    if len(local) > 64:
        return "part before the @ sign too long (over 64 characters)"
    if not LOCAL_RE.match(local):
        return "invalid character or dot placement before the @ sign"
    if not domain:
        return "nothing after the @ sign"
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError:
        return "invalid domain name"
    if len(ascii_domain) > 253:
        return "domain name too long"
    bad = sorted(set(re.sub(r"[A-Za-z0-9.-]", "", ascii_domain)))
    if bad:
        return "invalid character in the domain name: " + " ".join(bad)
    labels = ascii_domain.rstrip(".").split(".")
    if len(labels) < 2:
        return "domain without a dot (e.g. gmail.com)"
    if not all(LABEL_RE.match(label) for label in labels):
        return "invalid character in the domain name"
    if not TLD_RE.match(labels[-1]):
        return "invalid top-level domain"
    return None


def suggest(address):
    """Corrected address for a typo that can be fixed without guessing who the person is, or None.
    Fixed: spaces, comma / apostrophe / semicolon instead of a dot in the domain, double dots, trailing dot, "gmail.con",
    a domain at distance 1-2 of a popular domain ("gmial.com"), "@@", missing dot before com ("gmailcom")."""
    a = (address or "").strip().strip("<>").strip()
    if not a:
        return None
    a = re.sub(r"\s+", "", a)
    a = re.sub(r"@+", "@", a)
    if a.count("@") != 1:
        return None
    local, domain = a.split("@")
    local = local.strip(".")
    domain = domain.lower()
    domain = re.sub(r"[,;'`´’:]+", ".", domain)
    domain = re.sub(r"\.{2,}", ".", domain).strip(".")
    domain = KNOWN_TYPOS.get(domain, domain)
    if domain not in POPULAR_DOMAINS and not is_disposable(domain):
        best, best_d = None, 3
        for p in POPULAR_DOMAINS:
            dist = _distance(domain, p)
            if dist < best_d:
                best, best_d = p, dist
        # distance 1 always; distance 2 only for long enough names (a short real domain is often 2 edits away from a popular one)
        if best and (best_d == 1 or (best_d == 2 and len(domain) >= 9)):
            domain = best
    fixed = f"{local}@{domain}"
    if fixed == address or _syntax_error(fixed):
        return None
    return fixed


def check(address):
    """Offline analysis: {"valid": bool, "reason": str|None, "suggestion": str|None, "domain": str, "disposable": bool}.
    A syntactically valid address can still get a suggestion ("gmial.com": valid syntax, probable typo)."""
    a = (address or "").strip()
    reason = _syntax_error(a)
    domain = a.split("@", 1)[1].lower() if a.count("@") == 1 else ""
    sug = suggest(a)
    if reason is None and sug and sug.split("@")[1] != domain:
        reason = f"probable typo in the domain ({domain})"
    return {"valid": _syntax_error(a) is None, "reason": reason, "suggestion": sug, "domain": domain, "disposable": bool(domain) and is_disposable(domain)}


def syntax_fix(address):
    """Correction that changes no letter of the address: spaces around the « @ » or in the domain removed, « ' , ; : » replaced by a dot in the domain,
    doubled « @ » or dots, trailing dot. None if the address is valid, if a space remains inside the part before the « @ » (« marie claude@… »: a dot or
    nothing? only the person knows) or if only a guess on the domain name (gmial.com -> gmail.com) would fix it."""
    a = (address or "").strip().strip("<>").strip()
    if not a or _syntax_error(a) is None:
        return None
    a = re.sub(r"@+", "@", re.sub(r"\s*@\s*", "@", a))
    if a.count("@") != 1:
        return None
    local, domain = a.split("@")
    if re.search(r"\s", local):
        return None
    domain = re.sub(r"\s+", "", domain)
    domain = re.sub(r"[,;'`´’:]+", ".", domain)
    domain = re.sub(r"\.{2,}", ".", domain).strip(".")
    fixed = "%s@%s" % (local.strip("."), domain)
    return fixed if fixed != address and _syntax_error(fixed) is None else None


def issue(address):
    """(code, suggestion) for the Odoo field rlq_email_issue: "invalid" (the address cannot receive mail as written), "typo" (valid but a popular domain
    misspelled: gmial.com), "disposable" (throw-away mailbox), or (False, None) when nothing is wrong. An empty address is not an issue here."""
    if not (address or "").strip():
        return False, None
    c = check(address)
    if not c["valid"]:
        return "invalid", c["suggestion"]
    if c["reason"]:
        return "typo", c["suggestion"]
    if c["disposable"]:
        return "disposable", None
    return False, None
