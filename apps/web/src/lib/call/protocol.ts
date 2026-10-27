export type CallTurn = { speaker: "user" | "assistant"; text: string; turn_id: string | null; interrupted?: boolean };
export type CallSummary = { schema_version: 1; customer_intent: string; order_id: string | null; resolution_status: string; policy_outcome: string | null; call_summary: string; follow_up_needed: boolean };
export type CallEvent = { schema_version: 1; event_id: string; call_id: string; tenant_id: string; turn_id?: string | null; event_type: string; occurred_at: string; sequence: number; data: Record<string, unknown> };
export type ToolChip = { toolName: string; label: string; ok: boolean | null; turnId: string | null };
export type CapacityResponse = { capacity: "voice_available" | "text_only" | "busy" | "daily_limit_reached" | "unavailable"; checked_at: string; cache_seconds: 30 };
export type TokenResponse = { call_id: string; room_name: string; server_url: string; participant_token: string; expires_in_seconds: 600; voice_mode: "voice" | "text"; fallback_reason: string | null; max_call_seconds: number };
export type ClientMessage = { type: "text_input"; text: string } | { type: "end_call" };
export type ApiError = { error: { code: string; message: string }; fallback_mode: "text" | null };
const eventTypes = new Set(["state_changed", "transcript_turn", "tool_called", "tool_result", "interrupted", "provider_failover", "usage_tick", "error", "guardrail_triggered", "call_ended"]);
const apiErrorCodes = new Set(["AUTH_REQUIRED", "TOKEN_RATE_LIMIT", "CONCURRENT_CALL_LIMIT", "DAILY_IP_CALL_LIMIT", "MONTHLY_LIVEKIT_MINUTE_CAP", "MONTHLY_STT_CAP", "MONTHLY_TTS_CAP", "INVALID_ADMISSION_LIMITS", "VOICE_CAP_REACHED", "VOICE_UNAVAILABLE", "ORIGIN_NOT_ALLOWED", "INVALID_REQUEST", "MIGRATION_NOT_APPLIED", "CALL_DURATION_LIMIT", "PER_CALL_TTS_LIMIT", "AGENT_START_TIMEOUT", "CONNECTION_FAILED", "MIC_DENIED", "NO_MICROPHONE", "UNSUPPORTED_BROWSER", "TEXT_MODE_TURN_FAILED", "SUMMARY_UNAVAILABLE", "SESSION_EXPIRED", "UNKNOWN_ERROR"]);
export function isKnownEventType(value: string) { return eventTypes.has(value); }

export function parseCallEvent(input: unknown): CallEvent | null {
  if (!input || typeof input !== "object") return null;
  const value = input as Record<string, unknown>;
  if (value.schema_version !== 1 || typeof value.event_id !== "string" || typeof value.call_id !== "string" || typeof value.tenant_id !== "string" || typeof value.event_type !== "string" || typeof value.occurred_at !== "string" || !Number.isInteger(value.sequence) || !value.data || typeof value.data !== "object") return null;
  if (!isKnownEventType(value.event_type)) { if (process.env.NODE_ENV !== "production") console.warn("Ignoring unknown call event type"); return null; }
  return value as CallEvent;
}

export function parseApiError(input: unknown): ApiError | null {
  if (!input || typeof input !== "object") return null;
  const value = input as Partial<ApiError>;
  if (!value.error || typeof value.error.code !== "string" || !apiErrorCodes.has(value.error.code) || typeof value.error.message !== "string") return null;
  return { error: value.error, fallback_mode: value.fallback_mode ?? null };
}
