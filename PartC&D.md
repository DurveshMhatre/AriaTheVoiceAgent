
# PART C: Phase 0 Execution Prompt

The coding agent finished its Phase 0 research and asked 8 questions. This part records your answers, then gives the agent its build instructions. Part D covers what comes after.

## C1. Decision record (your answers)

| # | Question | Decision | Reason |
| --- | --- | --- | --- |
| 1 | Web hosting | **Vercel Hobby** for the assessment deployment only. Keep the app portable: no Vercel-only storage, KV or edge features. Write an ADR to migrate to Cloudflare Pages or Netlify before any commercial use. | Vercel's Hobby terms limit it to personal, non-commercial use. A hiring assessment fits. A paid SaaS does not. |
| 2 | Sarvam STT | Use the **official LiveKit Sarvam plugin** with `saaras:v3`. Keep `saaras:v3-realtime` (beta) behind a config flag, off by default. No custom WebSocket client unless the plugin fails a Phase 2 test. | Fewest moving parts. A beta endpoint can change without notice. |
| 3 | Gemini model | **Do not hard-code a model.** Config holds an ordered candidate list. At startup the agent lists the models the key can use and picks the first that supports tool calling. Initial list: `gemini-3.1-flash-lite`, then `gemini-3.5-flash`. Never use `-preview` IDs or any 2.x model. | Google's deprecation page lists gemini-2.5-flash, 2.5-flash-lite and 2.5-pro with an earliest shutdown of 16 Oct 2026, and the 2.0 models ended on 1 Jun 2026. Model IDs change fast. |
| 4 | Voice vs text | Text mode is acceptable as a fallback. Build it as a first-class **Voice / Text toggle** running the same Brain. Switch to text automatically when voice quota is exhausted, and label it clearly. | The evaluator can always test something, even when free credits run out. |
| 5 | Public access | **Login required.** Email + password with email verification, and magic link as a second option (Supabase Auth). Also create a **demo evaluator account** in the Supabase dashboard so evaluators need no email. Configure custom SMTP. No anonymous calls. | Supabase's built-in email sender only delivers to your own team members and is capped at 2 emails per hour, so evaluators would never receive a magic link. |
| 6 | Aura contact details | Keep `PLACEHOLDER`. The agent never speaks a phone number, email or URL. For follow-ups it says the support team will follow up, and records a ticket row. Later you may add a real inbox you control, marked as demo. | Never invent contact details. |
| 7 | Supabase usage | Minimal. The database is used for: auth, **one batched write at call end** (call, turns, tool calls, summary), and one usage-counter update at call end. No per-turn writes, polling or realtime subscriptions. Mock orders and tenant config live in code and YAML behind interfaces, not in the database. | Protects free-tier limits, avoids the inactivity-pause risk, keeps the Brain testable offline. |
| 8 | Customer identity | Keep order-ID-only lookup with `verified: false`. OTP is documented, not built. Login identifies the **evaluator** (the app user), not the **customer** on the call, and is used only for quotas and abuse limits. | They are different things. Mixing them would imply the demo verifies customers. |

## C2. The Phase 0 prompt (send this to the agent)

\=====

**Phase 0 is approved to build.** Your research and questions are accepted. Decisions D1 to D8 below are binding amendments to `AGENTS.md`. You are still in Phase 0: **no application code, no voice worker, no UI, no migrations, no deployment.** The only executable code allowed is contract-validation and environment-check tooling.

### 1. Binding decisions

- **D1 Hosting:** Vercel Hobby for the assessment only; keep the web app portable; ADR to migrate before commercial use.
- **D2 STT:** official LiveKit Sarvam plugin, model `saaras:v3`; `saaras:v3-realtime` behind a flag, off by default.
- **D3 LLM:** no hard-coded model. Ordered `model_candidates` in config, resolved at startup against the models the key can actually use, requiring tool-calling support. Start with `gemini-3.1-flash-lite`, then `gemini-3.5-flash`. No `-preview` or 2.x IDs. Groq stays as failover. Google's free tier may use inputs to improve its products, so the demo uses only fake data.
- **D4 Text mode:** a first-class Voice/Text toggle on the same Brain, with automatic switch to text when voice quota is exhausted.
- **D5 Access:** login required (email + password with verification; magic link secondary), a pre-created demo evaluator account, custom SMTP, no anonymous calls. Auth is built in Phase 3; Phase 0 writes the ADR only.
- **D6 Contacts:** `PLACEHOLDER` values; the agent never speaks a contact detail and records a ticket instead.
- **D7 Database:** minimal writes (auth, one batched write and one counter update at call end). Mock orders and tenant config are in code and YAML behind an `OrderRepository` and a `TenantConfigLoader` interface.
- **D8 Identity:** `verified: false` seam; OTP documented only; login is the evaluator, not the customer.

### 2. Secrets (my keys are already in `.env`)

