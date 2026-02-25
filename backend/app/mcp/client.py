from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class MCPError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]


class BaseMCPClient:
    async def list_tools(self, endpoint: str) -> list[MCPTool]:
        raise NotImplementedError

    async def call_tool(self, endpoint: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class HttpMCPClient(BaseMCPClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.mcp_timeout_seconds

    async def list_tools(self, endpoint: str) -> list[MCPTool]:
        try:
            # trust_env=False avoids accidental proxy routing for localhost/private IP MCP endpoints.
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await client.get(f"{endpoint.rstrip('/')}/tools/list")
                resp.raise_for_status()
                payload = resp.json()
            tools = []
            for t in payload.get("tools", []):
                tools.append(
                    MCPTool(
                        name=t.get("name", "unknown"),
                        description=t.get("description", ""),
                        input_schema=t.get("input_schema", {}),
                    )
                )
            return tools
        except httpx.TimeoutException as exc:
            raise MCPError("MCP_CONNECT_TIMEOUT", f"MCP list_tools timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            raise MCPError(
                "MCP_UNAVAILABLE",
                f"MCP list_tools HTTP {exc.response.status_code}: {body}",
            ) from exc
        except Exception as exc:
            raise MCPError("MCP_UNAVAILABLE", f"MCP list_tools failed: {exc}") from exc

    async def call_tool(self, endpoint: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                resp = await client.post(
                    f"{endpoint.rstrip('/')}/tools/call",
                    json={"name": tool_name, "arguments": arguments},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.TimeoutException as exc:
            raise MCPError("MCP_CONNECT_TIMEOUT", f"MCP call timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            raise MCPError(
                "MCP_UNAVAILABLE",
                f"MCP call HTTP {exc.response.status_code}: {body}",
            ) from exc
        except Exception as exc:
            raise MCPError("MCP_UNAVAILABLE", f"MCP call failed: {exc}") from exc


class StdioMCPClient(BaseMCPClient):
    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.mcp_timeout_seconds

    async def list_tools(self, endpoint: str) -> list[MCPTool]:
        payload = await self._exec(endpoint, {"method": "tools/list", "params": {}})
        tools = []
        for t in payload.get("tools", []):
            tools.append(
                MCPTool(
                    name=t.get("name", "unknown"),
                    description=t.get("description", ""),
                    input_schema=t.get("input_schema", {}),
                )
            )
        return tools

    async def call_tool(self, endpoint: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._exec(endpoint, {"method": "tools/call", "params": {"name": tool_name, "arguments": arguments}})

    async def _exec(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert proc.stdin is not None
            assert proc.stdout is not None
            proc.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
            await proc.stdin.drain()
            proc.stdin.close()

            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout)
            if not raw:
                stderr = await proc.stderr.read() if proc.stderr else b""
                raise MCPError("MCP_UNAVAILABLE", f"MCP stdio empty response: {stderr.decode('utf-8', 'ignore')}")
            return json.loads(raw.decode("utf-8"))
        except asyncio.TimeoutError as exc:
            raise MCPError("MCP_CONNECT_TIMEOUT", "MCP stdio timeout") from exc
        except MCPError:
            raise
        except Exception as exc:
            raise MCPError("MCP_UNAVAILABLE", f"MCP stdio failed: {exc}") from exc


class MCPClientManager:
    def __init__(self) -> None:
        settings = get_settings()
        mode = settings.mcp_mode.lower()
        self.mode = mode
        self.http_client = HttpMCPClient()
        self.stdio_client = StdioMCPClient()

    def client_for_endpoint(self, endpoint: str) -> BaseMCPClient:
        if self.mode == "http":
            return self.http_client
        if self.mode == "stdio":
            return self.stdio_client

        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return self.http_client
        return self.stdio_client
