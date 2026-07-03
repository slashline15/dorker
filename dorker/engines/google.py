"""Google engine — direct HTML scraping with anti-detection."""

import logging
import random
import re
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from dorker.engines.base import BaseEngine, SearchResult
from dorker.anti_detect import Session, DelayManager

logger = logging.getLogger(__name__)

GOOGLE_URL = "https://www.google.com/search"


class GoogleEngine(BaseEngine):
    """Google search via direct HTML scraping."""

    name = "google"

    def __init__(
        self,
        session: Optional[Session] = None,
        delay: Optional[DelayManager] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.session = session or Session()
        self.delay = delay or DelayManager(min_delay=4.0, max_delay=12.0)
        self.timeout = timeout
        self.max_retries = max_retries

    def is_available(self) -> bool:
        return True

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0

        for page_num in range(pages):
            self.delay.wait()

            start = page_num * 10
            page_results = self._fetch_page(query, start)

            if not page_results:
                logger.debug("No results on page %d, stopping", page_num + 1)
                break

            for r in page_results:
                position += 1
                r.position = position
                results.append(r)

            if page_num < pages - 1:
                self.session.rotate()

        return results

    def _fetch_page(self, query: str, start: int) -> list[SearchResult]:
        """Fetch a single page of Google results."""
        params = {
            "q": query,
            "num": 10,
            "start": start,
            "hl": "en",
            "safe": "off",
        }

        for attempt in range(self.max_retries):
            try:
                r = requests.get(
                    GOOGLE_URL,
                    params=params,
                    headers=self.session.headers(),
                    timeout=self.timeout,
                )

                if r.status_code == 429:
                    logger.warning("Google rate limited — backing off")
                    self.delay.mark_error()
                    self.delay.wait()
                    self.session.rotate()
                    continue

                if r.status_code != 200:
                    logger.warning(
                        "Google returned %d on attempt %d",
                        r.status_code,
                        attempt + 1,
                    )
                    self.delay.mark_error()
                    self.delay.wait()
                    continue

                self.delay.mark_success()
                return self._parse_html(r.text)

            except requests.Timeout:
                logger.warning("Google timeout on attempt %d", attempt + 1)
                self.delay.mark_error()
                self.delay.wait()
            except requests.RequestException as e:
                logger.warning("Google request error: %s", e)
                self.delay.mark_error()
                self.delay.wait()

        return []

    def _parse_html(self, html: str) -> list[SearchResult]:
        """Parse Google search results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Google's result containers have various selectors
        # Modern Google uses div.g or div[data-sokoban-container]
        result_divs = soup.select("div.g")

        for div in result_divs:
            # Skip non-result divs
            if div.select_one("div.g:not([data-sokoban-container])"):
                continue

            # Title and link
            link_el = div.select_one("a[href^='http']")
            if not link_el:
                link_el = div.select_one("h3")
                if link_el:
                    parent_a = link_el.find_parent("a")
                    if parent_a:
                        link_el = parent_a

            if not link_el:
                continue

            url = str(link_el.get("href", "") or "")
            if not url or not url.startswith("http"):
                continue

            # Title
            title_el = div.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else ""

            # Snippet
            snippet_els = div.select("div.VwiC3b, span.aCOpRe, div[data-sncf]")
            snippet = ""
            for el in snippet_els:
                text = el.get_text(strip=True)
                if len(text) > len(snippet):
                    snippet = text

            if url:
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
