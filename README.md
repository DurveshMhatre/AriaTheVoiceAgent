# Aria Voice CX Platform

Phase 0 establishes the contracts, tenant seed, research ledger, ADRs, and free-tier safety checks for a browser-only Aura Skincare voice-support demo.

No application code, voice worker, UI, migrations, or deployment is included in Phase 0.

## Verify Phase 0

```powershell
python -m pip install jsonschema PyYAML
python scripts/validate_contracts.py
python scripts/check_env.py
```

The environment checker prints only `SET` or `MISSING`. Never commit `.env` or paste secrets into chat.

## Secret scanning

The preferred scanner is gitleaks. If it is not installed, the pre-commit hook and the manual check use the repository-contained PowerShell equivalent:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/secret_scan.ps1
```

It checks tracked working-tree files and every reachable Git commit, and prints only filenames or a pass count.

## Phase 1 text mode

From PowerShell:

```powershell
Set-Location apps/agent
python -m brain.cli --tenant aura --llm mock
```

The CLI supports `/state`, `/events`, `/summary`, `/usage`, `/orders`, `/reset`, and `/quit`. Run the deterministic evaluation suite from the repository root with:

```powershell
python evals/runner/runner.py --mode scripted
```

The scripted suite never calls Gemini or Groq and writes its JSON report under the gitignored `evals/results/` directory.

## How I think about the system

1. The Brain is separate from audio so policy and guardrails can be tested cheaply.
2. Business rules are deterministic code, not model instructions.
3. Provider adapters and caps protect free quotas and make failures visible.
4. Contracts and ADRs make the design explainable and portable.
