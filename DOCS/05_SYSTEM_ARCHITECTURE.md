# Arquitetura do sistema

## Visao geral

MindSight AI segue uma arquitetura fullstack simples, adequada para MVP:

- Frontend React/Vite consome API REST e renderiza chat/biblioteca.
- Backend Flask expoe endpoints versionados em `/api/v1`.
- Servicos de aplicacao concentram regras de chat, livros, uploads e busca.
- SQLAlchemy persiste sessoes, mensagens, livros e anexos em SQLite.
- Gateways opcionais integram OpenAI, Hugging Face e LangSmith.

```mermaid
flowchart LR
  U[Usuario] --> FE[Frontend React + Vite]
  FE -->|REST / JSON| API[Flask API /api/v1]
  FE -->|SSE simulado| API
  API --> R[Routes]
  R --> S[Services]
  S --> Repo[Repositories]
  Repo --> DB[(SQLite)]
  S --> FS[(Storage uploads)]
  S --> LLM[OpenAI / Hugging Face via LangChain]
  S --> LS[LangSmith opcional]
  S --> SS[Semantic Search local]
```

## Containers

```mermaid
flowchart TB
  subgraph Browser
    App[React App]
    Query[TanStack Query cache]
  end

  subgraph Backend
    Flask[Flask app factory]
    Routes[Blueprints HTTP]
    Services[Application services]
    Repos[SQLAlchemy repositories]
  end

  subgraph Data
    SQLite[(app.db)]
    Uploads[(storage/uploads)]
    HashDocs[(6 documentos + hashing local)]
  end

  subgraph External
    OpenAI[OpenAI API]
    HF[Hugging Face Router]
    LangSmith[LangSmith tracing/feedback]
  end

  App --> Query
  Query --> Routes
  Routes --> Services
  Services --> Repos
  Repos --> SQLite
  Services --> Uploads
  Services --> OpenAI
  Services --> HF
  Services --> LangSmith
  Services --> HashDocs
```

## Camadas backend

| Camada | Arquivos | Responsabilidade |
| --- | --- | --- |
| App factory | `backend/app/__init__.py` | Criar Flask app, registrar blueprints, inicializar extensoes e handlers. |
| Rotas | `backend/app/routes/*.py` | Traduzir HTTP em chamadas de servico e respostas JSON. |
| Servicos | `backend/app/services/*.py` | Regras de negocio, gateways, upload, importacao e busca. |
| Repositorios | `backend/app/repositories.py` | Persistencia SQLAlchemy e queries. |
| Modelos | `backend/app/models.py` | Entidades `Book`, `ChatSession`, `ChatMessage`, `Attachment`. |
| Config | `backend/app/config.py`, `env_loader.py` | Variaveis de ambiente, paths e configuracoes por ambiente. |

## Fluxo de chat

```mermaid
sequenceDiagram
  actor User
  participant UI as React UI
  participant API as Flask /chat/messages
  participant Chat as ChatService
  participant Repo as ChatRepository
  participant Books as BookRepository
  participant Files as UploadService
  participant LLM as Gateway LLM/local

  User->>UI: Envia pergunta/anexos
  UI->>API: POST /chat/messages
  API->>Chat: ask(session, content, mode, attachments)
  Chat->>Repo: valida sessao e historico
  Chat->>Repo: cria mensagem user
  Chat->>Books: busca livros relevantes
  Chat->>Files: extrai texto dos anexos
  Chat->>LLM: answer(prompt, history, context)
  LLM-->>Chat: resposta ou erro
  Chat->>Repo: cria mensagem assistant
  API-->>UI: IDs, status e mensagem
```

Observacao: o endpoint SSE atual nao transmite tokens reais do provedor; ele faz split da mensagem persistida e emite tokens simulados.

## Fluxo de upload/anexos

```mermaid
flowchart TD
  A[Usuario seleciona arquivo] --> B[Frontend valida tamanho e extensao]
  B --> C[POST /attachments multipart]
  C --> D[Backend valida sessao, kind, extensao]
  D --> E[Salva arquivo em storage/uploads]
  E --> F[Persiste Attachment]
  F --> G[POST /chat/messages com attachment_ids]
  G --> H[ChatService associa anexos a mensagem]
  H --> I[Extrai texto quando documento suportado]
```

Risco atual: upload e envio de mensagem nao sao uma unica transacao. O cliente remove uploads remotos em falhas conhecidas e restaura os arquivos locais para retry; o backend tambem impede reutilizar um anexo ja vinculado. Um crash/abandono ainda pode deixar orfao, pois nao ha job de backstop.

## Fluxo de importacao de livro

```mermaid
flowchart TD
  A[Upload TXT/MD/JSON/PDF] --> B[BookImportService]
  B --> C{Extensao}
  C -->|PDF| D[pypdf extract_text]
  C -->|Texto/JSON| E[decode UTF-8]
  D --> F[BookMetadataExtractor heuristico]
  E --> F
  F --> G[BookService valida payload]
  G --> H[BookRepository cria Book]
```

## Modelo de dados

```mermaid
erDiagram
  BOOK {
    string id PK
    string title
    string category
    string author
    date publication_date
    text summary
    datetime created_at
  }

  CHAT_SESSION {
    string id PK
    string title
    boolean pinned
    datetime pinned_at
    datetime created_at
    datetime updated_at
  }

  CHAT_MESSAGE {
    string id PK
    string session_id FK
    string role
    text content
    string thinking_mode
    string status
    string trace_id
    datetime created_at
  }

  ATTACHMENT {
    string id PK
    string session_id FK
    string message_id FK
    string filename
    string mime_type
    int size
    string kind
    string storage_path
    datetime created_at
  }

  CHAT_SESSION ||--o{ CHAT_MESSAGE : has
  CHAT_SESSION ||--o{ ATTACHMENT : has
  CHAT_MESSAGE ||--o{ ATTACHMENT : links
```

## Frontend

| Area | Arquivos | Responsabilidade |
| --- | --- | --- |
| Raiz de composicao | `frontend/src/App.tsx` | Coordena queries/mutacoes, selecao de view e composicao das features. |
| API client | `frontend/src/shared/api/client.ts` | Chamadas REST e tratamento basico de erro. |
| Credencial runtime | `frontend/src/shared/api/credentials.ts` | Mantem a API key apenas na sessao do navegador. |
| Tipos | `frontend/src/shared/api/types.ts` | Contratos TypeScript usados pela UI. |
| Chat | `frontend/src/features/chat/*` | Sidebar, header, conversa, composer, Markdown, anexos, audio e gestos. |
| Livros | `frontend/src/features/books/*` | Administracao, importacao, filtros e cards. |
| Configuracoes | `frontend/src/features/settings/*` | Tema, modelos, thinking mode e credencial de sessao. |
| UI base | `frontend/src/components/ui/*` | Botao, textarea e badge. |
| Estilo | `frontend/src/app/styles/globals.css` | Tokens Tailwind, temas e estilos Markdown. |

O primeiro corte reduziu `App.tsx` de cerca de 1.550 para 462 linhas fisicas. O proximo corte, se a complexidade crescer, e extrair hooks controladores para sessoes, envio de mensagens e anexos; componentes visuais de chat, livros e configuracoes ja estao separados.
