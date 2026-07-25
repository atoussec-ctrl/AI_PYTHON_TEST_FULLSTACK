"""Contract tests for the atomic multipart chat path.

The browser must be able to send message fields and files in one request.  A
failure anywhere before the database commit must leave neither rows nor files
behind; otherwise the old upload-then-send orphan window has merely moved.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.extensions import db
from app.models import Attachment, ChatMessage
from app.services.chat import ChatService


def _session_id(client) -> str:
    return client.post("/api/v1/chat/sessions", json={}).get_json()["id"]


def test_multipart_message_persists_and_links_files_in_one_request(client, app):
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Use o anexo como contexto",
            "thinking_mode": "balanced",
            "files": [(BytesIO(b"contexto atomico"), "contexto.txt")],
            "attachment_kinds": ["document"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages").get_json()
    user_message = next(message for message in messages if message["role"] == "user")
    assert [item["filename"] for item in user_message["attachments"]] == ["contexto.txt"]

    with app.app_context():
        attachment = db.session.query(Attachment).one()
        assert attachment.message_id == user_message["id"]
        assert Path(attachment.storage_path).read_text(encoding="utf-8") == "contexto atomico"


def test_multipart_batch_failure_rolls_back_every_file_and_row(client, app):
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Este lote deve falhar",
            "files": [
                (BytesIO(b"primeiro valido"), "primeiro.txt"),
                (BytesIO(b"nao e uma imagem"), "disfarcado.png"),
            ],
            "attachment_kinds": ["document", "image"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    with app.app_context():
        assert db.session.query(Attachment).count() == 0
        assert db.session.query(ChatMessage).count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).glob("*")) == []


def test_multipart_message_failure_compensates_staged_files(client, app, monkeypatch):
    session_id = _session_id(client)

    def fail_ask(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(ChatService, "ask", fail_ask)

    with pytest.raises(RuntimeError, match="database unavailable"):
        client.post(
            "/api/v1/chat/messages",
            data={
                "session_id": session_id,
                "content": "Falhe depois do upload",
                "files": [(BytesIO(b"temporario"), "temporario.txt")],
                "attachment_kinds": ["document"],
            },
            content_type="multipart/form-data",
        )

    with app.app_context():
        assert db.session.query(Attachment).count() == 0
        assert db.session.query(ChatMessage).count() == 0
    assert list(Path(app.config["UPLOAD_DIR"]).iterdir()) == []


def test_multipart_message_rejects_more_files_than_configured(client, app):
    app.config["MAX_ATTACHMENTS_PER_MESSAGE"] = 2
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Muitos anexos",
            "files": [
                (BytesIO(b"um"), "um.txt"),
                (BytesIO(b"dois"), "dois.txt"),
                (BytesIO(b"tres"), "tres.txt"),
            ],
            "attachment_kinds": ["document", "document", "document"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "files"
    with app.app_context():
        assert db.session.query(Attachment).count() == 0


def test_multipart_message_rejects_mismatched_file_kind_lists(client, app):
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Metadados incompletos",
            "files": [
                (BytesIO(b"um"), "um.txt"),
                (BytesIO(b"dois"), "dois.txt"),
            ],
            "attachment_kinds": ["document"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "attachment_kinds"
    assert list(Path(app.config["UPLOAD_DIR"]).glob("*")) == []


def test_multipart_message_rejects_files_combined_with_preuploaded_ids(client):
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Fluxos ambiguos",
            "attachment_ids": ["att_existing"],
            "files": [(BytesIO(b"novo"), "novo.txt")],
            "attachment_kinds": ["document"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "attachments"


def test_multipart_message_has_its_own_bounded_request_limit(client, app):
    app.config["MAX_MESSAGE_UPLOAD_SIZE_MB"] = 1
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        data={
            "session_id": session_id,
            "content": "Grande demais",
            "files": [(BytesIO(b"x" * (1024 * 1024 + 1)), "grande.txt")],
            "attachment_kinds": ["document"],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "REQUEST_ENTITY_TOO_LARGE"


def test_json_message_rejects_more_preuploaded_ids_than_configured(client, app):
    app.config["MAX_ATTACHMENTS_PER_MESSAGE"] = 2
    session_id = _session_id(client)

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "Muitos IDs",
            "attachment_ids": ["att_1", "att_2", "att_3"],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "attachment_ids"
