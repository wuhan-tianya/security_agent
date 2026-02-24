from __future__ import annotations

from typing import Any


def append_event(state: dict[str, Any], event: str, data: dict[str, Any]) -> None:
    state.setdefault("events", []).append({"event": event, "data": data})
