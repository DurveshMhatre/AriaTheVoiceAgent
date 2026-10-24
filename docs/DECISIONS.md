
## ADR-020: Lazy provider adapters
**Context:** Provider SDKs change independently and free-tier credentials may be absent in local development.
**Decision:** Keep Gemini and Groq imports lazy, resolve configured candidates at startup, and expose only provider-neutral Brain events. Vendor response metadata remains inside adapters.
**Alternatives:** Import all SDKs at module import time or bind Brain to one SDK.
**Consequences:** Mock mode works without provider packages or keys; real-mode compatibility must be checked against the pinned SDK and official docs.
