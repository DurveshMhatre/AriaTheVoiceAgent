from __future__ import annotations

from datetime import datetime
from typing import Any


def event(
    event_type: str,
    call_id: str,
    tenant_id: str,
    data: dict[str, Any],
    turn_id: str | None = None,
    sequence: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": f"evt-{sequence}",
        "call_id": call_id,
        "turn_id": turn_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "occurred_at": datetime.now().astimezone().isoformat(),
        "sequence": sequence,
        "data": data,
    }
