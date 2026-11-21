import psycopg2
import pytest

from jds.check_db import _is_transient
from jds.config import ConfigError, get_database_url, mask_url

VALID = "postgresql://neondb_owner:s3cr3t@ep-x-123.ap-southeast-1.aws.neon.tech/jds?sslmode=require"


def test_mask_url_hides_password():
    masked = mask_url(VALID)
    assert "s3cr3t" not in masked
    assert "neondb_owner:***@" in masked


def test_mask_url_without_password_unchanged():
    assert mask_url("postgresql://host/db") == "postgresql://host/db"


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError, match="kosong"):
        get_database_url(load_env=False)


def test_sslmode_required(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", VALID.split("?")[0])
    with pytest.raises(ConfigError, match="sslmode"):
        get_database_url(load_env=False)


def test_valid_url_returned(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", VALID)
    assert get_database_url(load_env=False) == VALID


def test_auth_error_is_not_retried():
    err = psycopg2.OperationalError('password authentication failed for user "x"')
    assert _is_transient(err) is False


def test_timeout_is_retried():
    assert _is_transient(psycopg2.OperationalError("timeout expired")) is True
