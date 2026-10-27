"""Paged public Ollama library. Website data is metadata, never model authority.

Only fixed HTTPS library endpoints are fetched. Each successful page is cached
atomically; stale pages remain usable offline. A full sync publishes its inventory
only after reaching the real end of pagination, preserving the last good snapshot.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

from local_cli import __version__
from local_cli.model_catalog import _CACHE_DIR, _classify_model
from local_cli.model_search import ModelSearchUnavailable, _parse_pull_count

_MAX_PAGE = 1000
_MAX_HTML = 8_000_000
_TTL = 24 * 60 * 60
_LOCK = threading.RLock()
_SYNC = threading.Lock()
_FAMILY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}\Z")
_TAG = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,191}\Z")
_CAPABILITIES = {"tools", "vision", "thinking", "embedding", "decision", "code"}


class ModelLibraryNetworkUnavailable(ModelSearchUnavailable):
    """The network or library service is unavailable, rather than one family."""


def _text(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _fetch(path, params=None):
    url = "https://ollama.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    headers = {"User-Agent": f"Nova/{__version__}"}
    if path == "/search":
        # The full document route ignores page for its cards; Ollama's HTMX
        # fragment is the route used by its own infinite-scroll interface.
        headers["HX-Request"] = "true"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if urllib.parse.urlparse(response.geturl()).hostname != "ollama.com":
                raise ValueError("Unexpected redirect")
            data = response.read(_MAX_HTML + 1)
        if len(data) > _MAX_HTML:
            raise ValueError("Oversized response")
        return data.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        failure = ModelSearchUnavailable if error.code in (404, 410) else ModelLibraryNetworkUnavailable
        raise failure("Model library is unavailable.") from None
    except Exception:
        raise ModelLibraryNetworkUnavailable("Model library is unavailable.") from None


def _next_page(page_html, page):
    # Never follow an arbitrary URL extracted from remote HTML.
    links = re.findall(r'(?:hx-get|href)=["\']([^"\']+)["\']', page_html)
    for link in links:
        parsed = urllib.parse.urlparse(html.unescape(link))
        if parsed.netloc or parsed.path not in ("/search", ""):
            continue
        values = urllib.parse.parse_qs(parsed.query)
        try:
            number = int((values.get("page") or values.get("p") or [0])[0])
        except ValueError:
            continue
        if number == page + 1:
            return number
    if re.search(r'data-has-more=["\']true["\']', page_html):
        return page + 1
    return None


def parse_search_page(page_html, page=1):
    """Accept current and older public-library cards; reject unknown markup."""
    models = {}
    for card in re.findall(r"<li\b[^>]*>(.*?)</li>", page_html, re.S | re.I):
        match = re.search(r'href=["\']/library/([^"\'/?#:]+)["\']', card)
        if not match:
            continue
        name = html.unescape(match[1])
        if not _FAMILY.fullmatch(name):
            continue
        desc = re.search(r"<p\b[^>]*>(.*?)</p>", card, re.S | re.I)
        description = _text(desc[1])[:1000] if desc else ""
        spans = [_text(s) for s in re.findall(r"<span\b[^>]*>([^<]*)</span>", card, re.S)]
        tags = list(dict.fromkeys(s.lower() for s in spans if s.lower() in _CAPABILITIES | {"cloud", "local"}))
        sizes = list(dict.fromkeys(s.lower() for s in spans if re.fullmatch(r"\d+(?:\.\d+)?[bBmM]", s)))
        pull = re.search(r'title=["\']([\d,]+) downloads["\']', card)
        legacy_pull = re.search(r"x-test-pull-count[^>]*>([^<]+)", card)
        pulls = _parse_pull_count(pull[1] if pull else legacy_pull[1] if legacy_pull else "0")
        cloud_only = "cloud" in tags and not sizes and "local" not in tags
        models[name] = dict(name=name, display=name, description=description,
            category=_classify_model(name, tags, description), tags=tags, sizes=sizes,
            params="", size_gb=0, installed=False, pulls=pulls,
            kind="embedding" if "embedding" in tags else "llm",
            cloud_only=cloud_only, family=True)
    recognized = models or re.search(r"data-result-count|x-test-model|No (?:models|results|matches)|0 models", page_html, re.I)
    if not recognized:
        raise ModelSearchUnavailable("Model library format is unavailable.")
    return {"models": list(models.values()), "nextPage": _next_page(page_html, page)}


def parse_variants(page_html, family):
    if not _FAMILY.fullmatch(family):
        raise ValueError("Invalid family")
    variants = {}
    # The compact mobile link contains all four columns, including actual size.
    for link, contents in re.findall(r'<a\b[^>]*href=["\'](/library/[^"\']+)["\'][^>]*>(.*?)</a>', page_html, re.S):
        name = html.unescape(link.removeprefix("/library/"))
        prefix, separator, tag = name.partition(":")
        if prefix != family or not separator or not _TAG.fullmatch(tag):
            continue
        text = _text(contents)
        size = re.search(r"\b(\d+(?:\.\d+)?)\s*(KB|MB|GB|TB)\b", text, re.I)
        context = re.search(r"\b(\d+(?:\.\d+)?)([KM]?)\s+context", text, re.I)
        cloud = bool(re.search(r"\bcloud\b", text, re.I) or tag.endswith("-cloud") or tag == "cloud")
        # Desktop-only duplicate links contain only the name; don't overwrite
        # the complete row or misclassify a cloud tag as a local download.
        if not size and not cloud:
            continue
        size_gb = float(size[1]) * {"KB": 1e-6, "MB": .001, "GB": 1, "TB": 1000}[size[2].upper()] if size else 0
        variants[name] = dict(name=name, size_gb=round(size_gb, 6),
            size_label=size[0] if size else "", cloud_only=cloud,
            context_length=int(float(context[1]) * {"": 1, "K": 1024, "M": 1024**2}[context[2].upper()]) if context else 0)
    if not variants:
        raise ModelSearchUnavailable("Model variants are unavailable.")
    return list(variants.values())


def _cache_path(kind, key):
    digest = hashlib.sha256(key.encode()).hexdigest()
    return _CACHE_DIR / "library" / kind / (digest + ".json")


def _read(path):
    try:
        if path.stat().st_size > _MAX_HTML:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema") != 1 or type(value.get("syncedAt")) is not int or not 0 <= value["syncedAt"] <= 8_640_000_000_000:
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _cached_request(path, fetch, refresh):
    cached = _read(path)
    if cached and not refresh and time.time() - cached["syncedAt"] < _TTL:
        return {**cached, "offline": False, "stale": False}
    try:
        data = {**fetch(), "schema": 1, "syncedAt": int(time.time())}
    except ModelSearchUnavailable:
        if not cached:
            raise
        return {**cached, "offline": True, "stale": time.time() - cached["syncedAt"] >= _TTL}
    with _LOCK:
        _write(path, data)
    return {**data, "offline": False, "stale": False}


def search_library(query="", *, page=1, kind="all", capability="", local=True, refresh=False, source="auto"):
    if not isinstance(query, str) or len(query) > 200 or type(page) is not int or not 1 <= page <= _MAX_PAGE:
        raise ValueError("Invalid library query")
    if kind not in ("all", "llm", "embedding") or capability not in ("", "tools", "vision", "thinking") or type(local) is not bool or type(refresh) is not bool or source not in ("auto", "web", "snapshot"):
        raise ValueError("Invalid library filter")
    query = query.strip()
    inventory = cached_inventory()
    if source == "snapshot" and not inventory["syncedAt"]:
        raise ModelSearchUnavailable("Saved model library is unavailable.")
    if inventory["syncedAt"] and (source == "snapshot" or source == "auto" and not refresh and time.time() - inventory["syncedAt"] < _TTL):
        return _inventory_page(inventory, query, page, kind, capability, local, offline=time.time() - inventory["syncedAt"] >= _TTL)
    filters = (["local"] if local else []) + (["embedding"] if kind == "embedding" else []) + ([capability] if capability else [])
    params = dict(q=query, page=page, o="popular", c=filters)
    path = _cache_path("pages", json.dumps(params, sort_keys=True))
    def fetch():
        result = parse_search_page(_fetch("/search", params), page)
        if result["nextPage"] and result["nextPage"] > _MAX_PAGE:
            raise ModelSearchUnavailable("Model library pagination limit reached.")
        return result
    try:
        result = _cached_request(path, fetch, refresh)
    except ModelSearchUnavailable:
        if inventory["syncedAt"] and page == 1:
            return _inventory_page(inventory, query, page, kind, capability, local, offline=True)
        raise
    result["models"] = [m for m in result["models"] if (not local or not m["cloud_only"]) and (kind == "all" or m["kind"] == kind)
        and (not capability or capability in m["tags"])]
    return {**result, "page": page, "query": query, "kind": kind, "capability": capability, "local": local, "source": "web"}


def model_variants(family, *, refresh=False):
    if not isinstance(family, str) or not _FAMILY.fullmatch(family) or type(refresh) is not bool:
        raise ValueError("Invalid family")
    return {**_cached_request(_cache_path("variants", family),
        lambda: {"variants": parse_variants(_fetch("/library/" + family + "/tags"), family)}, refresh), "family": family}


def cached_model_variants(family):
    """Read cached variants without attempting a network request."""
    if not isinstance(family, str) or not _FAMILY.fullmatch(family):
        raise ValueError("Invalid family")
    data = _read(_cache_path("variants", family))
    if not data or not isinstance(data.get("variants"), list):
        raise ModelSearchUnavailable("Saved model variants are unavailable.")
    return {**data, "family": family, "offline": True, "stale": time.time() - data["syncedAt"] >= _TTL}


def cached_inventory():
    data = _read(_CACHE_DIR / "library" / "inventory.json")
    return data if data and isinstance(data.get("models"), list) else {"models": [], "syncedAt": 0}


def _inventory_page(inventory, query, page, kind, capability, local, *, offline):
    models = [m for m in inventory["models"] if (not local or not m["cloud_only"]) and
        (kind == "all" or kind == m["kind"]) and (not capability or capability in m["tags"]) and
        (not query or query.casefold() in " ".join([m["name"], m["description"], *m["tags"]]).casefold())]
    start = (page - 1) * 20
    return dict(models=models[start:start + 20], nextPage=page + 1 if start + 20 < len(models) else None,
        page=page, query=query, kind=kind, capability=capability, local=local,
        syncedAt=inventory["syncedAt"], offline=offline, stale=time.time() - inventory["syncedAt"] >= _TTL, source="snapshot")


def synchronize_catalog(*, raise_on_error=True, progress=None):
    """Synchronize every published family; never mistake a partial pass for all."""
    if not _SYNC.acquire(blocking=False):
        raise ModelSearchUnavailable("A library synchronization is already running.")
    try:
        previous = cached_inventory()
        models = {}
        page, fingerprints = 1, set()
        while page is not None:
            # All public families are cached; local is the UI's default filter.
            result = search_library(page=page, local=False, refresh=True)
            if result["offline"]:
                raise ModelSearchUnavailable("Model library is unavailable.")
            fingerprint = tuple(m["name"] for m in result["models"])
            if result["nextPage"] and (not fingerprint or fingerprint in fingerprints):
                raise ModelSearchUnavailable("Model library pagination is unavailable.")
            fingerprints.add(fingerprint)
            models.update((m["name"], m) for m in result["models"])
            if progress:
                progress(len(models))
            page = result["nextPage"]
        data = dict(schema=1, syncedAt=int(time.time()), models=list(models.values()))
        with _LOCK:
            _write(_CACHE_DIR / "library" / "inventory.json", data)
        old_names = {m["name"] for m in previous["models"]}
        return dict(added=len(models.keys() - old_names), updated=len(models.keys() & old_names), total=len(models), syncedAt=data["syncedAt"])
    finally:
        _SYNC.release()
