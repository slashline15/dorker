"""Runs multiple search engines concurrently, each with its own isolated identity."""

import asyncio
import logging
import time

from typing import Optional

from dorker.anti_detect import DelayManager, Session
from dorker.engines import ENGINES, SearchResult
from dorker.proxy import ProxyPool

logger = logging.getLogger("dorker")


async def _run_one(
    engine_name: str,
    query: str,
    pages: int,
    timeout: int,
    max_retries: int,
    delay_range: tuple[float, float],
    proxy: Optional[str],
    proxy_pool: Optional[ProxyPool],
) -> list[SearchResult]:
    engine_cls = ENGINES.get(engine_name)
    if engine_cls is None:
        logger.error("Unknown engine: %s", engine_name)
        return []

    session = Session(proxy=proxy_pool.pick() if proxy_pool else proxy, proxy_pool=proxy_pool)
    engine = engine_cls(
        session=session,
        delay=DelayManager(min_delay=delay_range[0], max_delay=delay_range[1]),
        timeout=timeout,
        max_retries=max_retries,
    )

    if not engine.is_available():
        logger.error("Engine %s is not available", engine_name)
        return []

    logger.info("Searching %s for: %s", engine_name, query)
    start = time.monotonic()
    results = await asyncio.to_thread(engine.search, query, pages)
    elapsed = time.monotonic() - start
    logger.info("%s: %d results in %.1fs", engine_name, len(results), elapsed)
    return results


async def run_search(
    query: str,
    engine_names: list[str],
    pages: int = 1,
    timeout: int = 15,
    max_retries: int = 3,
    delay_range: tuple[float, float] = (2.0, 8.0),
    proxy: Optional[str] = None,
    proxy_pool: Optional[ProxyPool] = None,
) -> list[SearchResult]:
    """Run each named engine in its own thread with an isolated Session/DelayManager.

    A failure in one engine (raised exception) does not prevent the others
    from returning their results.
    """
    tasks = [
        _run_one(name, query, pages, timeout, max_retries, delay_range, proxy, proxy_pool)
        for name in engine_names
    ]
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[SearchResult] = []
    for engine_name, outcome in zip(engine_names, gathered):
        if isinstance(outcome, BaseException):
            logger.error("Engine %s raised an exception: %s", engine_name, outcome)
            continue
        all_results.extend(outcome)

    return all_results
