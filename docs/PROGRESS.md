# Progress

## Voice-call repair plan — 2026-10-27

The owner requests a working evaluator microphone-to-speaker call and repair of the voice-to-text and message-processing errors. Preserve existing local work and the approved provider, authentication, and quota architecture; do not deploy or change account settings.

1. Reproduce provider/message and voice-session failures offline, then add regression tests before repairs. Acceptance: fragmented tool calls assemble correctly, tool results match their call IDs, and voice failures leave the same Brain usable in text mode.
2. Repair the smallest affected provider, Brain, worker, and transport paths. Check the pinned SDK APIs against official docs and retain strict policy enforcement and bounded usage.
3. Run Python, contract, deterministic eval, and web checks; start the local app and exercise browser paths. A real call requires verified evaluator login, applied admission migrations, and confirmed remaining free-provider quota. Record actual results and any blocked checks; do not claim microphone/audio success from mocks.

Status: repairs and verification in progress. Local configuration declares all required names, including `LIVEKIT_URL`; root and web env files refer to the same file, and no secret values were printed. Regressions first failed for premature Groq tool fragments, missing result IDs, leaked Gemini metadata, default text selection, microphone fallback, and Next's normalized-host origin checks. Provider/Brain repairs now pass 11 focused tests; web type/lint and 91 tests pass. Contract checks pass 32/32; deterministic evals pass 16/16 without provider calls. The authenticated browser scripted demo shows order tracking, scope redirection, live state and transcript without console errors; this is a UI/mock check, not proof of real AI or audio.

The owner confirmed remaining free LiveKit/Sarvam quota and realtime access and authorized one supervised voice call of at most five minutes. The embedded browser reports microphone permission denied and zero physical audio inputs, so automated audio testing used local, prerecorded speech through a virtual microphone; a physical microphone/speaker walkthrough remains separate. No shared account settings or quota caps were changed.

The authorized real call was admitted in voice mode and reached Sarvam realtime STT and Bulbul v3 TTS startup, but the Windows worker exited with code 3 without a Python traceback before any conversational transcript or meaningful response audio. Real voice acceptance has not passed. The browser incorrectly stayed Listening until its five-minute timeout; the room ended and its owner-bound release returned HTTP 204. Temporary microphone/fetch overrides were restored. Do not start another metered call without renewed authorization.

Offline investigation found Windows System event 2004 at 05:17:41 with only about 23 MiB of available committed memory before the failed call; this supports resource exhaustion as a possibility, not a confirmed crash cause. Synthetic MP3 decoding, PCM output, resampling and RecorderIO probes did not reproduce the failure. A separate CRT-abort control produced the same exit-code-3/no-stderr signature but does not identify the failing component. Containment plan: explicitly disable optional SDK audio recording and select supported Sarvam `linear16` output to remove compressed decoding from this call path, preserving STT/TTS providers, streaming and caps. Add offline regressions for both options and verify actual PCM frame emission without provider requests. A subsequent real call remains required to establish voice acceptance.

Browser worker-loss handling now reports a connection error, stops the microphone and releases admission without a voice retry; completed summaries and unrelated participant departures are protected. A startup-race regression also prevents microphone initialization from returning a live token after worker loss. Web typecheck/lint and all 95 tests pass. The local browser mock walkthrough verified order transcript/summary and an injected worker-loss alert without console errors. Python tests pass 71/71, contracts 32/32 and scripted evals 16/16 with zero provider calls; scoped Ruff and strict worker/provider/Brain mypy checks pass. The actual Sarvam SDK PCM stream test covers split-sample buffering, frame contents, 22,050-to-48,000 Hz native resampling and native AudioSource capture while replacing only the provider response and forbidding compressed decoder use. These checks do not establish a successful live provider call or physical speaker playback.

The isolated production build completed successfully and its browser-bundle scan passed for all six actual secret values checked. This does not remove the existing Next.js security deployment hold. This repair section supersedes older missing-env, login, migration-admission, build-stall, and no-call observations below; the authenticated token/capacity/release routes were exercised, but full migration verification remains separate.

## Current status — 2026-10-27 — Phase 3 local implementation

