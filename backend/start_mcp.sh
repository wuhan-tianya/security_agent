#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found in PATH"
  exit 1
fi

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-19000}"

uv sync --extra dev
exec uv run uvicorn app.mcp.local_server:app --host "$HOST" --port "$PORT" --reload
