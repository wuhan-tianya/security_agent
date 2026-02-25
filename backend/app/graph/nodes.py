from __future__ import annotations

import re
from typing import Any

from app.graph.events import append_event
from app.graph.state import AgentState
from app.llm.openai_compatible import OpenAICompatibleClient
from app.mcp.client import MCPClientManager, MCPError
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader
from app.prompts.renderer import render_user_prompt


_IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _valid_ipv4(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        n = int(p)
        if n < 0 or n > 255:
            return False
    return True


def _fallback_summary_from_tool(tool_name: str | None, tool_result: dict[str, Any] | None) -> str:
    if not tool_result:
        return "工具调用已完成，但没有返回可用结果。"

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


async def load_prompt_node(state: AgentState, prompt_loader: PromptLoader) -> AgentState:
    state["system_prompt"] = prompt_loader.load_system_prompt()
    state["user_template"] = prompt_loader.load_user_template()
    state["tool_policy"] = prompt_loader.load_tool_policy()
    append_event(state, "prompt_loaded", {"ok": True})
    return state


async def memory_read_node(state: AgentState, repo: Repository) -> AgentState:
    session_id = state["session_id"]
    repo.ensure_session(session_id)
    recent = repo.get_recent_messages(session_id, limit=8)
    summary = repo.get_latest_summary(session_id) or ""
    memory_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])
    if summary:
        memory_context = f"summary: {summary}\n{memory_context}".strip()
    state["memory_context"] = memory_context
    append_event(state, "memory_read", {"message_count": len(recent), "has_summary": bool(summary)})
    return state


async def parse_target_vehicle_node(state: AgentState) -> AgentState:
    text = state["user_input"]
    parsed_ip = None
    for match in _IP_PATTERN.findall(text):
        if _valid_ipv4(match):
            parsed_ip = match
            break
    state["parsed_vehicle_ip"] = parsed_ip
    append_event(state, "vehicle_ip_parsed", {"ip": parsed_ip})
    return state


async def resolve_vehicle_node(state: AgentState, repo: Repository) -> AgentState:
    parsed_ip = state.get("parsed_vehicle_ip")
    vehicles = repo.list_vehicles()
    state["available_vehicles"] = [
        {
            "vehicle_name": v.vehicle_name,
            "ip": v.ip,
            "status": v.status,
            "is_configured": v.is_configured,
        }
        for v in vehicles
    ]

    if not parsed_ip:
        state["error_code"] = "VEHICLE_NOT_SELECTED"
        state["error_message"] = "未检测到车机 IP"
        append_event(state, "vehicle_selection_required", {"reason": "ip_missing", "vehicles": state["available_vehicles"]})
        return state

    vehicle = repo.get_vehicle_by_ip(parsed_ip)
    if not vehicle:
        state["error_code"] = "VEHICLE_NOT_REGISTERED"
        state["error_message"] = f"车机 IP 未注册: {parsed_ip}"
        append_event(state, "vehicle_selection_required", {"reason": "ip_not_registered", "ip": parsed_ip, "vehicles": state["available_vehicles"]})
        return state

    if not vehicle.is_configured or not vehicle.mcp_endpoint:
        state["error_code"] = "VEHICLE_NOT_CONFIGURED"
        state["error_message"] = f"车机未完成 MCP 配置: {parsed_ip}"
        state["selected_vehicle_ip"] = vehicle.ip
        state["selected_vehicle_name"] = vehicle.vehicle_name
        append_event(
            state,
            "vehicle_unconfigured",
            {
                "vehicle_name": vehicle.vehicle_name,
                "ip": vehicle.ip,
                "required": ["mcp_endpoint", "auth", "connectivity"],
            },
        )
        return state

    state["selected_vehicle_ip"] = vehicle.ip
    state["selected_vehicle_name"] = vehicle.vehicle_name
    state["selected_vehicle_endpoint"] = vehicle.mcp_endpoint
    state["error_code"] = None
    state["error_message"] = None
    append_event(
        state,
        "vehicle_connected",
        {"vehicle_name": vehicle.vehicle_name, "ip": vehicle.ip, "endpoint": vehicle.mcp_endpoint},
    )
    return state


def decide_vehicle_branch(state: AgentState) -> str:
    if state.get("error_code") == "VEHICLE_NOT_SELECTED":
        return "vehicle_missing"
    if state.get("error_code") == "VEHICLE_NOT_REGISTERED":
        return "vehicle_missing"
    if state.get("error_code") == "VEHICLE_NOT_CONFIGURED":
        return "vehicle_unconfigured"
    return "vehicle_ready"


