import pytest


def test_create_and_search_books(client):
    response = client.post(
        "/api/v1/books",
        json={
            "title": "Python Fluente",
            "category": "Programação",
            "author": "Luciano Ramalho",
            "publication_date": "2015-08-20",
            "summary": "Livro avançado sobre Python.",
        },
    )

    assert response.status_code == 201
    created = response.get_json()
    assert created["id"]
    assert created["title"] == "Python Fluente"
    assert created["category"] == "Programação"
    assert created["publication_year"] == 2015

    by_title = client.get("/api/v1/books?title=python").get_json()
    by_author = client.get("/api/v1/books?author=luciano").get_json()
    by_query = client.get("/api/v1/books?q=avançado").get_json()

    assert len(by_title) == 1
    assert len(by_author) == 1
    assert len(by_query) == 1
    assert by_title[0]["publication_date"] == "2015-08-20"

    detail = client.get(f"/api/v1/books/{created['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["author"] == "Luciano Ramalho"


def test_import_book_from_uploaded_metadata_file(client):
    from io import BytesIO

    content = b"""Titulo: Arquitetura Limpa em Python
Autor: Ana Silva
Categoria: Arquitetura
Ano: 2021
Resumo: Guia pratico para organizar projetos Python com casos de uso, testes e camadas.
"""

    response = client.post(
        "/api/v1/books/import",
        data={"file": (BytesIO(content), "arquitetura.md")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["book"]["title"] == "Arquitetura Limpa em Python"
    assert payload["book"]["category"] == "Arquitetura"
    assert payload["book"]["publication_year"] == 2021


def test_create_book_validates_required_fields(client):
    response = client.post("/api/v1/books", json={"title": "Sem autor"})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["field"] == "author"


@pytest.mark.parametrize("field", ["title", "author", "summary"])
def test_create_book_rejects_null_required_text_fields(client, field):
    payload = _valid_book_payload(**{field: None})

    response = client.post("/api/v1/books", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == field


def test_create_book_rejects_non_object_json_body(client):
    response = client.post("/api/v1/books", json=["not", "an", "object"])

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "body"


def test_search_books_by_category_filter(client):
    client.post(
        "/api/v1/books",
        json={
            "title": "Domain-Driven Design",
            "category": "Arquitetura",
            "author": "Eric Evans",
            "publication_year": 2003,
            "summary": "Modelagem orientada a domínio.",
        },
    )

    results = client.get("/api/v1/books?category=arquitetura").get_json()

    assert len(results) == 1
    assert results[0]["category"] == "Arquitetura"


def test_free_text_search_ranks_by_category_and_author_matches(client):
    client.post(
        "/api/v1/books",
        json={
            "title": "Refactoring",
            "category": "Engenharia",
            "author": "Martin Fowler",
            "publication_year": 1999,
            "summary": "Melhoria incremental de código existente.",
        },
    )

    by_category = client.get("/api/v1/books?q=engenharia").get_json()
    by_author = client.get("/api/v1/books?q=fowler").get_json()

    assert len(by_category) == 1
    assert len(by_author) == 1


def test_free_text_search_returns_all_books_when_query_is_only_stopwords(client):
    client.post(
        "/api/v1/books",
        json={
            "title": "Clean Architecture",
            "category": "Arquitetura",
            "author": "Robert Martin",
            "publication_year": 2017,
            "summary": "Princípios de design de sistemas.",
        },
    )

    results = client.get("/api/v1/books?q=como%20para%20com").get_json()

    assert len(results) == 1


def _valid_book_payload(**overrides):
    payload = {
        "title": "Livro de Teste",
        "author": "Autor Teste",
        "summary": "Resumo de teste.",
        "publication_year": 2020,
    }
    payload.update(overrides)
    return payload


def test_create_book_rejects_invalid_iso_date(client):
    response = client.post(
        "/api/v1/books",
        json=_valid_book_payload(publication_date="20-2020", publication_year=None),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["details"]["field"] == "publication_date"


def test_create_book_requires_date_or_year(client):
    payload = _valid_book_payload()
    payload.pop("publication_year")

    response = client.post("/api/v1/books", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "publication_date"


def test_create_book_rejects_non_numeric_year(client):
    response = client.post(
        "/api/v1/books", json=_valid_book_payload(publication_year="não é um ano")
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "publication_year"


def test_create_book_rejects_year_out_of_range(client):
    response = client.post("/api/v1/books", json=_valid_book_payload(publication_year=99))

    assert response.status_code == 400
    assert response.get_json()["error"]["details"]["field"] == "publication_year"


def test_get_book_returns_404_when_missing(client):
    response = client.get("/api/v1/books/livro_inexistente")

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Livro não encontrado."
