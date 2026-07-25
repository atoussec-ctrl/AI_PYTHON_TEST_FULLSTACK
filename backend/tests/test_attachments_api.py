from io import BytesIO
from pathlib import Path

from app.extensions import db
from app.models import Attachment


def test_upload_attachment_validates_and_hides_storage_path(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "document",
            "file": (BytesIO(b"print('hello')"), "example.py"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["kind"] == "document"
    assert payload["filename"] == "example.py"
    assert "storage_path" not in payload
    assert payload["url"].startswith("/api/v1/attachments/")


def test_upload_rejects_dangerous_extension(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "document",
            "file": (BytesIO(b"bad"), "payload.exe"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_upload_rejects_missing_file(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "file"


def test_upload_rejects_extension_mismatched_with_declared_kind(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "image",
            "file": (BytesIO(b"nao e uma imagem"), "notas.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "file"


def test_upload_rejects_undetectable_kind(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "file": (BytesIO(b"binario desconhecido"), "arquivo.xyz"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "kind"


def test_upload_rejects_missing_session_with_404(client):
    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": "sessao_inexistente",
            "kind": "document",
            "file": (BytesIO(b"conteudo"), "notas.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_upload_rejects_file_larger_than_configured_limit(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    app.config["MAX_UPLOAD_SIZE_MB"] = 0  # qualquer arquivo não vazio excede 0MB

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "document",
            "file": (BytesIO(b"conteudo maior que zero bytes"), "grande.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "file"
    assert list(Path(app.config["UPLOAD_DIR"]).glob("*")) == []


def test_upload_returns_structured_413_when_http_body_exceeds_global_limit(client, app):
    app.config["MAX_CONTENT_LENGTH"] = 1

    response = client.post(
        "/api/v1/attachments",
        data={"session_id": "unused", "file": (BytesIO(b"content"), "notes.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    body = response.get_json()
    assert body["error"]["code"] == "REQUEST_ENTITY_TOO_LARGE"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_upload_rejects_a_disguised_image_and_removes_quarantine(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "image",
            "file": (BytesIO(b"plain text pretending to be an image"), "fake.png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "file"
    assert list(Path(app.config["UPLOAD_DIR"]).glob("*")) == []


def test_upload_rejects_declared_mime_mismatched_with_extension(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "kind": "document",
            "file": (BytesIO(b"content"), "notes.txt", "image/png"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "Content-Type" in response.get_json()["error"]["message"]
    assert not Path(app.config["UPLOAD_DIR"]).exists()


def test_upload_uses_server_canonical_mime_for_generic_client_metadata(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "file": (BytesIO(b"content"), "notes.txt", "application/octet-stream"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    assert response.get_json()["mime_type"] == "text/plain"


def test_upload_rejects_an_oversized_filename_before_writing(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    response = client.post(
        "/api/v1/attachments",
        data={
            "session_id": session_id,
            "file": (BytesIO(b"content"), f"{'a' * 181}.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "excede" in response.get_json()["error"]["message"]
    assert not Path(app.config["UPLOAD_DIR"]).exists()


def test_get_attachment_downloads_the_uploaded_file(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    upload = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id, "file": (BytesIO(b"print('hello')"), "example.py")},
        content_type="multipart/form-data",
    )
    attachment_id = upload.get_json()["id"]

    response = client.get(f"/api/v1/attachments/{attachment_id}")

    assert response.status_code == 200
    assert response.data == b"print('hello')"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "example.py" in response.headers["Content-Disposition"]


def test_get_attachment_returns_404_when_record_missing(client):
    response = client.get("/api/v1/attachments/anexo_inexistente")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Anexo não encontrado."


def test_get_attachment_returns_404_when_file_missing_from_disk(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    upload = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id, "file": (BytesIO(b"conteudo"), "nota.txt")},
        content_type="multipart/form-data",
    )
    attachment_id = upload.get_json()["id"]

    with app.app_context():
        attachment = db.session.get(Attachment, attachment_id)
        Path(attachment.storage_path).unlink()

    response = client.get(f"/api/v1/attachments/{attachment_id}")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Arquivo do anexo não encontrado."


# ── DELETE /attachments/<id> — cleanup de anexos órfãos ──
#
# Compensa o risco documentado no roadmap: o frontend faz upload de anexo e
# envio de mensagem em duas chamadas HTTP separadas; se a segunda falhar
# (rede, validação, ou até uma falha no meio de um lote com vários anexos),
# os anexos já enviados ficariam órfãos em disco e no banco sem este endpoint.


def test_delete_unlinked_attachment_removes_record_and_file(client, app):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    upload = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id, "file": (BytesIO(b"conteudo"), "nota.txt")},
        content_type="multipart/form-data",
    )
    attachment_id = upload.get_json()["id"]
    with app.app_context():
        storage_path = Path(db.session.get(Attachment, attachment_id).storage_path)
    assert storage_path.exists()

    response = client.delete(f"/api/v1/attachments/{attachment_id}")

    assert response.status_code == 204
    with app.app_context():
        assert db.session.get(Attachment, attachment_id) is None
    assert not storage_path.exists()


def test_delete_linked_attachment_is_rejected(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    upload = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id, "file": (BytesIO(b"conteudo"), "nota.txt")},
        content_type="multipart/form-data",
    )
    attachment_id = upload.get_json()["id"]
    client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "oi", "attachment_ids": [attachment_id]},
    )

    response = client.delete(f"/api/v1/attachments/{attachment_id}")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_nonexistent_attachment_returns_404(client):
    response = client.delete("/api/v1/attachments/anexo_inexistente")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"
