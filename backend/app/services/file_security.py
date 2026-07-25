"""Defense-in-depth validation for user-controlled files.

Extension and Content-Type checks are useful UX filters, but neither proves
what a file contains.  This module keeps the policy in one place and adds a
small signature/content check before a file becomes a persisted attachment or
is handed to a parser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import BinaryIO

from werkzeug.utils import secure_filename

from app.errors import ValidationError

ALLOWED_EXTENSIONS: dict[str, frozenset[str]] = {
    "document": frozenset({"txt", "md", "py", "json", "pdf"}),
    "image": frozenset({"png", "jpg", "jpeg", "webp"}),
    "audio": frozenset({"webm", "wav", "mp3"}),
}

TEXT_EXTENSIONS = frozenset({"txt", "md", "py", "json"})
DEFAULT_MAX_FILENAME_CHARS = 180
COPY_CHUNK_BYTES = 64 * 1024

CANONICAL_MIME_BY_EXTENSION = {
    "txt": "text/plain",
    "md": "text/markdown",
    "py": "text/x-python",
    "json": "application/json",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "webm": "video/webm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
}

DECLARED_MIME_BY_EXTENSION: dict[str, frozenset[str]] = {
    "txt": frozenset({"text/plain"}),
    "md": frozenset({"text/markdown", "text/plain"}),
    "py": frozenset({"text/x-python", "text/plain"}),
    "json": frozenset({"application/json", "text/json", "text/plain"}),
    "pdf": frozenset({"application/pdf"}),
    "png": frozenset({"image/png"}),
    "jpg": frozenset({"image/jpeg"}),
    "jpeg": frozenset({"image/jpeg"}),
    "webp": frozenset({"image/webp"}),
    "webm": frozenset({"audio/webm", "video/webm"}),
    "wav": frozenset({"audio/wav", "audio/x-wav", "audio/wave"}),
    "mp3": frozenset({"audio/mpeg", "audio/mp3"}),
}


def extension_for(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def safe_filename(filename: str, *, max_chars: int = DEFAULT_MAX_FILENAME_CHARS) -> str:
    """Normalize an untrusted display name and enforce the database/path bound."""
    if len(filename) > max_chars:
        raise ValidationError(
            f"Nome do arquivo excede o limite de {max_chars} caracteres.", field="file"
        )
    normalized = secure_filename(filename)
    if not normalized or len(normalized) > max_chars:
        raise ValidationError("Nome de arquivo inválido.", field="file")
    return normalized


def kind_for_extension(extension: str) -> str | None:
    for kind, extensions in ALLOWED_EXTENSIONS.items():
        if extension in extensions:
            return kind
    return None


def canonical_mime_type(extension: str) -> str:
    try:
        return CANONICAL_MIME_BY_EXTENSION[extension]
    except KeyError as exc:
        raise ValidationError("Extensão de arquivo não permitida.", field="file") from exc


def validate_declared_mime(extension: str, declared_mime: str | None) -> None:
    """Reject obvious metadata mismatches without trusting MIME as proof.

    ``application/octet-stream`` is accepted because browsers and CLI clients
    legitimately use it when they cannot infer a type.  Raw content is always
    checked separately.
    """
    normalized = (declared_mime or "").partition(";")[0].strip().lower()
    if not normalized or normalized == "application/octet-stream":
        return
    if normalized not in DECLARED_MIME_BY_EXTENSION.get(extension, frozenset()):
        raise ValidationError("Content-Type não corresponde à extensão do arquivo.", field="file")


def copy_stream_limited(source: BinaryIO, destination: Path, max_bytes: int) -> int:
    """Copy a stream without ever accepting more than ``max_bytes``."""
    if max_bytes < 0:
        raise ValueError("max_bytes deve ser maior ou igual a zero")
    size = 0
    with destination.open("xb") as target:
        while chunk := source.read(COPY_CHUNK_BYTES):
            size += len(chunk)
            if size > max_bytes:
                raise ValidationError("Arquivo excede o tamanho máximo permitido.", field="file")
            target.write(chunk)
    return size


def read_stream_limited(source: BinaryIO, max_bytes: int) -> bytes:
    """Read at most a bounded payload into memory and reject overflow."""
    if max_bytes < 0:
        raise ValueError("max_bytes deve ser maior ou igual a zero")
    chunks: list[bytes] = []
    size = 0
    while size <= max_bytes:
        # Binary streams may legally return a short read before EOF. Keep
        # reading, but never hold more than max_bytes + one probe byte.
        chunk = source.read(min(COPY_CHUNK_BYTES, max_bytes - size + 1))
        if not chunk:
            break
        size += len(chunk)
        if size > max_bytes:
            raise ValidationError("Arquivo excede o tamanho máximo permitido.", field="file")
        chunks.append(chunk)
    return b"".join(chunks)


def validate_file_path(path: Path, extension: str) -> str:
    """Validate a bounded file in quarantine and return its canonical MIME."""
    size = path.stat().st_size
    if size == 0:
        raise ValidationError("Arquivo vazio não é permitido.", field="file")

    if extension in TEXT_EXTENSIONS:
        validate_file_bytes(path.read_bytes(), extension)
        return canonical_mime_type(extension)

    with path.open("rb") as handle:
        head = handle.read(32)
        handle.seek(max(0, size - 1024))
        tail = handle.read(1024)
    _validate_binary_signature(extension, head, tail)
    return canonical_mime_type(extension)


def validate_file_bytes(raw: bytes, extension: str) -> str:
    """Validate in-memory content, used by the book import path."""
    if not raw:
        raise ValidationError("Arquivo vazio não é permitido.", field="file")
    if extension in TEXT_EXTENSIONS:
        _validate_text(raw, extension)
    else:
        _validate_binary_signature(extension, raw[:32], raw[-1024:])
    return canonical_mime_type(extension)


def _validate_text(raw: bytes, extension: str) -> None:
    if b"\x00" in raw:
        raise ValidationError("Arquivo de texto contém bytes nulos.", field="file")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Arquivo de texto deve usar UTF-8.", field="file") from exc
    if extension == "json":
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValidationError("Arquivo JSON inválido.", field="file") from exc


def _validate_binary_signature(extension: str, head: bytes, tail: bytes) -> None:
    valid = False
    if extension == "pdf":
        valid = head.startswith(b"%PDF-") and b"%%EOF" in tail
    elif extension == "png":
        valid = head.startswith(b"\x89PNG\r\n\x1a\n") and head[12:16] == b"IHDR"
    elif extension in {"jpg", "jpeg"}:
        valid = head.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in tail
    elif extension == "webp":
        valid = head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    elif extension == "wav":
        valid = head.startswith(b"RIFF") and head[8:12] == b"WAVE"
    elif extension == "webm":
        valid = head.startswith(b"\x1a\x45\xdf\xa3")
    elif extension == "mp3":
        valid = head.startswith(b"ID3") or (
            len(head) >= 2 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0
        )

    if not valid:
        raise ValidationError(
            "Conteúdo do arquivo não corresponde à extensão declarada.", field="file"
        )
