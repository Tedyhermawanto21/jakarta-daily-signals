"""Jakarta Daily Signals: daily FX, weather, and air quality pipeline for Jakarta."""

import os

__version__ = "0.1.0"

# Must be set before dlt reads its config; setdefault keeps it overridable.
os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
