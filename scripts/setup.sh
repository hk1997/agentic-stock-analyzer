#!/usr/bin/env bash
# setup.sh — Bootstrap dev environments using /tmp to bypass macOS directory restrictions
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="/tmp/stock-venv"
NODE_DIR="/tmp/stock-ui-node"

echo "=== 🔧 Agentic Stock Analyzer — Environment Setup ==="

# ─── Python Virtual Environment ───────────────────────────────────────────
echo ""
echo "→ Setting up Python venv at $VENV_DIR ..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "  ✓ Created venv"
else
  echo "  ✓ Venv already exists"
fi

# Install/upgrade pip and install requirements
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt" --quiet
echo "  ✓ Python dependencies installed"

# Create symlink in project root for IDE support
if [ ! -L "$PROJECT_ROOT/.venv" ] && [ ! -d "$PROJECT_ROOT/.venv" ]; then
  ln -sf "$VENV_DIR" "$PROJECT_ROOT/.venv" 2>/dev/null || true
  echo "  ✓ Symlinked .venv → $VENV_DIR"
elif [ -L "$PROJECT_ROOT/.venv" ]; then
  echo "  ✓ .venv symlink already exists"
else
  echo "  ⚠ .venv directory exists (not a symlink), skipping"
fi

# ─── Node.js Environment ─────────────────────────────────────────────────
WEBUI_DIR="$PROJECT_ROOT/web-ui-v2"
if [ -f "$WEBUI_DIR/package.json" ]; then
  echo ""
  echo "→ Setting up Node modules at $NODE_DIR ..."
  mkdir -p "$NODE_DIR"

  # Install into /tmp, then symlink
  cd "$WEBUI_DIR"
  npm install --cache /tmp/npm-cache --prefix "$NODE_DIR" --quiet 2>/dev/null || \
    npm install --cache /tmp/npm-cache --prefix "$NODE_DIR"

  # Symlink node_modules back into project
  if [ ! -L "$WEBUI_DIR/node_modules" ] && [ ! -d "$WEBUI_DIR/node_modules" ]; then
    ln -sf "$NODE_DIR/node_modules" "$WEBUI_DIR/node_modules" 2>/dev/null || true
    echo "  ✓ Symlinked node_modules"
  elif [ -L "$WEBUI_DIR/node_modules" ]; then
    echo "  ✓ node_modules symlink already exists"
  else
    echo "  ⚠ node_modules directory exists, skipping"
  fi
  cd "$PROJECT_ROOT"
else
  echo ""
  echo "→ Skipping Node setup (web-ui-v2/package.json not found yet)"
fi

echo ""
echo "=== ✅ Setup Complete ==="
echo ""
echo "Quick start:"
echo "  make dev-api    # Start FastAPI backend on :8000"
echo "  make dev-ui     # Start Vite frontend on :5173"
echo "  make test       # Run all tests"
