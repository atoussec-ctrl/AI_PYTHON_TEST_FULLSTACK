# Guia de Execução — MindSight AI

Documento operacional com os comandos reais usados para instalar, lintar, testar (com cobertura), subir e validar a stack **MindSight AI** (backend Flask + frontend React/Vite) neste ambiente **Windows** (Git Bash / PowerShell). Os resultados foram revalidados em 2026-07-24.

> Para visão geral do produto, arquitetura e API, veja o [`README.md`](README.md). Este guia foca só em "como rodar".

---

## Índice

- [0. Particularidade deste ambiente (Windows)](#0-particularidade-deste-ambiente-windows)
- [1. Pré-requisitos verificados](#1-pré-requisitos-verificados)
- [2. Configuração de ambiente (.env)](#2-configuração-de-ambiente-env)
- [3. Instalação de dependências](#3-instalação-de-dependências)
- [4. Lint](#4-lint)
- [5. Typecheck](#5-typecheck)
- [6. Testes e cobertura](#6-testes-e-cobertura)
- [7. Build de produção (frontend)](#7-build-de-produção-frontend)
- [8. Subir a stack](#8-subir-a-stack)
- [9. Testar a stack em execução](#9-testar-a-stack-em-execução)
- [10. Parar os serviços](#10-parar-os-serviços)
- [11. Alternativa: Docker Compose](#11-alternativa-docker-compose)
- [12. Divergências encontradas vs. README](#12-divergências-encontradas-vs-readme)
- [13. Troubleshooting específico do Windows](#13-troubleshooting-específico-do-windows)
- [14. Bug corrigido: CHAT_GATEWAY/chaves de API não aplicados do .env](#14-bug-corrigido-chat_gatewaychaves-de-api-não-aplicados-do-env)

---

## 0. Particularidade deste ambiente (Windows)

O `Makefile` do projeto foi escrito para Linux/macOS (usa `.venv/bin/...`, `&&`/`&` de shell POSIX). Neste ambiente **o comando `make` não está instalado** (Git Bash no Windows) e a venv Python usa a pasta **`Scripts/`**, não `bin/`. Por isso, todos os comandos deste guia são a versão **manual** (equivalente a cada alvo do Makefile), rodável tanto em Git Bash quanto adaptável a PowerShell.

| Item | Linux/macOS (Makefile) | Windows (usado aqui) |
|------|------------------------|-----------------------|
| Python da venv | `backend/.venv/bin/python` | `backend/.venv/Scripts/python.exe` |
| pytest da venv | `backend/.venv/bin/pytest` | `backend/.venv/Scripts/pytest.exe` |
| ruff da venv | `backend/.venv/bin/ruff` | `backend/.venv/Scripts/ruff.exe` |
| `make dev` (paralelo) | `$(MAKE) backend-dev & $(MAKE) frontend-dev` | dois terminais/processos em background separados (seção 8) |

Se você instalar `make` no Windows (ex.: via Chocolatey `choco install make` ou WSL), os alvos do `Makefile` funcionam, mas ainda seria necessário ajustar `bin` → `Scripts` — o que o Makefile atual **não faz automaticamente** no Windows.

---

## 1. Pré-requisitos verificados

Versões confirmadas neste ambiente:

```bash
python3 --version   # Python 3.14.6  (projeto requer 3.12+)
node --version       # v24.18.0
pnpm --version       # 11.9.0
make --version       # NÃO instalado neste ambiente
```

Se `pnpm` não existir: `corepack enable && corepack prepare pnpm@10.34.5 --activate`.

---

## 2. Configuração de ambiente (.env)

```bash
cp .env.example .env
```

O `.env.example` já vem pronto para rodar **sem nenhuma chave de API**:

- `CHAT_GATEWAY=local` → respostas determinísticas (sem custo, sem chamada externa)
- `OPENAI_API_KEY` / `HUGGINGFACE_API_KEY` / `LANGSMITH_API_KEY` vazios

Para IA real, edite `.env` e defina `CHAT_GATEWAY=openai` (com `OPENAI_API_KEY`) ou `CHAT_GATEWAY=auto` (tenta Hugging Face → OpenAI → local).

---

## 3. Instalação de dependências

### Backend (Python / Flask)

```bash
cd backend
python3 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
```

Dependências opcionais para uma evolução com FAISS/Sentence Transformers — pesadas e não usadas pelo endpoint semântico demonstrativo atual:

```bash
.venv/Scripts/python.exe -m pip install -e ".[ai,dev]"
```

`pyproject.toml` é a fonte única das dependências; os arquivos `requirements*.txt` são wrappers de compatibilidade.

**Resultado obtido:** instalação concluída sem erros (Flask 3.x, SQLAlchemy, LangSmith, langchain-openai, pytest e Ruff).

### Frontend (React / Vite)

```bash
cd frontend
pnpm install
```

**Resultado obtido:** instalação com lockfile congelado concluída (React 19, Vite 8, TanStack Query, Vitest, Playwright, Storybook, ESLint e TypeScript 6).

---

## 4. Lint

### Backend (Ruff)

```bash
cd backend
.venv/Scripts/ruff.exe check .
```

**Resultado obtido:** `All checks passed!`

### Frontend (ESLint)

```bash
cd frontend
pnpm lint
```

**Resultado obtido:** nenhum erro ou warning.

---

## 5. Typecheck

### Backend (compileall — checagem de sintaxe)

```bash
cd backend
.venv/Scripts/python.exe -m compileall app
```

### Frontend (tsc)

```bash
cd frontend
pnpm typecheck
```

**Resultado obtido:** sem erros de tipo em ambos.

---

## 6. Testes e cobertura

### Backend (pytest + pytest-cov)

```bash
cd backend
.venv/Scripts/pytest.exe --cov=app --cov-report=term-missing --cov-fail-under=95 -v
```

**Resultado obtido:**

- **305 testes passaram** (0 falhas, 0 warnings)
- **Cobertura total: 98.67%** (mínimo exigido: 95% — atingido)
- A suíte cobre validação de payloads, segurança de arquivos/PDF, configuração, observabilidade, rate limiting, contratos e compensação de anexos, além dos fluxos funcionais.

Somente os testes, sem cobertura:

```bash
.venv/Scripts/pytest.exe -v --tb=short
```

### Frontend (Vitest)

```bash
cd frontend
pnpm test              # execução única, sem cobertura
pnpm test:coverage      # com cobertura (script dedicado do package.json)
```

**Resultado obtido:**

- **19 arquivos de teste, 109 testes passaram** (0 falhas)
- **Cobertura: 84.50% statements / 81.50% branches / 82.40% functions / 86.08% lines**
- A medição agora inclui todo o código executável de produção. A configuração anterior informava 95.09% de linhas sobre um subconjunto curado e escondia `App.tsx`, hooks e componentes; no escopo completo, o baseline real era 73.67%.

> Nota: `pnpm test -- --coverage` (com `--` extra) **não ativa** a cobertura por causa de como os argumentos são repassados; use `pnpm test:coverage` diretamente.

### E2E (Playwright)

Instale o Chromium gerenciado pelo Playwright. Mantenha a porta 3002 livre para os cenários de UI e 3003/5001 livres para o smoke real:

```bash
cd frontend
pnpm exec playwright install chromium
pnpm test:e2e
pnpm test:e2e:fullstack
```

**Resultado obtido:** 5 cenários de UI passaram e 1 foi pulado (cenário exclusivo de mobile no projeto desktop); o smoke full-stack passou 1 jornada.

Os cenários de `test:e2e` interceptam a API e validam a UI. `test:e2e:fullstack` sobe Vite e Flask, usa o gateway local determinístico, atravessa o proxy e confirma persistência em um SQLite de arquivo isolado por `TEST_DATABASE_URL`; os unitários continuam usando `:memory:`.

---

## 7. Build de produção (frontend)

```bash
cd frontend
pnpm build
```

**Resultado obtido:** build concluído em ~1.2s, gerando `dist/` (index.html 0.86KB, CSS 37.07KB, chunk Markdown 322.75KB / 99.59KB gzip e bundle principal 435.75KB / 135.68KB gzip).

---

## 8. Subir a stack

### Opção recomendada — `start-stack.ps1` / `stop-stack.ps1`

Scripts PowerShell criados neste guia para automatizar tudo abaixo em um único comando:

```powershell
./start-stack.ps1              # sobe tudo, testa e abre o navegador
./start-stack.ps1 -NoBrowser    # sobe e testa sem abrir o navegador
./start-stack.ps1 -SkipSeed     # pula o seed do catálogo
```

O que o script faz, nesta ordem:

1. **Pré-flight**: valida que a venv do backend e o `node_modules` do frontend existem, e que `.env` está presente (copia de `.env.example` se faltar).
2. **Libera portas presas**: verifica se as portas 5000/3002 já estão em uso (ex.: um `run.py` ou `pnpm dev` de uma execução anterior que travou) e **finaliza esses processos automaticamente** antes de prosseguir. Se a porta continuar ocupada após a tentativa, o script aborta com erro em vez de subir um serviço que vai falhar.
3. **Seed** do catálogo de livros (idempotente).
4. Sobe **backend** (`python run.py`) e **frontend** (`pnpm dev`) em background, redirecionando logs para `.stack-logs/`.
5. Faz **polling dos health checks** (`/api/v1/health` e `http://localhost:3002`) com timeout de 40s.
6. **Smoke tests**: health check, listagem de livros, e um fluxo completo de chat (criar sessão → enviar mensagem → validar resposta do gateway configurado em `CHAT_GATEWAY`).
7. Abre a aplicação no navegador padrão (a menos que `-NoBrowser`).

Para parar tudo:

```powershell
./stop-stack.ps1
```

Finaliza os processos pelo PID salvo em `.stack-pids.json` e, como garantia extra, também finaliza qualquer processo ainda escutando nas portas 5000/3002.

> **Nota sobre o pnpm no Windows:** `Start-Process` não consegue executar o shim `pnpm.ps1`/`pnpm.cmd` diretamente como um binário Win32 (erro `%1 is not a valid Win32 application`). O script contorna isso rodando `pnpm dev` através de `cmd.exe /c`, e depois resolve o PID real do processo Node que fica escutando a porta 3002 (não o PID do `cmd.exe` wrapper) para registrar em `.stack-pids.json`.

### Opção manual (equivalente, passo a passo)

Se preferir não usar o script, suba os dois serviços manualmente, cada um em background/terminal próprio:

**Terminal 1 — Backend (Flask, porta 5000):**

```bash
cd backend
.venv/Scripts/python.exe seed.py   # popula catálogo de livros (idempotente)
.venv/Scripts/python.exe run.py
```

**Terminal 2 — Frontend (Vite, porta 3002):**

```bash
cd frontend
pnpm dev
```

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3002 |
| Backend API | http://localhost:5000/api/v1 |
| Health check | http://localhost:5000/api/v1/health |
| Documentação interativa | http://localhost:5000/docs |
| OpenAPI JSON | http://localhost:5000/openapi.json |

---

## 9. Testar a stack em execução

Testes realizados manualmente neste ambiente, todos com sucesso:

**Health check do backend:**

```bash
curl -s http://localhost:5000/api/v1/health
# {"request_id": null, "service": "python-ai-assistant", "status": "ok"}
```

**Frontend servindo:**

```bash
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:3002
# HTTP 200
```

**Métricas Prometheus:**

```bash
curl -s http://localhost:5000/metrics
# inclui mindsight_http_requests_total e mindsight_chat_gateway_*
```

Se `API_KEY` estiver configurada, inclua `Authorization: Bearer <valor>`. Os labels usam templates de rota, nunca IDs concretos.

**Listagem de livros (dados do seed):**

```bash
curl -s http://localhost:5000/api/v1/books
# retorna 5 livros (The Pragmatic Programmer, Refactoring, etc.)
```

**Fluxo completo de chat (criar sessão → enviar mensagem → resposta da IA):**

```bash
# 1. Criar sessão
curl -s -X POST http://localhost:5000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"Teste stack"}'

# 2. Enviar mensagem (use o "id" retornado acima como session_id)
curl -s -X POST http://localhost:5000/api/v1/chat/messages \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<SESSION_ID>","content":"O que e uma lista em Python?","thinking_mode":"fast"}'
```

Resultado: o gateway `local` (sem chave de API) respondeu corretamente com uma explicação sobre listas em Python, incluindo bloco de código — confirma que o modo determinístico funciona out-of-the-box.

**Backstop de uploads órfãos (execute primeiro em dry-run):**

```powershell
cd backend
.\.venv\Scripts\python.exe -m flask --app run:app cleanup-uploads --dry-run
.\.venv\Scripts\python.exe -m flask --app run:app cleanup-uploads
```

O frontend corrente não depende desse job no fluxo normal: arquivos e mensagem seguem juntos em um único request multipart. A rotina cobre clientes legados e quedas abruptas entre filesystem e commit.

Para testar via navegador: abra http://localhost:3002, envie uma pergunta no chat e confirme a reprodução progressiva via SSE. A chamada ao provedor termina antes do endpoint de stream; portanto, isto ainda não é streaming token a token do LLM.

---

## 10. Parar os serviços

Nos terminais onde `run.py` e `pnpm dev` estão rodando, pressione `Ctrl+C`. Se estiverem em background (nohup/job), finalize os processos Python (`run.py`) e Node (`vite`) via Gerenciador de Tarefas ou:

```bash
# Git Bash — encontrar e matar processos nas portas 5000/3002
netstat -ano | grep -E ':5000|:3002'
taskkill //PID <pid> //F
```

---

## 11. Alternativa: Docker Compose

Requer `.env` na raiz e Docker Desktop rodando. Libere as portas 5000 e 3002 antes.

```bash
docker compose up --build
```

- Frontend: http://localhost:3002
- Backend: http://localhost:5000
- Volume persistente para `backend/storage` (SQLite e uploads; o índice FAISS ainda não participa do fluxo atual)

```bash
docker compose down    # parar
docker compose logs -f # acompanhar logs
```

> Validado em 2026-07-24: as imagens de backend e frontend foram compiladas com sucesso por `docker compose build backend frontend`.

---

## 12. Divergências encontradas vs. README

Durante a validação real, estas divergências foram encontradas e reconciliadas no `README.md`:

1. **Rota OpenAPI:** o servidor expõe **`GET /openapi.json`** e **`GET /docs`** na raiz, sem o prefixo `/api/v1`; a tabela principal agora explicita essa exceção.
2. **`make` no Windows:** o Makefile assume shell POSIX e layout `bin/` da venv; em Git Bash no Windows nenhum dos alvos funciona sem adaptação (ver seção 0).
3. **Bug de ordem de import — `.env` não era aplicado ao `CHAT_GATEWAY`/chaves de API** (corrigido neste guia, ver seção 14).

---

## 13. Troubleshooting específico do Windows

### `make: command not found`

Não há `make` neste ambiente. Use os comandos manuais deste guia, ou instale `make` via Chocolatey (`choco install make`) — ainda assim adapte `bin/` → `Scripts/` nos alvos do Makefile.

### venv sem pasta `bin/`

Normal no Windows: os executáveis ficam em `backend/.venv/Scripts/` (ex.: `python.exe`, `pytest.exe`, `ruff.exe`), não em `bin/`.

### Porta 5000 ou 3002 em uso

```bash
netstat -ano | grep -E ':5000|:3002'
taskkill //PID <pid> //F
```

### `pnpm: command not found`

```bash
corepack enable
corepack prepare pnpm@10.34.5 --activate
```

### Chat retorna erro de IA logo após clonar

Confirme `CHAT_GATEWAY=local` no `.env` (default já é esse). `CHAT_GATEWAY=auto`/`openai` sem chave válida falha.

---

## 14. Bug corrigido: CHAT_GATEWAY/chaves de API não aplicados do .env

Ao configurar `CHAT_GATEWAY=auto` com uma `HUGGINGFACE_API_KEY` real no `.env`, o backend continuava respondendo com o gateway **local** determinístico em vez de chamar o DeepSeek via Hugging Face — sem nenhum erro nos logs.

### Causa raiz

`backend/run.py` fazia, nesta ordem:

```python
from app.env_loader import load_project_env
load_project_env()
from app import create_app
```

Em Python, `from app.env_loader import load_project_env` precisa primeiro inicializar o pacote `app` (rodar `app/__init__.py` por completo) antes de importar o submódulo `env_loader`. E `app/__init__.py` faz `from app.config import config_by_name` logo na linha 11 — o que avalia a classe `Config` (`CHAT_GATEWAY: str = os.getenv("CHAT_GATEWAY", "local")`, `HUGGINGFACE_API_KEY: str = os.getenv(...)`, etc.) **antes** de `load_project_env()` ser executado.

Resultado: os valores de `Config` ficavam presos nos defaults (`"local"`, chave vazia), mesmo com o `.env` correto, porque a leitura do `os.getenv` acontecia cedo demais na cadeia de imports. Isso só não afetava o Docker Compose porque lá `env_file: .env` injeta as variáveis diretamente no ambiente do container antes do Python iniciar, contornando o problema por acaso.

### Correção aplicada

**`backend/app/config.py`** — chama `load_project_env()` no topo do próprio módulo, garantindo que o `.env` é carregado antes de qualquer leitura de `os.getenv`, não importa qual seja o ponto de entrada (`run.py`, `seed.py`, testes):

```python
from app.env_loader import load_project_env

load_project_env()

BASE_DIR = Path(__file__).resolve().parent.parent
```

Isso expôs um segundo problema: `backend/app/services/observability.py` lia `LANGSMITH_TRACING` via `os.getenv` direto (ignorando o `TestingConfig`, que força tracing desligado nos testes). Como agora o `.env` real passou a ser carregado também durante os testes, `LANGSMITH_TRACING=true` do `.env` real vazava para dentro dos testes e quebrava `test_create_session_send_message_and_stream` (esperava feedback não gravado). Corrigido para preferir `current_app.config` quando há contexto de app (mesmo padrão já usado em `_gateway_setting` no `chat.py`), caindo para `os.getenv` só fora de contexto de request (usado pelos decorators `@traceable_if_enabled`, aplicados em tempo de import):

```python
def langsmith_enabled() -> bool:
    if has_app_context():
        return str(current_app.config.get("LANGSMITH_TRACING", "false")).lower() == "true"
    return os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
```

### Validação

- `pytest --cov=app --cov-fail-under=95` → **305 passed**, cobertura 98.67%.
- `ruff check .` → sem erros.
- Fluxo de chat real via `start-stack.ps1`: resposta passou de texto local ("Em Python, uma lista é criada usando colchetes...") para resposta real do DeepSeek via Hugging Face ("Uma **lista** em Python é uma estrutura de dados mutável e ordenada...").
