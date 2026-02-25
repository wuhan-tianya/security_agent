from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes_chat import router as chat_router
from app.api.routes_tools import router as tools_router
from app.core.config import get_settings
from app.db.database import Database
from app.mcp.client import MCPClientManager
from app.memory.repository import Repository
from app.services.agent_service import AgentService

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_logger(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.time()
    body_preview = ""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        try:
            body = await request.body()
            body_preview = body.decode("utf-8", errors="ignore")[:2000]
        except Exception:
            body_preview = ""
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    logger.bind(request_id=request_id).info(
        "method={} path={} status={} duration_ms={} body={}",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        body_preview,
    )
    response.headers["x-request-id"] = request_id
    return response


@app.on_event("startup")
def on_startup() -> None:
    db = Database(settings.db_path)
    db.init_schema()

    repo = Repository(db)
    mcp = MCPClientManager()

    app.state.db = db
    app.state.repo = repo
    app.state.mcp_manager = mcp
    app.state.agent_service = AgentService(repo)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.include_router(chat_router)
app.include_router(tools_router)
