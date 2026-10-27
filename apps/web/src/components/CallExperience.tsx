"use client";
import React, { FormEvent, useEffect, useMemo, useReducer, useRef, useState } from "react";
import orders from "@/fixtures/test_orders.json";
import { errorForCode } from "@/lib/call/errors";
import { FakeTransport } from "@/lib/call/fakeTransport";
import { LiveKitTransport } from "@/lib/call/livekitTransport";
import { callReducer } from "@/lib/call/reducer";
import { initialCallState } from "@/lib/call/state";
import type { CallTransport, TransportStatus } from "@/lib/call/transport";
import type { CapacityResponse, TokenResponse } from "@/lib/call/protocol";
import ThemeToggle from "@/components/ThemeToggle";

const capacityLabels: Record<CapacityResponse["capacity"], string> = { voice_available: "Voice available", text_only: "Text only · demo voice credits used", busy: "Aria is busy", daily_limit_reached: "Daily demo limit reached", unavailable: "Capacity unavailable" };
const stateLabels: Record<string, string> = { idle: "Ready", requesting_token: "Connecting", connecting: "Connecting", waiting_for_agent: "Waking Aria", live: "Listening", listening: "Listening", thinking: "Thinking", speaking: "Speaking", ending: "Ending call", ended: "Ended", error: "Call needs attention" };
function percentile(values: number[], p: number) { if (!values.length) return null; const sorted = [...values].sort((a, b) => a - b); return sorted[Math.min(sorted.length - 1, Math.ceil(p * sorted.length) - 1)]; }

