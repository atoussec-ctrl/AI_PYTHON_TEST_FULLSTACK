"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.extensions import db as _db


def _dispose_database(application: Flask) -> None:
    with application.app_context():
        _db.session.remove()
        _db.engine.dispose()


@pytest.fixture()
def app_factory() -> Generator[Callable[[str | None], Flask], None, None]:
    """Create extra app instances and deterministically close their engines."""
    applications: list[Flask] = []

    def factory(config_name: str | None = None) -> Flask:
        application = create_app(config_name)
        applications.append(application)
        return application

    yield factory
    for application in reversed(applications):
        _dispose_database(application)


@pytest.fixture()
def app(tmp_path: Path) -> Generator[Flask, None, None]:
    """Create a Flask app configured for isolated tests."""
    application = create_app("testing")
    application.config["UPLOAD_DIR"] = str(tmp_path / "uploads")
    with application.app_context():
        _db.drop_all()
        _db.create_all()
    yield application
    with application.app_context():
        _db.session.remove()
        _db.drop_all()
    _dispose_database(application)


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Return a Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture()
def db_session(app: Flask) -> Generator:
    """Provide a clean database session for each test.

    Rolls back all changes after the test finishes so every test
    starts with a pristine database.
    """
    with app.app_context():
        yield _db.session
        _db.session.rollback()
