"""Buktikan user Looker Studio benar-benar read-only (Tahap 11).

    uv run python -m jds.check_reader

Membaca LOOKER_READER_URL dari .env (koneksi sebagai looker_reader, BUKAN pemilik).
Yang diharapkan:
- SELECT di schema marts berhasil,
- SELECT di schema raw ditolak,
- lapisan 1 (setting role): INSERT biasa ditolak karena transaksi read-only (SQLSTATE 25006),
- lapisan 2 (GRANT): INSERT/CREATE tetap ditolak walau transaksi DIPAKSA `read write`
  (SQLSTATE 42501). Setting sesi bisa dimatikan siapa saja; yang benar-benar mengunci
  adalah GRANT. Setiap cek di-rollback, jadi tidak ada perubahan yang tersisa.
Exit 0 jika semua sesuai harapan, 1 jika ada yang tidak sesuai, 2 jika konfigurasi salah.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import psycopg2

from jds.check_db import connect
from jds.config import ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging

log = logging.getLogger("jds.check_reader")

ENV_NAME = "LOOKER_READER_URL"


@dataclass(frozen=True)
class Check:
    name: str
    sql: str
    should_succeed: bool
    force_read_write: bool = False  # True = lewati lapisan 1, uji GRANT saja
    expect_code: str = ""  # SQLSTATE penolakan yang diharapkan (42501 = permission denied)


DENIED = "42501"  # insufficient_privilege
READ_ONLY = "25006"  # read_only_sql_transaction
INSERT_SQL = "insert into marts.dash_latest_summary (location_id) values ('__check__')"

CHECKS: tuple[Check, ...] = (
    Check("SELECT marts.dash_daily_signals", "select count(*) from marts.dash_daily_signals", True),
    Check(
        "SELECT marts.dash_latest_summary", "select count(*) from marts.dash_latest_summary", True
    ),
    Check("SELECT raw.fx_rates", "select count(*) from raw.fx_rates", False, expect_code=DENIED),
    Check(
        "SELECT staging.stg_fx_rates",
        "select count(*) from staging.stg_fx_rates",
        False,
        expect_code=DENIED,
    ),
    Check("INSERT marts (lapisan 1: read-only)", INSERT_SQL, False, expect_code=READ_ONLY),
    Check("INSERT marts (lapisan 2: GRANT)", INSERT_SQL, False, True, DENIED),
    Check(
        "CREATE TABLE marts (GRANT)", "create table marts.__check__ (id int)", False, True, DENIED
    ),
    Check(
        "CREATE TABLE public (GRANT)", "create table public.__check__ (id int)", False, True, DENIED
    ),
)


def run_check(conn, check: Check) -> tuple[bool, str]:
    """Jalankan satu cek; selalu rollback supaya tidak ada perubahan yang tersisa."""
    try:
        with conn.cursor() as cur:
            if check.force_read_write:
                cur.execute("set transaction read write")  # harus perintah pertama di transaksi
            cur.execute(check.sql)
            detail = f"berhasil ({cur.fetchone()[0]} baris)" if cur.description else "berhasil"
        succeeded = True
    except psycopg2.Error as exc:
        succeeded = False
        code = exc.pgcode or ""
        detail = f"ditolak: {code} {(exc.pgerror or '').strip().splitlines()[0]}"
    finally:
        conn.rollback()
    if succeeded or check.should_succeed:
        return succeeded == check.should_succeed, detail
    # Ditolak sesuai harapan, tapi harus oleh lapisan yang benar.
    return (not check.expect_code or code == check.expect_code), detail


def main() -> int:
    setup_logging()
    try:
        url = get_database_url(env_name=ENV_NAME)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    log.info("Koneksi sebagai: %s", mask_url(url))
    conn = connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("select current_user, current_setting('default_transaction_read_only')")
            user, read_only = cur.fetchone()
        conn.rollback()
        log.info("current_user=%s, default_transaction_read_only=%s", user, read_only)

        failures = 0
        for check in CHECKS:
            ok, detail = run_check(conn, check)
            expected = "boleh" if check.should_succeed else "harus ditolak"
            log.log(
                logging.INFO if ok else logging.ERROR,
                "%s %-42s (%s) -> %s",
                "OK  " if ok else "GAGAL",
                check.name,
                expected,
                detail,
            )
            failures += not ok
    finally:
        conn.close()

    if failures:
        log.error("%d cek tidak sesuai harapan: user ini BUKAN read-only yang aman.", failures)
        return 1
    log.info("Semua %d cek lulus: user hanya bisa membaca schema marts.", len(CHECKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
