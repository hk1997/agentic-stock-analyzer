#!/usr/bin/env bash
# setup.sh — Updated to use Poetry and native npm install
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== 🔧 Agentic Stock Analyzer — Environment Setup ==="

# ─── Python Environment ───────────────────────────────────────────
echo ""
echo "→ Checking for Poetry..."
if ! command -v poetry &> /dev/null; then
  echo "  ⚠ Poetry is not installed. Please install it: curl -sSL https://install.python-poetry.org | python3 -"
  exit 1
fi

echo "→ Installing Python dependencies with Poetry..."
cd "$PROJECT_ROOT"
poetry install

# ─── Node.js Environment ─────────────────────────────────────────────────
WEBUI_DIR="$PROJECT_ROOT/web-ui-v2"
if [ -d "$WEBUI_DIR" ]; then
  echo ""
  echo "→ Setting up Node modules..."
  cd "$WEBUI_DIR"
  npm install
  cd "$PROJECT_ROOT"
fi

echo ""
echo "=== ✅ Setup Complete ==="