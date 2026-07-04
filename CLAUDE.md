# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` (see `uv.lock`) and requires Python >=3.13.

```bash
uv sync                                      # install dependencies
uv run dorker "site:gov.br senha"                       # run a search
uv run dorker                                           # no query → enters interactive REPL mode
uv run dorker "filetype:pdf confidential" --engine all --output results.json --format json
```

There is no test suite or linter configured in this project (no `[tool.pytest]`/`[tool.ruff]` in `pyproject.toml`, no dev dependency group). Verification is manual: run the CLI and inspect output/logs.

The optional AI query-expansion feature (`--ai-expand`) needs the `anthropic` package: `uv pip install 'dorker[ai]'` (or `uv sync --extra ai`). Without it, `--ai-expand` logs a warning and falls back to running the query unmodified — this is intentional, not a bug.

## Architecture

`dorker` is a CLI that fans a search query out to multiple search engines concurrently, merges/deduplicates/ranks the results, and optionally offers an interactive REPL and AI-assisted query expansion.

- **Entry point**: `dorker/cli.py:main` (registered as the `dorker` script; also reachable via `python -m dorker`). With no `query` argument (or `-i`/`--interactive`), it enters `dorker/repl.py:run_repl` instead of running a single search.
- **Engine registry** (`dorker/engines/registry.py`): `ENGINES: dict[str, type[BaseEngine]]` is the single source of truth mapping engine names to classes. `--engine all` expands to `list(ENGINES)` — adding a new engine only requires registering it here; `cli.py` needs no changes.
- **Engines** (`dorker/engines/`): all subclass `BaseEngine` (`dorker/engines/base.py`) and implement `search(query, pages) -> list[SearchResult]` / `is_available()`.
  - `duckduckgo.py` wraps the third-party `ddgs` library directly (no HTML parsing, no `httpx`).
  - `google.py`, `mojeek.py`, `searx.py`, `brave.py` scrape HTML via `httpx` + `BeautifulSoup`, sharing a common retry/backoff/block-detection loop via `dorker/engines/scraping_base.py::fetch_with_retry` (don't reimplement per-engine retry logic — extend `fetch_with_retry` instead).
  - `searx.py` additionally manages a pool of public SearX/SearXNG instances via `dorker/rotation.py::HealthTrackedPool` (generic health-tracked candidate pool — also reused by `dorker/proxy.py::ProxyPool`).
  - A **Bing** engine was deliberately not built: it serves a hard JS challenge page on the very first plain request, and building scraping for it would edge toward the "bypass anti-bot" territory this project avoids. Don't add one without revisiting that call.
- **Concurrency** (`dorker/orchestrator.py::run_search`): runs each engine in its own thread via `asyncio.to_thread` (not full async — `ddgs` and the scraping libs are sync, and the I/O-bound bottleneck doesn't need true async to parallelize). Each engine gets its **own** `Session` and `DelayManager` instance — they are not shared across engines. A failure in one engine (raised exception) doesn't prevent others from returning results (`asyncio.gather(..., return_exceptions=True)`).
- **Anti-detection** (`dorker/anti_detect.py`): `Session` (fake browser identity — UA/headers/cookies/`proxy`, with `.rotate()` regenerating everything including a fresh proxy from `proxy_pool` if one is set) and `DelayManager` (randomized inter-request delay with exponential backoff via `mark_error()`/`mark_success()`). Both are constructed fresh per engine per search (see Concurrency above) — never shared/mutated across engines.
- **Block detection** (`dorker/block_detection.py::classify_response`): checks response body content **before** status code, because CAPTCHA/challenge pages are often served with a normal 200 (e.g. after a redirect) — status-code-only checks miss them. Markers are deliberately long, specific phrases (not bare words like `"captcha"`), and only checked when the response body is short (`< 20_000` chars) — a generic word appearing inside a huge legitimate results page (e.g. in an embedded i18n bundle) is a false positive, not a real block. On `BLOCKED_CAPTCHA`, `fetch_with_retry` stops immediately and does **not** retry — this is a deliberate ethical boundary, not a bug: the project does not attempt to detect-and-bypass anti-bot challenges.
- **Proxy support**: `--proxy`/`--tor`/`--proxy-file` in `cli.py` resolve to a `proxy: str | None` and/or `dorker/proxy.py::ProxyPool` passed into `orchestrator.run_search`, which threads them into each engine's `Session`. Use `socks5h://` (not `socks5://`) for Tor/SOCKS so DNS resolves through the proxy.
- **Result post-processing pipeline** (`cli.py:main`, in order): `dorker/dedup.py::deduplicate` (merges same-URL results across engines into one `SearchResult`, tracking all contributing engines in `.sources`) → `dorker/filters.py::filter_results` (`--include-domain`/`--exclude-domain`/`--min-snippet-length`) → `dorker/ranking.py::rank` (default `--sort score`: a simple, explainable score — cross-engine agreement + query-term matches + snippet length — not ML) → positions renumbered → `dorker/history.py::save_search` (SQLite at `~/.local/share/dorker/history.db`, skippable with `--no-history`) → `dorker/output.py::write_output`.
- **`SearchResult`** (`dorker/engines/base.py`) has `sources: list[str]` and `score: float` in addition to the original fields. Any new field added here must also be threaded through all three formatters in `dorker/output.py` (`format_table`/`format_json`/`format_csv`) — easy to update two of three and silently drop a field from the third.
- **REPL** (`dorker/repl.py::run_repl`): builds one `ReplState` (engines/pages/format/sort settings) for the whole session and reuses it across queries — unlike the one-shot CLI path, engine objects aren't recreated per query. Commands are `:engine`, `:pages`, `:format`, `:sort`, `:history`, `:save`, `:help`, `:quit`/`:exit`; anything not starting with `:` is treated as a new query and run through the same `orchestrator.run_search` → dedup → filter → rank → history → output pipeline as the non-interactive path.
- **AI query expansion** (`dorker/ai/query_expand.py::suggest_variations`, opt-in via `--ai-expand`): calls the Anthropic API (`claude-opus-4-8`) to suggest dork variations as plain text, shown to the user for manual selection before running. The model only ever sees/produces text — it never touches scraped HTML, search engines, or anti-detection in any way; this boundary is intentional and should be preserved in any future AI feature. Degrades to a no-op (with a logged warning) if the `anthropic` package isn't installed or no credentials resolve — both are expected states for a project where this dependency is optional, so failures here are caught broadly (`except Exception`) rather than only `anthropic`'s own exception types.

## Non-obvious repo state

- `--engine all` runs **all** currently-registered engines (`duckduckgo`, `mojeek`, `google`, `searx`, `brave`) — this used to silently only run 2 of 4 engines before the registry refactor; if search volume/latency seems off, check `ENGINES` in `dorker/engines/registry.py` rather than assuming a specific hardcoded list.
- `data/` is gitignored; holds ad-hoc output files from manual runs, not a durable store (the durable one is `dorker/history.py`'s SQLite DB under `~/.local/share/dorker/`).
- Google/Mojeek/SearX returning 0 results in a given run is often real upstream rate-limiting/CAPTCHA from repeated local testing, not a parsing bug — check the logs for `blocked by CAPTCHA` / rate-limit warnings before assuming a selector broke.
