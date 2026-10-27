# Architecture Decision Records

## ADR-001: Cascaded pipeline
**Context:** The product needs inspectable text, guardrails, tools, and swappable Indian-language providers.
**Decision:** Use streaming STT → LLM with tools → TTS.
**Alternatives:** Native speech-to-speech; batch processing.
**Consequences:** More observable seams and provider code, but stronger testing and policy enforcement.

## ADR-002: LiveKit Agents on LiveKit Cloud
**Context:** Voice sessions are long-lived and need WebRTC, turn handling, and interruptions.
**Decision:** Use LiveKit Agents Python on the free Build plan.
**Alternatives:** Serverless audio worker; self-hosted media server.
**Consequences:** Free quotas and cold starts require metering and visible failure states.

## ADR-003: Brain/Voice split
**Context:** Business logic must be testable without audio credits.
**Decision:** Keep a pure text Brain separate from LiveKit voice I/O.
**Alternatives:** Put policy in the audio worker.
**Consequences:** A little more interface design, but text evals and future channels are cheap.

## ADR-004: Provider adapters and fallbacks
**Context:** Free quotas are scarce and providers change.
**Decision:** Use typed provider interfaces, mocks, ordered fallbacks, and circuit breakers.
**Alternatives:** Hard-code one provider.
**Consequences:** More setup now, safer demos and easier substitutions later.

## ADR-005: Supabase RLS and minimal writes
**Context:** Data is multi-tenant-ready but free quotas are limited.
**Decision:** Use RLS and one batched call-end write plus one counter update; orders/config remain code/YAML.
**Alternatives:** Per-turn writes or a separate database.
**Consequences:** Lower quota use and simpler Brain; less live persistence during a call.

## ADR-006: Metering and caps
**Context:** Build has hard limits and provider quotas are variable.
**Decision:** Cap calls at 300 seconds, idle at 45 seconds, concurrency at 4, and user calls per day by config. Switch to text when voice quota is exhausted.
**Alternatives:** Rely on provider errors.
**Consequences:** Graceful demo behavior instead of silent quota failure.

## ADR-007: Vercel Hobby assessment hosting
**Context:** The project needs a public web URL at $0 for personal, non-commercial showcasing.
**Decision:** Use Vercel Hobby for the personal, non-commercial version of this project, without Vercel-only storage/KV/edge features. Commercial showcases are out of scope; re-check terms before any scope change.
**Alternatives:** Cloudflare Pages; Netlify.
**Consequences:** The app stays portable. If the project later becomes commercial, choose a host and plan that comply with the then-current terms.

## ADR-008: Sarvam plugin and `saaras:v3`
**Context:** The official LiveKit plugin minimizes custom realtime code.
**Decision:** Use the official plugin with `saaras:v3`; keep `saaras:v3-realtime` disabled behind a flag.
**Alternatives:** Custom WebSocket client; beta realtime endpoint.
**Consequences:** Fewer moving parts; Phase 2 must verify current plugin parameters.

## ADR-009: Gemini candidate resolution
**Context:** Model IDs and availability change quickly.
**Decision:** Resolve `gemini-3.1-flash-lite`, then `gemini-3.5-flash`, at startup based on tool-calling support; Groq is failover.
**Alternatives:** One hard-coded model; 2.x or preview IDs.
**Consequences:** Startup discovery is required; no unsupported model is silently selected.

## ADR-010: Auth and evaluator access
**Context:** Public anonymous calls could exhaust free quotas.
**Decision:** Require Supabase email/password verification or magic link, plus a pre-created demo evaluator account. Keep the built-in email sender for team-only development; configure custom email delivery before external sign-up or verification is needed.
**Alternatives:** Anonymous access; third-party auth.
**Consequences:** Safer quotas, but Phase 3 must handle evaluator onboarding.

## ADR-011: Text fallback
**Context:** Voice quotas may run out during evaluation.
**Decision:** Make Voice/Text a first-class toggle and visibly switch to text on quota exhaustion.
**Alternatives:** Fail the entire demo.
**Consequences:** Evaluators can still test the Brain without audio.

## ADR-012: Identity seam
**Context:** Order-ID-only lookup is acceptable for this fictional demo but not production.
**Decision:** Keep `verified: false`; document OTP as future work.
**Alternatives:** Pretend evaluator login verifies the customer.
**Consequences:** Honest demo privacy boundary.

