"""Interactive REPL: run multiple queries without restarting the process."""

import argparse
import asyncio
import shlex
import sys

from dorker import history
from dorker.dedup import deduplicate
from dorker.engines import ENGINES, SearchResult
from dorker.filters import filter_results
from dorker.orchestrator import run_search
from dorker.output import write_output
from dorker.ranking import rank

HELP_TEXT = """
Type a query to search, or use one of these commands:
  :engine NAME[,NAME...]   Set engine(s) to use (or "all")
  :pages N                 Set number of result pages to fetch
  :format FORMAT           Set output format (table/json/csv)
  :sort MODE               Set sort order (score/position/engine)
  :history [N]             Show the last N queries (default 10)
  :save FILE               Save the last results to a file
  :help                    Show this message
  :quit / :exit            Leave the REPL
""".strip()


class ReplState:
    """Holds settings and engine/session state that persist across queries."""

    def __init__(self, default_args: argparse.Namespace):
        self.engines: list[str] = (
            list(ENGINES) if default_args.engine == "all" else [default_args.engine]
        )
        self.pages = default_args.pages
        self.fmt = default_args.format
        self.sort = default_args.sort
        self.timeout = default_args.timeout
        self.max_retries = default_args.max_retries
        self.delay_range = (default_args.delay[0], default_args.delay[1])
        self.proxy = None
        self.proxy_pool = None
        self.last_results: list[SearchResult] = []

    def status_line(self) -> str:
        return (
            f"engines={','.join(self.engines)} pages={self.pages} "
            f"format={self.fmt} sort={self.sort}"
        )


def _handle_command(command: str, state: ReplState) -> bool:
    """Handle a `:command` line. Returns False if the REPL should exit."""
    parts = shlex.split(command[1:])
    if not parts:
        return True
    name, args = parts[0], parts[1:]

    if name in ("quit", "exit"):
        return False
    elif name == "help":
        print(HELP_TEXT)
        print(state.status_line())
    elif name == "engine" and args:
        value = args[0]
        state.engines = list(ENGINES) if value == "all" else value.split(",")
    elif name == "pages" and args:
        state.pages = int(args[0])
    elif name == "format" and args:
        state.fmt = args[0]
    elif name == "sort" and args:
        state.sort = args[0]
    elif name == "history":
        limit = int(args[0]) if args else 10
        for row in history.list_history(limit):
            print(f"[{row['id']}] {row['timestamp']}  {row['query']}  ({row['engines']})")
    elif name == "save" and args:
        if not state.last_results:
            print("No results to save yet — run a query first.")
        else:
            write_output(state.last_results, fmt=state.fmt, output_file=args[0])
    else:
        print(f"Unknown command: {command} (try :help)")

    return True


async def _run_query(query: str, state: ReplState):
    results = await run_search(
        query=query,
        engine_names=state.engines,
        pages=state.pages,
        timeout=state.timeout,
        max_retries=state.max_retries,
        delay_range=state.delay_range,
        proxy=state.proxy,
        proxy_pool=state.proxy_pool,
    )
    results = deduplicate(results)
    results = filter_results(results)

    if state.sort == "score":
        results = rank(results, query)
    elif state.sort == "engine":
        results.sort(key=lambda r: r.engine)
    else:
        results.sort(key=lambda r: r.position)

    for i, r in enumerate(results, 1):
        r.position = i

    history.save_search(query, state.engines, results)
    state.last_results = results

    write_output(results, fmt=state.fmt)
    print(
        f"\nTotal: {len(results)} results from {len(state.engines)} engine(s)",
        file=sys.stderr,
    )


def run_repl(default_args: argparse.Namespace):
    state = ReplState(default_args)
    print("dorker interactive mode. Type :help for commands, :quit to leave.")
    print(state.status_line())

    while True:
        try:
            line = input("dorker> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        if line.startswith(":"):
            if not _handle_command(line, state):
                break
            continue

        try:
            asyncio.run(_run_query(line, state))
        except Exception as e:
            print(f"Search failed: {e}")
