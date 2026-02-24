from __future__ import annotations

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    model: str | None = None


class VehicleUpsertRequest(BaseModel):
    vehicle_name: str
    ip: str
    mcp_endpoint: str | None = None
    status: str = "offline"
    is_configured: bool = False
    auth_type: str = "none"
    auth_secret_ref: str | None = None
