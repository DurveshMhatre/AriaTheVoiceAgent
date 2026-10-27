Phase 2 code is approved. Start **Phase 3: the web widget.** Follow `AGENTS.md` and its amendments. Phase 3 delivers the browser experience and closes the Phase 2 gate. **Do not add voice-pipeline features, database persistence (Phase 4) or deployment (Phase 5).** Worker changes are allowed only to fix protocol gaps or bugs found by the UI or the real call, each with an ADR and tests. Every command you give me must run in Windows PowerShell.

### 1. Binding decisions (answers to the open gate items)

| # | Item | Decision |
| --- | --- | --- |
| G1 | Supabase migration | I apply it myself in the Supabase dashboard SQL Editor (no CLI install). You write `docs/RUNBOOK_SUPABASE.md`: a plain-English review of `202610250001_phase2_voice_admission.sql`, exact click-by-click steps, one verification query and its expected output. Review checklist: RLS on every table; no direct table access for `anon` or `authenticated`; admission functions executable only by the service role; any `SECURITY DEFINER` function sets a fixed `search_path`; **every slot-release path** (normal end, client abort, worker crash, never connected) with a reservation TTL no longer than the call cap plus a margin. Amend the migration if the TTL is missing, as a new migration file, never by editing the applied one. |
| G2 | `IP_HASH_SECRET` | I generate it locally and put it only in `.env`. You give me the PowerShell command. It must use a cryptographic random source, and I never paste the value into chat. `check_env.py` verifies presence and length of at least 32 characters, never the value. `.env.example` lists every cap variable with its default. |
| G3 | Model and STT settings | `LLM_MODEL_CANDIDATES=gemini-3.1-flash-lite,gemini-3.5-flash`, `STT_MODEL=saaras:v3-realtime`, `SARVAM_REALTIME_ENABLED=true`. If startup resolution rejects every candidate, stop and report. Do not add models without a reviewed ADR. |
| G4 | Next.js security | Do not deploy 15.5.27. Mitigations now: **no Server Actions anywhere** (route handlers and client fetch only); `images.unoptimized = true`; no `next/image` and no `next/og`; `poweredByHeader: false`. Upgrade to **15.5.28** on or after 2026-10-29 as a separate commit, then run `npm audit` with registry access (ask me to run it if your network cannot), and review the React advisory for patched `react`/`react-dom` versions. Read all three advisories from the official post and record them in `RESEARCH.md`. If I tell you the submission deadline is earlier than 2026-10-29, I may waive the age hold for this one patch. Before using it, verify provenance (npm provenance, matching GitHub release tag, changelog review). |
| G5 | Auth | Supabase Auth with the built-in email sender for now. **Public sign-up disabled.** Email + password is the primary sign-in. Magic link is secondary and works only for team addresses, so label it honestly. A **demo evaluator account** is created by me in the dashboard (auto-confirmed, no email needed), and its password is shared only in the submission email, never in the repo or UI. Custom SMTP stays a documented future step. |
| G6 | Real-call test | One manual call after the UI exists: five minutes maximum, one concurrent call. Follow `docs/RUNBOOK_REAL_CALL.md` (section 8). If `saaras:v3-realtime` is rejected for account access, propose adding the legacy `sarvam.STT` (`saaras:v3`, same vendor, same credits) as the second STT in the chain, via ADR, before settling for text mode. |
| G7 | Browser voice fallback | Optional, built last (section 9), only after acceptance criteria 1 to 8 pass. |
| G8 | Python runtime | Fresh Python 3.12 virtual environment with all pinned dependencies. If 3.12 is not installed, tell me exactly what to download. |
| G9 | Hosting | Local only in Phase 3. The app must still be deployable to Vercel Hobby later: Node route handlers (not Edge), no Vercel-only features. |

### 2. Task 0: close the Phase 2 gate and Phase 1 debt (one commit each)

Items 3 and 4 need my hands. Do not wait for them: continue with items 1, 2, 5 and 6 and then build the UI against the fake transport (section 4).

