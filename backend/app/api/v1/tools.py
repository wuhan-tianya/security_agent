from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_registry
from app.skills.registry import SkillRegistry


router = APIRouter(tags=["tools"])


@router.get("/tools")
async def list_tools(registry: SkillRegistry = Depends(get_registry)):
    tools = registry.list_tools()
    return {"tools": [{"name": t.name, "description": t.description} for t in tools]}
