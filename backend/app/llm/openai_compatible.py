from __future__ import annotations

import json as _json_module
from typing import Any, AsyncIterator

import httpx
from loguru import logger

from app.core.config import get_settings


def _truncate_messages_for_log(messages: list[dict[str, Any]], max_chars: int = 2000) -> str:
    """Serialize messages for logging, truncating to avoid flooding."""
    try:
        text = _json_module.dumps(messages, ensure_ascii=False)
        if len(text) > max_chars:
            return text[:max_chars] + f"... (truncated, total {len(text)} chars)"
        return text
    except Exception:
        return str(messages)[:max_chars]


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat_completion(self, messages: list[dict[str, Any]], model: str | None = None) -> str:
        result = await self._chat_completion_raw(messages=messages, model=model)
        return result["content"]

    async def chat_completion_with_tools(
        self,
        messages: list[dict[str, Any]],
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

    async def stream_chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> AsyncIterator[str | tuple[str, str]]:
        model_name = model or self.settings.llm_model
        if not self.settings.llm_api_key:
            yield "模型未配置 API Key，已返回基于规则的结果。"  # type: ignore[misc]
            return

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0,
            "stream": True,
        }
        logger.bind(event="llm_stream_request").info(
            "model={} message_count={} messages={}",
            model_name,
            len(messages),
            _truncate_messages_for_log(messages),
        )
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}", "User-Agent": "KimiCLI/1.6"}
        emitted_text = ""
        last_raw_chunk = ""
        no_progress_count = 0
        same_chunk_repeat = 0

        # Use separate timeouts: connect can be short, but read must be long
        # because thinking models (DeepSeek R1, Kimi, etc.) may spend minutes
        # in their reasoning phase before emitting the first content token.
        timeout = httpx.Timeout(
            connect=min(self.settings.llm_timeout_seconds, 30),
            read=300.0,
            write=30.0,
            pool=30.0,
        )
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        stripped = line.strip()
                        if not stripped.startswith("data:"):
                            continue
                        data = stripped.split("data:", 1)[1].strip()
                        if data == "[DONE]":
                            logger.bind(event="llm_stream_done").info(
                                "model={} total_emitted_chars={}", model_name, len(emitted_text)
                            )
                            break
                        try:
                            chunk = _json_module.loads(data)
                        except Exception:
                            logger.bind(event="llm_stream_parse_failed").warning("stream_line={}", stripped[:500])
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {})

                        # ---- reasoning_content (thinking tokens) ----
                        reasoning = delta.get("reasoning_content")
                        if reasoning:
                            yield ("reasoning", reasoning)

                        content = delta.get("content")
                        if not content:
                            continue

                        raw_chunk = content if isinstance(content, str) else str(content)
                        out = raw_chunk

                        # Compatibility: some providers stream cumulative content instead of deltas.
                        if emitted_text and raw_chunk.startswith(emitted_text):
                            out = raw_chunk[len(emitted_text):]
                        elif emitted_text and emitted_text.startswith(raw_chunk):
                            out = ""
                        elif raw_chunk == last_raw_chunk:
                            out = ""

                        if out:
                            emitted_text += out
                            no_progress_count = 0
                            same_chunk_repeat = 0
                            yield out
                        else:
                            no_progress_count += 1
                            if raw_chunk == last_raw_chunk:
                                same_chunk_repeat += 1
                            else:
                                same_chunk_repeat = 0
                            # Avoid endless repeating tail chunks from buggy gateways.
                            if same_chunk_repeat >= 40 or no_progress_count >= 300:
                                logger.bind(event="llm_stream_stalled").warning(
                                    "breaking stream due to no progress repeat={} stalled={}",
                                    same_chunk_repeat,
                                    no_progress_count,
                                )
                                break
                        last_raw_chunk = raw_chunk
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                body = exc.response.text[:500] if exc.response is not None else ""
                logger.bind(event="llm_http_error_stream").error("status={} body={}", status, body)
                raise RuntimeError(f"LLM HTTP {status}: {body}") from exc

    async def _chat_completion_raw(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model_name = model or self.settings.llm_model
        if not self.settings.llm_api_key:
            return {
                "content": "模型未配置 API Key，已返回基于规则的结果。",
                "tool_calls": [],
                "reasoning_content": "",
            }

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

        tool_names = [t.get("function", {}).get("name", "?") for t in (tools or [])]
        logger.bind(event="llm_request").info(
            "model={} message_count={} tools={} tool_choice={} messages={}",
            model_name,
            len(messages),
            tool_names or None,
            tool_choice,
            _truncate_messages_for_log(messages),
        )

        try:
            # trust_env=False avoids accidental proxy forwarding for private/self-hosted gateways.
            timeout = httpx.Timeout(
                connect=min(self.settings.llm_timeout_seconds, 30),
                read=300.0,
                write=30.0,
                pool=30.0,
            )
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
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
            logger.bind(event="llm_http_error").error("status={} body={}", status, body)
            raise RuntimeError(f"LLM HTTP {status}: {body}") from exc

        choices = data.get("choices") or []
        if not choices:
            logger.bind(event="llm_response").warning("model={} empty_choices", model_name)
            return {"content": "", "tool_calls": [], "reasoning_content": ""}
        message = choices[0].get("message") or {}
        result = {
            "content": message.get("content") or "",
            "tool_calls": message.get("tool_calls") or [],
            "reasoning_content": message.get("reasoning_content") or "",
        }
        content_preview = (result["content"] or "")[:500]
        reasoning_preview = (result["reasoning_content"] or "")[:300]
        logger.bind(event="llm_response").info(
            "model={} content_len={} tool_calls_count={} reasoning_len={} content_preview={} reasoning_preview={}",
            model_name,
            len(result["content"]),
            len(result["tool_calls"]),
            len(result["reasoning_content"]),
            content_preview,
            reasoning_preview,
        )
        return result
