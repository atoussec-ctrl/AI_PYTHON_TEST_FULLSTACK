# Revisao de Clean Architecture e qualidade — 2026-07-24

## Escopo e conclusao

Esta revisao cobriu estrutura de pastas, codigo de producao, testes, contratos, dependencias, CI, Docker, Makefile e documentacao do monorepo. Foram executadas verificacoes estaticas e dinamicas e aplicadas correcoes de baixo ou medio risco que podiam ser comprovadas por teste.

O projeto esta em bom estado para um MVP single-tenant e para avaliacao tecnica. Ele possui separacao util por camadas, gateways substituiveis, migrations, testes extensos e um frontend agora modular. Ainda nao e Clean Architecture estrita: os servicos de aplicacao conhecem Flask-SQLAlchemy, configuracao Flask e entidades ORM, e a spec OpenAPI/serializacao Python continuam escritas manualmente. Os tipos TypeScript, porem, agora sao gerados do contrato e verificados no CI.

A recomendacao e preservar o desenho simples atual e aprofundar os limites arquiteturais somente nos pontos em que existe risco concreto: autenticacao/ownership, AV/isolamento para uploads publicos, streaming e operacao em escala. A transacao de anexos e o backstop de orfaos foram fechados nesta continuacao.

## Resultado mensuravel

| Indicador | Baseline observado | Depois da revisao |
| --- | --- | --- |
| Backend | 204 testes; 81 warnings de recursos; 99.77% de cobertura | 305 testes; 0 warnings; 98.67% de cobertura; gate de 95% |
| Frontend | 98 testes; relatorio aparente de 95.09% de linhas sobre apenas 204 linhas selecionadas | 109 testes; 86.08% de linhas sobre 575 linhas executaveis; gates globais ativos |
| Cobertura frontend real | 73.67% de linhas quando o escopo completo era forcado | 86.08% lines; 82.40% functions; 81.50% branches; 84.50% statements |
| Raiz React | `App.tsx` com cerca de 1.550 linhas | 462 linhas fisicas; componentes separados por feature |
| Browser tests | Dependiam de Chrome do host e nao rodaram no baseline | UI com mocks: 5 passaram/1 pulado; smoke real Browser -> Vite -> Flask -> SQLite: 1 passou |
| Docker | Resultado de build nao comprovado na auditoria | Imagens backend e frontend compiladas com sucesso |

A pequena reducao percentual do backend nao e regressao: houve adicao de codigo de validacao, seguranca, PDF, contrato e operacao. O total continua muito acima do gate de 95%.

## Arquitetura atual

```text
Browser / React
  App (composition root e controller de UI)
    -> features/chat | features/books | features/settings
    -> shared/api (HTTP + credencial runtime)
          |
          v
Flask HTTP adapters (blueprints + validacao de payload)
    -> application services
         -> repositories concretos -> SQLAlchemy models -> SQLite
         -> ChatCompletionGateway -> local | OpenAI-compatible | HF router
         -> upload filesystem / LangSmith opcional
```

### Limites que funcionam bem

- Blueprints traduzem HTTP e delegam regras relevantes aos servicos.
- `ChatCompletionGateway` aplica Strategy e permite gateway local deterministico ou provedores externos.
- `ChatService` e `BookService` recebem repositorios/gateway por construtor, facilitando testes.
- Repositories concentram queries e persistencia; services controlam commits dos casos de uso.
- App Factory Flask, migrations Alembic e configuracoes por ambiente estao estabelecidas.
- O frontend separa codigo por feature e centraliza acesso HTTP em `shared/api`.
- TanStack Query administra estado remoto; estado visual permanece local aos componentes.

### Limites ainda permeaveis

- Services importam `db`, `current_app`, modelos e repositories concretos; casos de uso nao sao independentes do framework.
- Repositories misturam Repository com Active Record (`Model.query`) e retornam entidades SQLAlchemy diretamente.
- Commits pertencem aos services, mas nao ha uma abstracao de Unit of Work para trocar banco ou testar transacoes sem Flask.
- O OpenAPI de aproximadamente 540 linhas e os modelos/validadores Python ainda evoluem manualmente; o artefato JSON e os tipos TypeScript agora sao derivados e verificados.
- `App.tsx` ainda coordena queries, mutations, navegacao interna e retry; esta aceitavel no tamanho atual, mas e o proximo limite se novos fluxos forem adicionados.

