import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/auth/server";
export const runtime = "nodejs";
export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const next = request.nextUrl.searchParams.get("next");
  const destination = next === "/call" ? "/call" : "/login";
  if (!code) return NextResponse.redirect(new URL("/login?error=link", request.url));
  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) return NextResponse.redirect(new URL("/login?error=link", request.url));
  return NextResponse.redirect(new URL(destination, request.url));
}
