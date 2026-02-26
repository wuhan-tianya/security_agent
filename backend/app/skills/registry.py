from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable

from skills.scripts.base_tool import BaseTool


@dataclass
class SkillInfo:
    name: str
    description: str


class SkillRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        module = importlib.import_module("skills.scripts")
        for class_name in getattr(module, "__all__", []):
            cls = getattr(module, class_name, None)
            if cls is None:
                continue
            tool = cls()
            if not isinstance(tool, BaseTool):
                continue
            self._tools[tool.name] = tool

    def list_tools(self) -> list[SkillInfo]:
        return [SkillInfo(name=t.name, description=t.description) for t in self._tools.values()]

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def pick_tool(self, user_input: str) -> BaseTool | None:
        lowered = user_input.lower()
        for tool in self._tools.values():
            if tool.name.lower() in lowered:
                return tool
        return next(iter(self._tools.values()), None)
