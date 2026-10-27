-- Phase 3 admission hardening. Apply after 202610250001_phase2_voice_admission.sql.
-- Authenticated callers never receive direct table privileges; only service_role
-- can call these SECURITY DEFINER functions.

alter table public.voice_admissions add column if not exists evaluator_id uuid;

create or replace function public.check_voice_token_rate_limit_bounded(
  p_ip_hash text, p_max_requests integer
) returns boolean
language plpgsql security definer set search_path = public, pg_temp
as $$
begin
  if p_max_requests not between 1 and 5 then return false; end if;
  perform pg_advisory_xact_lock(hashtextextended(p_ip_hash, 1));
  delete from public.voice_token_requests where requested_at < now() - interval '1 day';
  if (select count(*) from public.voice_token_requests
      where ip_hash = p_ip_hash and requested_at > now() - interval '1 minute') >= p_max_requests then
    return false;
  end if;
  insert into public.voice_token_requests(ip_hash) values (p_ip_hash);
  return true;
end;
$$;

create or replace function public.reserve_voice_call_for_evaluator(
  p_call_id uuid, p_evaluator_id uuid, p_tenant_id text, p_ip_hash text,
  p_requested_mode text, p_max_concurrent integer, p_daily_calls_per_ip integer,
  p_max_call_seconds integer, p_monthly_agent_seconds_cap integer,
  p_monthly_stt_seconds_cap integer, p_monthly_tts_characters_cap integer,
  p_reserved_tts_characters integer
) returns jsonb
language plpgsql security definer set search_path = public, pg_temp
as $$
declare
  v_month date := date_trunc('month', now() at time zone 'utc')::date;
  v_agent_used integer; v_stt_used integer; v_tts_used integer;
  v_agent_reserved integer; v_stt_reserved integer; v_tts_reserved integer;
  v_mode text := p_requested_mode; v_fallback_reason text;
begin
  if p_evaluator_id is null or p_tenant_id <> 'aura'
    or p_requested_mode not in ('voice', 'text')
    or p_max_concurrent not between 1 and 4
    or p_daily_calls_per_ip not between 1 and 5
    or p_max_call_seconds not between 1 and 300
    or p_monthly_agent_seconds_cap not between 1 and 7200
    or p_monthly_stt_seconds_cap not between 1 and 7200
    or p_monthly_tts_characters_cap not between 1 and 10000
    or p_reserved_tts_characters not between 1 and 2500 then
    return jsonb_build_object('allowed', false, 'reason', 'INVALID_ADMISSION_LIMITS');
  end if;
  perform pg_advisory_xact_lock(hashtextextended(p_tenant_id, 0));
  update public.voice_admissions set status = 'expired'
    where status = 'reserved' and expires_at <= now();
  if (select count(*) from public.voice_admissions where tenant_id = p_tenant_id
      and status = 'reserved' and expires_at > now()) >= p_max_concurrent then
    return jsonb_build_object('allowed', false, 'reason', 'CONCURRENT_CALL_LIMIT');
  end if;
  if (select count(*) from public.voice_admissions where ip_hash = p_ip_hash
      and created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc'
      and status <> 'released') >= p_daily_calls_per_ip then
    return jsonb_build_object('allowed', false, 'reason', 'DAILY_IP_CALL_LIMIT');
  end if;
  insert into public.voice_usage_counters(tenant_id, usage_month) values (p_tenant_id, v_month)
    on conflict (tenant_id, usage_month) do nothing;
  select agent_seconds, stt_seconds, tts_characters into v_agent_used, v_stt_used, v_tts_used
    from public.voice_usage_counters where tenant_id = p_tenant_id and usage_month = v_month for update;
  select coalesce(sum(reserved_agent_seconds), 0), coalesce(sum(reserved_stt_seconds), 0),
         coalesce(sum(reserved_tts_characters), 0) into v_agent_reserved, v_stt_reserved, v_tts_reserved
    from public.voice_admissions where tenant_id = p_tenant_id and status = 'reserved' and expires_at > now();
  if v_agent_used + v_agent_reserved + p_max_call_seconds > p_monthly_agent_seconds_cap then
    return jsonb_build_object('allowed', false, 'reason', 'MONTHLY_LIVEKIT_MINUTE_CAP');
  end if;
  if v_mode = 'voice' and v_stt_used + v_stt_reserved + p_max_call_seconds > p_monthly_stt_seconds_cap then
    v_mode := 'text'; v_fallback_reason := 'MONTHLY_STT_CAP';
  end if;
  if v_mode = 'voice' and v_tts_used + v_tts_reserved + p_reserved_tts_characters > p_monthly_tts_characters_cap then
    v_mode := 'text'; v_fallback_reason := coalesce(v_fallback_reason, 'MONTHLY_TTS_CAP');
  end if;
  insert into public.voice_admissions(call_id, evaluator_id, tenant_id, ip_hash, mode, status,
      reserved_agent_seconds, reserved_stt_seconds, reserved_tts_characters, expires_at)
    values (p_call_id, p_evaluator_id, p_tenant_id, p_ip_hash, v_mode, 'reserved', p_max_call_seconds,
      case when v_mode = 'voice' then p_max_call_seconds else 0 end,
      case when v_mode = 'voice' then p_reserved_tts_characters else 0 end,
      now() + interval '15 minutes');
  return jsonb_build_object('allowed', true, 'mode', v_mode, 'reason', v_fallback_reason);
