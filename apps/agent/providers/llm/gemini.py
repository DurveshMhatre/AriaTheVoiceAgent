from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from .base import Message


class GeminiProvider:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini mode")
        from google import genai
        self._client = genai.Client(api_key=self.api_key)

    async def generate(self, messages: list[Message], tools: list[dict[str, Any]], params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        from google.genai import types
        contents = [types.Content(role=item.role, parts=[types.Part.from_text(text=item.content or "")]) for item in messages if item.content is not None]
        declarations = []
        for tool in tools:
            declarations.append(types.FunctionDeclaration(name=tool["name"], description=tool.get("description", ""), parameters_json_schema=tool.get("input_schema", {})))
        config = types.GenerateContentConfig(temperature=params.get("temperature", 0.1), max_output_tokens=params.get("max_output_tokens", 160), thinking_config=types.ThinkingConfig(thinking_level=params.get("thinking_level", "minimal")), tools=[types.Tool(function_declarations=declarations)] if declarations else None)
        stream = await self._client.aio.models.generate_content_stream(model=self.model, contents=contents, config=config)
        async for chunk in stream:
            for candidate in chunk.candidates or []:
                for part in candidate.content.parts or []:
                    if getattr(part, "function_call", None):
                        call = part.function_call
                        yield {"tool_call": {"call_id": getattr(part, "thought_signature", "gemini-call"), "name": call.name, "arguments": dict(call.args or {})}, "provider_metadata": {"thought_signature": getattr(part, "thought_signature", None)}}
                    elif getattr(part, "text", None):
                        yield {"text": part.text}
