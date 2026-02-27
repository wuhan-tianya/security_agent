from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat_completion(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        result = await self._chat_completion_raw(messages=messages, model=model)
        return result["content"]

    async def chat_completion_with_tools(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        result = await self._chat_completion_raw(
            messages=messages,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )
        return result

    async def _chat_completion_raw(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_name = model or self.settings.llm_model
        if not self.settings.llm_api_key:
            return {"content": "模型未配置 API Key，已返回基于规则的结果。", "tool_calls": []}

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0,
        }
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}", "User-Agent": "KimiCLI/1.6"}

        try:
            # trust_env=False avoids accidental proxy forwarding for private/self-hosted gateways.
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds, trust_env=False) as client:
                resp = await client.post(
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text[:500] if exc.response is not None else ""
            raise RuntimeError(f"LLM HTTP {status}: {body}") from exc

        message = data["choices"][0]["message"]
        return {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
        }
