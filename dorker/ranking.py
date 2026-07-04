"""Simple, explainable relevance ranking for merged search results.

Not a machine-learned model — just three signals a user can reason about:
how many engines agreed on a result, how often the query terms show up in
the title/snippet, and how substantial the snippet is.
"""

import re

from dorker.engines.base import SearchResult


def _term_count(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in terms)


def rank(results: list[SearchResult], query: str) -> list[SearchResult]:
    """Score results in place and return them sorted by score, highest first."""
    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]

    for r in results:
        sources = r.sources or [r.engine]
        source_score = len(sources) * 10
        term_score = _term_count(r.title, terms) * 3 + _term_count(r.snippet, terms)
        length_score = min(len(r.snippet), 200) / 20
        r.score = source_score + term_score + length_score

    return sorted(results, key=lambda r: r.score, reverse=True)
