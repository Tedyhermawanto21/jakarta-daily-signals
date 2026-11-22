"""FX rates from the Frankfurter API (ECB reference rates).

ECB business days only. USD/IDR is a cross rate via EUR, not Bank Indonesia's JISDOR.
A range starting on a holiday is moved back to the previous business day by the API.
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
    """{"base": "USD", "rates": {"2026-11-20": {"IDR": 18263}}} -> one row per date and quote."""
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
    """Daily base->quote rates for [start, end], inclusive."""
    url = f"{BASE_URL}/{start.isoformat()}..{end.isoformat()}"
    payload = get_json(url, params={"base": base, "symbols": ",".join(quotes)})
    rows = parse_timeseries(payload)
    log.info(
        "Frankfurter %s..%s (requested %s..%s): %d rows",
        payload.get("start_date"),
        payload.get("end_date"),
        start,
        end,
        len(rows),
    )
    yield from rows
