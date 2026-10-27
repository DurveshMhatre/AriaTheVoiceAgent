import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveKitTransport } from "./livekitTransport";

const fake = vi.hoisted(() => ({ handlers: {} as Record<string, (...args: unknown[]) => void>, micFailure: false, onMicEnabled: undefined as (() => void) | undefined }));

vi.mock("livekit-client", () => ({
  RoomEvent: {
    DataReceived: "data_received",
    Connected: "connected",
    Reconnecting: "reconnecting",
    Reconnected: "reconnected",
    Disconnected: "disconnected",
    ParticipantConnected: "participant_connected",
    ParticipantDisconnected: "participant_disconnected",
    TrackSubscribed: "track_subscribed",
  },
  Track: { Kind: { Audio: "audio" } },
  Room: class {
    localParticipant = {
      publishData: vi.fn(async () => undefined),
      setMicrophoneEnabled: vi.fn(async (enabled: boolean) => {
        if (fake.micFailure) throw new DOMException("denied", "NotAllowedError");
        if (enabled) fake.onMicEnabled?.();
      }),
    };
    on = vi.fn((event: string, callback: (...args: unknown[]) => void) => {
      fake.handlers[event] = callback;
      return this;
    });
    startAudio = vi.fn(async () => undefined);
    connect = vi.fn(async () => { fake.handlers.connected?.(); });
    disconnect = vi.fn(async () => { fake.handlers.disconnected?.(); });
  },
}));

const token = {
  call_id: "call-1",
  room_name: "room-1",
  server_url: "wss://livekit.example.test",
  participant_token: "short-lived",
  expires_in_seconds: 600,
  voice_mode: "text" as const,
  fallback_reason: null,
  max_call_seconds: 300,
};

describe("LiveKitTransport", () => {
  beforeEach(() => {
    fake.handlers = {};
    fake.micFailure = false;
    fake.onMicEnabled = undefined;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/release")) return new Response(null, { status: 204 });
      return Response.json(token);
    }));
  });

  it("connects, publishes messages, receives events, attaches audio, and releases", async () => {
    const transport = new LiveKitTransport();
    const statuses: string[] = [];
    const events: unknown[] = [];
    transport.onStatus((status) => statuses.push(status));
    transport.onEvent((event) => events.push(event));
    await transport.connect("text");
    expect(statuses).not.toContain("agent_active");
    fake.handlers.reconnecting();
    fake.handlers.reconnected();
    const callEvent = { schema_version: 1, event_id: "evt-1", call_id: "call-1", tenant_id: "aura", event_type: "state_changed", turn_id: "t1", occurred_at: "2026-10-26T10:00:00Z", sequence: 1, data: { state: "LISTENING" } };
    fake.handlers.data_received(new TextEncoder().encode(JSON.stringify(callEvent)), null, null, "aria.call-event");
    fake.handlers.data_received(new TextEncoder().encode(JSON.stringify({ state: "SPEAKING", sequence: 2 })), null, null, "aria.agent-state");
    fake.handlers.data_received(new TextEncoder().encode("{}"), null, null, "unrelated");
    const audio = document.createElement("audio");
    vi.spyOn(audio, "pause").mockImplementation(() => undefined);
    fake.handlers.track_subscribed({ kind: "audio", attach: () => audio });
    await transport.send({ type: "text_input", text: "hello" });
    await transport.setMic(true);
    await transport.disconnect();
    expect(statuses).toContain("agent_active");
    expect(statuses).toContain("reconnecting");
    expect(events).toHaveLength(2);
    expect(audio.isConnected).toBe(false);
    expect(fetch).toHaveBeenCalledWith("/api/livekit/release", expect.objectContaining({ method: "POST" }));
  });

  it("switches off the microphone when the worker falls back to text", async () => {
    const transport = new LiveKitTransport();
    await transport.connect("text");
    const setMic = vi.spyOn(transport, "setMic");
    const event = { schema_version: 1, event_id: "fallback-1", call_id: "call-1", tenant_id: "aura", event_type: "provider_failover", occurred_at: "2026-10-26T10:00:00Z", sequence: 1, data: { kind: "stt", from_provider: "sarvam_voice", to_provider: "text_mode" } };
    fake.handlers.data_received(new TextEncoder().encode(JSON.stringify(event)), null, null, "aria.call-event");
    expect(setMic).toHaveBeenCalledWith(false);
    await transport.disconnect();
  });

  it("reports an agent disappearing and releases the call only once", async () => {
    const transport = new LiveKitTransport();
    const onStatus = vi.fn();
    transport.onStatus(onStatus);
    await transport.connect("text");
    fake.handlers.participant_disconnected({ isAgent: true });
    expect(onStatus).toHaveBeenCalledWith("error", "CONNECTION_FAILED");
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/livekit/release", expect.any(Object)));
    await transport.disconnect();
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes("/release"))).toHaveLength(1);
  });

  it("does not report a live call if the agent dies during microphone startup", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/release")) return new Response(null, { status: 204 });
      return Response.json({ ...token, voice_mode: "voice" });
    }));
    fake.onMicEnabled = () => fake.handlers.participant_disconnected({ isAgent: true });
    await expect(new LiveKitTransport().connect("voice")).rejects.toMatchObject({ code: "CONNECTION_FAILED" });
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/livekit/release", expect.any(Object)));
  });

  it("ignores unrelated participant departures and a completed agent call", async () => {
    const transport = new LiveKitTransport();
    const onStatus = vi.fn();
    transport.onStatus(onStatus);
    await transport.connect("text");
    fake.handlers.participant_disconnected({ isAgent: false });
    expect(onStatus).not.toHaveBeenCalledWith("error", expect.anything());
    const ended = { schema_version: 1, event_id: "ended-1", call_id: "call-1", tenant_id: "aura", event_type: "call_ended", occurred_at: "2026-10-26T10:00:00Z", sequence: 2, data: { transcript: [], summary: { customer_intent: "OTHER", order_id: null, resolution_status: "UNRESOLVED", policy_outcome: null, call_summary: "Call ended.", follow_up_needed: false } } };
    fake.handlers.data_received(new TextEncoder().encode(JSON.stringify(ended)), null, null, "aria.call-event");
    fake.handlers.participant_disconnected({ isAgent: true });
    expect(onStatus).not.toHaveBeenCalledWith("error", expect.anything());
    await transport.disconnect();
    expect(onStatus).not.toHaveBeenCalledWith("disconnected", undefined);
  });

  it("returns the API error code when token admission is denied", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "AUTH_REQUIRED", message: "Sign in." }, fallback_mode: "text" }, { status: 401 })));
    await expect(new LiveKitTransport().connect("voice")).rejects.toMatchObject({ code: "AUTH_REQUIRED" });
  });

  it("releases a room and identifies a denied microphone", async () => {
    fake.micFailure = true;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/release")) return new Response(null, { status: 204 });
      return Response.json({ ...token, voice_mode: "voice" });
    }));
    await expect(new LiveKitTransport().connect("voice")).rejects.toMatchObject({ code: "MIC_DENIED" });
    expect(fetch).toHaveBeenCalledWith("/api/livekit/release", expect.any(Object));
  });
});
