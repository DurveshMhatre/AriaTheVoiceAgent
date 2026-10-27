# Supabase Phase 2 and 3 setup runbook

The owner applies SQL manually. Do not run these migrations through an automated client. Use a Supabase project on its free plan; do not enable billing.

## Migration review

Apply these files in order:

1. `supabase/migrations/202610250001_phase2_voice_admission.sql`
2. `supabase/migrations/202610260001_phase3_capacity_release.sql`
3. `supabase/migrations/202610270001_evaluator_daily_voice_exemption.sql`

The first creates the usage counter, admission and token-request tables; enables RLS; revokes direct table access from `PUBLIC`, `anon`, and `authenticated`; and exposes rate-limit, reserve, release, and complete RPCs only to `service_role`. Every `SECURITY DEFINER` function pins `search_path` to `public, pg_temp`. The second adds the evaluator owner to reservations, an owner-bound reserve and release path for the authenticated web app, and a coarse capacity-read RPC. The web token route and release route use these owner-bound functions.

The third migration exempts only the Supabase account whose email is `evaluator@ariaagent.com` from the daily-per-IP call count. It does not remove the shared four-call concurrency cap, monthly LiveKit/Sarvam quotas, five-minute call duration, or per-minute token-start limit. The account must exist in Supabase Auth with this email. This is intended for the single evaluator account; do not change the email match to a client-controlled request field.

Reservations expire after 15 minutes. Calls have a maximum duration of 5 minutes, leaving a 10-minute margin. Normal worker completion writes usage and marks the reservation completed; browser end/abort calls the evaluator-bound release route; a worker crash or a room that never connects is recovered by expiry. Completed or released reservations do not consume concurrency. Daily call counting excludes only released reservations.

## Dashboard steps

1. Sign in to the Supabase dashboard and open the intended Aura demo project.
2. Confirm the project is on the free plan and billing is not enabled.
3. Open **SQL Editor** and choose **New query**.
4. In the repository, open `supabase/migrations/202610250001_phase2_voice_admission.sql`, copy the complete file, paste it into the editor, and click **Run**.
5. Confirm the query finishes successfully. Do not edit the applied file.
6. Open another **New query**, paste the complete contents of `supabase/migrations/202610260001_phase3_capacity_release.sql`, and click **Run**.
7. Open another **New query**, paste the complete contents of `supabase/migrations/202610270001_evaluator_daily_voice_exemption.sql`, and click **Run**.
8. Paste the verification query below into a new editor tab and click **Run**.
9. Confirm every row says `PASS`. The expected output is 3 table rows and 8 function rows, each with `PASS` in the final column. To check that the evaluator account exists, run `select id, email, email_confirmed_at from auth.users where lower(email) = 'evaluator@ariaagent.com';` and verify exactly one row is returned and `email_confirmed_at` is not null. Do not share or commit the returned UUID.

```sql
with expected_tables(name) as (
  values ('voice_usage_counters'), ('voice_admissions'), ('voice_token_requests')
), table_checks as (
  select 'table:' || e.name as object_name,
         case when c.relrowsecurity
                   and not has_table_privilege('anon', c.oid, 'select')
                   and not has_table_privilege('anon', c.oid, 'insert')
                   and not has_table_privilege('authenticated', c.oid, 'select')
                   and not has_table_privilege('authenticated', c.oid, 'insert')
              then 'PASS' else 'FAIL' end as result
  from expected_tables e
  left join pg_class c on c.oid = ('public.' || e.name)::regclass
), expected_functions(signature) as (
  values
    ('check_voice_token_rate_limit(text)'),
    ('check_voice_token_rate_limit_bounded(text,integer)'),
    ('reserve_voice_call(uuid,text,text,text,integer,integer,integer,integer,integer,integer,integer)'),
    ('release_voice_call(uuid)'),
    ('complete_voice_call(uuid,integer,integer,integer)'),
    ('reserve_voice_call_for_evaluator(uuid,uuid,text,text,text,integer,integer,integer,integer,integer,integer,integer)'),
    ('release_voice_call_for_evaluator(uuid,uuid)'),
    ('get_voice_capacity(text,uuid,text)')
), function_checks as (
  select 'function:' || e.signature as object_name,
         case when p.oid is not null and p.prosecdef
                   and has_function_privilege('service_role', p.oid, 'execute')
                   and not has_function_privilege('anon', p.oid, 'execute')
                   and not has_function_privilege('authenticated', p.oid, 'execute')
                   and coalesce(p.proconfig @> array['search_path=public, pg_temp'], false)
              then 'PASS' else 'FAIL' end as result
  from expected_functions e
  left join pg_proc p on p.oid = to_regprocedure('public.' || e.signature)
)
select object_name, result from table_checks
union all
select object_name, result from function_checks
order by object_name;
```

Expected rows: `table:voice_admissions`, `table:voice_token_requests`, `table:voice_usage_counters`, plus the eight `function:*` rows listed in the query. All results must be `PASS`. If a table says `FAIL`, stop; do not test the widget against that project. If the result count is not 11, stop and report the missing object names.

The evaluator account no longer needs the manual daily-release query: its daily per-IP check is skipped by the third migration. Avoid manually marking all of the account's daily admissions as `released`; doing that while a call is active can prevent the worker from finalizing that call's usage correctly. A still-active session may continue to count against shared concurrency until it ends or expires.

## Local readiness

Generate `IP_HASH_SECRET` locally from PowerShell at the repository root. This command writes the random value into `.env` and does not print it:

```powershell
$envPath = Join-Path (Get-Location) '.env'
$secret = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$lines = Get-Content -LiteralPath $envPath
$found = $false
$updated = foreach ($line in $lines) {
    if ($line -match '^IP_HASH_SECRET=') { $found = $true; "IP_HASH_SECRET=$secret" }
    else { $line }
}
if (-not $found) { $updated += "IP_HASH_SECRET=$secret" }
Set-Content -LiteralPath $envPath -Value $updated -Encoding utf8
Remove-Variable secret, lines, updated, found
```

After you apply both migrations and configure the local environment, tell Codex that the SQL verification returned 11 `PASS` rows. Do not paste `.env`, API keys, or the generated secret.
