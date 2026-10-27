"""Report whether required environment variables exist without revealing values."""
from __future__ import annotations

import os
from pathlib import Path

VARIABLES = [
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "SARVAM_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "LLM_MODEL_CANDIDATES",
    "SARVAM_STT_MODE",
    "STT_MODEL",
    "SARVAM_REALTIME_ENABLED",
    "SARVAM_TTS_SPEAKER",
    "LIVEKIT_AGENT_NAME",
    "MAX_CALL_SECONDS",
    "IDLE_TIMEOUT_SECONDS",
    "MAX_CONCURRENT_CALLS",
    "MAX_DAILY_CALLS_PER_IP",
    "MAX_TOKEN_REQUESTS_PER_IP_PER_MINUTE",
    "MAX_LIVEKIT_AGENT_SECONDS_MONTH",
    "MAX_SARVAM_STT_SECONDS_MONTH",
    "MAX_SARVAM_TTS_CHARACTERS_MONTH",
    "MAX_TTS_CHARACTERS_PER_CALL",
    "IP_HASH_SECRET",
    "VOICE_MODE",
    "LLM_MODE",
]


def dotenv_names(path: Path) -> set[str]:
    """Return names declared in dotenv without reading or printing values."""
    if not path.exists():
        return set()
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        if name and value and name.replace("_", "a").isalnum() and name[0].isalpha():
            names.add(name)
    return names


declared = dotenv_names(Path(__file__).resolve().parents[1] / ".env")

def dotenv_value(path: Path, target: str) -> str | None:
    """Read a local value for validation without printing it."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == target:
            return value.strip().strip("\"'")
    return None

env_path = Path(__file__).resolve().parents[1] / ".env"

for name in VARIABLES:
    print(f"{name}: {'SET' if os.getenv(name) or name in declared else 'MISSING'}")

ip_hash_secret = os.getenv("IP_HASH_SECRET") or dotenv_value(env_path, "IP_HASH_SECRET") or ""
print(f"IP_HASH_SECRET length: {'PASS' if len(ip_hash_secret) >= 32 else 'FAIL (needs at least 32 characters)'}")