Para este MVP, introduzir entidades puras, interfaces para todo repository e uma Unit of Work abstrata agora teria custo maior que o beneficio. A extracao passa a valer quando surgir um segundo mecanismo de persistencia, regras de dominio complexas ou necessidade de testar use cases totalmente fora do Flask.

## Avaliacao pelos principios solicitados

### Clean Code

Estado: alinhado, com hotspots conhecidos.

Melhorias aplicadas:

- Validacao de JSON/texto/listas foi centralizada em `backend/app/validation.py`.
- Payload `null`, arrays e objetos em campos textuais agora resultam em 400 tipado, nunca em string `"None"` ou 500 acidental.
- Erros de configuracao deixaram de ser classificados como erro 400 do cliente; apenas `ValidationError` representa entrada invalida.
- Componentes React receberam nomes e responsabilidades de feature.
- Utilitarios e dependencias sem consumidores foram removidos.

Hotspots atuais, por linhas fisicas:

| Arquivo | Linhas | Leitura arquitetural |
| --- | ---: | --- |
| `backend/app/services/chat.py` | 584 | Reune prompt, politicas de modelo, gateways, formatacao de contexto e use case; principal candidato a cortes internos. |
| `backend/app/routes/openapi.py` | 540 | Grande por duplicacao manual de contrato; geracao reduz mais risco que apenas dividir o arquivo. |
| `frontend/src/App.tsx` | 462 | Raiz de composicao e controller; tamanho agora administravel. |
| `frontend/src/features/books/BooksAdminView.tsx` | 392 | Feature coesa, mas formulario e lista podem ser extraidos se evoluirem separadamente. |

Tamanho isolado nao determina falta de qualidade. O criterio para nova extracao deve ser quantidade de motivos independentes para mudar, nao uma meta arbitraria de linhas.

### SOLID

| Principio | Estado | Evidencia |
| --- | --- | --- |
| SRP | Melhorado | Chat, livros e configuracoes deixaram a raiz React; validacao saiu das rotas. `chat.py` ainda tem mais de uma responsabilidade. |
| OCP | Bom nos gateways | Novos gateways podem implementar a interface pequena; a factory central ainda precisa conhecer cada estrategia. |
| LSP | Adequado | Gateways obedecem ao mesmo contrato de resposta; o local e um substituto deterministico nos testes. |
| ISP | Adequado | Interfaces/objetos colaborativos sao pequenos; nao ha interfaces amplas impostas aos consumidores. |
| DIP | Parcial | Services aceitam collaborators injetados, mas defaults e tipos concretos continuam acoplados a Flask/SQLAlchemy. |

### DRY

Corrigido:

- `pyproject.toml` passou a ser a fonte de dependencias Python; `requirements*.txt` sao wrappers.
- Validacao repetida foi consolidada.
- Configuracoes de modelos possuem defaults alinhados entre UI e backend.
- Utilitarios mortos e tres dependencias frontend sem uso foram removidos nesta rodada, alem das remocoes anteriores.

Duplicacoes deliberadas ou residuais:

- OpenAPI e serializacao ORM representam o mesmo contrato em dois lugares manuais; TypeScript deixou de ser uma terceira fonte.
- `VITE_CHAT_MODELS` e `ALLOWED_CHAT_MODELS` precisam permanecer alinhados manualmente.
- Textos e schemas da fonte OpenAPI continuam manuais.

Tipos TypeScript gerados e validacao de drift foram concluidos. O proximo passo, apenas se o contrato crescer e o risco justificar, e validar respostas Python reais contra o schema ou adotar schemas Python que tambem produzam documentacao; nao adicionar uma biblioteca apenas para reduzir linhas.

### KISS

O gateway local, SQLite, Flask blueprints e feature folders sao escolhas proporcionais ao escopo. Foram evitadas abstracoes sem segundo consumidor. As configuracoes de FAISS, a denominacao de streaming e a credencial compilada no frontend eram pontos em que a aparencia era mais complexa/capaz que a implementacao; a documentacao e o fluxo de credencial foram corrigidos para expor a realidade.

### Design Patterns

Padroes presentes e adequados:

- Application Factory: criacao/configuracao do Flask.
- Strategy: gateways de chat.
- Repository: acesso a livros, sessoes, mensagens e anexos.
- Dependency Injection: construtores dos services.
- Facade: cliente HTTP do frontend.
- Feature Modules: chat, livros e configuracoes.
- Composition Root: `App.tsx` no browser e `create_app` no backend.

Nao ha justificativa atual para adicionar CQRS, event bus, mediator ou microservices. Um Unit of Work e portas de repository tornam-se uteis quando houver Postgres/multitenancy ou use cases com transacoes mais complexas.

