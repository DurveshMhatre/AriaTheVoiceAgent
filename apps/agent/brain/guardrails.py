from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuardrailResult:
    text: str
    triggered: bool
    reasons: tuple[str, ...]


_PROMISES = re.compile(
    r"\b(refund approved|i will process|guaranteed|i have cancelled|replacement is guaranteed)\b",
    re.I,
)
_URL = re.compile(r"https?://|www\.", re.I)


def validate_output(
    text: str,
    config: dict[str, Any],
    grounded: list[str] | None = None,
    escalation: bool = False,
    detail_requested: bool = False,
) -> GuardrailResult:
    reasons: list[str] = []
    fallback = (
        "I can share only confirmed Aura information, and the support team can follow up if needed."
    )
    if _PROMISES.search(text):
        reasons.append("PROMISE_LANGUAGE")
    if _URL.search(text):
        text = _URL.sub("", text).strip()
        reasons.append("URL_REMOVED")
    text = re.sub(r"[\*_`#•]", "", text).strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not detail_requested and len(sentences) > 2:
        text = " ".join(sentences[:2])
        reasons.append("SENTENCE_LIMIT")
    if escalation and not re.search(r"support team|follow up|escalat", text, re.I):
        text = (text.rstrip(".!?") + ". The support team can follow up if needed.").strip()
        reasons.append("ESCALATION_OFFER")
    if "PROMISE_LANGUAGE" in reasons:
        return GuardrailResult(fallback, True, tuple(reasons))
    return GuardrailResult(text, bool(reasons), tuple(reasons))
