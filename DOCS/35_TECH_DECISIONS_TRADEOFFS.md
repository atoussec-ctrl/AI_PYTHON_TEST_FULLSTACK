# Decisoes tecnicas e tradeoffs

## Backend

| Escolha | Por que faz sentido | Vantagens | Tradeoffs / riscos | Alternativas |
| --- | --- | --- | --- | --- |
| Python 3.12+ | Ecossistema forte para IA, APIs e testes. | Produtivo, legivel, bom suporte a LangChain/SQLAlchemy. | Performance depende de desenho de IO e workers. | Node, Go, Java/Kotlin. |
| Flask 3 | API pequena, prova backend e controle explicito. | Simples, flexivel, baixo overhead. | Menos opinativo que FastAPI; schemas e docs exigem disciplina. | FastAPI, Django REST. |
| Flask-SQLAlchemy/SQLAlchemy | ORM maduro e conhecido. | Modelagem relacional, queries expressivas, facil teste. | Entidades ORM ainda atravessam limites de camada. | SQLModel, Django ORM, Prisma. |
| SQLite | Setup local simples e zero infra. | Excelente para MVP, testes e demos. | Concorrencia limitada, backup/operacao simples demais para escala. | Postgres, MySQL. |
| Alembic/Flask-Migrate | Versiona o schema fora dos testes. | Historico reproduzivel e caminho para Postgres. | Migrar automaticamente no preload do Gunicorn exige coordenacao operacional em mais de uma replica. | Job de migration separado no deploy. |
| Gateway local deterministico | Rodar sem chaves e sem custo. | Testes estaveis, onboarding rapido. | Nao mede qualidade real do LLM. | Mocks por teste, fixtures gravadas. |
| LangChain OpenAI-compatible | Reutiliza interface para OpenAI e HF router. | Troca de provedor mais simples. | Dependencia extra e diferencas sutis de parametros por modelo. | SDK OpenAI direto, LiteLLM. |
| LangSmith opcional | Observabilidade de chains e feedback. | Bom para depurar prompts e runs. | Custo/privacidade e dependencia externa. | OpenTelemetry, logs proprios. |
| Prometheus client | Metricas operacionais pull-based e padrao aberto. | Counters/histograms baratos, labels controladas e suporte a Gunicorn multiprocess. | Exige scraper, dashboards/alertas e limpeza correta do diretorio entre boots. | OpenTelemetry Metrics, StatsD. |
| pypdf | Extracao local de texto PDF. | Sem servico externo, suficiente para PDFs textuais. | PDFs escaneados nao funcionam; pode ser pesado. | OCR, unstructured.io, PyMuPDF. |
| Multipart atomico + compensacao | Elimina o fluxo browser upload-then-send sem introduzir fila/objeto distribuido. | Um commit para rows/mensagens e cleanup imediato em erro. | Filesystem nao participa do ACID; crash exige o job idempotente por idade. | Object storage com lifecycle, outbox/workflow assíncrono. |

## Frontend

| Escolha | Por que faz sentido | Vantagens | Tradeoffs / riscos | Alternativas |
| --- | --- | --- | --- | --- |
| React 19 | Padrao comum para UI rica. | Ecossistema amplo, componentes testaveis. | Exige disciplina de estado e separacao de responsabilidades. | Vue, Svelte, Solid. |
| Vite | Dev server e build modernos. | Rapido, simples, boa integracao com Vitest. | Dependencias nativas podem falhar em sandbox/Windows restritivo. | Next.js, CRA, Rsbuild. |
| TypeScript | Tipagem do contrato e UI. | Reduz erros de props/payloads. | Tipos manuais podem divergir do backend. | JS puro, geracao via OpenAPI. |
| TanStack Query | Estado servidor/cache. | Invalida queries, retries e async state de forma limpa. | Precisa chaves consistentes e invalidacao correta. | SWR, RTK Query. |
| Tailwind CSS 4 | Design tokens e composicao rapida. | Produtividade e padrao visual consistente. | CSS pode ficar acoplado ao markup; classes longas. | CSS Modules, Panda, vanilla-extract. |
| Framer Motion | Animacoes e gestos. | Boa UX para sidebar/swipe. | Acessibilidade precisa ser implementada separadamente. | CSS transitions, Radix gestures. |
| react-markdown + remark-gfm | Renderizacao segura de Markdown. | Evita HTML perigoso por default e suporta GFM. | Highlight e copy code precisam componentes customizados. | MDX, markdown-it. |
| Playwright + Chromium gerenciado | Teste e2e real e reproduzivel no CI. | Excelente para fluxos de UI sem depender de Chrome do host. | Download inicial do browser e custo maior que testes de componente. | Cypress, Vitest browser mode. |

## DevOps e qualidade

| Escolha | Por que faz sentido | Vantagens | Tradeoffs / riscos | Alternativas |
| --- | --- | --- | --- | --- |
| Docker Compose | Orquestracao local simples. | Backend usa Gunicorn e as imagens compilam em um comando. | Frontend ainda usa Vite dev server; nao e uma imagem de entrega estatica/edge. | Nginx/Caddy, Kubernetes, Railway/Fly configs. |
| Makefile | Padroniza comandos. | Bom para Linux/macOS/CI. | Windows precisa adaptacao ou scripts PowerShell. | Taskfile, npm scripts raiz, Just. |
| Ruff | Lint Python rapido. | Baixo custo; CI exige lint e `ruff format --check`. | O alvo local `make lint` ainda executa apenas lint. | Black+Flake8, PyLint. |
| Pytest | Testes backend. | Fixtures simples, 305 testes, cobertura de 98.67% e apps de teste com engines descartadas. | Alta cobertura nao substitui testes de carga/concorrencia. | unittest. |
| Vitest | Testes frontend integrados ao Vite. | Rapido e natural para TS/React. | Depende de config Vite carregar corretamente. | Jest, Web Test Runner. |

## Decisao: manter gateway local como default

Decisao recomendada: manter `CHAT_GATEWAY=local` no `.env.example`.

Motivos:

- Evita exigir chave externa no primeiro run.
- Mantem CI deterministicamente verde.
- Permite avaliar arquitetura sem custo.

Tradeoff:

- Demos locais nao refletem qualidade de um modelo real.

Mitigacao:

- Documentar claramente o modo ativo.
- Adicionar smoke tests opcionais para provedores reais em ambiente com secrets.

## Decisao: migrar para Postgres somente quando houver multiusuario

SQLite e suficiente para MVP e avaliacao tecnica. A migracao para Postgres deve acontecer junto com:

- Auth e ownership.
- Migracoes Alembic.
- Paginacao.
- Backup/restore formal.
- Observabilidade de queries.

Migrar antes disso aumenta complexidade sem resolver o maior risco atual: ausencia de controle de acesso.
