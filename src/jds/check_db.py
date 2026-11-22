"""Check the Neon Postgres connection and the project schemas.

uv run python -m jds.check_db           # check only
uv run python -m jds.check_db --init    # create missing schemas, then check
"""

from __future__ import annotations

import argparse
import logging
import sys

import psycopg2
from psycopg2 import sql
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from jds.config import SCHEMAS, ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging

log = logging.getLogger("jds.check_db")

_PERMANENT_ERRORS = ("password authentication failed", "does not exist", "invalid dsn")


def _is_transient(exc: BaseException) -> bool:
    """Retry only temporary errors, e.g. a Neon compute waking up from a cold start."""
    if not isinstance(exc, psycopg2.OperationalError):
        return False
    msg = str(exc).lower()
    return not any(p in msg for p in _PERMANENT_ERRORS)


@retry(
    retry=retry_if_exception(_is_transient),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def connect(url: str):
    return psycopg2.connect(url, connect_timeout=15, application_name="jds-check-db")


def run(init: bool) -> int:
    try:
        url = get_database_url()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    log.info("Connecting to %s", mask_url(url))
    try:
        conn = connect(url)
    except psycopg2.OperationalError as exc:
        log.error("Connection failed: %s", str(exc).strip())
        return 1

    try:
        with conn, conn.cursor() as cur:
            if init:
                for schema in SCHEMAS:
                    cur.execute(
                        sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                    )
                log.info("--init: CREATE SCHEMA IF NOT EXISTS for %s", ", ".join(SCHEMAS))

            cur.execute("SELECT version(), current_database(), current_user")
            version, database, user = cur.fetchone()
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name = ANY(%s) ORDER BY schema_name",
                (list(SCHEMAS),),
            )
            found = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    log.info("Postgres : %s", version.split(",")[0])
    log.info("Database : %s (user: %s)", database, user)
    log.info("Schemas  : %s", ", ".join(found) or "(none)")

    missing = sorted(set(SCHEMAS) - set(found))
    if missing:
        log.error("Missing schemas: %s. Run again with --init.", ", ".join(missing))
        return 1
    log.info("OK: connected and all %d schemas exist.", len(SCHEMAS))
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--init", action="store_true", help="create missing schemas")
    args = parser.parse_args(argv)
    return run(init=args.init)


if __name__ == "__main__":
    sys.exit(main())
