"""Search engines package."""

from dorker.engines.base import BaseEngine, SearchResult
from dorker.engines.duckduckgo import DuckDuckGoEngine
from dorker.engines.searx import SearXEngine
from dorker.engines.google import GoogleEngine
from dorker.engines.mojeek import MojeekEngine
from dorker.engines.brave import BraveEngine
from dorker.engines.registry import ENGINES

__all__ = [
    "BaseEngine",
    "SearchResult",
    "DuckDuckGoEngine",
    "SearXEngine",
    "GoogleEngine",
    "MojeekEngine",
    "BraveEngine",
    "ENGINES",
]
