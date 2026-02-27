from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_agent_service
from app.api.v1.schemas import ChatStreamRequest
from app.services.agent_service import AgentService


router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest, service: AgentService = Depends(get_agent_service)):
    return StreamingResponse(
        service.stream_sse_events(
            session_id=req.session_id,
            user_input=req.user_input,
            model=req.model,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
