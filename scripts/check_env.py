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
    "LLM_MODEL_CANDIDATES",
    "STT_MODEL",
    "SARVAM_REALTIME_ENABLED",
    "VOICE_MODE",
    "NEXT_SUPABASE_URL",
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
        name = line.split("=", 1)[0].strip()
        if name and name.replace("_", "a").isalnum() and name[0].isalpha():
            names.add(name)
    return names


declared = dotenv_names(Path(__file__).resolve().parents[1] / ".env")

for name in VARIABLES:
    print(f"{name}: {'SET' if os.getenv(name) or name in declared else 'MISSING'}")
