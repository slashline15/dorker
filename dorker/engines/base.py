"""Base engine interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SearchResult:
    """A single search result from any engine."""

    url: str
    title: str
    snippet: str
    engine: str
    position: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sources: list[str] = field(default_factory=list)
    score: float = 0.0


class BaseEngine(ABC):
    """Abstract search engine."""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        """Execute a search and return results."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the engine is reachable."""
        ...
