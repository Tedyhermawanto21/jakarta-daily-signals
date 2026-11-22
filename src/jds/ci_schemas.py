"""Schema sementara per PR untuk CI (Tahap 10).

    DBT_SCHEMA_PREFIX=ci_pr_12 uv run python -m jds.ci_schemas list
    DBT_SCHEMA_PREFIX=ci_pr_12 uv run python -m jds.ci_schemas drop

dbt menulis model ke `<prefix>_staging` / `<prefix>_marts` (lihat macro generate_schema_name).
Setelah CI selesai, `drop` menghapus semua schema berawalan `<prefix>_`.

Pengaman: prefix WAJIB berbentuk `ci_pr_<angka>`. Nama lain (mis. "marts", "raw", "")
ditolak sebelum ada koneksi ke database, jadi skrip ini tidak bisa menghapus schema asli.
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
            f"{PREFIX_ENV}={prefix!r} tidak valid: harus berbentuk ci_pr_<nomor PR>, mis. ci_pr_12."
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
    """Hapus semua schema `<prefix>_*`. Idempoten: tidak ada schema = tidak ada yang dihapus."""
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
            log.info("Schema %s_*: %s", prefix, ", ".join(schemas) or "(tidak ada)")
        else:
            schemas = drop_schemas(conn, prefix)
            log.info("Dihapus %d schema: %s", len(schemas), ", ".join(schemas) or "(tidak ada)")
    except Exception:
        log.exception("Gagal %s schema %s_*", args.action, prefix)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
