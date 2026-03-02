from __future__ import annotations

import inspect
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from loguru import logger

from app.graph.events import append_event
from app.graph.nodes import _fallback_summary_from_tool
from app.graph.nodes import (
    build_reflect_messages,
    classify_security_intent,
    load_prompt_node,
    memory_read_node,
    memory_write_node,
    skill_call_node,
)
from app.graph.builder import build_graph
from app.core.config import get_settings
from app.llm.openai_compatible import OpenAICompatibleClient
from app.memory.repository import Repository
from app.prompts.loader import PromptLoader
from app.skills.registry import SkillRegistry


class AgentService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.settings = get_settings()
        self.prompt_loader = PromptLoader()
        self.registry = SkillRegistry()
        self.llm_client = OpenAICompatibleClient()
        self.graph = build_graph(repo, self.prompt_loader, self.registry, self.llm_client)

    async def run(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        initial_state: dict[str, Any] = {
            "session_id": session_id,
            "user_input": user_input,
            "model": model,
            "events": [],
        }
        result = await self.graph.ainvoke(initial_state)
        return result

    async def stream_sse_events(
        self,
        session_id: str,
        user_input: str,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        yield self._format_sse("run_started", {"session_id": session_id})
        state: dict[str, Any] = {
            "session_id": session_id,
            "user_input": user_input,
            "model": model,
            "events": [],
        }

        emitted = 0
        async def _emit_new_events():
            nonlocal emitted
            for evt in state.get("events", [])[emitted:]:
                yield self._format_sse(evt["event"], evt["data"])
            emitted = len(state.get("events", []))

        state = await load_prompt_node(state, self.prompt_loader)
        async for msg in _emit_new_events():
            yield msg

        state = await memory_read_node(state, self.repo)
        async for msg in _emit_new_events():
            yield msg

        state = await classify_security_intent(state, self.llm_client)
        async for msg in _emit_new_events():
            yield msg

        state = await skill_call_node(state, self.registry, self.llm_client)
        async for msg in _emit_new_events():
            yield msg

        if state.get("error_code"):
            final_response = f"工具调用失败（{state['error_code']}）：{state.get('error_message', 'unknown error')}"
            append_event(state, "reasoning_trace", {"decision": "fast_fail_on_skill_error"})
        else:
            messages = build_reflect_messages(state)

            try:
                logger.bind(session_id=state.get("session_id")).info("llm_messages={}", messages)
            except Exception:
                pass

            try:
                final_response = await self._run_model_loop_with_tools(state, messages)
                generated_reports = state.get("generated_reports") or []
                if generated_reports:
                    link_lines = []
                    for idx, item in enumerate(generated_reports, 1):
                        url = item.get("url") or ""
                        name = item.get("filename") or f"report_{idx}"
                        if url:
                            link_lines.append(f"{idx}. [{name}]({url})")
                    if link_lines:
                        final_response = (final_response or "").rstrip() + "\n\n报告链接：\n" + "\n".join(link_lines)
                if final_response:
                    for chunk in self._chunk_text(final_response):
                        yield self._format_sse("llm_token", {"token": chunk})
                else:
                    final_response = "工具调用已完成，但模型未返回文本结果。"
            except Exception as exc:
                logger.bind(session_id=state.get("session_id")).exception("llm_stream_failed_fallback: {}", str(exc))
                append_event(
                    state,
                    "reasoning_trace",
                    {"decision": "llm_stream_failed_retry_non_stream", "error": str(exc)[:300]},
                )
                try:
                    final_response = await self.llm_client.chat_completion(messages, model=state.get("model"))
                    if final_response:
                        yield self._format_sse("llm_token", {"token": final_response})
                except Exception as exc2:
                    logger.bind(session_id=state.get("session_id")).exception(
                        "llm_non_stream_failed_fallback: {}", str(exc2)
                    )
                    final_response = _fallback_summary_from_tool(state.get("selected_tool"), state.get("tool_result"))
                    append_event(
                        state,
                        "reasoning_trace",
                        {"decision": "llm_non_stream_failed_fallback", "error": str(exc2)[:300]},
                    )

        state["final_response"] = final_response
        append_event(state, "llm_response", {"preview": final_response[:500]})
        async for msg in _emit_new_events():
            yield msg

        state = await memory_write_node(state, self.repo)
        async for msg in _emit_new_events():
            yield msg

        if state.get("error_code"):
            yield self._format_sse(
                "run_error",
                {"error_code": state.get("error_code"), "message": state.get("error_message")},
            )

        yield self._format_sse("run_finished", {"final_response": final_response})

    @staticmethod
    def _format_sse(event: str, payload: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _chunk_text(text: str, size: int = 24) -> list[str]:
        if not text:
            return []
        return [text[i : i + size] for i in range(0, len(text), size)]

    async def _run_model_loop_with_tools(self, state: dict[str, Any], messages: list[dict[str, Any]]) -> str:
        tool_defs = self._build_runtime_tool_defs()
        if not tool_defs:
            return await self.llm_client.chat_completion(messages, model=state.get("model"))

        max_rounds = 8
        for round_idx in range(max_rounds):
            resp = await self.llm_client.chat_completion_with_tools(
                messages=messages,
                tools=tool_defs,
                tool_choice="auto",
                model=state.get("model"),
            )
            normalized_calls = self._normalize_model_tool_calls(resp, round_idx=round_idx)
            if not normalized_calls:
                return resp.get("content") or ""

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": resp.get("content") or "",
                "tool_calls": normalized_calls,
            }
            if "reasoning_content" in resp:
                assistant_msg["reasoning_content"] = resp.get("reasoning_content") or ""
            messages.append(assistant_msg)

            for call in normalized_calls:
                fn = call.get("function") or {}
                tool_name = fn.get("name")
                if not tool_name:
                    continue

                args_raw = fn.get("arguments") or "{}"
                if isinstance(args_raw, dict):
                    args = dict(args_raw)
                else:
                    try:
                        args = json.loads(args_raw) if str(args_raw).strip() else {}
                    except Exception:
                        logger.bind(session_id=state.get("session_id")).warning(
                            "reflect_tool_args_parse_failed tool={} args_raw={}",
                            tool_name,
                            str(args_raw)[:600],
                        )
                        args = {}

                append_event(state, "skill_call_started", {"tool": tool_name, "arguments": args})
                append_event(state, "mcp_call_started", {"tool": tool_name, "arguments": args})
                result = self._execute_tool_call(tool_name=tool_name, args=args)
                if tool_name == "generate_security_report" and result.get("success"):
                    report_data = result.get("data") or {}
                    state.setdefault("generated_reports", []).append(
                        {
                            "url": report_data.get("report_url") or "",
                            "filename": report_data.get("filename") or "",
                        }
                    )
                if result.get("success"):
                    append_event(state, "skill_call_finished", {"tool": tool_name, "result": result})
                    append_event(state, "mcp_call_finished", {"tool": tool_name, "result": result})
                else:
                    append_event(
                        state,
                        "skill_call_failed",
                        {"error_code": "SKILL_CALL_FAILED", "message": result.get("error", "unknown")},
                    )
                    append_event(
                        state,
                        "mcp_call_failed",
                        {"error_code": "SKILL_CALL_FAILED", "message": result.get("error", "unknown")},
                    )

                try:
                    tool_content = json.dumps(result, ensure_ascii=False)
                except Exception:
                    tool_content = str(result)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id"),
                        "content": tool_content,
                    }
                )

        logger.bind(session_id=state.get("session_id")).warning("model_tool_loop_reached_max_rounds rounds={}", max_rounds)
        return "工具调用轮次达到上限，已停止。"

    def _build_runtime_tool_defs(self) -> list[dict[str, Any]]:
        defs: list[dict[str, Any]] = []
        for info in self.registry.list_tools():
            tool = self.registry.get_tool(info.name)
            if tool is None:
                continue
            defs.append(
                {
                    "type": "function",
                    "function": {
                        "name": info.name,
                        "description": info.description,
                        "parameters": self._build_schema_from_execute(tool.execute),
                    },
                }
            )

        defs.append(
            {
                "type": "function",
                "function": {
                    "name": "generate_security_report",
                    "description": "生成安全测试报告并写入 summaries 目录，返回可访问路径",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "report_type": {"type": "string"},
                            "modules": {"type": "array", "items": {"type": "string"}},
                            "findings": {"type": "object"},
                            "output_filename": {"type": "string"},
                            "output_path": {"type": "string"},
                            "format": {"type": "string"},
                        },
                        "required": [],
                    },
                },
            }
        )
        return defs

    def _build_schema_from_execute(self, fn: Any) -> dict[str, Any]:
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []

        for name, p in sig.parameters.items():
            if name in {"self", "kwargs"}:
                continue
            if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
                continue
            prop: dict[str, Any] = {"type": "string"}
            ann = p.annotation
            ann_text = str(ann)
            if ann in (int, "int"):
                prop["type"] = "integer"
            elif ann in (float, "float"):
                prop["type"] = "number"
            elif ann in (bool, "bool"):
                prop["type"] = "boolean"
            elif "List" in ann_text or "list" in ann_text:
                prop = {"type": "array", "items": {"type": "string"}}
            properties[name] = prop
            if p.default is inspect.Parameter.empty:
                required.append(name)

        if not properties:
            properties = {"query": {"type": "string", "description": "User request or query to analyze."}}
            required = []

        return {"type": "object", "properties": properties, "required": required}

    def _normalize_model_tool_calls(self, resp: dict[str, Any], round_idx: int) -> list[dict[str, Any]]:
        raw_tool_calls = resp.get("tool_calls") or []
        normalized_calls: list[dict[str, Any]] = []

        for idx, call in enumerate(raw_tool_calls):
            call_id = call.get("id") or f"reflect_call_{round_idx}_{idx}"
            fn = call.get("function") or {}
            normalized_calls.append(
                {
                    "id": call_id,
                    "type": call.get("type") or "function",
                    "function": {
                        "name": fn.get("name") or call.get("name"),
                        "arguments": fn.get("arguments") or "{}",
                    },
                }
            )

        if normalized_calls:
            return normalized_calls

        content = resp.get("content") or ""
        if "<function_calls>" not in content:
            return []

        invoke_pattern = re.compile(r"<invoke\s+name=\"([^\"]+)\"\s*>(.*?)</invoke>", re.S | re.I)
        param_pattern = re.compile(r"<parameter\s+name=\"([^\"]+)\"\s*>(.*?)</parameter>", re.S | re.I)

        parsed: list[dict[str, Any]] = []
        for idx, (name, body) in enumerate(invoke_pattern.findall(content)):
            args: dict[str, Any] = {}
            for p_name, p_value in param_pattern.findall(body):
                args[p_name] = self._coerce_param_value(p_value)
            parsed.append(
                {
                    "id": f"content_call_{round_idx}_{idx}",
                    "type": "function",
                    "function": {"name": name.strip(), "arguments": json.dumps(args, ensure_ascii=False)},
                }
            )
        return parsed

    @staticmethod
    def _coerce_param_value(raw: str) -> Any:
        value = (raw or "").strip()
        if not value:
            return ""
        try:
            return json.loads(value)
        except Exception:
            return value

    def _execute_tool_call(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "generate_security_report":
            return self._execute_generate_security_report(args)

        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return {"success": False, "error": f"tool not found: {tool_name}", "data": {}}
        try:
            return tool.execute(**args)
        except Exception as exc:
            logger.exception("tool_execute_failed tool={} error={}", tool_name, str(exc))
            return {"success": False, "error": str(exc), "data": {}}

    def _execute_generate_security_report(self, args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("title") or "安全测试报告")
        report_type = str(args.get("report_type") or "comprehensive")
        findings = args.get("findings") or {}
        modules = args.get("modules") or []
        fmt = str(args.get("format") or "html").lower()

        backend_root = Path(__file__).resolve().parents[2]
        summaries_dir = backend_root / "summaries"
        summaries_dir.mkdir(parents=True, exist_ok=True)

        output_filename = args.get("output_filename")
        output_path = args.get("output_path")
        if output_filename:
            filename = Path(str(output_filename)).name
        elif output_path:
            filename = Path(str(output_path)).name
        else:
            ext = "md" if fmt == "md" else "html"
            filename = f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        report_file = summaries_dir / filename

        findings_text = json.dumps(findings, ensure_ascii=False, indent=2)
        modules_text = ", ".join(modules) if isinstance(modules, list) else str(modules)
        if fmt == "md":
            content = (
                f"# {title}\n\n"
                f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}\n"
                f"- 报告类型: {report_type}\n"
                f"- 模块: {modules_text}\n\n"
                f"## 发现\n\n```json\n{findings_text}\n```\n"
            )
        else:
            content = (
                "<!doctype html><html><head><meta charset='utf-8'>"
                f"<title>{title}</title></head><body>"
                f"<h1>{title}</h1>"
                f"<p>生成时间: {datetime.now().isoformat(timespec='seconds')}</p>"
                f"<p>报告类型: {report_type}</p>"
                f"<p>模块: {modules_text}</p>"
                "<h2>发现</h2>"
                f"<pre>{findings_text}</pre>"
                "</body></html>"
            )
        report_file.write_text(content, encoding="utf-8")

        relative_url = f"/summaries/{report_file.name}"
        base = (self.settings.public_base_url or "").rstrip("/")
        report_url = f"{base}{relative_url}" if base else relative_url
        return {
            "success": True,
            "data": {
                "report_path": str(report_file),
                "report_url": report_url,
                "relative_url": relative_url,
                "filename": report_file.name,
                "format": fmt,
            },
            "error": "",
        }
