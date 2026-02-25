from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.schemas import ChatStreamRequest
from app.services.agent_service import AgentService


router = APIRouter(prefix="/v1", tags=["chat"])


def get_agent_service() -> AgentService:
    from app.main import app

    return app.state.agent_service


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest, service: AgentService = Depends(get_agent_service)):
    return StreamingResponse(
        service.stream_sse_events(
            session_id=req.session_id,
            user_input=req.user_input,
            model=req.model,
            target_vehicle_ip=req.target_vehicle_ip,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
