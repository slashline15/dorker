"""Mojeek engine — independent search engine, no JS required."""

import logging
from typing import Optional

from bs4 import BeautifulSoup

from dorker.engines.base import BaseEngine, SearchResult
from dorker.engines.scraping_base import fetch_with_retry
from dorker.anti_detect import Session, DelayManager

logger = logging.getLogger(__name__)

MOJEEK_URL = "https://www.mojeek.com/search"

# Mojeek-friendly User-Agents (blocks some Chrome UAs)
MOJEEK_UAS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


class MojeekEngine(BaseEngine):
    """Mojeek search engine — independent index, no JavaScript required."""

    name = "mojeek"

    def __init__(
        self,
        session: Optional[Session] = None,
        delay: Optional[DelayManager] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.session = session or Session()
        # Override UA with Mojeek-friendly one
        import random
        self.session.user_agent = random.choice(MOJEEK_UAS)
        self.delay = delay or DelayManager(min_delay=2.0, max_delay=6.0)
        self.timeout = timeout
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return True

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0

        for page_num in range(pages):
            self.delay.wait()

            params = {
                "q": query,
            }
            if page_num > 0:
                params["s"] = str(page_num * 10)

            page_results = self._fetch_page(params)

            if not page_results:
                break

            for r in page_results:
                position += 1
                r.position = position
                results.append(r)

            if page_num < pages - 1:
                self.session.rotate()

        return results

    def _fetch_page(self, params: dict) -> list[SearchResult]:
        html = fetch_with_retry(
            MOJEEK_URL,
            params=params,
            session=self.session,
            delay=self.delay,
            timeout=self.timeout,
            max_retries=self.max_retries,
            engine_name="Mojeek",
            extra_headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            rate_limit_statuses=(429, 403),
        )
        if html is None:
            return []
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Mojeek results are in li elements inside div.results
        for li in soup.select(".results li"):
            # Title and link
            title_el = li.select_one("h2 a.title, a.ob")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = str(title_el.get("href", "") or "")

            # Snippet
            snippet_el = li.select_one("p.s, .snippet, .description")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            if url and title:
                results.append(
                    SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet,
                        engine=self.name,
                        position=0,
                    )
                )

        return results
