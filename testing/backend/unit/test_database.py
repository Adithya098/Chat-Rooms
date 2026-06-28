from app import database


def test_database_url_uses_db_parts(monkeypatch):
    monkeypatch.setenv("DB_USER", "user1")
    monkeypatch.setenv("DB_PASSWORD", "pass1")
    monkeypatch.setenv("DB_HOST", "db.local")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_NAME", "chat_test")
    monkeypatch.setenv("DB_SSLMODE", "require")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    url = str(database._database_url())
    assert "db.local:5433/chat_test" in url
    assert "sslmode=require" in url


def test_database_url_falls_back_to_database_url(monkeypatch):
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost:5432/override")

    # The DATABASE_URL driver is normalized to psycopg (the Render fix), so a bare
    # postgresql:// URL is rewritten to postgresql+psycopg://.
    assert database._database_url() == "postgresql+psycopg://localhost:5432/override"


def test_database_url_normalizes_postgres_scheme(monkeypatch):
    monkeypatch.delenv("DB_USER", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)
    monkeypatch.delenv("DB_HOST", raising=False)
    # The legacy postgres:// scheme is likewise rewritten to postgresql+psycopg://.
    monkeypatch.setenv("DATABASE_URL", "postgres://localhost:5432/legacy")

    assert database._database_url() == "postgresql+psycopg://localhost:5432/legacy"
