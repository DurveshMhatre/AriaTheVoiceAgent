from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any, cast


class GeminiProvider:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini mode")
        from google import genai

        self._client = genai.Client(api_key=self.api_key)

    async def generate(
        self, messages: list[Any], tools: list[dict[str, Any]], params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        from google.genai import types

        contents: list[types.Content] = []
        system_instruction: str | None = None

        for item in messages:
            role = item["role"] if isinstance(item, dict) else item.role
            content = item.get("content") if isinstance(item, dict) else item.content
            tool_calls = (
                item.get("tool_calls")
                if isinstance(item, dict)
                else getattr(item, "tool_calls", None)
            )
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)

            if role == "system":
                system_instruction = content
            elif role == "user":
                if content:
                    contents.append(
                        types.Content(role="user", parts=[types.Part.from_text(text=content)])
                    )
            elif role in ("assistant", "model"):
                parts: list[types.Part] = []
                if content:
                    parts.append(types.Part.from_text(text=content))
                for tc in tool_calls or []:
                    tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tc_args = (
                        tc.get("arguments", {})
                        if isinstance(tc, dict)
                        else getattr(tc, "arguments", {})
                    )
                    if isinstance(tc_args, str):
                        try:
                            tc_args = json.loads(tc_args)
                        except Exception:
                            tc_args = {}
                    tc_sig = (
                        tc.get("thought_signature")
                        if isinstance(tc, dict)
                        else getattr(tc, "thought_signature", None)
                    )
                    if not tc_sig and isinstance(item, dict):
                        tc_sig = (item.get("provider_metadata") or {}).get("thought_signature")
                    call_id = (
                        (tc.get("call_id") or tc.get("id"))
                        if isinstance(tc, dict)
                        else getattr(tc, "call_id", None)
                    )
                    func_call = types.FunctionCall(name=tc_name, args=tc_args, id=call_id)
                    parts.append(types.Part(function_call=func_call, thought_signature=tc_sig))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                tc_name = name or "tool"
                resp_payload: Any = content or {}
                if isinstance(content, str):
                    try:
                        resp_payload = json.loads(content)
                    except Exception:
                        resp_payload = {"result": content}
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=tc_name,
                                    id=(
                                        item.get("tool_call_id")
                                        if isinstance(item, dict)
                                        else getattr(item, "tool_call_id", None)
                                    ),
                                    response={"result": resp_payload},
                                )
                            )
                        ],
                    )
                )

        declarations: list[types.FunctionDeclaration] = []
        for tool in tools:
            schema = tool.get("input_schema") or tool.get("parameters") or {}
            declarations.append(
                types.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters_json_schema=schema,
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=params.get("temperature", 0.1),
            max_output_tokens=params.get("max_output_tokens", 160),
            thinking_config=types.ThinkingConfig(
                thinking_level=params.get("thinking_level", "minimal")
            ),
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
        )
        stream = await self._client.aio.models.generate_content_stream(
            model=self.model, contents=cast(Any, contents), config=config
        )
        async for chunk in stream:
            for candidate in chunk.candidates or []:
                if candidate.content is None:
                    continue
                for part in candidate.content.parts or []:
                    if getattr(part, "function_call", None):
                        call = part.function_call
                        if call is None:
                            continue
                        call_id = getattr(call, "id", None) or "gemini-call"
                        thought_sig = getattr(part, "thought_signature", None)
                        yield {
                            "tool_call": {
                                "call_id": call_id,
                                "name": call.name,
                                "arguments": dict(call.args or {}),
                                "thought_signature": thought_sig,
                            },
                            "provider_metadata": {"thought_signature": thought_sig},
                        }
                    elif getattr(part, "text", None):
                        yield {"text": part.text}