async def ask_vehicle_selection_node(state: AgentState) -> AgentState:
    vehicles = state.get("available_vehicles") or []
    lines = ["请先选择要连接的车机 IP。"]
    if state.get("error_code") == "VEHICLE_NOT_REGISTERED":
        lines.append(state.get("error_message", "指定 IP 未注册。"))
    if vehicles:
        lines.append("可选车机：")
        for v in vehicles:
            lines.append(f"- {v['vehicle_name']} ({v['ip']}) 状态={v['status']} 已配置={v['is_configured']}")
    else:
        lines.append("当前没有可用车机，请先在平台注册车机并完成 MCP 配置。")

    lines.append("请选择要连接的车机 IP/名称。")
    state["final_response"] = "\n".join(lines)
    return state


async def ask_vehicle_config_node(state: AgentState) -> AgentState:
    ip = state.get("selected_vehicle_ip", "unknown")
    name = state.get("selected_vehicle_name", "unknown")
    state["final_response"] = (
        f"车机 {name} ({ip}) 尚未完成 MCP 配置。请先完成：\n"
        "1. 配置 mcp_endpoint\n"
        "2. 配置认证参数\n"
        "3. 确认网络连通性\n"
        "配置完成后请重新发起请求。"
    )
    return state


async def mcp_call_node(state: AgentState, mcp_manager: MCPClientManager) -> AgentState:
    endpoint = state["selected_vehicle_endpoint"]
    client = mcp_manager.client_for_endpoint(endpoint)
    query = state["user_input"]
    try:
        tools = await client.list_tools(endpoint)
        state["available_tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]
        append_event(state, "mcp_tools_discovered", {"count": len(tools), "tools": [t.name for t in tools]})

        if not tools:
            raise MCPError("MCP_UNAVAILABLE", "目标车机没有可用 MCP 工具")

        selected_tool = None
        lowered = query.lower()
        for t in tools:
            if t.name.lower() in lowered:
                selected_tool = t
                break
        if not selected_tool:
            selected_tool = tools[0]

        state["selected_tool"] = selected_tool.name
        append_event(
            state,
            "mcp_call_started",
            {
                "ip": state.get("selected_vehicle_ip"),
                "tool": selected_tool.name,
                "endpoint": endpoint,
            },
        )

        result = await client.call_tool(endpoint, selected_tool.name, {"query": query})
        state["tool_result"] = result
        append_event(state, "mcp_call_finished", {"tool": selected_tool.name, "result_preview": str(result)[:400]})
    except MCPError as exc:
        state["error_code"] = exc.code
        state["error_message"] = exc.message
        append_event(state, "vehicle_connect_failed", {"ip": state.get("selected_vehicle_ip"), "error_code": exc.code, "message": exc.message})
        append_event(state, "mcp_call_failed", {"error_code": exc.code, "message": exc.message})
    return state


async def reflect_node(state: AgentState, llm_client: OpenAICompatibleClient) -> AgentState:
    if state.get("final_response"):
        append_event(state, "reasoning_trace", {"decision": "need_user_vehicle_selection_or_configuration"})
        return state

    if state.get("error_code"):
        state["final_response"] = f"工具调用失败（{state['error_code']}）：{state.get('error_message', 'unknown error')}"
        append_event(state, "reasoning_trace", {"decision": "fast_fail_on_mcp_error"})
        return state

    system_prompt = state["system_prompt"]
    user_prompt = render_user_prompt(state["user_template"], state["user_input"], state.get("memory_context", ""))
    tool_policy = state["tool_policy"]

    tool_result_text = str(state.get("tool_result", {}))
    messages = [
        {"role": "system", "content": system_prompt + "\n" + tool_policy},
        {
            "role": "user",
            "content": f"{user_prompt}\n\n工具结果:\n{tool_result_text}\n\n请给出简洁的安全分析结论。",
        },
    ]

    try:
        final = await llm_client.chat_completion(messages, model=state.get("model"))
    except Exception as exc:
        final = _fallback_summary_from_tool(state.get("selected_tool"), state.get("tool_result"))
        append_event(state, "reasoning_trace", {"decision": "llm_summary_failed_fallback", "error": str(exc)[:300]})

    state["final_response"] = final
    append_event(state, "reasoning_trace", {"decision": "mcp_result_reflected", "tool": state.get("selected_tool")})
    return state


async def memory_write_node(state: AgentState, repo: Repository) -> AgentState:
    session_id = state["session_id"]
    repo.append_message(session_id, "user", state["user_input"])
    repo.append_message(
        session_id,
        "assistant",
        state.get("final_response", ""),
        {
            "selected_vehicle_ip": state.get("selected_vehicle_ip"),
            "selected_tool": state.get("selected_tool"),
            "error_code": state.get("error_code"),
        },
    )
    if state.get("selected_vehicle_ip"):
        repo.set_last_vehicle_ip(session_id, state.get("selected_vehicle_ip"))

    summary = (state.get("final_response") or "")[:300]
    repo.upsert_summary(session_id, summary)
    append_event(state, "memory_write", {"session_id": session_id})
    return state
