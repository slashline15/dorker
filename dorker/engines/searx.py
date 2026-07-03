"""SearX engine — queries public SearX instances with rotation."""

import logging
import random
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from dorker.engines.base import BaseEngine, SearchResult
from dorker.anti_detect import Session, DelayManager

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
        self._working_instances: list[str] = []
        self._dead_instances: set[str] = set()

    def is_available(self) -> bool:
        return len(self._get_working_instances()) > 0

    def _get_working_instances(self) -> list[str]:
        """Return list of instances that responded recently."""
        if self._working_instances:
            return self._working_instances

        # Probe a few instances
        candidates = random.sample(
            [i for i in self.instances if i not in self._dead_instances],
            min(5, len(self.instances)),
        )
        for url in candidates:
            if self._probe_instance(url):
                self._working_instances.append(url)

        return self._working_instances

    def _probe_instance(self, base_url: str) -> bool:
        """Quick health check on a SearX instance."""
        try:
            r = requests.get(
                f"{base_url}/search",
                params={"q": "test"},
                headers=self.session.headers(),
                timeout=5,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True
            return False
        except Exception:
            return False

    def _pick_instance(self) -> Optional[str]:
        """Pick a working instance, rotating through them."""
        working = self._get_working_instances()
        if not working:
            return None
        return random.choice(working)

    def _mark_dead(self, base_url: str):
        """Remove a dead instance from rotation."""
        if base_url in self._working_instances:
            self._working_instances.remove(base_url)
        self._dead_instances.add(base_url)

    def search(self, query: str, pages: int = 1) -> list[SearchResult]:
        results: list[SearchResult] = []
        position = 0

        for page_num in range(pages):
            self.delay.wait()

            instance = self._pick_instance()
            if not instance:
                logger.error("No working SearX instances available")
                break

            page_results = self._fetch_page(instance, query, page_num + 1)

            if page_results is None:
                # Instance failed, try another
                self._mark_dead(instance)
                instance = self._pick_instance()
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

        for attempt in range(self.max_retries):
            try:
                r = requests.get(
                    search_url,
                    params=params,
                    headers=self.session.headers(),
                    timeout=self.timeout,
                )

                if r.status_code == 429:
                    logger.warning("SearX rate limited on %s", base_url)
                    self.delay.mark_error()
                    self.delay.wait()
                    continue

                if r.status_code != 200:
                    logger.warning(
                        "SearX returned %d from %s", r.status_code, base_url
                    )
                    self.delay.mark_error()
                    self.delay.wait()
                    continue

                self.delay.mark_success()
                return self._parse_html(r.text, base_url)

            except requests.Timeout:
                logger.warning("SearX timeout on %s", base_url)
                self.delay.mark_error()
                self.delay.wait()
            except requests.RequestException as e:
                logger.warning("SearX error on %s: %s", base_url, e)
                self.delay.mark_error()
                self.delay.wait()

        return None

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
