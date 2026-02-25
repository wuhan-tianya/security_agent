from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    user_input: str
    model: str | None

    system_prompt: str
    user_template: str
    tool_policy: str
    memory_context: str

    parsed_vehicle_ip: str | None
    selected_vehicle_ip: str | None
    selected_vehicle_name: str | None
    selected_vehicle_endpoint: str | None

    error_code: str | None
    error_message: str | None

    available_vehicles: list[dict[str, Any]]
    available_tools: list[dict[str, Any]]
    selected_tool: str | None
    tool_result: dict[str, Any] | None
    security_intent: bool | None
    llm_response_preview: str | None

    final_response: str
    events: list[dict[str, Any]]
