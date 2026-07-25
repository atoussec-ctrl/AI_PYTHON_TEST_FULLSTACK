"""Unit tests for the shared, defense-in-depth file policy."""

from __future__ import annotations

from io import BytesIO

import pytest

from app.errors import ValidationError
from app.services.file_security import (
    canonical_mime_type,
    copy_stream_limited,
    extension_for,
    kind_for_extension,
    read_stream_limited,
    safe_filename,
    validate_declared_mime,
    validate_file_bytes,
    validate_file_path,
)


def test_safe_filename_normalizes_untrusted_path_components():
    filename = safe_filename("../../ relatório final?.txt")

    assert filename == "relatorio_final.txt"
    assert "/" not in filename
    assert "\\" not in filename


@pytest.mark.parametrize("filename", ["", "?", "a" * 181 + ".txt"])
def test_safe_filename_rejects_empty_or_oversized_names(filename):
    with pytest.raises(ValidationError, match="arquivo|excede"):
        safe_filename(filename)


def test_extension_kind_and_canonical_mime_share_one_policy():
    assert extension_for("REPORT.PDF") == "pdf"
    assert kind_for_extension("pdf") == "document"
    assert kind_for_extension("exe") is None
    assert canonical_mime_type("pdf") == "application/pdf"

    with pytest.raises(ValidationError, match="Extensão"):
        canonical_mime_type("exe")


@pytest.mark.parametrize("declared", [None, "", "application/octet-stream"])
def test_declared_mime_allows_missing_or_generic_client_metadata(declared):
    validate_declared_mime("png", declared)


def test_declared_mime_rejects_an_obvious_extension_mismatch():
    with pytest.raises(ValidationError, match="Content-Type"):
        validate_declared_mime("png", "text/plain; charset=utf-8")


def test_bounded_stream_helpers_reject_overflow(tmp_path):
    with pytest.raises(ValidationError, match="tamanho máximo"):
        read_stream_limited(BytesIO(b"1234"), 3)

    destination = tmp_path / "quarantine"
    with pytest.raises(ValidationError, match="tamanho máximo"):
        copy_stream_limited(BytesIO(b"1234"), destination, 3)
    assert destination.read_bytes() == b""


def test_bounded_stream_helpers_accept_the_exact_limit(tmp_path):
    assert read_stream_limited(BytesIO(b"123"), 3) == b"123"

    destination = tmp_path / "quarantine"
    assert copy_stream_limited(BytesIO(b"123"), destination, 3) == 3
    assert destination.read_bytes() == b"123"


def test_bounded_memory_reader_handles_short_reads_without_missing_overflow():
    class ShortReadStream(BytesIO):
        def read(self, size=-1):
            return super().read(min(size, 1))

    with pytest.raises(ValidationError, match="tamanho máximo"):
        read_stream_limited(ShortReadStream(b"1234"), 3)

    assert read_stream_limited(ShortReadStream(b"123"), 3) == b"123"


@pytest.mark.parametrize(
    ("extension", "raw"),
    [
        ("txt", "olá".encode()),
        ("json", b'{"title":"Clean Code"}'),
        ("pdf", b"%PDF-1.4\n1 0 obj\nendobj\n%%EOF"),
        ("png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"),
        ("jpg", b"\xff\xd8\xffpayload\xff\xd9"),
        ("jpeg", b"\xff\xd8\xffpayload\xff\xd9"),
        ("webp", b"RIFF\x00\x00\x00\x00WEBP"),
        ("wav", b"RIFF\x00\x00\x00\x00WAVE"),
        ("webm", b"\x1a\x45\xdf\xa3payload"),
        ("mp3", b"ID3payload"),
        ("mp3", b"\xff\xe3payload"),
    ],
)
def test_content_validation_accepts_supported_signatures(extension, raw):
    assert validate_file_bytes(raw, extension) == canonical_mime_type(extension)


@pytest.mark.parametrize(
    ("extension", "raw", "message"),
    [
        ("txt", b"a\x00b", "bytes nulos"),
        ("txt", b"\xff\xfe", "UTF-8"),
        ("json", b"{invalid", "JSON inválido"),
        ("pdf", b"not a pdf", "não corresponde"),
        ("png", b"not a png", "não corresponde"),
    ],
)
def test_content_validation_rejects_malformed_or_disguised_files(extension, raw, message):
    with pytest.raises(ValidationError, match=message):
        validate_file_bytes(raw, extension)


def test_file_path_validation_rejects_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.touch()

    with pytest.raises(ValidationError, match="vazio"):
        validate_file_path(path, "txt")


def test_stream_helpers_reject_negative_limits(tmp_path):
    with pytest.raises(ValueError, match="maior ou igual"):
        read_stream_limited(BytesIO(), -1)
    with pytest.raises(ValueError, match="maior ou igual"):
        copy_stream_limited(BytesIO(), tmp_path / "file", -1)