export default function CallExperience({ email }: { email: string }) {
  const [state, dispatch] = useReducer(callReducer, undefined, initialCallState);
  const [selectedMode, setSelectedMode] = useState<"voice" | "text">("voice");
  const [message, setMessage] = useState(""); const [wakeNotice, setWakeNotice] = useState(false); const [capacityBusy, setCapacityBusy] = useState(true);
  const transport = useRef<CallTransport | null>(null); const token = useRef<TokenResponse | null>(null); const unsubscribers = useRef<Array<() => void>>([]);
  const tokenTimer = useRef<number | null>(null); const connectTimer = useRef<number | null>(null); const wakeTimer = useRef<number | null>(null); const agentTimer = useRef<number | null>(null); const endTimer = useRef<number | null>(null); const reconnectTimer = useRef<number | null>(null); const endingSent = useRef(false); const lastCapacityFetch = useRef(0); const audioElements = useRef<HTMLAudioElement[]>([]);
  const capacityBlocked = state.capacity === "busy" || state.capacity === "daily_limit_reached";
  const latency = useMemo(() => ["stt_final_ms", "llm_first_token_ms", "tts_first_byte_ms", "end_to_end_ms"].map((key) => { const values = state.latencies.map((item) => item[key]).filter((value): value is number => typeof value === "number"); return { key, p50: percentile(values, .5), p95: percentile(values, .95) }; }), [state.latencies]);

  async function refreshCapacity(force = false) {
    if (!force && Date.now() - lastCapacityFetch.current < 5_000) return;
    lastCapacityFetch.current = Date.now(); setCapacityBusy(true);
    try { const response = await fetch("/api/capacity", { cache: "no-store" }); const value = await response.json() as CapacityResponse; if (response.ok) dispatch({ type: "CAPACITY", capacity: value.capacity }); }
    catch { dispatch({ type: "CAPACITY", capacity: "unavailable" }); }
    finally { setCapacityBusy(false); }
  }
  useEffect(() => { void refreshCapacity(true); const audioElementsForCleanup = audioElements.current; return () => { unsubscribers.current.forEach((fn) => fn()); audioElementsForCleanup.forEach((audio) => audio.remove()); void transport.current?.disconnect(); }; }, []);
  useEffect(() => { if (state.mode === "text" && state.phase === "live") setSelectedMode("text"); }, [state.mode, state.phase]);
  useEffect(() => {
    const active = ["requesting_token", "connecting", "waiting_for_agent", "live", "ending"].includes(state.phase);
    if (!active) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn);
  }, [state.phase]);
  useEffect(() => {
    if (state.phase !== "live") return;
    const timer = window.setInterval(() => dispatch({ type: "TICK" }), 1000); return () => window.clearInterval(timer);
  }, [state.phase]);
  useEffect(() => {
    if (state.phase === "waiting_for_agent") {
      setWakeNotice(false); wakeTimer.current = window.setTimeout(() => setWakeNotice(true), 8_000);
      agentTimer.current = window.setTimeout(() => { dispatch({ type: "FAIL", error: { code: "AGENT_START_TIMEOUT", message: "" } }); void transport.current?.disconnect(); }, 30_000);
      return () => { if (wakeTimer.current) window.clearTimeout(wakeTimer.current); if (agentTimer.current) window.clearTimeout(agentTimer.current); };
    }
  }, [state.phase]);
  useEffect(() => {
    if (state.phase !== "ending" || endingSent.current) return;
    endingSent.current = true;
    void transport.current?.send({ type: "end_call" }).catch(() => undefined);
    endTimer.current = window.setTimeout(() => { dispatch({ type: "END_TIMEOUT" }); void transport.current?.disconnect(); }, 10_000);
  }, [state.phase]);
  useEffect(() => {
    if (state.phase === "ended") { if (endTimer.current) window.clearTimeout(endTimer.current); void transport.current?.disconnect(); void refreshCapacity(true); }
  }, [state.phase]);

  function clearTimers() { [tokenTimer, connectTimer, wakeTimer, agentTimer, endTimer, reconnectTimer].forEach((ref) => { if (ref.current) window.clearTimeout(ref.current); ref.current = null; }); endingSent.current = false; }
  async function start(mode: "voice" | "text", fake = false) {
    if (state.phase === "requesting_token" || state.phase === "connecting" || state.phase === "live" || capacityBlocked) return;
    if (mode === "voice" && (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia)) {
      dispatch({ type: "FAIL", error: { code: "UNSUPPORTED_BROWSER", message: "" } });
      return;
    }
    clearTimers(); setWakeNotice(false); token.current = null; dispatch({ type: "START_REQUEST" });
    const current = fake && process.env.NODE_ENV !== "production" ? new FakeTransport() : new LiveKitTransport();
    transport.current = current;
    let connected = false; let tokenReceived = false; let agentActive = false;
    unsubscribers.current = [current.onEvent((event) => dispatch({ type: "EVENT", event })), current.onStatus((status: TransportStatus, detail?: string) => {
      if (status === "token_received") { tokenReceived = true; if (tokenTimer.current) window.clearTimeout(tokenTimer.current); connectTimer.current = window.setTimeout(() => { dispatch({ type: "FAIL", error: { code: "CONNECTION_FAILED", message: "" } }); void current.disconnect(); }, 20_000); }
      if (status === "connected") { connected = true; if (connectTimer.current) window.clearTimeout(connectTimer.current); if (token.current) dispatch({ type: "ROOM_CONNECTED" }); }
      if (status === "agent_active") { agentActive = true; dispatch({ type: "AGENT_ACTIVE" }); }
      if (status === "reconnecting") { dispatch({ type: "RECONNECT" }); reconnectTimer.current = window.setTimeout(() => { dispatch({ type: "FAIL", error: { code: "CONNECTION_FAILED", message: "" } }); void current.disconnect(); }, 15_000); }
      if (status === "reconnected") { dispatch({ type: "RECONNECTED" }); if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current); }
      if (status === "disconnected" && !endingSent.current) dispatch({ type: "FAIL", error: { code: "CONNECTION_FAILED", message: "" } });
      if (status === "error" && !endingSent.current) dispatch({ type: "FAIL", error: { code: detail ?? "UNKNOWN_ERROR", message: "" } });
    })];
    tokenTimer.current = window.setTimeout(() => { if (!tokenReceived) { dispatch({ type: "FAIL", error: { code: "VOICE_UNAVAILABLE", message: "" } }); void current.disconnect(); } }, 10_000);
    try {
      const received = await current.connect(mode); token.current = received;
      dispatch({ type: "TOKEN_RECEIVED", mode: received.voice_mode, maxCallSeconds: received.max_call_seconds, fallbackReason: received.fallback_reason });
      if (connected) dispatch({ type: "ROOM_CONNECTED" });
      if (agentActive) dispatch({ type: "AGENT_ACTIVE" });
      setSelectedMode(received.voice_mode);
    } catch (error) {
      const code = error && typeof error === "object" && "code" in error && typeof error.code === "string" ? error.code : "VOICE_UNAVAILABLE";
      dispatch({ type: "FAIL", error: { code, message: "" } });
    } finally { if (tokenTimer.current) window.clearTimeout(tokenTimer.current); }
  }
  async function end() { if (state.phase === "live" || state.phase === "waiting_for_agent") dispatch({ type: "END_REQUEST" }); else { await transport.current?.disconnect(); dispatch({ type: "END_TIMEOUT" }); } }
  async function submitMessage(event: FormEvent) { event.preventDefault(); const text = message.trim(); if (!text) return; setMessage(""); try { await transport.current?.send({ type: "text_input", text }); } catch { dispatch({ type: "FAIL", error: { code: "TEXT_MODE_TURN_FAILED", message: "" } }); } }
  async function signOut() { await fetch("/api/auth/signout", { method: "POST" }); window.location.assign("/login"); }
  async function exportText() { const text = state.transcript.map((turn) => `${turn.speaker === "assistant" ? "Aria" : "Customer"}: ${turn.text}${turn.interrupted ? " [interrupted]" : ""}`).join("\n"); download("aria-transcript.txt", text); }
  function download(name: string, content: string) { const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" })); const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click(); URL.revokeObjectURL(url); }
  const statusLabel = state.reconnecting ? "Reconnecting" : wakeNotice ? "Waking Aria · this can take up to 20 seconds" : state.phase === "live" ? stateLabels[state.agentState.toLowerCase()] : stateLabels[state.phase] ?? state.phase;
  const friendlyError = state.error ? errorForCode(state.error.code) : null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-signal" aria-hidden="true" />
          <span className="brand-line"><span className="brand-name">ARIA</span><span className="brand-divider">{"//"}</span><span className="brand-product">VOICE CX</span></span>
          <span className="topbar-caption">AURA SKINCARE · EVALUATOR DEMO</span>
        </div>
        <div className="topbar-actions">
          <span className="user-chip">Signed in as {email}</span>
          <ThemeToggle />
          <button className="button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <main className="console-shell">
        <div className="workspace-grid">
          <aside className="session-rail" aria-label="Call controls and test orders">
            <section className="panel session-panel" aria-labelledby="session-title">
              <div className="panel-heading">
                <div><p className="eyebrow">LIVE SESSION</p><h1 id="session-title">Aura support</h1></div>
                <span className="state-pill" data-phase={state.phase} aria-live="polite">{statusLabel}</span>
              </div>
              {state.phase === "live" && <div className="session-clock">{Math.floor(state.elapsedSeconds / 60)}:{String(state.elapsedSeconds % 60).padStart(2, "0")} elapsed · {Math.max(0, state.maxCallSeconds - state.elapsedSeconds)}s left</div>}
              {state.phase === "live" && state.maxCallSeconds - state.elapsedSeconds <= 30 && <p className="notice">This demo call ends in {Math.max(0, state.maxCallSeconds - state.elapsedSeconds)} seconds.</p>}

              <div className="capacity-block">
                <span className="eyebrow">DEMO CAPACITY</span>
                <span className={`capacity-chip ${state.capacity === "voice_available" ? "available" : state.capacity === "text_only" ? "text-only" : ""}`} aria-live="polite">
                  {capacityBusy ? "Checking capacity…" : capacityLabels[state.capacity]}
                </span>
              </div>

              <div className="mode-switch" role="group" aria-label="Conversation mode">
                <button className={`button ${selectedMode === "voice" ? "selected" : ""}`} disabled={state.phase !== "idle" && state.phase !== "error"} onClick={() => setSelectedMode("voice")}>Voice</button>
                <button className={`button ${selectedMode === "text" ? "selected" : ""}`} disabled={state.phase !== "idle" && state.phase !== "error"} onClick={() => setSelectedMode("text")}>Text</button>
              </div>

              <div className="call-controls">
                <div className="button-row">
                  <button className="button primary" disabled={capacityBlocked || (state.phase !== "idle" && state.phase !== "error" && state.phase !== "ended")} onClick={() => void start(selectedMode)}>Start call</button>
                  <button className="button danger" disabled={state.phase === "idle" || state.phase === "ended" || state.phase === "error"} onClick={() => void end()}>End call</button>
                </div>
                {process.env.NODE_ENV !== "production" && <button className="button" disabled={state.phase !== "idle" && state.phase !== "error" && state.phase !== "ended"} onClick={() => void start("text", true)}>Run scripted demo</button>}
                <button className="button" onClick={() => void refreshCapacity(true)}>Refresh capacity</button>
              </div>

              <div className="notice"><strong>Privacy and demo notice.</strong> Aria is an AI assistant and calls are transcribed. Demo orders are fictional; do not share real personal details. Headphones work best because speaker echo can interrupt Aria.</div>
              {state.textFallbackReason && <p className="fallback" role="status">Voice is unavailable; Aria is continuing in text mode through the same support system.</p>}
              {friendlyError && <div className="notice error" role="alert"><strong>{friendlyError.message}</strong><p>{friendlyError.action}</p>{state.error?.code === "MIC_DENIED" || state.error?.code === "NO_MICROPHONE" || state.error?.code === "UNSUPPORTED_BROWSER" || state.error?.code === "AGENT_START_TIMEOUT" ? <button className="button" onClick={() => { dispatch({ type: "RESET" }); setSelectedMode("text"); void start("text"); }}>Continue in text mode</button> : null}</div>}
            </section>

            <section className="panel order-panel" aria-labelledby="orders-title">
              <div className="panel-heading"><div><p className="eyebrow">REFERENCE RECORDS</p><h2 id="orders-title">Test orders</h2></div></div>
              <p className="subtle" style={{ padding: "0 16px", marginBottom: 6 }}>Fictional demo records for Aria&apos;s order tools.</p>
              <div className="order-list">
                {orders.map((order) => <div className="order" key={order.order_id}>
                  <div className="order-title"><strong>{order.order_id}</strong><button className="button copy-id" onClick={() => void navigator.clipboard?.writeText(order.order_id)}>Copy ID</button></div>
                  <p><strong>{order.customer}</strong><br />{order.product}</p>
                  <p>₹{order.value_inr} · {order.status}<br /><span className="subtle">{order.notes}</span></p>
                  <button className="button" onClick={() => setMessage(order.try_saying)}>{order.try_saying}</button>
                </div>)}
              </div>
            </section>
          </aside>

          <section className="conversation-column" aria-label="Aria conversation">
            <article className="panel conversation-panel">
              <header className="panel-heading">
                <div><p className="eyebrow">CONVERSATION STREAM</p><h2>Transcript</h2><p className="subtle">Turns appear here as Aria and the evaluator speak.</p></div>
                {state.phase === "live" && <span className="state-pill" data-phase="live">{state.mode === "text" ? "TEXT SESSION" : "VOICE SESSION"}</span>}
              </header>
              <div className="transcript" role="log" aria-live="polite" aria-label="Call transcript">
                {state.transcript.length === 0 ? <p className="subtle transcript-empty">Start a call to see the transcript.</p> : state.transcript.map((turn, index) => <div className={`turn ${turn.speaker}`} key={`${turn.turn_id}-${index}`}><strong>{turn.speaker === "assistant" ? "Aria" : "You"}{turn.interrupted ? " · interrupted" : ""}</strong>{turn.text}</div>)}
              </div>
              {state.tools.length > 0 && <div className="tool-list" aria-label="Tools used">{state.tools.map((tool, index) => <span className="chip" key={`${tool.toolName}-${index}`}>{tool.label}</span>)}</div>}
              {state.phase === "live" && state.mode === "text" && <form className="chat-form" onSubmit={submitMessage}><label className="visually-hidden" htmlFor="message">Message Aria</label><input id="message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} placeholder="Type a message to Aria" /><button className="button primary">Send</button></form>}
            </article>
          </section>

          <aside className="inspector-rail" aria-label="Call summary and diagnostics">
            {state.summary ? <article className="panel summary-panel">
              <div className="panel-heading"><div><p className="eyebrow">POST-CALL</p><h2>Call summary</h2></div></div>
              <p className="summary-copy">{state.summary.call_summary}</p>
              <div className="summary-meta"><span className="chip">{state.summary.customer_intent.replaceAll("_", " ")}</span><span className="chip">{state.summary.resolution_status.replaceAll("_", " ")}</span>{state.summary.order_id && <span className="chip">{state.summary.order_id}</span>}</div>
              {state.summary.follow_up_needed && <p className="summary-followup">A support team follow-up is needed.</p>}
              <div className="call-controls"><button className="button" onClick={() => download("aria-summary.json", JSON.stringify(state.summary, null, 2))}>Download summary JSON</button><button className="button" onClick={() => void exportText()}>Download transcript</button><button className="button primary" onClick={() => { clearTimers(); token.current = null; dispatch({ type: "RESET" }); void refreshCapacity(true); }}>Start new call</button></div>
              <details><summary className="subtle">View summary JSON</summary><pre>{JSON.stringify(state.summary, null, 2)}</pre></details>
            </article> : <article className="panel">
              <p className="eyebrow">POST-CALL</p><h2>Summary appears here</h2><p className="inspector-placeholder">When the call ends, Aria&apos;s intent, outcome, and follow-up status will be shown in this panel.</p>
            </article>}

            <details className="panel dev-panel">
              <summary>Developer diagnostics</summary>
              <div className="dev-content">
                <p className="subtle">Export contains transcript and event data, but no auth tokens, provider keys, or IP address.</p>
                <table><thead><tr><th>Latency</th><th>p50</th><th>p95</th></tr></thead><tbody>{latency.map((item) => <tr key={item.key}><td>{item.key}</td><td>{item.p50 ?? "—"} ms</td><td>{item.p95 ?? "—"} ms</td></tr>)}</tbody></table>
                <p className="subtle">Provider failovers: {state.events.filter((event) => event.event_type === "provider_failover").length}</p>
                <button className="button" onClick={() => download("aria-diagnostics.json", JSON.stringify({ phase: state.phase, mode: state.mode, transcript: state.transcript, tools: state.tools, latencies: state.latencies, events: state.events }, null, 2))}>Export diagnostics</button>
                <pre>{JSON.stringify(state.events.slice(-20), null, 2)}</pre>
              </div>
            </details>
          </aside>
        </div>
      </main>
    </div>
  );
}
