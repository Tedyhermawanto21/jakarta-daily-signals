"""Retry rules of jds.http.get_json, with Session.get mocked."""

import json

import pytest
import requests
from tenacity import wait_none

from jds import http
from jds.http import TransientHTTPError, get_json


def make_response(status: int, body: dict | None = None) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(body or {}).encode()
    resp.url = "https://api.test/v1/x"
    return resp


class FakeGet:
    """Returns queued outcomes (Response or Exception) and counts calls."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, url, params=None, timeout=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    """Disable backoff sleeps; the retry logic itself is unchanged."""
    monkeypatch.setattr(get_json.retry, "wait", wait_none())
    monkeypatch.setattr(get_json.retry, "sleep", lambda _seconds: None)


def install(monkeypatch, fake: FakeGet) -> FakeGet:
    monkeypatch.setattr(http._session, "get", fake)
    return fake


def test_success_first_try(monkeypatch):
    fake = install(monkeypatch, FakeGet(make_response(200, {"ok": 1})))
    assert get_json("https://api.test/v1/x") == {"ok": 1}
    assert fake.calls == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_transient_status_is_retried_then_succeeds(monkeypatch, status):
    fake = install(monkeypatch, FakeGet(make_response(status), make_response(200, {"ok": 1})))
    assert get_json("https://api.test/v1/x") == {"ok": 1}
    assert fake.calls == 2


@pytest.mark.parametrize("exc", [requests.ConnectionError("reset"), requests.Timeout("slow")])
def test_network_errors_are_retried(monkeypatch, exc):
    fake = install(monkeypatch, FakeGet(exc, make_response(200, {"ok": 1})))
    assert get_json("https://api.test/v1/x") == {"ok": 1}
    assert fake.calls == 2


@pytest.mark.parametrize("status", [400, 401, 404])
def test_client_errors_fail_immediately_without_retry(monkeypatch, status):
    fake = install(monkeypatch, FakeGet(make_response(status)))
    with pytest.raises(requests.HTTPError):
        get_json("https://api.test/v1/x")
    assert fake.calls == 1


def test_gives_up_after_5_attempts(monkeypatch):
    fake = install(monkeypatch, FakeGet(*[make_response(503) for _ in range(5)]))
    with pytest.raises(TransientHTTPError):
        get_json("https://api.test/v1/x")
    assert fake.calls == 5
