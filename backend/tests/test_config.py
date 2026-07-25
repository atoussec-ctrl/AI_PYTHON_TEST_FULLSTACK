"""Unit tests for pure helpers in app.config."""

from __future__ import annotations

import pytest

from app.config import (
    BASE_DIR,
    InsecureConfigurationError,
    InvalidConfigurationError,
    assert_production_config_is_safe,
    assert_resource_limits_are_valid,
    resolve_sqlite_url,
)


def test_resolve_sqlite_url_converts_dot_relative_path():
    result = resolve_sqlite_url("sqlite:///./storage/app.db")

    assert result == f"sqlite:///{BASE_DIR / 'storage/app.db'}"


def test_resolve_sqlite_url_converts_bare_relative_path():
    result = resolve_sqlite_url("sqlite:///storage/app.db")

    assert result == f"sqlite:///{BASE_DIR / 'storage/app.db'}"


def test_resolve_sqlite_url_preserves_in_memory_database():
    assert resolve_sqlite_url("sqlite:///:memory:") == "sqlite:///:memory:"


def test_resolve_sqlite_url_leaves_absolute_four_slash_path_untouched():
    result = resolve_sqlite_url("sqlite:////absolute/path/app.db")

    assert result == "sqlite:////absolute/path/app.db"


def test_resolve_sqlite_url_leaves_non_sqlite_urls_untouched():
    result = resolve_sqlite_url("postgresql://user:pass@localhost/db")

    assert result == "postgresql://user:pass@localhost/db"


@pytest.mark.parametrize(
    "secret_key",
    ["", "replace-me", "changeme", "change-me", "dev-secret-key-change-me"],
)
def test_assert_production_config_rejects_placeholder_secret_key(secret_key):
    with pytest.raises(InsecureConfigurationError, match="SECRET_KEY"):
        assert_production_config_is_safe({"SECRET_KEY": secret_key, "API_KEY": "a-real-key"})


@pytest.mark.parametrize("api_key", ["", "replace-me", "changeme", "change-me"])
def test_assert_production_config_rejects_placeholder_api_key(api_key):
    with pytest.raises(InsecureConfigurationError, match="API_KEY"):
        assert_production_config_is_safe({"SECRET_KEY": "a-real-secret", "API_KEY": api_key})


def test_assert_production_config_accepts_real_secrets():
    assert_production_config_is_safe({"SECRET_KEY": "a-real-secret", "API_KEY": "a-real-key"})


def _valid_resource_limits() -> dict[str, object]:
    return {
        "MAX_UPLOAD_SIZE_MB": 10,
        "MAX_MESSAGE_UPLOAD_SIZE_MB": 50,
        "MAX_ATTACHMENTS_PER_MESSAGE": 5,
        "ORPHAN_UPLOAD_MAX_AGE_HOURS": 24,
        "MAX_UPLOAD_FILENAME_CHARS": 180,
        "MAX_PDF_PAGES": 50,
        "MAX_PDF_CONTENT_STREAM_MB": 16,
        "MAX_PDF_EXTRACTED_CHARS": 100_000,
        "MAX_PDF_PROCESSING_SECONDS": 10,
    }


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_UPLOAD_SIZE_MB", 0),
        ("MAX_MESSAGE_UPLOAD_SIZE_MB", 0),
        ("MAX_ATTACHMENTS_PER_MESSAGE", -1),
        ("ORPHAN_UPLOAD_MAX_AGE_HOURS", "invalid"),
        ("MAX_PDF_PAGES", -1),
        ("MAX_PDF_PROCESSING_SECONDS", "invalid"),
        ("MAX_PDF_EXTRACTED_CHARS", True),
    ],
)
def test_resource_limits_reject_non_positive_or_non_integer_values(name, value):
    limits = _valid_resource_limits()
    limits[name] = value

    with pytest.raises(InvalidConfigurationError, match=name):
        assert_resource_limits_are_valid(limits)


def test_resource_limits_reject_filename_bound_larger_than_database_schema():
    limits = _valid_resource_limits()
    limits["MAX_UPLOAD_FILENAME_CHARS"] = 256

    with pytest.raises(InvalidConfigurationError, match="255"):
        assert_resource_limits_are_valid(limits)


def test_resource_limits_accept_safe_values():
    assert_resource_limits_are_valid(_valid_resource_limits())
