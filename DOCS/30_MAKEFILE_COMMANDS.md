# Comandos de operacao local

O Makefile e o ponto de entrada recomendado em sistemas Unix-like. No Windows, os scripts PowerShell `start-stack.ps1` e `stop-stack.ps1` tambem existem no workspace local.

## Instalacao

| Comando | O que faz |
| --- | --- |
| `make install` | Instala dependencias backend e frontend. |
| `make backend-install` | Cria venv e instala `backend/requirements.txt`. |
| `make backend-install-ai` | Instala dependencias opcionais de IA/RAG. |

## Desenvolvimento

| Comando | O que faz |
| --- | --- |
| `make dev` | Sobe backend e frontend em paralelo. |
| `make backend-dev` | Roda Flask localmente. |
| `make frontend-dev` | Roda Vite na porta 3002. |
| `docker compose up --build` | Sobe ambiente containerizado. |

## Banco e seed

| Comando | O que faz |
| --- | --- |
| `make seed` | Popula catalogo inicial de livros. |
| `make db-backup` | Copia SQLite atual para `backend/storage/backups`. |
| `make db-restore` | Restaura backup mais recente. |

## Uploads e operacao

| Comando | O que faz |
| --- | --- |
| `make uploads-cleanup-dry-run` | Relata rows e arquivos orfaos antigos sem alterar dados. |
| `make uploads-cleanup` | Remove orfaos mais antigos que `ORPHAN_UPLOAD_MAX_AGE_HOURS`. |
| `curl http://localhost:5000/metrics` | Consulta metricas Prometheus; envie Bearer token se `API_KEY` estiver ativa. |

## Qualidade

| Comando | O que faz |
| --- | --- |
| `make backend-test` | Executa pytest. |
| `make backend-test-cov` | Executa pytest com cobertura minima. |
| `make frontend-test` | Executa Vitest. |
| `make frontend-test-cov` | Executa Vitest com coverage. |
| `make test` | Executa backend e frontend. |
| `make lint` | Ruff + ESLint. |
| `make typecheck` | `compileall` backend + `tsc` frontend. |
| `make build` | Build de producao do frontend. |

## Observacoes Windows

No ambiente auditado, os comandos equivalentes executados foram:

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m flask --app run:app cleanup-uploads --dry-run

cd ..\frontend
pnpm typecheck
pnpm lint
pnpm test
```

Se o pytest falhar com permissao no diretorio temporario, use um `--basetemp` gravavel ou rode fora de um sandbox restritivo.

## Riscos operacionais do Makefile atual

- `make clean` remove banco, indice, uploads, `node_modules` e caches. Usar somente em ambiente local.
- Caminhos do Makefile usam estilo Unix (`.venv/bin/python`), entao no Windows puro e melhor usar PowerShell ou adaptar comandos.
- `make dev` usa processos em background simples; para uso prolongado, scripts dedicados ou Docker Compose dao mais controle de logs e shutdown.