## ADR-013: Contact placeholders
**Context:** No real Aura support details were supplied.
**Decision:** Keep email, phone, URL, and speaker contact values as `PLACEHOLDER`; never speak them.
**Alternatives:** Invent details; use personal details.
**Consequences:** Follow-up is recorded as a ticket without a fabricated channel.

## ADR-014: Policy literal threshold
**Context:** The specification says free shipping is above ₹499, making exactly ₹499 charged.
**Decision:** Implement the literal `above` rule and flag the ambiguity.
**Alternatives:** Interpret “above” as at-or-above.
**Consequences:** Tests will make the chosen behavior explicit.

## ADR-015: Phase 1 contract amendments
**Context:** The Brain must distinguish order-record evidence from customer claims, damage cases, confirmation failures, and escalation reasons.
**Decision:** Extend tool results and summary outcomes while keeping schema version 1.
**Alternatives:** Return a bare boolean or free-text reason.
**Consequences:** The Brain can explain missing evidence safely, and contract conformance tests become more important.

## ADR-016: Order confirmation gate
**Context:** An evaluator login does not verify the customer named by an order ID.
**Decision:** Candidate IDs must be confirmed before order lookup, cancellation, or order-based eligibility checks.
**Alternatives:** Trust the first normalized ID.
**Consequences:** One extra conversational turn prevents accidental disclosure and guessing.

## ADR-017: Provider-neutral messages and streaming seam
**Context:** Gemini and Groq represent tool-call turns differently, while Phase 2 needs sentence streaming and interruption support.
**Decision:** The Brain uses internal message/tool/result types and exposes an async event stream; adapters retain vendor-specific fields privately.
**Alternatives:** Put SDK response objects in Brain state.
**Consequences:** Adapter code is more explicit, but provider changes do not rewrite policy code.

## ADR-018: Scripted-first test strategy
**Context:** Real quotas are scarce and model behavior is nondeterministic.
**Decision:** CI uses scripted MockLLM scenarios; live evals are manual, capped, and never golden by default.
**Alternatives:** Run live calls in CI.
**Consequences:** CI proves plumbing and guardrails, not current model quality.

## ADR-019: Python tooling
**Context:** The Brain is Python and must remain understandable for a solo developer.
**Decision:** Python 3.12 with pinned pytest, pytest-cov, Ruff, mypy strict on `brain/`, jsonschema, and PyYAML.
**Alternatives:** Unpinned dependencies or a larger framework.
**Consequences:** Reproducible local checks, with dependency updates requiring an explicit research pass.

## ADR-020: Lazy provider adapters
**Context:** Provider SDKs change independently and free-tier credentials may be absent in local development.
**Decision:** Keep Gemini and Groq imports lazy, resolve configured candidates at startup, and expose only provider-neutral Brain events. Vendor response metadata remains inside adapters.
**Alternatives:** Import all SDKs at module import time or bind Brain to one SDK.
**Consequences:** Mock mode works without provider packages or keys; real-mode compatibility must be checked against the pinned SDK and official docs.

## ADR-021: Sarvam STT selection and voice failure fallback
**Context:** Phase 2 needs a documented Sarvam configuration and a path that keeps Aria available when real voice STT is unavailable without exceeding the $0 constraint.
**Decision:** Use the official LiveKit Sarvam Python plugin and explicitly configure `sarvam.STT(model="saaras:v3", language="en-IN")`. If voice STT fails or quota is exhausted, visibly switch the user to text mode and continue through the same Brain. Use mock STT in development, CI, and evals. Select an exact plugin version before implementation that passes the repository's two-week release-age rule; the currently latest 1.8.8 is too new to pin today. Do not select another metered provider until its free tier is verified.
**Alternatives:** Use `STTRealtime` (`saaras:v3-realtime`), which is a separate API requiring subscription access and does not auto-reconnect; add a second real provider, which needs its own free-tier and adapter review.
**Consequences:** The Brain remains usable during voice outages without an additional provider cost. Voice continuity is not preserved during fallback; the UI must explain the switch.

