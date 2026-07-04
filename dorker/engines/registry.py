"""Central registry mapping engine names to their implementation classes."""

from dorker.engines.base import BaseEngine
from dorker.engines.brave import BraveEngine
from dorker.engines.duckduckgo import DuckDuckGoEngine
from dorker.engines.google import GoogleEngine
from dorker.engines.mojeek import MojeekEngine
from dorker.engines.searx import SearXEngine

ENGINES: dict[str, type[BaseEngine]] = {
    "duckduckgo": DuckDuckGoEngine,
    "mojeek": MojeekEngine,
    "google": GoogleEngine,
    "searx": SearXEngine,
    "brave": BraveEngine,
}