Phase 3 widget and local protocol work is implemented. The local unit, lint, type, coverage, and contract checks pass. **The Phase 3 gate remains open** because the owner has not confirmed the two Supabase migrations or evaluator login, `LIVEKIT_URL` is missing from the local `.env`, the production build stalls in Next.js type checking, and no authenticated browser walkthrough or live Sarvam call has been run. The app remains local and undeployed. Do not deploy the current Next.js 15.5.27 pin.

### Phase 3 plan and delivered scope

1. Protocol/contracts and worker final-event guarantee — implemented and contract-tested.
2. Authenticated server routes, capacity and owner-bound reservation release — implemented; SQL application is owner-only and pending.
3. Call transport abstraction, reducer, fake and LiveKit transports — implemented.
4. Responsive call widget, login, test-order helper, capacity status, transcript/tool chips, summary and diagnostics — implemented. The Stitch references informed the graphite/cyan/lime control-console styling, compact telemetry, and dark/light theme toggle; unsupported controls and fabricated runtime telemetry were excluded. TypeScript check passes after the UI update; no manual authenticated browser walkthrough or desktop/mobile visual inspection has occurred.
5. CI web gates and secret-canary check — added; local lint/typecheck/tests and coverage pass. The production build stalls during Next.js generated type checking. The standalone TypeScript check passes. The bundle secret-canary check has not run against a completed production build.
6. Shared environment loading — the `apps/web` npm scripts preload the repository-root `.env` through `apps/web/load-root-env.cjs` using `@next/env` before the Next CLI initializes. This makes `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` available to Auth without duplicating `.env` into `apps/web`.
7. Phase 1 coverage debt — closed locally at 90% total Brain coverage; per-module target table below.
8. Live provider eval and real call — not run. The owner reports LiveKit and Sarvam usage is available; exact account balances and realtime access still need confirmation before the supervised call. Gemini availability is unconfirmed; Groq is configured as the LLM failover. No provider credit was consumed.
9. Optional browser SpeechRecognition fallback — not built because acceptance criteria 1–8 are not yet complete.

### Local checks completed on 2026-10-26

- `scripts/validate_contracts.py`: **PASS**, 32 schema/sample/config checks.
- `pytest -p no:cacheprovider`: **PASS**, 34 tests including voice event ordering and the browser fixture cross-check.
- Brain coverage: **PASS**, 90% total. `ids` 96%, `policy` 100%, `guardrails` 100%, `state` 100%.
- Ruff: **PASS**, no issues in `apps/agent`.
- mypy: **PASS**, 14 Brain source files; targeted strict voice/provider check: 13 files.
- Scripted evals: **PASS**, 16/16, zero provider calls, 0 quota calls, max live-call cap 80.
- Web TypeScript and ESLint: **PASS**.
- Web unit/component suite: **PASS**, 85 tests.
- Web coverage: **PASS**, 95.95% lines overall; reducer 96.49%, protocol 100%, error mapping 100%. The `transport.ts` interface is type-only and has no runtime statements. Coverage was written to a temp directory because the workspace ACL rejects creation of `apps/web/coverage`.
- `scripts/check_env.py`: safe name-only output. Supabase URLs, provider key names, LLM/STT selections, all caps, `IP_HASH_SECRET` (length check **PASS**), and mock/real switches are set in `.env`. `LIVEKIT_URL` is **MISSING**. Values were not printed.
- Web production build: **NOT PASS**. `npm run build` on Next.js 15.5.27 remained in its generated type-check stage without completing; a separate `npm run typecheck` passes. No successful production artifact is claimed.
- Bundle secret-canary: **NOT RUN** against a completed build. No secret-leak result is claimed.
- `git diff --check`: **PASS**, with Windows line-ending/global-ignore warnings only.

### Brain coverage by module

| Module | Coverage |
| --- | ---: |
| `ids` | 96% |
| `policy` | 100% |
| `guardrails` | 100% |
| `state` | 100% |
| Brain total | 90% |

The complete coverage output and current rerun commands are in the checks below and in this progress section; no live-eval latency or provider-quota numbers are claimed.

### Manual/account-dependent gate items

