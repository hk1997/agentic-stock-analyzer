# Auto-detect local network IP address (macOS first, then Linux fallback)
LOCAL_IP := $(shell ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I | awk '{print $$1}' 2>/dev/null || echo "localhost")

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
	@echo "Detected Local IP: $(LOCAL_IP)"
	@echo "Starting Docker Compose environment..."
	VITE_API_URL=http://$(LOCAL_IP):8000 docker-compose --env-file /dev/null up --build

docker-down:
	@echo "Stopping Docker Compose environment..."
	docker-compose --env-file /dev/null down

docker-clean:
	@echo "Stopping Docker Compose and cleaning volumes..."
	docker-compose --env-file /dev/null down -v

docker-persistent-up:
	@echo "Detected Local IP: $(LOCAL_IP)"
	@echo "Starting persistent Docker Compose environment in the background..."
	VITE_API_URL=http://$(LOCAL_IP):8000 docker-compose -f docker-compose.persistent.yml up -d

docker-persistent-down:
	@echo "Stopping persistent Docker Compose environment..."
	docker-compose -f docker-compose.persistent.yml down



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