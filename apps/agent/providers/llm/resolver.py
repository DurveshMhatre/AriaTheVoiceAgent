from __future__ import annotations

from collections.abc import Iterable


def resolve_model(candidates: Iterable[str], available: Iterable[dict[str, object]]) -> str:
    supported = {str(item["name"]): bool(item.get("tool_calling", False)) for item in available}
    for candidate in candidates:
        if supported.get(candidate, False):
            return candidate
    raise RuntimeError("No configured model is available with tool calling")
