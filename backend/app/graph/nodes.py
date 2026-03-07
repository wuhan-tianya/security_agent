from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from app.graph.events import append_event
from app.graph.state import AgentState
from app.core.config import get_settings
from app.llm.openai_compatible import OpenAICompatibleClient
from app.skills.registry import SkillRegistry
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader
from app.prompts.renderer import render_user_prompt


def _fallback_summary_from_tool(
    tool_name: str | None,
    tool_result: dict[str, Any] | list[dict[str, Any]] | None,
) -> str:
    if not tool_result:
        return "工具调用已完成，但没有返回可用结果。"

    if isinstance(tool_result, list):
        snippets = []
        for item in tool_result[:5]:
            tname = item.get("tool") if isinstance(item, dict) else None
            result = item.get("result") if isinstance(item, dict) else None
            snippets.append(_fallback_summary_from_tool(tname, result))
        return "\n\n".join(snippets)

    success = bool(tool_result.get("success"))
    data = tool_result.get("data", {})
    error = tool_result.get("error") or ""
    title = f"工具 `{tool_name or 'unknown'}` 执行结果："

    if not success:
        return f"{title}\n- 状态：失败\n- 错误：{error or 'unknown'}"

    lines = [title, "- 状态：成功"]
    if isinstance(data, dict):
        if "risk_level" in data:
            lines.append(f"- 风险等级：{data.get('risk_level')}")
        if "reachable" in data:
            lines.append(f"- 可达性：{data.get('reachable')}")
        if "latency_ms" in data:
            lines.append(f"- 延迟：{data.get('latency_ms')} ms")
        if "findings" in data and isinstance(data.get("findings"), list):
            findings = data.get("findings") or []
            if findings:
                lines.append("- 关键发现：")
                for item in findings[:5]:
                    lines.append(f"  - {item}")
        if "summary" in data and data.get("summary"):
            lines.append(f"- 摘要：{data.get('summary')}")
        if "note" in data and data.get("note"):
            lines.append(f"- 备注：{data.get('note')}")

    if len(lines) == 2:
        lines.append(f"- 原始结果：{str(tool_result)[:300]}")
    return "\n".join(lines)


async def classify_security_intent(state: AgentState, llm_client: OpenAICompatibleClient) -> AgentState:
    # Allow tests or callers to pre-fill the decision.
    if state.get("security_intent") is not None:
        return state

    text = state.get("user_input", "")
    prompt = (
        "You are a binary classifier. Determine if the user's intent is related to security testing "
        "(e.g., security scan, vulnerability analysis, permission/cert checks). "
        "Reply with only YES or NO.\n\n"
        f"User: {text}"
    )
    messages = [
        {"role": "system", "content": "Answer with only YES or NO."},
        {"role": "user", "content": prompt},
    ]
    try:
        resp = await llm_client.chat_completion(messages, model=state.get("model"))
        normalized = resp.strip().upper()
        state["security_intent"] = normalized.startswith("YES")
        append_event(state, "reasoning_trace", {"decision": "intent_classified", "security_intent": state["security_intent"]})
    except Exception as exc:
        state["security_intent"] = False
        append_event(state, "reasoning_trace", {"decision": "intent_classify_failed", "error": str(exc)[:300]})
    return state


async def load_prompt_node(state: AgentState, prompt_loader: PromptLoader) -> AgentState:
    state["system_prompt"] = prompt_loader.load_system_prompt()
    state["user_template"] = prompt_loader.load_user_template()
    state["tool_policy"] = prompt_loader.load_tool_policy()
    append_event(state, "prompt_loaded", {"ok": True})
    return state


async def memory_read_node(state: AgentState, repo: Repository) -> AgentState:
    session_id = state["session_id"]
    settings = get_settings()
    repo.ensure_session(session_id)
    recent = repo.get_recent_messages(session_id, limit=settings.memory_context_message_limit)
    summary = repo.get_latest_summary(session_id) or ""
    memory_context = "\n".join([f"{m['role']}: {_sanitize_history_content(m['content'])}" for m in recent])
    if summary:
        memory_context = f"summary: {summary}\n{memory_context}".strip()
    state["memory_context"] = memory_context
    append_event(state, "memory_read", {"message_count": len(recent), "has_summary": bool(summary)})
    return state


def _sanitize_history_content(content: str) -> str:
    text = content or ""
    # Prevent old tool markup from being interpreted as fresh tool calls.
    text = re.sub(r"<function_calls>.*?</function_calls>", "[history tool calls omitted]", text, flags=re.S | re.I)
    return text


