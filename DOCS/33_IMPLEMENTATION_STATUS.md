# Status de implementacao

Auditoria realizada em 2026-07-03. Revalidado em 2026-07-24 apos o hardening de entradas, modularizacao do frontend e revisao completa dos gates de teste.

## Backend

| Area | Status | Observacoes |
| --- | --- | --- |
| App factory Flask | Implementado | `create_app` registra blueprints, CORS e handlers. |
| Health check | Implementado | `/health` e `/api/v1/health`. |
| Livros | Implementado | Criacao, listagem, busca e detalhe. |
| Importacao de livros | Implementado | TXT/MD/JSON/PDF com política comum de tipo/tamanho e limites de páginas, stream descompactado, texto e tempo cooperativo para PDF. |
| Chat | Implementado | Sessoes, mensagens, historico, contexto de livros e anexos; arquivos podem seguir no mesmo multipart atomico da mensagem. |
| SSE | Parcial | Emite playback da mensagem persistida, nao stream real do LLM. |
| Gateways IA | Parcial | Local, OpenAI-compatible, HF router; timeout e rate limit por IP em produção; sem retry com backoff. |
| LangSmith | Parcial | Tracing/feedback opcional com no-op resiliente. |
| Uploads | Implementado com ressalva | Allowlist, nome seguro, MIME/assinatura, limites, quarentena, staging transacional, compensacao e CLI idempotente de orfaos por idade. AV/CDR e isolamento preemptivo continuam condicionais a deploy publico. |
| Metricas | Implementado | `/metrics` Prometheus mede requests, status, latencia e gateway; labels sao limitadas e o container agrega workers Gunicorn. |
| Busca semantica | Demo | Hashing local; config de FAISS/embeddings ainda nao efetivada. |
| Persistencia | Implementado | SQLite + SQLAlchemy com migracoes versionadas (Alembic/Flask-Migrate). |
| Autenticacao | Implementado (minima) | Segredo compartilhado via `API_KEY`/`Authorization: Bearer`, comparacao em tempo constante e credencial de frontend apenas em `sessionStorage`; sem contas nem ownership. Adequado ao MVP single-tenant controlado, nao a um deploy publico/multiusuario. |
| WSGI de producao | Implementado | Container roda Gunicorn (`--preload` + `post_fork` para migration/engine seguros com multiplos workers), nao mais o dev server do Flask. |
| OpenAPI | Implementado | Spec executável no backend, artefato JSON verificado, nullability corrigida e tipos TypeScript gerados por `openapi-typescript`; CI bloqueia drift. |

## Frontend

| Area | Status | Observacoes |
| --- | --- | --- |
| Shell de chat | Implementado | Layout responsivo com sidebar e composer. |
| Biblioteca | Implementado | Cadastro, filtros, importacao e acao "perguntar a IA". |
| API client | Implementado | Cliente HTTP isolado e testado. |
| Markdown | Implementado | `react-markdown` com GFM, highlight e botao copiar. |
| Anexos | Implementado | Validacao local, preview e envio multipart unico; o backend assume rollback/compensacao. |
| Audio | Parcial | Grava via MediaRecorder; sem transcricao real dedicada. |
| Tema | Implementado | Claro/escuro persistido em localStorage. |
| Browser/E2E de UI | Implementado | Playwright usa Chromium gerenciado: 5 cenários passaram e 1 mobile-only foi pulado no desktop; chamadas são interceptadas para testes rápidos de UI. |
| Smoke full-stack | Implementado | Uma jornada separada sobe Flask e Vite, atravessa o proxy real, valida request ID e persiste chat/anexo/livro em SQLite de arquivo isolado; `:memory:` permanece restrito aos unitários. |
| Acessibilidade | Implementado | Drawer mobile com `role=dialog`, `aria-modal`, focus trap e Escape; pin/delete de sessão já tinha alternativa por teclado desde a Fase 1. |
| Modularidade | Implementado (primeira etapa) | `App.tsx` caiu de aproximadamente 1.550 para 462 linhas fisicas; chat, livros e configuracoes possuem componentes de feature dedicados e estao no gate real de cobertura. A raiz ainda coordena queries/mutations e pode evoluir para hooks controladores. |
| Busca de conversas | Implementado | Filtro por título na sidebar. |
| Localizacao | Implementado | Datas relativas e agrupamentos usam PT-BR; documento HTML declara `lang=pt-BR`. |
| Credencial da API | Implementado com ressalva | Informada em Configuracoes e mantida por sessao; nunca compilada em `VITE_*`. `sessionStorage` continua acessivel a JavaScript e nao substitui autenticacao de usuario/BFF. |

## Testes e verificacoes

Resultado local da auditoria:

| Comando | Resultado |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m ruff check app tests` | Passou. |
| `backend/.venv/Scripts/python.exe -m compileall app` | Passou. |
| `frontend pnpm typecheck` | Passou. |
| `frontend pnpm lint` | Passou. |
| `frontend pnpm test:coverage` | Passou: 19 arquivos, 109 testes; 86.08% lines, 82.40% functions, 81.50% branches e 84.50% statements no escopo executavel completo. |
| `frontend pnpm test:e2e` | Passou: 5; pulado: 1 mobile-only no projeto desktop. |
| `frontend pnpm test:e2e:fullstack` | Passou: 1 jornada real Browser -> Vite -> Flask -> SQLite. |
| `frontend pnpm api:check` | Passou: tipos gerados estão sincronizados com `backend/openapi.json`. |
| `backend pytest --cov=app --cov-fail-under=95` | Passou: 305 testes, 0 warnings; cobertura 98.67%. |
| `docker compose build backend frontend` | Passou para ambas as imagens. |

## Pendencias mais relevantes

1. Streaming real do provedor (hoje a rota SSE reproduz uma mensagem ja persistida).
2. Conectar a busca semantica aos livros reais ou remover a configuracao FAISS ainda inativa (hoje indexa 6 documentos fixos).
3. Tracing distribuido/OpenTelemetry e dashboards/alertas sobre as metricas ja expostas.
4. Retry com backoff no gateway de IA (timeout ja existe; falha ainda nao tenta novamente).
5. Extrair da raiz do frontend os controladores de queries/mutations caso a complexidade de produto volte a crescer.
6. Adicionar AV/CDR e executar parsing em worker/processo isolado se uploads passarem a ser públicos ou não confiáveis em escala.

Concluidas desde a auditoria original: WSGI de producao, autenticacao minima por API key, guarda de config insegura em producao, migracoes Alembic, paginacao, endpoint multipart atomico de mensagem/anexos, limpeza idempotente de orfaos, timeout do gateway de IA, rate limiting, metricas Prometheus multiprocess, validacao estrita, `request_id` correlacionado, modularizacao do frontend, localizacao PT-BR, hardening de uploads/PDF, contratos TypeScript gerados e smoke full-stack real no CI.
