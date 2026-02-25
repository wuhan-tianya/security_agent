from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.graph.builder import build_graph
from app.llm.openai_compatible import OpenAICompatibleClient
from app.mcp.client import MCPClientManager
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader


class AgentService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.prompt_loader = PromptLoader()
        self.mcp_manager = MCPClientManager()
        self.llm_client = OpenAICompatibleClient()
        self.graph = build_graph(repo, self.prompt_loader, self.mcp_manager, self.llm_client)

    async def run(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
        target_vehicle_ip: str | None = None,
    ) -> dict[str, Any]:
        initial_state: dict[str, Any] = {
            "session_id": session_id,
            "user_input": user_input,
            "model": model,
            "selected_vehicle_ip": target_vehicle_ip,
            "events": [],
        }
        result = await self.graph.ainvoke(initial_state)
        return result

    async def stream_sse_events(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
        target_vehicle_ip: str | None = None,
    ) -> AsyncIterator[str]:
        yield self._format_sse("run_started", {"session_id": session_id})
        result = await self.run(session_id, user_input, model, target_vehicle_ip)

        for evt in result.get("events", []):
            yield self._format_sse(evt["event"], evt["data"])

        final_response = result.get("final_response", "")
        for token in final_response.split():
            yield self._format_sse("llm_token", {"token": token})

        if result.get("error_code"):
            yield self._format_sse(
                "run_error",
                {"error_code": result.get("error_code"), "message": result.get("error_message")},
            )

        yield self._format_sse("run_finished", {"final_response": final_response})

    @staticmethod
    def _format_sse(event: str, payload: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