- Apply `202610250001_phase2_voice_admission.sql`, then `202610260001_phase3_capacity_release.sql` in Supabase SQL Editor. Verify all 11 rows in `docs/RUNBOOK_SUPABASE.md` say `PASS`.
- Add `LIVEKIT_URL` from the LiveKit project settings to the local `.env`, then rerun `scripts/check_env.py`. The other required names, including `IP_HASH_SECRET` and public Supabase settings, currently pass the safe local check.
- Create or confirm the verified evaluator account in Supabase Auth. Sign in with that same email and password; keep the password out of chat/repository.
- Owner reports LiveKit and Sarvam usage is available. Before the one capped voice call, confirm exact remaining balances in the dashboards. Gemini availability is unconfirmed; the configured Groq key is the LLM failover. Do not fall back to another metered voice provider. The authenticated browser walkthrough, live call, observed latencies, and before/after credit values remain pending.
- Resolve the local Next build stall, then run a successful production build and `npm run check:bundle-secrets` against that output. Do not deploy the current Next.js 15.5.27 pin.
- Next.js upgrade/audit: first eligible separate patch date is 2026-10-29. The CI audit is non-blocking until the 15.5.28 and matching React patch commit. Do not deploy the current pin.

### Phase 4 proposal — not started

After Phase 3 approval, add the persistence migration with tenant RLS, persist the final call, chronological turns, tool calls and validated summary in one batched call-end write, and add a simple authenticated history/detail view. Preserve mock order/config repositories, call-end usage metering, the current event contracts, and the existing per-turn database budget. Required owner setup: Supabase project/migrations, evaluator account, and server-only Supabase service-role key. No additional paid account is required.

## Current status — 2026-10-25

Phase 1 text-mode acceptance and quality gates passed under Python 3.12.14. Ruff and mypy cleanup is complete. Older notes below describe earlier attempts before the supported runtime and pinned dependencies were available; this current section supersedes their runtime, test, and quality-gate status.

### Phase 1 verification results

- `python scripts/validate_contracts.py`: **PASS**, 21 valid/rejected contract checks.
- `python -m pytest -p no:cacheprovider`: **PASS**, 13 tests.
- `python -m pytest -p no:cacheprovider --cov=brain --cov-report=term-missing`: **PASS**, 13 tests; 66% total Brain coverage. Coverage data was directed to a temporary path because the ignored-file path was not writable in this environment.
- `python evals/runner/runner.py --mode scripted`: **PASS**, 16/16 scenarios, zero provider calls. Results are in gitignored `evals/results/scripted-latest.json`.
- Interactive `brain.cli --tenant aura --llm mock` smoke check: `/orders` listed all three seeded records and an order utterance prompted for normalized-ID confirmation. The generic mock reply did not execute a follow-on tool, so scripted evals remain the behavioral acceptance evidence.
- Ruff: **PASS**, `ruff check --no-cache .` reports no issues.
- mypy: **PASS**, strict mode reports no issues in 14 Brain source files.
- `python scripts/check_env.py`: ran without printing secret values. 11 of 14 declared environment-variable names are present; `LLM_MODEL_CANDIDATES`, `STT_MODEL`, and `SARVAM_REALTIME_ENABLED` are Phase 2 setup items.
- `git diff --check`: **PASS**. Git printed line-ending and global-ignore access warnings on Windows; neither indicates a whitespace error in the diff.

The test run exposed and fixed natural-language order-ID normalization and the cancel confirmation flow. It also showed that Windows needs pinned IANA timezone data and JSON Schema `date-time` validation dependencies; these are now in `apps/agent/pyproject.toml`. No LiveKit worker, audio, live provider calls, web UI, database, or deployment has been added. No provider quota was used.

### Reproduce the Phase 1 checks

From the repository root, using the Python 3.12 workspace environment:

```powershell
.\.venv\Scripts\python.exe scripts\validate_contracts.py
Push-Location apps\agent
..\..\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
..\..\.venv\Scripts\ruff.exe check --no-cache .
..\..\.venv\Scripts\mypy.exe --cache-dir "$env:TEMP\aria-mypy-cache"
Pop-Location
.\.venv\Scripts\python.exe evals\runner\runner.py --mode scripted
```

Coverage can be repeated with `COVERAGE_FILE` pointed at a writable temporary path. The eval runner writes its latest JSON result to the ignored results folder; if the local Windows ACL rejects that write, grant the runner workspace write access and rerun it. Its printed scenario summary alone does not count as a complete runner pass unless the process exits successfully.

