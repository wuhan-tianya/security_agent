from __future__ import annotations

import pytest

from app.graph.nodes import skill_call_node


class _FakeTool:
    name = "apk_analyzer"
    description = ""

    def execute(self, **kwargs):
        return {"ok": True, "arguments": kwargs}


class _FakeRegistry:
    def list_tools(self):
        return [type("Info", (), {"name": "apk_analyzer", "description": ""})()]

    def pick_tool(self, user_input: str):
        return _FakeTool()


@pytest.mark.asyncio
async def test_skill_call_runs_when_security_intent_true():
    state = {
        "session_id": "s1",
        "user_input": "做一次安全扫描",
        "security_intent": True,
        "events": [],
    }
    state = await skill_call_node(state, _FakeRegistry())
    assert state["tool_result"]["ok"] is True


@pytest.mark.asyncio
async def test_skip_skill_for_non_security_intent():
    state = {
        "session_id": "s1",
        "user_input": "今天天气怎么样",
        "security_intent": False,
        "events": [],
    }
    state = await skill_call_node(state, _FakeRegistry())
    assert state.get("selected_tool") is None
    assert state.get("tool_result") is None
