# Aria architecture in plain English

Aria is split into a Brain and voice plumbing. The Brain receives text, keeps call state, applies deterministic policy functions, decides when a tool is needed, validates the final answer, and creates the post-call summary. Voice plumbing converts audio to text and text back to audio through LiveKit and provider adapters. This means policy tests and evaluator scenarios can run without using voice credits.

The model is not trusted to decide business policy. For example, the return window and COD limit come from code and tenant configuration. The model only explains the result in a concise voice. If a provider fails or a free quota is exhausted, the system records the event and uses the configured fallback or clearly switches to text mode.

The login identifies the evaluator for access and usage limits. It does not verify the customer named by an order ID. The call state therefore keeps a `verified: false` seam for a future OTP flow.

The web server checks evaluator login and free-tier capacity before issuing a short-lived LiveKit room token. The token only joins that one room, can publish the microphone in voice mode, and can publish text messages in text mode. The browser never receives LiveKit API secrets, the Supabase service-role key, or Sarvam credentials.

If the monthly Sarvam allowance is used up, the admission check can still create a data-only room while LiveKit capacity remains. The same Brain receives the text and applies the same policies and tools. If a live voice provider fails during a call, the worker reports the switch and uses that same Brain in text mode. The interface that lets an evaluator choose and see text mode is being built in Phase 3.
