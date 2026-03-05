.PHONY: setup dev-api dev-ui test lint clean refresh docker-dev docker-down docker-clean

# ── Setup ──────────────────────────────────────────────────
setup:
	@chmod +x scripts/setup.sh && bash scripts/setup.sh

# Force a clean reinstall if dependencies get messy
refresh: clean setup

# ── Development Servers (Local) ─────────────────────────────
dev-api:
	@echo "Starting FastAPI on http://localhost:8000 ..."
	poetry run uvicorn api.main:app --reload --port 8000

dev-ui:
	@echo "Starting Vite on http://localhost:5173 ..."
	cd web-ui-v2 && npm run dev

# ── Docker Development ─────────────────────────────────────
docker-dev:
	@echo "Starting Docker Compose environment..."
	docker-compose --env-file /dev/null up --build

docker-down:
	@echo "Stopping Docker Compose environment..."
	docker-compose --env-file /dev/null down

docker-clean:
	@echo "Stopping Docker Compose and cleaning volumes..."
	docker-compose --env-file /dev/null down -v

# ── Tests & Linting ────────────────────────────────────────
test:
	@echo "Running Python tests ..."
	cd tests && poetry run pytest --confcutdir=. -v --tb=short

lint:
	@echo "Running Ruff linter..."
	poetry run ruff check api/ tests/ --fix
	@if [ -d web-ui-v2/node_modules ]; then \
		cd web-ui-v2 && npm run lint; \
	fi

# ── Clean ──────────────────────────────────────────────────
clean:
	rm -rf .pytest_cache .ruff_cache
	find . -path ./web-ui -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	@if command -v poetry &> /dev/null; then \
		echo "Removing poetry env if exists"; \
		poetry env remove python || true; \
	fi
	rm -rf web-ui-v2/node_modules
	@echo "✓ Cleaned environment and cache"