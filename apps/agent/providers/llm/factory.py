from __future__ import annotations

import os
from typing import Any

from .mock import MockLLM


def create_llm(mode: str, model: str | None = None) -> Any:
    selected = mode.lower()
    if selected == "mock":
        return MockLLM()
    if selected == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model or os.getenv("LLM_MODEL", "gemini-3.1-flash-lite"))
    if selected == "groq":
        from .groq import GroqProvider
        return GroqProvider(model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))
    if selected == "auto":
        if os.getenv("GEMINI_API_KEY"):
            from .gemini import GeminiProvider
            return GeminiProvider(model or os.getenv("LLM_MODEL", "gemini-3.1-flash-lite"))
        if os.getenv("GROQ_API_KEY"):
            from .groq import GroqProvider
            return GroqProvider(model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"))
        return MockLLM()
    raise ValueError(f"Unsupported LLM mode: {mode}")
