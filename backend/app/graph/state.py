from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    session_id: str
    user_input: str
    model: str | None
    apk_path: str | None

    system_prompt: str
    user_template: str
    tool_policy: str
    memory_context: str

    error_code: str | None
    error_message: str | None
    available_tools: list[dict[str, Any]]
    selected_tools: list[str] | None
    selected_tool: str | None
    tool_calls: list[dict[str, Any]] | None
    tool_router_assistant_message: dict[str, Any] | None
    tool_result: dict[str, Any] | list[dict[str, Any]] | None
    security_intent: bool | None
    llm_response_preview: str | None

    final_response: str
    events: list[dict[str, Any]]
