"""Unit tests closing coverage gaps in app.services.uploads.

Exercises read_attachment_text and infer_kind directly (no HTTP layer) since
these are pure data-transformation branches that don't need a full request.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Attachment
from app.services.uploads import UploadService, infer_kind, read_attachment_text

pypdf = pytest.importorskip("pypdf")


def _attachment(**overrides) -> Attachment:
    defaults: dict[str, object] = {
        "session_id": "session-1",
        "filename": "nota.txt",
        "mime_type": "text/plain",
        "size": 10,
        "kind": "document",
        "storage_path": "/nao-existe/nota.txt",
    }
    defaults.update(overrides)
    return Attachment(**defaults)


def test_read_attachment_text_returns_none_for_non_document_kind():
    attachment = _attachment(kind="image", filename="foto.png")

    assert read_attachment_text(attachment) is None


def test_read_attachment_text_returns_none_for_non_extractable_extension():
    attachment = _attachment(kind="document", filename="planilha.csv")

    assert read_attachment_text(attachment) is None


def test_read_attachment_text_returns_none_when_file_missing_on_disk():
    attachment = _attachment(storage_path="/caminho/que/nao/existe/nota.txt")

    assert read_attachment_text(attachment) is None


def test_read_attachment_text_returns_none_for_blank_file(tmp_path):
    path = tmp_path / "vazio.txt"
    path.write_text("   \n  ", encoding="utf-8")

    assert read_attachment_text(_attachment(storage_path=str(path))) is None


def test_read_attachment_text_reads_plain_text_file(tmp_path):
    path = tmp_path / "nota.txt"
    path.write_text("conteudo relevante do anexo", encoding="utf-8")

    text = read_attachment_text(_attachment(storage_path=str(path)))

    assert text == "conteudo relevante do anexo"


def test_read_attachment_text_reads_pdf_file(tmp_path):
    from tests.test_pdf_extraction import _handcrafted_pdf

    pdf_bytes = _handcrafted_pdf(["Ola mundo em PDF"])
    path = tmp_path / "doc.pdf"
    path.write_bytes(pdf_bytes)

    text = read_attachment_text(_attachment(storage_path=str(path), filename="doc.pdf"))

    assert text is not None
    assert "Ola mundo" in text


def test_infer_kind_falls_back_to_mime_prefix_when_extension_unknown():
    assert infer_kind("arquivo-sem-extensao", "image/png") == "image"


def test_infer_kind_returns_none_when_nothing_matches():
    assert infer_kind("arquivo.xyz", "application/x-unknown") is None


def test_save_rolls_back_database_and_file_when_commit_fails(client, app, monkeypatch):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    def fail_commit():
        raise RuntimeError("database unavailable")

    with app.app_context():
        monkeypatch.setattr(db.session, "commit", fail_commit)
        file = FileStorage(
            stream=BytesIO(b"safe content"),
            filename="notes.txt",
            content_type="text/plain",
        )

        with pytest.raises(RuntimeError, match="database unavailable"):
            UploadService().save(file=file, session_id=session_id)

        assert db.session.query(Attachment).count() == 0
        assert list(Path(app.config["UPLOAD_DIR"]).glob("*")) == []
