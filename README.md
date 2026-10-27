# Aria Voice CX Platform

Aria is a browser-based voice customer-support assistant for **Aura Skincare**, a fictional Indian skincare brand. Customers can speak with Aria, ask questions about Aura's products and policies, and check sample order information. The experience also supports text conversations.

> **Project status:** The owner has confirmed that audio mode is now working. This repository is a development project; that confirmation does not mean the app is publicly deployed.

## What Aria can do

- Hold a browser voice conversation, with a text mode available through the same conversation brain.
- Answer using Aura's configured brand information and deterministic order and policy tools.
- Look up sample orders and apply return, cancellation, shipping, and cash-on-delivery rules.
- Show call state and transcript, with graceful text-mode behavior when voice capacity or a voice provider is unavailable.
- Protect provider credentials on the server and limit call duration and usage.

The included orders and brand are demo data. This is not connected to a real store, and it must not be used to make real customer-service decisions.

## How it works

The app separates conversation decisions from audio handling:

1. **Web app** — Next.js and TypeScript provide evaluator sign-in and the browser call experience.
2. **Voice worker** — Python and LiveKit Agents connect browser audio to the voice pipeline.
3. **Speech providers** — Sarvam realtime speech recognition (`saaras:v3-realtime`) and Bulbul text-to-speech provide the configured voice path.
4. **Conversation brain** — Provider adapters connect the LLM to deterministic tools, Aura's policies, output guardrails, and call summaries. Gemini is preferred when available, with Groq as the configured LLM fallback.
5. **Data and access** — Supabase provides evaluator authentication and quota admission. LiveKit issues short-lived room access through the server API.

The brain can also run with mock providers for development and automated checks without spending voice-provider quota.

## Repository map

```text
apps/web/       Next.js browser app and server API routes
apps/agent/     Python conversation brain, providers, and LiveKit worker
contracts/      Shared API and call-event schemas with sample payloads
docs/           Architecture, decisions, progress, research, and runbooks
evals/          Deterministic text-mode conversation scenarios
supabase/       Database migrations for call admission and capacity
```

## Run locally

### 1. Configure local services

Copy `.env.example` to `.env` at the repository root and fill in the credentials for the services you have configured. Never commit `.env` or put provider secrets in variables prefixed with `NEXT_PUBLIC_`. For the web app, Supabase evaluator authentication and the server-side Supabase, LiveKit, and IP-hash settings are needed. Real voice additionally requires the LiveKit worker credentials and Sarvam access; an LLM key is needed for a real model. Keep `VOICE_MODE=mock` and `LLM_MODE=mock` when you want to work without real voice-provider calls.

Apply the relevant Supabase migrations in `supabase/migrations/` and create a verified evaluator account before testing authenticated calls. See [the Supabase setup runbook](docs/RUNBOOK_SUPABASE.md) and [the real-call runbook](docs/RUNBOOK_REAL_CALL.md) for setup and quota precautions.

### 2. Install dependencies

From the repository root in PowerShell:

```powershell
python -m pip install -e "apps/agent[voice,providers]"
Set-Location apps/web
npm ci
```

### 3. Start the agent and web app

In the first terminal, from the repository root:

```powershell
Set-Location apps/agent
python -m voice.worker dev
```

In a second terminal, from the repository root:

```powershell
Set-Location apps/web
npm run dev
```

Open `http://localhost:3000` and sign in with the verified evaluator account. For local-only usage and troubleshooting, follow the runbooks rather than enabling real voice by default.

## Run the text-mode checks

From the repository root:

```powershell
python scripts/validate_contracts.py
python evals/runner/runner.py --mode scripted
```

The scripted evaluations use mock behavior and do not call Gemini, Groq, or Sarvam. Agent unit tests and web checks are documented in the project files and CI workflow.

## Deployment direction

The intended hosting split is Vercel for the Next.js web app and LiveKit Cloud for the long-running LiveKit voice worker. The worker is not deployed as a Vercel function. Keep within the project's approved free-tier and personal-use constraints; deployment requires configuring secrets in each service's server-side settings. The application is not described here as publicly deployed.

## Security and demo limitations

- Keep `.env`, Supabase service-role credentials, LiveKit API secrets, Sarvam keys, and LLM keys out of Git and browser code.
- The order records are fixtures; order-ID-only lookup is for this demo and is not production customer verification.
- Aura contact details are placeholders. Aria must not invent contact information or promise a refund or replacement.
- Live service availability and free quotas depend on the provider accounts configured by the operator.
- Vercel Hobby is restricted to personal, non-commercial use. Review the current platform terms before changing the project's use or hosting plan.

## Project documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Progress and acceptance gates](docs/PROGRESS.md)
- [Technical research](docs/RESEARCH.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Plain-language explainer](docs/EXPLAINER.md)
- [Supabase setup runbook](docs/RUNBOOK_SUPABASE.md)
- [Real voice call runbook](docs/RUNBOOK_REAL_CALL.md)
- [Assessment demo video guide and approach note](docs/DEMO_VIDEO_GUIDE.md)