- Never print, log, echo or commit any value from `.env*`. Never ask me to paste a key into chat.
- Confirm `.gitignore` excludes `.env` and `.env.*` (except `.env.example`) and key or certificate files.
- Write `scripts/check_env.py`, which prints only `SET` or `MISSING` for each variable name, never a value.
- Add a secret-scanning step (gitleaks or an equivalent free tool) to `ci.yml` and a local pre-commit hook.
- `.env.example` lists names only, including new ones: `LLM_MODEL_CANDIDATES`, `STT_MODEL`, `SARVAM_REALTIME_ENABLED=false`, `VOICE_MODE=mock`. SMTP credentials are configured in the Supabase dashboard, never in the repo.

### 3. Tasks, in this order (one commit per task, conventional commit messages)

1. **Amend `AGENTS.md`.** Add `## 10. Amendments (Phase 0)` recording D1 to D8, and edit these clauses so nothing contradicts: 6.3 (orders live in code behind `OrderRepository`, not the DB), 6.7 (login screen, Voice/Text toggle), 6.9 (list which tables are written and when, per D7), and section 5 (text-mode fallback when voice quota runs out).
2. **Re-verify research.** Update `docs/RESEARCH.md`. Treat these as claims to check against official docs, not facts: Gemini deprecation dates and free-tier model list; the LiveKit Sarvam plugin's current Python parameters and model strings (including streaming versus REST fallback); Vercel Hobby terms; Supabase built-in email limits and the free SMTP provider options (daily limits, sender-verification rules). For every entry record URL, date read, version, and a `VERIFIED` or `ASSUMED` label.
3. **Repo skeleton.** Match the locked layout, plus `scripts/`, `contracts/samples/valid/` and `contracts/samples/invalid/`.
4. **Revise the contracts** with these changes:
   - Add `schema_version` (const 1) to every contract.
   - `call_events`: make `data` a discriminated union keyed by `event_type`, with a required shape for each type. Require `turn_id` for turn-scoped events. Carry the four per-turn latency fields (`stt_final_ms`, `llm_first_token_ms`, `tts_first_byte_ms`, `end_to_end_ms`).
   - `tool_schemas`: keep the four tool definitions and add a `tool_result` envelope `{ ok, data, error_code, speakable_hint }` with an `error_code` enum (`INVALID_FORMAT`, `NOT_FOUND`, `NOT_ELIGIBLE`, `TIMEOUT`, `INTERNAL`). Every tool input must have `additionalProperties: false`.
   - `call_summary`: replace the Aura-specific `ORD-[0-9]{3}` pattern with a generic ID pattern (the tenant owns its ID format). Replace free-text `policy_outcome` with a nullable enum, for example `RETURN_WINDOW_EXPIRED`, `ITEM_OPENED`, `RETURN_ELIGIBLE`, `NOT_YET_DELIVERED`, `CANCEL_ALLOWED`, `CANCEL_BLOCKED_SHIPPED`, `NONE`.
   - `tenant_config`: bind `enabled_tools` to the tool-name enum; add `providers` with ordered `stt`, `llm` (with `model_candidates`) and `tts` chains; add a default `voice_mode`; add `free_shipping_rule` (`above` or `at_or_above`), `cod_limit_inclusive` and `id_format`; keep contact fields as `PLACEHOLDER` and add `contact_verified: false`.
   - `format: date-time` is ignored by validators unless a format checker is enabled. Enable it and test it.
5. **Samples.** For each contract, at least 2 valid and 3 invalid samples (missing required field, bad enum value, extra property; for events a data shape that does not match its `event_type`; for the summary a malformed ID).
6. **Validator.** `python scripts/validate_contracts.py` uses a Draft 2020-12 validator with format checking, validates every valid sample, **confirms every invalid sample is rejected**, and exits non-zero on any failure.
7. **Aura seed.** `apps/agent/tenants/aura.yaml` validates against `tenant_config`, contains every fact in `AGENTS.md` 6.2, and sets caps: 300 s call length, 45 s idle, 4 concurrent calls, a per-user daily call cap. Also write `docs/POLICY_BOUNDARIES.md`, a table of boundary cases to implement in Phase 1 (₹499 versus ₹500, day 7 versus day 8, ₹2,500 versus ₹2,501, relative dates, undelivered orders, damage claims needing photos). **Document only; implement nothing.**
8. **ADRs.** In `docs/DECISIONS.md`, one ADR each for: cascaded pipeline; LiveKit Agents on LiveKit Cloud; Brain/Voice split; provider adapters and fallbacks; Supabase RLS with minimal writes; metering and caps; hosting (Vercel Hobby and its migration trigger); Sarvam plugin and `saaras:v3`; Gemini candidate list and startup resolution; auth with custom SMTP and demo evaluator; text-mode fallback; identity seam; contact placeholders. Each ADR has context, decision, alternatives and consequences.
9. **Docs.** One-page `docs/ARCHITECTURE.md` with a call-flow diagram in text and a failure-mode table (provider down, quota exhausted, mumbled audio, unknown order ID, mic denied); an initial plain-English `docs/EXPLAINER.md`; `docs/BACKLOG.md` (Hinglish, OTP, telephony, human handoff, dashboards, barge-in tuning, migration off Vercel); `docs/PROGRESS.md`.
10. **CI skeleton.** `ci.yml` runs the contract validator and the secret scan. No application jobs yet.

