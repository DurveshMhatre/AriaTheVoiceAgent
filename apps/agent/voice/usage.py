from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class SupabaseUsageMeter:
    def __init__(self, base_url: str, service_role_key: str) -> None:
        self.url = f"{base_url.rstrip('/')}/rest/v1/rpc/complete_voice_call"
        self.service_role_key = service_role_key

    async def complete_call(
        self,
        call_id: str,
        *,
        agent_seconds: int,
        stt_seconds: int,
        tts_characters: int,
    ) -> None:
        payload: dict[str, str | int] = {
            "p_call_id": call_id,
            "p_agent_seconds": max(0, agent_seconds),
            "p_stt_seconds": max(0, stt_seconds),
            "p_tts_characters": max(0, tts_characters),
        }
        await asyncio.to_thread(self._post, payload)

    def _post(self, payload: dict[str, str | int]) -> None:
        request = Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=5) as response:
                if response.status >= 400:
                    raise RuntimeError(
                        f"Supabase usage update failed with HTTP {response.status}"
                    )
        except HTTPError as exc:
            raise RuntimeError(
                f"Supabase usage update failed with HTTP {exc.code}"
            ) from exc

    @classmethod
    def from_env(cls) -> SupabaseUsageMeter:
        url = os.getenv("SUPABASE_URL", "").strip()
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise RuntimeError("Supabase server credentials are required in real voice mode")
        return cls(url, key)
