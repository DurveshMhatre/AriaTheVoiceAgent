import { isKnownEventType, type CallEvent } from "./protocol";
import { initialCallState, type CallState } from "./state";

export type CallAction =
  | { type: "START_REQUEST" } | { type: "TOKEN_RECEIVED"; mode: "voice" | "text"; maxCallSeconds?: number; fallbackReason?: string | null }
  | { type: "ROOM_CONNECTED" } | { type: "AGENT_ACTIVE" } | { type: "EVENT"; event: CallEvent }
  | { type: "END_REQUEST" } | { type: "END_TIMEOUT" } | { type: "FAIL"; error: { code: string; message: string } }
  | { type: "TICK" } | { type: "RECONNECT" } | { type: "RECONNECTED" } | { type: "CAPACITY"; capacity: CallState["capacity"] } | { type: "RESET" };

function stateFromEvents(state: CallState, events: CallEvent[]): CallState {
  const next = { ...state, events, transcript: [] as CallState["transcript"], tools: [] as CallState["tools"], latencies: [] as CallState["latencies"], summary: null as CallState["summary"] };
  for (const event of events) {
    const data = event.data;
    if (event.event_type === "state_changed" && typeof data.state === "string") {
      next.agentState = data.state as CallState["agentState"];
      if (next.phase === "waiting_for_agent" && data.state !== "CONNECTING") next.phase = "live";
      if (data.state === "ENDED") next.phase = "ending";
    } else if (event.event_type === "transcript_turn") {
      if (data.speaker === "user" || data.speaker === "assistant") {
        next.transcript.push({ speaker: data.speaker, text: String(data.text ?? ""), turn_id: event.turn_id ?? null });
        const latency = Object.fromEntries(["stt_final_ms", "llm_first_token_ms", "tts_first_byte_ms", "end_to_end_ms"].map((key) => [key, typeof data[key] === "number" ? data[key] as number : null]));
        if (Object.values(latency).some((value) => value !== null)) next.latencies.push(latency);
      }
    } else if (event.event_type === "tool_called") {
      const name = String(data.tool_name ?? "tool");
      const orderId = data.arguments && typeof data.arguments === "object" ? String((data.arguments as Record<string, unknown>).order_id ?? "") : "";
      next.tools.push({ toolName: name, label: name === "get_order_details" && orderId ? `Looking up ${orderId}` : `Checking ${name.replaceAll("_", " ")}`, ok: null, turnId: event.turn_id ?? null });
    } else if (event.event_type === "tool_result") {
      const name = String(data.tool_name ?? "tool");
      const index = next.tools.findLastIndex((tool) => tool.toolName === name && tool.ok === null);
      const ok = data.ok === true;
      const result = ok ? String(data.speakable_hint ?? data.status ?? "checked") : "could not be checked";
      if (index >= 0) {
        const prefix = next.tools[index].label.startsWith("Looking up ") ? next.tools[index].label.replace("Looking up", "Looked up") : name.replaceAll("_", " ");
        next.tools[index] = { ...next.tools[index], ok, label: `${prefix}: ${result}` };
      }
      else next.tools.push({ toolName: name, label: `${name.replaceAll("_", " ")}: ${result}`, ok, turnId: event.turn_id ?? null });
    } else if (event.event_type === "interrupted") {
      const turnId = event.turn_id ?? null;
      const turn = [...next.transcript].reverse().find((item) => item.speaker === "assistant" && item.turn_id === turnId);
      if (turn) turn.interrupted = true;
      else next.transcript.push({ speaker: "assistant", text: String(data.spoken_text ?? ""), turn_id: turnId, interrupted: true });
    } else if (event.event_type === "provider_failover" && data.to_provider === "text_mode") {
      next.mode = "text"; next.textFallbackReason = String(data.kind ?? "voice");
    } else if (event.event_type === "error") {
      next.error = { code: String(data.code ?? "UNKNOWN_ERROR"), message: String(data.message ?? "") };
    } else if (event.event_type === "call_ended") {
      if (Array.isArray(data.transcript)) next.transcript = data.transcript as CallState["transcript"];
      if (data.summary && typeof data.summary === "object") next.summary = data.summary as CallState["summary"];
      next.agentState = "ENDED"; next.phase = "ended";
    }
  }
  return next;
}

export function callReducer(state: CallState = initialCallState(), action: CallAction): CallState {
  switch (action.type) {
    case "RESET": return initialCallState();
    case "START_REQUEST": return { ...state, phase: "requesting_token", error: null, elapsedSeconds: 0, summary: null, transcript: [], tools: [], events: [], seenEventIds: [] };
    case "TOKEN_RECEIVED": {
      const alreadyFailedOver = state.events.some((item) => item.event_type === "provider_failover" && item.data.to_provider === "text_mode");
      return { ...state, phase: "connecting", mode: alreadyFailedOver ? "text" : action.mode, maxCallSeconds: action.maxCallSeconds ?? 300, textFallbackReason: action.fallbackReason ?? (alreadyFailedOver ? "provider failure" : null) };
    }
    case "ROOM_CONNECTED": return { ...state, phase: state.agentState !== "CONNECTING" ? "live" : "waiting_for_agent", reconnecting: false };
    case "AGENT_ACTIVE": return { ...state, phase: "live" };
    case "EVENT": {
      if (!isKnownEventType(action.event.event_type)) { if (process.env.NODE_ENV !== "production") console.warn("Ignoring unknown call event type"); return state; }
      if (state.seenEventIds.includes(action.event.event_id)) return state;
      const all = [...state.events, action.event].sort((a, b) => a.sequence - b.sequence || a.event_id.localeCompare(b.event_id));
      return stateFromEvents({ ...state, seenEventIds: [...state.seenEventIds, action.event.event_id] }, all);
    }
    case "END_REQUEST": return state.phase === "idle" || state.phase === "ended" ? state : { ...state, phase: "ending" };
    case "END_TIMEOUT": return { ...state, phase: "ended", error: state.summary ? state.error : { code: "SUMMARY_UNAVAILABLE", message: "" } };
    case "FAIL": return { ...state, phase: "error", error: action.error };
    case "TICK": return { ...state, elapsedSeconds: Math.min(state.maxCallSeconds, state.elapsedSeconds + 1), phase: state.elapsedSeconds + 1 >= state.maxCallSeconds && state.phase === "live" ? "ending" : state.phase };
    case "RECONNECT": return { ...state, reconnecting: true };
    case "RECONNECTED": return { ...state, reconnecting: false };
    case "CAPACITY": return { ...state, capacity: action.capacity };
  }
}