1. **Clean environment run.** Create the venv, install pinned dependencies, then run the **entire** suite including the voice tests, plus `ruff`, `mypy`, the contract validator and the scripted evals. Put the full outputs in `PROGRESS.md`.
2. **Next.js mitigations** from G4.
3. **Migration review and runbook** (G1). Stop and ask me to confirm that I applied it and that the verification output matches.
4. **Environment readiness** (G2, G3). I fill `.env`, then you run `check_env.py`.
5. **Phase 1 debt.** Raise coverage to at least 95% on `ids`, `policy`, `guardrails` and `state`, and at least 85% overall. Show the per-module table. Then run **one capped live eval** (`LIVE_EVAL_MAX_CALLS` 80, `--llm auto`) and report pass or fail per scenario and assertion, time-to-first-token p50 and p95, and the quota ledger. Include 5 live CLI transcripts (ORD-101 tracking, day-20 opened return without an order ID, cancel ORD-103 with confirmation, unknown ID, flight to Goa). Save no golden files without my approval.
6. **CI web job.** Install, lint, typecheck, test, build with **canary secret values** (unique fake strings), then verify that none of them appear in the client bundle. Run `npm audit --audit-level=high`. Keep it non-blocking until the 15.5.28 upgrade commit, with a dated TODO, then make it blocking.

### 3. Protocol first

Read the worker and token endpoint code, then write `docs/PROTOCOL.md` covering: token request and response, data-channel topics (`aria.call-event` carries `call_events` contract objects), client-to-worker messages, the agent-state signal, voice versus text mode, and what `call_ended` carries.

- Add JSON Schemas for anything missing: `client_message`, `token_response`, `capacity_response`, and an `api_error` shape with a closed enum of error codes. Add valid and invalid samples, and extend the validator.
- The post-call view must work **without the database**. If `call_ended` does not already carry the final transcript and summary, change the worker to publish one reliable final event with both before it closes the room (ADR plus tests).
- Write a table mapping every admission or API error code to a friendly message and a next action (for example, concurrency limit: 'Aria is busy, try again in a minute'; IP daily limit; token rate limit; monthly cap: offer text mode; unauthenticated: go to login). Use the real codes from the code and migration.

### 4. Web architecture

```
apps/web/src/
  app/  login/  auth/callback/  call/  api/livekit/token/  api/capacity/   (route handlers only)
  lib/call/  state.ts  reducer.ts  protocol.ts  errors.ts  transport.ts  livekitTransport.ts  fakeTransport.ts
  lib/auth/  components/  fixtures/test_orders.json
```

- **Transport interface.** `CallTransport` hides LiveKit behind `connect`, `disconnect`, `send`, `onEvent`, `setMic`. `LiveKitTransport` is the real one. `FakeTransport` replays scripted event sequences. It is enabled only when `NODE_ENV` is not production. No auth-bypass flags anywhere.
- **Pure reducer.** Call state is derived from events: idempotent (dedupe by `event_id`), ordered by `sequence`, unknown event types ignored with a dev warning. It holds phase, agent state, mode, transcript, tool chips, per-turn latency, timers, error and summary.
- **Client state machine:**

| Phase | Entered when | Leaves when | Timeout and behaviour |
| --- | --- | --- | --- |
| `idle` | page ready | Start pressed | n/a |
| `requesting_token` | Start pressed | token received or error | 10 s, then error with retry button |
| `connecting` | token received | room joined | 20 s, then error |
| `waiting_for_agent` | room joined | agent participant active | Show 'Waking Aria up, this can take up to 20 seconds' after 8 s. At 30 s, end the call, release the slot, offer retry or text mode |
| `live` | agent active | End pressed, cap reached or disconnect | Agent sub-state from events: listening, thinking, speaking. 'Reconnecting' if the transport drops. End the call if reconnecting exceeds 15 s |
| `ending` | End pressed or cap reached | `call_ended` event or 10 s | Send `end_call`, wait for the summary, otherwise show 'Summary unavailable' with the local transcript |
| `ended` | summary or timeout | New call | Show post-call view |
| `error(code)` | any failure | Retry or Reset | Friendly message from the table in section 3 |

