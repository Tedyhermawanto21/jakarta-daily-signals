import pytest

from jds import check_reader
from jds.check_reader import CHECKS, DENIED
from jds.config import ConfigError, get_database_url


def test_every_rejection_check_names_the_expected_layer():
    # Tanpa expect_code, penolakan oleh lapisan yang salah (mis. 25006) bisa lolos diam-diam.
    for check in CHECKS:
        if not check.should_succeed:
            assert check.expect_code, check.name


def test_grant_layer_is_tested_with_forced_read_write_transaction():
    forced = [c for c in CHECKS if c.force_read_write]
    assert forced and all(c.expect_code == DENIED and not c.should_succeed for c in forced)
    assert any("insert" in c.sql for c in forced)


def test_reader_url_uses_its_own_env_name(monkeypatch):
    monkeypatch.delenv("LOOKER_READER_URL", raising=False)
    with pytest.raises(ConfigError, match="LOOKER_READER_URL kosong"):
        get_database_url(load_env=False, env_name="LOOKER_READER_URL")


def test_cli_exits_2_without_url_and_never_connects(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("tidak boleh konek")

    monkeypatch.setattr(check_reader, "connect", boom)
    monkeypatch.setattr("jds.config.load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("LOOKER_READER_URL", raising=False)
    assert check_reader.main() == 2
