"""Ingestion entrypoint. Safe to re-run: every resource merges on its primary key.

uv run python -m jds.pipeline --source fx --dest duckdb
uv run python -m jds.pipeline --source all --dest duckdb --start 2026-11-01 --end 2026-11-20
uv run python -m jds.pipeline --source all --dest postgres
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import dlt
from dotenv import load_dotenv

from jds.check_db import connect
from jds.config import LOCATIONS, TIMEZONE, ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging
from jds.sources.frankfurter import fx_rates
from jds.sources.open_meteo import air_quality_hourly, weather_daily

log = logging.getLogger("jds.pipeline")

DATASET = "raw"
# Absolute on purpose: dlt keeps pipeline state in ~/.dlt and reuses the stored path for
# relative paths, so a second clone would silently write into the first clone's file.
REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DUCKDB = REPO_ROOT / "data" / "jds_local.duckdb"
DEFAULT_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class SourceSpec:
    table: str
    date_column: str
    primary_key: tuple[str, ...]


SOURCES: dict[str, SourceSpec] = {
    "fx": SourceSpec("fx_rates", "rate_date", ("rate_date", "base", "quote")),
    "weather": SourceSpec("weather_daily", "date_wib", ("date_wib", "location_id")),
    "air": SourceSpec("air_quality_hourly", "date_wib", ("ts_wib", "location_id")),
}


@dataclass(frozen=True)
class TableSummary:
    rows: int
    duplicate_keys: int
    min_date: date | None
    max_date: date | None


def now_wib() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE))


def today_wib() -> date:
    return now_wib().date()


def resolve_range(start: date | None, end: date | None, today: date) -> tuple[date, date]:
    """Default range is [today - 7, today] in WIB. Future dates are rejected."""
    end = end or today
    start = start or end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if end > today:
        raise ValueError(f"--end {end} is in the future (today in WIB: {today}).")
    if start > end:
        raise ValueError(f"--start {start} is after --end {end}.")
    return start, end


def make_destination(dest: str):
    if dest == "duckdb":
        LOCAL_DUCKDB.parent.mkdir(exist_ok=True)
        return dlt.destinations.duckdb(str(LOCAL_DUCKDB))
    if dest == "postgres":
        url = get_database_url()
        log.info("Destination Neon Postgres: %s", mask_url(url))
        connect(url).close()  # wake the Neon compute with retries before dlt connects
        return dlt.destinations.postgres(credentials=url)
    raise ValueError(f"Unknown destination: {dest}")


def build_resources(selected: list[str], start: date, end: date, now: datetime) -> list:
    factories = {
        "fx": lambda: fx_rates(start, end),
        "weather": lambda: weather_daily(start, end, LOCATIONS, now),
        "air": lambda: air_quality_hourly(start, end, LOCATIONS, now),
    }
    return [factories[name]() for name in selected]


def summarize(pipeline: dlt.Pipeline, selected: list[str]) -> dict[str, TableSummary]:
    """Row and duplicate-key counts per table. Any duplicate means merge did not work."""
    out = {}
    with pipeline.sql_client() as client:
        for name in selected:
            spec = SOURCES[name]
            pk = ", ".join(spec.primary_key)
            ((total, min_d, max_d),) = client.execute_sql(
                f"SELECT count(*), min({spec.date_column}), max({spec.date_column}) "
                f"FROM {spec.table}"
            )
            (dupes,) = client.execute_sql(
                f"SELECT count(*) FROM (SELECT {pk} FROM {spec.table} "
                f"GROUP BY {pk} HAVING count(*) > 1) d"
            )[0]
            out[spec.table] = TableSummary(total, dupes, min_d, max_d)
    return out


def load(
    pipeline: dlt.Pipeline, selected: list[str], start: date, end: date, now: datetime
) -> dict[str, TableSummary]:
    log.info("Running source=%s range=%s..%s", ",".join(selected), start, end)
    load_info = pipeline.run(build_resources(selected, start, end, now))
    log.info("Load finished: %s", load_info)

    summary = summarize(pipeline, selected)
    for table, s in summary.items():
        log.info(
            "%s.%s now: %d rows (%s to %s), duplicate keys: %d",
            DATASET,
            table,
            s.rows,
            s.min_date,
            s.max_date,
            s.duplicate_keys,
        )
    return summary


def run(source: str, dest: str, start: date, end: date) -> int:
    pipeline = dlt.pipeline(
        pipeline_name=f"jds_{dest}",
        destination=make_destination(dest),
        dataset_name=DATASET,
    )
    selected = list(SOURCES) if source == "all" else [source]
    summary = load(pipeline, selected, start, end, now_wib())

    dupes = {t: s.duplicate_keys for t, s in summary.items() if s.duplicate_keys}
    if dupes:
        log.error("Duplicate primary keys found: %s", dupes)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    setup_logging()
    parser = argparse.ArgumentParser(description="Jakarta Daily Signals ingestion")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument("--dest", choices=["duckdb", "postgres"], default="duckdb")
    parser.add_argument("--start", type=date.fromisoformat, help="YYYY-MM-DD (WIB)")
    parser.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (WIB)")
    args = parser.parse_args(argv)

    try:
        start, end = resolve_range(args.start, args.end, today_wib())
        return run(args.source, args.dest, start, end)
    except (ValueError, ConfigError) as exc:
        log.error("%s", exc)
        return 2
    except Exception:
        log.exception("Pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
