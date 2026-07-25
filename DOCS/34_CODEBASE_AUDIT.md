# Auditoria da codebase

## Escopo

Analise estatica e verificacoes locais do monorepo:

- Backend Flask/Python.
- Frontend React/Vite/TypeScript.
- Testes, Docker, Makefile, CI e documentacao existente.

Na auditoria original nao foram aplicadas correcoes; ela permanece abaixo como registro historico da evidencia encontrada naquele momento.

**Revalidacao 2026-07-24:** os achados 1, 3, 4, 5, 6, 7, 10, 12 e 13 foram fechados. O achado 2 foi mitigado para um MVP single-tenant por API key, mas auth/ownership continua obrigatorio para uso publico. Os achados 8, 9 e 11 mantem trabalho residual. O fluxo atual envia arquivos e mensagem em um multipart transacional, possui limpeza idempotente de orfaos e expoe metricas Prometheus com suporte multiprocess. No achado 4, AV/CDR e processo isolado permanecem condicionais a exposicao publica. A analise atual e as evidencias estao em `DOCS/37_CLEAN_ARCHITECTURE_REVIEW_2026-07-24.md`.

## Achados criticos/altos

### 1. Servidor Flask precisa de perfil de producao

Evidencia:

- `backend/run.py` roda o servidor Flask de desenvolvimento.
- `backend/Dockerfile` usa `CMD ["python", "run.py"]`.
- `docker-compose.yml` configura `APP_ENV=development`.

Impacto:

- O container local se parece com ambiente final, mas nao usa WSGI.
- Se `FLASK_DEBUG=true` for usado fora de debug local, o debugger Flask fica exposto.

Recomendacao:

- Usar Gunicorn/Waitress em container.
- Manter debug apenas via flag explicita `FLASK_DEBUG=true`.
- Falhar startup se `APP_ENV=production` usar secret/debug inseguros.

### 2. API sem autenticacao/autorizacao

Evidencia:

- Nao ha middleware de auth em `backend/app/__init__.py`.
- Endpoints permitem listar/deletar sessoes, cadastrar livros e baixar anexos por ID.

Impacto:

- Qualquer cliente com acesso a API pode ler, modificar ou apagar dados.
- IDs aleatorios reduzem enumeracao, mas nao substituem controle de acesso.

Recomendacao:

- Adicionar autenticacao por JWT, sessao ou API key.
- Incluir `user_id`/ownership em `ChatSession`, `Attachment`, `Book` se multiusuario.
- Validar ownership em todas as rotas de leitura/escrita.

### 3. Schema gerenciado no startup

Evidencia:

- `db.create_all()` roda no startup.
- `_ensure_sqlite_schema()` aplica `ALTER TABLE` manual e somente SQLite.

Impacto:

- Sem historico versionado de schema.
- Risco de divergencia entre ambientes.
- Dificulta migrar para Postgres/MySQL.

Recomendacao:

- Adotar Alembic/Flask-Migrate.
- Remover alteracoes DDL do startup.
- Adicionar workflow de migracao para CI/deploy.

## Achados medios

### 4. Uploads precisam de hardening

Evidencia:

- Validacao depende de extensao e `mimetype` informado.
- Arquivo e salvo antes de checar tamanho no disco.
- Importacao le arquivo inteiro em memoria.

Impacto:

- Risco de arquivo malicioso ou disfarce de MIME.
- Uso excessivo de memoria com arquivos grandes ou PDFs complexos.

Recomendacao:

- Validar assinatura real do arquivo quando possivel.
- Aplicar `MAX_CONTENT_LENGTH` e checagem antecipada.
- Definir limite de paginas/tempo para PDF.
- Considerar quarentena/AV se exposto publicamente.

### 5. Delete de sessao deve remover arquivo fisico

Evidencia:

- Relacionamentos ORM apagam registros em cascata.
- O servico de chat deve remover os arquivos listados em `storage_path` quando a sessao e deletada.

Impacto:

- Sem esse cleanup, haveria vazamento de armazenamento e retencao indevida de dados.

Recomendacao:

- Manter o servico de delecao coletando paths antes do commit e removendo arquivos depois.
- Adicionar job de limpeza de anexos orfaos.
- Cobrir com teste de filesystem.

### 6. Upload e envio de mensagem nao sao transacionais

Evidencia:

- Frontend faz `uploadAttachment` antes de `sendMessage`.
- Se `sendMessage` falha, anexos ja foram persistidos.
- Em falha/retry, frontend restaura texto, mas nao restaura anexos limpos em `onMutate`.

Impacto:

- Arquivos orfaos.
- Experiencia ruim em retry com anexos.

Recomendacao:

- Criar endpoint unico `POST /chat/messages` multipart com arquivos.
- Ou adicionar compensacao: cleanup de attachments se envio falhar.
- No frontend, adiar `revokePendingAttachment` ate sucesso ou restaurar anexos no erro.

### 7. Listagens sem paginacao

Evidencia:

- Repositorios usam `.all()` para livros, sessoes e mensagens.

Impacto:

- Crescimento de latencia e memoria conforme dados aumentam.
- Dificuldade para UI manter performance.

Recomendacao:

