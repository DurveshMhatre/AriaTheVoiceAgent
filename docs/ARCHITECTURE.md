# Architecture

## Call flow

`Evaluator login -> Next.js token route -> quota reservation -> short-lived, microphone-only LiveKit token -> WebRTC room -> LiveKit Agent -> Sarvam realtime STT -> Brain/LLM/tools/guardrails -> Sarvam Bulbul v3 TTS -> WebRTC audio`

The worker resolves the configured Gemini 3 model candidates against the models available to its key and requiring content generation, then configures Groq as the LLM failover. It buffers a provider response until the turn succeeds, so a failed partial turn is not replayed to the customer. If Sarvam STT/TTS fails or the TTS cap is reached, it closes the voice session and accepts text over the room data channel through the same Brain state.

Before issuing a token, the Node route verifies a Supabase authenticated, email-confirmed evaluator, hashes the request IP, and reserves one bounded call through a service-only database RPC. Reservations enforce concurrency, daily-per-IP and per-minute caps, and monthly agent/STT/TTS limits. At call end the worker reconciles actual capped usage in a single RPC call. The tables deny browser roles access and have RLS enabled.

At call end: `transcript + call state -> summary validation/fallback -> one batched Supabase write + one usage-counter update`.

Orders and tenant configuration are loaded from code/YAML behind interfaces. They are not read from the database during the demo.

## Failure modes

| Failure | Safe behavior |
|---|---|
| Provider unavailable | Circuit breaker skips it during cooldown and tries the next configured provider. |
| Voice quota exhausted | Stop starting real voice and visibly switch to text mode. |
| Mumbled audio | Ask for repetition; after three unclear turns offer escalation. |
| Unknown order ID | Ask the customer to repeat or verify; never guess; offer escalation after two failures. |
| Microphone denied | Explain how to enable it and offer text mode. |
| Unknown fact | Say the information is unavailable and offer support follow-up; never invent. |

If real Sarvam STT fails or its quota is exhausted, the voice session must show a clear explanation and offer text mode using the same Brain. The fallback does not silently retry against an unapproved paid provider. Mock STT is for development, CI, and evals.

The text fallback accepts client messages on `aria.client-message`. `aria.call-event` carries transcript, state, tool, latency, failover, error, and final call events. Phase 3 provides the authenticated widget, event reducer, LiveKit/fake transports, and a post-call summary that works without the database. See `docs/PROTOCOL.md`.

## Supabase request budget per session

| User/session action | Supabase requests | Notes |
| --- | ---: | --- |
| Sign in | 1 Auth API request | Email/password; magic link is secondary and subject to the built-in sender limit. |
| Load protected call page | 1 Auth API validation, 1 coarse capacity RPC | `getUser()` validates the user; capacity is cached for up to 30 seconds. |
| Start a call | 1 Auth API validation, 1 rate-limit RPC, 1 admission RPC | Each route validates the session. The admission RPC atomically reserves capacity and checks monthly limits. |
| End/abort before worker completion | 1 Auth API validation, 1 owner-bound release RPC | Safe and idempotent. |
| Worker call end | 1 usage-completion RPC | Records actual capped usage once. The worker also publishes the final transcript and summary over LiveKit. |
| After a call | 1 capacity RPC | Refresh once after end, no polling or realtime subscription. |
| Manual capacity refresh | 1 capacity RPC | UI debounce is 5 seconds; server returns a 30-second private cache hint. |

There is no per-turn database write and no capacity polling. Phase 4 will add one batched call-end write for calls, turns, tool calls, and summary; it will not change this per-turn budget.

## Auth email and hosting constraints

Supabase's built-in email sender is limited to team addresses and a low shared rate limit, so it is for team-only development. Configure custom email delivery before enabling evaluator sign-up, verification, or other mail-dependent flows for external addresses. A pre-created verified evaluator account can still sign in. A standby SMTP provider needs an explicit routing/failover mechanism such as Supabase Send Email Hook; storing SMTP settings alone does not provide failover.

Vercel Hobby is for the personal, non-commercial version of this project. Commercial showcases are out of scope. If that changes, re-check the current terms and select a compliant host and plan before deployment. Keep the application portable.

Production customer verification would use OTP to the registered phone. OTP is not implemented in this assessment.
