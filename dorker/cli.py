"""CLI entry point for dorker."""

import argparse
import asyncio
import logging
import sys

from dorker import history
from dorker.dedup import deduplicate
from dorker.engines import ENGINES, SearchResult
from dorker.filters import filter_results
from dorker.orchestrator import run_search
from dorker.output import write_output
from dorker.proxy import ProxyPool
from dorker.ranking import rank
from dorker.repl import run_repl

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
        nargs="?",
        default=None,
        help="Search query / dork string (omit to enter interactive mode)",
    )
    p.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Enter interactive REPL mode (also triggered by omitting query)",
    )
    p.add_argument(
        "-e", "--engine",
        choices=[*ENGINES, "all"],
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
        "--proxy",
        metavar="URL",
        help="Proxy URL for all requests (http://, socks5://, socks5h://)",
    )
    p.add_argument(
        "--tor",
        action="store_true",
        help="Shortcut for --proxy socks5h://127.0.0.1:9050 (standalone Tor daemon)",
    )
    p.add_argument(
        "--proxy-file",
        metavar="FILE",
        help="File with one proxy URL per line; rotates between healthy ones",
    )
    p.add_argument(
        "--include-domain",
        action="append",
        metavar="DOMAIN",
        help="Only keep results from this domain (repeatable)",
    )
    p.add_argument(
        "--exclude-domain",
        action="append",
        metavar="DOMAIN",
        help="Drop results from this domain (repeatable)",
    )
    p.add_argument(
        "--min-snippet-length",
        type=int,
        default=0,
        metavar="N",
        help="Drop results with a snippet shorter than N characters",
    )
    p.add_argument(
        "--sort",
        choices=["score", "position", "engine"],
        default="score",
        help="Result order: score (relevance), position (per-engine order), or engine (default: score)",
    )
    p.add_argument(
        "--no-history",
        action="store_true",
        help="Don't save this search to local history",
    )
    p.add_argument(
        "--ai-expand",
        action="store_true",
        help="Suggest AI-generated dork variations before searching (requires 'dorker[ai]' + an Anthropic API key)",
    )

    return p


def _resolve_queries(query: str, ai_expand: bool) -> list[str]:
    """Return the list of queries to run: just the original, or the original
    plus any AI-suggested variations the user chooses to include."""
    if not ai_expand:
        return [query]

    from dorker.ai.query_expand import suggest_variations

    suggestions = suggest_variations(query)
    if not suggestions:
        return [query]

    print("AI-suggested query variations:", file=sys.stderr)
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s}", file=sys.stderr)

    try:
        choice = input("Include which? (e.g. 1,3 / blank for none): ").strip()
    except EOFError:
        choice = ""

    indices = [int(x) for x in choice.split(",") if x.strip().isdigit()]
    extra = [suggestions[i - 1] for i in indices if 0 < i <= len(suggestions)]
    return [query, *extra]


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

    if args.interactive or args.query is None:
        run_repl(args)
        return

    # Determine engines to use
    if args.engine == "all":
        engines = list(ENGINES)
    else:
        engines = [args.engine]

    # Resolve proxy configuration
    if args.tor and args.proxy:
        parser.error("--tor and --proxy are mutually exclusive")
    proxy = "socks5h://127.0.0.1:9050" if args.tor else args.proxy
    proxy_pool = ProxyPool.from_file(args.proxy_file) if args.proxy_file else None

    queries = _resolve_queries(args.query, args.ai_expand)

    # Run engines concurrently (per query), each with its own isolated identity
    all_results: list[SearchResult] = []
    for q in queries:
        all_results.extend(
            asyncio.run(
                run_search(
                    query=q,
                    engine_names=engines,
                    pages=args.pages,
                    timeout=args.timeout,
                    max_retries=args.max_retries,
                    delay_range=(args.delay[0], args.delay[1]),
                    proxy=proxy,
                    proxy_pool=proxy_pool,
                )
            )
        )

    all_results = deduplicate(all_results)
    all_results = filter_results(
        all_results,
        include_domains=args.include_domain,
        exclude_domains=args.exclude_domain,
        min_snippet_length=args.min_snippet_length,
    )

    if args.sort == "score":
        all_results = rank(all_results, args.query)
    elif args.sort == "engine":
        all_results.sort(key=lambda r: r.engine)
    else:
        all_results.sort(key=lambda r: r.position)

    # Re-number positions to reflect the final display order
    for i, r in enumerate(all_results, 1):
        r.position = i

    if not args.no_history:
        history.save_search(args.query, engines, all_results)

    # Output
    write_output(all_results, fmt=args.format, output_file=args.output)

    # Summary to stderr
    print(
        f"\nTotal: {len(all_results)} results from {len(engines)} engine(s)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
