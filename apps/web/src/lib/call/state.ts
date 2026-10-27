import type { ApiError, CallEvent, CallSummary, CallTurn, CapacityResponse, ToolChip } from "./protocol";

export type CallPhase = "idle" | "requesting_token" | "connecting" | "waiting_for_agent" | "live" | "ending" | "ended" | "error";
export type AgentState = "CONNECTING" | "LISTENING" | "THINKING" | "SPEAKING" | "ENDED";
export type CallMode = "voice" | "text";

export type CallState = {
  phase: CallPhase; agentState: AgentState; mode: CallMode;
  capacity: CapacityResponse["capacity"]; events: CallEvent[]; seenEventIds: string[];
  transcript: CallTurn[]; tools: ToolChip[]; latencies: Array<Record<string, number | null>>;
  elapsedSeconds: number; maxCallSeconds: number; summary: CallSummary | null;
  error: ApiError["error"] | null; textFallbackReason: string | null; reconnecting: boolean;
};

export const initialCallState = (): CallState => ({
  phase: "idle", agentState: "CONNECTING", mode: "text", capacity: "unavailable",
  events: [], seenEventIds: [], transcript: [], tools: [], latencies: [], elapsedSeconds: 0,
  maxCallSeconds: 300, summary: null, error: null, textFallbackReason: null, reconnecting: false,
});
