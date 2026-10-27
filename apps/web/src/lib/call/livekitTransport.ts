import type { CallEvent, ClientMessage, TokenResponse } from "./protocol";
import type { CallTransport, TransportStatus } from "./transport";
import { parseCallEvent, parseApiError } from "./protocol";

export class LiveKitTransport implements CallTransport {
  private room: import("livekit-client").Room | null = null;
  private eventHandlers = new Set<(event: CallEvent) => void>();
  private statusHandlers = new Set<(status: TransportStatus, detail?: string) => void>();
  private token: TokenResponse | null = null;
  private audioElements = new Set<HTMLAudioElement>();
  private textOnly = false;
  private emitStatus(status: TransportStatus, detail?: string) { this.statusHandlers.forEach((handler) => handler(status, detail)); }
  onEvent(callback: (event: CallEvent) => void) { this.eventHandlers.add(callback); return () => this.eventHandlers.delete(callback); }
  onStatus(callback: (status: TransportStatus, detail?: string) => void) { this.statusHandlers.add(callback); return () => this.statusHandlers.delete(callback); }

  async connect(mode: "voice" | "text") {
    this.emitStatus("connecting");
    const response = await fetch("/api/livekit/token", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }) });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const error = parseApiError(body);
      throw Object.assign(new Error(error?.error.message ?? "Call request failed"), { code: error?.error.code ?? "UNKNOWN_ERROR" });
    }
    const token = body as TokenResponse;
    this.token = token;
    this.textOnly = token.voice_mode === "text";
    this.emitStatus("token_received");
    const lk = await import("livekit-client");
    const room = new lk.Room({ adaptiveStream: true, dynacast: true });
    this.room = room;
    let callEnded = false;
    room.on(lk.RoomEvent.DataReceived, (payload, _participant, _kind, topic) => {
      if (topic !== "aria.call-event" && topic !== "aria.agent-state") return;
      try {
        const decoded = JSON.parse(new TextDecoder().decode(payload)) as unknown;
        if (topic === "aria.call-event") {
          const event = parseCallEvent(decoded);
          if (event && event.call_id === token.call_id) {
            if (event.event_type === "call_ended") callEnded = true;
            if (event.event_type === "provider_failover" && event.data.to_provider === "text_mode") {
              this.textOnly = true;
              void this.setMic(false).catch(() => undefined);
            }
            this.eventHandlers.forEach((handler) => handler(event));
            if (event.event_type === "state_changed" && ["LISTENING", "THINKING", "SPEAKING"].includes(String(event.data.state))) this.emitStatus("agent_active");
          }
        } else if (decoded && typeof decoded === "object" && "state" in decoded) {
          const item = decoded as Record<string, unknown>;
          const event: CallEvent = { schema_version: 1, event_id: `agent-state-${String(item.sequence ?? Date.now())}`, call_id: token.call_id, tenant_id: "aura", event_type: "state_changed", occurred_at: new Date().toISOString(), sequence: Number(item.sequence ?? Date.now()), data: { state: item.state } };
          this.eventHandlers.forEach((handler) => handler(event));
        }
      } catch { this.emitStatus("error", "INVALID_EVENT"); }
    });
    room.on(lk.RoomEvent.Connected, () => this.emitStatus("connected"));
    room.on(lk.RoomEvent.Reconnecting, () => this.emitStatus("reconnecting"));
    room.on(lk.RoomEvent.Reconnected, () => this.emitStatus("reconnected"));
    room.on(lk.RoomEvent.Disconnected, () => {
      if (this.room !== room) return;
      if (!callEnded) this.emitStatus("disconnected");
      void this.disconnect().catch(() => undefined);
    });
    room.on(lk.RoomEvent.ParticipantDisconnected, (participant) => {
      if (!participant.isAgent || this.room !== room || callEnded) return;
      this.emitStatus("error", "CONNECTION_FAILED");
      void this.disconnect().catch(() => undefined);
    });
    room.on(lk.RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === lk.Track.Kind.Audio) {
        const audio = track.attach(); audio.autoplay = true; audio.setAttribute("aria-label", "Aria voice"); document.body.append(audio); this.audioElements.add(audio);
      }
    });
    // Call inside the user's click path so Safari can unlock audio playback.
    const playback = room.startAudio().catch(() => undefined);
    try {
      await room.connect(token.server_url, token.participant_token, { maxRetries: 1, autoSubscribe: true });
      await playback;
      if (this.room !== room) throw Object.assign(new Error("CONNECTION_FAILED"), { code: "CONNECTION_FAILED" });
      if (!this.textOnly) {
        try { await room.localParticipant.setMicrophoneEnabled(true); }
        catch (error) {
          const code = error instanceof DOMException && error.name === "NotFoundError" ? "NO_MICROPHONE" : "MIC_DENIED";
          throw Object.assign(new Error(code), { code });
        }
        if (this.room !== room) {
          await room.localParticipant.setMicrophoneEnabled(false).catch(() => undefined);
          throw Object.assign(new Error("CONNECTION_FAILED"), { code: "CONNECTION_FAILED" });
        }
        if (this.textOnly) await this.setMic(false);
      }
      return token;
    } catch (error) {
      await this.disconnect();
      throw error;
    }
  }

  async send(message: ClientMessage) {
    if (!this.room) throw new Error("NOT_CONNECTED");
    await this.room.localParticipant.publishData(new TextEncoder().encode(JSON.stringify(message)), { reliable: true, topic: "aria.client-message" });
  }
  async setMic(enabled: boolean) { if (this.room) await this.room.localParticipant.setMicrophoneEnabled(enabled); }
  async disconnect() {
    const callId = this.token?.call_id;
    const room = this.room;
    this.token = null;
    this.room = null;
    if (room) { await room.localParticipant.setMicrophoneEnabled(false).catch(() => undefined); await room.disconnect(); }
    this.audioElements.forEach((audio) => { audio.pause(); audio.srcObject = null; audio.remove(); }); this.audioElements.clear();
    if (callId) await fetch("/api/livekit/release", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ call_id: callId }) }).catch(() => undefined);
  }
}
