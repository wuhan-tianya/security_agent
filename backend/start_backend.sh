#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found in PATH"
  exit 1
fi

uv sync --extra dev
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
