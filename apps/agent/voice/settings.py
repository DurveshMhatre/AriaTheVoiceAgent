from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceSettings:
    mode: str
    stt_mode: str
    realtime_enabled: bool
    max_call_seconds: int
    idle_timeout_seconds: int
    max_concurrent_calls: int
    monthly_stt_seconds_cap: int
    monthly_tts_characters_cap: int
    per_call_tts_characters_cap: int
    agent_name: str

    @classmethod
    def from_env(cls) -> VoiceSettings:
        mode = os.getenv("VOICE_MODE", "mock").strip().lower()
        stt_mode = os.getenv("SARVAM_STT_MODE", "realtime").strip().lower()
        realtime_enabled_raw = os.getenv("SARVAM_REALTIME_ENABLED", "true").strip().lower()
        stt_model = os.getenv("STT_MODEL", "saaras:v3-realtime").strip()
        if mode not in {"mock", "real"}:
            raise ValueError("VOICE_MODE must be mock or real")
        if stt_mode not in {"realtime", "legacy"}:
            raise ValueError("SARVAM_STT_MODE must be realtime or legacy")
        if realtime_enabled_raw not in {"true", "false"}:
            raise ValueError("SARVAM_REALTIME_ENABLED must be true or false")
        if stt_mode == "realtime" and stt_model != "saaras:v3-realtime":
            raise ValueError("STT_MODEL must be saaras:v3-realtime for realtime mode")
        return cls(
            mode=mode,
            stt_mode=stt_mode,
            realtime_enabled=realtime_enabled_raw == "true",
            max_call_seconds=_bounded_int("MAX_CALL_SECONDS", 300, 30, 300),
            idle_timeout_seconds=_bounded_int("IDLE_TIMEOUT_SECONDS", 45, 10, 120),
            max_concurrent_calls=_bounded_int("MAX_CONCURRENT_CALLS", 4, 1, 4),
            monthly_stt_seconds_cap=_bounded_int("MAX_SARVAM_STT_SECONDS_MONTH", 7200, 60, 7200),
            monthly_tts_characters_cap=_bounded_int(
                "MAX_SARVAM_TTS_CHARACTERS_MONTH", 10000, 100, 10000
            ),
            per_call_tts_characters_cap=_bounded_int(
                "MAX_TTS_CHARACTERS_PER_CALL", 2500, 100, 2500
            ),
            agent_name=os.getenv("LIVEKIT_AGENT_NAME", "aria-voice").strip() or "aria-voice",
        )


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
