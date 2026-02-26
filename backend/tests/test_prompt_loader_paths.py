from __future__ import annotations

from pathlib import Path

from app.prompts.loader import PromptLoader


def test_prompt_loader_resolves_from_backend_root(monkeypatch):
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)

    loader = PromptLoader()

    assert "安全智能体" in loader.load_system_prompt()
    assert "{{user_input}}" in loader.load_user_template()
    assert "工具调用策略" in loader.load_tool_policy()
