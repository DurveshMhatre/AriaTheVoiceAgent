import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/auth/server";
export const runtime = "nodejs";
export async function POST(request: NextRequest) {
  const requestOrigin = new URL(request.url);
  requestOrigin.host = request.headers.get("host") ?? requestOrigin.host;
  if (request.headers.get("origin") !== requestOrigin.origin) return NextResponse.json({ error: { code: "ORIGIN_NOT_ALLOWED", message: "Invalid request origin." }, fallback_mode: "text" }, { status: 403 });
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Send a JSON call reference." }, fallback_mode: "text" }, { status: 415 });
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || !user.email_confirmed_at) return NextResponse.json({ error: { code: "AUTH_REQUIRED", message: "Please sign in with a confirmed evaluator account." }, fallback_mode: "text" }, { status: 401 });
  let callId: unknown;
  try { callId = (await request.json() as { call_id?: unknown }).call_id; } catch { callId = null; }
  if (typeof callId !== "string" || !/^[0-9a-f-]{36}$/i.test(callId)) return NextResponse.json({ error: { code: "INVALID_REQUEST", message: "Invalid call reference." }, fallback_mode: "text" }, { status: 400 });
  const url = process.env.SUPABASE_URL; const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return NextResponse.json({ error: { code: "VOICE_UNAVAILABLE", message: "Call capacity is unavailable." }, fallback_mode: "text" }, { status: 503 });
  const response = await fetch(`${url}/rest/v1/rpc/release_voice_call_for_evaluator`, { method: "POST", headers: { apikey: key, Authorization: `Bearer ${key}`, "Content-Type": "application/json" }, body: JSON.stringify({ p_call_id: callId, p_evaluator_id: user.id }), cache: "no-store" });
  if (!response.ok) return NextResponse.json({ error: { code: "VOICE_UNAVAILABLE", message: "Call capacity is unavailable." }, fallback_mode: "text" }, { status: 503 });
  return new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}
