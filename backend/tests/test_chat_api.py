def test_create_session_send_message_and_stream(client):
    session_response = client.post("/api/v1/chat/sessions", json={"title": "Listas"})
    assert session_response.status_code == 201
    session_id = session_response.get_json()["id"]

    message_response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "Como criar uma lista em Python?",
            "thinking_mode": "balanced",
        },
    )

    assert message_response.status_code == 201
    payload = message_response.get_json()
    assert payload["status"] == "completed"
    assert "lista" in payload["assistant_message"]["content"].lower()
    assert "trace_id" in payload["assistant_message"]

    messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages").get_json()
    assert [message["role"] for message in messages] == ["user", "assistant"]

    stream = client.get(f"/api/v1/chat/messages/{payload['assistant_message_id']}/stream")
    assert stream.status_code == 200
    assert b"event: token" in stream.data
    assert b"event: done" in stream.data
    assert stream.headers["Cache-Control"] == "no-cache"
    assert stream.headers["X-Accel-Buffering"] == "no"

    feedback = client.post(
        f"/api/v1/chat/messages/{payload['assistant_message_id']}/feedback",
        json={"score": 1, "comment": "boa resposta"},
    )
    assert feedback.status_code == 202
    assert feedback.get_json()["recorded"] is False


def test_create_session_treats_null_title_as_the_default(client):
    response = client.post("/api/v1/chat/sessions", json={"title": None})

    assert response.status_code == 201
    assert response.get_json()["title"] == "Nova conversa"


def test_chat_rejects_non_object_json_body(client):
    response = client.post("/api/v1/chat/messages", json=["invalid"])

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "body"


def test_chat_rejects_non_string_content(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": {"unexpected": "object"}},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "content"


def test_chat_rejects_attachment_ids_that_are_not_a_list(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "oi", "attachment_ids": "att_1"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "attachment_ids"


def test_chat_rejects_invalid_thinking_mode(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "Oi",
            "thinking_mode": "slow",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_rejects_message_over_max_length(client, app):
    app.config["CHAT_MAX_MESSAGE_CHARS"] = 20
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "x" * 21},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "content"


def test_chat_accepts_message_at_max_length(client, app):
    app.config["CHAT_MAX_MESSAGE_CHARS"] = 20
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "x" * 20},
    )

    assert response.status_code == 201


def test_chat_rejects_empty_content_without_attachments(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages", json={"session_id": session_id, "content": "   "}
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "content"


def test_create_message_returns_404_for_missing_session(client):
    response = client.post(
        "/api/v1/chat/messages",
        json={"session_id": "sessao_inexistente", "content": "Oi"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_create_message_requires_session_id(client):
    response = client.post("/api/v1/chat/messages", json={"content": "Oi"})

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "session_id"


def test_create_message_accepts_multipart_form_data(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/chat/messages",
        data={"session_id": session_id, "content": "Oi via formulário"},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json()["status"] == "completed"


def test_stream_returns_404_for_missing_message(client):
    response = client.get("/api/v1/chat/messages/mensagem_inexistente/stream")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_feedback_returns_404_for_missing_message(client):
    response = client.post("/api/v1/chat/messages/mensagem_inexistente/feedback", json={"score": 1})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_feedback_rejects_non_numeric_score(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    message = client.post(
        "/api/v1/chat/messages", json={"session_id": session_id, "content": "oi"}
    ).get_json()

    response = client.post(
        f"/api/v1/chat/messages/{message['assistant_message_id']}/feedback",
        json={"score": "ótimo"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "score"


def test_feedback_rejects_score_out_of_range(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    message = client.post(
        "/api/v1/chat/messages", json={"session_id": session_id, "content": "oi"}
    ).get_json()

    response = client.post(
        f"/api/v1/chat/messages/{message['assistant_message_id']}/feedback",
        json={"score": 2},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "score"


def test_stream_emits_error_event_for_failed_message(client, app):
    from app.extensions import db
    from app.repositories import ChatRepository

    with app.app_context():
        repository = ChatRepository()
        session = repository.create_session("Falha")
        assistant_message = repository.create_message(
            session_id=session.id,
            role="assistant",
            content="Não foi possível gerar a resposta da IA agora.",
            status="failed",
        )
        message_id = assistant_message.id
        db.session.commit()  # repositories only flush now — the caller owns the commit

    stream = client.get(f"/api/v1/chat/messages/{message_id}/stream")

    assert stream.status_code == 200
    assert b"event: error" in stream.data
    assert b"event: token" not in stream.data
    assert b"event: done" not in stream.data
