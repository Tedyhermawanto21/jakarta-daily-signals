"""Daily summary and anomaly rules, without I/O.

One summary message per morning, with a ⚠️ line per new anomaly. Message text is Indonesian
because it is read by Jakarta residents; anomaly details come from marts.fct_anomalies.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
ANOMALY_TITLE = {"pm25_high": "Udara tidak sehat", "fx_move": "Kurs bergerak tajam"}
SOURCE_NOTE = "Sumber: Frankfurter/ECB · Open-Meteo (model CAMS)"

Row = Mapping[str, Any]


@dataclass(frozen=True)
class Anomaly:
    signal_date: date
    alert_type: str
    location_id: str
    detail: str

    @property
    def key(self) -> tuple[date, str, str]:
        return (self.signal_date, self.alert_type, self.location_id)


def fmt_num(value: float, decimals: int = 1) -> str:
    """Indonesian number format: 18263.5 -> '18.263,5'."""
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{fmt_num(value, 2)}%"


def fmt_date(d: date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"


def fmt_short(d: date) -> str:
    return f"{d.day} {BULAN[d.month - 1]}"


def new_anomalies(
    candidates: Iterable[Anomaly], already_sent: set[tuple[date, str, str]]
) -> list[Anomaly]:
    """Drop anomalies that were already reported (by date, type and location)."""
    return [a for a in candidates if a.key not in already_sent]


def _fx_line(today: Row | None) -> str:
    if not today or today.get("usd_idr_rate") is None:
        return "💱 USD/IDR: data kurs belum tersedia"
    line = f"💱 USD/IDR {fmt_num(today['usd_idr_rate'], 0)}"
    if today.get("fx_pct_change") is not None and today.get("fx_prev_rate_date"):
        line += f" ({fmt_pct(today['fx_pct_change'])} vs {fmt_short(today['fx_prev_rate_date'])})"
    return line + f", kurs ECB {fmt_short(today['fx_rate_date'])}"


def _weather_line(label: str, row: Row | None) -> str:
    if not row or row.get("temp_max_c") is None:
        return f"{label}: data cuaca belum tersedia"
    return (
        f"{label}: {fmt_num(row['temp_min_c'], 0)}–{fmt_num(row['temp_max_c'], 0)}°C, "
        f"hujan {fmt_num(row['precipitation_mm'])} mm"
    )


def _air_line(yesterday: Row | None) -> str:
    if not yesterday or not yesterday.get("aq_is_complete"):
        hours = (yesterday or {}).get("aq_hours_actual", 0)
        return f"🌫 PM2.5 kemarin: data belum lengkap ({hours}/24 jam)"
    return (
        f"🌫 PM2.5 kemarin: {fmt_num(yesterday['pm25_avg'])} µg/m³ "
        f"({yesterday['pm25_category_ispu']}), puncak jam {yesterday['pm25_peak_hour']:02d}:00 WIB"
    )


def build_message(
    report_date: date, yesterday: Row | None, today: Row | None, anomalies: list[Anomaly]
) -> str:
    """Plain-text daily summary (no parse_mode)."""
    if anomalies:
        header = [
            f"⚠️ {ANOMALY_TITLE.get(a.alert_type, a.alert_type)}: {a.detail}" for a in anomalies
        ]
    else:
        header = ["✅ Tidak ada anomali baru."]

    y_label = "🌡 Kemarin"
    if yesterday:
        y_date = yesterday["date_wib"]
        y_label += f" ({HARI[y_date.weekday()]} {fmt_short(y_date)})"

    body = [
        f"Jakarta Daily Signals · {fmt_date(report_date)}",
        # As-of yesterday: the ECB publishes today's rate around 22:00 WIB.
        _fx_line(yesterday),
        _weather_line(y_label, yesterday),
        _air_line(yesterday),
        _weather_line("📅 Hari ini (prakiraan)", today),
    ]
    return "\n".join([*header, "", *body, "", SOURCE_NOTE])