## Correcoes aplicadas

### Integridade de entrada e dados

- Rejeicao consistente de JSON que nao seja objeto.
- Rejeicao de tipos incorretos em titulo, conteudo, modelo, thinking mode, feedback e IDs de anexo.
- Validacao de ano com quatro digitos na criacao e importacao de livros.
- Rejeicao de anexo pertencente a outra sessao ou ja vinculado a uma mensagem.
- Preservacao da atomicidade de mensagem do usuario, vinculo dos anexos e resposta do assistente no mesmo commit.

### Seguranca e operacao

- Comparacao da API key com `compare_digest` e esquema Bearer case-insensitive.
- IDs externos de request sao limitados a 128 caracteres e a um alfabeto seguro.
- Filtro de request ID foi ligado ao handler que realmente formata logs filhos.
- Cada request emite metodo, path, status e `duration_ms`; excecoes 500 sao registradas.
- Rate-limit storage em memoria foi tornado explicito para eliminar configuracao implicita/warning.
- OpenAPI agora declara Bearer auth e isenta apenas o health check.
- Erros internos `ValueError` nao vazam nem sao mascarados como validacao do cliente.
- Uploads usam uma policy unica de allowlist, nome seguro, MIME declarado, assinatura/conteudo e MIME canonico definido pelo servidor.
- Arquivos sao copiados com limite para quarentena; so recebem o nome final por rename atomico depois da validacao e sao removidos se o commit do banco falhar.
- O frontend envia campos e arquivos em um unico `POST /chat/messages`; staging, vinculo e mensagens compartilham o commit, com rollback e compensacao fisica em qualquer falha anterior.
- `cleanup-uploads` fornece o backstop idempotente para clientes legados/crash: usa idade minima, dry-run, nomes gerados, confinamento a `UPLOAD_DIR`, nao segue symlinks, faz DELETE condicional e preserva paths ainda referenciados.
- Importacao e anexos compartilham limite de tamanho; PDFs possuem limites de paginas, content streams descompactados, texto extraido e deadline cooperativo.
- Limites de recurso invalidos agora interrompem o startup, inclusive nome configurado acima da coluna de 255 caracteres.
- `pypdf>=6.14.2` preserva os limites de seguranca recentes da propria biblioteca, alem dos limites mais estritos da aplicacao.
- `/metrics` expoe counters/histograms Prometheus para requests e gateways, usa templates de rota para limitar cardinalidade e agrega os workers Gunicorn no modo multiprocess.

### Frontend

- `App.tsx` foi convertido em raiz de composicao; sidebar, header, conversa, composer, livros e configuracoes foram extraidos.
- Em falha/abort de envio, texto e anexos locais voltam ao composer; previews so sao revogados em sucesso, remocao ou unmount. Nao existe mais uma sequencia remota upload-then-send no cliente corrente.
- Controles de anexo/audio ficam desabilitados durante envio para evitar corrida.
- A API key nao usa mais `VITE_API_KEY`; e informada em runtime e guardada em `sessionStorage`.
- Lista de modelos e configuravel e o fallback contem apenas os dois modelos aceitos pelo backend por default.
- Datas relativas, grupos e metadados HTML foram localizados para PT-BR.
- Playwright usa Chromium gerenciado, retry apenas no CI e traces em falha.
- Um smoke separado sobe Vite e Flask, atravessa o proxy real e confirma chat, anexo multipart e livro persistidos em SQLite de arquivo isolado, sem compartilhar a conexão `:memory:` entre requisições concorrentes.
- ESLint ignora o artefato gerado pelo Storybook.

### Dependencias e entrega

- Dependencias Python foram consolidadas em `pyproject.toml` com extras `dev` e `ai`.
- A imagem backend instala apenas runtime, sem pytest/Ruff e sem o extra pesado de IA.
- `requirements.txt`, `requirements-dev.txt` e `requirements-ai.txt` preservam compatibilidade sem listas divergentes.
- CI backend usa o mesmo metadata de dependencias.
- A spec executavel exporta `backend/openapi.json`; `openapi-typescript` gera `schema.d.ts`, e backend/frontend CI bloqueiam artefatos desatualizados.
- `make frontend-test-cov` agora executa o script de cobertura correto.
- `*.egg-info` foi ignorado e o artefato local gerado durante validacao foi removido.
- Dependencias frontend sem uso foram removidas do manifesto/lockfile.
- `pnpm 10.34.5` foi fixado no manifesto e nos workflows; Corepack/Docker deixam de selecionar uma major diferente silenciosamente.

