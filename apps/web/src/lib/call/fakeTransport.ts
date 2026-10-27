import type { CallEvent, ClientMessage, TokenResponse } from "./protocol";
import type { CallTransport, TransportStatus } from "./transport";

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
export class FakeTransport implements CallTransport {
  private listeners = new Set<(event: CallEvent) => void>();
  private statuses = new Set<(status: TransportStatus, detail?: string) => void>();
  private sequence = 0; private callId = "fake-call"; private mode: "voice" | "text" = "text";
  private transcript: Array<{ speaker: "user" | "assistant"; text: string; turn_id: string | null; interrupted: boolean }> = [];
  onEvent(callback: (event: CallEvent) => void) { this.listeners.add(callback); return () => this.listeners.delete(callback); }
  onStatus(callback: (status: TransportStatus, detail?: string) => void) { this.statuses.add(callback); return () => this.statuses.delete(callback); }
  private status(status: TransportStatus, detail?: string) { this.statuses.forEach((fn) => fn(status, detail)); }
  private emit(event_type: string, data: Record<string, unknown>, turn_id: string | null = null) {
    if (event_type === "transcript_turn" && (data.speaker === "user" || data.speaker === "assistant")) this.transcript.push({ speaker: data.speaker, text: String(data.text ?? ""), turn_id, interrupted: false });
    const event: CallEvent = { schema_version: 1, event_id: `fake-${++this.sequence}`, call_id: this.callId, tenant_id: "aura", turn_id, event_type, occurred_at: new Date().toISOString(), sequence: this.sequence, data };
    this.listeners.forEach((fn) => fn(event));
  }
  async connect(mode: "voice" | "text"): Promise<TokenResponse> {
    if (process.env.NODE_ENV === "production") throw Object.assign(new Error("Fake transport is disabled in production"), { code: "UNKNOWN_ERROR" });
    this.mode = mode; this.sequence = 0; this.transcript = []; this.status("connecting"); await wait(100); this.status("token_received"); await wait(250); this.status("connected");
    await wait(350); this.status("agent_active");
    if (mode === "voice") this.emit("provider_failover", { kind: "stt", from_provider: "fake_voice", to_provider: "text_mode" });
    this.emit("state_changed", { state: "LISTENING" }, "turn-0");
    return { call_id: this.callId, room_name: "fake-room", server_url: "wss://fake.invalid", participant_token: "fake", expires_in_seconds: 600, voice_mode: mode, fallback_reason: null, max_call_seconds: 300 };
  }
  async send(message: ClientMessage) {
    if (message.type === "end_call") { this.finish(); return; }
    const text = message.text;
    const turn = `turn-${this.sequence + 1}`;
    this.emit("transcript_turn", { speaker: "user", text, stt_final_ms: null, llm_first_token_ms: null, tts_first_byte_ms: null, end_to_end_ms: null }, turn);
    this.emit("state_changed", { state: "THINKING" }, turn); await wait(250);
    const order = text.match(/ORD[- ]?10[123]/i)?.[0]?.replace(" ", "-").toUpperCase();
    if (order) {
      this.emit("tool_called", { tool_name: "get_order_details", arguments: { order_id: order } }, turn);
      await wait(150); this.emit("tool_result", { tool_name: "get_order_details", ok: true, status: order === "ORD-101" ? "Out for Delivery" : order === "ORD-102" ? "Delivered" : "Processing" }, turn);
    }
    const response = order ? `I found ${order}. The demo order status is ${order === "ORD-101" ? "out for delivery" : order === "ORD-102" ? "delivered" : "processing"}.` : /flight|goa/i.test(text) ? "I can help with Aura Skincare products, orders, and policies. What can I check for you?" : "I can help with Aura Skincare orders and policies. Could you tell me your order ID?";
    this.emit("transcript_turn", { speaker: "assistant", text: response, stt_final_ms: 260, llm_first_token_ms: 310, tts_first_byte_ms: null, end_to_end_ms: 570 }, turn);
    this.emit("state_changed", { state: "LISTENING" }, turn);
  }
  private finish() {
    this.emit("call_ended", { reason: "user_ended", transcript: this.transcript, summary: { schema_version: 1, customer_intent: "OTHER", order_id: null, resolution_status: "UNRESOLVED", policy_outcome: null, call_summary: "This scripted demo call ended.", follow_up_needed: false } });
  }
  async disconnect() { this.finish(); this.status("disconnected"); }
  async setMic() { }
}
