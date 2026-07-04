"""Protocol for pluggable AI providers."""

from typing import Protocol


class AIProvider(Protocol):
    def expand_query(self, query: str) -> list[str]:
        """Return suggested variations of a dork query."""
        ...