### Manual Phase 1 text-mode walkthrough

Run the deterministic Brain without provider keys or audio:

```powershell
Push-Location apps\agent
..\..\.venv\Scripts\python.exe -m brain.cli --tenant aura --llm mock
```

Use this session as a CLI smoke check, not as the policy acceptance test:

1. Enter `/orders` and confirm only the three seeded Aura mock orders appear.
2. Enter `Where is ORD-101?` and verify Aria normalizes the ID and asks for confirmation. The generic mock LLM does not perform the order lookup after confirmation.
3. Enter `/events`, `/summary`, `/usage`, and `/quit` to inspect text-mode events and state.

The deterministic behavioral acceptance check is `python evals/runner/runner.py --mode scripted`, which ran all 16 policy, tool, privacy, and guardrail scenarios without provider calls. The interactive CLI mock is intentionally generic; use the scripted eval for cancellation, order-tool, injection, and out-of-scope assertions. Neither check verifies browser audio, LiveKit connectivity, real provider credentials, free-tier quotas, or end-to-end voice latency; those are Phase 2 checks.

## Phase 2 — Voice I/O implementation plan and active work

Phase 2 approved by the owner on 2026-10-25, including delegated selection of the LiveKit package line and Sarvam STT mode. Selected LiveKit Agents/plugin versions are 1.8.6; selected STT is Sarvam `saaras:v3-realtime` via `STTRealtime`, with visible text mode as the provider/quota fallback. See ADR-024 and ADR-025.

### Implementation status

Phase 2 code is implemented locally. The Phase 2 gate is **not closed**: the Supabase migration has not been applied to a project, and the browser widget belongs to Phase 3. No live STT/TTS call or browser-to-worker call is claimed.

1. **Voice dependencies — DONE.** `livekit-agents==1.8.6`, `livekit-plugins-sarvam==1.8.6`; Node token dependencies are pinned in `apps/web/package-lock.json`.
2. **Provider configuration — DONE in code.** Sarvam `STTRealtime` uses `saaras:v3-realtime`, `en-IN`, and `fast`; Bulbul v3 is TTS. Gemini candidate resolution checks the key's model inventory and tool-call eligibility. Groq is the ordered LLM failover. Voice provider failure changes the worker to the same Brain over text data messages; no alternate paid voice provider is used.
3. **LiveKit worker — DONE in code.** Session state, transcript/tool/failover/latency events, idle prompt, 300-second hard close, interruption truncation, and text-mode data channel are implemented.
4. **Quota protection — DONE in code; database application pending.** Admission RPC enforces four concurrent calls, five calls per IP per UTC day, five token requests per IP per minute, 300 seconds per call, and application monthly caps of 7,200 LiveKit-agent seconds, 7,200 Sarvam STT seconds, and 10,000 TTS characters. A Sarvam cap returns a text-only room token while LiveKit minute capacity remains. Per-call TTS is capped at 2,500 characters. The migration `supabase/migrations/202610250001_phase2_voice_admission.sql` must be applied before the endpoint can issue tokens.
5. **Token endpoint — DONE in code.** `POST /api/livekit/token` requires a verified Supabase user, HMAC-hashes IP, reserves admission, and issues a 10-minute room token with microphone-only audio rights in voice mode or data-only publishing in text mode. Secrets remain server-side.
6. **Provider-free verification — PASS.** Python: Ruff, strict mypy on voice/provider code, 21 pytest tests; deterministic eval runner 16/16; web TypeScript check and Next production build. These checks make no provider calls.
7. **Manual real-voice/browser check — PENDING.** The environment-name scan finds base provider credentials declared, but `IP_HASH_SECRET` and new cap variables are absent. Do not run a real call until the migration is applied, `IP_HASH_SECRET` is set, account free quota is confirmed, and Phase 3 browser controls exist. No account-specific remaining Sarvam credit was inspected.

### Verification results on 2026-10-25

