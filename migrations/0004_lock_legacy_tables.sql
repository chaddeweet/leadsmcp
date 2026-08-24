do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'leadsmcp_ghl_installs',
    'users',
    'lead_batches',
    'leads',
    'chat_messages',
    'billing_records',
    'sessions'
  ]
  loop
    if to_regclass('public.' || table_name) is not null then
      execute format(
        'alter table public.%I enable row level security',
        table_name
      );
      execute format(
        'revoke all on table public.%I from anon, authenticated',
        table_name
      );
    end if;
  end loop;
end
$$;

-- LeadsMCP currently accesses durable data only through the server-side
-- Supabase service role, which bypasses RLS. No anon/authenticated policies are
-- intentionally created here; add narrow policies later only for a reviewed
-- browser-facing feature.
