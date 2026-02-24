# Security Agent

FastAPI + LangGraph backend for multi-vehicle remote MCP routing.

## Quick Start

### 1. Enter backend directory

```bash
cd backend
```

### 2. Install dependencies (uv)

```bash
uv sync --extra dev
```

### 3. Configure model/MCP parameters (JSON)

Edit `backend/config/settings.json` (if you are in repo root), or `config/settings.json` (if already in `backend/`):

```json
{
  "llm_base_url": "http://localhost:8001/v1",
  "llm_api_key": "",
  "llm_model": "gpt-4o-mini",
  "llm_timeout_seconds": 30,
  "mcp_mode": "hybrid",
  "mcp_timeout_seconds": 30
}
```

Optional override:
- `CONFIG_FILE=/path/to/settings.json`
- environment variables (e.g. `LLM_MODEL`) override JSON values.

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

### 6. Add a vehicle (required before MCP call)

```bash
curl -X POST http://127.0.0.1:8000/v1/vehicles \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_name": "car-a",
    "ip": "10.1.1.2",
    "mcp_endpoint": "http://10.1.1.2:9000",
    "status": "online",
    "is_configured": true,
    "auth_type": "none",
    "auth_secret_ref": null
  }'
```

### 7. Start chat stream

```bash
curl -N -X POST http://127.0.0.1:8000/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-001",
    "user_input": "请连接 10.1.1.2 并做安全检查",
    "model": "gpt-4o-mini"
  }'
```

## Tests

```bash
uv run pytest -q
```
