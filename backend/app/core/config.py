from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Settings(BaseModel):
    app_name: str = "Vehicle Security Agent"
    db_path: str = "./data/security_agent.db"
    config_file: str = "config/settings.json"

    llm_base_url: str = "http://localhost:8001/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 30


    default_system_prompt_file: str = "prompts/system.md"
    default_user_prompt_file: str = "prompts/user_template.md"
    default_tool_policy_file: str = "prompts/policies/tool_call_policy.md"

    @classmethod
    def load(cls) -> "Settings":
        defaults = cls()
        data: dict[str, Any] = defaults.model_dump()

        config_file = os.getenv("CONFIG_FILE", data["config_file"])
        data["config_file"] = config_file
        file_data = cls._load_json_file(config_file)
        if file_data:
            data.update(file_data)

        env_mapping = {
            "APP_NAME": "app_name",
            "DB_PATH": "db_path",
            "LLM_BASE_URL": "llm_base_url",
            "LLM_API_KEY": "llm_api_key",
            "LLM_MODEL": "llm_model",
            "LLM_TIMEOUT_SECONDS": "llm_timeout_seconds",
            "DEFAULT_SYSTEM_PROMPT_FILE": "default_system_prompt_file",
            "DEFAULT_USER_PROMPT_FILE": "default_user_prompt_file",
            "DEFAULT_TOOL_POLICY_FILE": "default_tool_policy_file",
        }
        for env_name, field_name in env_mapping.items():
            value = os.getenv(env_name)
            if value is not None:
                data[field_name] = value

        return cls(**data)

    @staticmethod
    def _load_json_file(config_file: str) -> dict[str, Any]:
        path = Path(config_file)
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError(f"Config file must be a JSON object: {config_file}")
        return payload


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()
