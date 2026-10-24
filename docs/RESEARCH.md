# Research ledger

Read date: 2026-10-25. Sources are official unless marked otherwise.

| Topic | Source | Version/date | Status | Key fact or gotcha |
|---|---|---|---|---|
| LiveKit Agents Python | https://docs.livekit.io/agents/ | current docs | VERIFIED | Python/Node agents, streaming pipelines, tools, interruptions, agent server deployment. |
| LiveKit Agents package | https://pypi.org/project/livekit-agents/ | 1.8.8; page retrieved 2026-10-25 | VERIFIED | Requires Python >=3.10,<3.15. Pin exact version before Phase 2. |
| LiveKit Cloud quotas | https://docs.livekit.io/deploy/admin/quotas-and-limits/ | current docs | VERIFIED | Build: 5 agent sessions, 1,000 agent minutes/month, hard cap, possible 10–20s cold start. |
| Sarvam STT overview | https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/overview | current docs | VERIFIED | `saaras:v3-realtime` is beta; legacy WebSocket is `saaras:v3`; REST currently recommends `saaras:v4`. |
| Sarvam STT streaming | https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/streaming-api | current docs | VERIFIED | Streaming accepts WAV/raw PCM; Python helper currently fixes encoding to WAV. |
| Sarvam credits | https://docs.sarvam.ai/api/getting-started/ratelimits | current docs | VERIFIED | ₹100 signup credit per verified user, never expires; account-wide key pool. |
| Sarvam TTS | https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/overview | current docs | VERIFIED | Bulbul V3, 30+ voices, REST up to 2,500 chars, HTTP/WebSocket streaming. |
| Gemini rate limits | https://ai.google.dev/gemini-api/docs/rate-limits | current docs | VERIFIED | Project-level RPM/TPM/RPD; exact limits vary and must be read from AI Studio. |
| Gemini pricing/models | https://ai.google.dev/gemini-api/docs/pricing | current docs, read 2026-10-25 | VERIFIED | Free-tier availability and model names are model-specific; no billing for this project. |
| Gemini deprecations | https://ai.google.dev/gemini-api/docs/deprecations | current docs, read 2026-10-25 | VERIFIED | Gemini 3.5 Flash has no shutdown date announced but is marked as replaced by 3.6 Flash; 3.1 Flash-Lite has no shutdown date announced. The binding candidate list is retained, but startup resolution must reject unavailable models. |
| Gemini thinking/function calling | https://ai.google.dev/gemini-api/docs/thinking | current docs, read 2026-10-25 | VERIFIED | `thinking_level` controls reasoning; minimal/low is appropriate for short support turns. Tool-call turns may require provider-specific reasoning context, so the adapter must preserve vendor response parts and never expose them to Brain types. |
| Groq limits | https://console.groq.com/docs/rate-limits | current docs | VERIFIED | Organization-level RPM/RPD/TPM/TPD and audio limits; exact active values are account-specific. |
| Groq tool calling | https://console.groq.com/docs/tool-use/local-tool-calling | current docs, read 2026-10-25 | VERIFIED | Chat Completions supports function tools, `tool_choice`, tool-call message threading, and low temperature for deterministic calls. The adapter must preserve assistant tool-call messages and tool results. |
| Supabase pricing | https://supabase.com/pricing | current docs | VERIFIED | Free: 2 projects, 500 MB DB/project, 5 GB egress, 1 GB storage, 50k MAU; pause after one week inactivity. |
| Supabase billing | https://supabase.com/docs/guides/platform/billing-on-supabase | current docs | VERIFIED | Free quotas and two-project limit; quotas differ by item and may be organization-wide. |
| Vercel Hobby terms | pending official terms re-check | pending | ASSUMED | Assessment-only use is approved by D1; commercial migration trigger must be documented before deployment. |
| Supabase email limits/custom SMTP | pending official auth email docs | pending | ASSUMED | Custom SMTP and a demo evaluator account are D5 requirements; verify limits/options before Phase 3. |
| LiveKit Sarvam plugin parameters | pending current plugin docs | pending | ASSUMED | D2 requires the official plugin with `saaras:v3`; exact current constructor parameters must be verified before Phase 2. |
| Gemini deprecation dates | verified above | 2026-10-25 | VERIFIED | Current deprecation page was checked; candidate resolution remains mandatory because model availability changes. |
