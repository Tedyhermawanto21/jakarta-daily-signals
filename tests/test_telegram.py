"""Telegram client without network: safe retries and the token never leaks."""

import pytest
import requests
from tenacity import wait_none

from jds.alerts import telegram
from jds.alerts.telegram import TelegramError, send_message

TOKEN = "123456:SECRET-TOKEN-abc"


class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def ok(mid=42):
    return FakeResp(200, {"ok": True, "result": {"message_id": mid}})


class FakePost:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, url, json=None, timeout=None):
        self.calls += 1
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    monkeypatch.setattr(telegram, "wait_exponential", lambda **_: wait_none())


def install(monkeypatch, fake):
    monkeypatch.setattr(telegram.requests, "post", fake)
    return fake


def test_success_returns_message_id(monkeypatch):
    fake = install(monkeypatch, FakePost(ok(7)))
    assert send_message(TOKEN, "1", "hi") == 7
    assert fake.calls == 1


def test_429_and_5xx_are_retried(monkeypatch):
    fake = install(
        monkeypatch,
        FakePost(
            FakeResp(429, {"ok": False, "description": "Too Many Requests"}),
            FakeResp(502, {}),
            ok(),
        ),
    )
    assert send_message(TOKEN, "1", "hi") == 42
    assert fake.calls == 3


def test_connect_error_is_retried(monkeypatch):
    fake = install(monkeypatch, FakePost(requests.ConnectionError("refused"), ok()))
    assert send_message(TOKEN, "1", "hi") == 42
    assert fake.calls == 2


def test_read_timeout_is_not_retried_to_avoid_duplicates(monkeypatch):
    fake = install(monkeypatch, FakePost(requests.ReadTimeout("read timed out"), ok()))
    with pytest.raises(TelegramError, match="not retried"):
        send_message(TOKEN, "1", "hi")
    assert fake.calls == 1


def test_bad_request_is_not_retried(monkeypatch):
    fake = install(
        monkeypatch, FakePost(FakeResp(400, {"ok": False, "description": "chat not found"}))
    )
    with pytest.raises(TelegramError, match="chat not found"):
        send_message(TOKEN, "1", "hi")
    assert fake.calls == 1


def test_token_never_leaks_in_errors_or_logs(monkeypatch, capsys):
    url_in_error = f"HTTPSConnectionPool: Max retries with url: /bot{TOKEN}/sendMessage"
    install(monkeypatch, FakePost(*[requests.ConnectionError(url_in_error)] * 4))
    with pytest.raises(TelegramError) as info:
        send_message(TOKEN, "1", "hi")
    assert TOKEN not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__
    assert TOKEN not in capsys.readouterr().err
