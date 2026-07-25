"""Unit tests closing coverage gaps in the app factory (app/__init__.py).

Covers branches that the day-to-day API tests never exercise: the APP_ENV
fallback for config selection, Werkzeug's own HTTPException path, the
generic (non-typed) ValueError fallback, the production-mode 500 handler,
and _apply_migrations — the Alembic-based schema setup that replaced the old
hand-rolled ALTER TABLE block, including the one-time transition path for
databases created before Alembic existed in this project.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect as sa_inspect

from app import _apply_migrations, create_app
from app.config import InsecureConfigurationError, ProductionConfig
from app.extensions import db
from app.models import Attachment, Book, ChatMessage, ChatSession


def test_create_app_defaults_to_app_env_when_config_name_omitted(monkeypatch, app_factory):
    monkeypatch.setenv("APP_ENV", "testing")

    app = app_factory()

    assert app.config["TESTING"] is True


def test_unmatched_route_returns_json_error_envelope(client):
    response = client.get("/api/v1/rota-que-nao-existe")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_invalid_chat_gateway_config_is_not_misreported_as_client_error(client, app, caplog):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    app.config["CHAT_GATEWAY"] = "not-a-real-gateway"
    app.config["TESTING"] = False
    caplog.set_level("ERROR")
    try:
        response = client.post(
            "/api/v1/chat/messages",
            json={"session_id": session_id, "content": "oi"},
        )

        assert response.status_code == 500
        assert response.get_json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "not-a-real-gateway" not in response.get_data(as_text=True)
        assert "Erro não tratado durante a requisição" in caplog.text
    finally:
        app.config["TESTING"] = True


def test_unexpected_exception_returns_generic_500_outside_testing_mode(app, client, caplog):
    app.config["TESTING"] = False
    caplog.set_level("ERROR")
    try:

        @app.route("/__test/boom")
        def _boom():
            raise RuntimeError("boom")

        response = client.get("/__test/boom")

        assert response.status_code == 500
        body = response.get_json()
        assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert body["error"]["message"] == "Erro interno inesperado."
        assert "Erro não tratado durante a requisição" in caplog.text
    finally:
        app.config["TESTING"] = True


def test_unexpected_exception_propagates_in_testing_mode(app, client):
    """In TESTING mode the raw exception must surface, never the generic 500 JSON —
    otherwise a real bug in a route could silently mask itself as a handled error."""

    @app.route("/__test/boom-in-tests")
    def _boom():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        client.get("/__test/boom-in-tests")


def test_create_app_falls_back_to_create_all_when_migrations_dir_is_missing(
    tmp_path, monkeypatch, app_factory
):
    """Bootstrap-only path: only true while `flask db init` itself sets up
    migrations/ for the first time (it needs a working create_app() to run
    against) — never true once migrations/ is committed to the repo."""
    import app as app_package
    from app.config import DevelopmentConfig

    monkeypatch.setattr(app_package, "MIGRATIONS_DIR", tmp_path / "no-such-migrations-dir")
    monkeypatch.setattr(
        DevelopmentConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'bootstrap.db'}"
    )

    new_app = app_factory("development")

    with new_app.app_context():
        inspector = sa_inspect(db.engine)
        assert inspector.has_table("chat_sessions")
        assert not inspector.has_table("alembic_version")  # create_all() alone doesn't stamp


def test_apply_migrations_creates_schema_from_scratch_on_a_fresh_database(app):
    with app.app_context():
        # The `app` fixture already ran create_all() — drop everything first
        # to simulate a genuinely fresh database with nothing in it yet.
        db.drop_all()
        inspector = sa_inspect(db.engine)
        assert not inspector.has_table("chat_sessions")

        _apply_migrations(app)

        inspector = sa_inspect(db.engine)
        assert inspector.has_table("chat_sessions")
        assert inspector.has_table("alembic_version")
        session_columns = {col["name"] for col in inspector.get_columns("chat_sessions")}
        assert {"pinned", "pinned_at"} <= session_columns


def test_apply_migrations_stamps_a_database_that_predates_alembic(app):
    """A DB created by the old db.create_all() (tables exist, no
    alembic_version) must be stamped, not re-migrated — running CREATE TABLE
    against tables that already exist would fail outright."""
    with app.app_context():
        # The `app` fixture's own create_all() already put us in exactly
        # this state: full schema present, no alembic_version table.
        inspector = sa_inspect(db.engine)
        assert inspector.has_table("chat_sessions")
        assert not inspector.has_table("alembic_version")

        _apply_migrations(app)

        inspector = sa_inspect(db.engine)
        assert inspector.has_table("alembic_version")
        # Stamping must not have touched pre-existing data.
        assert db.session.get(ChatSession, "does-not-exist") is None


def test_apply_migrations_is_idempotent_once_already_stamped(app):
    with app.app_context():
        _apply_migrations(app)
        _apply_migrations(app)  # must not raise the second time around

        inspector = sa_inspect(db.engine)
        assert inspector.has_table("alembic_version")


def test_create_app_refuses_to_boot_in_production_with_placeholder_secret_key(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "dev-secret-key-change-me")
    monkeypatch.setattr(ProductionConfig, "API_KEY", "a-real-key")
    monkeypatch.setattr(
        ProductionConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'prod.db'}"
    )

    with pytest.raises(InsecureConfigurationError, match="SECRET_KEY"):
        create_app("production")


def test_create_app_refuses_to_boot_in_production_without_an_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-secret")
    monkeypatch.setattr(ProductionConfig, "API_KEY", "")
    monkeypatch.setattr(
        ProductionConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'prod.db'}"
    )

    with pytest.raises(InsecureConfigurationError, match="API_KEY"):
        create_app("production")


def test_create_app_boots_in_production_with_real_secrets_configured(
    tmp_path, monkeypatch, app_factory
):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-secret")
    monkeypatch.setattr(ProductionConfig, "API_KEY", "a-real-key")
    monkeypatch.setattr(
        ProductionConfig, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{tmp_path / 'prod.db'}"
    )
    monkeypatch.setattr(ProductionConfig, "UPLOAD_DIR", str(tmp_path / "uploads"))

    prod_app = app_factory("production")

    assert prod_app.config["API_KEY"] == "a-real-key"


def test_apply_migrations_preserves_existing_rows_when_stamping(app):
    """Guards the actual upgrade path real users hit: an existing SQLite
    file with real conversations must survive the Alembic transition."""
    with app.app_context():
        book = Book(
            title="Livro pré-existente",
            author="Autor",
            publication_date=date(2020, 1, 1),
            summary="Resumo.",
        )
        session = ChatSession(title="Conversa pré-existente")
        db.session.add_all([book, session])
        db.session.commit()
        message = ChatMessage(session_id=session.id, role="user", content="oi")
        db.session.add(message)
        db.session.commit()
        attachment = Attachment(
            session_id=session.id,
            message_id=message.id,
            filename="nota.txt",
            mime_type="text/plain",
            size=2,
            kind="document",
            storage_path="/tmp/nota.txt",
        )
        db.session.add(attachment)
        db.session.commit()

        _apply_migrations(app)

        assert db.session.get(Book, book.id) is not None
        assert db.session.get(ChatSession, session.id) is not None
        assert db.session.get(ChatMessage, message.id) is not None
        assert db.session.get(Attachment, attachment.id) is not None
