"""Open the DuckDB UI on the local database at http://localhost:4213 (Ctrl+C to stop).

The project database is attached read-only and stays locked while the UI runs.
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
        log.error("%s does not exist yet. Run the pipeline first.", LOCAL_DUCKDB)
        return 1

    # The UI needs a writable catalog of its own, so the main instance is in-memory.
    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{LOCAL_DUCKDB.as_posix()}' AS {CATALOG} (READ_ONLY)")
        con.execute(f"USE {CATALOG}")
        con.sql("INSTALL ui; LOAD ui;")
        con.sql("CALL start_ui_server()")
        log.info("DuckDB UI running at %s (%s = %s, read-only)", UI_URL, CATALOG, LOCAL_DUCKDB)
        log.info("Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping DuckDB UI.")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
