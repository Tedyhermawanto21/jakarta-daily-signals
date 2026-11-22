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


def test_expected_host_accepts_matching_endpoint_or_full_host(monkeypatch):
    url = "postgresql://u:p@ep-prod-123.c-3.ap-southeast-1.aws.neon.tech/jds?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", url)
    for expected in ("ep-prod-123", "EP-PROD-123.c-3.ap-southeast-1.aws.neon.tech"):
        monkeypatch.setenv("EXPECTED_DB_HOST", expected)
        assert get_database_url(load_env=False) == url


def test_expected_host_rejects_dev_url_in_production(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@ep-dev-999.c-3.ap-southeast-1.aws.neon.tech/jds?sslmode=require",
    )
    monkeypatch.setenv("EXPECTED_DB_HOST", "ep-prod-123")
    with pytest.raises(ConfigError, match="bukan EXPECTED_DB_HOST"):
        get_database_url(load_env=False)


def test_expected_host_is_optional_and_ignored_for_other_urls(monkeypatch):
    url = "postgresql://u:p@ep-dev-999.neon.tech/jds?sslmode=require"
    monkeypatch.delenv("EXPECTED_DB_HOST", raising=False)
    monkeypatch.setenv("DATABASE_URL", url)
    assert get_database_url(load_env=False) == url
    monkeypatch.setenv("EXPECTED_DB_HOST", "ep-prod-123")
    monkeypatch.setenv("LOOKER_READER_URL", url)  # cek host hanya untuk DATABASE_URL
    assert get_database_url(load_env=False, env_name="LOOKER_READER_URL") == url
