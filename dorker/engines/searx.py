"""SearX engine — queries public SearX instances with rotation."""

import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from dorker.engines.base import BaseEngine, SearchResult
from dorker.engines.scraping_base import fetch_with_retry
from dorker.anti_detect import Session, DelayManager
from dorker.rotation import HealthTrackedPool

logger = logging.getLogger(__name__)

# Public SearX/SearXNG instances (verified working as of 2026)
# These aggregate Google, Bing, DuckDuckGo, Brave, etc.
SEARX_INSTANCES = [
    "https://search.sapti.me",
    "https://searx.be",
    "https://search.bus-hit.me",
    "https://searx.tiekoetter.com",
    "https://searx.work",
    "https://search.rowie.at",
    "https://searx.si",
    "https://search.ononoki.org",
    "https://searx.dresden.network",
    "https://searx.fmac.xyz",
    "https://search.rhscz.eu",
    "https://searx.roflcopter.fr",
    "https://searx.mha.fi",
    "https://search.canine.tools",
    "https://searx.oloke.xyz",
    "https://searx.xyz",
    "https://searxng.world",
    "https://search.hbubli.cc",
    "https://searx.ox2.fr",
    "https://searx.prvcy.eu",
]

# Fallback: SearXNG public instances
SEARXNG_INSTANCES = [
    "https://searxng.site",
    "https://search.inetol.net",
    "https://search.ipv6s.net",
    "https://opnxng.com",
    "https://priv.au",
    "https://search.smnz.de",
]


class SearXEngine(BaseEngine):
    """SearX/SearXNG meta-search engine with instance rotation."""

    name = "searx"

    def __init__(
        self,
        session: Optional[Session] = None,
        delay: Optional[DelayManager] = None,
        timeout: int = 20,
        max_retries: int = 3,
        instances: Optional[list[str]] = None,
    ):
        self.session = session or Session()
        self.delay = delay or DelayManager(min_delay=3.0, max_delay=8.0)
        self.timeout = timeout
        self.max_retries = max_retries
        self.instances = instances or (SEARX_INSTANCES + SEARXNG_INSTANCES)
        self._pool = HealthTrackedPool(self.instances, probe=self._probe_instance)

    def is_available(self) -> bool:
        return len(self._pool.get_working()) > 0

    def _probe_instance(self, base_url: str) -> bool:
        """Quick health check on a SearX instance."""
        try:
            r = httpx.get(
                f"{base_url}/search",
                params={"q": "test"},
                headers=self.session.headers(),
                timeout=5,
                follow_redirects=True,
                proxy=self.session.proxy,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True
            return False
        except Exception:
            return False

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0

        for page_num in range(pages):
            self.delay.wait()

            instance = self._pool.pick()
            if not instance:
                logger.error("No working SearX instances available")
                break

            page_results = self._fetch_page(instance, query, page_num + 1)

            if page_results is None:
                # Instance failed, try another
                self._pool.mark_dead(instance)
                instance = self._pool.pick()
                if not instance:
                    break
                page_results = self._fetch_page(instance, query, page_num + 1)

            if not page_results:
                break

            for r in page_results:
                position += 1
                r.position = position
                results.append(r)

            # Rotate identity between pages
            if page_num < pages - 1:
                self.session.rotate()

        return results

    def _fetch_page(
        self, base_url: str, query: str, page: int
    ) -> Optional[list[SearchResult]]:
        """Fetch a single page from a SearX instance."""
        search_url = f"{base_url}/search"

        params = {
            "q": query,
            "categories": "general",
            "language": "en",
            "format": "html",
        }
        if page > 1:
            params["pageno"] = str(page)

        html = fetch_with_retry(
            search_url,
            params=params,
            session=self.session,
            delay=self.delay,
            timeout=self.timeout,
            max_retries=self.max_retries,
            engine_name=f"SearX ({base_url})",
            rotate_on_rate_limit=False,
        )
        if html is None:
            return None
        return self._parse_html(html, base_url)

    def _parse_html(
        self, html: str, base_url: str
    ) -> list[SearchResult]:
        """Parse SearX/SearXNG HTML results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        # SearX classic: results in div.article
        # SearXNG: results in article.result
        for article in soup.select("article.result, div.result, .result"):
            # Title
            title_el = article.select_one("h3 a, h4 a, .result-title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")

            # Snippet
            snippet_el = article.select_one(
                ".result-content, .result-snippet, .content, p.content"
            )
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            # Engine source (SearXNG shows which engine provided the result)
            engine_el = article.select_one(".result-engines, .result-source")
            source_engine = engine_el.get_text(strip=True) if engine_el else ""

            if url and title:
                results.append(
                    SearchResult(
                        url=str(url),
                        title=title,
                        snippet=snippet,
                        engine=f"{self.name}/{source_engine}" if source_engine else self.name,
                        position=0,
                    )
                )

        return results
