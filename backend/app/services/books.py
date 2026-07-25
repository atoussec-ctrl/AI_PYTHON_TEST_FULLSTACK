"""Book use cases."""

from __future__ import annotations

from datetime import date

from app.errors import NotFoundError, ValidationError
from app.extensions import db
from app.repositories import BookRepository
from app.validation import required_text


def parse_book_payload(payload: dict[str, object]) -> dict[str, object]:
    title = required_text(payload, "title")
    author = required_text(payload, "author")
    summary = required_text(payload, "summary")
    raw_category = payload.get("category")
    if raw_category is not None and not isinstance(raw_category, str):
        raise ValidationError("Campo category deve ser texto.", field="category")
    publication_date = parse_publication_date(payload)

    return {
        "title": title,
        "category": (raw_category or "Programação").strip() or "Programação",
        "author": author,
        "publication_date": publication_date,
        "summary": summary,
    }


def parse_publication_date(payload: dict[str, object]) -> date:
    date_value = payload.get("publication_date")
    if date_value is not None and not isinstance(date_value, str):
        raise ValidationError(
            "Campo publication_date deve usar o formato YYYY-MM-DD.",
            field="publication_date",
        )
    raw_date = (date_value or "").strip()
    if raw_date:
        try:
            return date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValidationError(
                "Campo publication_date deve usar o formato YYYY-MM-DD.",
                field="publication_date",
            ) from exc

    year_value = payload.get("publication_year", payload.get("year"))
    if isinstance(year_value, bool) or (
        year_value is not None and not isinstance(year_value, (str, int))
    ):
        raise ValidationError(
            "Campo publication_year deve ser um ano numérico.", field="publication_year"
        )
    raw_year = str(year_value).strip() if year_value is not None else ""
    if not raw_year:
        raise ValidationError(
            "Campo publication_date ou publication_year é obrigatório.",
            field="publication_date",
        )
    try:
        year = int(raw_year)
    except ValueError as exc:
        raise ValidationError(
            "Campo publication_year deve ser um ano numérico.", field="publication_year"
        ) from exc
    if year < 1000 or year > 9999:
        raise ValidationError(
            "Campo publication_year deve conter quatro dígitos.", field="publication_year"
        )
    return date(year, 1, 1)


class BookService:
    def __init__(self, repository: BookRepository | None = None) -> None:
        self.repository = repository or BookRepository()

    def create(self, payload: dict[str, object]):
        data = parse_book_payload(payload)
        book = self.repository.create(**data)
        db.session.commit()
        return book

    def get(self, book_id: str):
        book = self.repository.get(book_id)
        if not book:
            raise NotFoundError("Livro não encontrado.")
        return book

    def search(
        self,
        title: str | None = None,
        author: str | None = None,
        category: str | None = None,
        query_text: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ):
        return self.repository.search(
            title=title,
            author=author,
            category=category,
            query_text=query_text,
            limit=limit,
            offset=offset,
        )
