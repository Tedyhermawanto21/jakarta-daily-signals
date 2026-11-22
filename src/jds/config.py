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


def get_database_url(load_env: bool = True, env_name: str = "DATABASE_URL") -> str:
    """Ambil URL database dari env `env_name` dan validasi formatnya.

    load_dotenv() tidak menimpa variabel yang sudah ada, jadi di CI nilai dari
    GitHub Secrets tetap dipakai.
    """
    if load_env:
        load_dotenv()
    url = os.getenv(env_name, "").strip()
    if not url:
        raise ConfigError(
            f"{env_name} kosong. Isi di .env (lokal) atau GitHub Secrets (CI). Lihat .env.example."
        )
    if not url.startswith(("postgresql://", "postgres://")):
        raise ConfigError(f"{env_name} harus diawali 'postgresql://'.")
    if "sslmode=" not in url:
        raise ConfigError(f"{env_name} wajib memuat 'sslmode=require' (Neon mewajibkan SSL).")
    if env_name == "DATABASE_URL":
        check_expected_host(url)
    return url


def check_expected_host(url: str) -> None:
    """Tolak URL yang mengarah ke host lain dari EXPECTED_DB_HOST (jika env itu diisi).

    Pengaman untuk workflow production: secret DATABASE_URL yang tidak sengaja diisi URL
    branch dev akan membuat workflow gagal di awal, bukan diam-diam menulis ke database
    yang salah (pernah terjadi di Tahap 11). Nilai boleh endpoint ID (ep-xxx) atau host penuh.
    """
    expected = os.getenv("EXPECTED_DB_HOST", "").strip().lower()
    if not expected:
        return
    host = (urlsplit(url).hostname or "").lower()
    if expected not in (host, host.split(".", 1)[0]):
        raise ConfigError(
            f"DATABASE_URL mengarah ke host '{host}', bukan EXPECTED_DB_HOST '{expected}'. "
            "Periksa secret DATABASE_URL (production vs dev)."
        )


def mask_url(url: str) -> str:
    """Ganti password di URL dengan *** supaya aman ditulis ke log."""
    parts = urlsplit(url)
    if parts.password is None:
        return url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return urlunsplit(parts._replace(netloc=netloc))
