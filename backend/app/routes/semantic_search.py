"""Semantic search routes."""

from flask import Blueprint, jsonify, request

from app.services.semantic_search import SemanticSearchService
from app.utils.http import validation_error
from app.validation import json_object, optional_text

semantic_search_bp = Blueprint("semantic_search", __name__)


@semantic_search_bp.post("/semantic-search")
def semantic_search():
    payload = json_object(request.get_json(silent=True))
    try:
        k = int(payload.get("k", 3))
    except (TypeError, ValueError):
        return validation_error("Campo k deve ser numérico.", "k")

    results = SemanticSearchService().search(query=optional_text(payload, "query"), k=k)
    return jsonify({"results": results})
