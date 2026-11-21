from jds import config, pipeline


def test_postgres_without_database_url_exits_2_before_any_network(monkeypatch, capsys):
    # Jangan baca .env asli: ada 2 tempat yang memanggil load_dotenv (pipeline & config).
    monkeypatch.setattr(pipeline, "load_dotenv", lambda: None)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    def fail(*_a, **_k):
        raise AssertionError("tidak boleh ada koneksi/HTTP")

    monkeypatch.setattr(pipeline, "connect", fail)
    monkeypatch.setattr(pipeline, "build_resources", fail)

    assert pipeline.main(["--source", "fx", "--dest", "postgres"]) == 2
    # setup_logging() memakai basicConfig(force=True) -> log ke stderr, bukan ke caplog
    assert "DATABASE_URL kosong" in capsys.readouterr().err
