"""Klien Telegram Bot API minimal.

Keamanan: token bot ada DI URL (https://api.telegram.org/bot<TOKEN>/...). Pesan error requests
mencantumkan URL, jadi semua error di sini disaring dari token dan dilempar `from None`
(tanpa traceback berantai yang memuat URL asli).

Aturan retry sendMessage (cegah pesan ganda):
- dicoba ulang : gagal konek (pesan belum terkirim), HTTP 429, HTTP 5xx
- TIDAK diulang: read timeout (pesan mungkin sudah terkirim), HTTP 4xx lain

Setup chat_id:
    uv run python -m jds.alerts.telegram --chat-id   # setelah kirim /start ke bot
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import requests
from dotenv import load_dotenv
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from jds.config import ConfigError
from jds.logging_setup import setup_logging

log = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"
TIMEOUT = 20  # detik


class TelegramError(RuntimeError):
    """Gagal permanen (tidak dicoba ulang)."""


class _Retryable(RuntimeError):
    """Gagal sementara; aman dicoba ulang karena pesan pasti belum terkirim."""


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID kosong. Isi di .env (lihat Tahap 8)."
        )
    return token, chat_id


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _log_retry(token: str):
    def before_sleep(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        log.warning(
            "Telegram gagal sementara (percobaan %d): %s. Mencoba lagi...",
            state.attempt_number,
            _redact(str(exc), token),
        )

    return before_sleep


def _call(token: str, method: str, payload: dict | None = None) -> dict:
    """Satu panggilan API. Mengubah semua error menjadi _Retryable / TelegramError tanpa token."""
    url = f"{API_BASE}/bot{token}/{method}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=TIMEOUT)
    except requests.ReadTimeout:
        raise TelegramError(
            f"{method}: timeout setelah request terkirim; tidak diulang (cegah pesan ganda)."
        ) from None
    except requests.ConnectionError as exc:  # termasuk ConnectTimeout
        raise _Retryable(f"{method}: gagal konek: {_redact(str(exc), token)}") from None

    try:
        body = resp.json()
    except ValueError:
        body = {}
    description = _redact(str(body.get("description", "")), token)

    if resp.status_code == 429 or resp.status_code >= 500:
        raise _Retryable(f"{method}: HTTP {resp.status_code} {description}")
    if resp.status_code != 200 or not body.get("ok"):
        raise TelegramError(f"{method}: HTTP {resp.status_code} {description}")
    return body["result"]


def send_message(token: str, chat_id: str, text: str) -> int:
    """Kirim teks biasa, kembalikan message_id."""
    retrying = Retrying(
        retry=retry_if_exception_type(_Retryable),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=_log_retry(token),
        reraise=True,
    )
    try:
        for attempt in retrying:
            with attempt:
                result = _call(
                    token,
                    "sendMessage",
                    {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
                )
    except _Retryable as exc:
        raise TelegramError(f"menyerah setelah 4 percobaan: {exc}") from None
    return int(result["message_id"])


def list_chats(token: str) -> list[tuple[int, str]]:
    """Chat yang pernah mengirim pesan ke bot (dari getUpdates)."""
    chats: dict[int, str] = {}
    for update in _call(token, "getUpdates"):
        msg = update.get("message") or update.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if "id" in chat:
            name = chat.get("title") or " ".join(
                p for p in (chat.get("first_name"), chat.get("last_name")) if p
            )
            chats[chat["id"]] = f"{chat.get('type')}: {name}"
    return sorted(chats.items())


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(description="Helper setup Telegram")
    parser.add_argument("--chat-id", action="store_true", help="tampilkan chat_id dari getUpdates")
    args = parser.parse_args(argv)
    if not args.chat_id:
        parser.print_help()
        return 2

    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log.error("TELEGRAM_BOT_TOKEN kosong di .env.")
        return 2
    try:
        chats = list_chats(token)
    except (TelegramError, _Retryable) as exc:
        log.error("%s", exc)
        return 1
    if not chats:
        log.warning("Belum ada chat. Buka bot di Telegram, kirim /start, lalu jalankan lagi.")
        return 1
    for chat_id, label in chats:
        log.info("chat_id=%s  (%s)", chat_id, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
