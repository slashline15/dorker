"""Output formatting: JSON, CSV, table."""

import json
import csv
import sys
from io import StringIO
from typing import Optional

from dorker.engines.base import SearchResult


def format_table(results: list[SearchResult]) -> str:
    """Format results as a readable table for terminal output."""
    if not results:
        return "No results found."

    lines = []
    for r in results:
        lines.append(f"[{r.position:3d}] {r.title}")
        lines.append(f"      URL:    {r.url}")
        lines.append(f"      Engine: {r.engine}")
        if r.snippet:
            # Truncate long snippets
            snippet = r.snippet[:200] + "..." if len(r.snippet) > 200 else r.snippet
            lines.append(f"      Snippet: {snippet}")
        lines.append("")

    return "\n".join(lines)


def format_json(results: list[SearchResult], pretty: bool = True) -> str:
    """Format results as JSON."""
    data = [
        {
            "position": r.position,
            "title": r.title,
            "url": r.url,
            "snippet": r.snippet,
            "engine": r.engine,
            "timestamp": r.timestamp,
        }
        for r in results
    ]
    indent = 2 if pretty else None
    return json.dumps(data, indent=indent, ensure_ascii=False)


def format_csv(results: list[SearchResult]) -> str:
    """Format results as CSV."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["position", "title", "url", "snippet", "engine", "timestamp"])
    for r in results:
        writer.writerow(
            [r.position, r.title, r.url, r.snippet, r.engine, r.timestamp]
        )
    return output.getvalue()


def write_output(
    results: list[SearchResult],
    fmt: str = "table",
    output_file: Optional[str] = None,
):
    """Write results to stdout or file."""
    formatters = {
        "table": format_table,
        "json": format_json,
        "csv": format_csv,
    }

    formatter = formatters.get(fmt, format_table)
    output = formatter(results)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Results written to {output_file}", file=sys.stderr)
    else:
        print(output)
