# One-call real voice check

This runbook is for one manually supervised local call after Phase 3's fake-transport and security checks pass. Text mode remains the default for development, tests, and all other walkthroughs. Do not start the call until the Supabase migration is applied and verified, `IP_HASH_SECRET` is set, and you have checked the free-plan balances below.

## Preflight

Read these values from the provider dashboards and share only the numeric remaining balances/limits, never secrets:

- LiveKit Build plan minutes and current month usage.
- Sarvam remaining credits and the account's `saaras:v3-realtime` access.
- Gemini request/token limits and the active model candidates available for tool calling.
- Confirmation that the current Supabase project is on free plan and the SQL verification reports 11 `PASS` rows.

The app hard cap is 5 minutes per call, four concurrent reservations in SQL and five calls per IP per UTC day. For this supervised check, run only one browser call and end within 5 minutes. Sarvam STT and TTS are capped at 7,200 seconds and 10,000 characters per month, with 2,500 TTS characters per call. The reservation is 15 minutes and expires automatically after a crash or a room that never connects.

## Start locally in PowerShell

For the single supervised real call, set `VOICE_MODE=real` and `LLM_MODE=auto` in `.env`. In `auto` mode the worker checks the approved Gemini candidates first and uses the configured Groq key if Gemini has no eligible model or a request fails. This fallback is for the LLM only. If LiveKit or Sarvam voice access fails, the app switches visibly to text mode; it must not retry a metered voice provider. Restore `VOICE_MODE=mock` and `LLM_MODE=mock` after the check.

Terminal 1, from the repository root:

```powershell
Push-Location apps\agent
..\..\.venv\Scripts\python.exe -m voice.worker dev
```

Terminal 2, from the repository root:

```powershell
Push-Location apps\web
npm run dev
```

Open `http://localhost:3000`, sign in with the evaluator account created in Supabase Auth, check the capacity chip, choose **Voice**, and click **Start call**. If the account reports text-only or unavailable, use text mode and do not retry voice.

## Short utterance sequence

Keep the entire call under five minutes. Use these one by one and wait for each answer:

1. “Where is ORD-101?” Confirm Aria reads back the order ID and reports its tracking status from the tool.
2. “I opened it 20 days after delivery. Can I return it?” Confirm Aria refuses politely under the return policy.
3. “Cancel order ZZZ-999.” Confirm Aria does not guess or expose a different order.
4. “Book me a flight to Goa.” Confirm Aria redirects to Aura products, orders, and policies.

End the call once these checks finish. Stop immediately if the timer reaches 4:30, the call exceeds 5 minutes, the dashboard balance is lower than expected, unexpected provider spend is shown, secrets appear in diagnostics, or the browser reports an unrecognized admission/error code.

## Record

Save the developer-panel diagnostics export locally and record: selected voice/text mode, each scenario outcome, p50 and p95 for STT final, LLM first token, TTS first byte and end-to-end latency, total elapsed seconds, LiveKit minutes before/after, Sarvam credits before/after, and any fallback reason. Do not commit transcripts or diagnostic exports unless the owner approves; they may contain user utterances.

## Credit planning estimate

Provider dashboard balances are not available to this local runbook, so exact remaining minutes cannot be claimed yet. The project caps allow at most 120 LiveKit/Sarvam STT minutes and 10,000 Sarvam TTS characters per month. A conservative allocation is:

| Use | Voice minutes | TTS characters |
| --- | ---: | ---: |
| One Phase 3 real-call test | 5 | 2,500 maximum |
| Up to three Phase 5 demo-video takes | 6 total (2 each) | 1,500 total (500 each) |
| Evaluator pool | Up to 15 | Up to 6,000 |
| **Planned total** | **26** | **10,000** |

This leaves a theoretical 94 minutes under the 120-minute application cap, but account-level credits may be lower and the TTS plan consumes the full character cap. Update these estimates from the dashboard before authorizing another real call.

## Attempt — 2026-10-27

The owner confirmed free quota/realtime access and authorized one capped call. With evaluator login, admission returned voice mode and Sarvam realtime STT/Bulbul v3 TTS initialized. The Windows worker exited code 3 without a traceback before a conversational transcript or audible answer. This is a failed real-voice check, not an acceptance pass; latency and exact usage cannot be reported from the incomplete events. The browser ended on its five-minute cap and admission release returned HTTP 204. Temporary prerecorded virtual-microphone testing was removed. Physical microphone/speaker verification remains pending; another metered attempt needs renewed owner authorization.

Before an authorized retry, ensure Windows has adequate available committed memory; a System event reported only about 23 MiB free shortly before the failed call. The cause is not established. The worker now requests uncompressed `linear16` Sarvam audio and disables optional SDK audio recording; both paths pass offline SDK/native-audio checks, but their live provider behavior remains unverified. Do not enable recording, switch providers, reconnect voice or adjust quota caps as a crash workaround. Capture a native abort stack in an approved diagnostic run if the exit recurs; no native crash dump is currently available.
