"""Shared logging setup for all entrypoints."""

from __future__ import annotations

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s - %(message)s"


def setup_logging(level: str | None = None) -> None:
    """Level from the argument, then LOG_LEVEL, default INFO."""
    # Windows cp1252 consoles cannot encode emoji or µ when output is piped.
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")
    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(level=level_name, format=LOG_FORMAT, force=True)
