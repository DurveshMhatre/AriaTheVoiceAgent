# Progress

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

Not yet implemented: full provider adapters, complete streaming turn/tool loop, CLI, all required eval scenarios, coverage run, live eval, and the remaining Phase 1 ADRs. No audio, LiveKit, web UI, database, or deployment was added.
