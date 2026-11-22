"""Print rows from the local DuckDB file (read-only).

uv run python -m jds.peek fx_rates --limit 20
uv run python -m jds.peek air_quality_hourly --date 2026-11-20
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import duckdb

from jds.pipeline import DATASET, LOCAL_DUCKDB, SOURCES

DATE_COLUMNS = {s.table: s.date_column for s in SOURCES.values()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("table", choices=sorted(DATE_COLUMNS))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--date", type=date.fromisoformat, help="filter one date (WIB)")
    args = parser.parse_args(argv)

    if not LOCAL_DUCKDB.exists():
        print(f"{LOCAL_DUCKDB} does not exist yet. Run the pipeline first.", file=sys.stderr)
        return 1

    table = f"{DATASET}.{args.table}"
    date_col = DATE_COLUMNS[args.table]
    with duckdb.connect(str(LOCAL_DUCKDB), read_only=True) as con:
        select = f"SELECT * EXCLUDE (_dlt_load_id, _dlt_id) FROM {table}"
        if args.date:
            rel = con.sql(f"{select} WHERE {date_col} = ? ORDER BY 1", params=[args.date])
        else:
            rel = con.sql(f"{select} ORDER BY 1 DESC LIMIT ?", params=[args.limit])
        rows = rel.fetchall()
        print(format_table(rel.columns, rows))
        total = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
    if args.date:
        print(f"Rows for {date_col} = {args.date}: {len(rows)}")
    print(f"Total rows in {table}: {total}")
    return 0


def format_table(columns: list[str], rows: list[tuple]) -> str:
    """Plain ASCII table (rel.show() breaks on Windows cp1252 consoles)."""
    cells = [[str(c) for c in columns]] + [[str(v) for v in row] for row in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(columns))]
    lines = [" | ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in cells]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
