"""TDD: minimal shared-secret authentication gating the whole HTTP API.

The gate only activates once an operator sets API_KEY. Leaving it unset (the
default, and what TestingConfig pins) keeps local dev and CI fully open —
matching this project's "no external key required" DX goal.
"""

from __future__ import annotations


def test_request_is_allowed_when_no_api_key_is_configured(client):
    response = client.get("/api/v1/books")

    assert response.status_code == 200


def test_request_is_rejected_without_credential_when_api_key_is_configured(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.get("/api/v1/books")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_request_is_rejected_with_wrong_credential(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.get("/api/v1/books", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401


def test_request_is_rejected_with_malformed_authorization_header(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.get("/api/v1/books", headers={"Authorization": "s3cret"})

    assert response.status_code == 401


def test_request_is_accepted_with_correct_credential(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.get("/api/v1/books", headers={"Authorization": "Bearer s3cret"})

    assert response.status_code == 200


def test_bearer_scheme_is_case_insensitive(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.get("/api/v1/books", headers={"Authorization": "bearer s3cret"})

    assert response.status_code == 200


def test_health_endpoints_are_exempt_even_when_api_key_is_configured(app, client):
    app.config["API_KEY"] = "s3cret"

    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_cors_preflight_request_is_exempt_from_the_api_key_check(app, client):
    app.config["API_KEY"] = "s3cret"

    response = client.options(
        "/api/v1/books",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code != 401
