"""Chat session and message routes."""

from __future__ import annotations

import json
import time

from flask import Blueprint, Response, current_app, jsonify, request

from app.errors import ValidationError
from app.extensions import limiter
from app.repositories import ChatRepository
from app.services.chat import ChatService
from app.services.observability import record_feedback
from app.services.uploads import UploadService
from app.utils.http import error_response, parse_pagination, validation_error
from app.validation import json_object, optional_text, required_text, string_list

chat_bp = Blueprint("chat", __name__)


def _chat_message_rate_limit() -> str:
    """Read fresh on every request (not fixed at import time) so tests can
    override RATE_LIMIT_CHAT_MESSAGES per app instance."""
    return current_app.config["RATE_LIMIT_CHAT_MESSAGES"]


@chat_bp.get("/chat/sessions")
def list_sessions():
    limit, offset = parse_pagination(request.args)
    sessions = ChatRepository().list_sessions(limit=limit, offset=offset)
    return jsonify([session.to_dict() for session in sessions])


@chat_bp.post("/chat/sessions")
def create_session():
    payload = json_object(request.get_json(silent=True))
    title = optional_text(payload, "title", default="Nova conversa")
    session = ChatService().create_session(title)
    return jsonify(session.to_dict()), 201


@chat_bp.delete("/chat/sessions/<session_id>")
def delete_session(session_id: str):
    ChatService().delete_session(session_id)
    return "", 204


@chat_bp.patch("/chat/sessions/<session_id>")
def update_session(session_id: str):
    payload = request.get_json(silent=True) or {}
    if "pinned" not in payload:
        return validation_error("Campo pinned é obrigatório.", "pinned")
    if not isinstance(payload["pinned"], bool):
        return validation_error("Campo pinned deve ser booleano.", "pinned")

    session = ChatService().update_session(session_id, pinned=payload["pinned"])
    return jsonify(session.to_dict())


@chat_bp.get("/chat/sessions/<session_id>/messages")
def list_messages(session_id: str):
    repository = ChatRepository()
    if not repository.get_session(session_id):
        return error_response("NOT_FOUND", "Sessão de chat não encontrada.", 404)
    limit, offset = parse_pagination(request.args)
    messages = repository.list_messages(session_id, limit=limit, offset=offset)
    return jsonify([message.to_dict() for message in messages])


@chat_bp.post("/chat/messages")
@limiter.limit(_chat_message_rate_limit)
def create_message():
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        # Flask 3.1 supports a view-specific body limit.  A chat may contain
        # several files, while single-file endpoints keep the stricter global
        # MAX_CONTENT_LENGTH configured by the app factory.
        request.max_content_length = (
            int(current_app.config["MAX_MESSAGE_UPLOAD_SIZE_MB"]) * 1024 * 1024
        )
        request.max_form_parts = 10 + 2 * int(current_app.config["MAX_ATTACHMENTS_PER_MESSAGE"])
        payload = request.form
        attachment_ids = string_list(request.form.getlist("attachment_ids"), "attachment_ids")
        files = request.files.getlist("files")
        attachment_kinds = request.form.getlist("attachment_kinds")
    else:
        payload = json_object(request.get_json(silent=True))
        attachment_ids = string_list(payload.get("attachment_ids"), "attachment_ids")
        files = []
        attachment_kinds = []

    session_id = required_text(payload, "session_id")
    content = optional_text(payload, "content")
    thinking_mode = optional_text(payload, "thinking_mode", default="balanced")
    model = optional_text(payload, "model").strip() or None

    if files and attachment_ids:
        raise ValidationError(
            "Use files ou attachment_ids, não ambos no mesmo envio.", field="attachments"
        )
    if attachment_kinds and len(attachment_kinds) != len(files):
        raise ValidationError(
            "Cada arquivo deve possuir um attachment_kind correspondente.",
            field="attachment_kinds",
        )

    upload_service = UploadService()
    staged = []
    if files:
        kinds = attachment_kinds or [None] * len(files)
        staged = upload_service.stage_many(
            files=files,
            session_id=session_id,
            kinds=kinds,
        )
        attachment_ids = [attachment.id for attachment in staged]

    try:
        user_message, assistant_message = ChatService(model=model).ask(
            session_id=session_id,
            content=content,
            thinking_mode=thinking_mode,
            attachment_ids=attachment_ids,
        )
    except Exception:
        if staged:
            upload_service.discard_staged(staged)
        raise

    return jsonify(
        {
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "status": assistant_message.status,
            "assistant_message": assistant_message.to_dict(),
        }
    ), 201


@chat_bp.get("/chat/messages/<assistant_message_id>/stream")
def stream_message(assistant_message_id: str):
    message = ChatRepository().get_message(assistant_message_id)
    if not message:
        return error_response("NOT_FOUND", "Mensagem não encontrada.", 404)

    def generate():
        if message.status == "failed":
            yield (
                "event: error\n"
                f"data: {json.dumps({'message_id': message.id, 'content': message.content})}\n\n"
            )
            return
        for token in message.content.split(" "):
            yield f"event: token\ndata: {json.dumps({'content': token + ' '})}\n\n"
            time.sleep(0.001)
        yield f"event: done\ndata: {json.dumps({'message_id': message.id})}\n\n"

    response = Response(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@chat_bp.post("/chat/messages/<assistant_message_id>/feedback")
def create_feedback(assistant_message_id: str):
    message = ChatRepository().get_message(assistant_message_id)
    if not message:
        return error_response("NOT_FOUND", "Mensagem não encontrada.", 404)

    payload = json_object(request.get_json(silent=True))
    try:
        score = float(payload.get("score"))
    except (TypeError, ValueError):
        return validation_error("Campo score deve ser numérico.", "score")
    if score < -1 or score > 1:
        return validation_error("Campo score deve estar entre -1 e 1.", "score")

    result = record_feedback(
        run_id=message.trace_id,
        score=score,
        key=optional_text(payload, "key", default="user_score").strip() or "user_score",
        comment=optional_text(payload, "comment").strip() or None,
    )
    return result, 202
