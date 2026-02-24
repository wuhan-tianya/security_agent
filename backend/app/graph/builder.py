from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    ask_vehicle_config_node,
    ask_vehicle_selection_node,
    decide_vehicle_branch,
    load_prompt_node,
    mcp_call_node,
    memory_read_node,
    memory_write_node,
    parse_target_vehicle_node,
    reflect_node,
    resolve_vehicle_node,
)
from app.graph.state import AgentState
from app.llm.openai_compatible import OpenAICompatibleClient
from app.mcp.client import MCPClientManager
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader


def build_graph(repo: Repository, prompt_loader: PromptLoader, mcp_manager: MCPClientManager, llm_client: OpenAICompatibleClient):
    graph = StateGraph(AgentState)

    async def _load_prompt(state):
        return await load_prompt_node(state, prompt_loader)

    async def _memory_read(state):
        return await memory_read_node(state, repo)

    async def _resolve_vehicle(state):
        return await resolve_vehicle_node(state, repo)

    async def _mcp_call(state):
        return await mcp_call_node(state, mcp_manager)

    async def _reflect(state):
        return await reflect_node(state, llm_client)

    async def _memory_write(state):
        return await memory_write_node(state, repo)

    graph.add_node("load_prompt", _load_prompt)
    graph.add_node("memory_read", _memory_read)
    graph.add_node("parse_target_vehicle", parse_target_vehicle_node)
    graph.add_node("resolve_vehicle", _resolve_vehicle)
    graph.add_node("ask_vehicle_selection", ask_vehicle_selection_node)
    graph.add_node("ask_vehicle_config", ask_vehicle_config_node)
    graph.add_node("mcp_call", _mcp_call)
    graph.add_node("reflect", _reflect)
    graph.add_node("memory_write", _memory_write)

    graph.set_entry_point("load_prompt")
    graph.add_edge("load_prompt", "memory_read")
    graph.add_edge("memory_read", "parse_target_vehicle")
    graph.add_edge("parse_target_vehicle", "resolve_vehicle")

    graph.add_conditional_edges(
        "resolve_vehicle",
        decide_vehicle_branch,
        {
            "vehicle_ready": "mcp_call",
            "vehicle_missing": "ask_vehicle_selection",
            "vehicle_unconfigured": "ask_vehicle_config",
        },
    )

    graph.add_edge("mcp_call", "reflect")
    graph.add_edge("ask_vehicle_selection", "reflect")
    graph.add_edge("ask_vehicle_config", "reflect")
    graph.add_edge("reflect", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile()
