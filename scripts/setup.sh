#!/usr/bin/env bash
# setup.sh — Updated to resolve PyYAML/AWS-CDK dependency conflicts
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

# 1. Upgrade core build tools FIRST (Crucial for PyYAML 6.x)
echo "  → Upgrading build tools..."
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel --quiet

# 2. Pre-install PyYAML with a workaround for the "long" build process
# This prevents the 'ResolutionImpossible' crash during the main requirements install
echo "  → Pre-installing PyYAML..."
"$VENV_DIR/bin/pip" install "PyYAML>=6.0.1" --no-build-isolation --quiet

# 3. Install requirements
echo "  → Installing project dependencies..."
# Removed --quiet here so you can see exactly where it hangs if it fails again
"$VENV_DIR/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
echo "  ✓ Python dependencies installed"

# Create symlink in project root for IDE support
if [ ! -L "$PROJECT_ROOT/.venv" ] && [ ! -d "$PROJECT_ROOT/.venv" ]; then
  ln -sf "$VENV_DIR" "$PROJECT_ROOT/.venv" 2>/dev/null || true
  echo "  ✓ Symlinked .venv → $VENV_DIR"
fi

# ─── Node.js Environment ─────────────────────────────────────────────────
WEBUI_DIR="$PROJECT_ROOT/web-ui-v2"
if [ -f "$WEBUI_DIR/package.json" ]; then
  echo ""
  echo "→ Setting up Node modules at $NODE_DIR ..."
  mkdir -p "$NODE_DIR"

  # Copy package manifests into /tmp so npm install runs there (bypasses EPERM)
  cp "$WEBUI_DIR/package.json" "$NODE_DIR/package.json"
  [ -f "$WEBUI_DIR/package-lock.json" ] && cp "$WEBUI_DIR/package-lock.json" "$NODE_DIR/package-lock.json" || true

  # Run npm install inside /tmp
  cd "$NODE_DIR"
  npm install --cache /tmp/npm-cache --quiet
  cd "$PROJECT_ROOT"

  # Attempt to symlink node_modules back into the project.
  # This may fail on macOS due to directory-level EPERM restrictions — that's OK,
  # because `make dev-ui` references the /tmp vite binary directly.
  if [ ! -L "$WEBUI_DIR/node_modules" ] && [ ! -d "$WEBUI_DIR/node_modules" ]; then
    ln -sf "$NODE_DIR/node_modules" "$WEBUI_DIR/node_modules" 2>/dev/null && \
      echo "  ✓ Symlinked node_modules → $NODE_DIR/node_modules" || \
      echo "  ⚠ Could not symlink node_modules (EPERM) — using /tmp vite binary directly"
  else
    echo "  ✓ node_modules already present"
  fi
fi

echo ""
echo "=== ✅ Setup Complete ==="