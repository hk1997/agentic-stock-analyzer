.PHONY: setup dev-api dev-ui test lint clean

VENV := /tmp/stock-venv
PYTHON := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

# ── Setup ──────────────────────────────────────────────────
setup:
	@chmod +x scripts/setup.sh && bash scripts/setup.sh

# ── Development Servers ────────────────────────────────────
dev-api:
	@echo "Starting FastAPI on http://localhost:8000 ..."
	$(PYTHON) -m uvicorn api.main:app --reload --port 8000

dev-ui:
	@echo "Starting Vite on http://localhost:5173 ..."
	cd web-ui-v2 && npx vite --port 5173

# ── Tests ──────────────────────────────────────────────────
test:
	@echo "Running Python tests ..."
	$(PYTHON) -m pytest tests/ -v --tb=short
	@if [ -f web-ui-v2/package.json ]; then \
		echo "Running frontend tests ..."; \
		cd web-ui-v2 && npx vitest run; \
	fi

# ── Lint ───────────────────────────────────────────────────
lint:
	$(PYTHON) -m ruff check api/ app/ tests/
	@if [ -f web-ui-v2/package.json ]; then \
		cd web-ui-v2 && npx eslint src/; \
	fi

# ── Clean ──────────────────────────────────────────────────
clean:
	rm -rf /tmp/stock-venv /tmp/stock-ui-node /tmp/npm-cache
	rm -f .venv
	rm -f web-ui-v2/node_modules
	@echo "✓ Cleaned all temp environments"
