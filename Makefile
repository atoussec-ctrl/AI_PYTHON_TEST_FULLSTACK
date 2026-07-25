# ═══════════════════════════════════════════════════════════
# MindSight AI — Makefile
# ═══════════════════════════════════════════════════════════

BACKEND_VENV := backend/.venv
BACKEND_PY := $(BACKEND_VENV)/bin/python
BACKEND_PYTEST := $(BACKEND_VENV)/bin/pytest
BACKEND_RUFF := $(BACKEND_VENV)/bin/ruff
BACKEND_PIP := python3 -m pip --python $(BACKEND_VENV)

.PHONY: install backend-venv backend-install backend-install-ai dev backend-dev frontend-dev docker-up docker-down docker-logs test lint typecheck build clean backend-test backend-test-cov frontend-test frontend-test-cov seed backend-seed db-backup db-restore uploads-cleanup uploads-cleanup-dry-run api-generate api-check

BACKEND_DB := backend/storage/app.db

# ── Install ──
install: backend-install
	@echo "Installing frontend dependencies..."
	cd frontend && pnpm install
	@echo "All core dependencies installed"

backend-venv:
	@if [ -x $(BACKEND_PY) ]; then \
		: ; \
	elif python3 -m venv $(BACKEND_VENV) 2>/dev/null; then \
		: ; \
	else \
		echo "Creating venv without ensurepip (install python3-venv for a simpler setup)..."; \
		python3 -m venv $(BACKEND_VENV) --without-pip; \
		curl -fsSL https://bootstrap.pypa.io/get-pip.py | $(BACKEND_PY); \
	fi

backend-install: backend-venv
	@echo "Installing backend dependencies into $(BACKEND_VENV)..."
	cd backend && python3 -m pip --python .venv install -r requirements-dev.txt

backend-install-ai: backend-venv
	@echo "Installing optional AI dependencies into $(BACKEND_VENV)..."
	cd backend && python3 -m pip --python .venv install -e ".[ai,dev]"

# ── Development ──
backend-dev:
	cd backend && .venv/bin/python run.py

frontend-dev:
	cd frontend && pnpm dev

dev:
	@echo "🚀 Starting MindSight AI..."
	$(MAKE) backend-dev & $(MAKE) frontend-dev

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Database ──
backend-seed:
	cd backend && .venv/bin/python seed.py

seed: backend-seed

# Faz backup do SQLite atual em storage/backups/app-<timestamp>.db
db-backup:
	@mkdir -p backend/storage/backups
	@if [ -f $(BACKEND_DB) ]; then \
		cp $(BACKEND_DB) backend/storage/backups/app-$$(date +%Y%m%d-%H%M%S).db ; \
		echo "Backup salvo em backend/storage/backups/" ; \
	else \
		echo "Nada para fazer backup: $(BACKEND_DB) não existe." ; \
	fi

# Restaura o backup mais recente. Uso: make db-restore
db-restore:
	@latest=$$(ls -1t backend/storage/backups/app-*.db 2>/dev/null | head -n1) ; \
	if [ -n "$$latest" ]; then \
		cp "$$latest" $(BACKEND_DB) ; \
		echo "Restaurado de $$latest" ; \
	else \
		echo "Nenhum backup encontrado em backend/storage/backups/." ; \
	fi

uploads-cleanup:
	cd backend && .venv/bin/python -m flask --app run:app cleanup-uploads

uploads-cleanup-dry-run:
	cd backend && .venv/bin/python -m flask --app run:app cleanup-uploads --dry-run

# ── Tests ──
backend-test:
	cd backend && .venv/bin/pytest -v --tb=short

backend-test-cov:
	cd backend && .venv/bin/pytest --cov=app --cov-report=term-missing --cov-fail-under=95 -v

frontend-test:
	cd frontend && pnpm test

frontend-test-cov:
	cd frontend && pnpm test:coverage

test: backend-test frontend-test

# ── Quality ──
lint:
	cd backend && .venv/bin/ruff check .
	cd frontend && pnpm lint

typecheck:
	cd backend && .venv/bin/python -m compileall app
	cd frontend && pnpm typecheck

api-generate:
	cd backend && .venv/bin/python scripts/export_openapi.py
	cd frontend && pnpm api:generate

api-check:
	cd backend && .venv/bin/python scripts/export_openapi.py --check
	cd frontend && pnpm api:check

# ── Build ──
build:
	cd frontend && pnpm build

# ── Clean ──
clean:
	rm -rf backend/storage/app.db
	rm -rf backend/storage/faiss.index
	rm -rf backend/storage/uploads/*
	rm -rf frontend/dist
	rm -rf frontend/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
