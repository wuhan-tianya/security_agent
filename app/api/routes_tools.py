from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import VehicleUpsertRequest
from app.mcp.client import MCPClientManager, MCPError
from app.memory.repository import Repository


router = APIRouter(prefix="/v1", tags=["ops"])


def get_repo() -> Repository:
    from app.main import app

    return app.state.repo


def get_mcp_manager() -> MCPClientManager:
    from app.main import app

    return app.state.mcp_manager


@router.get("/tools")
async def list_tools(ip: str | None = None, repo: Repository = Depends(get_repo), mcp: MCPClientManager = Depends(get_mcp_manager)):
    vehicles = repo.list_vehicles()
    if ip:
        vehicles = [v for v in vehicles if v.ip == ip]

    results = []
    for v in vehicles:
        if not v.is_configured or not v.mcp_endpoint:
            continue
        client = mcp.client_for_endpoint(v.mcp_endpoint)
        try:
            tools = await client.list_tools(v.mcp_endpoint)
            for t in tools:
                results.append(
                    {
                        "vehicle_name": v.vehicle_name,
                        "ip": v.ip,
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.input_schema,
                        "source_endpoint": v.mcp_endpoint,
                    }
                )
        except MCPError:
            continue
    return {"tools": results}


@router.get("/sessions/{session_id}/memory")
def get_memory(session_id: str, repo: Repository = Depends(get_repo)):
    return {
        "session_id": session_id,
        "recent_messages": repo.get_recent_messages(session_id),
        "latest_summary": repo.get_latest_summary(session_id),
        "last_vehicle_ip": repo.get_last_vehicle_ip(session_id),
    }


@router.post("/sessions/{session_id}/reset")
def reset_session(session_id: str, repo: Repository = Depends(get_repo)):
    db = repo.db
    with db.connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM memory_snapshots WHERE session_id=?", (session_id,))
        conn.execute("UPDATE sessions SET last_vehicle_ip=NULL WHERE session_id=?", (session_id,))
    return {"ok": True, "session_id": session_id}


@router.get("/vehicles")
def list_vehicles(repo: Repository = Depends(get_repo)):
    vehicles = repo.list_vehicles()
    return {
        "vehicles": [
            {
                "vehicle_name": v.vehicle_name,
                "ip": v.ip,
                "mcp_endpoint": v.mcp_endpoint,
                "status": v.status,
                "is_configured": v.is_configured,
                "last_seen_at": v.last_seen_at,
            }
            for v in vehicles
        ]
    }


@router.post("/vehicles")
def upsert_vehicle(req: VehicleUpsertRequest, repo: Repository = Depends(get_repo)):
    repo.upsert_vehicle(
        vehicle_name=req.vehicle_name,
        ip=req.ip,
        mcp_endpoint=req.mcp_endpoint,
        status=req.status,
        is_configured=req.is_configured,
        auth_type=req.auth_type,
        auth_secret_ref=req.auth_secret_ref,
    )
    return {"ok": True}
