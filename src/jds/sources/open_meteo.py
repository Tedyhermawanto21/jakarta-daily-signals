"""Sumber cuaca & kualitas udara dari Open-Meteo (gratis, non-komersial, tanpa API key).

Catatan sumber:
- Semua request memakai timezone=Asia/Jakarta, jadi "time" yang dikembalikan adalah waktu
  lokal WIB TANPA offset (mis. "2026-11-20T13:00"). Offset ditempelkan di parser.
- Koordinat dibulatkan ke grid model, dan grid weather != grid air quality. Koordinat grid
  disimpan apa adanya (grid_latitude/grid_longitude) supaya transparan.
- Air quality adalah model CAMS (estimasi grid), bukan sensor stasiun.
- Tanggal/jam >= sekarang adalah PRAKIRAAN (is_forecast = true). Run berikutnya akan
  menimpanya dengan nilai terbaru lewat merge.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import dlt

from jds.config import TIMEZONE, Location
from jds.http import get_json

log = logging.getLogger(__name__)

# Historical Forecast API, BUKAN api.open-meteo.com/v1/forecast: endpoint forecast biasa hanya
# menyimpan ~75 hari ke belakang. Untuk tanggal lebih lama ia tetap HTTP 200 tapi nilainya null
# (ditemukan saat backfill Tahap 6). Historical API memberi nilai identik untuk tanggal yang
# tumpang tindih (diverifikasi 14..23 Nov 2026), grid sama, dan juga mencakup hari ini + prakiraan.
WEATHER_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

DAILY_WEATHER_VARS = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "rain_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "relative_humidity_2m_mean",
)
HOURLY_AIR_VARS = ("pm2_5", "pm10", "us_aqi")

_TZ = ZoneInfo(TIMEZONE)


def _columns_to_rows(block: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    """Open-Meteo mengirim data per kolom ({"time": [...], "x": [...]}); ubah jadi per baris."""
    keys = list(block)
    for values in zip(*(block[k] for k in keys), strict=True):
        yield dict(zip(keys, values, strict=True))


def _params(loc: Location, start: date, end: date) -> dict[str, Any]:
    return {
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "timezone": TIMEZONE,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def parse_weather_daily(
    payload: dict[str, Any], location_id: str, today: date
) -> list[dict[str, Any]]:
    """Respons daily -> 1 baris per (date_wib, location_id)."""
    rows = []
    for rec in _columns_to_rows(payload["daily"]):
        day = date.fromisoformat(rec.pop("time"))
        rows.append(
            {
                "date_wib": day,
                "location_id": location_id,
                "grid_latitude": payload.get("latitude"),
                "grid_longitude": payload.get("longitude"),
                **rec,
                "is_forecast": day >= today,
            }
        )
    return rows


def parse_air_quality_hourly(
    payload: dict[str, Any], location_id: str, now: datetime
) -> list[dict[str, Any]]:
    """Respons hourly -> 1 baris per (ts_wib, location_id). ts_wib = timestamptz (+07:00)."""
    rows = []
    for rec in _columns_to_rows(payload["hourly"]):
        ts = datetime.fromisoformat(rec.pop("time")).replace(tzinfo=_TZ)
        rows.append(
            {
                "ts_wib": ts,
                "date_wib": ts.date(),
                "hour_wib": ts.hour,
                "location_id": location_id,
                "grid_latitude": payload.get("latitude"),
                "grid_longitude": payload.get("longitude"),
                **rec,
                "is_forecast": ts > now,
            }
        )
    return rows


@dlt.resource(
    name="weather_daily",
    write_disposition="merge",
    primary_key=("date_wib", "location_id"),
    columns={
        "date_wib": {"data_type": "date", "nullable": False},
        "location_id": {"data_type": "text", "nullable": False},
        "weather_code": {"data_type": "bigint"},
        "is_forecast": {"data_type": "bool", "nullable": False},
    },
)
def weather_daily(
    start: date, end: date, locations: Iterable[Location], now: datetime
) -> Iterator[dict[str, Any]]:
    for loc in locations:
        params = {**_params(loc, start, end), "daily": ",".join(DAILY_WEATHER_VARS)}
        rows = parse_weather_daily(get_json(WEATHER_URL, params), loc.location_id, now.date())
        empty = sum(r.get("temperature_2m_max") is None for r in rows)
        log.info(
            "Open-Meteo weather %s %s..%s: %d hari (suhu kosong: %d)",
            loc.location_id,
            start,
            end,
            len(rows),
            empty,
        )
        if empty:
            log.warning("%d hari cuaca tanpa nilai suhu: cek rentang data API.", empty)
        yield from rows


@dlt.resource(
    name="air_quality_hourly",
    write_disposition="merge",
    primary_key=("ts_wib", "location_id"),
    columns={
        "ts_wib": {"data_type": "timestamp", "nullable": False, "timezone": True},
        "date_wib": {"data_type": "date", "nullable": False},
        "hour_wib": {"data_type": "bigint", "nullable": False},
        "location_id": {"data_type": "text", "nullable": False},
        "pm2_5": {"data_type": "double"},
        "pm10": {"data_type": "double"},
        "us_aqi": {"data_type": "double"},
        "is_forecast": {"data_type": "bool", "nullable": False},
    },
)
def air_quality_hourly(
    start: date, end: date, locations: Iterable[Location], now: datetime
) -> Iterator[dict[str, Any]]:
    for loc in locations:
        params = {**_params(loc, start, end), "hourly": ",".join(HOURLY_AIR_VARS)}
        rows = parse_air_quality_hourly(get_json(AIR_QUALITY_URL, params), loc.location_id, now)
        nulls = sum(r["pm2_5"] is None for r in rows)
        log.info(
            "Open-Meteo air %s %s..%s: %d jam (pm2_5 kosong: %d)",
            loc.location_id,
            start,
            end,
            len(rows),
            nulls,
        )
        yield from rows
