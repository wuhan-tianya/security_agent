from __future__ import annotations

from app.memory.repository import Repository
from app.services.agent_service import AgentService
from app.skills.registry import SkillRegistry


def get_agent_service() -> AgentService:
    from app.main import app

    return app.state.agent_service


def get_repo() -> Repository:
    from app.main import app

    return app.state.repo


def get_registry() -> SkillRegistry:
    from app.main import app

    return app.state.agent_service.registry
