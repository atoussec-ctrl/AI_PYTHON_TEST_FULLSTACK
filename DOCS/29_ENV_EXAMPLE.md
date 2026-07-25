# Variaveis de ambiente

As variaveis ficam em `.env` na raiz do projeto. O backend carrega esse arquivo via `backend/app/env_loader.py`.

## Aplicacao

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `APP_ENV` | `development`, `testing`, `production` | Seleciona config Flask. |
| `LOG_LEVEL` | `INFO` | Aplicado ao logger raiz. O request ID recebido e validado/limitado e cada requisicao emite metodo, path, status e `duration_ms`. |
| `FLASK_DEBUG` | `false` | Liga o debug server apenas quando explicitamente `true` em `backend/run.py`. |
| `SECRET_KEY` | valor forte | Chave de assinatura Flask. Obrigatoria em producao. |
| `API_KEY` | valor forte | Segredo compartilhado exigido no header `Authorization: Bearer <valor>` para toda a API, exceto `/health`. Vazio = API aberta (padrao de dev local). |

Em `APP_ENV=production`, o startup falha (`InsecureConfigurationError`) se `SECRET_KEY` ou `API_KEY` estiverem vazios ou forem um placeholder conhecido (`replace-me`, `changeme`, `change-me`, ou o default de dev). Ver `app/config.py::assert_production_config_is_safe`.

## Banco de dados

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./storage/app.db` | URI SQLAlchemy. |

Tradeoff atual: SQLite simplifica setup local, mas nao resolve concorrencia, migracoes e operacao multiusuario como Postgres.

## Gateway de chat

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `CHAT_GATEWAY` | `local`, `openai`, `huggingface`, `auto` | Seleciona gateway. |
| `OPENAI_API_KEY` | chave real | Usada quando gateway OpenAI estiver ativo. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Modelo OpenAI default. |
| `HUGGINGFACE_API_KEY` | chave real | Usada pelo router Hugging Face. |
| `HF_CHAT_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | Modelo HF default. |
| `HF_BASE_URL` | `https://router.huggingface.co/v1` | Endpoint OpenAI-compatible. |
| `CHAT_MAX_OUTPUT_TOKENS` | `4096` | Limite de tokens de saida. |
| `CHAT_MAX_MESSAGE_CHARS` | `8000` | Limite de caracteres da mensagem antes de chamar o provedor. |
| `CHAT_GATEWAY_TIMEOUT_SECONDS` | `30` | Timeout de cada chamada ao provedor — evita requisicao presa indefinidamente. |
| `ALLOWED_CHAT_MODELS` | CSV ou vazio | Allowlist de modelos solicitaveis pelo cliente. Vazio permite apenas `HF_CHAT_MODEL` e `OPENAI_MODEL`. |
| `RATE_LIMIT_CHAT_MESSAGES` | `20 per minute` | Limite por IP no endpoint que chama o provedor pago. Contador em memoria por processo (nao exato sob multiplos workers do Gunicorn sem Redis). |

O modo `local` e o melhor default para desenvolvimento e CI, pois nao depende de rede nem de custo externo.

## LangSmith

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `LANGSMITH_TRACING` | `false` | Habilita tracing. |
| `LANGSMITH_API_KEY` | chave real | Autenticacao LangSmith. |
| `LANGSMITH_PROJECT` | `mindsight-ai` | Projeto de traces. |

O codigo degrada para no-op quando tracing esta desabilitado ou pacote/chave falha.

## Embeddings e busca

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Modelo planejado para embeddings reais. |
| `VECTOR_STORE` | `faiss` | Vector store planejado. |
| `FAISS_INDEX_PATH` | `./storage/faiss.index` | Caminho do indice. |

Estado atual: a busca semantica usa hashing local demonstrativo, nao FAISS real.

## Uploads

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `UPLOAD_DIR` | `./storage/uploads` | Pasta de arquivos. |
| `MAX_UPLOAD_SIZE_MB` | `10` | Limite por arquivo. |
| `MAX_MESSAGE_UPLOAD_SIZE_MB` | `50` | Limite agregado do request multipart de mensagem; aplicado apenas nessa rota. |
| `MAX_ATTACHMENTS_PER_MESSAGE` | `5` | Quantidade máxima de anexos/IDs por mensagem. |
| `ORPHAN_UPLOAD_MAX_AGE_HOURS` | `24` | Idade mínima usada pelo comando idempotente `cleanup-uploads`. |
| `MAX_UPLOAD_FILENAME_CHARS` | `180` | Limite do nome normalizado; o startup rejeita valores acima dos 255 caracteres do schema. |
| `MAX_PDF_PAGES` | `50` | Máximo de páginas processadas por PDF. |
| `MAX_PDF_CONTENT_STREAM_MB` | `16` | Máximo acumulado dos content streams descompactados. |
| `MAX_PDF_EXTRACTED_CHARS` | `100000` | Máximo de caracteres produzidos pelo extrator. |
| `MAX_PDF_PROCESSING_SECONDS` | `10` | Deadline cooperativo verificado entre etapas/páginas. |

Todos esses limites devem ser inteiros positivos; configuração inválida interrompe o startup. O fluxo de upload normaliza o nome, cruza extensão e MIME declarado, valida conteúdo/assinatura, grava primeiro em quarentena e só então faz rename atômico. O frontend envia arquivos e mensagem em um único multipart; erro de lote/commit causa rollback e compensação física. Como backstop para crash e clientes legados, agende `python -m flask --app run:app cleanup-uploads` e valide antes com `--dry-run`.

Recomendacoes adicionais para producao publica:

- Manter testes garantindo remocao fisica quando sessoes/anexos forem deletados.
- Adicionar antivírus/CDR assíncrono conforme exposição e perfil dos documentos.
- Executar parsing pesado em processo/worker isolado quando for necessário um timeout preemptivo; o deadline atual é cooperativo.
- Considerar armazenamento externo, como S3, quando houver escala.

## CORS e frontend

| Variavel | Exemplo | Uso |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3002` | Origens aceitas pelo Flask-CORS. |
| `RATE_LIMIT_DEFAULT` | `200 per minute` | Limite global por IP aplicado a toda a API (ver secao de gateway de chat para o limite dedicado do endpoint de mensagens). |
| `RATELIMIT_STORAGE_URI` | `memory://` | Storage do Flask-Limiter. Use Redis ou equivalente para contador compartilhado entre workers. |
| `VITE_API_BASE_URL` | `http://localhost:5000/api/v1` | Base URL usada pelo frontend. |
| `VITE_API_PROXY_TARGET` | `http://localhost:5000` | Proxy do Vite em desenvolvimento. |
| `VITE_APP_NAME` | `MindSight AI` | Nome exibido na UI. |
| `VITE_DEFAULT_THINKING_MODE` | `balanced` | Modo inicial do chat. |
| `VITE_CHAT_MODELS` | CSV | Modelos exibidos na UI; deve permanecer alinhado a `ALLOWED_CHAT_MODELS`. Sem valor, usa os defaults HF/OpenAI. |

Nunca coloque `API_KEY` em `VITE_*`: o Vite incorporaria o segredo ao bundle publico. A UI recebe a credencial em Configuracoes e a mantem somente em `sessionStorage`. Isso reduz vazamento acidental no build, mas nao substitui autenticacao por usuario; para deploy publico, prefira um proxy/BFF e ownership no backend.
