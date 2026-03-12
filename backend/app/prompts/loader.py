from pathlib import Path

from app.core.config import get_settings


class PromptLoader:
    def __init__(self) -> None:
        self.settings = get_settings()
        # backend/app/prompts/loader.py -> backend/
        self.backend_root = Path(__file__).resolve().parents[2]

    def _resolve(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path

        # 1) current working directory
        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return cwd_path

        # 2) backend root directory (stable across different startup cwd)
        backend_path = self.backend_root / path
        return backend_path

    # ---- generic loader ----
    def load_prompt(self, relative_path: str) -> str:
        """Load any prompt file by its path relative to the prompts/ directory."""
        return self._resolve(f"prompts/{relative_path}").read_text(encoding="utf-8").strip()

    # ---- existing loaders ----
    def load_system_prompt(self) -> str:
        return self._resolve(self.settings.default_system_prompt_file).read_text(encoding="utf-8")

    def load_user_template(self) -> str:
        return self._resolve(self.settings.default_user_prompt_file).read_text(encoding="utf-8")

    def load_tool_policy(self) -> str:
        return self._resolve(self.settings.default_tool_policy_file).read_text(encoding="utf-8")

    # ---- new prompt loaders ----
    def load_classify_intent_system(self) -> str:
        return self.load_prompt("classify_intent_system.md")

    def load_classify_intent_user(self) -> str:
        return self.load_prompt("classify_intent_user.md")

    def load_tool_router_system(self) -> str:
        return self.load_prompt("tool_router_system.md")

    def load_in_progress_retry(self) -> str:
        return self.load_prompt("in_progress_retry.md")

