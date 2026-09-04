from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/handoff"
    )
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/handoff"
