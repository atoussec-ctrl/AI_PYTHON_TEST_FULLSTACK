"""Flask application factory for MindSight AI."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify
from flask_limiter.errors import RateLimitExceeded
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect as sa_inspect
from werkzeug.exceptions import HTTPException

from app.config import (
    assert_production_config_is_safe,
    assert_resource_limits_are_valid,
    config_by_name,
)
from app.errors import AuthenticationError, NotFoundError, ValidationError
from app.extensions import cors, db, limiter, migrate
from app.metrics import register_metrics_middleware
from app.request_id import configure_logging, current_request_id, register_request_id_middleware
from app.security import register_api_key_guard
from app.utils.http import error_response

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production'.
                     Falls back to the ``APP_ENV`` env-var, then 'development'.

    Returns:
        A fully configured Flask app instance.
    """
    if config_name is None:
        config_name = os.getenv("APP_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    assert_resource_limits_are_valid(app.config)
    app.config["MAX_CONTENT_LENGTH"] = int(app.config["MAX_UPLOAD_SIZE_MB"]) * 1024 * 1024
    if config_name == "production":
        assert_production_config_is_safe(app.config)

    configure_logging(app)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(MIGRATIONS_DIR))
    cors.init_app(app, origins=app.config["CORS_ALLOWED_ORIGINS"].split(","))
    limiter.init_app(app)

    _register_blueprints(app)
    _register_commands(app)
    _register_error_handlers(app)
    register_request_id_middleware(app)
    register_metrics_middleware(app)
    register_api_key_guard(app)

    @app.route("/health")
    def health():  # type: ignore[return]
        return jsonify(
            {
                "status": "ok",
                "service": "python-ai-assistant",
                "request_id": current_request_id(),
            }
        )

    with app.app_context():
        from app import models  # noqa: F401

        database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if str(database_uri).startswith("sqlite:///"):
            database_path = Path(str(database_uri).removeprefix("sqlite:///"))
            database_path.parent.mkdir(parents=True, exist_ok=True)
        Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)

        if app.config.get("TESTING"):
            # In-memory, recreated per test — a full migration run adds
            # nothing but latency here, and the DB never outlives the test.
            db.create_all()
        elif MIGRATIONS_DIR.exists():
            _apply_migrations(app)
        else:
            # Bootstrapping only: migrations/ doesn't exist yet, which is
            # only true while `flask db init` itself is being set up (it
            # needs a working create_app() to run against). Never true once
            # migrations/ is committed to the repo.
            db.create_all()

    return app


def _register_blueprints(app: Flask) -> None:
    """Import and register all API blueprints."""
    from app.routes.attachments import attachments_bp
    from app.routes.books import books_bp
    from app.routes.chat import chat_bp
    from app.routes.health import health_bp
    from app.routes.metrics import metrics_bp
    from app.routes.openapi import docs_bp
    from app.routes.semantic_search import semantic_search_bp

    app.register_blueprint(health_bp, url_prefix="/api/v1")
    app.register_blueprint(books_bp, url_prefix="/api/v1")
    app.register_blueprint(chat_bp, url_prefix="/api/v1")
    app.register_blueprint(attachments_bp, url_prefix="/api/v1")
    app.register_blueprint(semantic_search_bp, url_prefix="/api/v1")
    app.register_blueprint(docs_bp)
    app.register_blueprint(metrics_bp)


def _register_commands(app: Flask) -> None:
    from app.commands import register_commands

    register_commands(app)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):  # type: ignore[no-untyped-def]
        return error_response(
            code=error.name.replace(" ", "_").upper(),
            message=error.description,
            status_code=error.code or 500,
        )

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit_exceeded(error: RateLimitExceeded):  # type: ignore[no-untyped-def]
        return error_response(
            code="RATE_LIMIT_EXCEEDED",
            message="Muitas requisições em pouco tempo. Tente novamente em instantes.",
            status_code=429,
        )

    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(error: AuthenticationError):  # type: ignore[no-untyped-def]
        return error_response(
            code="UNAUTHORIZED",
            message=str(error),
            status_code=401,
        )

    @app.errorhandler(NotFoundError)
    def handle_not_found_error(error: NotFoundError):  # type: ignore[no-untyped-def]
        return error_response(
            code="NOT_FOUND",
            message=str(error),
            status_code=404,
        )

    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):  # type: ignore[no-untyped-def]
        return error_response(
            code="VALIDATION_ERROR",
            message=str(error),
            status_code=400,
            details={"field": error.field} if error.field else {},
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):  # type: ignore[no-untyped-def]
        if app.config.get("TESTING"):
            raise error
        app.logger.exception("Erro não tratado durante a requisição")
        return error_response(
            code="INTERNAL_SERVER_ERROR",
            message="Erro interno inesperado.",
            status_code=500,
        )


def _apply_migrations(app: Flask) -> None:
    """Bring the schema up to date using real Alembic migrations.

    Replaces the old db.create_all() + hand-rolled ALTER TABLE block, which
    only ever worked for SQLite and had no version history or rollback path
    — switching to Postgres would have silently left the schema stuck at
    whatever db.create_all() produced on day one.

    Handles the one-time transition for databases that predate Alembic: if
    the tables already exist (created by the old code) but there's no
    alembic_version table yet, the schema already matches this project's
    baseline migration — that's what the old code kept it in sync with — so
    it's stamped as up to date instead of re-running CREATE TABLE against
    tables that already exist. Anything else just upgrades normally.
    """
    inspector = sa_inspect(db.engine)
    schema_predates_alembic = inspector.has_table("chat_sessions") and not inspector.has_table(
        "alembic_version"
    )
    if schema_predates_alembic:
        stamp()
    else:
        upgrade()
