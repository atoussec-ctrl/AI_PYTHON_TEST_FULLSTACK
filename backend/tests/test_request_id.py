"""TDD: request correlation.

Every response gets an X-Request-ID — generated when the client doesn't
send one, echoed back unchanged when it does — and application log records
emitted during that request carry the same id via a logging filter. Also
covers LOG_LEVEL actually being applied globally, which it previously
wasn't (documented in .env.example but never read by app code).
"""

from __future__ import annotations

import logging
from io import StringIO

from app.request_id import RequestIdLogFilter, configure_logging, current_request_id


def test_generates_a_request_id_when_the_client_does_not_send_one(client):
    response = client.get("/api/v1/health")

    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert response.get_json()["request_id"] == request_id


def test_generated_request_ids_are_unique_per_request(client):
    first = client.get("/api/v1/health").headers["X-Request-ID"]
    second = client.get("/api/v1/health").headers["X-Request-ID"]

    assert first != second


def test_echoes_back_a_client_provided_request_id(client):
    response = client.get("/api/v1/health", headers={"X-Request-ID": "client-abc-123"})

    assert response.headers["X-Request-ID"] == "client-abc-123"
    assert response.get_json()["request_id"] == "client-abc-123"


def test_replaces_an_unsafe_or_oversized_client_request_id(client):
    supplied = "x" * 129

    response = client.get("/api/v1/health", headers={"X-Request-ID": supplied})

    assert response.headers["X-Request-ID"] != supplied
    assert len(response.headers["X-Request-ID"]) == 36


def test_error_response_body_includes_the_same_request_id_as_the_header(client):
    response = client.get("/api/v1/rota-que-nao-existe", headers={"X-Request-ID": "trace-1"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "trace-1"
    assert response.get_json()["request_id"] == "trace-1"


def test_unprefixed_health_route_also_gets_a_request_id(client):
    response = client.get("/health")

    assert response.headers.get("X-Request-ID")
    assert response.get_json()["request_id"] == response.headers["X-Request-ID"]


# ── RequestIdLogFilter: injects the current request's id into log records ──


def test_log_filter_attaches_the_current_request_id(app):
    with app.test_request_context("/"):
        from flask import g

        g.request_id = "trace-xyz"
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)

        RequestIdLogFilter().filter(record)

    assert record.request_id == "trace-xyz"


def test_log_filter_defaults_to_a_dash_outside_a_request_context():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "msg", None, None)

    RequestIdLogFilter().filter(record)

    assert record.request_id == "-"


def test_current_request_id_returns_none_outside_a_request_context():
    assert current_request_id() is None


# ── configure_logging: applies LOG_LEVEL, stays test-safe ──


def test_configure_logging_applies_log_level_from_config(app):
    app.config["LOG_LEVEL"] = "DEBUG"

    configure_logging(app)

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_does_not_attach_a_stream_handler_in_testing_mode(app):
    # pytest's own LogCaptureHandler (a StreamHandler subclass) is already
    # attached to the root logger for every test — assert configure_logging
    # doesn't add one on top of it, rather than "no StreamHandler exists".
    handlers_before = len(logging.getLogger().handlers)

    configure_logging(app)

    assert len(logging.getLogger().handlers) == handlers_before


def test_configure_logging_does_not_duplicate_the_request_id_filter(app):
    configure_logging(app)
    configure_logging(app)

    filters = [f for f in logging.getLogger().filters if isinstance(f, RequestIdLogFilter)]
    assert len(filters) == 1


def test_configure_logging_attaches_a_formatted_stream_handler_outside_testing_mode(app):
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    app.config["TESTING"] = False

    try:
        configure_logging(app)
        new_handlers = [h for h in root.handlers if h not in handlers_before]

        assert len(new_handlers) == 1
        assert "request_id" in new_handlers[0].formatter._fmt
        assert any(isinstance(item, RequestIdLogFilter) for item in new_handlers[0].filters)
    finally:
        for handler in root.handlers[:]:
            if handler not in handlers_before:
                root.removeHandler(handler)


def test_configured_handler_formats_records_from_child_loggers(app):
    root = logging.getLogger()
    handlers_before = list(root.handlers)
    app.config["TESTING"] = False

    try:
        configure_logging(app)
        handler = next(handler for handler in root.handlers if handler not in handlers_before)
        stream = StringIO()
        handler.setStream(stream)

        with app.test_request_context("/"):
            from flask import g

            g.request_id = "child-trace"
            logging.getLogger("app.services.example").warning("child message")

        output = stream.getvalue()
        assert "request_id=child-trace" in output
        assert "child message" in output
    finally:
        for handler in root.handlers[:]:
            if handler not in handlers_before:
                root.removeHandler(handler)
