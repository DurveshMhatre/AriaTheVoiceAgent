import { createHmac, randomUUID } from "node:crypto";
import { RoomAgentDispatch, RoomConfiguration, TrackSource } from "@livekit/protocol";
import { AccessToken } from "livekit-server-sdk";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/auth/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const tenantId = "aura";

function boundedEnv(name: string, fallback: number, maximum: number): number {
  const raw = process.env[name]?.trim();
  const parsed = raw ? Number(raw) : fallback;
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > maximum) {
    throw new Error(`Invalid server configuration: ${name}`);
  }
  return parsed;
}

function requiredEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`Missing server configuration: ${name}`);
  if (name === "IP_HASH_SECRET" && value.length < 32) throw new Error("IP_HASH_SECRET must contain at least 32 characters");
  return value;
}

function jsonError(status: number, code: string, message: string) {
  return NextResponse.json(
    { error: { code, message }, fallback_mode: "text" },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}

async function reserveCall(callId: string, evaluatorId: string, ipHash: string, requestedMode: "voice" | "text") {
  const maxCallSeconds = boundedEnv("MAX_CALL_SECONDS", 300, 300);
  const maxConcurrentCalls = boundedEnv("MAX_CONCURRENT_CALLS", 4, 4);
  const dailyCallsPerIp = boundedEnv("MAX_DAILY_CALLS_PER_IP", 5, 5);
  const maxMonthlyAgentSeconds = boundedEnv("MAX_LIVEKIT_AGENT_SECONDS_MONTH", 7_200, 7_200);
  const maxMonthlySttSeconds = boundedEnv("MAX_SARVAM_STT_SECONDS_MONTH", 7_200, 7_200);
  const maxMonthlyTtsCharacters = boundedEnv(
    "MAX_SARVAM_TTS_CHARACTERS_MONTH",
    10_000,
    10_000,
  );
  const reservedTtsCharacters = boundedEnv("MAX_TTS_CHARACTERS_PER_CALL", 2_500, 2_500);
  const baseUrl = requiredEnv("SUPABASE_URL");
  const serviceKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
  const response = await fetch(`${baseUrl}/rest/v1/rpc/reserve_voice_call_for_evaluator`, {
    method: "POST",
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${serviceKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      p_call_id: callId,
      p_evaluator_id: evaluatorId,
      p_tenant_id: tenantId,
      p_ip_hash: ipHash,
      p_requested_mode: process.env.VOICE_MODE?.trim().toLowerCase() === "real" ? requestedMode : "text",
      p_max_concurrent: maxConcurrentCalls,
      p_daily_calls_per_ip: dailyCallsPerIp,
      p_max_call_seconds: maxCallSeconds,
      p_monthly_agent_seconds_cap: maxMonthlyAgentSeconds,
      p_monthly_stt_seconds_cap: maxMonthlySttSeconds,
      p_monthly_tts_characters_cap: maxMonthlyTtsCharacters,
      p_reserved_tts_characters: reservedTtsCharacters,
    }),
    cache: "no-store",
  });
  if (!response.ok) throw Object.assign(new Error("Admission check failed"), { code: response.status === 404 ? "MIGRATION_NOT_APPLIED" : "VOICE_UNAVAILABLE" });
  return (await response.json()) as {
    allowed: boolean;
    mode?: "voice" | "text";
    reason?: string | null;
  };
}

async function checkTokenRateLimit(ipHash: string): Promise<boolean> {
  const serviceKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
  const response = await fetch(
    `${requiredEnv("SUPABASE_URL")}/rest/v1/rpc/check_voice_token_rate_limit_bounded`,
    {
      method: "POST",
      headers: {
        apikey: serviceKey,
        Authorization: `Bearer ${serviceKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        p_ip_hash: ipHash,
        p_max_requests: boundedEnv("MAX_TOKEN_REQUESTS_PER_IP_PER_MINUTE", 5, 5),
      }),
      cache: "no-store",
    },
  );
  if (!response.ok) throw new Error(`Token rate check failed (${response.status})`);
  return (await response.json()) as boolean;
}

async function releaseReservation(callId: string, evaluatorId: string) {
  const serviceKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
  await fetch(`${requiredEnv("SUPABASE_URL")}/rest/v1/rpc/release_voice_call_for_evaluator`, {
    method: "POST",
    headers: {
      apikey: serviceKey,
      Authorization: `Bearer ${serviceKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ p_call_id: callId, p_evaluator_id: evaluatorId }),
    cache: "no-store",
  });
}

