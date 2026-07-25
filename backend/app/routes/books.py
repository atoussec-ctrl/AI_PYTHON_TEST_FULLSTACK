"""Book API routes."""

from flask import Blueprint, jsonify, request

from app.services.book_import import BookImportService
from app.services.books import BookService
from app.utils.http import parse_pagination
from app.validation import json_object

books_bp = Blueprint("books", __name__)


@books_bp.post("/books")
def create_book():
    payload = json_object(request.get_json(silent=True))
    book = BookService().create(payload)
    return jsonify(book.to_dict()), 201


@books_bp.post("/books/import")
def import_book():
    book, extracted = BookImportService().import_file(request.files.get("file"))
    return jsonify(
        {
            "book": book.to_dict(),
            "extracted": {
                "title": extracted.title,
                "category": extracted.category,
                "author": extracted.author,
                "publication_year": extracted.publication_year,
                "summary": extracted.summary,
            },
        }
    ), 201


@books_bp.get("/books")
def list_books():
    title = request.args.get("title")
    author = request.args.get("author")
    category = request.args.get("category")
    query_text = request.args.get("q")
    limit, offset = parse_pagination(request.args)
    books = BookService().search(
        title=title,
        author=author,
        category=category,
        query_text=query_text,
        limit=limit,
        offset=offset,
    )
    return jsonify([book.to_dict() for book in books])


@books_bp.get("/books/<book_id>")
def get_book(book_id: str):
    book = BookService().get(book_id)
    return jsonify(book.to_dict())
