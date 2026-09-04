from app.config import Settings


def test_settings_reads_database_url_from_env(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/handoff"
    )
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/handoff"


def test_settings_splits_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/handoff")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com,http://b.com")
    settings = Settings()
    assert settings.cors_origins == ["http://a.com", "http://b.com"]
