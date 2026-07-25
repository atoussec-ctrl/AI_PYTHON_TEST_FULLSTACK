"""Prometheus metrics contract and instrumentation tests."""

from __future__ import annotations


def test_metrics_expose_request_count_errors_and_latency_with_route_templates(client):
    client.get("/api/v1/health")
    client.get("/api/v1/chat/sessions/sensitive-instance-id/messages")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.content_type.startswith("text/plain")
    payload = response.get_data(as_text=True)
    assert (
        'mindsight_http_requests_total{method="GET",route="/api/v1/health",status="200"}' in payload
    )
    assert (
        'mindsight_http_requests_total{method="GET",'
        'route="/api/v1/chat/sessions/<session_id>/messages",status="404"}' in payload
    )
    assert "sensitive-instance-id" not in payload
    assert "mindsight_http_request_duration_seconds_bucket" in payload


def test_metrics_record_chat_gateway_success(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    message = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "Como criar uma lista?"},
    )
    assert message.status_code == 201

    payload = client.get("/metrics").get_data(as_text=True)

    assert 'mindsight_chat_gateway_calls_total{outcome="success",provider="local"}' in payload
    assert (
        'mindsight_chat_gateway_duration_seconds_count{outcome="success",provider="local"}'
        in payload
    )


def test_metrics_record_chat_gateway_failure(client, app, monkeypatch):
    from app.services.chat import LocalPythonAssistantGateway

    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(LocalPythonAssistantGateway, "answer", fail)
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "falhe"},
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "failed"
    payload = client.get("/metrics").get_data(as_text=True)
    assert 'mindsight_chat_gateway_calls_total{outcome="failure",provider="local"}' in payload


def test_metrics_endpoint_obeys_api_key_guard(client, app):
    app.config["API_KEY"] = "metrics-secret"

    denied = client.get("/metrics")
    allowed = client.get("/metrics", headers={"Authorization": "Bearer metrics-secret"})

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_metrics_failure_never_breaks_the_http_response(client, monkeypatch, caplog):
    from app.metrics import HTTP_REQUESTS

    def fail_labels(**kwargs):
        raise RuntimeError("metrics backend unavailable")

    monkeypatch.setattr(HTTP_REQUESTS, "labels", fail_labels)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "Falha ao registrar métricas HTTP" in caplog.text


def test_metrics_payload_supports_prometheus_multiprocess_directory(tmp_path, monkeypatch):
    from app.metrics import metrics_payload

    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    payload, content_type = metrics_payload()

    assert isinstance(payload, bytes)
    assert content_type.startswith("text/plain")
