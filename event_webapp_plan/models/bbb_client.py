# -*- coding: utf-8 -*-
# Copyright (C) 2026 Services-Conseils Linux Inc.  (info@rencontres-linux.quebec)
# Copyright (C) 2026 Rencontres Linux au Québec contributors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your option) any later version. (http://www.gnu.org/licenses/agpl)
"""BigBlueButton helpers: API calls, join URLs and the frame check.

No Odoo model lives here, only plain functions, so the models, the
controller and the tests share them; every network access goes through
`requests.get` of this module, which the tests replace.

API. Every call is GET <api>/<call>?<query>&checksum=<hex>, where the
checksum is the SHA-256 hex digest of <call> + <query> + <shared secret>.
BigBlueButton 2.6 and later accept SHA-256 and pick the algorithm from the
length of the checksum. The query is built once with urlencode and sent
exactly as hashed. The answer is XML: <returncode> is SUCCESS or FAILED,
and a failure carries <messageKey> and <message>.

The secret never leaves the server: it only feeds the digest. BbbError
carries a kind and the server's messageKey, never a URL, so logging it
leaks neither the secret nor a join URL. It is raised `from None`: the
requests exception it replaces names the signed URL (urllib3 prints it in
"Max retries exceeded with url: ..."), and a chained cause would print it
in every traceback, the one Odoo sends back in a JSON-RPC error included.

Join URLs carry the createTime of the running session, read from
getMeetingInfo: BigBlueButton refuses such a URL in any later session of
the same meetingID, so a copied join URL stops working when the session
ends.

Cache. The room pages and their status polls ask for the meeting state
from inside an Odoo worker. `cached_meeting_info()` keeps each answer
RUNNING_TTL seconds per (server, meeting), and after a failure to reach
the server (network, HTTP status or not XML) answers with the same error
for FAILURE_TTL seconds without calling it, so an unreachable server
costs one connect timeout per minute and per worker process instead of
one per page view. The cache lives in the process memory of each worker.
A caller may refuse a meeting state older than a given age (`max_age`):
"Join again" accepts FRESH_TTL seconds at most, since the end of a
meeting sends every client to its logoutURL at once and a state cached
before the end would send the visitor to a join URL the server refuses.

Frame check. A page can be shown in an iframe of the Odoo page unless its
headers forbid it. A Content-Security-Policy with a frame-ancestors
directive takes precedence over X-Frame-Options, as browsers do; a
Content-Security-Policy-Report-Only header enforces nothing.

Same site. BigBlueButton keeps the session of its client in a cookie set
by the join URL, without SameSite attribute. A browser stores no such
cookie for a frame whose site differs from the site of the top page
(SameSite defaults to Lax; Safari and the browsers that block third-party
cookies refuse it whatever its attributes), and the client then fails to
load. `same_site()` tells whether two URLs share a site: same scheme, and
same host or same registrable domain. The registrable domain comes from
the public suffix list of tldextract when that library is installed (its
bundled copy, never a download), else from a conservative rule (see
`registrable_domain()`); an answer wrong toward "another site" only costs
the frame, the other way back brings the failure.
"""

import hashlib
import ipaddress
import re
import threading
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from lxml import etree

try:
    import tldextract
except ImportError:  # pragma: no cover - optional library
    tldextract = None

TIMEOUT = 5
# API calls: (connect, read) timeouts in seconds. A server that drops the
# packets holds a worker for the connect timeout only.
API_TIMEOUT = (3, 5)
RUNNING_TTL = 10
# Largest age, in seconds, of a meeting state that a read with max_age
# accepts; it bounds the calls of repeated "Join again" clicks.
FRESH_TTL = 2
FAILURE_TTL = 60
CACHE_MAX = 512
USER_AGENT = "Odoo event_webapp_plan"
DEFAULT_PORTS = {"http": 80, "https": 443}
# CSP host-source: [scheme://]host[:port][/path], host possibly "*" or
# starting with "*.".
HOST_SOURCE_RE = re.compile(
    r"^(?:(?P<scheme>[a-z][a-z0-9+.-]*)://)?"
    r"(?P<host>\*|(?:\*\.)?[a-z0-9.-]+)"
    r"(?::(?P<port>\*|[0-9]+))?"
    r"(?P<path>/.*)?$"
)
SCHEME_SOURCE_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.-]*):$")
# Longest second-level label that the built-in rule takes for a public
# suffix under a two-letter country code: a province or a "co" or "com"
# label under the code of its country.
SUFFIX_LABEL_MAX = 3


