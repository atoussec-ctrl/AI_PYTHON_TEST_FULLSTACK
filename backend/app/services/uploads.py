"""Upload validation and storage."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.datastructures import FileStorage

from app.errors import NotFoundError, ValidationError
from app.extensions import db
from app.models import Attachment
from app.repositories import ChatRepository
from app.services.file_security import (
    ALLOWED_EXTENSIONS,
    copy_stream_limited,
    extension_for,
    safe_filename,
    validate_declared_mime,
    validate_file_path,
)

ALLOWED_MIME_PREFIXES = {
    "document": ("text/", "application/json", "application/pdf"),
    "image": ("image/png", "image/jpeg", "image/webp"),
    "audio": ("audio/", "video/webm"),
}

# Extensões de documento legíveis como texto puro.
TEXT_EXTRACTABLE_EXTENSIONS = {"txt", "md", "py", "json"}
MAX_ATTACHMENT_TEXT_CHARS = 4000

logger = logging.getLogger(__name__)


def read_attachment_text(attachment: Attachment) -> str | None:
    """Return the attachment's text content for AI context, when extractable."""
    if attachment.kind != "document":
        return None
    extension = extension_for(attachment.filename)
    try:
        if extension == "pdf":
            from app.services.book_import import extract_pdf_text

            raw = Path(attachment.storage_path).read_bytes()
            text = extract_pdf_text(raw)
        elif extension in TEXT_EXTRACTABLE_EXTENSIONS:
            text = Path(attachment.storage_path).read_text(encoding="utf-8", errors="ignore")
        else:
            return None
    except OSError:
        return None
    text = text.strip()
    if not text:
        return None
    return text[:MAX_ATTACHMENT_TEXT_CHARS]


def infer_kind(filename: str, mime_type: str) -> str | None:
    ext = extension_for(filename)
    for kind, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return kind
    for kind, prefixes in ALLOWED_MIME_PREFIXES.items():
        if mime_type and any(mime_type.startswith(prefix) for prefix in prefixes):
            return kind
    return None


class UploadService:
    def __init__(self, chat_repository: ChatRepository | None = None) -> None:
        self.chat_repository = chat_repository or ChatRepository()

    def save(
        self, *, file: FileStorage | None, session_id: str, kind: str | None = None
    ) -> Attachment:
        """Persist one standalone upload and own its database transaction."""
        attachment: Attachment | None = None
        try:
            attachment = self.stage(file=file, session_id=session_id, kind=kind)
            db.session.commit()
        except Exception:
            db.session.rollback()
            if attachment is not None:
                self.remove_storage_files([attachment])
            raise
        return attachment

    def stage(
        self, *, file: FileStorage | None, session_id: str, kind: str | None = None
    ) -> Attachment:
        """Validate, store and flush one upload without committing it.

        This is the composable half of the use case.  Callers that combine an
        upload with other database writes own the final commit and must call
        :meth:`discard_staged` if a later operation fails.
        """
        session = self.chat_repository.get_session(session_id)
        if not session:
            raise NotFoundError("Sessão de chat não encontrada.")
        try:
            return self._stage_file(file=file, session_id=session_id, kind=kind)
        except Exception:
            db.session.rollback()
            raise

    def stage_many(
        self,
        *,
        files: list[FileStorage],
        session_id: str,
        kinds: list[str | None],
    ) -> list[Attachment]:
        """Stage a bounded batch in the caller's current unit of work."""
        if not self.chat_repository.get_session(session_id):
            raise NotFoundError("Sessão de chat não encontrada.")
        max_files = int(current_app.config["MAX_ATTACHMENTS_PER_MESSAGE"])
        if len(files) > max_files:
            raise ValidationError(
                f"Uma mensagem aceita no máximo {max_files} anexos.", field="files"
            )
        if len(kinds) != len(files):
            raise ValidationError(
                "Cada arquivo deve possuir um attachment_kind correspondente.",
                field="attachment_kinds",
            )

        staged: list[Attachment] = []
        try:
            for file, kind in zip(files, kinds, strict=True):
                staged.append(self._stage_file(file=file, session_id=session_id, kind=kind))
        except Exception:
            db.session.rollback()
            self.remove_storage_files(staged)
            raise
        return staged

    def _stage_file(
        self, *, file: FileStorage | None, session_id: str, kind: str | None
    ) -> Attachment:
        if not file or not file.filename:
            raise ValidationError("Campo file é obrigatório.", field="file")

        original_name = safe_filename(
            file.filename,
            max_chars=int(current_app.config["MAX_UPLOAD_FILENAME_CHARS"]),
        )
        declared_mime = file.mimetype or "application/octet-stream"
        detected_kind = kind or infer_kind(original_name, declared_mime)
        if detected_kind not in ALLOWED_EXTENSIONS:
            raise ValidationError("Tipo de anexo inválido.", field="kind")

        ext = extension_for(original_name)
        if ext not in ALLOWED_EXTENSIONS[detected_kind]:
            raise ValidationError("Extensão de arquivo não permitida.", field="file")
        validate_declared_mime(ext, declared_mime)

        max_bytes = int(current_app.config["MAX_UPLOAD_SIZE_MB"]) * 1024 * 1024
        upload_dir = Path(current_app.config["UPLOAD_DIR"])
        upload_dir.mkdir(parents=True, exist_ok=True)

        identifier = uuid4().hex
        storage_name = f"{identifier}.{ext}"
        storage_path = upload_dir / storage_name
        quarantine_path = upload_dir / f".{identifier}.uploading"
        try:
            size = copy_stream_limited(file.stream, quarantine_path, max_bytes)
            mime_type = validate_file_path(quarantine_path, ext)
            quarantine_path.replace(storage_path)
        except Exception:
            quarantine_path.unlink(missing_ok=True)
            storage_path.unlink(missing_ok=True)
            raise

        attachment = Attachment(
            session_id=session_id,
            filename=original_name,
            mime_type=mime_type,
            size=size,
            kind=detected_kind,
            storage_path=str(storage_path),
        )
        try:
            db.session.add(attachment)
            db.session.flush()
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise
        return attachment

    def discard_staged(self, attachments: list[Attachment]) -> None:
        """Rollback database state and compensate files staged in this request."""
        db.session.rollback()
        self.remove_storage_files(attachments)

    @staticmethod
    def remove_storage_files(attachments: list[Attachment]) -> None:
        for attachment in attachments:
            try:
                Path(attachment.storage_path).unlink(missing_ok=True)
            except OSError:
                logger.warning(
                    "Não foi possível remover anexo compensado %s",
                    attachment.storage_path,
                    exc_info=True,
                )

    def delete_unlinked(self, attachment_id: str) -> None:
        """Remove an attachment that was uploaded but never linked to a message.

        Backstop for the two-request upload-then-send flow: if sending the
        message fails (network, validation, or a partial multi-file upload
        batch), the client calls this to clean up what it just uploaded
        instead of leaving orphaned rows and files behind. Refuses to touch
        an attachment that's already part of a real conversation.
        """
        attachment = self.chat_repository.get_attachment(attachment_id)
        if not attachment:
            raise NotFoundError("Anexo não encontrado.")
        if attachment.message_id is not None:
            raise ValidationError("Anexo já vinculado a uma mensagem.", field="attachment_id")

        storage_path = Path(attachment.storage_path)
        db.session.delete(attachment)
        db.session.commit()
        storage_path.unlink(missing_ok=True)
