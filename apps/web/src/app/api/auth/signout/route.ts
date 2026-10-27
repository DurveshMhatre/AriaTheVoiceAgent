import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/auth/server";
export const runtime = "nodejs";
export async function POST(request: NextRequest) {
  const requestOrigin = new URL(request.url);
  requestOrigin.host = request.headers.get("host") ?? requestOrigin.host;
  if (request.headers.get("origin") !== requestOrigin.origin) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  const supabase = await createClient();
  await supabase.auth.signOut();
  return NextResponse.json({ ok: true }, { headers: { "Cache-Control": "no-store" } });
}
