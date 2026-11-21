"""Konfigurasi terpusat. Semua rahasia dibaca dari environment (.env lokal / GitHub Secrets)."""

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


# Satu titik dulu (PLAN §8 #4). Tambah lokasi cukup dengan menambah baris di sini.
LOCATIONS: tuple[Location, ...] = (Location("jkt_monas", "Jakarta (Monas)", -6.1754, 106.8272),)


class ConfigError(RuntimeError):
    """Konfigurasi wajib tidak ada atau tidak valid."""


def get_database_url(load_env: bool = True) -> str:
    """Ambil DATABASE_URL dan validasi formatnya.

    load_dotenv() tidak menimpa variabel yang sudah ada, jadi di CI nilai dari
    GitHub Secrets tetap dipakai.
    """
    if load_env:
        load_dotenv()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise ConfigError(
            "DATABASE_URL kosong. Isi di .env (lokal) atau GitHub Secrets (CI). Lihat .env.example."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ConfigError("DATABASE_URL harus diawali 'postgresql://'.")
    if "sslmode=" not in url:
        raise ConfigError("DATABASE_URL wajib memuat 'sslmode=require' (Neon mewajibkan SSL).")
    return url


def mask_url(url: str) -> str:
    """Ganti password di URL dengan *** supaya aman ditulis ke log."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return urlunsplit(parts._replace(netloc=netloc))