## TDD e piramide de testes

### Estado atual

```text
               Browser/full-stack
      1 smoke real + 5 UI pass / 1 skip
   (jornada real no topo; UI detalhada com mocks)

       Integracao de componentes e HTTP
  Flask test client + SQLite; React Testing Library
       maior parte dos 305 + 109 testes

           Unidade / funcoes puras
 validacao, parsing, config, hashing, gateways,
 utils, hooks, attachments e credenciais
```

A forma e saudavel: muitos testes rapidos na base/meio e poucos testes de browser. Os cenarios detalhados de UI continuam interceptando a API para serem deterministicos; a lacuna React -> proxy Vite -> Flask -> SQLite foi fechada por uma unica jornada separada com gateway local.

Proxima melhoria da piramide:

1. Manter testes puros para validadores, parsers, policies e formatters.
2. Manter Flask client/SQLite e React Testing Library como camada de integracao dominante.
3. Manter o unico smoke full-stack focado na integracao entre processos; ampliar apenas quando surgir uma nova jornada critica.
4. Reservar browser tests detalhados para jornadas criticas; nao duplicar toda regra de negocio no topo caro da piramide.

Todas as correcoes desta revisao receberam teste de regressao no nivel mais proximo do risco. O fluxo recomendado para novos fixes e: reproduzir com teste falhando, aplicar a menor correcao, refatorar com a suite verde e atualizar contrato/documentacao quando o comportamento publico mudar.

## Riscos residuais priorizados

### P0 — antes de deploy publico ou multiusuario

| Risco | Por que importa | Criterio de aceite |
| --- | --- | --- |
| Auth e ownership reais | Uma API key compartilhada nao identifica usuario; quem possui a chave acessa todo o conjunto de dados. | Identity provider/JWT ou sessao, `user_id` nos recursos e testes cruzados de 403/404. |
| Uploads publicos/hostis | Assinatura valida formato, nao garante que o conteudo seja benigno; deadline cooperativo nao interrompe uma unica operacao presa no parser. | AV/CDR e parsing em processo/worker isolado com timeout preemptivo conforme exposicao. |
| Infra multiworker | SQLite e `memory://` no limiter nao fornecem concorrencia/contagem global para escala publica. | Postgres e storage compartilhado do limiter, ou limites operacionais formalmente aceitos para uma unica instancia. |

### P1 — confiabilidade e manutencao

| Risco | Estado | Proximo corte |
| --- | --- | --- |
| Streaming | SSE apenas reproduz resposta ja persistida e ocupa worker sincrono. | Gateway com streaming real, cancelamento, backpressure e persistencia incremental. |
| Contrato Python manual | Serializacao ORM e fonte OpenAPI ainda podem divergir; artefato e TS ja sao gerados/verificados. | Validar respostas reais contra o schema se novos endpoints aumentarem o risco. |
| Reprodutibilidade Python | Ha ranges no `pyproject`, mas nao lock de ambiente. | Lock com `uv`, pip-tools ou ferramenta escolhida e politica de atualizacao. |
| Frontend em container | Compose usa Vite dev server. | Imagem multi-stage com artefato estatico/proxy para perfil de producao. |

### P2 — evolucao controlada

- Separar `chat.py` em policy/config, gateways, prompt/context e use case quando houver nova mudanca nessas areas.
- Adicionar retry com backoff/jitter somente para erros idempotentes e antes de persistir resposta; controlar duplicacao/custo do provedor.
- Construir dashboards/alertas e, se necessario, complementar Prometheus com OpenTelemetry para traces, tokens e custo.
- Avaliar code splitting do bundle de documentacao do Storybook se ele passar a ser publicado; o build atual conclui, mas avisa sobre chunk acima de 500 kB.
- Conectar busca semantica ao acervo real ou remover de vez as configuracoes FAISS inativas.
- Migrar busca textual Python-side para FTS/SQL e paginacao por cursor quando o volume justificar.
- Adotar mypy/Pyright se tipagem estatica backend passar a ser um objetivo; `compileall` verifica sintaxe, nao tipos.
- Expor modelos permitidos por endpoint de configuracao para eliminar o alinhamento manual entre duas variaveis.

## Compatibilidade e mudancas de comportamento