### 4. Rules

No paid account, billing, or payment method. No new dependencies beyond the validator tooling. No real keys anywhere in the repo. Do not start Phase 1. If something is unclear and affects architecture, ask (at most 5 questions).

### 5. Gate report (then stop and wait)

Give me: the file tree; the full output of `python scripts/validate_contracts.py` and `python scripts/check_env.py`; proof that no `.env` file is tracked (`git ls-files`); the ADR titles; every deviation from this prompt; open questions; and a proposed Phase 1 plan. Explain in plain English what Phase 0 produced and why it matters.

\=====

## C3. Your gate checklist (before you approve Phase 1)

- Ask the agent for the exact commands, run the validator yourself, and confirm you see invalid samples being rejected.
- Confirm no `.env` file appears in the tracked-files list.
- Skim the ADR titles. Anything surprising goes back to the team discussion.
- Ask: *"Explain Phase 0 as if to an interviewer."* If you cannot follow the answer, ask again before moving on.
- **One new account is needed later (Phase 3), not now:** a free email-sending provider for Supabase custom SMTP. The agent's RESEARCH file will list the options and limits.

---

# PART D: Next procedure

## D1. The loop for every phase

1. Paste the phase prompt. The agent writes its plan in `docs/PROGRESS.md` and builds.
2. At the gate, ask for proof (command output), not a summary.
3. Ask for the plain-English explanation and update `docs/EXPLAINER.md`.
4. Bring the gate report back here. The team reviews it before you approve.
5. Send the next phase prompt.

## D2. Phase 1 prompt: the Brain, text mode (send after Phase 0 is approved)

\=====

Phase 0 is approved and closed. Start **Phase 1: the Brain, text mode only.** No audio, no LiveKit, no web UI, no database. Follow `AGENTS.md` including its amendments.

### Scope

- **Data seams:** `OrderRepository` (in-memory, seeded with dates relative to an injectable `Clock`) and `TenantConfigLoader` (reads `aura.yaml`, validates it against the contract).
- **`normalize_order_id`:** a test table of at least 25 spoken and written variants, such as 'O R D one zero one', 'order one oh one', 'ord 101' and 'ORD-101', plus garbage inputs that must return `None`.
- **`PolicyEngine` (pure functions):** shipping fee, COD eligibility, return eligibility, cancellation eligibility, damage-report window. Implement every boundary in `docs/POLICY_BOUNDARIES.md`. Reason codes map to the summary's `policy_outcome` enum.
- **Tools:** the four tools with the `tool_result` envelope, timeouts, and an idempotency key on `cancel_order`. `escalate_to_human` records an in-memory ticket and never claims a live transfer.
- **`CallState`:** intent, candidate ID, confirmed ID, ID attempts, unclear-turn count, escalation flag, `verified: false`, tool results. Serialisable, with transitions unit-tested.
- **Prompt builder:** builds the system prompt from tenant config. Snapshot-tested. It must contain no policy number that does not come from config.
- **Turn loop:** user text, then LLM with tools, then output validator, then speakable text. Maximum 3 tool rounds, per-tool timeouts, graceful spoken errors.
- **Output validator** (`AGENTS.md` 6.5): blocks promises such as 'refund approved', unknown amounts, dates and statuses, markdown, lists, URLs, and replies longer than 2 sentences, and replaces them with a safe fallback line plus a `guardrail_triggered` event.
- **Summary generator:** schema-validated, one retry, deterministic fallback built from `CallState`.
- **LLM adapters:** Gemini adapter with startup model resolution (D3), Groq failover with a circuit breaker, and a scripted `MockLLM`.
- **Text CLI:** `python -m brain.cli --tenant aura` so I can chat with Aria in the terminal.
- **Eval runner:** the 14 required scenarios from `AGENTS.md` as YAML. Two modes: `scripted` (MockLLM with recorded responses, the CI default, zero quota) and `live` (real LLM, manual, with a daily call cap and a quota printout).

### Rules

- Test-first for `PolicyEngine`, `normalize_order_id` and the validator: show the failing run, then the passing run.
- No business rule inside a prompt. If a rule is missing from code, add it to code.
- Free-tier discipline: ask before running more than one full live eval pass per day. Do not record live transcripts as golden files until I approve them.
- Report honestly: failed scenarios and flaky behaviour go in `PROGRESS.md`.

### Acceptance criteria

- All unit tests pass, with counts shown; at least 95% line coverage on the policy engine, ID normaliser and validator.
- All 14 scenarios pass in `scripted` mode, and one `live` pass is reported with every failure analysed.
- A CLI transcript of 5 scenarios (tracking, day-20 opened return, cancel on ORD-103, bad ID, out-of-scope flight) is pasted into `PROGRESS.md`.
- `EXPLAINER.md` gains a plain-English section on how the agent decides when to call a tool and how the guardrails work.
- Gate report in the Phase 0 format, then stop and wait.

\=====
