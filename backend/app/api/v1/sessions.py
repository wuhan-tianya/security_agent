from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repo
from app.memory.repository import Repository

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions(repo: Repository = Depends(get_repo)):
    sessions = repo.list_sessions()
    return {"sessions": sessions}


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
