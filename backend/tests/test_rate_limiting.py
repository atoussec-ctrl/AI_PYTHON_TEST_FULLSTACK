"""TDD: rate limiting protects the chat endpoint (the one that calls a
paid LLM provider) from cost/abuse.

Disabled by default in tests (RATELIMIT_ENABLED=False, pinned in
TestingConfig) so the rest of the suite's repeated calls to the same routes
never get throttled. flask-limiter reads RATELIMIT_ENABLED once at
init_app() time and caches it on the extension instance — mutating
app.config after the app already exists has no effect, so each test here
monkeypatches TestingConfig and builds a fresh app instead, the same
pattern used for the production-config guard tests.
"""

from __future__ import annotations

from app.config import TestingConfig


def _client_with_rate_limiting_enabled(app_factory, monkeypatch, chat_limit="1 per hour"):
    monkeypatch.setattr(TestingConfig, "RATELIMIT_ENABLED", True)
    monkeypatch.setattr(TestingConfig, "RATE_LIMIT_CHAT_MESSAGES", chat_limit)
    app = app_factory("testing")
    with app.app_context():
        from app.extensions import db

        db.create_all()
    return app.test_client()


def test_rate_limiting_is_disabled_by_default_in_tests(client):
    for _ in range(10):
        response = client.get("/api/v1/books")

    assert response.status_code == 200


def test_exceeding_the_chat_message_limit_returns_429(app_factory, monkeypatch):
    client = _client_with_rate_limiting_enabled(app_factory, monkeypatch)
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    first = client.post("/api/v1/chat/messages", json={"session_id": session_id, "content": "oi"})
    second = client.post(
        "/api/v1/chat/messages", json={"session_id": session_id, "content": "oi de novo"}
    )

    assert first.status_code == 201
    assert second.status_code == 429
    body = second.get_json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limit_response_includes_retry_after_header(app_factory, monkeypatch):
    client = _client_with_rate_limiting_enabled(app_factory, monkeypatch)
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    client.post("/api/v1/chat/messages", json={"session_id": session_id, "content": "oi"})
    response = client.post(
        "/api/v1/chat/messages", json={"session_id": session_id, "content": "de novo"}
    )

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_other_routes_are_unaffected_by_the_chat_specific_limit(app_factory, monkeypatch):
    client = _client_with_rate_limiting_enabled(app_factory, monkeypatch)
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    client.post("/api/v1/chat/messages", json={"session_id": session_id, "content": "oi"})

    response = client.get("/api/v1/books")

    assert response.status_code == 200


def test_limit_allows_requests_again_once_the_window_is_wide_enough(app_factory, monkeypatch):
    client = _client_with_rate_limiting_enabled(app_factory, monkeypatch, chat_limit="2 per hour")
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    responses = [
        client.post("/api/v1/chat/messages", json={"session_id": session_id, "content": f"msg {i}"})
        for i in range(2)
    ]

    assert all(response.status_code == 201 for response in responses)
