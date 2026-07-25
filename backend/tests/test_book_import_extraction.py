"""Unit tests closing coverage gaps in app.services.book_import.

Exercises the heuristic extractor's fallback chain (JSON payload -> labelled
regex -> markdown heading / bare year / paragraph position) directly, plus
the file-level validation branches of BookImportService.import_file.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from app.errors import ValidationError
from app.services.book_import import (
    BookImportService,
    BookMetadataExtractor,
    extract_pdf_text,
    parse_json_content,
)

# ── BookMetadataExtractor: campos obrigatórios ausentes ──


def test_extract_reports_missing_title_only():
    content = "Autor: Fulano\nAno: 2020\nResumo: Um resumo qualquer suficientemente longo."
    with pytest.raises(ValidationError, match="title"):
        BookMetadataExtractor().extract(filename="", content=content)


def test_extract_reports_missing_author():
    content = "Titulo: Livro Sem Autor\nAno: 2020\nResumo: Um resumo qualquer."
    with pytest.raises(ValidationError, match="author"):
        BookMetadataExtractor().extract(filename="livro.txt", content=content)


def test_extract_reports_missing_year():
    content = "Titulo: Livro Sem Ano\nAutor: Fulano\nResumo: Um resumo qualquer."
    with pytest.raises(ValidationError, match="publication_year"):
        BookMetadataExtractor().extract(filename="livro.txt", content=content)


def test_extract_reports_missing_summary():
    # Single line on purpose: >=3 non-blank lines would trigger the paragraph
    # fallback in summary_from_text, masking the "missing summary" case.
    content = '{"titulo": "Livro Sem Resumo", "autor": "Fulano", "ano": 2020}'
    with pytest.raises(ValidationError, match="summary"):
        BookMetadataExtractor().extract(filename="livro.json", content=content)


# ── Fallbacks: heading markdown, ano solto no texto, resumo por parágrafo ──


def test_extract_falls_back_to_heading_bare_year_and_paragraph_summary():
    content = "\n".join(
        [
            "# Domain-Driven Design",
            "Autor: Eric Evans",
            "Este eh um resumo em paragrafo separado sem o rotulo resumo.",
            "Mais um paragrafo de contexto adicional para o resumo heuristico.",
            "Lancado em 2019 por uma editora sem usar a palavra ano ou year antes do numero.",
        ]
    )

    extracted = BookMetadataExtractor().extract(filename="ddd.txt", content=content)

    assert extracted.title == "Domain-Driven Design"
    assert extracted.author == "Eric Evans"
    assert extracted.publication_year == 2019
    assert "paragrafo" in extracted.summary


def test_extract_falls_back_to_filename_when_no_title_signal_at_all():
    content = "Autor: Fulano\nAno: 2020\nResumo: Resumo sem nenhum titulo ou heading."

    extracted = BookMetadataExtractor().extract(
        filename="meu_livro_sem_titulo.txt", content=content
    )

    assert extracted.title == "meu livro sem titulo"


# ── Extração via payload JSON (aliases pt-BR) ──


def test_extract_reads_fields_from_json_payload_aliases():
    content = (
        '{"titulo": "Título via JSON", "autor": "Autora JSON", '
        '"categoria": "Ficção", "ano": 2021, '
        '"resumo": "Resumo direto do JSON, sem precisar de regex."}'
    )

    extracted = BookMetadataExtractor().extract(filename="livro.json", content=content)

    assert extracted.title == "Título via JSON"
    assert extracted.author == "Autora JSON"
    assert extracted.category == "Ficção"
    assert extracted.publication_year == 2021


def test_parse_json_content_ignores_non_object_json():
    assert parse_json_content("[1, 2, 3]") is None
    assert parse_json_content('"apenas uma string"') is None


def test_extract_rejects_a_year_with_more_than_four_digits():
    extractor = BookMetadataExtractor()

    with pytest.raises(ValidationError, match="quatro dígitos"):
        extractor.extract(
            filename="book.json",
            content=(
                '{"title":"Livro","author":"Autora","publication_year":10000,"summary":"Resumo"}'
            ),
        )


# ── BookImportService.import_file: validações de arquivo ──


def test_import_file_requires_a_file():
    with pytest.raises(ValidationError, match="obrigatório"):
        BookImportService().import_file(None)


def test_import_file_rejects_unsupported_extension():
    file = BytesIO(b"conteudo")
    file.filename = "imagem.png"

    with pytest.raises(ValidationError, match=r"\.txt, \.md, \.json ou \.pdf"):
        BookImportService().import_file(file)


# ── extract_pdf_text: PDF corrompido ──


def test_extract_pdf_text_returns_empty_string_for_corrupt_pdf():
    assert extract_pdf_text(b"isto nao e um PDF valido") == ""
