from datetime import date

import pytest

from jds.pipeline import resolve_range
from jds.sources.frankfurter import parse_timeseries

# Contoh respons nyata (dipangkas) dari /v1/2026-11-14..2026-11-21?base=USD&symbols=IDR
PAYLOAD = {
    "amount": 1.0,
    "base": "USD",
    "start_date": "2026-11-13",
    "end_date": "2026-11-20",
    "rates": {"2026-11-20": {"IDR": 18263}, "2026-11-13": {"IDR": 18245}},
}


def test_parse_timeseries_flat_and_sorted():
    rows = parse_timeseries(PAYLOAD)
    assert [r["rate_date"] for r in rows] == [date(2026, 11, 13), date(2026, 11, 20)]
    assert rows[-1] == {
        "rate_date": date(2026, 11, 20),
        "base": "USD",
        "quote": "IDR",
        "rate": 18263.0,
        "source": "frankfurter/ecb",
    }


def test_parse_timeseries_empty_rates():
    assert parse_timeseries({"base": "USD", "rates": {}}) == []


def test_resolve_range_default_is_7_days_back():
    today = date(2026, 11, 21)
    assert resolve_range(None, None, today) == (date(2026, 11, 14), today)


def test_resolve_range_rejects_future():
    with pytest.raises(ValueError, match="masa depan"):
        resolve_range(None, date(2026, 11, 22), date(2026, 11, 21))


def test_resolve_range_rejects_inverted():
    with pytest.raises(ValueError, match="setelah"):
        resolve_range(date(2026, 11, 20), date(2026, 11, 10), date(2026, 11, 21))
