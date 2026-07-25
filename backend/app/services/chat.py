"""Chat use cases and AI gateway abstractions."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from flask import current_app, has_app_context

from app.errors import NotFoundError, ValidationError
from app.extensions import db
from app.metrics import record_gateway_call
from app.models import Attachment, Book
from app.repositories import BookRepository, ChatRepository
from app.services.observability import current_run_id, traceable_if_enabled
from app.services.uploads import read_attachment_text

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 12
HISTORY_BOOK_FALLBACK_TURNS = 3
GATEWAY_FAILURE_MESSAGE = (
    "Não foi possível gerar a resposta da IA agora. Tente novamente em instantes."
)
DEFAULT_CHAT_MAX_MESSAGE_CHARS = 8000
DEFAULT_CHAT_GATEWAY_TIMEOUT_SECONDS = 30

# Modelos OpenAI de reasoning aceitam reasoning_effort, mas rejeitam temperature.
REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5")

# Router de Inference Providers do Hugging Face (compatível com a API da OpenAI).
HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"
DEFAULT_HF_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
DEFAULT_CHAT_MAX_OUTPUT_TOKENS = 4096
TRUNCATION_NOTICE = (
    "\n\n---\n\n"
    "*Resposta interrompida por limite de tokens. "
    "Aumente `CHAT_MAX_OUTPUT_TOKENS` ou peça para continuar.*"
)

SYSTEM_PROMPT = """Você é um assistente sênior especializado em Python.
Responda em português.
Explique passo a passo quando necessário.
Inclua exemplos de código claros.
Quando houver risco de erro, avise.
Não invente APIs.
Priorize Flask, FastAPI, SQLAlchemy, testes, arquitetura e boas práticas."""

THINKING_MODES: dict[str, dict[str, object]] = {
    "fast": {
        "temperature": 0.2,
        "reasoning_effort": "low",
        "instruction": "Seja direto e objetivo.",
    },
    "balanced": {
        "temperature": 0.3,
        "reasoning_effort": "medium",
        "instruction": "Explique com exemplos.",
    },
    "deep": {
        "temperature": 0.2,
        "reasoning_effort": "high",
        "instruction": "Analise trade-offs e detalhe.",
    },
}


@dataclass(frozen=True)
class ChatAnswer:
    content: str
    thinking_mode: str


class ChatCompletionGateway:
    def answer(
        self,
        question: str,
        thinking_mode: str,
        book_context: list[Book] | None = None,
        history: list[dict[str, str]] | None = None,
        attachment_context: str | None = None,
    ) -> str:
        raise NotImplementedError


class LocalPythonAssistantGateway(ChatCompletionGateway):
    """Deterministic local gateway for development and tests."""

    provider = "local"

    @traceable_if_enabled("chat.local_python_assistant", run_type="llm")
    def answer(
        self,
        question: str,
        thinking_mode: str,
        book_context: list[Book] | None = None,
        history: list[dict[str, str]] | None = None,
        attachment_context: str | None = None,
    ) -> str:
        normalized = question.strip().lower()
        mode_hint = THINKING_MODES[thinking_mode]["instruction"]
        sections: list[str] = []
        if attachment_context:
            sections.append(
                "Analisei os anexos enviados nesta conversa e considerei o conteúdo "
                f"deles na resposta.\n\n{attachment_context}"
            )
        if book_context:
            book_lines = []
            for book in book_context:
                book_lines.append(
                    "\n".join(
                        [
                            f"- Título: {book.title}",
                            f"  Categoria: {book.category}",
                            f"  Autor: {book.author}",
                            f"  Publicação: {book.publication_date.isoformat()}",
                            f"  Resumo: {book.summary}",
                            f"  Fonte: biblioteca local, id `{book.id}`",
                        ]
                    )
                )
            sections.append(
                "Encontrei informações na biblioteca local e vou citar apenas o que "
                "está registrado na base.\n\n"
                f"{chr(10).join(book_lines)}\n\n"
                "Com base nesses registros, posso resumir, explicar trechos do resumo "
                "e comparar os livros encontrados. Se você pedir algo que não esteja "
                "nesses campos, eu vou sinalizar a limitação em vez de inventar."
            )
        if sections:
            return "\n\n".join(sections) + f"\n\nModo de resposta: {thinking_mode}. {mode_hint}"
        if "lista" in normalized:
            return (
                "Em Python, uma lista é criada usando colchetes.\n\n"
                "```python\n"
                "numbers = [1, 2, 3]\n"
                'names = ["Ana", "Bruno", "Carla"]\n'
                'names.append("Daniel")\n'
                "print(names[0])\n"
                "```\n\n"
                "Listas preservam ordem, aceitam itens repetidos e são mutáveis. "
                f"Modo de resposta: {thinking_mode}. {mode_hint}"
            )
        return (
            "Posso ajudar com Python, Flask, SQLAlchemy, testes e arquitetura. "
            "Envie o trecho de código, erro ou objetivo, e eu respondo em português "
            f"com foco prático. Modo de resposta: {thinking_mode}. {mode_hint}"
        )


class LangChainOpenAIGateway(ChatCompletionGateway):
    """Gateway for any OpenAI-compatible endpoint (OpenAI, HF router/DeepSeek).

    Imported lazily so tests do not require LangChain.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.provider = provider or ("openai_compatible" if base_url else "openai")

    @traceable_if_enabled("chat.langchain_openai", run_type="llm")
    def answer(
        self,
        question: str,
        thinking_mode: str,
        book_context: list[Book] | None = None,
        history: list[dict[str, str]] | None = None,
        attachment_context: str | None = None,
    ) -> str:
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on optional packages
            raise RuntimeError("Dependências LangChain/OpenAI não instaladas.") from exc

        llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=chat_gateway_timeout_seconds(),
            **chat_model_kwargs(self.model, thinking_mode),
        )
        prompt = build_prompt_messages(
            question=question,
            thinking_mode=thinking_mode,
            book_context_text=format_book_context(book_context or []),
            history=history or [],
            attachment_context=attachment_context,
        )
        lc_messages = []
        for role, content in prompt:
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))
        response = llm.invoke(lc_messages)
        content = extract_ai_message_content(response)
        finish_reason = (getattr(response, "response_metadata", None) or {}).get("finish_reason")
        if finish_reason == "length":
            logger.warning(
                "Resposta truncada pelo limite de tokens (model=%s, max_tokens=%s)",
                self.model,
                chat_max_output_tokens(),
            )
            content = f"{content.rstrip()}{TRUNCATION_NOTICE}"
        return content


