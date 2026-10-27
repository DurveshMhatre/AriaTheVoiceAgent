import { describe, expect, it, vi } from "vitest";
import { callReducer } from "./reducer";
import { initialCallState } from "./state";
import type { CallEvent } from "./protocol";

function event(sequence: number, event_type: string, data: Record<string, unknown>, turn_id: string | null = "turn-1", event_id = `e${sequence}`): CallEvent {
  return { schema_version: 1, event_id, call_id: "call-test", tenant_id: "aura", turn_id, event_type, occurred_at: "2026-10-26T10:00:00Z", sequence, data };
}
const userTurn = (sequence: number, text = "question", id = `u${sequence}`) => event(sequence, "transcript_turn", { speaker: "user", text, stt_final_ms: 10, llm_first_token_ms: null, tts_first_byte_ms: null, end_to_end_ms: null }, "turn-1", id);
const duplicateCases = Array.from({ length: 10 }, (_, index) => [`duplicate-${index}`, index + 1]);
const orderCases = Array.from({ length: 10 }, (_, index) => [`ordered pair ${index}`, index]);
const failoverCases = Array.from({ length: 8 }, (_, index) => [`failover ${index}`, index]);
const interruptCases = Array.from({ length: 5 }, (_, index) => [`interrupt ${index}`, index]);
const failureCases = ["AUTH_REQUIRED", "CONNECTION_FAILED", "AGENT_START_TIMEOUT", "VOICE_UNAVAILABLE"];
const unknownCases = ["unknown_a", "future_event", "" ];

