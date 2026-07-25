"""Request correlation: assign/echo X-Request-ID, apply LOG_LEVEL globally.

Every log line and error response emitted while handling a request should
carry the same id so an operator can grep one request's story out of the
logs. LOG_LEVEL existed in .env.example but nothing ever read it — the root
logger stayed at Python's default regardless of what an operator configured.
"""

from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from flask import Flask, g, has_request_context, request

logger = logging.getLogger(__name__)

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestIdLogFilter(logging.Filter):
    """Attaches the current request's id to every LogRecord as %(request_id)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = g.request_id if has_request_context() and "request_id" in g else "-"
        return True


def current_request_id() -> str | None:
    if has_request_context() and "request_id" in g:
        return g.request_id
    return None


def register_request_id_middleware(app: Flask) -> None:
    @app.before_request
    def _assign_request_id() -> None:
        supplied_request_id = request.headers.get("X-Request-ID", "")
        g.request_id = (
            supplied_request_id if _SAFE_REQUEST_ID.fullmatch(supplied_request_id) else str(uuid4())
        )
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _echo_request_id(response):  # type: ignore[no-untyped-def]
        response.headers["X-Request-ID"] = g.get("request_id", "")
        started_at = g.get("request_started_at")
        duration_ms = (time.perf_counter() - started_at) * 1000 if started_at is not None else 0.0
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response


class _RequestIdStreamHandler(logging.StreamHandler):
    """Marker subclass so the idempotency check below only ever matches a
    handler this module added — a generic `isinstance(x, StreamHandler)`
    check would also match unrelated handlers already on the root logger
    (e.g. pytest's own log-capture handler is a StreamHandler subclass too),
    and wrongly skip adding ours."""


def configure_logging(app: Flask) -> None:
    root = logging.getLogger()
    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))

    request_id_filter = next(
        (existing for existing in root.filters if isinstance(existing, RequestIdLogFilter)),
        None,
    )
    if request_id_filter is None:
        request_id_filter = RequestIdLogFilter()
        root.addFilter(request_id_filter)

    if app.config.get("TESTING"):
        # Adding a handler here would sit alongside pytest's own log-capture
        # handler (caplog) rather than replacing it, but it's still noise
        # test runs don't need — skip it entirely in testing mode.
        return
    handler = next(
        (existing for existing in root.handlers if isinstance(existing, _RequestIdStreamHandler)),
        None,
    )
    if handler is None:
        handler = _RequestIdStreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s: %(message)s"
            )
        )
        root.addHandler(handler)
    if not any(isinstance(existing, RequestIdLogFilter) for existing in handler.filters):
        # Logger filters are not applied to records propagated by child
        # loggers. The handler filter guarantees the formatter always sees
        # request_id for app.services.*, app.routes.*, and every other child.
        handler.addFilter(request_id_filter)
