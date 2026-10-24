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
**Context:** The assessment needs a public web URL at $0.
**Decision:** Use Vercel Hobby only for assessment deployment, without Vercel-only storage/KV/edge features.
**Alternatives:** Cloudflare Pages; Netlify.
**Consequences:** Portable app now; migrate before any commercial use or terms change.

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
**Decision:** Require Supabase email/password verification or magic link, plus a pre-created demo evaluator account; configure custom SMTP in the dashboard.
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
