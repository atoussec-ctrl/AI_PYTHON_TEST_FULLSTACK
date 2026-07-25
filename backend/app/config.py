"""MindSight AI configuration."""

import os
from collections.abc import Mapping
from pathlib import Path

from app.env_loader import load_project_env

# Importing this module via `from app.env_loader import ...` (as run.py does)
# triggers `app/__init__.py` first, which imports this module — so by the
# time run.py's own load_project_env() call would run, Config's os.getenv()
# class attributes below have already been evaluated against a stale
# environment. Loading here guarantees .env is applied before those reads,
# regardless of which entry point (run.py, seed.py, tests) imports `app` first.
load_project_env()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE = 5


def resolve_sqlite_url(value: str) -> str:
    if value == "sqlite:///:memory:":
        return value
    if value.startswith("sqlite:///./"):
        relative_path = value.removeprefix("sqlite:///./")
        return f"sqlite:///{BASE_DIR / relative_path}"
    if value.startswith("sqlite:///") and not value.startswith("sqlite:////"):
        relative_path = value.removeprefix("sqlite:///")
        return f"sqlite:///{BASE_DIR / relative_path}"
    return value


class Config:
    """Base configuration shared by all environments."""

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    JSON_SORT_KEYS: bool = False

    # Database
    SQLALCHEMY_DATABASE_URI: str = resolve_sqlite_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'storage' / 'app.db'}")
    )

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    CHAT_GATEWAY: str = os.getenv("CHAT_GATEWAY", "local")
    # Limite de tokens de saída enviado ao provedor (HF usa 1024 se omitido).
    CHAT_MAX_OUTPUT_TOKENS: int = int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "4096"))
    # Limite de caracteres por mensagem de entrada (protege o prompt do LLM).
    CHAT_MAX_MESSAGE_CHARS: int = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "8000"))
    # Timeout (segundos) de cada chamada ao provedor de IA — sem isso, um
    # provedor lento ou travado prende a requisição indefinidamente.
    CHAT_GATEWAY_TIMEOUT_SECONDS: int = int(os.getenv("CHAT_GATEWAY_TIMEOUT_SECONDS", "30"))

    # Rate limiting (flask-limiter). Armazenamento em memória por processo —
    # sob múltiplos workers do Gunicorn, o limite real é aproximadamente
    # RATE_LIMIT_CHAT_MESSAGES × número de workers, não um contador global
    # compartilhado. Suficiente para conter abuso básico nesta escala; um
    # backend compartilhado (Redis) seria necessário para um limite exato
    # entre processos.
    RATELIMIT_DEFAULT: str = os.getenv("RATE_LIMIT_DEFAULT", "200 per minute")
    RATELIMIT_STORAGE_URI: str = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED: bool = True
    # Limite dedicado e mais estrito para o endpoint que chama o provedor de
    # IA pago — lido dinamicamente a cada requisição (ver routes/chat.py),
    # não fixado na importação do módulo.
    RATE_LIMIT_CHAT_MESSAGES: str = os.getenv("RATE_LIMIT_CHAT_MESSAGES", "20 per minute")
    # CSV de modelos que o cliente pode solicitar explicitamente. Vazio = só os
    # modelos já configurados pelo operador (HF_CHAT_MODEL / OPENAI_MODEL).
    ALLOWED_CHAT_MODELS: str = os.getenv("ALLOWED_CHAT_MODELS", "")

    # Hugging Face Inference Providers (DeepSeek V4 etc.)
    # Aceita HUGGINGFACE_API_KEY ou HUGGINGFACE_API_TOKEN.
    HUGGINGFACE_API_KEY: str = os.getenv(
        "HUGGINGFACE_API_KEY", os.getenv("HUGGINGFACE_API_TOKEN", "")
    )
    HF_CHAT_MODEL: str = os.getenv("HF_CHAT_MODEL", "deepseek-ai/DeepSeek-V4-Flash")
    HF_BASE_URL: str = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1")

    # LangSmith
    LANGSMITH_TRACING: str = os.getenv("LANGSMITH_TRACING", "false")
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "mindsight-ai")

    # Embeddings / Vector Store
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    VECTOR_STORE: str = os.getenv("VECTOR_STORE", "faiss")
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", str(BASE_DIR / "storage" / "faiss.index"))

    # Uploads
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "storage" / "uploads"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    # A multipart chat request may contain several individually bounded files.
    # Flask's per-request override applies this aggregate ceiling only to that
    # endpoint; other upload endpoints retain MAX_UPLOAD_SIZE_MB.
    MAX_MESSAGE_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_MESSAGE_UPLOAD_SIZE_MB", "50"))
    MAX_ATTACHMENTS_PER_MESSAGE: int = int(
        os.getenv("MAX_ATTACHMENTS_PER_MESSAGE", str(DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE))
    )
    ORPHAN_UPLOAD_MAX_AGE_HOURS: int = int(os.getenv("ORPHAN_UPLOAD_MAX_AGE_HOURS", "24"))
    MAX_UPLOAD_FILENAME_CHARS: int = int(os.getenv("MAX_UPLOAD_FILENAME_CHARS", "180"))
    MAX_PDF_PAGES: int = int(os.getenv("MAX_PDF_PAGES", "50"))
    MAX_PDF_CONTENT_STREAM_MB: int = int(os.getenv("MAX_PDF_CONTENT_STREAM_MB", "16"))
    MAX_PDF_EXTRACTED_CHARS: int = int(os.getenv("MAX_PDF_EXTRACTED_CHARS", "100000"))
    MAX_PDF_PROCESSING_SECONDS: int = int(os.getenv("MAX_PDF_PROCESSING_SECONDS", "10"))
    MAX_CONTENT_LENGTH: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # CORS
    CORS_ALLOWED_ORIGINS: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3002,http://127.0.0.1:3002",
    )

    # API
    API_TITLE = "MindSight AI"
    API_VERSION = "v1"
    OPENAPI_VERSION = "3.0.3"

    # Shared-secret auth. Empty (the default) leaves the API open — matches
    # this project's "no external key required" local-dev goal. Setting it
    # activates the before_request gate in app/security.py; production
    # startup then requires it via assert_production_config_is_safe below.
    API_KEY: str = os.getenv("API_KEY", "")


