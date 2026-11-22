"""End-to-end idempotency: real dlt into a temporary DuckDB, all APIs mocked.

Same data rerun keeps row counts, changed values overwrite rows, overlapping ranges
do not duplicate, and forecast rows turn into actuals in place.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import dlt
import pytest

from jds.pipeline import SOURCES, load
from jds.sources import frankfurter, open_meteo

WIB = ZoneInfo("Asia/Jakarta")
ALL = list(SOURCES)


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


class FakeApis:
    """Fake Frankfurter and Open-Meteo. Bumping `version` changes every value."""

    def __init__(self):
        self.version = 1
        self.calls = 0

    def __call__(self, url: str, params: dict | None = None):
        self.calls += 1
        params = params or {}
        if url.startswith(frankfurter.BASE_URL):
            start_s, end_s = url.rsplit("/", 1)[1].split("..")
            days = _days(date.fromisoformat(start_s), date.fromisoformat(end_s))
            weekdays = [d for d in days if d.weekday() < 5]
            return {
                "base": params["base"],
                "rates": {d.isoformat(): {"IDR": 18000 + d.day + self.version} for d in weekdays},
            }

        days = _days(
            date.fromisoformat(params["start_date"]), date.fromisoformat(params["end_date"])
        )
        meta = {"latitude": -6.15, "longitude": 106.84}
        if url == open_meteo.WEATHER_URL:
            return {
                **meta,
                "daily": {
                    "time": [d.isoformat() for d in days],
                    "temperature_2m_max": [30.0 + self.version for _ in days],
                },
            }
        if url == open_meteo.AIR_QUALITY_URL:
            hours = [f"{d.isoformat()}T{h:02d}:00" for d in days for h in range(24)]
            return {**meta, "hourly": {"time": hours, "pm2_5": [40.0 + self.version] * len(hours)}}
        raise AssertionError(f"Unexpected URL: {url}")


@pytest.fixture
def fake_apis(monkeypatch) -> FakeApis:
    fake = FakeApis()
    monkeypatch.setattr(frankfurter, "get_json", fake)
    monkeypatch.setattr(open_meteo, "get_json", fake)
    return fake


@pytest.fixture
def pipeline(tmp_path) -> dlt.Pipeline:
    """Isolated pipeline: dlt state and DuckDB file live in pytest's tmp_path."""
    return dlt.pipeline(
        pipeline_name="jds_test",
        pipelines_dir=str(tmp_path / "pipelines"),
        destination=dlt.destinations.duckdb(str(tmp_path / "test.duckdb")),
        dataset_name="raw",
    )


def query(pipeline: dlt.Pipeline, sql: str):
    with pipeline.sql_client() as client:
        return client.execute_sql(sql)


START, END = date(2026, 11, 16), date(2026, 11, 20)  # Monday..Friday
AFTER = datetime(2026, 11, 22, 7, 17, tzinfo=WIB)  # every test date is in the past


def test_rerun_same_range_keeps_row_counts(pipeline, fake_apis):
    first = load(pipeline, ALL, START, END, AFTER)
    second = load(pipeline, ALL, START, END, AFTER)

    assert first == second
    assert first["fx_rates"].rows == 5
    assert first["weather_daily"].rows == 5
    assert first["air_quality_hourly"].rows == 5 * 24
    assert all(s.duplicate_keys == 0 for s in second.values())
    assert fake_apis.calls == 6  # 3 APIs x 2 runs: data really was fetched twice


def test_changed_values_overwrite_existing_rows(pipeline, fake_apis):
    load(pipeline, ALL, START, END, AFTER)
    fake_apis.version = 2  # the source revises its values
    summary = load(pipeline, ALL, START, END, AFTER)

    assert summary["fx_rates"].rows == 5
    assert query(pipeline, "SELECT DISTINCT rate FROM fx_rates WHERE rate_date = '2026-11-20'") == [
        (18000 + 20 + 2,)
    ]
    assert query(pipeline, "SELECT DISTINCT pm2_5 FROM air_quality_hourly") == [(42.0,)]


def test_overlapping_ranges_do_not_duplicate(pipeline, fake_apis):
    load(pipeline, ALL, date(2026, 11, 16), date(2026, 11, 18), AFTER)
    summary = load(pipeline, ALL, date(2026, 11, 17), date(2026, 11, 20), AFTER)

    assert summary["fx_rates"].rows == 5  # 16..20, not 3 + 4 = 7
    assert summary["weather_daily"].rows == 5
    assert summary["air_quality_hourly"].rows == 5 * 24
    assert all(s.duplicate_keys == 0 for s in summary.values())


def test_forecast_rows_become_actuals_on_next_run(pipeline, fake_apis):
    morning = datetime(2026, 11, 20, 10, 30, tzinfo=WIB)
    load(pipeline, ["air", "weather"], START, END, morning)
    forecast_hours = query(pipeline, "SELECT count(*) FROM air_quality_hourly WHERE is_forecast")[
        0
    ][0]
    assert forecast_hours == 13  # 11:00..23:00 on 20 Nov

    summary = load(pipeline, ["air", "weather"], START, END, AFTER)
    assert summary["air_quality_hourly"].rows == 5 * 24
    assert query(pipeline, "SELECT count(*) FROM air_quality_hourly WHERE is_forecast") == [(0,)]
    assert query(pipeline, "SELECT count(*) FROM weather_daily WHERE is_forecast") == [(0,)]
