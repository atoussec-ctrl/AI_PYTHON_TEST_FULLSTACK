# MindSight AI

Assistente fullstack de chat com IA focado em **Python**, com biblioteca virtual de livros, busca semântica demonstrativa e interface moderna inspirada em aplicações de chat com IA.

O projeto atende aos requisitos de uma prova backend: API REST em Flask, gateway de chat com LangChain/OpenAI ou Hugging Face, observabilidade opcional com LangSmith e frontend React consumindo a API. O estado real e as limitações estão registrados na [auditoria de arquitetura](DOCS/37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md).

---

## Índice

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Stack tecnológica](#stack-tecnológica)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Pré-requisitos](#pré-requisitos)
- [Quick Start](#quick-start)
- [Como clonar](#como-clonar)
- [Configuração de ambiente](#configuração-de-ambiente)
- [Como rodar](#como-rodar)
- [Como testar](#como-testar)
- [API REST](#api-rest)
- [Documentação adicional](#documentação-adicional)
- [Utilitários](#utilitários)
- [Solução de problemas](#solução-de-problemas)
- [Licença](#licença)

---

## Visão geral

**MindSight AI** é um monorepo com backend Flask e frontend Vite/React. O assistente responde perguntas sobre programação Python, usa a biblioteca local de livros como contexto quando relevante, aceita anexos (documentos, imagens e áudio) e persiste conversas em SQLite.

O gateway de IA suporta três modos de operação:

| Modo | Descrição |
|------|-----------|
| `local` | Respostas determinísticas — ideal para desenvolvimento e CI, sem chave de API |
| `openai` | Integração com modelos OpenAI via LangChain |
| `auto` | Prioriza Hugging Face (DeepSeek) → OpenAI → fallback local |

---

## Funcionalidades

### Chat com IA

- Conversas com histórico persistido por sessão
- Reprodução progressiva via Server-Sent Events (SSE) de uma resposta já concluída pelo provedor
- Modos de raciocínio: **rápido**, **equilibrado** e **profundo**
- Seleção de modelo (OpenAI, DeepSeek via Hugging Face, etc.)
- Renderização de Markdown com blocos de código e botão copiar
- Feedback de respostas integrado ao LangSmith (opcional)
- Fixar/desafixar conversas na sidebar
- Exclusão de sessões (incluindo gesto swipe no mobile)

### Biblioteca virtual

- Cadastro manual de livros (título, categoria, autor, ano, resumo)
- Importação de livros por upload (PDF, TXT, Markdown) com extração assistida
- Busca por título, autor, categoria ou texto livre
- Contexto de livros injetado automaticamente no chat quando a pergunta menciona o acervo

### Busca semântica

- Endpoint demonstrativo `POST /api/v1/semantic-search`
- Vetores locais determinísticos por hashing sobre seis documentos fixos
- O extra `requirements-ai.txt` instala dependências para uma evolução futura com FAISS/Sentence Transformers; o endpoint atual ainda não usa esse índice

### Anexos

- Upload de documentos, imagens e áudio
- Gravação de áudio via `MediaRecorder` no navegador
- Validação de tipo e tamanho no frontend e backend
- Texto extraído de anexos usado como contexto na resposta da IA
- Envio multipart atômico: arquivos, vínculo e mensagens compartilham a unidade de trabalho
- Backstop idempotente para órfãos de crash/abandono (`flask cleanup-uploads`)

### Operação

- Métricas Prometheus em `GET /metrics`, protegidas pela API key quando configurada
- Contadores e histogramas HTTP/gateway com labels de cardinalidade limitada
- Agregação multiprocess pronta para os dois workers Gunicorn do container

### Interface

- Layout responsivo (desktop, tablet e mobile)
- Sidebar com agrupamento de sessões e drawer no mobile
- Tema claro/escuro persistido em `localStorage`
- Tela de administração de livros
- Animações com Framer Motion

---

## Arquitetura

```
Usuário
  ↓
Frontend (React + Vite + TypeScript)
  ↓ REST / SSE (reprodução da resposta persistida)
Backend Flask (API /api/v1)
  ↓
Serviços de aplicação (chat, livros, uploads, busca semântica)
  ↓
Infraestrutura
  ├── SQLite (SQLAlchemy)
  ├── OpenAI / Hugging Face (LangChain)
  ├── LangSmith (tracing opcional)
  └── Hashing local (busca demonstrativa; FAISS é evolução futura)
```

**Modelos de dados:** `Book`, `ChatSession`, `ChatMessage`, `Attachment`

**Camadas backend:**

- `routes/` — blueprints Flask (HTTP)
- `services/` — regras de negócio e gateways de IA
- `repositories.py` — persistência
- `models.py` — entidades SQLAlchemy

**Frontend:**

- `App.tsx` — composição e coordenação dos fluxos principais
- `features/chat/` — sidebar, cabeçalho, conversa, composer, hooks e configuração
- `features/books/` — administração e cards de livros
- `features/settings/` — preferências e credencial de sessão
- `shared/api/` — cliente HTTP e tipos
- `components/ui/` — componentes base (estilo shadcn/ui)

---

## Stack tecnológica

### Backend

| Tecnologia | Uso |
|------------|-----|
| Python 3.12+ | Runtime |
| Flask 3.x | Framework web |
| Flask-SQLAlchemy | ORM |
| SQLite | Banco de dados |
| Validadores internos | Validação de payloads HTTP e regras de entrada |
| LangChain + LangChain-OpenAI | Integração com LLMs |
| LangSmith | Tracing e feedback |
| OpenAI API | Modelos GPT |
| Hugging Face Inference | DeepSeek e modelos compatíveis |
| FAISS + Sentence Transformers | Busca semântica (opcional) |
| pypdf | Extração de texto de PDFs |
| pytest + Ruff | Testes e lint |

### Frontend

| Tecnologia | Uso |
|------------|-----|
| React 19 | UI |
| TypeScript 6 | Tipagem |
| Vite 8 | Build e dev server |
| Tailwind CSS 4 | Estilos |
| TanStack Query | Estado servidor / cache |
| Framer Motion | Animações |
| react-markdown + remark-gfm | Renderização Markdown |
| Vitest + Testing Library | Testes unitários |
| Playwright | Testes E2E |
| Storybook | Documentação de componentes |
| lucide-react | Ícones |

### DevOps

| Tecnologia | Uso |
|------------|-----|
| Docker Compose | Orquestração local |
| Makefile | Automação de tarefas |

---

## Estrutura do repositório

```
mindsight/
├── backend/
│   ├── app/
│   │   ├── routes/          # Endpoints REST
│   │   ├── services/        # Lógica de negócio
│   │   ├── models.py        # Modelos SQLAlchemy
│   │   ├── repositories.py  # Acesso a dados
│   │   └── config.py        # Configurações por ambiente
│   ├── tests/               # Testes pytest com gate global de cobertura
│   ├── openapi.json         # Contrato exportado e verificado contra a spec executável
│   ├── storage/             # SQLite e uploads; path FAISS reservado
│   ├── pyproject.toml       # Fonte única de dependências e configuração Python
│   ├── requirements*.txt    # Wrappers de compatibilidade para os extras
│   ├── run.py               # Entry-point do servidor
│   └── seed.py              # Seed do catálogo de livros
├── frontend/
│   ├── src/
│   │   ├── App.tsx          # Raiz de composição
│   │   ├── features/        # Chat, livros e configurações
│   │   ├── shared/          # API client, utils, tipos
│   │   └── components/ui/   # Componentes base
│   ├── e2e/                 # Testes Playwright
│   └── package.json
├── DOCS/                    # Documentação técnica detalhada
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

---

## Pré-requisitos

| Ferramenta | Versão mínima | Observação |
|------------|---------------|------------|
| Python | 3.12+ | Com suporte a `venv` |
| Node.js | 20+ (recomendado 24) | Inclui Corepack para `pnpm` |
| pnpm | 10.34.5 | Fixado em `frontend/package.json` e alinhado entre Docker/CI/local |
| Make | 4+ | Automação dos comandos abaixo |
| Git | recente | Clone e versionamento |
| curl | recente | Fallback do Makefile para bootstrap do pip |

**Ubuntu/Debian — pacote do venv (recomendado):**

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip make curl
# Use a versão do Python instalada, por exemplo:
# sudo apt install -y python3.12-venv
```

Sem `python3-venv`, o `make install` ainda tenta um fallback (`venv --without-pip` + `get-pip.py`), mas instalar o pacote acima é mais simples.

**Opcional:**

- Docker e Docker Compose — ambiente containerizado
- Chromium do Playwright — instalado com `pnpm exec playwright install chromium`
- Chave `OPENAI_API_KEY` — respostas reais via OpenAI
- Chave `HUGGINGFACE_API_KEY` — modelos DeepSeek via Hugging Face
- Chave `LANGSMITH_API_KEY` — tracing (`LANGSMITH_TRACING=true`)

**Portas usadas localmente:**

| Porta | Serviço |
|-------|---------|
| 5000 | Backend Flask |
| 3002 | Frontend Vite (`strictPort`) |
| 6006 | Storybook (opcional) |

---

## Quick Start

Fluxo mínimo testado em clone limpo — funciona **sem chaves de API**:

```bash
git clone https://github.com/atoussec-ctrl/AI_PYTHON_TEST_FULLSTACK.git mindsight
cd mindsight
cp .env.example .env
make install
make seed
make dev
```

Abra http://localhost:3002, envie uma pergunta sobre Python e confirme a resposta.

Verifique o backend:

```bash
curl -s http://localhost:5000/api/v1/health
```

Consulte as métricas e simule a limpeza segura de uploads antigos:

```bash
curl -s http://localhost:5000/metrics
make uploads-cleanup-dry-run
```

Rodar a suíte de testes:

```bash
make test
```

> O `.env.example` já vem com `CHAT_GATEWAY=local` e chaves vazias. Placeholders como `replace-me` são ignorados pelo backend.

---

## Como clonar

```bash
git clone https://github.com/atoussec-ctrl/AI_PYTHON_TEST_FULLSTACK.git mindsight
cd mindsight
```

---

## Configuração de ambiente

1. Copie o template:

```bash
cp .env.example .env
```

2. Para o **primeiro run**, o `.env.example` já está pronto para desenvolvimento local:
   - `CHAT_GATEWAY=local` — respostas determinísticas, sem API externa
   - chaves de API vazias

3. Para **IA real**, edite `.env`:

```bash
# OpenAI
OPENAI_API_KEY=sua-chave-real
OPENAI_MODEL=gpt-4.1-mini
CHAT_GATEWAY=openai

# ou Hugging Face (DeepSeek) — auto tenta HF -> OpenAI -> local
HUGGINGFACE_API_KEY=sua-chave-real
HF_CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
CHAT_GATEWAY=auto
```

Se expuser modelos adicionais na UI, mantenha `VITE_CHAT_MODELS` e `ALLOWED_CHAT_MODELS` alinhados. O backend rejeita modelos não autorizados para evitar consumo acidental de modelos caros.

Se `API_KEY` estiver configurada, informe-a no campo **Credencial da API** da tela de configurações. Ela fica apenas em `sessionStorage`; nunca use `VITE_API_KEY`, pois variáveis `VITE_*` são incorporadas ao bundle público. Para uma aplicação pública ou multiusuário, use autenticação por usuário e um proxy/BFF — a chave compartilhada atual não implementa identidade nem propriedade dos dados.

4. (Opcional) Dependências extras de IA/RAG:

```bash
make backend-install-ai
```

---

## Como rodar

### Opção 1 — Makefile (recomendado)

Instalar dependências:

```bash
make install
```

Popular o catálogo inicial de livros:

```bash
make seed
```

Subir backend e frontend em paralelo:

```bash
make dev
```

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3002 |
| Backend API | http://localhost:5000/api/v1 |
| Health check | http://localhost:5000/api/v1/health |
| OpenAPI / Swagger | http://localhost:5000/docs |

Rodar apenas um serviço:

```bash
make backend-dev   # Flask na porta 5000
make frontend-dev  # Vite na porta 3002
```

### Opção 2 — Manual

**Backend:**

```bash
cd backend
python3 -m venv .venv
python3 -m pip --python .venv install -r requirements.txt
.venv/bin/python run.py
```

**Frontend:**

```bash
cd frontend
pnpm install
pnpm dev
```

O Vite faz proxy de `/api` para `http://localhost:5000` automaticamente.

### Opção 3 — Docker Compose

Requer `.env` na raiz (`cp .env.example .env`). Libere as portas **5000** e **3002** antes de subir.

```bash
docker compose up --build
```

- Frontend: http://localhost:3002
- Backend: http://localhost:5000
- Volume persistente para `backend/storage`

Comandos úteis:

```bash
make docker-down   # parar containers
make docker-logs     # acompanhar logs
```

---

## Como testar

### Todos os testes

```bash
make test
```

### Backend (pytest)

```bash
make backend-test
```

Com cobertura mínima de 95%:

```bash
make backend-test-cov
```

Ou manualmente:

```bash
cd backend
.venv/bin/pytest -v
.venv/bin/ruff check app tests
```

**Suíte atual:** 305 testes backend — health, validação, livros, chat, anexos atômicos, limpeza de órfãos, métricas Prometheus, segurança de arquivos/PDF, busca semântica, OpenAPI, seed, configuração, rate limiting, observabilidade e seleção de gateway. Cobertura total: **98.67%**, com gate de 95%.

### Frontend (Vitest)

```bash
make frontend-test
```

Com cobertura:

```bash
make frontend-test-cov
```

Ou manualmente:

```bash
cd frontend
pnpm test          # execução única
pnpm test:watch    # modo watch
pnpm lint
pnpm typecheck
pnpm api:check     # garante que os tipos gerados refletem backend/openapi.json
pnpm build
```

**Suíte atual:** 19 arquivos, 109 testes. Cobertura: 86.08% lines, 82.40% functions, 81.50% branches e 84.50% statements sobre todo o código executável de produção; gates de 84%, 80%, 80% e 82%, respectivamente.

### E2E (Playwright)

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:e2e
pnpm test:e2e:fullstack
```

Requisitos:

- Chromium gerenciado pelo Playwright
- Porta **3002** livre para os testes de UI; portas **3003** e **5001** livres para o smoke full-stack
- Backend instalado em `backend/.venv` para execução local do smoke

Resultado esperado: testes de UI com **5 passando / 1 pulado** (cenário mobile-only no projeto desktop) e smoke full-stack com **1 passando**.

`test:e2e` intercepta a API para validar a UI de forma rápida e determinística. `test:e2e:fullstack` sobe Vite e Flask, usa o proxy real e o gateway local, e confirma persistência em um SQLite de arquivo isolado sob `frontend/.cache`. O banco em arquivo evita interferência entre requisições concorrentes do servidor Flask que ocorreria com uma única conexão `:memory:`. O workflow `ci-fullstack.yml` executa essa jornada quando backend ou frontend mudam.

### Storybook

```bash
cd frontend
pnpm storybook
```

Abre em http://localhost:6006

### Qualidade geral

```bash
make lint       # Ruff (backend) + ESLint (frontend)
make typecheck  # compileall (backend) + tsc (frontend)
make api-check  # artefato OpenAPI + tipos TypeScript sem drift
make build      # build de produção do frontend
```

---

## API REST

Base URL da API: `http://localhost:5000/api/v1`. A documentação é uma exceção e fica na raiz do servidor.

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/health` | Health check |
| `POST` | `/books` | Cadastrar livro |
| `POST` | `/books/import` | Importar livro por upload |
| `GET` | `/books` | Listar/buscar livros |
| `GET` | `/books/{id}` | Detalhe de um livro |
| `GET` | `/chat/sessions` | Listar sessões |
| `POST` | `/chat/sessions` | Criar sessão |
| `PATCH` | `/chat/sessions/{id}` | Fixar/desafixar sessão |
| `DELETE` | `/chat/sessions/{id}` | Excluir sessão |
| `GET` | `/chat/sessions/{id}/messages` | Mensagens da sessão |
| `POST` | `/chat/messages` | Enviar mensagem em JSON ou multipart atômico com arquivos |
| `GET` | `/chat/messages/{id}/stream` | Reprodução SSE da resposta persistida |
| `POST` | `/chat/messages/{id}/feedback` | Feedback LangSmith |
| `POST` | `/attachments` | Upload de anexo |
| `GET` | `/attachments/{id}` | Download de anexo |
| `DELETE` | `/attachments/{id}` | Limpar upload legado ainda não vinculado |
| `POST` | `/semantic-search` | Busca vetorial demonstrativa por hashing |
| `GET` | `http://localhost:5000/metrics` | Métricas Prometheus |
| `GET` | `http://localhost:5000/openapi.json` | Especificação OpenAPI |
| `GET` | `http://localhost:5000/docs` | Documentação interativa |

Contrato completo em [`DOCS/06_BACKEND_FLASK_API_CONTRACT.md`](DOCS/06_BACKEND_FLASK_API_CONTRACT.md).

---

## Documentação adicional

A pasta [`DOCS/`](DOCS/) contém documentação técnica extensa:

| Documento | Conteúdo |
|-----------|----------|
| [`DOCS/00_README_FULLSTACK.md`](DOCS/00_README_FULLSTACK.md) | Visão geral do pacote de docs |
| [`DOCS/01_PRODUCT_VISION.md`](DOCS/01_PRODUCT_VISION.md) | Visão de produto e personas |
| [`DOCS/05_SYSTEM_ARCHITECTURE.md`](DOCS/05_SYSTEM_ARCHITECTURE.md) | Arquitetura e princípios SOLID |
| [`DOCS/33_IMPLEMENTATION_STATUS.md`](DOCS/33_IMPLEMENTATION_STATUS.md) | Status de implementação |
| [`DOCS/37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md`](DOCS/37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md) | Auditoria de Clean Architecture, SOLID e pirâmide de testes |
| [`DOCS/29_ENV_EXAMPLE.md`](DOCS/29_ENV_EXAMPLE.md) | Variáveis de ambiente |
| [`DOCS/30_MAKEFILE_COMMANDS.md`](DOCS/30_MAKEFILE_COMMANDS.md) | Comandos do Makefile |

---

## Utilitários

```bash
make seed         # Popular catálogo de livros (idempotente)
make db-backup    # Backup do SQLite
make db-restore   # Restaurar backup mais recente
make clean        # Limpar storage, dist e caches
```

---

## Solução de problemas

### `make install` falha ao criar o venv

**Sintoma:** `ensurepip is not available`

**Solução:**

```bash
sudo apt install -y python3-venv   # ou python3.12-venv / python3.14-venv
make install
```

O Makefile também tenta automaticamente `venv --without-pip` + bootstrap do pip.

### Chat retorna erro de IA logo após clonar

**Causa comum:** `CHAT_GATEWAY=auto` com chaves placeholder ou inválidas.

**Solução:** use `CHAT_GATEWAY=local` no `.env` (já é o default do `.env.example`).

### Porta 5000 ou 3002 em uso

**Sintoma:** `Address already in use` ou Docker `Bind for 0.0.0.0:5000 failed`

**Solução:**

```bash
ss -tlnp | grep -E ':5000|:3002'
make docker-down    # se houver containers antigos
# pare o processo listado ou encerre outra instância do projeto
```

### `pnpm: command not found`

```bash
corepack enable
corepack prepare pnpm@10.34.5 --activate
```

### Frontend sem resposta da API

Confirme que o backend está no ar e que o proxy aponta para a porta correta:

- Backend: http://localhost:5000/api/v1/health
- Dev local: Vite faz proxy de `/api` → `http://localhost:5000`

### Testes E2E falham

Execute `pnpm exec playwright install chromium`. Se a porta 3002 estiver ocupada, libere-a antes de rodar `pnpm test:e2e`.

---

## Licença

Consulte o repositório para informações de licenciamento. Se nenhuma licença estiver definida, o código é disponibilizado apenas para fins educacionais e de avaliação técnica.
