"""Jalankan dbt dengan kredensial dari DATABASE_URL (satu sumber kredensial).

    uv run python -m jds.run_dbt build
    uv run python -m jds.run_dbt source freshness
    uv run python -m jds.run_dbt test --select stg_fx_rates

dbt tidak membaca .env dan tidak bisa mem-parse URL Postgres. Wrapper ini:
1. memuat .env (lokal) / memakai env yang sudah ada (CI),
2. memecah DATABASE_URL menjadi env DBT_PG_* yang dibaca transform/profiles.yml,
3. membangunkan Neon (retry cold start),
4. menjalankan dbt lewat API programatik dbtRunner dengan --project-dir/--profiles-dir transform.

CI: env DBT_SCHEMA_PREFIX=ci_pr_<n> membuat dbt menulis ke ci_pr_<n>_staging/_marts
(divalidasi di sini; dibersihkan dengan `python -m jds.ci_schemas drop`).
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
    """postgresql://user:pass@host:port/db?sslmode=require -> env DBT_PG_*."""
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
        log.error("Berikan perintah dbt, mis.: python -m jds.run_dbt build")
        return 2

    try:
        prefix = os.environ.get(PREFIX_ENV, "").strip()
        if prefix:
            validate_prefix(prefix)  # cegah nama schema aneh sebelum dbt menulis apa pun
        url = get_database_url()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    os.environ.update(dbt_env_from_url(url))
    log.info("dbt -> %s", mask_url(url))
    if prefix:
        log.info("Schema CI: %s_staging, %s_marts (source raw tetap)", prefix, prefix)
    connect(url).close()  # bangunkan Neon sebelum dbt membuka banyak koneksi

    from dbt.cli.main import dbtRunner  # import lambat: dbt berat untuk diimpor

    result = dbtRunner().invoke(with_dirs(args))
    if result.exception is not None:
        log.error("dbt error: %s", result.exception)
        return 2
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
