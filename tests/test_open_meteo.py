from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from jds.sources.open_meteo import parse_air_quality_hourly, parse_weather_daily

WIB = ZoneInfo("Asia/Jakarta")

# Trimmed real Open-Meteo responses
WEATHER = {
    "latitude": -6.151142,
    "longitude": 106.8421,
    "daily": {
        "time": ["2026-11-20", "2026-11-21"],
        "temperature_2m_max": [31.9, 31.5],
        "precipitation_sum": [15.5, 5.8],
    },
}
AIR = {
    "latitude": -6.199997,
    "longitude": 106.80002,
    "hourly": {
        "time": [f"2026-11-20T{h:02d}:00" for h in range(24)],
        "pm2_5": [float(h) for h in range(23)] + [None],
        "pm10": [1.0] * 24,
    },
}


def test_weather_one_row_per_day_with_forecast_flag():
    rows = parse_weather_daily(WEATHER, "jkt_monas", today=date(2026, 11, 21))
    assert [r["date_wib"] for r in rows] == [date(2026, 11, 20), date(2026, 11, 21)]
    assert rows[0]["is_forecast"] is False
    assert rows[1]["is_forecast"] is True
    assert rows[0]["temperature_2m_max"] == 31.9
    assert rows[0]["location_id"] == "jkt_monas"
    assert rows[0]["grid_latitude"] == -6.151142
    assert "time" not in rows[0]


def test_air_quality_24_rows_timezone_aware_wib():
    now = datetime(2026, 11, 20, 12, 30, tzinfo=WIB)
    rows = parse_air_quality_hourly(AIR, "jkt_monas", now=now)
    assert len(rows) == 24
    first = rows[0]
    assert first["ts_wib"] == datetime(2026, 11, 20, 0, 0, tzinfo=WIB)
    assert first["ts_wib"].utcoffset().total_seconds() == 7 * 3600
    assert (first["date_wib"], first["hour_wib"]) == (date(2026, 11, 20), 0)
    # 00:00 WIB is 17:00 UTC on 19 Nov; the WIB date must stay 20 Nov.
    assert first["ts_wib"].astimezone(ZoneInfo("UTC")).date() == date(2026, 11, 19)


def test_air_quality_forecast_flag_and_null_kept():
    now = datetime(2026, 11, 20, 12, 30, tzinfo=WIB)
    rows = parse_air_quality_hourly(AIR, "jkt_monas", now=now)
    assert rows[12]["is_forecast"] is False
    assert rows[13]["is_forecast"] is True
    assert rows[23]["pm2_5"] is None  # kept here, tested in dbt


def test_mismatched_column_lengths_fail_loudly():
    bad = {"hourly": {"time": ["2026-11-20T00:00"], "pm2_5": []}}
    with pytest.raises(ValueError):
        parse_air_quality_hourly(bad, "x", now=datetime(2026, 11, 20, tzinfo=WIB))
