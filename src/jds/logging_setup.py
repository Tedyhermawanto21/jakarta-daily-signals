"""Konfigurasi logging terpusat untuk semua entrypoint."""

from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s - %(message)s"


def setup_logging(level: str | None = None) -> None:
    """Pasang format log standar. Level dari argumen, lalu env LOG_LEVEL, default INFO."""
    # Konsol Windows (cp1252) tidak bisa menulis emoji/µ saat output di-pipe. Ganti karakter
    # yang tak terkodekan dengan escape alih-alih membuat logging error. Linux/CI tetap UTF-8.
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")
    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(level=level_name, format=LOG_FORMAT, force=True)
