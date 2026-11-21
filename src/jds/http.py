"""HTTP client bersama: satu Session, timeout, dan retry dengan backoff.

Aturan retry:
- dicoba ulang : timeout, error koneksi, HTTP 429, HTTP 5xx  (biasanya sembuh sendiri)
- langsung gagal: HTTP 4xx lain (mis. 404 tanggal/simbol salah) -> bug di request kita
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
DEFAULT_TIMEOUT = 30  # detik

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class TransientHTTPError(RuntimeError):
    """Error HTTP yang layak dicoba ulang (429 / 5xx)."""


@retry(
    retry=retry_if_exception_type((TransientHTTPError, requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET dan kembalikan JSON. Raise requests.HTTPError untuk 4xx non-429."""
    log.debug("GET %s params=%s", url, params)
    resp = _session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TransientHTTPError(f"HTTP {resp.status_code} dari {resp.url}")
    resp.raise_for_status()
    return resp.json()
