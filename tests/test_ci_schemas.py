import pytest

from jds import ci_schemas, run_dbt
from jds.ci_schemas import drop_schemas, validate_prefix
from jds.config import ConfigError


class FakeCursor:
    def __init__(self, existing, executed):
        self.existing = existing
        self.executed = executed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchall(self):
        return [(name,) for name in self.existing]


class FakeConn:
    def __init__(self, existing):
        self.existing = existing
        self.executed = []
        self.committed = False

    def cursor(self):
        return FakeCursor(self.existing, self.executed)

    def commit(self):
        self.committed = True


@pytest.mark.parametrize("prefix", ["ci_pr_1", "ci_pr_12345"])
def test_validate_prefix_accepts_pr_numbers(prefix):
    assert validate_prefix(prefix) == prefix


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "marts",
        "raw",
        "staging",
        "ci_pr_",
        "ci_pr_x",
        "CI_PR_1",
        "ci_pr_1_marts",
        "ci_pr_1; drop",
    ],
)
def test_validate_prefix_rejects_anything_that_could_hit_real_schemas(prefix):
    with pytest.raises(ConfigError):
        validate_prefix(prefix)


def test_drop_schemas_drops_only_listed_schemas_quoted_and_commits():
    conn = FakeConn(["ci_pr_7_marts", "ci_pr_7_staging"])
    assert drop_schemas(conn, "ci_pr_7") == ["ci_pr_7_marts", "ci_pr_7_staging"]

    lookup, params = conn.executed[0]
    assert params == ("ci_pr_7_",)  # not "ci_pr_7", which would also match ci_pr_70
    drops = [repr(q) for q, _ in conn.executed[1:]]
    assert len(drops) == 2
    assert "Identifier('ci_pr_7_marts')" in drops[0]
    assert "Identifier('ci_pr_7_staging')" in drops[1]
    assert conn.committed


def test_drop_schemas_is_idempotent_when_nothing_exists():
    conn = FakeConn([])
    assert drop_schemas(conn, "ci_pr_7") == []
    assert len(conn.executed) == 1


def test_drop_schemas_refuses_bad_prefix_before_touching_db():
    conn = FakeConn(["marts"])
    with pytest.raises(ConfigError):
        drop_schemas(conn, "marts")
    assert conn.executed == []


def test_cli_rejects_bad_prefix_without_connecting(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("must not connect")

    monkeypatch.setattr(ci_schemas, "connect", boom)
    monkeypatch.setenv("DBT_SCHEMA_PREFIX", "marts")
    assert ci_schemas.main(["drop"]) == 2


def test_run_dbt_rejects_bad_prefix_before_running_dbt(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("must not connect")

    monkeypatch.setattr(run_dbt, "connect", boom)
    monkeypatch.setattr(run_dbt, "get_database_url", boom)
    monkeypatch.setenv("DBT_SCHEMA_PREFIX", "public")
    assert run_dbt.main(["build"]) == 2
