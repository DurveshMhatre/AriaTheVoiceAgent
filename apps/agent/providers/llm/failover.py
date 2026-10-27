from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .breaker import CircuitBreaker


@dataclass
class _Route:
    name: str
    provider: Any
    breaker: CircuitBreaker


class FailoverLLM:
    """Try configured providers in order and expose only a complete provider turn."""

    def __init__(
        self,
        routes: list[tuple[str, Any]],
        on_failover: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        self.routes = [_Route(name, provider, CircuitBreaker()) for name, provider in routes]
        self.on_failover = on_failover

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        failures: list[Exception] = []
        last_provider = "configured_llm"
        for route in self.routes:
            if not route.breaker.allow():
                continue
            try:
                output = [
                    item async for item in route.provider.generate(messages, tools, params)
                ]
            except Exception as exc:
                route.breaker.record_failure()
                failures.append(exc)
                last_provider = route.name
                continue
            route.breaker.record_success()
            if failures and self.on_failover is not None:
                await self.on_failover(last_provider, route.name)
            for item in output:
                yield item
            return
        if failures:
            raise RuntimeError("All configured LLM providers failed") from failures[-1]
        raise RuntimeError("All configured LLM providers are temporarily unavailable")
