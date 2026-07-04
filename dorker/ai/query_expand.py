"""Query expansion via the Anthropic API — suggests dork variations before searching.

The model only ever sees and produces text (the original query and suggested
variations). It never interacts with a search engine, sees scraped HTML, or
participates in anti-detection/bypass in any way — it runs strictly before
the normal engine/orchestrator pipeline, which is unchanged by this feature.
"""

import logging

logger = logging.getLogger("dorker")

_MODEL = "claude-opus-4-8"

_SYSTEM_PROMPT = (
    "You suggest alternative search dork queries (using operators like "
    "site:, filetype:, inurl:, intitle:) that explore the same information "
    "need as the user's original query from different angles — different "
    "operator combinations, synonyms, or related file types. "
    "Reply with exactly one variation per line, no numbering, no commentary."
)


def suggest_variations(query: str, count: int = 4) -> list[str]:
    """Return up to `count` suggested variations of a dork query.

    Returns an empty list if the `anthropic` package isn't installed or no
    API credentials are configured — callers should treat this as "feature
    unavailable", not an error, so dorker works the same with or without it.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning(
            "--ai-expand requires the 'anthropic' package: uv pip install 'dorker[ai]'"
        )
        return []

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Original query: {query}\nSuggest {count} variations.",
                }
            ],
        )
    except Exception as e:
        # Covers anthropic.APIError (bad/missing key, rate limit, network) as
        # well as the SDK's own TypeError when no credentials resolve at all —
        # any failure here means the feature is unavailable, not an error.
        logger.warning("AI query expansion unavailable: %s", e)
        return []

    text = "".join(block.text for block in response.content if block.type == "text")
    variations = [line.strip() for line in text.splitlines() if line.strip()]
    return variations[:count]
