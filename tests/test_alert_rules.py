from datetime import date

from jds.alerts.rules import Anomaly, build_message, fmt_date, fmt_num, fmt_pct, new_anomalies

YESTERDAY = {
    "date_wib": date(2026, 11, 17),
    "usd_idr_rate": 18271.0,
    "fx_rate_date": date(2026, 11, 17),
    "fx_prev_rate_date": date(2026, 11, 16),
    "fx_pct_change": 0.07,
    "temp_min_c": 25.2,
    "temp_max_c": 33.0,
    "precipitation_mm": 2.7,
    "aq_is_complete": True,
    "aq_hours_actual": 24,
    "pm25_avg": 79.0,
    "pm25_peak_hour": 23,
    "pm25_category_ispu": "Tidak Sehat",
}
# The 18 Nov rate exists (published 22:00 WIB) but must not appear in the morning report.
TODAY = {
    "date_wib": date(2026, 11, 18),
    "usd_idr_rate": 99999.0,
    "fx_rate_date": date(2026, 11, 18),
    "fx_prev_rate_date": date(2026, 11, 17),
    "fx_pct_change": 9.99,
    "temp_min_c": 24.6,
    "temp_max_c": 32.4,
    "precipitation_mm": 8.2,
}
PM = Anomaly(date(2026, 11, 17), "pm25_high", "jkt_monas", "PM2.5 rata-rata 79.0 µg/m³")


def test_indonesian_number_and_date_format():
    assert fmt_num(18263, 0) == "18.263"
    assert fmt_num(15.55) == "15,6"
    assert fmt_pct(0.07) == "+0,07%"
    assert fmt_pct(-1.63) == "-1,63%"
    assert fmt_date(date(2026, 11, 22)) == "Minggu, 22 Nov 2026"


def test_new_anomalies_drops_already_sent():
    fx = Anomaly(date(2026, 11, 17), "fx_move", "all", "USD/IDR ...")
    assert new_anomalies([PM, fx], already_sent={PM.key}) == [fx]


def test_message_with_anomaly_has_warning_on_top():
    text = build_message(date(2026, 11, 18), YESTERDAY, TODAY, [PM])
    lines = text.splitlines()
    assert lines[0] == "⚠️ Udara tidak sehat: PM2.5 rata-rata 79.0 µg/m³"
    assert "Jakarta Daily Signals · Rabu, 18 Nov 2026" in text
    assert "💱 USD/IDR 18.271 (+0,07% vs 16 Nov), kurs ECB 17 Nov" in text
    assert "99.999" not in text
    assert "🌡 Kemarin (Selasa 17 Nov): 25–33°C, hujan 2,7 mm" in text
    assert "🌫 PM2.5 kemarin: 79,0 µg/m³ (Tidak Sehat), puncak jam 23:00 WIB" in text
    assert "📅 Hari ini (prakiraan): 25–32°C, hujan 8,2 mm" in text


def test_message_without_anomaly_and_incomplete_air_and_missing_today():
    partial = {**YESTERDAY, "aq_is_complete": False, "aq_hours_actual": 20, "usd_idr_rate": None}
    text = build_message(date(2026, 11, 18), partial, None, [])
    assert text.startswith("✅ Tidak ada anomali baru.")
    assert "⚠️" not in text
    assert "data belum lengkap (20/24 jam)" in text
    assert "USD/IDR: data kurs belum tersedia" in text
    assert "📅 Hari ini (prakiraan): data cuaca belum tersedia" in text