- `ruff check --no-cache .`: **PASS**.
- `mypy --cache-dir "$env:TEMP\aria-mypy-cache"`: **PASS**, 14 Brain files; targeted strict check also passed for the voice worker and LLM provider modules.
- `python -m pytest -p no:cacheprovider`: **PASS**, 21 tests, including voice settings, event contract, and LLM failover.
- `python evals/runner/runner.py --mode scripted`: **PASS**, 16/16, zero provider calls.
- `npm run typecheck` (with incremental artifact disabled): **PASS**; `npm run build`: **PASS** on Next.js 15.5.27.
- `python scripts/check_env.py`: base credential variable names are present in the local environment file; `IP_HASH_SECRET` and new cap names are absent. No values were printed.
- No LiveKit room, Supabase schema, or Sarvam voice call was exercised. The Supabase CLI is not installed; the migration remains a local reviewed artifact. No provider credit was used by verification.

### Fresh local rerun before Phase 2 gate review

- Brain tests: **PASS**, 11 tests. The full suite could not collect the voice tests because this desktop Python environment has no LiveKit package installed.
- Contract samples and Aura config: **PASS**, 21 checks. This rerun exposed that `jsonschema`'s optional RFC3339 format checker is not installed by the CI contract job. The event schema now also constrains the timestamp syntax, and CI explicitly installs the pinned RFC3339 checker.
- Scripted eval assertions: **PASS**, 16/16 and zero provider calls. The default results folder is protected by this Windows environment, so the runner now accepts `--results-dir` and writes its report to a caller-selected location.
- Web TypeScript: **PASS**. A fresh production build was started but did not complete within this rerun window; the earlier recorded production build passed on Next.js 15.5.27.
- Ruff, mypy, and the complete voice test suite could not be rerun here: this machine has Python 3.14.7 while the project requires Python 3.12, and Ruff, mypy, LiveKit Agents, and the Sarvam plugin are not installed in the active environment. The pinned CI install remains the authoritative full run.
- `npm audit` could not reach the npm advisory service from this restricted network. Independently, the official Next.js security notice confirms that 15.5.27 is affected by the Oct. 14 Server Actions denial-of-service issue; fixed releases 15.5.28 and 16.4.1 were only 11 days old on this review date. Per the two-week release-age rule, do not install those yet. Web security audit remains an explicit **gate blocker**; the app is not deployed.
- `git diff --check`: **PASS** (only Git line-ending notices).

### Phase 2 acceptance criteria

- A local browser session connects through LiveKit to the Python worker and completes a real Sarvam STT → Brain/tools/guardrails → TTS turn.
- Mock mode remains the default for development, CI, and evals; real mode uses only verified free-tier configuration.
- STT or quota failure shows a clear message and continues in text mode; provider failures and latency stages are observable.
- Duration, idle, concurrency, per-IP, token-endpoint, and monthly usage caps are enforced before voice is considered live.
- Room tokens are short-lived and minimally privileged; no provider secrets reach the browser.
- Local commands, test output, quota use, known limitations, and risks are recorded before the Phase 2 gate.

### Remaining before closing the Phase 2 gate

- Apply the SQL migration in the selected Supabase project; configure `IP_HASH_SECRET` and ensure the project uses its free tier.
- Implement Phase 3's browser UI that consumes the token response and renders `aria.call-event` plus text fallback.
- After that UI exists, run one manually capped real call (five minutes maximum, one concurrent call, one call for the day) after confirming remaining free quota in provider dashboards, then record latency and outcome.
- Revisit the Next.js security patch after it passes the two-week release-age window; rerun `npm audit` with registry access and confirm the locked dependency tree is clear of high/critical findings before deployment.

## Decision update — 2026-10-25

- The original Phase 0 selection of legacy Sarvam `saaras:v3` was superseded by the owner's Phase 2 delegation. `saaras:v3-realtime` is primary; the fallback is visible text mode on the same Brain.
- Owner requested Supabase's built-in email for the current low-volume stage and custom SMTP as a future fallback. Official docs show built-in mail is team-address-only and currently limited to 2 messages/hour; external evaluator sign-up, verification, and other mail-dependent flows require custom email delivery. A pre-created verified evaluator can still sign in. Automatic fallback needs a Send Email Hook or equivalent routing layer.
- Owner confirmed Vercel Hobby for the personal, non-commercial project; commercial showcases are out of scope. Official terms were reviewed and the docs now record the restriction.
- Official sources and decisions are recorded in `docs/RESEARCH.md`, `docs/DECISIONS.md`, and `docs/ARCHITECTURE.md`.

