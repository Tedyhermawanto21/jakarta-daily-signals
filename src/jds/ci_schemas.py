"""Temporary per-PR schemas for CI.

    DBT_SCHEMA_PREFIX=ci_pr_12 uv run python -m jds.ci_schemas list
    DBT_SCHEMA_PREFIX=ci_pr_12 uv run python -m jds.ci_schemas drop

The prefix must match ci_pr_<digits>; anything else is rejected before connecting,
so this script can never drop a real schema such as marts or raw.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys

from psycopg2 import sql

from jds.check_db import connect
from jds.config import ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging

log = logging.getLogger("jds.ci_schemas")

PREFIX_ENV = "DBT_SCHEMA_PREFIX"
PREFIX_RE = re.compile(r"ci_pr_[0-9]{1,9}")


def validate_prefix(prefix: str) -> str:
    if not PREFIX_RE.fullmatch(prefix):
        raise ConfigError(
            f"{PREFIX_ENV}={prefix!r} is invalid: expected ci_pr_<PR number>, e.g. ci_pr_12."
        )
    return prefix


def list_schemas(conn, prefix: str) -> list[str]:
    validate_prefix(prefix)
    with conn.cursor() as cur:
        cur.execute(
            "select schema_name from information_schema.schemata"
            " where starts_with(schema_name, %s) order by schema_name",
            (prefix + "_",),
        )
        return [row[0] for row in cur.fetchall()]


def drop_schemas(conn, prefix: str) -> list[str]:
    """Drop every <prefix>_* schema. Idempotent."""
    schemas = list_schemas(conn, prefix)
    with conn.cursor() as cur:
        for name in schemas:
            cur.execute(sql.SQL("drop schema if exists {} cascade").format(sql.Identifier(name)))
    conn.commit()
    return schemas


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["list", "drop"])
    parser.add_argument("--prefix", default=None, help=f"default: env {PREFIX_ENV}")
    args = parser.parse_args(argv)

    try:
        prefix = validate_prefix(args.prefix or os.environ.get(PREFIX_ENV, ""))
        url = get_database_url()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    log.info("Database: %s", mask_url(url))
    conn = connect(url)
    try:
        if args.action == "list":
            schemas = list_schemas(conn, prefix)
            log.info("Schemas %s_*: %s", prefix, ", ".join(schemas) or "(none)")
        else:
            schemas = drop_schemas(conn, prefix)
            log.info("Dropped %d schemas: %s", len(schemas), ", ".join(schemas) or "(none)")
    except Exception:
        log.exception("Failed to %s schemas %s_*", args.action, prefix)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
