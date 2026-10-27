import asyncio
import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from providers.llm.breaker import CircuitBreaker
from providers.llm.failover import FailoverLLM
from providers.llm.gemini import GeminiProvider
from providers.llm.groq import GroqProvider
from providers.llm.resolver import resolve_model


def test_breaker_opens_after_threshold() -> None:
    breaker = CircuitBreaker(threshold=2)
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "closed"
    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow() is False


def test_resolver_uses_first_available_tool_model() -> None:
    available = [
        {"name": "gemini-3.1-flash-lite", "tool_calling": False},
        {"name": "gemini-3.5-flash", "tool_calling": True},
    ]
    assert (
        resolve_model(["gemini-3.1-flash-lite", "gemini-3.5-flash"], available)
        == "gemini-3.5-flash"
    )


def test_llm_failover_discards_partial_output_and_uses_next_provider() -> None:
    class BrokenProvider:
        async def generate(
            self, *_args: object, **_kwargs: object
        ) -> AsyncIterator[dict[str, Any]]:
            yield {"text": "partial answer"}
            raise RuntimeError("provider disconnected")

    class HealthyProvider:
        async def generate(
            self, *_args: object, **_kwargs: object
        ) -> AsyncIterator[dict[str, Any]]:
            yield {"text": "safe complete answer"}

    failovers: list[tuple[str, str]] = []

    async def on_failover(from_provider: str, to_provider: str) -> None:
        failovers.append((from_provider, to_provider))

    async def run() -> list[dict[str, object]]:
        provider = FailoverLLM(
            [("primary", BrokenProvider()), ("fallback", HealthyProvider())],
            on_failover,
        )
        return [item async for item in provider.generate([], [], {})]

    output = asyncio.run(run())

    assert output == [{"text": "safe complete answer"}]
    assert failovers == [("primary", "fallback")]


def groq_stream(chunks: list[list[dict[str, Any]]]) -> tuple[GroqProvider, list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []

    async def create(**kwargs: Any) -> AsyncIterator[Any]:
        requests.append(kwargs)

        async def stream() -> AsyncIterator[Any]:
            for calls in chunks:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=call["index"],
                                        id=call.get("id"),
                                        function=SimpleNamespace(
                                            name=call.get("name"),
                                            arguments=call.get("arguments", ""),
                                        ),
                                    )
                                    for call in calls
                                ],
                            )
                        )
                    ]
                )

        return stream()

    provider = GroqProvider.__new__(GroqProvider)
    provider.model = "llama-3.3-70b-versatile"
    provider._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create),
        )
    )
    return provider, requests


def test_groq_assembles_interleaved_tool_call_fragments() -> None:
    provider, _ = groq_stream(
        [
            [{"index": 0, "id": "lookup-1", "name": "get_order_details", "arguments": '{"order_'}],
            [
                {
                    "index": 1,
                    "id": "return-2",
                    "name": "check_return_eligibility",
                    "arguments": '{"opened":',
                }
            ],
            [{"index": 0, "arguments": 'id":"ORD-101"}'}, {"index": 1, "arguments": "false}"}],
        ]
    )

    async def run() -> list[dict[str, Any]]:
        return [item async for item in provider.generate([], [], {})]

    assert asyncio.run(run()) == [
        {
            "tool_call": {
                "call_id": "lookup-1",
                "name": "get_order_details",
                "arguments": {"order_id": "ORD-101"},
            }
        },
        {
            "tool_call": {
                "call_id": "return-2",
                "name": "check_return_eligibility",
                "arguments": {"opened": False},
            }
        },
    ]


def test_groq_rejects_incomplete_tool_arguments_before_dispatch() -> None:
    provider, _ = groq_stream(
        [
            [
                {
                    "index": 0,
                    "id": "lookup-1",
                    "name": "get_order_details",
                    "arguments": '{"order_id":',
                }
            ],
        ]
    )

    async def run() -> None:
        async for _ in provider.generate([], [], {}):
            pass

    with pytest.raises(ValueError):
        asyncio.run(run())


def test_groq_preserves_tool_result_id_without_vendor_metadata_leakage() -> None:
    provider, requests = groq_stream([])
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "call_id": "lookup-1",
                    "name": "get_order_details",
                    "arguments": {"order_id": "ORD-101"},
                    "thought_signature": b"gemini-only",
                },
            ],
            "provider_metadata": {"thought_signature": b"gemini-only"},
        },
        {
            "role": "tool",
            "name": "get_order_details",
            "tool_call_id": "lookup-1",
            "content": json.dumps({"ok": True}),
        },
    ]

    async def run() -> None:
        async for _ in provider.generate(messages, [], {}):
            pass

    asyncio.run(run())
    assert requests[0]["messages"][0]["tool_calls"][0]["id"] == "lookup-1"
    assert requests[0]["messages"][1]["tool_call_id"] == "lookup-1"
    assert "thought_signature" not in requests[0]["messages"][0]
    assert requests[0]["parallel_tool_calls"] is False


def test_gemini_preserves_function_response_ids_and_thought_signatures() -> None:
    from google.genai import types

    requests = []

    async def generate_content_stream(**kwargs: Any) -> AsyncIterator[Any]:
        requests.append(kwargs)

        async def stream() -> AsyncIterator[Any]:
            yield types.GenerateContentResponse(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="model",
                            parts=[types.Part.from_text(text="The order is out for delivery.")],
                        )
                    )
                ]
            )

        return stream()

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model = "gemini-3.1-flash-lite"
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content_stream=generate_content_stream,
            )
        )
    )
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "call_id": "gemini-lookup-1",
                    "name": "get_order_details",
                    "arguments": {"order_id": "ORD-101"},
                    "thought_signature": b"opaque-signature",
                }
            ],
        },
        {
            "role": "tool",
            "name": "get_order_details",
            "tool_call_id": "gemini-lookup-1",
            "content": json.dumps({"ok": True}),
        },
    ]

    async def run() -> None:
        async for _ in provider.generate(messages, [], {}):
            pass

    asyncio.run(run())
    contents = requests[0]["contents"]
    assert contents[0].parts[0].thought_signature == b"opaque-signature"
    assert contents[0].parts[0].function_call.id == "gemini-lookup-1"
    assert contents[1].parts[0].function_response.id == "gemini-lookup-1"
