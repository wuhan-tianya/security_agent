# Security Agent

FastAPI + LangGraph backend for local skill-driven security tooling.

## Quick Start

### 1. Enter backend directory

```bash
cd backend
```

### 2. Install dependencies (uv)

```bash
uv sync --extra dev
```

### 3. Configure model parameters (JSON)

Edit `backend/config/settings.json` (if you are in repo root), or `config/settings.json` (if already in `backend/`):

```json
{
  "llm_base_url": "http://localhost:8001/v1",
  "llm_api_key": "",
  "llm_model": "gpt-4o-mini",
  "llm_timeout_seconds": 30
}
```

Optional override:
- `CONFIG_FILE=/path/to/settings.json`
- environment variables (e.g. `LLM_MODEL`) override JSON values.

Kimi/OpenAI-Compatible 注意事项：
- `llm_base_url` 只填 API base（例如 `https://api.kimi.com/coding/v1`），不要包含 `/chat/completions`。
- 若出现 `403 Forbidden`，优先检查：
  - `llm_api_key` 是否有效且有对应模型权限。
  - `llm_model` 是否在当前账号可用。
  - 网关/代理是否限制该路径（后端已默认禁用环境代理转发）。

### 4. Run service

```bash
./start_backend.sh
```

Service default address:

```text
http://127.0.0.1:8000
```

### 5. Health check

```bash
curl http://127.0.0.1:8000/healthz
```

Expected:

```json
{"ok": true}
```

### 6. Start chat stream

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-001",
    "user_input": "请做安全检查",
    "model": "gpt-4o-mini"
  }'
```

## Tests

```bash
uv run pytest -q
```
