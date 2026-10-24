from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


class MockLLM:
    def __init__(self, scripted: list[dict[str, Any]] | None = None) -> None:
        self.scripted = scripted or [{"text": "I can help with Aura Skincare orders and policies."}]
        self.index = 0

    async def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        item = self.scripted[min(self.index, len(self.scripted) - 1)]
        self.index += 1
        yield item
