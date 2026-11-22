"""Shared HTTP client: one session, a timeout, and retry with backoff.

Retried: timeouts, connection errors, HTTP 429 and 5xx.
Not retried: other 4xx, which mean the request itself is wrong.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)

USER_AGENT = "jakarta-daily-signals/0.1 (+portfolio project)"
DEFAULT_TIMEOUT = 30

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class TransientHTTPError(RuntimeError):
    """HTTP error worth retrying (429 or 5xx)."""


@retry(
    retry=retry_if_exception_type((TransientHTTPError, requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET and return JSON. Raises requests.HTTPError for non-429 4xx."""
    log.debug("GET %s params=%s", url, params)
    resp = _session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TransientHTTPError(f"HTTP {resp.status_code} from {resp.url}")
    resp.raise_for_status()
    return resp.json()
