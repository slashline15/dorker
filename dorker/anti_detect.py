"""Anti-detection: rotating User-Agents, delays, isolated cookie jars."""

import random
import time
import http.cookiejar
from pathlib import Path
from dataclasses import dataclass, field

# ── User-Agent pool (50+ real browser UAs across platforms) ──────────────

UA_POOL = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    # Edge macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    # Safari iOS
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.102 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.100 Mobile Safari/537.36",
    # Opera Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/115.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 OPR/114.0.0.0",
    # Brave
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Vivaldi
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Vivaldi/7.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Vivaldi/7.0",
    # Chromium Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Older but still valid
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0",
    # Mobile Firefox
    "Mozilla/5.0 (Android 14; Mobile; rv:133.0) Gecko/133.0 Firefox/133.0",
    "Mozilla/5.0 (Android 14; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0",
    # Samsung Internet
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/130.0.6723.102 Mobile Safari/537.36",
    # UC Browser
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36 UCBrowser/16.0.0.1294",
]

# ── Accept-Language rotation ─────────────────────────────────────────────

LANG_POOL = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-US,en;q=0.9,pt;q=0.8",
    "pt-BR,pt;q=0.9,en;q=0.8,en-US;q=0.7",
    "en-CA,en;q=0.9,fr;q=0.8",
    "en-AU,en;q=0.9",
    "de-DE,de;q=0.9,en;q=0.8,en-US;q=0.7",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "es-ES,es;q=0.9,en;q=0.8",
    "en-US,en;q=0.9,es;q=0.8,pt;q=0.7",
]

# ── Referrer rotation ───────────────────────────────────────────────────

REFERRER_POOL = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://search.brave.com/",
    "https://www.google.com/search?q=related+topics",
    "https://www.bing.com/search?q=search+terms",
    "",  # direct visit
]

# ── Accept header rotation ───────────────────────────────────────────────

ACCEPT_POOL = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
]

# ── Sec-CH-UA rotation (client hints) ────────────────────────────────────

SEC_CH_UA_POOL = [
    '"Chromium";v="131", "Google Chrome";v="131", "Not?A_Brand";v="24"',
    '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    '"Chromium";v="129", "Google Chrome";v="129", "Not?A_Brand";v="99"',
    '"Microsoft Edge";v="131", "Chromium";v="131", "Not?A_Brand";v="24"',
    '"Firefox";v="133"',
    '"Opera";v="115", "Chromium";v="131", "Not?A_Brand";v="24"',
]


@dataclass
class Session:
    """Isolated session with its own cookie jar and identity."""

    cookie_jar: http.cookiejar.LWPCookieJar = field(
        default_factory=http.cookiejar.LWPCookieJar
    )
    user_agent: str = field(default_factory=lambda: random.choice(UA_POOL))
    accept_lang: str = field(default_factory=lambda: random.choice(LANG_POOL))
    referrer: str = field(default_factory=lambda: random.choice(REFERRER_POOL))
    accept: str = field(default_factory=lambda: random.choice(ACCEPT_POOL))
    sec_ch_ua: str = field(default_factory=lambda: random.choice(SEC_CH_UA_POOL))
    proxy: str | None = None
    proxy_pool: "HealthTrackedPool | None" = None

    def rotate(self):
        """Rotate all identifiers for a fresh fingerprint (and proxy, if pooled)."""
        self.user_agent = random.choice(UA_POOL)
        self.accept_lang = random.choice(LANG_POOL)
        self.referrer = random.choice(REFERRER_POOL)
        self.accept = random.choice(ACCEPT_POOL)
        self.sec_ch_ua = random.choice(SEC_CH_UA_POOL)
        self.cookie_jar = http.cookiejar.LWPCookieJar()
        if self.proxy_pool is not None:
            self.proxy = self.proxy_pool.pick()

    def headers(self, extra: dict | None = None) -> dict:
        """Build request headers from current session identity."""
        h = {
            "User-Agent": self.user_agent,
            "Accept": self.accept,
            "Accept-Language": self.accept_lang,
            # No "br": httpx's brotli decoder chokes on some real-world
            # responses (observed against Brave Search), turning a working
            # request into a hard decode failure on every retry.
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        if self.referrer:
            h["Referer"] = self.referrer
        if self.sec_ch_ua:
            h["Sec-CH-UA"] = self.sec_ch_ua
            h["Sec-CH-UA-Mobile"] = "?0"
            h["Sec-CH-UA-Platform"] = random.choice(
                ['"Windows"', '"macOS"', '"Linux"']
            )
        if extra:
            h.update(extra)
        return h


class DelayManager:
    """Intelligent delay with jitter between requests."""

    def __init__(self, min_delay: float = 2.0, max_delay: float = 8.0):
        self.min = min_delay
        self.max = max_delay
        self._last_request: float = 0.0
        self._consecutive_errors: int = 0

    def wait(self):
        """Sleep for a random interval, with backoff on errors."""
        base = random.uniform(self.min, self.max)
        backoff = base * (2 ** min(self._consecutive_errors, 4))
        jitter = random.uniform(-0.5, 0.5)
        delay = max(self.min, backoff + jitter)
        elapsed = time.monotonic() - self._last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.monotonic()

    def mark_error(self):
        self._consecutive_errors += 1

    def mark_success(self):
        self._consecutive_errors = max(0, self._consecutive_errors - 1)

    def reset(self):
        self._consecutive_errors = 0
