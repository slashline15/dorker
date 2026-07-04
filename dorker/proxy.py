"""User-supplied proxy pool with health tracking."""

import logging

import httpx

from dorker.rotation import HealthTrackedPool

logger = logging.getLogger(__name__)

# Used only to health-check a proxy; any endpoint that returns 200 quickly works.
PROBE_URL = "https://www.mojeek.com/"


def _probe_proxy(proxy: str) -> bool:
    try:
        r = httpx.get(PROBE_URL, proxy=proxy, timeout=8)
        return r.status_code == 200
    except Exception:
        return False


class ProxyPool(HealthTrackedPool[str]):
    """Health-tracked pool of proxy URLs (http://, socks5://, socks5h://)."""

    def __init__(self, proxies: list[str]):
        super().__init__(proxies, probe=_probe_proxy)

    @classmethod
    def from_file(cls, path: str) -> "ProxyPool":
        """Load one proxy URL per line; blank lines and '#' comments are skipped."""
        with open(path, "r", encoding="utf-8") as f:
            proxies = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
        return cls(proxies)
