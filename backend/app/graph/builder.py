from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    classify_security_intent,
    load_prompt_node,
    memory_read_node,
    memory_write_node,
    reflect_node,
    skill_call_node,
)
from app.graph.state import AgentState
from app.llm.openai_compatible import OpenAICompatibleClient
from app.skills.registry import SkillRegistry
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader


def build_graph(repo: Repository, prompt_loader: PromptLoader, registry: SkillRegistry, llm_client: OpenAICompatibleClient):
    graph = StateGraph(AgentState)

    async def _load_prompt(state):
        return await load_prompt_node(state, prompt_loader)

    async def _memory_read(state):
        return await memory_read_node(state, repo)

    async def _skill_call(state):
        return await skill_call_node(state, registry)

    async def _classify_intent(state):
        return await classify_security_intent(state, llm_client)

    async def _reflect(state):
        return await reflect_node(state, llm_client)

    async def _memory_write(state):
        return await memory_write_node(state, repo)

    graph.add_node("load_prompt", _load_prompt)
    graph.add_node("memory_read", _memory_read)
    graph.add_node("classify_intent", _classify_intent)
    graph.add_node("skill_call", _skill_call)
    graph.add_node("reflect", _reflect)
    graph.add_node("memory_write", _memory_write)

    graph.set_entry_point("load_prompt")
    graph.add_edge("load_prompt", "memory_read")
    graph.add_edge("memory_read", "classify_intent")

    graph.add_edge("classify_intent", "skill_call")
    graph.add_edge("skill_call", "reflect")
    graph.add_edge("reflect", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile()
