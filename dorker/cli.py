"""CLI entry point for dorker."""

import argparse
import logging
import sys
import time
from typing import Optional

from dorker.engines import DuckDuckGoEngine, SearXEngine, GoogleEngine, MojeekEngine, SearchResult
from dorker.anti_detect import Session, DelayManager
from dorker.output import write_output

logger = logging.getLogger("dorker")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dorker",
        description="Multi-engine search dork aggregator with anti-detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dorker "site:gov.br senha"
  dorker "intitle:index.of mp3" --engine duckduckgo --pages 3
  dorker "filetype:pdf confidential" --engine all --output results.json --format json
  dorker "inurl:admin login" --engine searx --delay 5 12 --timeout 20
        """,
    )

    p.add_argument(
        "query",
        help="Search query / dork string",
    )
    p.add_argument(
        "-e", "--engine",
        choices=["duckduckgo", "searx", "google", "mojeek", "all"],
        default="all",
        help="Search engine to use (default: all)",
    )
    p.add_argument(
        "-p", "--pages",
        type=int,
        default=1,
        help="Number of result pages to fetch (default: 1)",
    )
    p.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write results to file instead of stdout",
    )
    p.add_argument(
        "-f", "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )
    p.add_argument(
        "--delay",
        nargs=2,
        type=float,
        metavar=("MIN", "MAX"),
        default=[2.0, 8.0],
        help="Delay range between requests in seconds (default: 2 8)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="Request timeout in seconds (default: 15)",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries per request (default: 3)",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    p.add_argument(
        "--no-rotate",
        action="store_true",
        help="Disable identity rotation between pages",
    )

    return p


def run_engine(
    engine_name: str,
    query: str,
    pages: int,
    session: Session,
    delay: DelayManager,
    timeout: int,
    max_retries: int,
) -> list[SearchResult]:
    """Run a single engine and return results."""
    if engine_name == "duckduckgo":
        engine = DuckDuckGoEngine(
            session=session,
            delay=delay,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif engine_name == "searx":
        engine = SearXEngine(
            session=session,
            delay=delay,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif engine_name == "google":
        engine = GoogleEngine(
            session=session,
            delay=delay,
            timeout=timeout,
            max_retries=max_retries,
        )
    elif engine_name == "mojeek":
        engine = MojeekEngine(
            session=session,
            delay=delay,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        logger.error("Unknown engine: %s", engine_name)
        return []

    if not engine.is_available():
        logger.error("Engine %s is not available", engine_name)
        return []

    logger.info("Searching %s for: %s", engine_name, query)
    start = time.monotonic()
    results = engine.search(query, pages=pages)
    elapsed = time.monotonic() - start
    logger.info(
        "%s: %d results in %.1fs", engine_name, len(results), elapsed
    )
    return results


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Setup anti-detection
    session = Session()
    delay = DelayManager(min_delay=args.delay[0], max_delay=args.delay[1])

    # Determine engines to use
    if args.engine == "all":
        engines = ["duckduckgo", "mojeek"]
    else:
        engines = [args.engine]

    # Run engines
    all_results: list[SearchResult] = []

    for engine_name in engines:
        results = run_engine(
            engine_name=engine_name,
            query=args.query,
            pages=args.pages,
            session=session,
            delay=delay,
            timeout=args.timeout,
            max_retries=args.max_retries,
        )
        all_results.extend(results)

        # Rotate identity between engines
        if not args.no_rotate and engine_name != engines[-1]:
            session.rotate()

    # Sort by position (interleaved from multiple engines)
    all_results.sort(key=lambda r: r.position)

    # Re-number positions
    for i, r in enumerate(all_results, 1):
        r.position = i

    # Output
    write_output(all_results, fmt=args.format, output_file=args.output)

    # Summary to stderr
    print(
        f"\nTotal: {len(all_results)} results from {len(engines)} engine(s)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