## ADR-022: Supabase email stage and future fallback
**Context:** The owner wants Supabase's built-in email service for the current low-volume stage and custom SMTP available as users increase.
**Decision:** Keep the built-in sender only for team-address development and testing. Before external evaluator sign-up, verification, or other mail-dependent flows, configure custom email delivery because the built-in sender is restricted to project-organization addresses and currently limited to 2 messages per hour. For automatic provider failover, evaluate Supabase Send Email Hook or an owned routing layer; a second SMTP configuration by itself is not failover.
**Alternatives:** Configure custom SMTP immediately; disable email login; use an email hook from the beginning.
**Consequences:** No SMTP credentials are added to the repository. External evaluator sign-up, verification, and other mail-dependent flows cannot work until custom email delivery is configured; a pre-created verified account can still sign in with credentials.

## ADR-023: Cross-platform timezone and JSON Schema format validation
**Context:** Running the Phase 1 checks on Windows showed that Python's standard library did not include IANA time-zone data, and `jsonschema` does not validate `date-time` format unless an RFC3339 checker is installed.
**Decision:** Pin `tzdata==2026.5` for IANA time zones on platforms without system zoneinfo, `rfc3339-validator==0.1.4` so the existing `FormatChecker` enforces JSON Schema `date-time` values, and upgrade PyYAML to 6.0.3 to satisfy LiveKit Agents 1.8.6.
**Alternatives:** Hard-code India Standard Time or silently skip date-time format validation; rely on host-specific timezone databases.
**Consequences:** Aura's injectable clock and contract checks work consistently on Windows and other platforms. These dependencies are documented in `pyproject.toml` and `RESEARCH.md`.

## ADR-024: LiveKit Agents and Sarvam plugin version pins
**Context:** Phase 2 needs compatible, current SDKs while respecting the repository's two-week release-age hold.
**Decision:** Pin `livekit-agents==1.8.6` and `livekit-plugins-sarvam==1.8.6`. Both were released on 2026-10-09, support the repository's Python 3.12 runtime, and were published from the same LiveKit release commit. Versions 1.8.7 and later were too recent on the selection date.
**Alternatives:** Pin the newest 1.8.9/1.8.8 pair; use the older 1.8.4 pair.
**Consequences:** Avoids very recent changes while retaining the new Sarvam realtime API. Re-check release dates and docs before dependency upgrades.

## ADR-025: Sarvam realtime STT with same-Brain text fallback
**Context:** The owner asked me to choose between Saaras v3 legacy streaming and Saaras v3 realtime for the new Python voice agent. The project targets low response latency but must stay within free credits.
**Decision:** Use LiveKit's `sarvam.STTRealtime` (fixed model `saaras:v3-realtime`) with `language="en-IN"`, `stream_type="fast"`, and server VAD. If realtime access is unavailable, the socket fails, or quota is exhausted, emit a provider-failover event and visibly switch to text mode on the same Brain. Do not auto-reconnect or silently fall through to a second metered provider. Keep `sarvam.STT(model="saaras:v3")` as a configuration-selectable legacy option for diagnostics only, not an automatic paid fallback.
**Alternatives:** Use legacy `saaras:v3`, which emits only final transcripts; silently reconnect or retry against another paid provider.
**Consequences:** Realtime partial transcripts and server-side VAD support the conversational latency target. The API requires Sarvam realtime access, is billed, and does not reconnect automatically; first real use must be manually capped within the verified ₹100 free credit, and text mode remains available when voice is unavailable. This supersedes the earlier STT choice in ADR-008/ADR-021 and the D2 amendment in `AGENTS.md`, by the owner's explicit delegation on 2026-10-25.

## ADR-026: Runtime LLM resolution and complete-turn failover
**Context:** Phase 2 needs the approved Gemini model list to follow key availability and must keep Brain tool calls working if a provider fails mid-response.
**Decision:** At real-worker startup, list Gemini models for the configured key, keep only the approved Gemini 3 candidates that are available and support `generateContent` (the approved candidates support function calling), then add Groq as the next route. Buffer each candidate's output until its entire response succeeds; discard a partial failed attempt before trying the next route. Emit `provider_failover` when the route changes. Do not use preview or Gemini 2.x IDs.
**Alternatives:** Hard-code one Gemini model; retry a failed partial stream after already exposing its text or tool call.
**Consequences:** Startup checks model inventory without generating tokens. The first provider's complete response is buffered before the Brain consumes it; this preserves safe retries but does not stream provider output directly to speech.

