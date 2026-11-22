from jds import config, pipeline


def test_postgres_without_database_url_exits_2_before_any_network(monkeypatch, capsys):
    # Never read the real .env: both pipeline and config call load_dotenv.
    monkeypatch.setattr(pipeline, "load_dotenv", lambda: None)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def fail(*_a, **_k):
        raise AssertionError("no DB or HTTP call allowed")

    monkeypatch.setattr(pipeline, "connect", fail)
    monkeypatch.setattr(pipeline, "build_resources", fail)

    assert pipeline.main(["--source", "fx", "--dest", "postgres"]) == 2
    # setup_logging() uses basicConfig(force=True), so logs go to stderr, not caplog.
    assert "DATABASE_URL is empty" in capsys.readouterr().err


def test_local_duckdb_path_is_absolute_inside_repo():
    # A relative path lets dlt reuse the path stored by another clone's pipeline state.
    from jds.pipeline import LOCAL_DUCKDB, REPO_ROOT

    assert LOCAL_DUCKDB.is_absolute()
    assert LOCAL_DUCKDB.parent == REPO_ROOT / "data"
    assert (REPO_ROOT / "pyproject.toml").exists()
