# Browser and worker protocol

This document records the Phase 3 contract between the authenticated Next.js app, the LiveKit room, and the Python worker. The browser never receives Supabase service-role credentials or provider keys.

## Start-call API

`POST /api/livekit/token` is a JSON-only, same-origin request. The caller must already have a Supabase Auth session whose email is confirmed. The body is `{ "mode": "voice" | "text" }`. The server HMAC-hashes the caller IP, applies `MAX_TOKEN_REQUESTS_PER_IP_PER_MINUTE` (default 5), reserves capacity through the service-role RPC using `MAX_CONCURRENT_CALLS` (4) and `MAX_DAILY_CALLS_PER_IP` (5), and returns the `contracts/token_response.json` shape. A voice-cap fallback returns `voice_mode: "text"` and a short fallback reason. The room token is valid for 600 seconds and grants only the selected room, data publishing, subscription, and microphone publishing in voice mode.

`POST /api/livekit/release` accepts `{ "call_id": "UUID" }` and releases the matching reservation for the signed-in evaluator. It is safe to call after normal end or client abort. Worker completion records actual usage through `complete_voice_call`. If the browser or worker disappears, the reservation expires after 15 minutes: the 5-minute call cap plus a 10-minute cleanup margin.

`GET /api/capacity` requires a validated Supabase user and returns the coarse `contracts/capacity_response.json` shape. It is cached for at most 30 seconds. The UI refreshes on page load, after a call, and on a debounced manual request; it does not poll.

Errors use `contracts/api_error.json`. The browser maps each code to a friendly message and next action; unknown codes use the safe generic message.

| Code | Message | Next action |
| --- | --- | --- |
| `AUTH_REQUIRED` | Please sign in to start with Aria. | Go to sign in. |
| `TOKEN_RATE_LIMIT` | Too many start requests. Please wait a minute. | Try again in one minute. |
| `CONCURRENT_CALL_LIMIT` | Aria is busy with other callers. | Try again in a minute or use text mode. |
| `DAILY_IP_CALL_LIMIT` | Today’s demo call limit has been reached on this network. | Try again tomorrow. |
| `MONTHLY_LIVEKIT_MINUTE_CAP` | Demo voice minutes are used up for this month. | Choose text mode. |
| `MONTHLY_STT_CAP`, `MONTHLY_TTS_CAP`, `PER_CALL_TTS_LIMIT` | This call used its voice allowance. | Continue in text mode. |
| `INVALID_ADMISSION_LIMITS` | The call service is not configured correctly. | Contact the project owner. |
| `VOICE_CAP_REACHED` | Demo capacity is currently full. | Try text mode or come back later. |
| `VOICE_UNAVAILABLE` | Aria could not start right now. | Try again or continue in text mode. |
| `ORIGIN_NOT_ALLOWED` | This page cannot start a call from this address. | Reload the local app and try again. |
| `INVALID_REQUEST` | The call request was not valid. | Choose Voice or Text and try again. |
| `MIGRATION_NOT_APPLIED` | Call capacity is not configured yet. | Ask the owner to finish setup. |
| `CALL_DURATION_LIMIT` | This demo call reached its five-minute limit. | Start a new call. |
| `AGENT_START_TIMEOUT` | Aria did not wake up in time. | Retry or continue in text mode. |
| `CONNECTION_FAILED` | The call connection was interrupted. | Reconnect or continue in text mode. |
| `MIC_DENIED` | Microphone access was blocked. | Allow microphone access in browser settings or choose text mode. |
| `NO_MICROPHONE` | No microphone was found. | Connect a microphone or choose text mode. |
| `UNSUPPORTED_BROWSER` | This browser cannot start a voice call. | Use current Chrome or Edge, or choose text mode. |
| `TEXT_MODE_TURN_FAILED` | I couldn’t process that message. | Please try again shortly. |
| `SUMMARY_UNAVAILABLE` | The call summary is unavailable. | The transcript remains visible. |
| `SESSION_EXPIRED` | Your sign-in session expired. | Sign in again. |
| `UNKNOWN_ERROR` | Something unexpected happened. | Try again or choose text mode. |

## LiveKit topics

| Topic | Direction | Payload |
| --- | --- | --- |
| `aria.call-event` | worker → browser | One `contracts/call_events.json` object per event. Reliable publish. Sequence is monotonic within a call. |
| `aria.agent-state` | worker → browser | `{ "state": "CONNECTING" | "LISTENING" | "THINKING" | "SPEAKING" | "ENDED", "sequence": number }`. Browser adapts this signal to a `state_changed` event. |
| `aria.client-message` | browser → worker | A `contracts/client_message.json` object: `{ "type": "text_input", "text": "..." }` or `{ "type": "end_call" }`. Reliable publish. |

The worker emits `call_ended` reliably before session teardown. Its data contains the reason, the chronological final transcript, and a deterministic `call_summary.json`-compatible summary. This supports the post-call screen without a database. Phase 4 will persist the same data in a batched call-end write.

## Voice and text modes

Voice mode uses the configured LiveKit Agent, Sarvam `saaras:v3-realtime` STT and Sarvam TTS, then the same Brain, tools and policy checks used in text mode. On provider or quota failure, the client displays the fallback and can continue over `aria.client-message` with the same Brain. Explicit text mode starts without microphone publishing or Sarvam audio. Both modes receive the same structured call events and local post-call summary.

## Contract validation

The JSON Schemas and valid/invalid samples are validated by `scripts/validate_contracts.py`. TypeScript parsing has Ajv-based conformance tests, and Python worker tests validate the final `call_ended` event against the same contract.
