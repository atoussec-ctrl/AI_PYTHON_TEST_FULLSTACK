"""Low-cardinality Prometheus instrumentation for HTTP and chat gateways."""

from __future__ import annotations

import logging
import os
import time

from flask import Flask, g, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

logger = logging.getLogger(__name__)

HTTP_REQUESTS = Counter(
    "mindsight_http_requests_total",
    "Completed HTTP requests.",
    labelnames=("method", "route", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "mindsight_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "route"),
)
CHAT_GATEWAY_CALLS = Counter(
    "mindsight_chat_gateway_calls_total",
    "Chat gateway calls by bounded provider and outcome.",
    labelnames=("provider", "outcome"),
)
CHAT_GATEWAY_DURATION = Histogram(
    "mindsight_chat_gateway_duration_seconds",
    "Chat gateway call latency in seconds.",
    labelnames=("provider", "outcome"),
)


def register_metrics_middleware(app: Flask) -> None:
    @app.before_request
    def _start_request_metrics() -> None:
        g.metrics_started_at = time.perf_counter()

    @app.after_request
    def _record_request_metrics(response):  # type: ignore[no-untyped-def]
        try:
            started_at = g.get("metrics_started_at")
            duration = time.perf_counter() - started_at if started_at is not None else 0.0
            # url_rule is the route template, e.g. /sessions/<session_id>, so user
            # input and resource IDs never become unbounded Prometheus labels.
            route = request.url_rule.rule if request.url_rule is not None else "unmatched"
            labels = {"method": request.method, "route": route}
            HTTP_REQUESTS.labels(**labels, status=str(response.status_code)).inc()
            HTTP_REQUEST_DURATION.labels(**labels).observe(duration)
        except Exception:
            logger.exception("Falha ao registrar métricas HTTP")
        return response


def record_gateway_call(*, provider: str, outcome: str, duration_seconds: float) -> None:
    """Record gateway telemetry without allowing observability to break chat."""
    try:
        labels = {"provider": provider, "outcome": outcome}
        CHAT_GATEWAY_CALLS.labels(**labels).inc()
        CHAT_GATEWAY_DURATION.labels(**labels).observe(duration_seconds)
    except Exception:  # pragma: no cover - defensive isolation around third-party telemetry
        logger.exception("Falha ao registrar métricas do gateway de chat")


def metrics_payload() -> tuple[bytes, str]:
    """Render a local registry or aggregate all Gunicorn worker registries."""
    multiprocess_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if multiprocess_dir:
        registry = CollectorRegistry(support_collectors_without_names=True)
        multiprocess.MultiProcessCollector(registry, path=multiprocess_dir)
    else:
        registry = REGISTRY
    return generate_latest(registry), CONTENT_TYPE_LATEST
