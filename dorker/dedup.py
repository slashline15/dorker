"""URL-based deduplication of merged search results."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dorker.engines.base import SearchResult

_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "ref",
    "ref_src",
}


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    """Merge results pointing at the same normalized URL, tracking every engine that found it."""
    seen: dict[str, SearchResult] = {}
    order: list[str] = []

    for r in results:
        key = _normalize_url(r.url)
        if key not in seen:
            r.sources = [r.engine]
            seen[key] = r
            order.append(key)
        else:
            existing = seen[key]
            if r.engine not in existing.sources:
                existing.sources.append(r.engine)
            if len(r.snippet) > len(existing.snippet):
                existing.snippet = r.snippet

    return [seen[key] for key in order]