- Adicionar `limit`, `cursor` ou `page`.
- Definir limites maximos por endpoint.
- Indexar campos de busca e considerar FTS para livros.

### 8. Chamadas LLM sincronas sem timeout/rate limit explicitos

Evidencia:

- `ChatOpenAI` e criado sem timeout explicito.
- Falhas sao capturadas e persistidas como mensagem `failed`.

Impacto:

- Requests podem ficar presos.
- Usuarios podem gerar custo/latencia sem controle.

Recomendacao:

- Definir timeout, retry com backoff e budget de tokens.
- Adicionar rate limit por usuario/IP.
- Para respostas longas, considerar fila/background job e streaming real.

### 9. Contrato OpenAPI e tipos precisam permanecer sincronizados

Evidencia:

- Backend usa `status="failed"`.
- OpenAPI e frontend devem manter esse mesmo enum.

Impacto:

- Consumidores gerados por OpenAPI rejeitariam payload real se o enum divergisse.
- Frontend perderia tipagem precisa se mantivesse valores diferentes.

Recomendacao:

- Manter enum padronizado em backend, OpenAPI e TypeScript.
- Manter teste que valida o schema com valores reais.

### 10. Observabilidade incompleta

Evidencia:

- `X-Request-ID` e refletido, mas nao gerado quando ausente.
- `LOG_LEVEL` existe no `.env.example`, mas nao configura logging global.
- Nao ha metricas, duracao por request ou logs estruturados.

Impacto:

- Debug de incidentes fica dependente de logs manuais.
- Dificil correlacionar erros, traces LangSmith e requests HTTP.

Recomendacao:

- Middleware de request id, tempo de resposta e log JSON.
- Logger global com nivel vindo de config.
- Metricas basicas: latencia, status code, erros de gateway, tamanho upload.

### 11. Busca semantica e demonstrativa

Evidencia:

- `semantic_search.py` usa hashing local.
- `hash(token)` em Python varia por processo.
- Config expoe FAISS/embeddings, mas o caminho real nao usa vector store persistido.

Impacto:

- Resultados podem variar entre processos.
- A documentacao pode sugerir mais capacidade do que o codigo entrega.

Recomendacao:

- Usar hash estavel (`hashlib`) para o modo local.
- Implementar provider real com Sentence Transformers + FAISS quando dependencias AI estiverem instaladas.
- Documentar claramente modo demo vs modo real.

### 12. Frontend concentrado em `App.tsx`

Evidencia:

- `frontend/src/App.tsx` tem mais de 1600 linhas.
- O mesmo arquivo concentra layout, views, mutacoes, sidebar, biblioteca, settings e composer.

Impacto:

- Mudancas simples podem afetar areas distantes.
- Testes de unidade ficam mais dificeis.
- Coverage exclui parte relevante da logica de produto.

Recomendacao:

- Extrair `ChatPage`, `BooksAdminView`, `SettingsView`, `ChatComposer`.
- Criar hooks `useChatMutations`, `useBookMutations`, `usePendingAttachments`.
- Mover logica para modulos cobertos por Vitest.

### 13. Acessibilidade do mobile drawer e swipe

Evidencia:

- Drawer mobile nao tem `role="dialog"`, `aria-modal`, foco inicial, focus trap ou Escape.
- Delete/pin por swipe nao tem alternativa clara por teclado.

Impacto:

- Usuarios de teclado/leitores de tela tem experiencia limitada.
- Swipe delete sem confirmacao aumenta risco de exclusao acidental.

Recomendacao:

- Implementar componente `Dialog/Sheet` acessivel.
- Adicionar menu contextual/botoes visiveis para pin/delete.
- Confirmar delete ou oferecer undo.

## Achados baixos

| Achado | Impacto | Recomendacao | Status |
| --- | --- | --- | --- |
| Botao "Buscar chats" sem comportamento | UI sugere funcao inexistente. | Implementar busca ou remover/desabilitar. | Concluido — filtra sessoes por titulo. |
| TanStack Router instalado mas nao usado | Dependencia e modelo mental desnecessarios. | Usar rotas reais ou remover dependencia. | Concluido — dependencia removida (junto com `zod`, tambem instalado e nunca usado). |
| Labels de tempo em ingles | Inconsistencia de UX em app PT-BR. | Usar `Intl.RelativeTimeFormat('pt-BR')`. | Concluido — datas relativas e grupos em PT-BR. |
| Playwright usa `channel: chrome` | Falha em ambientes sem Google Chrome. | Usar Chromium padrao ou instalar Chrome no CI. | Concluido — configuracao e CI usam Chromium gerenciado pelo Playwright. |
| README referenciava `DOCS/` inexistente | Links quebrados. | Pasta `DOCS/` criada nesta auditoria. | Concluido. |

## Pontos fortes

- Separacao razoavel de backend em routes/services/repositories/models.
- Gateway local deterministico reduz custo e torna CI previsivel.
- Cliente API frontend esta isolado e bem testado.
- Markdown usa `react-markdown`, sem `dangerouslySetInnerHTML`.
- Testes cobrem muitos fluxos: CRUD, chat, anexos, PDF, feedback, gateway selection e UI.
- Docker Compose e Makefile facilitam entrada no projeto.
