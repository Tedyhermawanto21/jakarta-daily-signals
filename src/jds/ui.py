"""Buka DuckDB UI (open source, ekstensi resmi DuckDB) untuk database lokal.

    uv run python -m jds.ui          # lalu buka http://localhost:4213
    Ctrl+C untuk berhenti.

Catatan:
- Database dibuka READ-ONLY supaya UI tidak bisa mengubah data.
- Selama UI menyala, file DuckDB terkunci: hentikan UI sebelum menjalankan pipeline lagi.
- Run pertama mengunduh ekstensi `ui` dari extensions.duckdb.org; tampilan web dimuat
  dari ui.duckdb.org, sedangkan query dan data tetap diproses di laptop ini.
"""

from __future__ import annotations

import logging
import sys
import time

import duckdb

from jds.logging_setup import setup_logging
from jds.pipeline import LOCAL_DUCKDB

log = logging.getLogger("jds.ui")
UI_URL = "http://localhost:4213"
CATALOG = "jds_local"


def main() -> int:
    setup_logging()
    if not LOCAL_DUCKDB.exists():
        log.error("%s belum ada. Jalankan pipeline dulu.", LOCAL_DUCKDB)
        return 1

    # Instance utama in-memory (bisa ditulis) karena UI perlu membuat katalog state-nya
    # sendiri (_duckdb_ui). Data proyek di-ATTACH READ_ONLY sehingga tetap terlindungi.
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{LOCAL_DUCKDB.as_posix()}' AS {CATALOG} (READ_ONLY)")
        con.execute(f"USE {CATALOG}")
        con.sql("INSTALL ui; LOAD ui;")
        con.sql("CALL start_ui_server()")
        log.info(
            "DuckDB UI menyala di %s (katalog %s = %s, read-only)", UI_URL, CATALOG, LOCAL_DUCKDB
        )
        log.info("Tekan Ctrl+C untuk berhenti.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Menghentikan DuckDB UI.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
