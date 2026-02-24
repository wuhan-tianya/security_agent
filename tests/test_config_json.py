from __future__ import annotations

import json

from app.core.config import get_settings


def test_json_config_loaded(tmp_path, monkeypatch):
    cfg = {
        "llm_model": "test-model-from-json",
        "mcp_mode": "http",
        "llm_timeout_seconds": 55,
    }
    cfg_file = tmp_path / "settings.json"
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.setenv("CONFIG_FILE", str(cfg_file))
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.llm_model == "test-model-from-json"
    assert settings.mcp_mode == "http"
    assert settings.llm_timeout_seconds == 55


def test_env_overrides_json(tmp_path, monkeypatch):
    cfg = {
        "llm_model": "test-model-from-json"
    }
    cfg_file = tmp_path / "settings.json"
    cfg_file.write_text(json.dumps(cfg), encoding="utf-8")

    monkeypatch.setenv("CONFIG_FILE", str(cfg_file))
    monkeypatch.setenv("LLM_MODEL", "test-model-from-env")
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.llm_model == "test-model-from-env"
