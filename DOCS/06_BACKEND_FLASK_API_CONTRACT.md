# Contrato da API Flask

Base URL local: `http://localhost:5000/api/v1`

O backend tambem expoe:

- `GET /health`
- `GET /openapi.json`
- `GET /docs`

## Convencoes

Todas as respostas de erro seguem:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Mensagem legivel.",
    "details": {}
  },
  "request_id": "opcional"
}
```

Campos temporais sao retornados em ISO 8601. IDs sao strings geradas via UUID com prefixo para sessoes, mensagens e anexos.

## Endpoints versionados

Quando `API_KEY` esta preenchida, todos os endpoints abaixo exigem `Authorization: Bearer <valor>`, exceto os health checks. A chave e um segredo compartilhado, nao uma identidade de usuario.

| Metodo | Endpoint | Uso |
| --- | --- | --- |
| GET | `/health` | Health check da API versionada. |
| GET | `/books` | Lista/busca livros por titulo, autor, categoria ou `q`. |
| POST | `/books` | Cria livro manualmente. |
| POST | `/books/import` | Importa livro via TXT/MD/JSON/PDF. |
| GET | `/books/{book_id}` | Detalhe de livro. |
| GET | `/chat/sessions` | Lista sessoes de chat. |
| POST | `/chat/sessions` | Cria sessao. |
| PATCH | `/chat/sessions/{session_id}` | Atualiza metadados da sessao, hoje `pinned`. |
| DELETE | `/chat/sessions/{session_id}` | Remove sessao e registros relacionados. |
| GET | `/chat/sessions/{session_id}/messages` | Lista mensagens da sessao. |
| POST | `/chat/messages` | Envia pergunta e cria resposta. Aceita JSON legado com `attachment_ids` ou multipart atômico com arquivos. |
| GET | `/chat/messages/{assistant_message_id}/stream` | SSE simulado da mensagem ja persistida. |
| POST | `/chat/messages/{assistant_message_id}/feedback` | Envia feedback para LangSmith, se habilitado. |
| POST | `/attachments` | Upload de anexo para uma sessao. |
| GET | `/attachments/{attachment_id}` | Download de anexo. |
| DELETE | `/attachments/{attachment_id}` | Remove um anexo ainda nao vinculado a uma mensagem (cleanup apos falha no envio). Rejeita anexo ja vinculado. |
| POST | `/semantic-search` | Busca semantica local demonstrativa. |
| GET | `/metrics` | Métricas Prometheus; protegido por API key quando configurada. |

### Mensagem multipart atômica

`POST /chat/messages` aceita `multipart/form-data` com `session_id`, `content`, `thinking_mode`, `model`, campos repetidos `files` e campos repetidos `attachment_kinds`. O backend valida e faz staging de todos os arquivos, cria/vincula a mensagem e persiste a resposta em uma única transação de banco. Se validação, flush ou commit falhar, a transação sofre rollback e os arquivos já movidos são compensados.

O limite é `MAX_ATTACHMENTS_PER_MESSAGE`; cada arquivo respeita `MAX_UPLOAD_SIZE_MB` e o corpo multipart completo respeita `MAX_MESSAGE_UPLOAD_SIZE_MB`. `files` e IDs pré-enviados não podem ser combinados na mesma chamada.

O endpoint separado `POST /attachments` permanece compatível com clientes antigos. Para abandono ou crash nesse fluxo legado, execute periodicamente:

```bash
python -m flask --app run:app cleanup-uploads --dry-run
python -m flask --app run:app cleanup-uploads
```

A rotina remove somente registros não vinculados e nomes gerados pelo servidor dentro de `UPLOAD_DIR`, mais antigos que `ORPHAN_UPLOAD_MAX_AGE_HOURS`. O `DELETE` mantém os predicados de órfão no banco e nunca remove um path ainda referenciado.

### Métricas

`GET /metrics` usa o formato de exposição do Prometheus e publica:

- `mindsight_http_requests_total` por método, template de rota e status;
- `mindsight_http_request_duration_seconds` por método e template de rota;
- `mindsight_chat_gateway_calls_total` por provider e resultado;
- `mindsight_chat_gateway_duration_seconds` por provider e resultado.

IDs, URLs concretas, prompts e usuários não viram labels. No container Gunicorn, o diretório multiprocess é preparado antes do preload e agrega os dois workers.

## Modelos principais

### Book

```json
{
  "id": "book-id",
  "title": "Python Fluente",
  "category": "Programacao",
  "author": "Luciano Ramalho",
  "publication_date": "2015-01-01",
  "publication_year": 2015,
  "summary": "Resumo",
  "created_at": "2026-07-03T00:00:00Z"
}
```

### ChatSession

```json
{
  "id": "session_x",
  "title": "Nova conversa",
  "pinned": false,
  "pinned_at": null,
  "created_at": "2026-07-03T00:00:00Z",
  "updated_at": "2026-07-03T00:00:00Z"
}
```

### ChatMessage

```json
{
  "id": "msg_x",
  "session_id": "session_x",
  "role": "assistant",
  "content": "Resposta",
  "thinking_mode": "balanced",
  "status": "completed",
  "trace_id": null,
  "attachments": [],
  "created_at": "2026-07-03T00:00:00Z"
}
```

## Gaps de contrato encontrados

| Gap | Evidencia | Recomendacao |
| --- | --- | --- |
| Status de falha | Backend, OpenAPI e frontend usam `failed` para falha persistida do assistente. | Manter teste de contrato cobrindo esse enum. |
| OpenAPI e serializacao Python ainda sao manuais | O frontend deriva seus tipos de `backend/openapi.json` e o CI bloqueia drift; modelos/serializadores Python e a spec executavel ainda podem divergir semanticamente. | Manter testes de contrato sobre valores nulos/enums e, se o contrato crescer, validar respostas reais contra o schema. |
| Auth sem identidade/ownership | A API key protege o conjunto inteiro de dados com um segredo unico. | Adicionar contas/claims e ownership antes de um deploy publico/multiusuario. |
| Paginacao por offset | Listagens aceitam `limit`/`offset`, com limite maximo, mas nao retornam metadados/cursor. | Migrar para cursor e envelope quando volume/consistencia exigirem. |
| SSE nao e streaming real | Endpoint emite tokens de mensagem ja persistida. | Migrar para streaming real do gateway ou renomear como playback. |

## Criterios para manter contrato saudavel

- Cada novo endpoint deve ter teste HTTP.
- Cada schema OpenAPI deve refletir payload real serializado.
- O frontend deve consumir tipos gerados ou testados contra fixture do backend.
- Mudancas quebraveis devem ser versionadas em `/api/v2` ou protegidas por compatibilidade.