- Disable Start while a request is in flight. No automatic retry loops. Retry only by button.

### 5. UI specification (functional first, clean and accessible)

- **Layout:** call card (state indicator, Start and End buttons, Voice or Text toggle, mic level meter if cheap, elapsed time and cap countdown with a warning at 30 seconds left, capacity chip), transcript, and a side column with the Test Orders helper. Stacked on mobile.
- **State indicator:** Connecting, Waking Aria, Listening, Thinking, Speaking, Ended. Always text plus icon, never colour alone. Respect `prefers-reduced-motion`.
- **Transcript:** a `role=log` list of final turns with roles. Interrupted assistant turns are marked. Tool calls appear as small chips ('Looked up ORD-101: out for delivery'), because evaluators want to see function calling. Text input appears only in text mode.
- **Test Orders panel:** the three orders with ID (copy button), customer, product, value, status and notes, plus 'Try saying' chips. The panel reads from `fixtures/test_orders.json` (static strings such as 'Delivered 14 days ago', so it never goes stale). A Python test asserts the fixture matches the `OrderRepository` seeds (IDs, values, statuses).
- **Capacity chip:** Voice available, Text only (demo voice credits used), Busy, Daily limit reached. It comes from `GET /api/capacity` (authenticated, coarse states only, cached about 30 seconds on the server) and the token response.
- **Notices near Start:** Aria is an AI assistant; calls are transcribed; demo orders are fictional, so do not share real personal details; headphones work best (speaker echo can interrupt Aria).
- **Microphone:** handle denied permission, no device, and unsupported browser with clear steps and a 'Continue in text mode' button. Start audio playback inside the Start click handler so mobile Safari allows it. Warn before leaving the page during a live call.
- **Post-call view:** chronological transcript and the summary as a readable card plus raw JSON (copy button and download of JSON and plain text). 'Start new call' re-checks capacity.
- **Dev panel** (collapsed by default): event log, per-turn latency (`stt_final_ms`, `llm_first_token_ms`, `tts_first_byte_ms`, `end_to_end_ms`) with p50 and p95 for the session, failover events, and 'Export diagnostics' (no secrets, no tokens).
- **Accessibility:** native buttons, visible focus, WCAG AA contrast, `aria-live` for state changes, keyboard-complete flow.

### 6. Auth specification

- Pages: `/login` (email + password, secondary 'Email me a sign-in link' with an honest note), `/auth/callback` (code exchange; the `next` parameter must be an allow-listed relative path to prevent open redirects), and sign-out via POST.
- Friendly handling for wrong password, unconfirmed email, and email rate limit (2 per hour: 'Too many emails sent, try again later').
- **Server-side checks use `getUser()`** (validated with Supabase), not the unvalidated cookie session. Middleware may redirect, but every route handler and protected page re-checks the user itself, because middleware-only protection has failed in the past.
- Keep `SUPABASE_SERVICE_ROLE_KEY` out of any code path the browser bundle can reach.

### 7. Security and privacy

- Headers: `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`, `Permissions-Policy` allowing microphone for self only. A nonce-based CSP allowing only our origin, the Supabase project and the LiveKit project. Ship the CSP in **Report-Only** now and enforce it in Phase 5 on the real domain.
- Token endpoint: JSON-only `POST`, `Origin` check, input validation, no secrets or tokens in logs, IP only as the HMAC hash. Server logs are structured and contain no PII.
- **Bundle secret check:** build with canary values and fail if any secret-named canary appears in `.next/static`. It prints PASS or FAIL per variable name, never values.
- No third-party scripts, analytics or fonts from external hosts.

### 8. Supabase request budget and the real-call runbook

Keep a table in `docs/ARCHITECTURE.md` of database requests per session: sign-in (Auth API), one capacity read per page load, after a call ends and on a debounced manual refresh, one admission call at token request, and the worker's call-end usage update. No polling, no realtime subscriptions.

