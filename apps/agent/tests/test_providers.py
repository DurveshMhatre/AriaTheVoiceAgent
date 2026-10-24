from brain.providers.llm.breaker import CircuitBreaker
from brain.providers.llm.resolver import resolve_model


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
    assert resolve_model(["gemini-3.1-flash-lite", "gemini-3.5-flash"], available) == "gemini-3.5-flash"
