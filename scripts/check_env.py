"""Report whether required environment variables exist without revealing values."""
from __future__ import annotations

import os

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
]

for name in VARIABLES:
    print(f"{name}: {'SET' if os.getenv(name) else 'MISSING'}")
