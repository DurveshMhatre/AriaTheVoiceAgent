# Architecture

## Call flow

`Browser login -> Vercel web app -> short-lived LiveKit token -> WebRTC room -> LiveKit Agent -> STT -> Brain/LLM -> deterministic tools and guardrails -> TTS -> WebRTC audio`

At call end: `transcript + call state -> summary validation/fallback -> one batched Supabase write + one usage-counter update`.

Orders and tenant configuration are loaded from code/YAML behind interfaces. They are not read from the database during the demo.

## Failure modes

| Failure | Safe behavior |
|---|---|
| Provider unavailable | Circuit breaker skips it during cooldown and tries the next configured provider. |
| Voice quota exhausted | Stop starting real voice and visibly switch to text mode. |
| Mumbled audio | Ask for repetition; after three unclear turns offer escalation. |
| Unknown order ID | Ask the customer to repeat or verify; never guess; offer escalation after two failures. |
| Microphone denied | Explain how to enable it and offer text mode. |
| Unknown fact | Say the information is unavailable and offer support follow-up; never invent. |

Production customer verification would use OTP to the registered phone. OTP is not implemented in this assessment.
