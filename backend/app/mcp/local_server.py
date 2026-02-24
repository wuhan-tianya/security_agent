from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Local MCP Tool Server")


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


TOOLS = [
    {
        "name": "ping_vehicle",
        "description": "Return vehicle connectivity status",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        },
    },
    {
        "name": "apk_analyzer",
        "description": "Mock APK security analyzer",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        },
    },
]


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/tools/list")
def list_tools() -> dict[str, Any]:
    return {"tools": TOOLS}


@app.post("/tools/call")
def call_tool(req: ToolCallRequest) -> dict[str, Any]:
    if req.name not in {t["name"] for t in TOOLS}:
        raise HTTPException(status_code=404, detail=f"tool not found: {req.name}")

    query = req.arguments.get("query", "")

    if req.name == "ping_vehicle":
        return {
            "success": True,
            "tool": req.name,
            "data": {
                "reachable": True,
                "latency_ms": 8,
                "note": f"pong: {query}"
            },
            "error": ""
        }

    if req.name == "apk_analyzer":
        return {
            "success": True,
            "tool": req.name,
            "data": {
                "risk_level": "medium",
                "findings": [
                    "debuggable=true",
                    "exported activity detected"
                ],
                "summary": f"mock analyzed: {query}"
            },
            "error": ""
        }

    raise HTTPException(status_code=500, detail="unreachable")
