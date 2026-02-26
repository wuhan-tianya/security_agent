from __future__ import annotations

from fastapi import APIRouter, Depends

from app.memory.repository import Repository
from app.skills.registry import SkillRegistry


router = APIRouter(prefix="/v1", tags=["ops"])


def get_repo() -> Repository:
    from app.main import app

    return app.state.repo


def get_registry() -> SkillRegistry:
    from app.main import app

    return app.state.agent_service.registry


@router.get("/tools")
async def list_tools(registry: SkillRegistry = Depends(get_registry)):
    tools = registry.list_tools()
    return {"tools": [{"name": t.name, "description": t.description} for t in tools]}


@router.get("/sessions/{session_id}/memory")
def get_memory(session_id: str, repo: Repository = Depends(get_repo)):
    return {
        "session_id": session_id,
        "recent_messages": repo.get_recent_messages(session_id),
        "latest_summary": repo.get_latest_summary(session_id),
    }


@router.post("/sessions/{session_id}/reset")
def reset_session(session_id: str, repo: Repository = Depends(get_repo)):
    db = repo.db
    with db.connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM memory_snapshots WHERE session_id=?", (session_id,))
    return {"ok": True, "session_id": session_id}