## Phase 0 — Research and contracts

Status: Phase 0 closed; Phase 1 Task 0 and deterministic Brain foundations in progress.

Completed in this work session:

- Added the approved D1–D8 amendments to `AGENTS.md`.
- Created the repo skeleton and secret hygiene files.
- Added revised JSON Schema contracts and Aura YAML seed.
- Added policy-boundary documentation.
- Added validator and environment-check tooling.
- Added CI skeleton for contract validation and secret scanning.

Not started by design:

- No Brain implementation.
- No LiveKit worker.
- No UI.
- No database migrations.
- No deployment.
- No provider calls.

Validation evidence:

- PowerShell JSON parsing passed for all 20 samples: 8 valid and 12 invalid sample files.
- The required `python scripts/validate_contracts.py` could not run because this desktop has no installed Python runtime (`py` is only a launcher and reports no installed Python). No passing result is claimed.
- The required `python scripts/check_env.py` is present but could not run for the same reason. It has not printed or exposed any environment value.
- `.env` exists locally but is excluded by `.gitignore`; the repository currently has no tracked files before the Phase 0 commit.
- A full Draft 2020-12 validation run remains a gate item once Python plus `jsonschema` and `PyYAML` are available.

## Phase 1 — Brain, text mode only

Task 0 status: started.

The environment checker now detects declared variable names in the local `.env` without reading or printing values. The earlier `MISSING` result came from checking only inherited process variables. The local `.env` names include the provider keys, but this machine still has no installed Python runtime, so Python checks cannot run yet.

Implemented foundations: injectable IST clock, relative-date in-memory orders, tenant loader, order-ID normalization, English/Romanized-Hindi yes/no classification, deterministic policy functions, confirmation-aware tools, serializable call state, prompt builder, output guardrails, deterministic summary fallback, provider breaker/resolver seams, MockLLM, and initial unit tests.

Not yet complete or verified: provider integration against live SDKs, Python test execution, coverage run, live eval, and final contract-conformance checks. No audio, LiveKit, web UI, database, or deployment was added.

Additional Phase 1 work: lazy Gemini and Groq adapter modules, provider-neutral message types, model resolver, circuit breaker tests, mock-first factory, text CLI provider selection, initial scripted scenario YAML, and a quota-safe scripted runner placeholder. These files have not been executed because Python is not installed on this desktop; no test or coverage pass is claimed.

## Phase 1 completion segment

Implemented the bounded async tool-call turn loop with a three-round tool limit, eight-second turn deadline, filler events before tools, structured tool results, ID confirmation, explicit cancellation confirmation, per-sentence output validation, escalation fallback, and `commit_spoken` interruption handling.

The CLI now supports `/state`, `/events`, `/summary`, `/usage`, `/orders`, `/reset`, and `/quit`. The scripted eval suite now contains the required core, policy, privacy, out-of-scope, injection, escalation, unknown-information, and misbehaving-model scenarios. The runner writes gitignored JSON results and reports pass/fail, tool calls, and quota usage.

Verification performed in this segment: contract JSON parsing and whitespace checks passed; the full-history secret scan passed. Python unit tests, mypy, Ruff, and the scripted runner remain unexecuted because no Python runtime is installed. No live provider calls were made.

## LiveKit Cloud deployment update — 2026-10-27

The owner confirmed that local audio mode is working. The agent was deployed to the linked LiveKit Cloud project in the `ap-south` region, production deployment, as agent ID `CA_49j8Y9MZhtw8`. CLI status reports `Running` with one replica, and runtime logs confirm the `aria-voice` worker registered successfully. This verifies worker startup and registration; no browser-to-cloud real audio call was made during this deployment, so cloud end-to-end voice is not claimed as verified.

Deployment fixes: use Python 3.12 to match `pyproject.toml`; add the pinned LiveKit CLI `requirements.txt` manifest; install it in the agent Dockerfile; and launch the package with `python -m voice.worker start` so relative imports resolve. The worker secrets file `.env.production` is ignored by Git and was uploaded to LiveKit Cloud through the CLI. LiveKit injects its own connection credentials at runtime.

### Cloud session startup failure — plan before code

