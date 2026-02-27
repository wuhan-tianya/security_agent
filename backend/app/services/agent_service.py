from __future__ import annotations

import json
from typing import Any, AsyncIterator

from loguru import logger

from app.graph.events import append_event
from app.graph.nodes import _fallback_summary_from_tool
from app.graph.nodes import classify_security_intent, load_prompt_node, memory_read_node, memory_write_node, skill_call_node
from app.prompts.renderer import render_user_prompt
from app.graph.builder import build_graph
from app.llm.openai_compatible import OpenAICompatibleClient
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader
from app.skills.registry import SkillRegistry
from app.core.config import get_settings


class AgentService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.prompt_loader = PromptLoader()
        self.registry = SkillRegistry()
        self.llm_client = OpenAICompatibleClient()
        self.graph = build_graph(repo, self.prompt_loader, self.registry, self.llm_client)

    async def run(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        initial_state: dict[str, Any] = {
            "session_id": session_id,
            "user_input": user_input,
            "model": model,
            "events": [],
        }
        result = await self.graph.ainvoke(initial_state)
        return result

    async def stream_sse_events(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        yield self._format_sse("run_started", {"session_id": session_id})
        state: dict[str, Any] = {
            "session_id": session_id,
            "user_input": user_input,
            "model": model,
            "events": [],
        }

        emitted = 0
        async def _emit_new_events():
            nonlocal emitted
            for evt in state.get("events", [])[emitted:]:
                yield self._format_sse(evt["event"], evt["data"])
            emitted = len(state.get("events", []))

        state = await load_prompt_node(state, self.prompt_loader)
        async for msg in _emit_new_events():
            yield msg

        state = await memory_read_node(state, self.repo)
        async for msg in _emit_new_events():
            yield msg

        state = await classify_security_intent(state, self.llm_client)
        async for msg in _emit_new_events():
            yield msg

        state = await skill_call_node(state, self.registry, self.llm_client)
        async for msg in _emit_new_events():
            yield msg

        if state.get("error_code"):
            final_response = f"工具调用失败（{state['error_code']}）：{state.get('error_message', 'unknown error')}"
            append_event(state, "reasoning_trace", {"decision": "fast_fail_on_skill_error"})
        else:
            system_prompt = state["system_prompt"]
            user_prompt = render_user_prompt(state["user_template"], state["user_input"], state.get("memory_context", ""))
            tool_policy = state["tool_policy"]
            tool_result = state.get("tool_result")
            tool_calls = state.get("tool_calls") or []

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt + "\n" + tool_policy},
                {"role": "user", "content": user_prompt},
            ]

            if tool_calls and isinstance(tool_result, list):
                assistant_msg: dict[str, Any] = {"role": "assistant", "content": "", "tool_calls": tool_calls}
                settings = get_settings()
                base_url = (settings.llm_base_url or "").lower()
                model_name = (state.get("model") or settings.llm_model or "").lower()
                if "kimi.com" in base_url or model_name.startswith("kimi"):
                    assistant_msg["reasoning_content"] = ""
                messages.append(assistant_msg)
                for item in tool_result:
                    tool_call_id = item.get("tool_call_id") or ""
                    result_payload = item.get("result")
                    try:
                        tool_content = json.dumps(result_payload, ensure_ascii=False)
                    except Exception:
                        tool_content = str(result_payload)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_content,
                        }
                    )
            elif tool_result is not None:
                tool_result_text = ""
                try:
                    tool_result_text = json.dumps(tool_result, ensure_ascii=False)
                except Exception:
                    tool_result_text = str(tool_result)
                messages[-1]["content"] = f"{user_prompt}\n\n工具结果:\n{tool_result_text}\n\n请给出简洁的安全分析结论。"

            try:
                logger.bind(session_id=state.get("session_id")).info("llm_messages={}", messages)
            except Exception:
                pass

            chunks: list[str] = []
            try:
                async for token in self.llm_client.stream_chat_completion(messages, model=state.get("model")):
                    if token:
                        chunks.append(token)
                        yield self._format_sse("llm_token", {"token": token})
                if chunks:
                    final_response = "".join(chunks)
                else:
                    # Fallback: provider might not support SSE streaming despite stream=true.
                    final_response = await self.llm_client.chat_completion(messages, model=state.get("model"))
                    if final_response:
                        yield self._format_sse("llm_token", {"token": final_response})
            except Exception as exc:
                logger.bind(session_id=state.get("session_id")).exception("llm_stream_failed_fallback: {}", str(exc))
                append_event(
                    state,
                    "reasoning_trace",
                    {"decision": "llm_stream_failed_retry_non_stream", "error": str(exc)[:300]},
                )
                try:
                    final_response = await self.llm_client.chat_completion(messages, model=state.get("model"))
                    if final_response:
                        yield self._format_sse("llm_token", {"token": final_response})
                except Exception as exc2:
                    logger.bind(session_id=state.get("session_id")).exception(
                        "llm_non_stream_failed_fallback: {}", str(exc2)
                    )
                    final_response = _fallback_summary_from_tool(state.get("selected_tool"), state.get("tool_result"))
                    append_event(
                        state,
                        "reasoning_trace",
                        {"decision": "llm_non_stream_failed_fallback", "error": str(exc2)[:300]},
                    )

        state["final_response"] = final_response
        append_event(state, "llm_response", {"preview": final_response[:500]})
        async for msg in _emit_new_events():
            yield msg

        state = await memory_write_node(state, self.repo)
        async for msg in _emit_new_events():
            yield msg

        if state.get("error_code"):
            yield self._format_sse(
                "run_error",
                {"error_code": state.get("error_code"), "message": state.get("error_message")},
            )

        yield self._format_sse("run_finished", {"final_response": final_response})

    @staticmethod
    def _format_sse(event: str, payload: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
