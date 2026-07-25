"""TDD (Red → Green → Refactor) para MS-101 (multi-turn) e MS-102 (anexos como contexto).

Inclui regressões apontadas pelo Bugbot:
- anexos de outra sessão não podem ser vinculados;
- falha do LLM não pode deixar mensagem do usuário órfã;
- reasoning_effort só para modelos de reasoning.
"""

from __future__ import annotations

from io import BytesIO

from app.services.chat import (
    ChatCompletionGateway,
    ChatService,
    build_prompt_messages,
    chat_model_kwargs,
)


class RecordingGateway(ChatCompletionGateway):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def answer(
        self,
        question,
        thinking_mode,
        book_context=None,
        history=None,
        attachment_context=None,
    ) -> str:
        self.calls.append(
            {
                "question": question,
                "thinking_mode": thinking_mode,
                "book_context": book_context,
                "history": history,
                "attachment_context": attachment_context,
            }
        )
        return "resposta gravada"


class FailingGateway(ChatCompletionGateway):
    def answer(self, question, thinking_mode, book_context=None, **kwargs) -> str:
        raise RuntimeError("LLM indisponível")


# ── MS-101: histórico multi-turn ──


def test_ask_passes_previous_turns_to_gateway(app):
    with app.app_context():
        gateway = RecordingGateway()
        service = ChatService(gateway=gateway)
        session = service.create_session("multi-turn")

        service.ask(session_id=session.id, content="primeira pergunta", thinking_mode="fast")
        service.ask(session_id=session.id, content="segunda pergunta", thinking_mode="fast")

        history = gateway.calls[-1]["history"]
        assert [(turn["role"], turn["content"]) for turn in history] == [
            ("user", "primeira pergunta"),
            ("assistant", "resposta gravada"),
        ]
        # A primeira chamada não tem turnos anteriores.
        assert gateway.calls[0]["history"] == []


def test_chat_follow_up_uses_previous_question_for_book_context(client):
    client.post(
        "/api/v1/books",
        json={
            "title": "Dom Casmurro",
            "author": "Machado de Assis",
            "category": "Romance",
            "publication_year": 1899,
            "summary": "Bentinho e Capitu.",
        },
    )
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]

    first = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "Fale do livro Dom Casmurro"},
    )
    assert first.status_code == 201
    assert "dom casmurro" in first.get_json()["assistant_message"]["content"].lower()

    follow_up = client.post(
        "/api/v1/chat/messages",
        json={"session_id": session_id, "content": "Pode detalhar mais?"},
    )
    assert follow_up.status_code == 201
    answer = follow_up.get_json()["assistant_message"]["content"]
    assert "Dom Casmurro" in answer
    assert "Machado de Assis" in answer


# ── MS-102: anexos como contexto ──


def _upload(client, session_id: str, filename: str, content: bytes) -> str:
    response = client.post(
        "/api/v1/attachments",
        data={"session_id": session_id, "file": (BytesIO(content), filename)},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    return response.get_json()["id"]


def test_chat_uses_attachment_text_in_answer(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    attachment_id = _upload(
        client,
        session_id,
        "receita.txt",
        "Receita secreta: bolo de fubá com erva-doce.".encode(),
    )

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "O que diz o documento anexado?",
            "attachment_ids": [attachment_id],
        },
    )

    assert response.status_code == 201
    answer = response.get_json()["assistant_message"]["content"]
    assert "receita.txt" in answer
    assert "bolo de fubá" in answer


def test_chat_rejects_attachment_from_another_session(client):
    session_a = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    session_b = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    foreign_attachment = _upload(client, session_b, "nota.txt", b"conteudo")

    response = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_a,
            "content": "Use o anexo",
            "attachment_ids": [foreign_attachment],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_chat_rejects_reusing_an_attachment_already_linked_to_a_message(client):
    session_id = client.post("/api/v1/chat/sessions", json={}).get_json()["id"]
    attachment_id = _upload(client, session_id, "nota.txt", b"conteudo")

    first = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "Primeiro envio",
            "attachment_ids": [attachment_id],
        },
    )
    second = client.post(
        "/api/v1/chat/messages",
        json={
            "session_id": session_id,
            "content": "Tente reutilizar",
            "attachment_ids": [attachment_id],
        },
    )

    assert first.status_code == 201
    assert second.status_code == 400
    messages = client.get(f"/api/v1/chat/sessions/{session_id}/messages").get_json()
    assert messages[0]["attachments"][0]["id"] == attachment_id


# ── Falha do gateway não deixa mensagem órfã nem estoura 500 ──


def test_gateway_failure_creates_failed_assistant_message(app):
    with app.app_context():
        service = ChatService(gateway=FailingGateway())
        session = service.create_session("falha")

        user_message, assistant_message = service.ask(
            session_id=session.id, content="olá", thinking_mode="fast"
        )

        assert user_message.id is not None
        assert assistant_message.status == "failed"
        assert "não foi possível" in assistant_message.content.lower()


# ── Montagem de prompt e kwargs do modelo (unitários puros) ──


def test_chat_model_kwargs_for_non_reasoning_model(app):
    with app.app_context():
        kwargs = chat_model_kwargs("gpt-4.1-mini", "deep")
    assert "reasoning_effort" not in kwargs
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 4096


def test_chat_model_kwargs_for_reasoning_model(app):
    with app.app_context():
        kwargs = chat_model_kwargs("o3-mini", "deep")
    assert kwargs["reasoning_effort"] == "high"
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 4096


def test_build_prompt_messages_includes_history_and_attachments():
    messages = build_prompt_messages(
        question="qual o próximo passo?",
        thinking_mode="balanced",
        book_context_text="Contexto de livros: nenhum.",
        history=[
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "olá!"},
        ],
        attachment_context="Anexo: plano.txt\nConteúdo: passo um",
    )

    assert messages[0][0] == "system"
    assert messages[1] == ("user", "oi")
    assert messages[2] == ("assistant", "olá!")
    final_role, final_content = messages[-1]
    assert final_role == "user"
    assert "qual o próximo passo?" in final_content
    assert "plano.txt" in final_content
