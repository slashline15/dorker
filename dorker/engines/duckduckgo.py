"""DuckDuckGo engine — using ddgs library."""

import logging
from typing import Optional

from ddgs import DDGS

from dorker.engines.base import BaseEngine, SearchResult
from dorker.anti_detect import Session, DelayManager

logger = logging.getLogger(__name__)


class DuckDuckGoEngine(BaseEngine):
    """DuckDuckGo search via ddgs library."""

    name = "duckduckgo"

    def __init__(
        self,
        session: Optional[Session] = None,
        delay: Optional[DelayManager] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.session = session or Session()
        self.delay = delay or DelayManager(min_delay=2.0, max_delay=6.0)
        self.timeout = timeout
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return True

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0
        max_results = pages * 25

        for attempt in range(self.max_retries):
            try:
                self.delay.wait()

                with DDGS(timeout=self.timeout, proxy=self.session.proxy) as ddgs:
                    raw_results = list(ddgs.text(query, max_results=max_results))

                self.delay.mark_success()

                for r in raw_results:
                    position += 1
                    results.append(
                        SearchResult(
                            url=r.get("href", ""),
                            title=r.get("title", ""),
                            snippet=r.get("body", ""),
                            engine=self.name,
                            position=position,
                        )
                    )

                logger.info(
                    "DuckDuckGo: %d results for '%s'", len(results), query
                )
                return results

            except Exception as e:
                logger.warning(
                    "DuckDuckGo error on attempt %d: %s", attempt + 1, e
                )
                self.delay.mark_error()
                self.delay.wait()
                self.session.rotate()

        return results