def chat_max_output_tokens() -> int:
    """Resolve output token cap from Flask config or env."""
    raw = _gateway_setting("CHAT_MAX_OUTPUT_TOKENS", str(DEFAULT_CHAT_MAX_OUTPUT_TOKENS))
    try:
        parsed = int(raw)
    except ValueError:
        parsed = DEFAULT_CHAT_MAX_OUTPUT_TOKENS
    return max(256, min(parsed, 128_000))


def chat_gateway_timeout_seconds() -> int:
    """Resolve the LLM request timeout from Flask config or env.

    Without an explicit timeout, a slow or hung provider call blocks the
    request indefinitely — this bounds it to a controlled failure instead.
    """
    raw = _gateway_setting(
        "CHAT_GATEWAY_TIMEOUT_SECONDS", str(DEFAULT_CHAT_GATEWAY_TIMEOUT_SECONDS)
    )
    try:
        parsed = int(raw)
    except ValueError:
        parsed = DEFAULT_CHAT_GATEWAY_TIMEOUT_SECONDS
    return max(1, min(parsed, 300))


def chat_max_message_chars() -> int:
    """Resolve the per-message input cap from Flask config or env.

    Protects against forwarding oversized prompts to the LLM — previously
    only the global 10MB Flask MAX_CONTENT_LENGTH bounded a single message.
    """
    raw = _gateway_setting("CHAT_MAX_MESSAGE_CHARS", str(DEFAULT_CHAT_MAX_MESSAGE_CHARS))
    try:
        parsed = int(raw)
    except ValueError:
        parsed = DEFAULT_CHAT_MAX_MESSAGE_CHARS
    return max(1, parsed)


