from __future__ import annotations

from pathlib import Path

import pytest

from app.db.database import Database
from app.graph.nodes import (
    mcp_call_node,
    parse_target_vehicle_node,
    resolve_vehicle_node,
)
from app.memory.repository import Repository


class _FakeMCPClient:
    async def list_tools(self, endpoint: str):
        return [type("Tool", (), {"name": "apk_analyzer", "description": "", "input_schema": {}})()]

    async def call_tool(self, endpoint: str, tool_name: str, arguments: dict):
        return {"ok": True, "tool": tool_name, "arguments": arguments}


class _FakeManager:
    def client_for_endpoint(self, endpoint: str):
        return _FakeMCPClient()


@pytest.fixture()
def repo(tmp_path: Path) -> Repository:
    db_file = tmp_path / "test.db"
    db = Database(str(db_file))
    db.init_schema()
    return Repository(db)


@pytest.mark.asyncio
async def test_valid_ip_routes_to_vehicle_and_calls_mcp(repo: Repository):
    repo.upsert_vehicle("car-a", "10.1.1.2", "http://10.1.1.2:9000", status="online", is_configured=True)

    state = {
        "session_id": "s1",
        "user_input": "请连接 10.1.1.2 做安全检查",
        "events": [],
    }
    state = await parse_target_vehicle_node(state)
    state = await resolve_vehicle_node(state, repo)

    assert state["selected_vehicle_ip"] == "10.1.1.2"
    assert state.get("error_code") is None

    state = await mcp_call_node(state, _FakeManager())
    assert state["tool_result"]["ok"] is True


@pytest.mark.asyncio
async def test_no_ip_requires_vehicle_selection(repo: Repository):
    repo.upsert_vehicle("car-a", "10.1.1.2", "http://10.1.1.2:9000", status="online", is_configured=True)
    state = {"session_id": "s1", "user_input": "帮我做安全检查", "events": []}

    state = await parse_target_vehicle_node(state)
    state = await resolve_vehicle_node(state, repo)

    assert state["error_code"] == "VEHICLE_NOT_SELECTED"


@pytest.mark.asyncio
async def test_unregistered_ip_requires_selection(repo: Repository):
    state = {"session_id": "s1", "user_input": "检查 10.8.8.8", "events": []}

    state = await parse_target_vehicle_node(state)
    state = await resolve_vehicle_node(state, repo)

    assert state["error_code"] == "VEHICLE_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_unconfigured_vehicle_requires_setup(repo: Repository):
    repo.upsert_vehicle("car-b", "10.2.2.3", None, status="online", is_configured=False)
    state = {"session_id": "s1", "user_input": "连接 10.2.2.3", "events": []}

    state = await parse_target_vehicle_node(state)
    state = await resolve_vehicle_node(state, repo)

    assert state["error_code"] == "VEHICLE_NOT_CONFIGURED"


def test_session_memory_isolated(repo: Repository):
    repo.append_message("s1", "user", "a")
    repo.append_message("s2", "user", "b")

    m1 = repo.get_recent_messages("s1")
    m2 = repo.get_recent_messages("s2")

    assert len(m1) == 1 and m1[0]["content"] == "a"
    assert len(m2) == 1 and m2[0]["content"] == "b"