describe("call reducer", () => {
  it.each(duplicateCases)("is idempotent for %s", (_label, n) => {
    const current = callReducer(initialCallState(), { type: "EVENT", event: userTurn(Number(n)) });
    expect(callReducer(current, { type: "EVENT", event: userTurn(Number(n)) })).toBe(current);
    expect(current.transcript).toHaveLength(1);
  });
  it.each(orderCases)("sorts sequence numbers for %s", (_label, n) => {
    const first = userTurn(Number(n) + 2, "second", `b${n}`);
    const second = event(Number(n) + 1, "transcript_turn", { speaker: "assistant", text: "first", stt_final_ms: null, llm_first_token_ms: 3, tts_first_byte_ms: null, end_to_end_ms: 4 }, "turn-1", `a${n}`);
    const outOfOrder = callReducer(callReducer(initialCallState(), { type: "EVENT", event: first }), { type: "EVENT", event: second });
    expect(outOfOrder.events.map((item) => item.sequence)).toEqual([Number(n) + 1, Number(n) + 2]);
    expect(outOfOrder.transcript.map((turn) => turn.text)).toEqual(["first", "second"]);
  });
  it.each(failoverCases)("switches to text mode after provider failover %s", (_label, n) => {
    const result = callReducer(initialCallState(), { type: "EVENT", event: event(Number(n) + 1, "provider_failover", { kind: "stt", from_provider: "sarvam", to_provider: "text_mode" }) });
    expect(result.mode).toBe("text"); expect(result.textFallbackReason).toBe("stt");
  });
  it.each(interruptCases)("marks only the interrupted assistant turn for %s", (_label, n) => {
    let result = callReducer(initialCallState(), { type: "EVENT", event: event(Number(n) + 1, "transcript_turn", { speaker: "assistant", text: "spoken", stt_final_ms: null, llm_first_token_ms: 4, tts_first_byte_ms: 5, end_to_end_ms: 6 }) });
    result = callReducer(result, { type: "EVENT", event: event(Number(n) + 2, "interrupted", { spoken_text: "spoken" }) });
    expect(result.transcript[0].interrupted).toBe(true);
  });
  it.each(failureCases)("records friendly failure state for %s", (code) => {
    const result = callReducer(initialCallState(), { type: "FAIL", error: { code, message: "" } });
    expect(result.phase).toBe("error"); expect(result.error?.code).toBe(code);
  });
  it.each(unknownCases)("ignores unknown event type %s", (eventType) => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const before = initialCallState(); const result = callReducer(before, { type: "EVENT", event: event(1, eventType, {}) });
    expect(result.events).toHaveLength(0); expect(warn).toHaveBeenCalled(); warn.mockRestore();
  });
  it("walks through token, room, wake, live, ending, and ended phases", () => {
    let state = callReducer(initialCallState(), { type: "START_REQUEST" }); expect(state.phase).toBe("requesting_token");
    state = callReducer(state, { type: "TOKEN_RECEIVED", mode: "text" }); expect(state.phase).toBe("connecting");
    state = callReducer(state, { type: "ROOM_CONNECTED" }); expect(state.phase).toBe("waiting_for_agent");
    state = callReducer(state, { type: "EVENT", event: event(1, "state_changed", { state: "LISTENING" }) }); expect(state.phase).toBe("live");
    state = callReducer(state, { type: "END_REQUEST" }); expect(state.phase).toBe("ending");
    state = callReducer(state, { type: "END_TIMEOUT" }); expect(state.phase).toBe("ended"); expect(state.error?.code).toBe("SUMMARY_UNAVAILABLE");
  });
  it("starts live after an agent state arrived before the room status callback", () => {
    let state = callReducer(initialCallState(), { type: "EVENT", event: event(1, "state_changed", { state: "LISTENING" }) });
    state = callReducer(state, { type: "ROOM_CONNECTED" }); expect(state.phase).toBe("live");
  });
  it("ends at the call cap and records capacity and reconnect transitions", () => {
    let state = callReducer(initialCallState(), { type: "TOKEN_RECEIVED", mode: "text", maxCallSeconds: 2 });
    state = callReducer(state, { type: "ROOM_CONNECTED" }); state = callReducer(state, { type: "EVENT", event: event(1, "state_changed", { state: "LISTENING" }) });
    state = callReducer(state, { type: "TICK" }); expect(state.phase).toBe("live"); state = callReducer(state, { type: "TICK" }); expect(state.phase).toBe("ending");
    state = callReducer(state, { type: "RECONNECT" }); expect(state.reconnecting).toBe(true); state = callReducer(state, { type: "RECONNECTED" }); expect(state.reconnecting).toBe(false);
    state = callReducer(state, { type: "CAPACITY", capacity: "text_only" }); expect(state.capacity).toBe("text_only");
  });
  it("covers fallback payloads and terminal transitions", () => {
    let state = callReducer(initialCallState(), { type: "AGENT_ACTIVE" });
    expect(state.phase).toBe("live");
    state = callReducer(state, { type: "EVENT", event: event(1, "state_changed", { state: "CONNECTING" }) });
    state = callReducer(state, { type: "EVENT", event: event(2, "transcript_turn", { speaker: "system", text: "ignored" }) });
    state = callReducer(state, { type: "EVENT", event: event(3, "transcript_turn", { speaker: "user", text: "hello", stt_final_ms: null, llm_first_token_ms: null, tts_first_byte_ms: null, end_to_end_ms: null }) });
    state = callReducer(state, { type: "EVENT", event: event(4, "tool_called", { tool_name: "unknown_tool" }) });
    state = callReducer(state, { type: "EVENT", event: event(5, "tool_result", { tool_name: "unknown_tool", ok: false }) });
    state = callReducer(state, { type: "EVENT", event: event(6, "interrupted", { spoken_text: "partial speech" }, "turn-missing") });
    state = callReducer(state, { type: "EVENT", event: event(7, "provider_failover", { kind: "stt", from_provider: "a", to_provider: "another_provider" }) });
    state = callReducer(state, { type: "EVENT", event: event(8, "error", {}) });
    expect(state.transcript.some((turn) => turn.text === "partial speech" && turn.interrupted)).toBe(true);
    expect(state.tools.at(-1)?.ok).toBe(false);
    expect(state.error?.code).toBe("UNKNOWN_ERROR");
    state = callReducer(state, { type: "EVENT", event: event(9, "call_ended", { transcript: "malformed", summary: { call_summary: "Finished" } }) });
    expect(state.phase).toBe("ended");
    expect(state.summary?.call_summary).toBe("Finished");
    state = callReducer(state, { type: "END_TIMEOUT" });
    expect(state.error?.code).toBe("UNKNOWN_ERROR");
  });
  it("keeps idle and ended calls unchanged on end request and tick", () => {
    const idle = callReducer(initialCallState(), { type: "END_REQUEST" });
    expect(idle.phase).toBe("idle");
    const ended = callReducer(idle, { type: "END_TIMEOUT" });
    expect(ended.phase).toBe("ended");
    expect(callReducer(ended, { type: "END_REQUEST" })).toBe(ended);
    expect(callReducer(ended, { type: "TICK" }).phase).toBe("ended");
  });
});
