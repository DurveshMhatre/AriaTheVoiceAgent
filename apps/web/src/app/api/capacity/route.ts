import { createHmac } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/auth/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || !user.email_confirmed_at) return NextResponse.json({ error: { code: "AUTH_REQUIRED", message: "Please sign in with a confirmed evaluator account." }, fallback_mode: "text" }, { status: 401, headers: { "Cache-Control": "no-store" } });
  const url = process.env.SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const secret = process.env.IP_HASH_SECRET;
  if (!url || !serviceKey || !secret || secret.length < 32) return NextResponse.json({ capacity: "unavailable", checked_at: new Date().toISOString(), cache_seconds: 30 }, { headers: { "Cache-Control": "private, max-age=30" } });
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const ipHash = createHmac("sha256", secret).update(ip).digest("hex");
  try {
    const response = await fetch(`${url}/rest/v1/rpc/get_voice_capacity`, {
      method: "POST", headers: { apikey: serviceKey, Authorization: `Bearer ${serviceKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ p_tenant_id: "aura", p_evaluator_id: user.id, p_ip_hash: ipHash }), cache: "no-store",
    });
    if (!response.ok) throw new Error("capacity query failed");
    const capacity = await response.json() as string;
    const allowed = ["voice_available", "text_only", "busy", "daily_limit_reached", "unavailable"];
    return NextResponse.json({ capacity: allowed.includes(capacity) ? capacity : "unavailable", checked_at: new Date().toISOString(), cache_seconds: 30 }, { headers: { "Cache-Control": "private, max-age=30, s-maxage=0" } });
  } catch {
    return NextResponse.json({ capacity: "unavailable", checked_at: new Date().toISOString(), cache_seconds: 30 }, { headers: { "Cache-Control": "private, max-age=30, s-maxage=0" } });
  }
}