export async function POST(request: NextRequest) {
  try {
    const requestOrigin = new URL(request.url);
    requestOrigin.host = request.headers.get("host") ?? requestOrigin.host;
    if (request.headers.get("origin") !== requestOrigin.origin) {
      return jsonError(403, "ORIGIN_NOT_ALLOWED", "This page cannot start a call from this address.");
    }
    if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
      return jsonError(415, "INVALID_REQUEST", "Send a JSON call request.");
    }
    let requestedMode: "voice" | "text";
    try {
      const body: unknown = await request.json();
      if (!body || typeof body !== "object" || !["voice", "text"].includes(String((body as { mode?: unknown }).mode))) throw new Error("mode");
      requestedMode = (body as { mode: "voice" | "text" }).mode;
    } catch {
      return jsonError(400, "INVALID_REQUEST", "Choose Voice or Text and try again.");
    }
    const rawIp = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
    const ipHash = createHmac("sha256", requiredEnv("IP_HASH_SECRET")).update(rawIp).digest("hex");
    if (!(await checkTokenRateLimit(ipHash))) {
      return jsonError(429, "TOKEN_RATE_LIMIT", "Too many call-start requests. Please wait a minute and try again.");
    }

    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user || !user.email_confirmed_at) {
      return jsonError(401, "AUTH_REQUIRED", "Sign in with a verified evaluator account to start a call.");
    }

    const callId = randomUUID();
    const admission = await reserveCall(callId, user.id, ipHash, requestedMode);
    if (!admission.allowed) {
      return jsonError(429, admission.reason ?? "VOICE_CAP_REACHED", "Voice demo capacity is currently full. Continue in text mode or try again later.");
    }

    try {
      const roomName = `aura-${callId}`;
      const maxCallSeconds = boundedEnv("MAX_CALL_SECONDS", 300, 300);
      const accessToken = new AccessToken(
        requiredEnv("LIVEKIT_API_KEY"),
        requiredEnv("LIVEKIT_API_SECRET"),
        { identity: `evaluator-${user.id}`, ttl: "10m" },
      );
      const realVoiceEnabled = process.env.VOICE_MODE?.trim().toLowerCase() === "real";
      const mode = admission.mode === "text" || !realVoiceEnabled ? "text" : "voice";
      accessToken.addGrant({
        roomJoin: true,
        room: roomName,
        canPublish: mode === "voice",
        ...(mode === "voice" ? { canPublishSources: [TrackSource.MICROPHONE] } : {}),
        canSubscribe: true,
        canPublishData: true,
      });
      accessToken.roomConfig = new RoomConfiguration({
        agents: [
          new RoomAgentDispatch({
            agentName: process.env.LIVEKIT_AGENT_NAME?.trim() || "aria-voice",
            metadata: JSON.stringify({ call_id: callId, tenant_id: tenantId, mode }),
          }),
        ],
      });
      const token = await accessToken.toJwt();
      return NextResponse.json(
        {
          call_id: callId,
          room_name: roomName,
          server_url: requiredEnv("LIVEKIT_URL"),
          participant_token: token,
          expires_in_seconds: 600,
          voice_mode: mode,
          fallback_reason: mode === "text" ? admission.reason ?? null : null,
          max_call_seconds: maxCallSeconds,
        },
        { headers: { "Cache-Control": "no-store" } },
      );
    } catch (error) {
      await releaseReservation(callId, user.id);
      throw error;
    }
  } catch (error) {
    const code = error && typeof error === "object" && "code" in error && typeof error.code === "string" ? error.code : "VOICE_UNAVAILABLE";
    return jsonError(code === "MIGRATION_NOT_APPLIED" ? 503 : 503, code, "Voice is unavailable right now. Continue in text mode and try again later.");
  }
}