Write `docs/RUNBOOK_REAL_CALL.md` for the one real call: a pre-flight checklist (dashboard balances for LiveKit usage, Sarvam credit and Gemini limits, which I will read and paste without secrets); the commands to start the worker and the web app in PowerShell; a short script of utterances covering tracking, a policy refusal, a bad ID and an out-of-scope request; stop conditions; and what to record (dev-panel export, latency percentiles, credit consumed). Include a **credit plan**: roughly how many real-voice minutes remain, and an allocation for this test, up to 3 demo-video takes in Phase 5, and the evaluator pool. Text mode is the default for every other test.

### 9. Optional last task: browser voice fallback (G7)

Only after acceptance criteria 1 to 8 pass. When Sarvam voice is unavailable, offer 'Browser voice (basic)': `SpeechRecognition` feeds the existing text-mode path, and `speechSynthesis` speaks Aria's replies (prefer an en-IN voice). Feature-detect. Off by default. Show a notice that browser speech recognition may send audio to the browser vendor's servers, and require a click to enable. Pause recognition while Aria speaks to avoid feedback loops, and cancel speech if the customer starts talking. Write an ADR. This keeps the assessment's core 'speak and hear' flow alive when free voice credits run out.

### 10. Tests and rules

- **Unit tests (Vitest):** table-driven reducer tests (at least 40 cases: duplicates, out-of-order events, unknown events, text-mode failover, cold-start timeout, reconnect, cap countdown, interrupted turns), protocol parsing with malformed input, the error-code mapper (every code), and contract conformance of every parsed event using Ajv in test builds only. Coverage of at least 90% on reducer, protocol and errors, and 80% on `lib/`.
- **Component tests (Testing Library with `FakeTransport`):** each phase of the state machine renders correctly, with roles and labels. Recorded scenarios: tracking call, policy refusal, bad ID, text-mode failover, quota denied, mic denied.
- **Python tests** for any protocol or contract changes and the fixture cross-check.
- Test-first for the reducer, protocol and error mapper. No business rule in the UI. Dependencies pinned, at least 14 days old, one commit per step with conventional messages, no `--no-verify`, no secrets in the diff. Add ADRs for: transport abstraction, protocol contracts, auth model, the slot-leak fix if needed, security headers, and the browser fallback if built.
- Report honestly: anything unverified or flaky goes in `PROGRESS.md`.

### 11. Order of work

Task 0 (items 1, 2, 5, 6), then protocol and contracts, transport interface and reducer (test-first), `FakeTransport`, UI components, auth, capacity endpoint, security headers, `LiveKitTransport`. Then pause for my G1 and G2 confirmations (if not already done), run the real call per the runbook, then the optional browser fallback.

### 12. Acceptance criteria

1. Task 0 complete, with the full environment run, the coverage table, the live eval report and the CI web job green apart from the dated audit TODO.
2. Migration applied and verified, including the slot-release review.
3. Login works for the demo evaluator account. Signed-out users cannot reach `/call` or the APIs.
4. A full call experience works end to end on `FakeTransport` for all state-machine phases, with the dev panel.
5. Test Orders panel, capacity chip, notices, transcript with tool chips, post-call summary and JSON download all work and are keyboard accessible, checked at mobile and desktop widths.
6. Text-mode call works through the real LiveKit worker with no Sarvam credit used.
7. One real voice call completes within the runbook limits, with latency numbers and credit use recorded. If realtime STT is rejected, the outcome and the proposed fix are recorded.
8. Bundle secret check passes. No Server Actions exist in the app. `npm audit` result reported. The 15.5.28 upgrade is done or explicitly scheduled for the first date allowed.
9. If built: browser voice fallback works in Chrome or Edge with the privacy notice.

### 13. Gate report, then stop

Give me the file tree, all test and coverage outputs, the runbook results, the database request budget table, the live eval and latency numbers, the credit plan with remaining estimates, every deviation, open questions (at most 5), the exact PowerShell commands to rerun everything, and a plain-English explanation of what Phase 3 produced. Propose the Phase 4 plan (persistence of calls, turns, tool calls and summaries with one batched write at call end, plus a simple history view) and list any accounts or keys I will need. Then **wait for my approval**.

\=====
