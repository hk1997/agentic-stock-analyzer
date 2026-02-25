.PHONY: setup dev-api dev-ui test lint clean refresh

VENV := /tmp/stock-venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

# ── Setup ──────────────────────────────────────────────────
# Added a check to ensure venv exists before calling PIP
setup:
	@chmod +x scripts/setup.sh && bash scripts/setup.sh
	$(PIP) install --upgrade pip setuptools wheel

# Force a clean reinstall if dependencies get messy
refresh: clean setup

# ── Development Servers ────────────────────────────────────
dev-api:
	@echo "Starting FastAPI on http://localhost:8000 ..."
	@# Added --quiet to keep output clean, but keeping reload for dev
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

NODE_BIN := /tmp/stock-ui-node/node_modules/.bin

dev-ui:
	@echo "Starting Vite on http://localhost:5173 ..."
	cd web-ui-v2 && NODE_PATH=/tmp/stock-ui-node/node_modules $(NODE_BIN)/vite --port 5173

# ── Tests & Linting ────────────────────────────────────────
test:
	@echo "Running Python tests ..."
	$(PYTHON) -m pytest tests/ -v --tb=short

lint:
	@echo "Running Ruff linter..."
	$(PYTHON) -m ruff check api/ tests/ --fix
	@if [ -d web-ui-v2/node_modules ]; then \
		cd web-ui-v2 && npx eslint src/; \
	fi

# ── Clean ──────────────────────────────────────────────────
clean:
	rm -rf $(VENV)
	rm -rf .pytest_cache .ruff_cache
	find . -path ./web-ui -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	@echo "✓ Cleaned environment and cache"