"""Result filtering: domain include/exclude, minimum snippet length."""

from typing import Optional
from urllib.parse import urlsplit

from dorker.engines.base import SearchResult


def _domain_of(url: str) -> str:
    return urlsplit(url).netloc.lower()


def filter_results(
    results: list[SearchResult],
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
    min_snippet_length: int = 0,
) -> list[SearchResult]:
    filtered = results

    if include_domains:
        includes = [d.lower() for d in include_domains]
        filtered = [
            r for r in filtered if any(_domain_of(r.url).endswith(d) for d in includes)
        ]

    if exclude_domains:
        excludes = [d.lower() for d in exclude_domains]
        filtered = [
            r for r in filtered if not any(_domain_of(r.url).endswith(d) for d in excludes)
        ]

    if min_snippet_length > 0:
        filtered = [r for r in filtered if len(r.snippet) >= min_snippet_length]

    return filtered
