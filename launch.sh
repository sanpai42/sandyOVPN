#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ -x "$APP_DIR/.venv/bin/python" ]] && "$APP_DIR/.venv/bin/python" -c "import cryptography" 2>/dev/null; then
  PYTHON="$APP_DIR/.venv/bin/python"
else
  PYTHON=python3
fi

exec "$PYTHON" -m sandyvpn
