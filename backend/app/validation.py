"""Small, framework-agnostic helpers for validating API input.

HTTP adapters should reject malformed shapes before values reach services.
Keeping these primitives together avoids the dangerous ``str(value)``
coercion that used to turn JSON ``null`` into the valid-looking text
``"None"`` in several endpoints.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.errors import ValidationError


def json_object(value: object) -> dict[str, object]:
    """Return a JSON object or an empty object for an absent request body."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError("O corpo da requisição deve ser um objeto JSON.", field="body")
    return value


def optional_text(
    payload: Mapping[str, object],
    field: str,
    *,
    default: str = "",
) -> str:
    """Read an optional string without coercing arbitrary JSON values."""
    value = payload.get(field)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValidationError(f"Campo {field} deve ser texto.", field=field)
    return value


def required_text(payload: Mapping[str, object], field: str) -> str:
    """Read and trim a required, non-blank string field."""
    value = optional_text(payload, field).strip()
    if not value:
        raise ValidationError(f"Campo {field} é obrigatório.", field=field)
    return value


def string_list(value: object, field: str) -> list[str]:
    """Validate a JSON list of non-blank strings and normalize whitespace."""
    if value is None:
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValidationError(f"Campo {field} deve ser uma lista de textos.", field=field)
    return [item.strip() for item in value]
