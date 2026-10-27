import { describe, expect, it } from "vitest";
import Ajv2020 from "ajv/dist/2020.js";
import schema from "../../../../../contracts/call_events.json";
import { parseApiError, parseCallEvent } from "./protocol";
const ajv = new Ajv2020({ strict: false, formats: { "date-time": /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/ } }); const validate = ajv.compile(schema);
const finalEvent = { schema_version: 1, event_id: "e-final", call_id: "c", turn_id: null, tenant_id: "aura", event_type: "call_ended", occurred_at: "2026-10-26T10:00:00Z", sequence: 2, data: { reason: "session_closed", transcript: [], summary: { schema_version: 1, customer_intent: "OTHER", order_id: null, resolution_status: "UNRESOLVED", policy_outcome: null, call_summary: "Call ended.", follow_up_needed: false } } };
describe("wire protocol", () => {
  it.each([null, {}, [], { event_id: "x" }, { ...finalEvent, sequence: "2" }, { ...finalEvent, data: null }])("rejects malformed event %j", (value) => expect(parseCallEvent(value)).toBeNull());
  it("accepts and validates each supported event shape", () => {
    const events = [finalEvent,
      { ...finalEvent, event_id: "e1", event_type: "state_changed", turn_id: "turn-0", data: { state: "LISTENING" } },
      { ...finalEvent, event_id: "e2", event_type: "transcript_turn", turn_id: "turn-1", data: { speaker: "user", text: "hi", stt_final_ms: null, llm_first_token_ms: null, tts_first_byte_ms: null, end_to_end_ms: null } },
      { ...finalEvent, event_id: "e3", event_type: "tool_called", turn_id: "turn-1", data: { tool_name: "get_order_details", arguments: { order_id: "ORD-101" } } },
      { ...finalEvent, event_id: "e4", event_type: "tool_result", turn_id: "turn-1", data: { tool_name: "get_order_details", ok: true, speakable_hint: "Out for delivery" } },
      { ...finalEvent, event_id: "e5", event_type: "interrupted", turn_id: "turn-1", data: { spoken_text: "partial" } },
      { ...finalEvent, event_id: "e6", event_type: "provider_failover", turn_id: null, data: { kind: "stt", from_provider: "sarvam", to_provider: "text_mode" } },
      { ...finalEvent, event_id: "e7", event_type: "usage_tick", turn_id: null, data: { agent_seconds: 1 } },
      { ...finalEvent, event_id: "e8", event_type: "error", turn_id: null, data: { code: "VOICE_UNAVAILABLE", message: "Try text." } },
      { ...finalEvent, event_id: "e9", event_type: "guardrail_triggered", turn_id: "turn-1", data: { rule: "validator" } }];
    for (const value of events) { const parsed = parseCallEvent(value); expect(parsed).not.toBeNull(); expect(validate(parsed)).toBe(true); }
  });
  it("rejects unknown event types and malformed API errors", () => {
    expect(parseCallEvent({ ...finalEvent, event_type: "new_event" })).toBeNull();
    expect(parseApiError({ error: { code: "UNLISTED", message: "x" } })).toBeNull();
    expect(parseApiError({ error: { code: "AUTH_REQUIRED", message: "Sign in" } })?.error.code).toBe("AUTH_REQUIRED");
  });
});