class BbbError(Exception):
    """Failed BigBlueButton call.

    `kind` is "network" (no answer), "http" (status other than 200, in
    `status`), "parse" (not XML) or "failed" (returncode FAILED, with the
    server's `key` and `message`).
    """

    def __init__(self, kind, key=None, message=None, status=None):
        super().__init__(kind)
        self.kind = kind
        self.key = key or ""
        self.message = message or ""
        self.status = status
        # True when the error comes from the failure cache, without call.
        self.cached = False

    def __str__(self):
        detail = self.key or (self.status and "HTTP %s" % self.status) or ""
        return "%s %s" % (self.kind, detail) if detail else self.kind


# ----------------------------------------------------------------------
# URLs
# ----------------------------------------------------------------------


def is_web_url(url):
    """True for an absolute http or https URL with a host and no blank."""
    if not url or any(c.isspace() for c in url):
        return False
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError:
        return False
    return parts.scheme.lower() in DEFAULT_PORTS and bool(parts.hostname)


def api_url(server_url):
    """API endpoint ".../bigbluebutton/api" of a server URL, or False.

    Accepts the server root, the ".../bigbluebutton/" URL printed by
    `bbb-conf --secret`, or the API endpoint itself.
    """
    url = (server_url or "").strip()
    if not is_web_url(url):
        return False
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if not path.endswith("/bigbluebutton/api"):
        if not path.endswith("/bigbluebutton"):
            path += "/bigbluebutton"
        path += "/api"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def checksum(call, query, secret, algorithm="sha256"):
    """Hex digest of `call` + `query` + `secret`."""
    raw = ("%s%s%s" % (call, query, secret)).encode()
    return hashlib.new(algorithm, raw).hexdigest()


def call_url(api, secret, call, params=None):
    """Signed URL of the API call `call` with the ordered `params`."""
    query = urlencode(list((params or {}).items()))
    signature = checksum(call, query, secret)
    if query:
        return "%s/%s?%s&checksum=%s" % (api, call, query, signature)
    return "%s/%s?checksum=%s" % (api, call, signature)


def join_url(
    api,
    secret,
    meeting_id,
    full_name,
    role,
    user_id,
    create_time=None,
    logout_url=None,
):
    """Signed join URL: BigBlueButton redirects it to its HTML5 client.

    `role` is "MODERATOR" or "VIEWER"; no password is sent, the role alone
    decides, which BigBlueButton 2.6 and later accept. `create_time`, the
    createTime of the running session, makes the server refuse the URL in
    any other session of the meeting. `logout_url` is sent as logoutURL, a
    join parameter of BigBlueButton 3.0 and later: the page the client of
    this user loads once they leave, in place of the logoutURL of the
    meeting (set at create, by Greenlight for instance). The client adds
    "reason=<text>" to its query. Earlier servers ignore the parameter.
    """
    params = {
        "fullName": full_name,
        "meetingID": meeting_id,
        "role": role,
        "userID": user_id,
        "redirect": "true",
    }
    if create_time:
        params["createTime"] = create_time
    if logout_url:
        params["logoutURL"] = logout_url
    return call_url(api, secret, "join", params)


# ----------------------------------------------------------------------
# API calls
# ----------------------------------------------------------------------


