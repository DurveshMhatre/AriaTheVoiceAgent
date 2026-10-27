import os

from sarvamai import SarvamAI


api_key = os.environ.get("SARVAM_API_KEY")
if not api_key:
    raise SystemExit("SARVAM_API_KEY is not set in the process environment.")

client = SarvamAI(api_subscription_key=api_key)
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[{"role": "user", "content": "Reply with one short greeting."}],
    max_tokens=32,
    reasoning_effort=None,
)

print(response.choices[0].message.content or "")