- Clientes que enviavam `null`, arrays ou objetos em campos textuais agora recebem 400 em vez de coercao silenciosa/erro interno.
- Um anexo ja vinculado nao pode ser reutilizado para outra mensagem.
- Um `ValueError` interno agora vira 500 generico e logado; validacoes de cliente continuam 400 por `ValidationError`.
- IDs de request inseguros ou maiores que 128 caracteres sao substituidos por UUID.
- O fallback da UI mostra somente DeepSeek Flash e `gpt-4.1-mini`. Modelos adicionais exigem alinhamento entre `VITE_CHAT_MODELS` e `ALLOWED_CHAT_MODELS`.
- A API key deixa de ser embutida no build; usuarios de backend protegido devem informa-la em Configuracoes a cada sessao do navegador.
- Uploads com MIME incompatível, assinatura inválida, texto não UTF-8/JSON inválido, nome excessivo ou limite excedido agora recebem 400 antes da persistencia definitiva.
- Importacao de PDF criptografado ou acima dos limites configurados agora recebe 400; operadores com limites invalidos recebem erro no startup.
- O formulario de livros envia `publication_year` numerico, conforme o contrato gerado.
- O frontend envia anexos no multipart do proprio `POST /chat/messages`; `POST /attachments` e seu DELETE permanecem apenas para compatibilidade.
- `/metrics` passa a fazer parte da superficie operacional e exige a mesma API key das demais rotas quando configurada.

Nenhuma migration de dados destrutiva foi adicionada nesta revisao.

## Evidencias de verificacao

| Verificacao | Resultado |
| --- | --- |
| Ruff lint | Passou. |
| Ruff format check | Passou em 69 arquivos. |
| Pytest + coverage | 305 passaram; 98.67%; gate 95%; sem warnings. |
| ESLint | Passou. |
| TypeScript | Passou. |
| OpenAPI/type drift | Exporter backend e `pnpm api:check` passaram. |
| Vitest + coverage | 19 arquivos, 109 testes; 86.08% lines; todos os gates globais passaram. |
| Vite production build | Passou. |
| Storybook build | Passou; registrou aviso nao bloqueante de chunk de documentacao acima de 500 kB. |
| Playwright Chromium | 5 passaram; 1 mobile-only pulado no projeto desktop. |
| Playwright full-stack | 1 passou via Vite proxy + Flask + SQLite de arquivo isolado. |
| Docker Compose build | Backend e frontend compilados com sucesso. |
| Smoke da imagem Gunicorn | `/metrics` respondeu 200 com 2 workers e agregou a serie normalizada de `/api/v1/health`. |

## Referencias tecnicas consultadas nesta continuacao

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): base para allowlist, nome gerado/normalizado, limite, storage fora do webroot, checagem de assinatura e defesa em profundidade.
- [pypdf — Extract Text](https://pypdf.readthedocs.io/en/latest/user/extract-text.html): documenta o risco de content streams descompactados muito maiores que o arquivo e recomenda medir o stream antes da extracao.
- [pypdf — Robustness and strict=False](https://pypdf.readthedocs.io/en/latest/user/robustness.html) e [Security](https://pypdf.readthedocs.io/en/latest/user/security.html): embasaram parser estrito, versao minima com limites internos e limites adicionais da aplicacao.
- [openapi-typescript CLI](https://openapi-ts.dev/cli): geracao local e modo `--check` para impedir drift.
- [Playwright webServer](https://playwright.dev/docs/test-webserver): configuracao suportada de multiplos servidores para o smoke full-stack.
- [Vitest — maxWorkers](https://main.vitest.dev/config/maxworkers): limite explicito de paralelismo para estabilizar memoria em CI e maquinas de desenvolvimento.
- [SQLAlchemy 2.0 — Transactions and Connection Management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html): commit/rollback explicitos e framing da unidade de trabalho.
- [Flask 3.1 — Resource Use](https://flask.palletsprojects.com/en/stable/web-security/#resource-use): limites de corpo/formulario globais e por request.
- [Prometheus Python client — Multiprocess Mode](https://prometheus.github.io/client_python/multiprocess/): registry por scrape, diretorio limpo antes do Gunicorn e hook `child_exit`.
- [Prometheus — Metric and label naming](https://prometheus.io/docs/practices/naming/): unidades base e rejeicao de labels de cardinalidade nao limitada.

## Decisao final

O codigo nao precisa ser convertido integralmente para uma Clean Architecture academica. A direcao correta e manter as fronteiras atuais, impedir que Flask/SQLAlchemy se espalhem para novos modulos de regra, extrair portas apenas quando houver segundo adapter e investir primeiro nos riscos de seguranca, contrato e operacao. Isso preserva KISS sem abandonar SOLID, DRY ou testabilidade.