Evidence from the production worker logs shows that the worker starts, registers as `aria-voice`, receives jobs, then raises `IndexError` while `_create_brain` calculates its repository root. The deployed container runs the application from `/app`, where `worker.py` has fewer parent directories than the local checkout. A separate `usage_update_failed` log indicates the Supabase usage-meter RPC also needs verification after the secrets update.

Plan and acceptance criteria:

- Resolve the repository/config root by checking the actual runtime layout instead of assuming a fixed `Path.parents` depth.
- Package the canonical tenant-config schema with the agent build context so the existing runtime schema validation still runs in LiveKit Cloud.
- Keep the packaged schema alongside the Aura tenant YAML (the current workspace ACL prevents creating a new `apps/agent/contracts/` folder); document/synchronize it with the canonical contract.
- Teach the tenant loader to read either the repository layout used locally or the packaged agent layout used in the container.
- Preserve the new safe stack-location logging that does not print exception messages or secrets.
- Confirm the build-local package paths and schema resources are consistent; then redeploy and use one short Console session to verify that the agent joins and begins greeting. Record any remaining Supabase RPC error separately.

Diagnosis and fix prepared locally:

- The new stack log identifies `Path.resolve().parents[3]` in `_create_brain` as the exact `IndexError` source: the container path is `/app/voice/worker.py`, which has no fourth parent. This is a packaging/path bug, not a missing LiveKit connection secret.
- Added runtime root discovery for both the repository checkout and the deployed `/app` layout. `TenantConfigLoader` now supports either `apps/agent/tenants` or packaged `tenants` paths.
- Added a packaged copy of `tenant_config.json` beside the Aura tenant seed so runtime schema validation remains enabled in the LiveKit build context. Its SHA-256 matches the canonical `contracts/tenant_config.json` at authoring time.
- This workspace cannot launch its configured `lk.exe` shim, so deployment and post-deploy session verification remain pending. The separate Supabase usage-meter RPC error also remains to be confirmed after secrets update.

## Assessment demo package — plan before writing

The owner needs a 3–5 minute video demonstrating a working voice call, an order lookup, a policy conversation, the post-call transcript and summary, and a brief architecture walkthrough, plus a 2–3 sentence approach note.

Plan and acceptance criteria:

- Create a timed recording script that uses the app's real UI and confirmation flow, including a safe cancellation refusal on ORD-101.
- Add pre-recording checks and explicit instructions for displaying the post-call transcript/summary without exposing credentials or real personal data.
- Include an architecture diagram and short spoken walkthrough that match the current implementation and clearly state demo limitations.
- Provide a standalone three-sentence approach note suitable for submission.

Completed:

- Added `docs/DEMO_VIDEO_GUIDE.md` with recording preflight, a timed 4:20 script, spoken ORD-101 lookup and safe cancellation refusal, a post-call transcript/summary segment, an architecture diagram/talk track, and the three-sentence approach note.
- Linked the guide from README. No app behavior or quota limits were changed.

## Evaluator daily voice limit exemption — plan before migration

The owner requests that the verified `evaluator@ariaagent.com` account no longer need a manual SQL update to regain daily voice admissions.

Plan and acceptance criteria:

- Add an additive Supabase migration that exempts only this authenticated evaluator from the daily-per-IP call cap in both admission and capacity-display RPCs.
- Keep the shared concurrent-call cap, monthly provider usage caps, per-call duration cap, and token-request rate limit in force to protect free-tier providers.
- Update the Supabase runbook with migration order, exact dashboard steps, and verification guidance. Explain why manually releasing all daily rows can disrupt active-call accounting.
- Do not apply the migration or access the user's Supabase project; the owner applies SQL manually.

Completed:

- Added `supabase/migrations/202610270001_evaluator_daily_voice_exemption.sql`. The verified `evaluator@ariaagent.com` user skips the daily-per-IP admission and capacity checks; all shared concurrency, monthly provider, per-call duration, and per-minute token-start caps remain active.
- Updated `docs/RUNBOOK_SUPABASE.md` with the migration step and evaluator-account verification. The owner must apply the new migration in Supabase SQL Editor before the exemption takes effect.
- Did not apply database changes or run a live voice call. The existing daily-release SQL is no longer needed after the migration is applied; manually releasing an active reservation could interfere with usage accounting.
