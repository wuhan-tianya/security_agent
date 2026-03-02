from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.db.database import Database
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

backend_root = Path(__file__).resolve().parents[1]
summaries_dir = backend_root / "summaries"
summaries_dir.mkdir(parents=True, exist_ok=True)
app.mount("/summaries", StaticFiles(directory=str(summaries_dir)), name="summaries")

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

    app.state.db = db
    app.state.repo = repo
    app.state.agent_service = AgentService(repo)


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.include_router(v1_router)
