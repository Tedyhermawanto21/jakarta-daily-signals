"""Prove that the Looker Studio user is read-only.

    uv run python -m jds.check_reader

Connects with LOOKER_READER_URL. SELECT on marts must work; raw and staging must be denied.
Writes must be denied twice: by the read-only setting (SQLSTATE 25006) and, with the
transaction forced to READ WRITE, by the grants themselves (42501). Every check is rolled back.
Exit code 0 = all as expected, 1 = something is not, 2 = configuration error.
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
    force_read_write: bool = False
    expect_code: str = ""


DENIED = "42501"
READ_ONLY = "25006"
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
    Check("INSERT marts (layer 1: read-only)", INSERT_SQL, False, expect_code=READ_ONLY),
    Check("INSERT marts (layer 2: grants)", INSERT_SQL, False, True, DENIED),
    Check(
        "CREATE TABLE marts (grants)", "create table marts.__check__ (id int)", False, True, DENIED
    ),
    Check(
        "CREATE TABLE public (grants)",
        "create table public.__check__ (id int)",
        False,
        True,
        DENIED,
    ),
)


def run_check(conn, check: Check) -> tuple[bool, str]:
    """Run one check and always roll back."""
    try:
        with conn.cursor() as cur:
            if check.force_read_write:
                cur.execute("set transaction read write")  # must be the first statement
            cur.execute(check.sql)
            detail = f"succeeded ({cur.fetchone()[0]} rows)" if cur.description else "succeeded"
        succeeded = True
    except psycopg2.Error as exc:
        succeeded = False
        code = exc.pgcode or ""
        detail = f"denied: {code} {(exc.pgerror or '').strip().splitlines()[0]}"
    finally:
        conn.rollback()
    if succeeded or check.should_succeed:
        return succeeded == check.should_succeed, detail
    # Denied as expected, but it must be denied by the right layer.
    return (not check.expect_code or code == check.expect_code), detail


def main() -> int:
    setup_logging()
    try:
        url = get_database_url(env_name=ENV_NAME)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    log.info("Connecting as: %s", mask_url(url))
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
            expected = "allowed" if check.should_succeed else "must be denied"
            log.log(
                logging.INFO if ok else logging.ERROR,
                "%s %-40s (%s) -> %s",
                "OK  " if ok else "FAIL",
                check.name,
                expected,
                detail,
            )
            failures += not ok
    finally:
        conn.close()

    if failures:
        log.error("%d checks did not match: this user is NOT safely read-only.", failures)
        return 1
    log.info("All %d checks passed: the user can only read the marts schema.", len(CHECKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
