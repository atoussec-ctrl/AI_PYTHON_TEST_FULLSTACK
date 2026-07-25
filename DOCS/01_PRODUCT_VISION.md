# Visao de produto

## Proposito

MindSight AI e um assistente fullstack para apoiar estudos e desenvolvimento em Python. O produto combina chat com IA, biblioteca local de livros, importacao de documentos e uma busca semantica demonstrativa.

O foco atual e provar competencia backend/fullstack: API REST em Flask, persistencia em SQLite, frontend React, testes, integracao opcional com LLMs e documentacao tecnica.

## Personas principais

| Persona | Necessidade | Funcionalidades relevantes |
| --- | --- | --- |
| Estudante de Python | Tirar duvidas e receber exemplos praticos. | Chat, modos de raciocinio, Markdown com codigo. |
| Avaliador tecnico | Ver arquitetura, API, testes e operabilidade. | Flask API, OpenAPI, testes, Makefile, docs. |
| Curador de biblioteca | Cadastrar ou importar livros e consultar acervo. | CRUD de livros, importacao PDF/TXT/MD/JSON, busca. |
| Desenvolvedor local | Rodar sem chaves externas e validar mudancas rapido. | `CHAT_GATEWAY=local`, Docker Compose, testes. |

## Jobs to be done

- Fazer uma pergunta sobre Python e receber resposta em portugues.
- Persistir uma conversa e continuar o contexto depois.
- Importar material de referencia e usar esse conteudo como fonte local.
- Consultar livros por titulo, autor, categoria ou texto livre.
- Rodar tudo localmente sem dependencia obrigatoria de chave de IA.
- Verificar o contrato da API e a saude do backend.

## Escopo do MVP

Incluido:

- Chat com sessoes persistidas.
- Gateway local deterministico para desenvolvimento e CI.
- Gateway OpenAI-compatible via LangChain para OpenAI e Hugging Face.
- Biblioteca local de livros.
- Upload de anexos e extracao de texto para documentos suportados.
- Busca semantica demonstrativa.
- Frontend responsivo com sidebar, biblioteca e settings.
- Testes backend e frontend.

Nao incluido ainda:

- Login, multiusuario e ownership (a API e protegida por segredo compartilhado unico, nao por conta de usuario — ver `API_KEY` em `DOCS/29_ENV_EXAMPLE.md`).
- Billing, planos, controle de quota e auditoria por usuario.
- Busca vetorial real persistida em FAISS para todo o acervo.
- Streaming real token-a-token do provedor LLM.
- Observabilidade completa (request ID e log de duracao ja existem; faltam metricas e tracing distribuido).

Ja incluido desde a auditoria inicial: WSGI de producao (Gunicorn) e autenticacao minima por API key, com guarda que falha o boot em producao se os segredos nao forem configurados.

## Indicadores de qualidade desejados

- Primeiro run local sem chave externa.
- Contrato OpenAPI sempre alinhado aos tipos do frontend.
- Falhas de IA degradam de forma clara sem derrubar a API.
- Uploads nao deixam arquivos orfaos.
- Testes cobrem regras de negocio, contrato HTTP e fluxos criticos de UI.
