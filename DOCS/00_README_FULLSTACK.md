# MindSight AI - Documentacao tecnica

Este pacote documenta a codebase fullstack atual, as escolhas tecnicas, os fluxos principais, os gaps encontrados e um roadmap pragmatico de melhoria.

## Leitura recomendada

| Documento | Quando usar |
| --- | --- |
| [01_PRODUCT_VISION.md](01_PRODUCT_VISION.md) | Entender objetivo de produto, publico e escopo do MVP. |
| [05_SYSTEM_ARCHITECTURE.md](05_SYSTEM_ARCHITECTURE.md) | Entender arquitetura, camadas, dados e fluxos tecnicos. |
| [06_BACKEND_FLASK_API_CONTRACT.md](06_BACKEND_FLASK_API_CONTRACT.md) | Consultar contrato REST, convencoes de erro e gaps de contrato. |
| [29_ENV_EXAMPLE.md](29_ENV_EXAMPLE.md) | Configurar variaveis de ambiente locais e de producao. |
| [30_MAKEFILE_COMMANDS.md](30_MAKEFILE_COMMANDS.md) | Operar instalacao, testes, build e ambiente local. |
| [33_IMPLEMENTATION_STATUS.md](33_IMPLEMENTATION_STATUS.md) | Ver o que esta implementado, testado e pendente. |
| [34_CODEBASE_AUDIT.md](34_CODEBASE_AUDIT.md) | Ler achados de arquitetura, seguranca, qualidade e operacao. |
| [35_TECH_DECISIONS_TRADEOFFS.md](35_TECH_DECISIONS_TRADEOFFS.md) | Entender por que cada tecnologia foi escolhida e seus tradeoffs. |
| [36_IMPROVEMENT_ROADMAP.md](36_IMPROVEMENT_ROADMAP.md) | Priorizar fixes e evolucoes por impacto. |
| [37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md](37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md) | Ver a revisao profunda mais recente, mudancas aplicadas, metricas e riscos residuais. |

## Resumo executivo

MindSight AI e um monorepo com backend Flask e frontend React/Vite. A aplicacao entrega um assistente de chat focado em Python, biblioteca local de livros, anexos, busca semantica demonstrativa e integracoes opcionais com OpenAI, Hugging Face e LangSmith.

O projeto esta bem estruturado para um MVP/teste tecnico: ha separacao de rotas, servicos e repositorios no backend; o frontend isola cliente HTTP, componentes de chat e hooks; e existe uma suite relevante de testes unitarios.

Os principais gaps residuais para evoluir de MVP local para produto operavel sao:

- Autenticacao por usuario e ownership antes de um deploy publico/multiusuario; a API key atual e um segredo unico de operador.
- AV/CDR e parsing preemptivamente isolado se uploads forem expostos a usuarios nao confiaveis; assinatura, limites e quarentena ja existem.
- Validacao automatica de respostas Python contra o OpenAPI se o contrato crescer; os tipos TypeScript ja sao gerados e verificados.
- Streaming real do provedor, retry com backoff e metricas de operacao/LLM.
- Busca semantica sobre o acervo real; o endpoint atual e uma demonstracao por hashing.
- Evoluir a raiz de composicao do frontend para hooks controladores apenas se os fluxos voltarem a crescer.

Ja estao implementados: Gunicorn, migracoes Alembic, paginacao, timeout e rate limit do chat, request ID com log de duracao, validacao estrita de payloads, hardening de uploads/PDF, tipos gerados do OpenAPI, smoke full-stack no CI, modularizacao do frontend e gates de cobertura sobre todo o codigo executavel.

## Estado da auditoria

Auditoria original feita em 2026-07-03 e revisada em 2026-07-24 sobre o estado local do workspace.

Verificacoes executadas:

- Backend: `ruff check app tests` passou.
- Backend: `compileall app` passou.
- Frontend: `pnpm typecheck` passou.
- Frontend: `pnpm lint` passou.
- Frontend: `pnpm test:coverage` passou com 19 arquivos e 109 testes; 86.08% de linhas no escopo completo.
- Frontend: Playwright passou com 5 cenarios e pulou 1 cenario mobile-only no projeto desktop.
- Full-stack: Playwright passou 1 jornada real via Vite proxy, Flask e SQLite de teste.
- Backend: 305 testes passaram sem warnings; cobertura 98.67% com gate de 95%.
- Docker: as imagens de backend e frontend foram compiladas com sucesso.
