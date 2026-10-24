# Progress

## Phase 0 — Research and contracts

Status: in progress pending validation and gate review.

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
