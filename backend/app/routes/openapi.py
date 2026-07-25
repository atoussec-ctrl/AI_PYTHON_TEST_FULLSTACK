"""OpenAPI contract and Swagger UI."""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.config import DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE

docs_bp = Blueprint("docs", __name__)


def openapi_spec() -> dict[str, object]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MindSight AI API",
            "version": "1.0.0",
            "description": (
                "Flask API for the backend AI challenge: virtual library, "
                "Python assistant, LangSmith feedback, uploads and semantic search."
            ),
        },
        "servers": [
            {"url": "http://localhost:5000", "description": "Local Flask"},
            {"url": "http://localhost:3002", "description": "Vite proxy / Docker frontend"},
        ],
        "tags": [
            {"name": "Health"},
            {"name": "Books"},
            {"name": "Chat"},
            {"name": "Attachments"},
            {"name": "Semantic Search"},
            {"name": "Observability"},
        ],
        "security": [{"bearerAuth": []}],
        "paths": paths(),
        "components": components(),
    }


def paths() -> dict[str, object]:
    return {
        "/api/v1/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Health check",
                "security": [],
                "responses": {"200": json_response("HealthResponse")},
            }
        },
        "/metrics": {
            "get": {
                "tags": ["Observability"],
                "summary": "Expose Prometheus metrics",
                "responses": {
                    "200": {
                        "description": "Prometheus text exposition format",
                        "content": {"text/plain": {"schema": {"type": "string"}}},
                    },
                    "401": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/books": {
            "get": {
                "tags": ["Books"],
                "summary": "Search books",
                "parameters": [
                    query_param("title", "Filter by title"),
                    query_param("author", "Filter by author"),
                    query_param("category", "Filter by category"),
                    query_param("q", "Search title, author, category and summary"),
                    *pagination_params(),
                ],
                "responses": {"200": array_response("Book")},
            },
            "post": {
                "tags": ["Books"],
                "summary": "Create a book",
                "requestBody": json_body("CreateBookRequest"),
                "responses": {
                    "201": json_response("Book"),
                    "400": json_response("ErrorResponse"),
                },
            },
        },
        "/api/v1/books/import": {
            "post": {
                "tags": ["Books"],
                "summary": "Import a book from uploaded file",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {
                                    "file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": (
                                            ".txt, .md, .json or .pdf containing "
                                            "title, author, category, year and summary. "
                                            "Content and declared MIME are validated; PDFs "
                                            "are subject to configured resource limits."
                                        ),
                                    }
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": json_response("ImportBookResponse"),
                    "400": json_response("ErrorResponse"),
                    "413": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/books/{book_id}": {
            "get": {
                "tags": ["Books"],
                "summary": "Get a book by id",
                "parameters": [path_param("book_id", "Book id")],
                "responses": {
                    "200": json_response("Book"),
                    "404": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/chat/sessions": {
            "get": {
                "tags": ["Chat"],
                "summary": "List chat sessions",
                "parameters": pagination_params(),
                "responses": {"200": array_response("ChatSession")},
            },
            "post": {
                "tags": ["Chat"],
                "summary": "Create chat session",
                "requestBody": json_body("CreateChatSessionRequest", required=False),
                "responses": {"201": json_response("ChatSession")},
            },
        },
        "/api/v1/chat/sessions/{session_id}": {
            "delete": {
                "tags": ["Chat"],
                "summary": "Delete a chat session and its messages",
                "parameters": [path_param("session_id", "Chat session id")],
                "responses": {
                    "204": {"description": "Session deleted"},
                    "404": json_response("ErrorResponse"),
                },
            },
            "patch": {
                "tags": ["Chat"],
                "summary": "Update chat session metadata",
                "parameters": [path_param("session_id", "Chat session id")],
                "requestBody": json_body("UpdateChatSessionRequest"),
                "responses": {
                    "200": json_response("ChatSession"),
                    "404": json_response("ErrorResponse"),
                },
            },
        },
        "/api/v1/chat/sessions/{session_id}/messages": {
            "get": {
                "tags": ["Chat"],
                "summary": "List messages from a session",
                "parameters": [path_param("session_id", "Chat session id"), *pagination_params()],
                "responses": {
                    "200": array_response("ChatMessage"),
                    "404": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/chat/messages": {
            "post": {
                "tags": ["Chat"],
                "summary": "Send a user message and create an assistant answer",
                "description": "Rate limited (RATE_LIMIT_CHAT_MESSAGES, default 20/min per IP).",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": ref("SendMessageRequest")},
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["session_id"],
                                "properties": {
                                    "session_id": string(),
                                    "content": string(),
                                    "thinking_mode": {
                                        "type": "string",
                                        "enum": ["fast", "balanced", "deep"],
                                    },
                                    "model": string(),
                                    "files": {
                                        "type": "array",
                                        "maxItems": DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE,
                                        "items": {"type": "string", "format": "binary"},
                                        "description": (
                                            "Files validated and linked to the user message "
                                            "within the same unit of work."
                                        ),
                                    },
                                    "attachment_kinds": {
                                        "type": "array",
                                        "maxItems": DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE,
                                        "items": {
                                            "type": "string",
                                            "enum": ["document", "image", "audio"],
                                        },
                                    },
                                },
                            }
                        },
                    },
                },
                "responses": {
                    "201": json_response("SendMessageResponse"),
                    "400": json_response("ErrorResponse"),
                    "413": json_response("ErrorResponse"),
                    "429": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/chat/messages/{assistant_message_id}/stream": {
            "get": {
                "tags": ["Chat"],
                "summary": "Stream assistant message via Server-Sent Events",
                "parameters": [path_param("assistant_message_id", "Assistant message id")],
                "responses": {
                    "200": {
                        "description": "SSE token stream",
                        "content": {"text/event-stream": {"schema": {"type": "string"}}},
                    },
                    "404": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/chat/messages/{assistant_message_id}/feedback": {
            "post": {
                "tags": ["Chat"],
                "summary": "Record LangSmith feedback for an assistant message",
                "parameters": [path_param("assistant_message_id", "Assistant message id")],
                "requestBody": json_body("FeedbackRequest"),
                "responses": {
                    "202": json_response("FeedbackResponse"),
                    "400": json_response("ErrorResponse"),
                    "404": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/attachments": {
            "post": {
                "tags": ["Attachments"],
                "summary": "Upload an attachment",
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["session_id", "file"],
                                "properties": {
                                    "session_id": {"type": "string"},
                                    "kind": {
                                        "type": "string",
                                        "enum": ["document", "image", "audio"],
                                    },
                                    "file": {
                                        "type": "string",
                                        "format": "binary",
                                        "description": (
                                            "Allowlisted document, image or audio. The server "
                                            "validates size, name, MIME and signature/content "
                                            "before moving it out of quarantine."
                                        ),
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "201": json_response("Attachment"),
                    "400": json_response("ErrorResponse"),
                    "413": json_response("ErrorResponse"),
                },
            }
        },
        "/api/v1/attachments/{attachment_id}": {
            "get": {
                "tags": ["Attachments"],
                "summary": "Download an attachment",
                "parameters": [path_param("attachment_id", "Attachment id")],
                "responses": {
                    "200": {"description": "Attachment bytes"},
                    "404": json_response("ErrorResponse"),
                },
            },
            "delete": {
                "tags": ["Attachments"],
                "summary": "Delete an attachment that was never linked to a message",
                "description": (
                    "Cleanup for the upload-then-send flow: removes an attachment "
                    "still awaiting a message. Rejects attachments already attached "
                    "to a message — use this only to compensate a failed send."
                ),
                "parameters": [path_param("attachment_id", "Attachment id")],
                "responses": {
                    "204": {"description": "Attachment deleted"},
                    "400": json_response("ErrorResponse"),
                    "404": json_response("ErrorResponse"),
                },
            },
        },
        "/api/v1/semantic-search": {
            "post": {
                "tags": ["Semantic Search"],
                "summary": "Run semantic search over local Python documents",
                "requestBody": json_body("SemanticSearchRequest"),
                "responses": {
                    "200": json_response("SemanticSearchResponse"),
                    "400": json_response("ErrorResponse"),
                },
            }
        },
    }


def components() -> dict[str, object]:
    return {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": (
                    "Shared API_KEY configured by the operator. Optional only when "
                    "the backend runs locally with API_KEY unset."
                ),
            }
        },
        "schemas": {
            "HealthResponse": object_schema(
                {"status": string(), "service": string(), "request_id": nullable_string()}
            ),
            "Book": object_schema(
                {
                    "id": string(),
                    "title": string(),
                    "category": string(),
                    "author": string(),
                    "publication_date": string("date"),
                    "publication_year": integer(),
                    "summary": string(),
                    "created_at": string("date-time"),
                }
            ),
            "CreateBookRequest": object_schema(
                {
                    "title": string(),
                    "category": string(),
                    "author": string(),
                    "publication_year": integer(),
                    "publication_date": string("date"),
                    "summary": string(),
                },
                required=["title", "author", "summary"],
            ),
            "ImportBookResponse": object_schema(
                {
                    "book": ref("Book"),
                    "extracted": object_schema(
                        {
                            "title": string(),
                            "category": string(),
                            "author": string(),
                            "publication_year": integer(),
                            "summary": string(),
                        }
                    ),
                }
            ),
            "ChatSession": object_schema(
                {
                    "id": string(),
                    "title": string(),
                    "pinned": {"type": "boolean"},
                    "pinned_at": nullable_string("date-time"),
                    "created_at": string("date-time"),
                    "updated_at": string("date-time"),
                }
            ),
            "CreateChatSessionRequest": object_schema({"title": string()}, required=[]),
            "UpdateChatSessionRequest": object_schema(
                {"pinned": {"type": "boolean"}},
                required=["pinned"],
            ),
            "Attachment": object_schema(
                {
                    "id": string(),
                    "filename": string(),
                    "mime_type": string(),
                    "size": integer(),
                    "kind": {"type": "string", "enum": ["document", "image", "audio"]},
                    "url": string(),
                    "created_at": string("date-time"),
                }
            ),
            "ChatMessage": object_schema(
                {
                    "id": string(),
                    "session_id": string(),
                    "role": {"type": "string", "enum": ["user", "assistant", "system"]},
                    "content": string(),
                    "thinking_mode": {
                        "type": "string",
                        "enum": ["fast", "balanced", "deep"],
                        "nullable": True,
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "streaming", "completed", "failed"],
                    },
                    "trace_id": nullable_string(),
                    "attachments": {"type": "array", "items": ref("Attachment")},
                    "created_at": string("date-time"),
                }
            ),
            "SendMessageRequest": object_schema(
                {
                    "session_id": string(),
                    "content": string(),
                    "thinking_mode": {
                        "type": "string",
                        "enum": ["fast", "balanced", "deep"],
                    },
                    "attachment_ids": {"type": "array", "items": string()},
                    "model": string(),
                },
                required=["session_id"],
            ),
            "SendMessageResponse": object_schema(
                {
                    "user_message_id": string(),
                    "assistant_message_id": string(),
                    "status": string(),
                    "assistant_message": ref("ChatMessage"),
                }
            ),
            "FeedbackRequest": object_schema(
                {
                    "score": {"type": "number", "minimum": -1, "maximum": 1},
                    "key": string(),
                    "comment": string(),
                },
                required=["score"],
            ),
            "FeedbackResponse": object_schema(
                {"recorded": {"type": "boolean"}, "reason": string(), "feedback_id": string()},
                required=["recorded"],
            ),
            "SemanticSearchRequest": object_schema(
                {"query": string(), "k": integer()}, required=["query"]
            ),
            "SemanticSearchResponse": object_schema(
                {
                    "results": {
                        "type": "array",
                        "items": object_schema(
                            {
                                "document_id": string(),
                                "title": string(),
                                "score": {"type": "number"},
                                "excerpt": string(),
                            }
                        ),
                    }
                }
            ),
            "ErrorResponse": object_schema(
                {
                    "error": object_schema(
                        {
                            "code": string(),
                            "message": string(),
                            "details": {
                                "type": "object",
                                "additionalProperties": True,
                            },
                        }
                    ),
                    "request_id": nullable_string(),
                }
            ),
        },
    }


def ref(schema_name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{schema_name}"}


def object_schema(
    properties: dict[str, object],
    required: list[str] | None = None,
) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties.keys()),
    }


def string(format_: str | None = None) -> dict[str, str]:
    schema = {"type": "string"}
    if format_:
        schema["format"] = format_
    return schema


def nullable_string(format_: str | None = None) -> dict[str, object]:
    schema: dict[str, object] = {"type": "string", "nullable": True}
    if format_:
        schema["format"] = format_
    return schema


def integer() -> dict[str, str]:
    return {"type": "integer"}


def json_body(schema_name: str, required: bool = True) -> dict[str, object]:
    return {
        "required": required,
        "content": {"application/json": {"schema": ref(schema_name)}},
    }


def json_response(schema_name: str) -> dict[str, object]:
    return {
        "description": "JSON response",
        "content": {"application/json": {"schema": ref(schema_name)}},
    }


def array_response(schema_name: str) -> dict[str, object]:
    return {
        "description": "JSON array response",
        "content": {"application/json": {"schema": {"type": "array", "items": ref(schema_name)}}},
    }


def query_param(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "in": "query",
        "required": False,
        "description": description,
        "schema": string(),
    }


def pagination_params() -> list[dict[str, object]]:
    return [
        {
            "name": "limit",
            "in": "query",
            "required": False,
            "description": "Max items to return (1-200). Omit for the full unbounded list.",
            "schema": integer(),
        },
        {
            "name": "offset",
            "in": "query",
            "required": False,
            "description": "Items to skip before collecting results. Omit to start at 0.",
            "schema": integer(),
        },
    ]


def path_param(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "description": description,
        "schema": string(),
    }


@docs_bp.get("/openapi.json")
def openapi_json():
    return jsonify(openapi_spec())


@docs_bp.get("/docs")
def docs():
    return """
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MindSight AI API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis],
      });
    </script>
  </body>
</html>
"""
