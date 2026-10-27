create table if not exists public.voice_usage_counters (
  tenant_id text not null,
  usage_month date not null,
  agent_seconds integer not null default 0 check (agent_seconds >= 0),
  stt_seconds integer not null default 0 check (stt_seconds >= 0),
  tts_characters integer not null default 0 check (tts_characters >= 0),
  primary key (tenant_id, usage_month)
);

create table if not exists public.voice_admissions (
  call_id uuid primary key,
  tenant_id text not null,
  ip_hash text not null,
  mode text not null check (mode in ('voice', 'text')),
  status text not null check (status in ('reserved', 'completed', 'released', 'expired')),
  reserved_agent_seconds integer not null,
  reserved_stt_seconds integer not null,
  reserved_tts_characters integer not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  completed_at timestamptz,
  actual_agent_seconds integer,
  actual_stt_seconds integer,
  actual_tts_characters integer
);

create index if not exists voice_admissions_active_idx
  on public.voice_admissions (tenant_id, status, expires_at);
create index if not exists voice_admissions_ip_day_idx
  on public.voice_admissions (ip_hash, created_at);

create table if not exists public.voice_token_requests (
  request_id bigint generated always as identity primary key,
  ip_hash text not null,
  requested_at timestamptz not null default now()
);
create index if not exists voice_token_requests_ip_time_idx
  on public.voice_token_requests (ip_hash, requested_at desc);

alter table public.voice_usage_counters enable row level security;
alter table public.voice_admissions enable row level security;
alter table public.voice_token_requests enable row level security;
revoke all on public.voice_usage_counters, public.voice_admissions, public.voice_token_requests
  from public, anon, authenticated;

create or replace function public.check_voice_token_rate_limit(p_ip_hash text)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  perform pg_advisory_xact_lock(hashtextextended(p_ip_hash, 1));
  delete from public.voice_token_requests where requested_at < now() - interval '1 day';
  if (select count(*) from public.voice_token_requests
      where ip_hash = p_ip_hash and requested_at > now() - interval '1 minute') >= 5 then
    return false;
  end if;
  insert into public.voice_token_requests(ip_hash) values (p_ip_hash);
  return true;
end;
$$;

create or replace function public.reserve_voice_call(
  p_call_id uuid,
  p_tenant_id text,
  p_ip_hash text,
  p_requested_mode text,
  p_max_concurrent integer,
  p_daily_calls_per_ip integer,
  p_max_call_seconds integer,
  p_monthly_agent_seconds_cap integer,
  p_monthly_stt_seconds_cap integer,
  p_monthly_tts_characters_cap integer,
  p_reserved_tts_characters integer
) returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_month date := date_trunc('month', now() at time zone 'utc')::date;
  v_agent_used integer;
  v_stt_used integer;
  v_tts_used integer;
  v_agent_reserved integer;
  v_stt_reserved integer;
  v_tts_reserved integer;
  v_mode text := p_requested_mode;
  v_fallback_reason text;
