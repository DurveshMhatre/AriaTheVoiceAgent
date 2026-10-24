from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class Message:
    role: str
    content: str | None = None
    tool_calls: tuple[dict[str, Any], ...] = ()
    provider_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


class LlmProvider(Protocol):
    async def generate(self, messages: list[Message], tools: list[dict[str, Any]], params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...
