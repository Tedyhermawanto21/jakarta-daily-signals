"""Sumber kurs dari Frankfurter API (data referensi ECB).

Catatan sumber:
- Hanya hari kerja ECB (tidak ada akhir pekan / libur ECB).
- Kurs USD/IDR adalah kurs silang via EUR, bukan JISDOR Bank Indonesia.
- Rentang yang dimulai di hari libur otomatis mundur ke hari kerja sebelumnya.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

import dlt

from jds.http import get_json

log = logging.getLogger(__name__)

BASE_URL = "https://api.frankfurter.dev/v1"
SOURCE_NAME = "frankfurter/ecb"


def parse_timeseries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Ubah respons time series Frankfurter menjadi baris datar.

    Input : {"base": "USD", "rates": {"2026-11-20": {"IDR": 18263}, ...}}
    Output: [{"rate_date": date(2026,11,20), "base": "USD", "quote": "IDR",
              "rate": 18263.0, "source": "frankfurter/ecb"}, ...]
    """
    base = payload["base"]
    rows = [
        {
            "rate_date": date.fromisoformat(day),
            "base": base,
            "quote": quote,
            "rate": float(value),
            "source": SOURCE_NAME,
        }
        for day, quotes in payload.get("rates", {}).items()
        for quote, value in quotes.items()
    ]
    return sorted(rows, key=lambda r: (r["rate_date"], r["quote"]))


@dlt.resource(
    name="fx_rates",
    write_disposition="merge",
    primary_key=("rate_date", "base", "quote"),
    columns={
        "rate_date": {"data_type": "date", "nullable": False},
        "base": {"data_type": "text", "nullable": False},
        "quote": {"data_type": "text", "nullable": False},
        "rate": {"data_type": "double", "nullable": False},
    },
)
def fx_rates(
    start: date, end: date, base: str = "USD", quotes: tuple[str, ...] = ("IDR",)
) -> Iterator[dict[str, Any]]:
    """Kurs harian base->quotes untuk rentang [start, end] (inklusif)."""
    url = f"{BASE_URL}/{start.isoformat()}..{end.isoformat()}"
    payload = get_json(url, params={"base": base, "symbols": ",".join(quotes)})
    rows = parse_timeseries(payload)
    log.info(
        "Frankfurter %s..%s (diminta %s..%s): %d baris",
        payload.get("start_date"),
        payload.get("end_date"),
        start,
        end,
        len(rows),
    )
    yield from rows
