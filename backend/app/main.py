from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_chat import router as chat_router
from app.api.routes_tools import router as tools_router
from app.core.config import get_settings
from app.db.database import Database
from app.mcp.client import MCPClientManager
from app.memory.repository import Repository
from app.services.agent_service import AgentService

settings = get_settings()
app = FastAPI(title=settings.app_name)


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
