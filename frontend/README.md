# Frontend — MindSight AI

Aplicacao React 19 + TypeScript + Vite. A raiz `App.tsx` coordena os fluxos e as interfaces visuais ficam separadas por feature:

- `src/features/chat`: sidebar, cabecalho, conversa, composer, anexos, audio e Markdown.
- `src/features/books`: administracao, importacao, filtros e cards.
- `src/features/settings`: tema, modelo, thinking mode e credencial da API por sessao.
- `src/shared/api`: cliente HTTP, contratos TypeScript e credencial runtime.
- `src/components/ui`: componentes visuais basicos.

## Desenvolvimento

```bash
pnpm install --frozen-lockfile
pnpm dev
```

O servidor usa a porta 3002 e faz proxy de `/api` para `VITE_API_PROXY_TARGET` (default `http://localhost:5000`).

Variaveis relevantes:

- `VITE_API_BASE_URL`: base da API; default local `http://localhost:5000/api/v1`.
- `VITE_API_PROXY_TARGET`: destino do proxy do Vite.
- `VITE_APP_NAME`: nome exibido.
- `VITE_DEFAULT_THINKING_MODE`: `fast`, `balanced` ou `deep`.
- `VITE_CHAT_MODELS`: CSV de modelos exibidos; deve coincidir com a allowlist do backend.

Nao use `VITE_API_KEY`: toda variavel `VITE_*` e publica no bundle. Se o backend exigir `API_KEY`, informe a credencial na tela Configuracoes; ela permanece apenas em `sessionStorage`. Um deploy publico deve usar autenticacao por usuario e proxy/BFF.

## Qualidade

```bash
pnpm lint
pnpm typecheck
pnpm api:check
pnpm test:coverage
pnpm build
pnpm build-storybook
```

O gate de cobertura inclui todo o codigo executavel em `src`, excluindo apenas testes, stories, tipos puros e o bootstrap `main.tsx`. `src/shared/api/schema.d.ts` e gerado de `backend/openapi.json`; use `pnpm api:generate` apos uma mudanca intencional de contrato e `pnpm api:check` para detectar drift.

## E2E

```bash
pnpm exec playwright install chromium
pnpm test:e2e
pnpm test:e2e:fullstack
```

O Playwright sobe os servidores automaticamente e usa o Chromium gerenciado pelo proprio runner. `test:e2e` intercepta as rotas HTTP para testar a UI deterministicamente. `test:e2e:fullstack` usa as portas 3003/5001, sobe Vite + Flask em modo de teste com SQLite de arquivo isolado em `.cache/fullstack-e2e`, atravessa o proxy real e confirma persistencia de chat, anexo enviado no multipart atomico e livro. Para este ultimo, instale antes o backend em `backend/.venv`.
