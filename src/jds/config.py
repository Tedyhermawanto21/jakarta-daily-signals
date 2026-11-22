"""Central configuration. Secrets come from the environment (.env locally, GitHub Secrets in CI)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv

TIMEZONE = "Asia/Jakarta"
SCHEMAS: tuple[str, ...] = ("raw", "staging", "marts", "ops")


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str
    latitude: float
    longitude: float


LOCATIONS: tuple[Location, ...] = (Location("jkt_monas", "Jakarta (Monas)", -6.1754, 106.8272),)


class ConfigError(RuntimeError):
    """Required configuration is missing or invalid."""


def get_database_url(load_env: bool = True, env_name: str = "DATABASE_URL") -> str:
    """Read and validate a Postgres URL. load_dotenv() never overrides existing variables."""
    if load_env:
        load_dotenv()
    url = os.getenv(env_name, "").strip()
    if not url:
        raise ConfigError(
            f"{env_name} is empty. Set it in .env (local) or GitHub Secrets (CI). See .env.example."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ConfigError(f"{env_name} must start with 'postgresql://'.")
    if "sslmode=" not in url:
        raise ConfigError(f"{env_name} must include 'sslmode=require' (Neon requires SSL).")
    if env_name == "DATABASE_URL":
        check_expected_host(url)
    return url


def check_expected_host(url: str) -> None:
    """Fail fast when EXPECTED_DB_HOST is set and the URL points elsewhere.

    Accepts an endpoint ID (ep-xxx) or a full host name.
    """
    expected = os.getenv("EXPECTED_DB_HOST", "").strip().lower()
    if not expected:
        return
    host = (urlsplit(url).hostname or "").lower()
    if expected not in (host, host.split(".", 1)[0]):
        raise ConfigError(
            f"DATABASE_URL points to host '{host}', not EXPECTED_DB_HOST '{expected}'. "
            "Check the DATABASE_URL secret (production vs dev)."
        )


def mask_url(url: str) -> str:
    """Replace the password with *** so the URL is safe to log."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return urlunsplit(parts._replace(netloc=netloc))