def parse_response(content):
    """Root element of a SUCCESS answer; raise BbbError otherwise.

    The parser resolves no entity and fetches nothing from the network.
    """
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(content, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise BbbError("parse") from exc
    if root is None or (root.findtext("returncode") or "") != "SUCCESS":
        raise BbbError(
            "failed",
            key=root.findtext("messageKey") if root is not None else "",
            message=root.findtext("message") if root is not None else "",
        )
    return root


def api_call(api, secret, call, params=None):
    """Run the API call and return the root of its XML answer."""
    try:
        response = requests.get(
            call_url(api, secret, call, params),
            timeout=API_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException:
        # from None: the requests exception names the signed URL.
        raise BbbError("network") from None
    if response.status_code != 200:
        raise BbbError("http", status=response.status_code)
    return parse_response(response.content)


def meeting_info(api, secret, meeting_id):
    """State of the meeting `meeting_id` from getMeetingInfo, as a dict
    with `running` and `create_time` (the createTime of the session, or
    ""). A meeting the server does not know (messageKey notFound) is not
    running."""
    try:
        root = api_call(
            api, secret, "getMeetingInfo", {"meetingID": meeting_id}
        )
    except BbbError as error:
        if error.kind == "failed" and error.key == "notFound":
            return {"running": False, "create_time": ""}
        raise
    return {
        "running": (root.findtext("running") or "").strip() == "true",
        "create_time": (root.findtext("createTime") or "").strip(),
    }


# Clock of the cache, replaced by the tests.
_clock = time.monotonic
_cache_lock = threading.Lock()
# (api, secret, meeting_id) -> (expiry, info)
_meeting_cache = {}
# (api, secret) -> (expiry, BbbError)
_failure_cache = {}


def cache_clear():
    """Forget every cached meeting state and server failure."""
    with _cache_lock:
        _meeting_cache.clear()
        _failure_cache.clear()


def _prune(cache, now):
    """Drop the expired entries of `cache` once it holds CACHE_MAX."""
    if len(cache) >= CACHE_MAX:
        for key in [k for k, (expiry, _v) in cache.items() if expiry <= now]:
            del cache[key]
        if len(cache) >= CACHE_MAX:
            cache.clear()


def cached_meeting_info(api, secret, meeting_id, max_age=None):
    """meeting_info() through the cache described in the module docstring.

    With `max_age` (seconds), a cached state older than that is not used:
    the server is asked, and its answer replaces the entry for every
    reader. A cached server failure still answers at once.

    A cached failure raises a new BbbError of the same kind, with `cached`
    set, so the caller logs only the failures of real calls. A "failed"
    answer (wrong secret, unknown call) is never cached: the settings may
    change at any time.
    """
    now = _clock()
    server = (api, secret)
    key = (api, secret, meeting_id)
    with _cache_lock:
        failure = _failure_cache.get(server)
        if failure and failure[0] > now:
            error = BbbError(
                failure[1].kind,
                key=failure[1].key,
                message=failure[1].message,
                status=failure[1].status,
            )
            error.cached = True
            raise error
        entry = _meeting_cache.get(key)
        # The entry was stored at expiry - RUNNING_TTL.
        if (
            entry
            and entry[0] > now
            and (max_age is None or entry[0] - RUNNING_TTL >= now - max_age)
        ):
            return dict(entry[1])
    try:
        info = meeting_info(api, secret, meeting_id)
    except BbbError as error:
        if error.kind in ("network", "http", "parse"):
            with _cache_lock:
                _prune(_failure_cache, now)
                _failure_cache[server] = (now + FAILURE_TTL, error)
        raise
    with _cache_lock:
        _failure_cache.pop(server, None)
        _prune(_meeting_cache, now)
        _meeting_cache[key] = (now + RUNNING_TTL, dict(info))
    return info


def meetings_from_xml(root):
    """Meetings of a getMeetings answer, breakout rooms left out, as dicts
    with name, meeting_id, participant_count and running."""
    meetings = []
    for node in root.iterfind("meetings/meeting"):
        if (node.findtext("isBreakout") or "").strip() == "true":
            continue
        try:
            count = int(node.findtext("participantCount") or 0)
        except ValueError:
            count = 0
        meetings.append(
            {
                "name": (node.findtext("meetingName") or "").strip(),
                "meeting_id": (node.findtext("meetingID") or "").strip(),
                "participant_count": count,
                "running": (node.findtext("running") or "").strip() == "true",
            }
        )
    return meetings


def get_meetings(api, secret):
    """Meetings currently known by the server (see meetings_from_xml)."""
    return meetings_from_xml(api_call(api, secret, "getMeetings"))


# ----------------------------------------------------------------------
# Frame check
# ----------------------------------------------------------------------


def _origin(url):
    """(scheme, host, port) of `url`, port defaulted from the scheme."""
    try:
        parts = urlsplit(url or "")
        port = parts.port
    except ValueError:
        return ("", "", None)
    scheme = parts.scheme.lower()
    return (
        scheme,
        (parts.hostname or "").lower(),
        port or DEFAULT_PORTS.get(scheme),
    )


def _source_matches(source, page_origin, base_origin):
    """True when the CSP source expression `source` matches the origin
    `base_origin` of the Odoo page, for a resource of `page_origin`."""
    base_scheme, base_host, base_port = base_origin
    if source == "*":
        return base_scheme in DEFAULT_PORTS
    if source == "'self'":
        return base_origin == page_origin
    match = SCHEME_SOURCE_RE.match(source)
    if match:
        scheme = match.group("scheme")
        # "http:" also matches https, the secure upgrade of CSP level 3.
        return base_scheme == scheme or (
            scheme == "http" and base_scheme == "https"
        )
    match = HOST_SOURCE_RE.match(source)
    if not match:
        return False
    scheme = match.group("scheme") or page_origin[0]
    if not (
        base_scheme == scheme or (scheme == "http" and base_scheme == "https")
    ):
        return False
    host = match.group("host")
    if host.startswith("*."):
        if not base_host.endswith(host[1:]):
            return False
    elif host != "*" and host != base_host:
        return False
    port = match.group("port")
    if port == "*":
        return True
    if port:
        return int(port) == base_port
    return base_port == DEFAULT_PORTS.get(base_scheme)


def frame_ancestors_allow(value, page_url, base_url):
    """True when the frame-ancestors source list `value` lets the Odoo
    page at `base_url` frame the resource at `page_url`. An empty list,
    or 'none', allows nothing."""
    page_origin = _origin(page_url)
    base_origin = _origin(base_url)
    sources = [s.lower() for s in value.split()]
    return any(
        _source_matches(source, page_origin, base_origin)
        for source in sources
        if source != "'none'"
    )


def frame_allowed(headers, page_url, base_url):
    """True when a page answered with `headers` at `page_url` (after the
    redirects) may be shown in an iframe of the Odoo page at `base_url`.

    Several headers of the same name arrive joined by commas: each
    Content-Security-Policy policy with frame-ancestors must allow, and
    one X-Frame-Options DENY or ALLOW-FROM (obsolete, unsupported by
    current browsers) refuses. Unknown X-Frame-Options values are ignored,
    as browsers ignore them.
    """
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    decisions = []
    for policy in (headers.get("content-security-policy") or "").split(","):
        for directive in policy.split(";"):
            tokens = directive.strip().split(None, 1)
            if tokens and tokens[0].lower() == "frame-ancestors":
                value = tokens[1] if len(tokens) > 1 else ""
                decisions.append(
                    frame_ancestors_allow(value, page_url, base_url)
                )
    if decisions:
        return all(decisions)
    values = [
        v.strip().lower()
        for v in (headers.get("x-frame-options") or "").split(",")
        if v.strip()
    ]
    if any(v == "deny" or v.startswith("allow-from") for v in values):
        return False
    if "sameorigin" in values:
        return _origin(page_url) == _origin(base_url)
    return True


def frame_check(url, base_url):
    """Fetch `url`, following redirects, and tell whether its final page
    may be framed by the Odoo page at `base_url`. Only the headers are
    read. No answer, or an HTTP error status, means not frameable."""
    try:
        response = requests.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=True,
            headers={"User-Agent": USER_AGENT},
        )
    except requests.RequestException:
        return False
    try:
        if response.status_code >= 400:
            return False
        return frame_allowed(response.headers, response.url or url, base_url)
    finally:
        response.close()


# ----------------------------------------------------------------------
# Same site
# ----------------------------------------------------------------------

# tldextract extractor on its bundled public suffix list, private section
# included (so two subdomains of a hosting suffix are two sites): no
# download, no disk cache. Built on first use.
_extractor = None


def _psl_registrable_domain(host):
    """Registrable domain of `host` from the public suffix list of
    tldextract, or "" when `host` is a public suffix itself."""
    global _extractor
    if _extractor is None:
        _extractor = tldextract.TLDExtract(
            suffix_list_urls=(),
            cache_dir=None,
            include_psl_private_domains=True,
        )
    result = _extractor(host)
    domain = getattr(result, "top_domain_under_public_suffix", None)
    if domain is None:
        domain = result.registered_domain
    return domain or ""


def registrable_domain(host):
    """Registrable domain of the lowercase host name `host`, or "" for an
    IP address, a single-label host or a public suffix.

    Without tldextract, the rule keeps the last two labels, or the last
    three when the last two look like a two-level public suffix: a label
    of SUFFIX_LABEL_MAX characters or fewer under a two-letter country
    code. A shorter answer than the true registrable domain would join
    two sites; this rule errs toward the longer one.
    """
    host = (host or "").rstrip(".")
    if not host or "." not in host:
        return ""
    try:
        ipaddress.ip_address(host)
        return ""
    except ValueError:
        pass
    if tldextract is not None:
        return _psl_registrable_domain(host)
    labels = host.split(".")
    if len(labels[-1]) == 2 and len(labels[-2]) <= SUFFIX_LABEL_MAX:
        size = 3
    else:
        size = 2
    if len(labels) < size:
        return ""
    return ".".join(labels[-size:])


def same_site(url_a, url_b):
    """True when the http or https URLs `url_a` and `url_b` belong to the
    same site, as browsers decide for cookies: same scheme (http and
    https are two sites), ports ignored, then same host or same
    registrable domain. An IP address or a single-label host (localhost)
    shares its site with the same host only. Anything else, an empty or
    invalid URL included, is False."""
    if not (is_web_url(url_a) and is_web_url(url_b)):
        return False
    parts_a, parts_b = urlsplit(url_a), urlsplit(url_b)
    if parts_a.scheme.lower() != parts_b.scheme.lower():
        return False
    host_a = parts_a.hostname.rstrip(".")
    host_b = parts_b.hostname.rstrip(".")
    if host_a == host_b:
        return True
    domain = registrable_domain(host_a)
    return bool(domain) and domain == registrable_domain(host_b)
