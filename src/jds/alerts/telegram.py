"""Minimal Telegram Bot API client.

The bot token is part of the URL, so every error is redacted and raised `from None`.
sendMessage is retried on connection errors, 429 and 5xx, but never on a read timeout:
the message may already have been delivered.

    uv run python -m jds.alerts.telegram --chat-id   # after sending /start to the bot
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
TIMEOUT = 20


class TelegramError(RuntimeError):
    """Permanent failure, not retried."""


class _Retryable(RuntimeError):
    """Temporary failure where the message was certainly not sent."""


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise ConfigError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is empty. Set them in .env.")
    return token, chat_id


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def _log_retry(token: str):
    def before_sleep(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        log.warning(
            "Telegram temporary failure (attempt %d): %s. Retrying...",
            state.attempt_number,
            _redact(str(exc), token),
        )

    return before_sleep


def _call(token: str, method: str, payload: dict | None = None) -> dict:
    """One API call; every error becomes _Retryable or TelegramError, without the token."""
    url = f"{API_BASE}/bot{token}/{method}"
    try:
        resp = requests.post(url, json=payload or {}, timeout=TIMEOUT)
    except requests.ReadTimeout:
        raise TelegramError(
            f"{method}: timed out after the request was sent; not retried to avoid duplicates."
        ) from None
    except requests.ConnectionError as exc:
        raise _Retryable(f"{method}: connection failed: {_redact(str(exc), token)}") from None

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
    """Send plain text and return the message_id."""
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
        raise TelegramError(f"gave up after 4 attempts: {exc}") from None
    return int(result["message_id"])


def list_chats(token: str) -> list[tuple[int, str]]:
    """Chats that have messaged the bot, from getUpdates."""
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
    parser = argparse.ArgumentParser(description="Telegram setup helper")
    parser.add_argument("--chat-id", action="store_true", help="print chat ids from getUpdates")
    args = parser.parse_args(argv)
    if not args.chat_id:
        parser.print_help()
        return 2

    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        log.error("TELEGRAM_BOT_TOKEN is empty in .env.")
        return 2
    try:
        chats = list_chats(token)
    except (TelegramError, _Retryable) as exc:
        log.error("%s", exc)
        return 1
    if not chats:
        log.warning("No chats yet. Open the bot in Telegram, send /start, then run this again.")
        return 1
    for chat_id, label in chats:
        log.info("chat_id=%s  (%s)", chat_id, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
