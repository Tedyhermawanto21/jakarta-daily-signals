"""Run dbt with credentials taken from DATABASE_URL, the single credential source.

    uv run python -m jds.run_dbt build
    uv run python -m jds.run_dbt source freshness
    uv run python -m jds.run_dbt test --select stg_fx_rates

Splits DATABASE_URL into the DBT_PG_* variables read by transform/profiles.yml, wakes Neon,
then runs dbtRunner. With DBT_SCHEMA_PREFIX=ci_pr_<n>, models go to ci_pr_<n>_* schemas.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from jds.check_db import connect
from jds.ci_schemas import PREFIX_ENV, validate_prefix
from jds.config import ConfigError, get_database_url, mask_url
from jds.logging_setup import setup_logging

log = logging.getLogger("jds.run_dbt")

DBT_DIR = Path(__file__).resolve().parents[2] / "transform"


def dbt_env_from_url(url: str) -> dict[str, str]:
    """postgresql://user:pass@host:port/db?sslmode=require -> DBT_PG_* variables."""
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    return {
        "DBT_PG_HOST": parts.hostname or "",
        "DBT_PG_PORT": str(parts.port or 5432),
        "DBT_PG_USER": unquote(parts.username or ""),
        "DBT_PG_PASSWORD": unquote(parts.password or ""),
        "DBT_PG_DBNAME": parts.path.lstrip("/"),
        "DBT_PG_SSLMODE": query.get("sslmode", ["require"])[0],
    }


def with_dirs(args: list[str]) -> list[str]:
    extra = []
    if "--project-dir" not in args:
        extra += ["--project-dir", str(DBT_DIR)]
    if "--profiles-dir" not in args:
        extra += ["--profiles-dir", str(DBT_DIR)]
    return args + extra


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        log.error("Pass a dbt command, e.g. python -m jds.run_dbt build")
        return 2

    try:
        prefix = os.environ.get(PREFIX_ENV, "").strip()
        if prefix:
            validate_prefix(prefix)
        url = get_database_url()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    os.environ.update(dbt_env_from_url(url))
    log.info("dbt -> %s", mask_url(url))
    if prefix:
        log.info("CI schemas: %s_staging, %s_marts (raw source unchanged)", prefix, prefix)
    connect(url).close()

    from dbt.cli.main import dbtRunner

    result = dbtRunner().invoke(with_dirs(args))
    if result.exception is not None:
        log.error("dbt error: %s", result.exception)
        return 2
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