async def skill_call_node(
    state: AgentState,
    registry: SkillRegistry,
    llm_client: OpenAICompatibleClient,
) -> AgentState:
    if not state.get("security_intent"):
        state["available_tools"] = []
        append_event(state, "reasoning_trace", {"decision": "skip_skill_non_security_intent"})
        return state

    query = state["user_input"]
    try:
        tools = registry.list_tools()
        state["available_tools"] = [{"name": t.name, "description": t.description} for t in tools]
        append_event(state, "skills_discovered", {"count": len(tools), "tools": [t.name for t in tools]})

        if not tools:
            state["error_code"] = "SKILL_UNAVAILABLE"
            state["error_message"] = "未发现可用本地工具"
            append_event(state, "skill_call_failed", {"error_code": "SKILL_UNAVAILABLE", "message": "no local skills"})
            append_event(state, "mcp_call_failed", {"error_code": "SKILL_UNAVAILABLE", "message": "no local skills"})
            return state

        # Use the model to decide which tools to call.
        tool_defs: list[dict[str, Any]] = []
        for t in tools:
            tool_defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "User request or query to analyze.",
                                }
                            },
                            "required": ["query"],
                        },
                    },
                }
            )

        route_messages = [
            {"role": "system", "content": "You are a tool router. Select tools to call based on the user request."},
            {"role": "user", "content": f"{query}\n\n[APK 文件已上传: {state.get('apk_path')}]" if state.get("apk_path") else query},
        ]
        route_resp = await llm_client.chat_completion_with_tools(
            route_messages,
            tools=tool_defs,
            tool_choice="auto",
            model=state.get("model"),
        )
        raw_tool_calls = route_resp.get("tool_calls") or []

        if not raw_tool_calls:
            append_event(state, "reasoning_trace", {"decision": "no_tool_selected"})
            return state

        tool_calls: list[dict[str, Any]] = []
        for idx, call in enumerate(raw_tool_calls):
            call_id = call.get("id") or f"call_{idx}"
            fn = call.get("function") or {}
            tool_calls.append(
                {
                    "id": call_id,
                    "type": call.get("type") or "function",
                    "function": {
                        "name": fn.get("name") or call.get("name"),
                        "arguments": fn.get("arguments") or "{}",
                    },
                }
            )

        state["tool_router_assistant_message"] = {
            "role": "assistant",
            "content": route_resp.get("content") or "",
            "tool_calls": tool_calls,
            "reasoning_content": route_resp.get("reasoning_content") or "",
        }

        results: list[dict[str, Any]] = []
        selected_tools: list[str] = []
        for call in tool_calls:
            if call.get("type") and call.get("type") != "function":
                continue
            fn = (call.get("function") or {})
            tool_name = fn.get("name") or call.get("name")
            if not tool_name:
                continue
            tool = registry.get_tool(tool_name)
            if not tool:
                continue

            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except Exception:
                logger.bind(session_id=state.get("session_id")).warning(
                    "tool_args_parse_failed tool={} args_raw={}",
                    tool_name,
                    str(args_raw)[:300],
                )
                args = {}
            if "query" not in args:
                args["query"] = query

            # 如果 state 中有 apk_path，自动注入到工具参数（仅当工具接受此参数时）
            apk_path = state.get("apk_path")
            if apk_path and "apk_path" not in args:
                import inspect as _inspect
                sig = _inspect.signature(tool.execute)
                if "apk_path" in sig.parameters or any(
                    p.kind == _inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                ):
                    args["apk_path"] = apk_path

            selected_tools.append(tool_name)
            append_event(state, "skill_call_started", {"tool": tool_name, "arguments": args})
            append_event(state, "mcp_call_started", {"tool": tool_name, "arguments": args})

            result = tool.execute(**args)
            append_event(state, "skill_call_finished", {"tool": tool_name, "result": result})
            append_event(state, "mcp_call_finished", {"tool": tool_name, "result": result})
            results.append({"tool": tool_name, "tool_call_id": call.get("id"), "result": result})

        state["selected_tools"] = selected_tools
        state["selected_tool"] = selected_tools[0] if selected_tools else None
        state["tool_calls"] = tool_calls
        state["tool_result"] = results
    except Exception as exc:
        logger.bind(session_id=state.get("session_id")).exception("skill_call_failed: {}", str(exc))
        state["error_code"] = "SKILL_CALL_FAILED"
        state["error_message"] = str(exc)
        append_event(state, "skill_call_failed", {"error_code": "SKILL_CALL_FAILED", "message": str(exc)})
        append_event(state, "mcp_call_failed", {"error_code": "SKILL_CALL_FAILED", "message": str(exc)})
    return state


def build_reflect_messages(state: AgentState) -> list[dict[str, Any]]:
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
        assistant_msg = dict(state.get("tool_router_assistant_message") or {})
        assistant_msg["role"] = "assistant"
        assistant_msg["tool_calls"] = tool_calls
        if "content" not in assistant_msg:
            assistant_msg["content"] = ""
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
        try:
            tool_result_text = json.dumps(tool_result, ensure_ascii=False)
        except Exception:
            tool_result_text = str(tool_result)
        messages[-1]["content"] = f"{user_prompt}\n\n工具结果:\n{tool_result_text}\n\n请给出简洁的安全分析结论。"

    return messages


async def reflect_node(state: AgentState, llm_client: OpenAICompatibleClient) -> AgentState:
    if state.get("error_code"):
        state["final_response"] = f"工具调用失败（{state['error_code']}）：{state.get('error_message', 'unknown error')}"
        append_event(state, "reasoning_trace", {"decision": "fast_fail_on_skill_error"})
        return state

    messages = build_reflect_messages(state)
    try:
        logger.bind(session_id=state.get("session_id")).info("llm_messages={}", messages)
    except Exception:
        pass

    try:
        final = await llm_client.chat_completion(messages, model=state.get("model"))
        state["llm_response_preview"] = final[:500]
        append_event(state, "llm_response", {"preview": final[:500]})
    except Exception as exc:
        final = _fallback_summary_from_tool(state.get("selected_tool"), state.get("tool_result"))
        append_event(state, "reasoning_trace", {"decision": "llm_summary_failed_fallback", "error": str(exc)[:300]})

    state["final_response"] = final
    append_event(state, "reasoning_trace", {"decision": "skill_result_reflected", "tool": state.get("selected_tool")})
    return state


async def memory_write_node(state: AgentState, repo: Repository) -> AgentState:
    session_id = state["session_id"]
    repo.append_message(session_id, "user", state["user_input"])
    repo.append_message(
        session_id,
        "assistant",
        state.get("final_response", ""),
        {
            "selected_tool": state.get("selected_tool"),
            "selected_tools": state.get("selected_tools"),
            "error_code": state.get("error_code"),
        },
    )

    summary = (state.get("final_response") or "")[:300]
    repo.upsert_summary(session_id, summary)
    append_event(state, "memory_write", {"session_id": session_id})
    return state
