from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any, cast


class GroqProvider:
    def __init__(self, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is required for Groq mode")
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=self.api_key)

    async def generate(
        self, messages: list[Any], tools: list[dict[str, Any]], params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for item in messages:
            role = item["role"] if isinstance(item, dict) else item.role
            content = item.get("content") if isinstance(item, dict) else item.content
            tool_calls = (
                item.get("tool_calls")
                if isinstance(item, dict)
                else getattr(item, "tool_calls", None)
            )
            name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)

            msg: dict[str, Any] = {"role": role, "content": content or ""}
            if role == "tool":
                tool_call_id = (
                    item.get("tool_call_id")
                    if isinstance(item, dict)
                    else getattr(item, "tool_call_id", None)
                )
                if not tool_call_id:
                    raise ValueError("Tool results require their matching tool_call_id")
                msg["tool_call_id"] = tool_call_id
                if name:
                    msg["name"] = name
            elif tool_calls:
                formatted_tool_calls = []
                for idx, tc in enumerate(tool_calls):
                    tc_id = (
                        (tc.get("call_id") or tc.get("id") or f"call_{idx}")
                        if isinstance(tc, dict)
                        else getattr(tc, "call_id", f"call_{idx}")
                    )
                    tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                    tc_args = (
                        tc.get("arguments")
                        if isinstance(tc, dict)
                        else getattr(tc, "arguments", {})
                    )
                    if not isinstance(tc_args, str):
                        tc_args = json.dumps(tc_args)
                    formatted_tool_calls.append(
                        {
                            "id": tc_id,
                            "type": "function",
                            "function": {"name": tc_name, "arguments": tc_args},
                        }
                    )
                msg["tool_calls"] = formatted_tool_calls

            payload.append(msg)

        groq_tools = None
        if tools:
            groq_tools = []
            for t in tools:
                if "function" in t:
                    groq_tools.append(t)
                else:
                    groq_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": t["name"],
                                "description": t.get("description", ""),
                                "parameters": t.get("input_schema") or t.get("parameters") or {},
                            },
                        }
                    )

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=cast(Any, payload),
            tools=cast(Any, groq_tools),
            temperature=params.get("temperature", 0.1),
            max_completion_tokens=params.get("max_output_tokens", 160),
            parallel_tool_calls=False,
            stream=True,
        )
        stream = cast(AsyncIterator[Any], response)
        pending: dict[int, dict[str, str]] = {}
        async for chunk in stream:
            for choice in chunk.choices:
                delta = choice.delta
                if delta.content:
                    yield {"text": delta.content}
                for call in delta.tool_calls or []:
                    assembled = pending.setdefault(
                        call.index, {"call_id": "", "name": "", "arguments": ""}
                    )
                    if call.id:
                        assembled["call_id"] = call.id
                    if call.function is not None:
                        assembled["name"] += call.function.name or ""
                        assembled["arguments"] += call.function.arguments or ""
        for index in sorted(pending):
            assembled = pending[index]
            if not assembled["call_id"] or not assembled["name"]:
                raise ValueError("Incomplete streamed tool call")
            arguments = json.loads(assembled["arguments"] or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("Tool arguments must be a JSON object")
            yield {
                "tool_call": {
                    "call_id": assembled["call_id"],
                    "name": assembled["name"],
                    "arguments": arguments,
                }
            }
