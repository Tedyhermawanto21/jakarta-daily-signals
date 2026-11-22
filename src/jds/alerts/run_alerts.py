"""Send the daily summary to Telegram, at most once per report date.

    uv run python -m jds.alerts.run_alerts --dry-run            # print, do not send
    uv run python -m jds.alerts.run_alerts                      # send (once per day)
    uv run python -m jds.alerts.run_alerts --date 2026-11-18    # a specific report date

At-most-once via ops.alert_log: reserve a 'sending' row (the primary key blocks concurrent
runs), send, then mark it 'sent'. A failed send releases the reservation. A row left in
'sending' (process died after sending) is never resent automatically; the run exits 1 instead.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta
from typing import Protocol

from psycopg2.extras import RealDictCursor

from jds.alerts.rules import Anomaly, Row, build_message, new_anomalies
from jds.alerts.telegram import get_credentials, send_message
from jds.check_db import connect
from jds.config import LOCATIONS, ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging
from jds.pipeline import today_wib

log = logging.getLogger("jds.alerts")

SUMMARY_TYPE = "daily_summary"
ALL = "all"

DDL = """
CREATE TABLE IF NOT EXISTS ops.alert_log (
    signal_date         date        NOT NULL,
    alert_type          text        NOT NULL,
    location_id         text        NOT NULL,
    status              text        NOT NULL CHECK (status IN ('sending', 'sent')),
    detail              text,
    telegram_message_id bigint,
    created_at          timestamptz NOT NULL DEFAULT now(),
    sent_at             timestamptz,
    PRIMARY KEY (signal_date, alert_type, location_id)
)
"""


class AlertStore(Protocol):
    def summary_status(self, report_date: date) -> str | None: ...
    def load_signals(self, report_date: date) -> tuple[Row | None, Row | None]: ...
    def load_candidates(self, yesterday: date, fx_date: date | None) -> list[Anomaly]: ...
    def sent_keys(self, candidates: list[Anomaly]) -> set[tuple[date, str, str]]: ...
    def reserve_summary(self, report_date: date) -> bool: ...
    def release_summary(self, report_date: date) -> None: ...
    def mark_sent(
        self, report_date: date, anomalies: list[Anomaly], message_id: int, text: str
    ) -> None: ...


class PgAlertStore:
    """Postgres implementation. Every write commits on its own."""

    def __init__(self, conn, location_id: str):
        self.conn = conn
        self.location_id = location_id
        with conn, conn.cursor() as cur:
            cur.execute(DDL)

    def _fetch(self, sql: str, params: dict) -> list[dict]:
        with self.conn, self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def summary_status(self, report_date: date) -> str | None:
        rows = self._fetch(
            "SELECT status FROM ops.alert_log WHERE signal_date = %(d)s "
            "AND alert_type = %(t)s AND location_id = %(l)s",
            {"d": report_date, "t": SUMMARY_TYPE, "l": ALL},
        )
        return rows[0]["status"] if rows else None

    def load_signals(self, report_date: date) -> tuple[Row | None, Row | None]:
        rows = self._fetch(
            "SELECT * FROM marts.fct_daily_signals WHERE location_id = %(l)s "
            "AND date_wib IN (%(y)s, %(t)s)",
            {"l": self.location_id, "y": report_date - timedelta(days=1), "t": report_date},
        )
        by_date = {r["date_wib"]: r for r in rows}
        return by_date.get(report_date - timedelta(days=1)), by_date.get(report_date)

    def load_candidates(self, yesterday: date, fx_date: date | None) -> list[Anomaly]:
        rows = self._fetch(
            "SELECT signal_date, alert_type, location_id, detail FROM marts.fct_anomalies "
            "WHERE (alert_type = 'pm25_high' AND signal_date = %(y)s AND location_id = %(l)s) "
            "   OR (alert_type = 'fx_move' AND signal_date = %(fx)s) "
            "ORDER BY alert_type",
            {"y": yesterday, "fx": fx_date, "l": self.location_id},
        )
        return [Anomaly(**r) for r in rows]

    def sent_keys(self, candidates: list[Anomaly]) -> set[tuple[date, str, str]]:
        if not candidates:
            return set()
        rows = self._fetch(
            "SELECT signal_date, alert_type, location_id FROM ops.alert_log "
            "WHERE status = 'sent' AND (signal_date, alert_type, location_id) "
            "IN (SELECT * FROM unnest(%(d)s::date[], %(t)s::text[], %(l)s::text[]))",
            {
                "d": [a.signal_date for a in candidates],
                "t": [a.alert_type for a in candidates],
                "l": [a.location_id for a in candidates],
            },
        )
        return {(r["signal_date"], r["alert_type"], r["location_id"]) for r in rows}

    def reserve_summary(self, report_date: date) -> bool:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ops.alert_log (signal_date, alert_type, location_id, status) "
                "VALUES (%s, %s, %s, 'sending') ON CONFLICT DO NOTHING",
                (report_date, SUMMARY_TYPE, ALL),
            )
            return cur.rowcount == 1

    def release_summary(self, report_date: date) -> None:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM ops.alert_log WHERE signal_date = %s AND alert_type = %s "
                "AND location_id = %s AND status = 'sending'",
                (report_date, SUMMARY_TYPE, ALL),
            )

    def mark_sent(
        self, report_date: date, anomalies: list[Anomaly], message_id: int, text: str
    ) -> None:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "UPDATE ops.alert_log SET status = 'sent', sent_at = now(), "
                "telegram_message_id = %s, detail = %s "
                "WHERE signal_date = %s AND alert_type = %s AND location_id = %s",
                (message_id, text, report_date, SUMMARY_TYPE, ALL),
            )
            for a in anomalies:
                cur.execute(
                    "INSERT INTO ops.alert_log (signal_date, alert_type, location_id, status, "
                    "detail, telegram_message_id, sent_at) "
                    "VALUES (%s, %s, %s, 'sent', %s, %s, now()) ON CONFLICT DO NOTHING",
                    (a.signal_date, a.alert_type, a.location_id, a.detail, message_id),
                )


def run(
    report_date: date,
    store: AlertStore,
    sender: Callable[[str], int] | None,
    dry_run: bool,
) -> int:
    yesterday, today = store.load_signals(report_date)
    if yesterday is None and today is None:
        log.error(
            "No rows in marts.fct_daily_signals for %s. Run the pipeline and dbt first.",
            report_date,
        )
        return 1

    fx_date = (yesterday or {}).get("fx_rate_date")
    candidates = store.load_candidates(report_date - timedelta(days=1), fx_date)
    anomalies = new_anomalies(candidates, store.sent_keys(candidates))
    text = build_message(report_date, yesterday, today, anomalies)
    log.info("Anomalies: %d candidates, %d not reported before", len(candidates), len(anomalies))

    if dry_run:
        log.info("DRY RUN: message NOT sent, alert_log NOT changed.\n%s", text)
        return 0

    status = store.summary_status(report_date)
    if status == "sent":
        log.info("Summary for %s already sent, skipping.", report_date)
        return 0
    if status == "sending":
        log.error(
            "Summary for %s is stuck in 'sending' from an interrupted run and is not resent "
            "(it may have been delivered). Check Telegram; if it is missing, delete that row "
            "from ops.alert_log and run again.",
            report_date,
        )
        return 1
    if not store.reserve_summary(report_date):
        log.info("Summary for %s is being sent by another run, skipping.", report_date)
        return 0

    assert sender is not None
    try:
        message_id = sender(text)
    except Exception:
        store.release_summary(report_date)
        log.error("Send failed; reservation released so the next run retries.")
        raise
    store.mark_sent(report_date, anomalies, message_id, text)
    log.info("Sent to Telegram (message_id=%s), %d anomalies logged.", message_id, len(anomalies))
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Daily summary -> Telegram")
    parser.add_argument("--dry-run", action="store_true", help="print the message, do not send")
    parser.add_argument(
        "--date", type=date.fromisoformat, help="report date (default: today in WIB)"
    )
    args = parser.parse_args(argv)
    report_date = args.date or today_wib()

    try:
        url = get_database_url()
        sender = None
        if not args.dry_run:
            token, chat_id = get_credentials()
            sender = lambda text: send_message(token, chat_id, text)  # noqa: E731
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    log.info("Report %s -> %s", report_date, mask_url(url))
    conn = connect(url)
    try:
        store = PgAlertStore(conn, LOCATIONS[0].location_id)
        return run(report_date, store, sender, args.dry_run)
    except Exception as exc:
        log.error("Alert failed: %s", exc)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
