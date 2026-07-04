"""Shared retry/backoff HTTP fetch logic for scraping-based engines."""

import logging
from typing import Optional

import httpx

from dorker.anti_detect import DelayManager, Session
from dorker.block_detection import BlockStatus, classify_response

logger = logging.getLogger(__name__)


def fetch_with_retry(
    url: str,
    *,
    params: dict,
    session: Session,
    delay: DelayManager,
    timeout: int,
    max_retries: int,
    engine_name: str,
    extra_headers: Optional[dict] = None,
    rate_limit_statuses: tuple[int, ...] = (429,),
    rotate_on_rate_limit: bool = True,
) -> Optional[str]:
    """GET a URL with retry/backoff and rate-limit handling.

    Returns the response body text, or None if all attempts failed.
    """
    for attempt in range(max_retries):
        try:
            r = httpx.get(
                url,
                params=params,
                headers=session.headers(extra_headers),
                timeout=timeout,
                follow_redirects=True,
                proxy=session.proxy,
            )

            # Content-based check first: blocking pages (e.g. Google's CAPTCHA
            # redirect) are often served with a normal 200 status.
            if classify_response(r.status_code, r.text) == BlockStatus.BLOCKED_CAPTCHA:
                logger.error(
                    "%s blocked by CAPTCHA (status %d) — stopping, not attempting "
                    "to bypass; try again later, use --proxy/--tor, or another engine",
                    engine_name,
                    r.status_code,
                )
                return None

            if r.status_code in rate_limit_statuses:
                logger.warning(
                    "%s rate limited/blocked (status %d)", engine_name, r.status_code
                )
                delay.mark_error()
                delay.wait()
                if rotate_on_rate_limit:
                    session.rotate()
                continue

            if r.status_code != 200:
                logger.warning(
                    "%s returned %d on attempt %d",
                    engine_name,
                    r.status_code,
                    attempt + 1,
                )
                delay.mark_error()
                delay.wait()
                continue

            delay.mark_success()
            return r.text

        except httpx.TimeoutException:
            logger.warning("%s timeout on attempt %d", engine_name, attempt + 1)
            delay.mark_error()
            delay.wait()
        except httpx.HTTPError as e:
            logger.warning("%s request error: %s", engine_name, e)
            delay.mark_error()
            delay.wait()

    return None
