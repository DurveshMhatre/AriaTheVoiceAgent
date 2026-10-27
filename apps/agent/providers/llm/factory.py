from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

from .mock import MockLLM
from .resolver import resolve_model


def _model_name(model: str | None, default: str) -> str:
    return model or os.getenv("LLM_MODEL") or default


def create_llm(mode: str, model: str | None = None) -> Any:
    selected = mode.lower()
    if selected == "mock":
        return MockLLM()
    if selected == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(_model_name(model, "gemini-3.1-flash-lite"))
    if selected == "groq":
        from .groq import GroqProvider

        return GroqProvider(_model_name(model, "llama-3.3-70b-versatile"))
    if selected == "auto":
        if os.getenv("GEMINI_API_KEY"):
            from .gemini import GeminiProvider

            return GeminiProvider(_model_name(model, "gemini-3.1-flash-lite"))
        if os.getenv("GROQ_API_KEY"):
            from .groq import GroqProvider

            return GroqProvider(_model_name(model, "llama-3.3-70b-versatile"))
        return MockLLM()
    raise ValueError(f"Unsupported LLM mode: {mode}")


async def create_real_llm(
    model_candidates: list[str],
    on_failover: Callable[[str, str], Awaitable[None]],
) -> Any:
    """Resolve approved Gemini candidates for this key, then add Groq as failover."""
    from .failover import FailoverLLM

    approved_candidates = {"gemini-3.1-flash-lite", "gemini-3.5-flash"}
    candidates = [
        candidate.strip()
        for candidate in model_candidates
        if candidate.strip() in approved_candidates
    ]
    routes: list[tuple[str, Any]] = []
    if os.getenv("GEMINI_API_KEY") and candidates:
        try:
            available = await _available_gemini_models()
            selected = resolve_model(candidates, available)
            from .gemini import GeminiProvider

            routes.append(("gemini", GeminiProvider(selected)))
        except Exception:
            # A metadata-list failure must not prevent the configured Groq route from starting.
            pass
    if os.getenv("GROQ_API_KEY"):
        from .groq import GroqProvider

        routes.append(
            ("groq", GroqProvider(os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")))
        )
    if not routes:
        raise RuntimeError("No configured Gemini or Groq model is available for this key")
    return FailoverLLM(routes, on_failover)


async def _available_gemini_models() -> list[dict[str, object]]:
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    approved_candidates = {"gemini-3.1-flash-lite", "gemini-3.5-flash"}

    def list_supported() -> list[dict[str, object]]:
        supported: list[dict[str, object]] = []
        for model in client.models.list():
            actions = getattr(model, "supported_actions", None) or []
            name = str(getattr(model, "name", "")).removeprefix("models/")
            if name:
                supported.append(
                    {
                        "name": name,
                        "tool_calling": name in approved_candidates
                        and "generateContent" in actions,
                    }
                )
        return supported

    try:
        return await asyncio.to_thread(list_supported)
    finally:
        client.close()