end;
$$;

create or replace function public.release_voice_call_for_evaluator(p_call_id uuid, p_evaluator_id uuid)
returns void language sql security definer set search_path = public, pg_temp
as $$
  update public.voice_admissions set status = 'released', completed_at = now()
  where call_id = p_call_id and evaluator_id = p_evaluator_id and status = 'reserved';
$$;

create or replace function public.get_voice_capacity(p_tenant_id text, p_evaluator_id uuid, p_ip_hash text)
returns text language plpgsql security definer set search_path = public, pg_temp
as $$
declare v_month date := date_trunc('month', now() at time zone 'utc')::date; v_used record;
begin
  if p_tenant_id <> 'aura' or p_evaluator_id is null then return 'unavailable'; end if;
  if (select count(*) from public.voice_admissions where tenant_id = p_tenant_id and status = 'reserved' and expires_at > now()) >= 4 then return 'busy'; end if;
  if (select count(*) from public.voice_admissions where ip_hash = p_ip_hash
      and created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc' and status <> 'released') >= 5 then return 'daily_limit_reached'; end if;
  select coalesce(agent_seconds, 0) as agent, coalesce(stt_seconds, 0) as stt, coalesce(tts_characters, 0) as tts
    into v_used from public.voice_usage_counters where tenant_id = p_tenant_id and usage_month = v_month;
  if not found then return 'voice_available'; end if;
  if v_used.agent >= 7200 then return 'unavailable'; end if;
  if v_used.stt >= 7200 or v_used.tts >= 10000 then return 'text_only'; end if;
  return 'voice_available';
end;
$$;

revoke all on function public.reserve_voice_call_for_evaluator(uuid, uuid, text, text, text, integer, integer, integer, integer, integer, integer, integer) from public, anon, authenticated;
revoke all on function public.check_voice_token_rate_limit_bounded(text, integer) from public, anon, authenticated;
revoke all on function public.release_voice_call_for_evaluator(uuid, uuid) from public, anon, authenticated;
revoke all on function public.get_voice_capacity(text, uuid, text) from public, anon, authenticated;
grant execute on function public.reserve_voice_call_for_evaluator(uuid, uuid, text, text, text, integer, integer, integer, integer, integer, integer, integer) to service_role;
grant execute on function public.check_voice_token_rate_limit_bounded(text, integer) to service_role;
grant execute on function public.release_voice_call_for_evaluator(uuid, uuid) to service_role;
grant execute on function public.get_voice_capacity(text, uuid, text) to service_role;
