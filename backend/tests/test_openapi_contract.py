import json
from pathlib import Path

from app.routes.openapi import openapi_spec


def test_openapi_documents_all_api_routes(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.get_json()
    paths = spec["paths"]

    expected = {
        "/api/v1/health",
        "/api/v1/books",
        "/api/v1/books/import",
        "/api/v1/books/{book_id}",
        "/api/v1/chat/sessions",
        "/api/v1/chat/sessions/{session_id}",
        "/api/v1/chat/sessions/{session_id}/messages",
        "/api/v1/chat/messages",
        "/api/v1/chat/messages/{assistant_message_id}/stream",
        "/api/v1/chat/messages/{assistant_message_id}/feedback",
        "/api/v1/attachments",
        "/api/v1/attachments/{attachment_id}",
        "/api/v1/semantic-search",
        "/metrics",
    }
    assert expected.issubset(paths.keys())
    assert "Book" in spec["components"]["schemas"]
    assert "ErrorResponse" in spec["components"]["schemas"]


def test_openapi_documents_shared_bearer_auth_and_exempts_health(client):
    spec = client.get("/openapi.json").get_json()

    assert spec["security"] == [{"bearerAuth": []}]
    assert spec["components"]["securitySchemes"]["bearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "description": (
            "Shared API_KEY configured by the operator. Optional only when "
            "the backend runs locally with API_KEY unset."
        ),
    }
    assert spec["paths"]["/api/v1/health"]["get"]["security"] == []


def test_openapi_chat_message_status_matches_runtime_values(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.get_json()
    status_schema = spec["components"]["schemas"]["ChatMessage"]["properties"]["status"]

    assert "failed" in status_schema["enum"]
    assert "error" not in status_schema["enum"]


def test_openapi_nullable_fields_match_runtime_values(client):
    schemas = client.get("/openapi.json").get_json()["components"]["schemas"]

    assert schemas["ChatSession"]["properties"]["pinned_at"] == {
        "type": "string",
        "format": "date-time",
        "nullable": True,
    }
    assert schemas["ChatMessage"]["properties"]["thinking_mode"]["nullable"] is True


def test_openapi_documents_global_upload_limit_responses(client):
    paths = client.get("/openapi.json").get_json()["paths"]

    assert "413" in paths["/api/v1/attachments"]["post"]["responses"]
    assert "413" in paths["/api/v1/books/import"]["post"]["responses"]


def test_openapi_documents_atomic_multipart_message_upload(client):
    operation = client.get("/openapi.json").get_json()["paths"]["/api/v1/chat/messages"]["post"]
    content = operation["requestBody"]["content"]

    assert "application/json" in content
    multipart = content["multipart/form-data"]["schema"]
    assert multipart["properties"]["files"]["type"] == "array"
    assert multipart["properties"]["files"]["maxItems"] == 5
    assert multipart["properties"]["attachment_kinds"]["maxItems"] == 5
    assert "413" in operation["responses"]


def test_committed_openapi_artifact_matches_executable_spec():
    artifact = Path(__file__).resolve().parents[1] / "openapi.json"

    assert json.loads(artifact.read_text(encoding="utf-8")) == openapi_spec()


def test_swagger_docs_page_points_to_openapi(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert b"SwaggerUIBundle" in response.data
    assert b"/openapi.json" in response.data
