"""Prometheus exposition endpoint."""

from flask import Blueprint, Response

from app.metrics import metrics_payload

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/metrics")
def metrics() -> Response:
    payload, content_type = metrics_payload()
    return Response(payload, content_type=content_type)
