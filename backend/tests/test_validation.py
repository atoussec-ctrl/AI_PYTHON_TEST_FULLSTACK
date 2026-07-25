from __future__ import annotations

import pytest

from app.errors import ValidationError
from app.validation import json_object, optional_text, required_text, string_list


def test_json_object_handles_absent_and_valid_payloads():
    payload = {"name": "MindSight"}

    assert json_object(None) == {}
    assert json_object(payload) is payload


def test_text_helpers_preserve_defaults_and_trim_required_values():
    payload = {"required": "  value  ", "optional": None}

    assert required_text(payload, "required") == "value"
    assert optional_text(payload, "optional", default="fallback") == "fallback"


@pytest.mark.parametrize("value", [42, {}, []])
def test_optional_text_rejects_non_string_values(value):
    with pytest.raises(ValidationError, match="deve ser texto"):
        optional_text({"field": value}, "field")


def test_required_text_rejects_blank_values():
    with pytest.raises(ValidationError, match="obrigatório"):
        required_text({"field": "  "}, "field")


def test_string_list_normalizes_values_and_rejects_invalid_shapes():
    assert string_list(None, "ids") == []
    assert string_list([" a ", "b"], "ids") == ["a", "b"]

    with pytest.raises(ValidationError, match="lista de textos"):
        string_list(["ok", ""], "ids")