class DevelopmentConfig(Config):
    """Development-specific settings."""

    DEBUG: bool = True


class TestingConfig(Config):
    """Testing-specific settings.

    Unit tests keep the fast in-memory default. Browser-level tests may opt
    into an isolated file database because Flask's threaded development
    server must not share one in-memory SQLite connection across concurrent
    requests.
    """

    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = resolve_sqlite_url(
        os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    )
    LANGSMITH_TRACING: str = "false"
    OPENAI_API_KEY: str = "test-key"
    HUGGINGFACE_API_KEY: str = ""
    CHAT_GATEWAY: str = "local"
    CHAT_MAX_MESSAGE_CHARS: int = 8000
    ALLOWED_CHAT_MODELS: str = ""
    UPLOAD_DIR: str = os.getenv("TEST_UPLOAD_DIR", "/tmp/mindsight-test-uploads")
    MAX_MESSAGE_UPLOAD_SIZE_MB: int = 50
    MAX_ATTACHMENTS_PER_MESSAGE: int = DEFAULT_MAX_ATTACHMENTS_PER_MESSAGE
    ORPHAN_UPLOAD_MAX_AGE_HOURS: int = 24
    MAX_UPLOAD_FILENAME_CHARS: int = 180
    MAX_PDF_PAGES: int = 50
    MAX_PDF_CONTENT_STREAM_MB: int = 16
    MAX_PDF_EXTRACTED_CHARS: int = 100000
    MAX_PDF_PROCESSING_SECONDS: int = 10
    FAISS_INDEX_PATH: str = "/tmp/mindsight-test-faiss.index"
    WTF_CSRF_ENABLED: bool = False
    API_KEY: str = ""
    # Pinned rather than inherited from a possibly noisy local .env — matches
    # Python's own default so existing caplog-based assertions stay unaffected.
    LOG_LEVEL: str = "WARNING"
    # Off by default so the suite's repeated calls to the same routes never
    # get throttled; individual rate-limit tests opt back in per test.
    RATELIMIT_ENABLED: bool = False


class ProductionConfig(Config):
    """Production-specific settings."""

    DEBUG: bool = False


config_by_name: dict[str, type[Config]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

# Values that must never reach a production boot — either an empty secret or
# one of the placeholders this project's own .env.example / docs suggest as
# a starting point (e.g. SECRET_KEY's own class default above).
INSECURE_PLACEHOLDER_VALUES = frozenset(
    {"", "replace-me", "changeme", "change-me", "dev-secret-key-change-me"}
)


class InsecureConfigurationError(RuntimeError):
    """Raised when APP_ENV=production would boot with a guessable secret."""


class InvalidConfigurationError(RuntimeError):
    """Raised when a resource limit is invalid or internally inconsistent."""


POSITIVE_RESOURCE_LIMITS = (
    "MAX_UPLOAD_SIZE_MB",
    "MAX_MESSAGE_UPLOAD_SIZE_MB",
    "MAX_ATTACHMENTS_PER_MESSAGE",
    "ORPHAN_UPLOAD_MAX_AGE_HOURS",
    "MAX_UPLOAD_FILENAME_CHARS",
    "MAX_PDF_PAGES",
    "MAX_PDF_CONTENT_STREAM_MB",
    "MAX_PDF_EXTRACTED_CHARS",
    "MAX_PDF_PROCESSING_SECONDS",
)


def assert_resource_limits_are_valid(app_config: Mapping[str, object]) -> None:
    """Fail at startup instead of turning bad limits into request-time 500s."""
    for name in POSITIVE_RESOURCE_LIMITS:
        raw_value = app_config.get(name)
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, str)):
            raise InvalidConfigurationError(f"{name} deve ser um inteiro maior que zero.")
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise InvalidConfigurationError(f"{name} deve ser um inteiro maior que zero.") from exc
        if value <= 0:
            raise InvalidConfigurationError(f"{name} deve ser maior que zero.")

    if int(app_config["MAX_UPLOAD_FILENAME_CHARS"]) > 255:
        raise InvalidConfigurationError(
            "MAX_UPLOAD_FILENAME_CHARS não pode exceder os 255 caracteres do schema."
        )


def assert_production_config_is_safe(app_config: Mapping[str, object]) -> None:
    """Fail fast instead of silently serving production traffic with a
    guessable SECRET_KEY or a fully public API (no API_KEY configured)."""
    if app_config.get("SECRET_KEY", "") in INSECURE_PLACEHOLDER_VALUES:
        raise InsecureConfigurationError(
            "SECRET_KEY não pode usar o valor padrão de desenvolvimento em produção. "
            "Defina um segredo real via variável de ambiente."
        )
    if app_config.get("API_KEY", "") in INSECURE_PLACEHOLDER_VALUES:
        raise InsecureConfigurationError(
            "API_KEY é obrigatório em produção — sem ele, a API fica totalmente "
            "pública. Defina um segredo real via variável de ambiente."
        )