def extract_ai_message_content(response: object) -> str:
    """Normalize LangChain AIMessage content (str or block list) to plain text."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def chat_model_kwargs(model: str, thinking_mode: str) -> dict[str, object]:
    """Build per-model kwargs: reasoning models reject temperature and vice-versa."""
    kwargs: dict[str, object] = {"max_tokens": chat_max_output_tokens()}
    normalized = model.lower()
    if "deepseek" in normalized:
        # Recomendação oficial do DeepSeek V4; thinking mode vira instrução de prompt.
        kwargs["temperature"] = 1.0
        return kwargs
    mode = THINKING_MODES[thinking_mode]
    if normalized.startswith(REASONING_MODEL_PREFIXES):
        kwargs["reasoning_effort"] = str(mode["reasoning_effort"])
        return kwargs
    kwargs["temperature"] = float(mode["temperature"])
    return kwargs


def build_prompt_messages(
    *,
    question: str,
    thinking_mode: str,
    book_context_text: str,
    history: list[dict[str, str]],
    attachment_context: str | None = None,
) -> list[tuple[str, str]]:
    """Assemble the (role, content) prompt: system + previous turns + current question."""
    mode = THINKING_MODES[thinking_mode]
    messages: list[tuple[str, str]] = [
        (
            "system",
            f"{SYSTEM_PROMPT}\n{mode['instruction']}\n"
            "Quando houver contexto de livros, cite somente dados presentes "
            "na biblioteca local e informe a fonte/id.",
        )
    ]
    for turn in history:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append((role, turn.get("content", "")))

    final_parts = [book_context_text]
    if attachment_context:
        final_parts.append(f"Anexos enviados pelo usuário:\n{attachment_context}")
    final_parts.append(f"Pergunta: {question}")
    messages.append(("user", "\n\n".join(final_parts)))
    return messages


def _gateway_setting(name: str, default: str = "") -> str:
    if has_app_context():
        return str(current_app.config.get(name, default))
    import os

    return os.getenv(name, default)


def _effective_api_key(value: str) -> str:
    """Ignore empty values and template placeholders from .env.example."""
    normalized = value.strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered in {
        "replace-me",
        "change-me",
        "change-me-in-production",
        "your-api-key",
        "your-key-here",
    }:
        return ""
    if lowered.startswith("replace-"):
        return ""
    return normalized


def _allowed_chat_models(hf_model: str, openai_model: str) -> set[str]:
    """Models a client is allowed to request explicitly.

    Without an explicit ALLOWED_CHAT_MODELS, only the operator's own
    configured defaults are allowed — closes the abuse vector where any
    caller could pick an arbitrary (and possibly expensive) model billed to
    the operator's API key.
    """
    raw = _gateway_setting("ALLOWED_CHAT_MODELS", "")
    configured = {item.strip() for item in raw.split(",") if item.strip()}
    if configured:
        return configured
    return {hf_model, openai_model}


def build_chat_gateway(model: str | None = None) -> ChatCompletionGateway:
    gateway_mode = _gateway_setting("CHAT_GATEWAY", "local").lower()
    openai_key = _effective_api_key(_gateway_setting("OPENAI_API_KEY"))
    openai_model = _gateway_setting("OPENAI_MODEL", "gpt-4.1-mini")
    hf_key = _effective_api_key(_gateway_setting("HUGGINGFACE_API_KEY"))
    hf_model = _gateway_setting("HF_CHAT_MODEL", DEFAULT_HF_CHAT_MODEL)
    hf_base_url = _gateway_setting("HF_BASE_URL", HF_ROUTER_BASE_URL)

    if gateway_mode not in {"local", "auto", "openai", "huggingface"}:
        raise ValueError("CHAT_GATEWAY deve ser local, auto, openai ou huggingface.")
    if gateway_mode == "local":
        return LocalPythonAssistantGateway()

    requested = (model or "").strip() or None
    if requested and requested not in _allowed_chat_models(hf_model, openai_model):
        raise ValidationError(
            f"Modelo '{requested}' não está na lista de modelos permitidos.", field="model"
        )
    # Modelos namespaced (ex.: deepseek-ai/DeepSeek-V4-Flash) vão pelo router do HF.
    is_hub_model = bool(requested and "/" in requested)

    if gateway_mode == "huggingface" or is_hub_model:
        if not hf_key:
            if gateway_mode == "auto":
                return LocalPythonAssistantGateway()
            raise ValueError(
                "HUGGINGFACE_API_KEY é obrigatório para usar modelos via Hugging Face."
            )
        return LangChainOpenAIGateway(
            model=requested if is_hub_model else hf_model,
            api_key=hf_key,
            base_url=hf_base_url,
            provider="huggingface",
        )

    if gateway_mode == "openai" or requested:
        if openai_key:
            return LangChainOpenAIGateway(model=requested or openai_model, api_key=openai_key)
        if gateway_mode == "openai":
            raise ValueError("OPENAI_API_KEY é obrigatório quando CHAT_GATEWAY=openai.")

    # auto: prioriza Hugging Face (DeepSeek), depois OpenAI, depois local.
    if hf_key:
        return LangChainOpenAIGateway(
            model=hf_model,
            api_key=hf_key,
            base_url=hf_base_url,
            provider="huggingface",
        )
    if openai_key:
        return LangChainOpenAIGateway(model=openai_model, api_key=openai_key)
    return LocalPythonAssistantGateway()


def normalize_thinking_mode(value: str | None) -> str:
    if not value:
        return "balanced"
    normalized = value.strip().lower()
    if normalized not in THINKING_MODES:
        raise ValidationError(
            "thinking_mode deve ser fast, balanced ou deep.", field="thinking_mode"
        )
    return normalized


class ChatService:
    def __init__(
        self,
        repository: ChatRepository | None = None,
        gateway: ChatCompletionGateway | None = None,
        book_repository: BookRepository | None = None,
        model: str | None = None,
    ) -> None:
        self.repository = repository or ChatRepository()
        self.gateway = gateway or build_chat_gateway(model)
        self.book_repository = book_repository or BookRepository()

    def create_session(self, title: str = "Nova conversa"):
        session = self.repository.create_session(title)
        db.session.commit()
        return session

    def delete_session(self, session_id: str) -> None:
        session = self.repository.get_session(session_id)
        if not session:
            raise NotFoundError("Sessão de chat não encontrada.")
        attachment_paths = [Path(attachment.storage_path) for attachment in session.attachments]
        if not self.repository.delete_session(session_id):
            raise NotFoundError("Sessão de chat não encontrada.")
        db.session.commit()

        for path in attachment_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Não foi possível remover anexo %s", path, exc_info=True)

    def update_session(self, session_id: str, *, pinned: bool) -> object:
        session = self.repository.update_session(session_id, pinned=pinned)
        if not session:
            raise NotFoundError("Sessão de chat não encontrada.")
        db.session.commit()
        return session

    @traceable_if_enabled("chat.ask", run_type="chain")
    def ask(
        self,
        *,
        session_id: str,
        content: str,
        thinking_mode: str | None,
        attachment_ids: list[str] | None = None,
    ) -> tuple[object, object]:
        if not self.repository.get_session(session_id):
            raise NotFoundError("Sessão de chat não encontrada.")
        if not content.strip() and not attachment_ids:
            raise ValidationError(
                "Campo content é obrigatório quando não há anexos.", field="content"
            )
        max_chars = chat_max_message_chars()
        if len(content) > max_chars:
            raise ValidationError(
                f"Campo content excede o limite de {max_chars} caracteres.", field="content"
            )

        mode = normalize_thinking_mode(thinking_mode)
        attachments = self._validated_attachments(attachment_ids or [], session_id)
        history = [
            {"role": message.role, "content": message.content}
            for message in self.repository.list_messages(session_id)[-HISTORY_LIMIT:]
        ]

        user_message = self.repository.create_message(
            session_id=session_id,
            role="user",
            content=content.strip(),
            thinking_mode=mode,
        )
        if attachments:
            self.repository.attach_to_message(
                [attachment.id for attachment in attachments], user_message.id
            )

        book_context = self._book_context(content, history)
        attachment_context = format_attachment_context(attachments)
        gateway_started_at = time.perf_counter()
        try:
            answer = self.gateway.answer(
                content,
                mode,
                book_context=book_context,
                history=history,
                attachment_context=attachment_context,
            )
            status = "completed"
            gateway_outcome = "success"
        except Exception:
            logger.exception("Falha ao gerar resposta da IA para a sessão %s", session_id)
            answer = GATEWAY_FAILURE_MESSAGE
            status = "failed"
            gateway_outcome = "failure"
        record_gateway_call(
            provider=getattr(self.gateway, "provider", "custom"),
            outcome=gateway_outcome,
            duration_seconds=time.perf_counter() - gateway_started_at,
        )
        trace_id = current_run_id()
        assistant_message = self.repository.create_message(
            session_id=session_id,
            role="assistant",
            content=answer,
            thinking_mode=mode,
            status=status,
            trace_id=trace_id,
        )
        # Single commit for the whole use case: user message + attachment
        # linking + assistant message land together or not at all — a
        # mid-sequence failure (before this point) rolls everything back
        # instead of leaving a partially-persisted conversation.
        db.session.commit()
        return user_message, assistant_message

    def _validated_attachments(
        self, attachment_ids: list[str], session_id: str
    ) -> list[Attachment]:
        if not attachment_ids:
            return []
        max_attachments = int(current_app.config["MAX_ATTACHMENTS_PER_MESSAGE"])
        if len(attachment_ids) > max_attachments:
            raise ValidationError(
                f"Uma mensagem aceita no máximo {max_attachments} anexos.",
                field="attachment_ids",
            )
        attachments = self.repository.find_attachments(attachment_ids)
        found_ids = {attachment.id for attachment in attachments}
        if len(found_ids) != len(set(attachment_ids)) or any(
            attachment.session_id != session_id or attachment.message_id is not None
            for attachment in attachments
        ):
            raise ValidationError("Anexos inválidos para esta sessão.", field="attachment_ids")
        return attachments

    def _book_context(self, content: str, history: list[dict[str, str]]) -> list[Book]:
        book_context = self.book_repository.relevant_for_question(content)
        if book_context:
            return book_context
        # Follow-up sem termos próprios: reusa as últimas perguntas do usuário.
        previous_questions = [
            turn["content"] for turn in reversed(history) if turn["role"] == "user"
        ]
        for question in previous_questions[:HISTORY_BOOK_FALLBACK_TURNS]:
            book_context = self.book_repository.relevant_for_question(question)
            if book_context:
                return book_context
        return []


def format_attachment_context(attachments: list[Attachment]) -> str | None:
    if not attachments:
        return None
    blocks = []
    for attachment in attachments:
        text = read_attachment_text(attachment)
        if text:
            blocks.append(f"Anexo: {attachment.filename}\nConteúdo:\n{text}")
        else:
            blocks.append(
                f"Anexo: {attachment.filename} ({attachment.kind}) "
                "sem extração de texto disponível."
            )
    return "\n\n".join(blocks)


def format_book_context(books: list[Book]) -> str:
    if not books:
        return "Contexto de livros: nenhum livro relevante encontrado na biblioteca local."
    blocks = [
        "\n".join(
            [
                f"Livro id: {book.id}",
                f"Título: {book.title}",
                f"Categoria: {book.category}",
                f"Autor: {book.author}",
                f"Data de publicação: {book.publication_date.isoformat()}",
                f"Resumo: {book.summary}",
            ]
        )
        for book in books
    ]
    return "Contexto de livros da biblioteca local:\n\n" + "\n\n".join(blocks)
