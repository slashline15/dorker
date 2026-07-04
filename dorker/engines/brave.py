"""Brave Search engine — direct HTML scraping."""

import logging
from typing import Optional

from bs4 import BeautifulSoup

from dorker.engines.base import BaseEngine, SearchResult
from dorker.engines.scraping_base import fetch_with_retry
from dorker.anti_detect import Session, DelayManager

logger = logging.getLogger(__name__)

BRAVE_URL = "https://search.brave.com/search"


class BraveEngine(BaseEngine):
    """Brave Search via direct HTML scraping."""

    name = "brave"

    def __init__(
        self,
        session: Optional[Session] = None,
        delay: Optional[DelayManager] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.session = session or Session()
        self.delay = delay or DelayManager(min_delay=3.0, max_delay=8.0)
        self.timeout = timeout
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return True

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0

        for page_num in range(pages):
            self.delay.wait()

            page_results = self._fetch_page(query, offset=page_num)

            if not page_results:
                break

            for r in page_results:
                position += 1
                r.position = position
                results.append(r)

            if page_num < pages - 1:
                self.session.rotate()

        return results

    def _fetch_page(self, query: str, offset: int) -> list[SearchResult]:
        params = {"q": query}
        if offset > 0:
            params["offset"] = offset

        html = fetch_with_retry(
            BRAVE_URL,
            params=params,
            session=self.session,
            delay=self.delay,
            timeout=self.timeout,
            max_retries=self.max_retries,
            engine_name="Brave",
        )
        if html is None:
            return []
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for snippet in soup.select("#results .snippet"):
            link_el = snippet.select_one("a")
            if not link_el:
                continue

            url = str(link_el.get("href", "") or "")
            if not url or not url.startswith("http"):
                continue

            title_el = link_el.select_one(".title")
            title = title_el.get_text(strip=True) if title_el else ""

            content_el = snippet.select_one(".generic-snippet .content")
            snippet_text = content_el.get_text(strip=True) if content_el else ""

            if url and title:
                results.append(
                    SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet_text,
                        engine=self.name,
                        position=0,
                    )
                )

        return results
