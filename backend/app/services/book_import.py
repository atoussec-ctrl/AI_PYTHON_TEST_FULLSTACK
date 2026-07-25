"""AI-assisted book import from uploaded files.

The MVP uses deterministic extraction so tests never call external LLMs. The
service boundary is intentionally isolated so a LangChain/OpenAI extractor can
replace the heuristic extractor later.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import monotonic

from flask import current_app, has_app_context
from werkzeug.datastructures import FileStorage

from app.errors import ValidationError
from app.models import Book
from app.services.books import BookService
from app.services.file_security import (
    extension_for,
    read_stream_limited,
    safe_filename,
    validate_declared_mime,
    validate_file_bytes,
)
from app.services.observability import traceable_if_enabled

DEFAULT_MAX_UPLOAD_SIZE_MB = 10
DEFAULT_MAX_FILENAME_CHARS = 180
DEFAULT_MAX_PDF_PAGES = 50
DEFAULT_MAX_PDF_CONTENT_STREAM_MB = 16
DEFAULT_MAX_PDF_EXTRACTED_CHARS = 100_000
DEFAULT_MAX_PDF_PROCESSING_SECONDS = 10


@dataclass(frozen=True)
class ExtractedBook:
    title: str
    category: str
    author: str
    publication_year: int
    summary: str


class BookMetadataExtractor:
    @traceable_if_enabled("books.extract_metadata", run_type="tool")
    def extract(self, *, filename: str, content: str) -> ExtractedBook:
        payload = parse_json_content(content) or {}
        title = value_from_payload(payload, "title", "titulo", "título") or regex_value(
            content, r"(?:t[ií]tulo|title)\s*[:\-]\s*(.+)"
        )
        title = title or heading_title(content) or Path(filename).stem.replace("_", " ")

        author = value_from_payload(payload, "author", "autor", "autora") or regex_value(
            content, r"(?:autor(?:a)?|author)\s*[:\-]\s*(.+)"
        )
        category = value_from_payload(payload, "category", "categoria") or regex_value(
            content, r"(?:categoria|category)\s*[:\-]\s*(.+)"
        )
        year_value = (
            value_from_payload(payload, "publication_year", "year", "ano")
            or regex_value(content, r"(?:ano|year|publica[cç][aã]o|publication)\D+(\d{4})")
            or first_year(content)
        )
        summary = value_from_payload(payload, "summary", "resumo") or summary_from_text(content)

        missing = []
        if not title:
            missing.append("title")
        if not author:
            missing.append("author")
        if not year_value:
            missing.append("publication_year")
        if not summary:
            missing.append("summary")
        if missing:
            raise ValidationError(
                "Não foi possível extrair metadados obrigatórios do livro: "
                + ", ".join(missing)
                + ". Inclua título, autor, ano e resumo no arquivo.",
                field="file",
            )

        try:
            publication_year = int(str(year_value).strip())
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Ano de publicação extraído deve ser numérico.", field="file"
            ) from exc
        if publication_year < 1000 or publication_year > 9999:
            raise ValidationError(
                "Ano de publicação extraído deve conter quatro dígitos.", field="file"
            )

        return ExtractedBook(
            title=clean(title),
            category=clean(category or "Programação"),
            author=clean(author),
            publication_year=publication_year,
            summary=clean(summary),
        )


class BookImportService:
    def __init__(
        self,
        extractor: BookMetadataExtractor | None = None,
        book_service: BookService | None = None,
    ) -> None:
        self.extractor = extractor or BookMetadataExtractor()
        self.book_service = book_service or BookService()

    @traceable_if_enabled("books.import_file", run_type="chain")
    def import_file(self, file: FileStorage | None) -> tuple[Book, ExtractedBook]:
        if not file or not file.filename:
            raise ValidationError("Campo file é obrigatório.", field="file")
        filename = safe_filename(
            file.filename,
            max_chars=_config_int("MAX_UPLOAD_FILENAME_CHARS", DEFAULT_MAX_FILENAME_CHARS),
        )
        extension = extension_for(filename)
        if extension not in {"txt", "md", "json", "pdf"}:
            raise ValidationError("Envie um arquivo .txt, .md, .json ou .pdf.", field="file")

        validate_declared_mime(extension, file.mimetype)
        max_bytes = _config_int("MAX_UPLOAD_SIZE_MB", DEFAULT_MAX_UPLOAD_SIZE_MB) * 1024 * 1024
        raw = read_stream_limited(file.stream, max_bytes)
        validate_file_bytes(raw, extension)

        if extension == "pdf":
            content = extract_pdf_text(raw)
        else:
            content = raw.decode("utf-8-sig")
        if not content.strip():
            raise ValidationError("Arquivo sem texto legível para extração.", field="file")

        extracted = self.extractor.extract(filename=filename, content=content)
        book = self.book_service.create(
            {
                "title": extracted.title,
                "category": extracted.category,
                "author": extracted.author,
                "publication_year": extracted.publication_year,
                "summary": extracted.summary,
            }
        )
        return book, extracted


def extract_pdf_text(
    raw: bytes,
    *,
    max_pages: int | None = None,
    max_content_stream_bytes: int | None = None,
    max_extracted_chars: int | None = None,
    max_processing_seconds: int | None = None,
) -> str:
    """Extract bounded text from a PDF.

    Invalid PDFs still return an empty string so callers can report the same
    user-facing "no readable text" error. Resource-limit violations are
    validation errors and are never hidden as an empty document.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("Dependência pypdf não instalada para leitura de PDF.") from exc

    page_limit = _positive_limit(
        max_pages,
        "MAX_PDF_PAGES",
        DEFAULT_MAX_PDF_PAGES,
    )
    stream_limit = _non_negative_limit(
        max_content_stream_bytes,
        "MAX_PDF_CONTENT_STREAM_MB",
        DEFAULT_MAX_PDF_CONTENT_STREAM_MB,
        multiplier=1024 * 1024,
    )
    text_limit = _positive_limit(
        max_extracted_chars,
        "MAX_PDF_EXTRACTED_CHARS",
        DEFAULT_MAX_PDF_EXTRACTED_CHARS,
    )
    time_limit = _positive_limit(
        max_processing_seconds,
        "MAX_PDF_PROCESSING_SECONDS",
        DEFAULT_MAX_PDF_PROCESSING_SECONDS,
    )
    deadline = monotonic() + time_limit

    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValidationError("PDF criptografado não é suportado.", field="file")
        if len(reader.pages) > page_limit:
            raise ValidationError(f"PDF excede o limite de {page_limit} páginas.", field="file")

        pages: list[str] = []
        content_stream_bytes = 0
        extracted_chars = 0
        for page in reader.pages:
            _ensure_before_deadline(deadline)
            contents = page.get_contents()
            if contents is not None:
                content_stream_bytes += len(contents.get_data())
                if content_stream_bytes > stream_limit:
                    raise ValidationError(
                        "PDF excede o limite seguro de conteúdo descompactado.",
                        field="file",
                    )

            page_text = page.extract_text() or ""
            extracted_chars += len(page_text)
            if extracted_chars > text_limit:
                raise ValidationError("PDF excede o limite seguro de texto extraído.", field="file")
            pages.append(page_text)
            _ensure_before_deadline(deadline)
    except ValidationError:
        raise
    except (MemoryError, RecursionError) as exc:
        raise ValidationError(
            "PDF excede os limites seguros de processamento.", field="file"
        ) from exc
    except Exception:
        return ""
    return "\n".join(pages).strip()


