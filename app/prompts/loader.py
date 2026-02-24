from pathlib import Path

from app.core.config import get_settings


class PromptLoader:
    def __init__(self) -> None:
        self.settings = get_settings()

    def load_system_prompt(self) -> str:
        return Path(self.settings.default_system_prompt_file).read_text(encoding="utf-8")

    def load_user_template(self) -> str:
        return Path(self.settings.default_user_prompt_file).read_text(encoding="utf-8")

    def load_tool_policy(self) -> str:
        return Path(self.settings.default_tool_policy_file).read_text(encoding="utf-8")
