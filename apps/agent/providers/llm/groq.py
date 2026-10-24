from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from .base import Message


class GroqProvider:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required for Groq mode")
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=self.api_key)

    async def generate(self, messages: list[Message], tools: list[dict[str, Any]], params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for item in messages:
            message: dict[str, Any] = {"role": item.role, "content": item.content}
            if item.tool_calls:
                message["tool_calls"] = list(item.tool_calls)
            if item.provider_metadata:
                message.update(item.provider_metadata)
            payload.append(message)
        response = await self._client.chat.completions.create(model=self.model, messages=payload, tools=tools or None, temperature=params.get("temperature", 0.1), max_completion_tokens=params.get("max_output_tokens", 160), stream=True)
        async for chunk in response:
            for choice in chunk.choices:
                delta = choice.delta
                if delta.content:
                    yield {"text": delta.content}
                for call in delta.tool_calls or []:
                    yield {"tool_call": {"call_id": call.id, "name": call.function.name, "arguments": call.function.arguments}}