def _config_int(name: str, default: int) -> int:
    value = current_app.config.get(name, default) if has_app_context() else default
    return int(value)


def _positive_limit(explicit: int | None, config_name: str, default: int) -> int:
    value = explicit if explicit is not None else _config_int(config_name, default)
    if value <= 0:
        raise ValueError(f"{config_name} deve ser maior que zero")
    return value


def _non_negative_limit(
    explicit: int | None,
    config_name: str,
    default: int,
    *,
    multiplier: int = 1,
) -> int:
    if explicit is not None:
        if explicit < 0:
            raise ValueError(f"{config_name} deve ser maior ou igual a zero")
        return explicit
    configured = _config_int(config_name, default)
    if configured < 0:
        raise ValueError(f"{config_name} deve ser maior ou igual a zero")
    return configured * multiplier


def _ensure_before_deadline(deadline: float) -> None:
    if monotonic() > deadline:
        raise ValidationError("PDF excedeu o tempo seguro de processamento.", field="file")


def parse_json_content(content: str) -> dict[str, object] | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def value_from_payload(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def regex_value(content: str, pattern: str) -> str | None:
    match = re.search(pattern, content, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def heading_title(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()
    return None


def first_year(content: str) -> str | None:
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b", content)
    return match.group(1) if match else None


def summary_from_text(content: str) -> str | None:
    match = re.search(
        r"(?:resumo|summary)\s*[:\-]\s*(.+?)(?:\n\s*\n|$)",
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
    if len(paragraphs) >= 3:
        return " ".join(paragraphs[2:])[:1200]
    return None


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().strip('"')