begin
  if p_tenant_id <> 'aura'
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
  if (select count(*) from public.voice_admissions
      where tenant_id = p_tenant_id and status = 'reserved' and expires_at > now()) >= p_max_concurrent then
    return jsonb_build_object('allowed', false, 'reason', 'CONCURRENT_CALL_LIMIT');
  end if;
  if (select count(*) from public.voice_admissions
      where ip_hash = p_ip_hash and created_at >= date_trunc('day', now() at time zone 'utc') at time zone 'utc'
        and status <> 'released') >= p_daily_calls_per_ip then
    return jsonb_build_object('allowed', false, 'reason', 'DAILY_IP_CALL_LIMIT');
  end if;

  insert into public.voice_usage_counters(tenant_id, usage_month) values (p_tenant_id, v_month)
    on conflict (tenant_id, usage_month) do nothing;
  select agent_seconds, stt_seconds, tts_characters into v_agent_used, v_stt_used, v_tts_used
    from public.voice_usage_counters where tenant_id = p_tenant_id and usage_month = v_month for update;
  select coalesce(sum(reserved_agent_seconds), 0), coalesce(sum(reserved_stt_seconds), 0),
         coalesce(sum(reserved_tts_characters), 0)
    into v_agent_reserved, v_stt_reserved, v_tts_reserved
    from public.voice_admissions where tenant_id = p_tenant_id and status = 'reserved' and expires_at > now();
  if v_agent_used + v_agent_reserved + p_max_call_seconds > p_monthly_agent_seconds_cap then
    return jsonb_build_object('allowed', false, 'reason', 'MONTHLY_LIVEKIT_MINUTE_CAP');
  end if;
  if v_mode = 'voice'
    and v_stt_used + v_stt_reserved + p_max_call_seconds > p_monthly_stt_seconds_cap then
    v_mode := 'text';
    v_fallback_reason := 'MONTHLY_STT_CAP';
  end if;
  if v_mode = 'voice'
    and v_tts_used + v_tts_reserved + p_reserved_tts_characters > p_monthly_tts_characters_cap then
    v_mode := 'text';
    v_fallback_reason := coalesce(v_fallback_reason, 'MONTHLY_TTS_CAP');
  end if;

  insert into public.voice_admissions(
    call_id, tenant_id, ip_hash, mode, status, reserved_agent_seconds,
    reserved_stt_seconds, reserved_tts_characters, expires_at
  ) values (
    p_call_id, p_tenant_id, p_ip_hash, v_mode, 'reserved', p_max_call_seconds,
    case when v_mode = 'voice' then p_max_call_seconds else 0 end,
    case when v_mode = 'voice' then p_reserved_tts_characters else 0 end,
    now() + interval '15 minutes'
  );
  return jsonb_build_object(
    'allowed', true,
    'mode', v_mode,
    'reason', v_fallback_reason
  );
end;
$$;

create or replace function public.release_voice_call(p_call_id uuid) returns void
language sql
security definer
set search_path = public, pg_temp
as $$
  update public.voice_admissions set status = 'released', completed_at = now()
  where call_id = p_call_id and status = 'reserved';
$$;

create or replace function public.complete_voice_call(
  p_call_id uuid,
  p_agent_seconds integer,
  p_stt_seconds integer,
  p_tts_characters integer
) returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_admission public.voice_admissions%rowtype;
  v_month date;
begin
  select * into v_admission from public.voice_admissions where call_id = p_call_id for update;
  if not found or v_admission.status <> 'reserved' then return; end if;
  v_month := date_trunc('month', v_admission.created_at at time zone 'utc')::date;
  update public.voice_admissions set status = 'completed', completed_at = now(),
    actual_agent_seconds = least(greatest(p_agent_seconds, 0), reserved_agent_seconds),
    actual_stt_seconds = least(greatest(p_stt_seconds, 0), reserved_stt_seconds),
    actual_tts_characters = least(greatest(p_tts_characters, 0), reserved_tts_characters)
    where call_id = p_call_id;
  insert into public.voice_usage_counters(tenant_id, usage_month, agent_seconds, stt_seconds, tts_characters)
  values (
    v_admission.tenant_id, v_month,
    least(greatest(p_agent_seconds, 0), v_admission.reserved_agent_seconds),
    least(greatest(p_stt_seconds, 0), v_admission.reserved_stt_seconds),
    least(greatest(p_tts_characters, 0), v_admission.reserved_tts_characters)
  ) on conflict (tenant_id, usage_month) do update set
    agent_seconds = public.voice_usage_counters.agent_seconds + excluded.agent_seconds,
    stt_seconds = public.voice_usage_counters.stt_seconds + excluded.stt_seconds,
    tts_characters = public.voice_usage_counters.tts_characters + excluded.tts_characters;
end;
$$;

revoke all on function public.check_voice_token_rate_limit(text) from public, anon, authenticated;
revoke all on function public.reserve_voice_call(uuid, text, text, text, integer, integer, integer, integer, integer, integer, integer) from public, anon, authenticated;
revoke all on function public.release_voice_call(uuid) from public, anon, authenticated;
revoke all on function public.complete_voice_call(uuid, integer, integer, integer) from public, anon, authenticated;
grant execute on function public.check_voice_token_rate_limit(text) to service_role;
grant execute on function public.reserve_voice_call(uuid, text, text, text, integer, integer, integer, integer, integer, integer, integer) to service_role;
grant execute on function public.release_voice_call(uuid) to service_role;
grant execute on function public.complete_voice_call(uuid, integer, integer, integer) to service_role;