## ADR-027: Token admission and text-mode quota fallback
**Context:** The Phase 2 endpoint must keep a call within free service limits before issuing LiveKit access, while the browser widget arrives in Phase 3.
**Decision:** The Node route authenticates a confirmed Supabase user, hashes the IP with a server-only HMAC key, then reserves capacity through service-role-only Postgres RPCs. Admission applies 4 concurrent calls, 5 calls/IP/UTC day, 5 token requests/IP/minute, 300 seconds/call, 7,200 monthly LiveKit-agent seconds, 7,200 Sarvam STT seconds, 10,000 TTS characters, and 2,500 TTS characters/call. If only the Sarvam monthly cap is exhausted, issue a data-only token for the same Brain over `aria.text-input`; if the LiveKit application cap is exhausted, refuse a new room clearly. Reconcile reservations once at call end.
**Alternatives:** Issue unrestricted tokens and meter afterward; return an unavailable error for every provider quota condition.
**Consequences:** Quota checks are atomic in the database and browser credentials remain minimally privileged. The migration must be applied before tokens can be issued; Phase 3 renders the returned text-mode reason and events.

## ADR-028: Browser transport boundary and deterministic fake transport
**Context:** The browser must support local demonstrations and real LiveKit rooms without coupling the call-state UI to one SDK or making fake access available in production.
**Decision:** Define `CallTransport` with connect, disconnect, send, event/status subscription, and microphone controls. Use `LiveKitTransport` for real rooms and a scripted `FakeTransport` only when `NODE_ENV` is not production. Both publish into the same reducer and protocol event types.
**Alternatives:** Put LiveKit client logic in UI components; use a fake browser-only UI unrelated to the real room protocol.
**Consequences:** Reducer and component tests run without account credentials or provider credits. Fake transport is rejected in production and does not count as a real voice test.

## ADR-029: Versioned browser/worker protocol and database-independent end event
**Context:** The Phase 3 post-call screen needs a transcript and summary even before Phase 4 persistence exists.
**Decision:** Use JSON Schemas for client messages, API errors, capacity, token responses, and call events. The worker reliably publishes one final `call_ended` event containing transcript and deterministic summary before room teardown. The browser reducer deduplicates event IDs and sorts by sequence.
**Alternatives:** Read post-call data from the database; reconstruct final state from non-final events.
**Consequences:** Local post-call UX works without database persistence. Phase 4 must preserve these contract shapes when it adds the batched call-end write.

## ADR-030: Evaluator authentication and protected route checks
**Context:** Anonymous public calls could exhaust free provider quotas, and a middleware redirect alone is not an API authorization boundary.
**Decision:** Disable signup, require a pre-created confirmed evaluator, use email/password as primary login and team-address-only magic link as secondary, validate identity with Supabase `getUser()` in each protected page/API handler, and keep the service-role key server-only.
**Alternatives:** Anonymous calls; rely only on middleware; enable public signup using the built-in sender.
**Consequences:** The owner must create the evaluator account in the dashboard. External magic-link delivery needs the approved future SMTP setup.

## ADR-031: Report-only nonce CSP and Node route handlers
**Context:** The app needs browser security headers while preserving Next's nonce handling and remaining portable to a later host.
**Decision:** Add a fresh nonce and a restrictive CSP to forwarded request headers for Next rendering, return the same policy as `Content-Security-Policy-Report-Only`, and add frame, content-type, referrer, and microphone permission headers. API routes use the Node runtime; no Server Actions, `next/image`, `next/og`, or host-specific storage are used.
**Alternatives:** Enforce CSP before the deployed domain's report behavior is reviewed; use server actions or Edge-specific APIs.
**Consequences:** CSP violations are observable without blocking the assessment UI. Enforce CSP after validating the deployed origins during Phase 5.

## ADR-032: Owner-bound release and reservation expiry
**Context:** Browser cancellation or a crash between reservation and worker start can leak a concurrency slot.
**Decision:** Add a new migration with an evaluator ID on admission and an owner-bound release RPC. Client end/abort uses that RPC; worker completion finalizes usage; an abandoned reservation expires after 15 minutes, which is the 5-minute call cap plus a 10-minute margin. The applied Phase 2 migration remains immutable.
**Alternatives:** Allow the browser to release any call ID; edit the applied migration; rely on worker startup to release every reservation.
**Consequences:** The release route requires a validated signed-in user and SQL restricts the RPC to `service_role`. The owner applies and verifies the additive migration manually.
