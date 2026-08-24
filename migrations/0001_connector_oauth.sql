-- Supabase schema for the MCP custom-connector OAuth 2.0 / DCR authorization server.
-- Run in the Supabase SQL editor (or `supabase db execute`). The server talks to
-- this table via PostgREST using the service-role key, so Row Level Security is
-- left enabled with no public policies: only the service role (which bypasses RLS)
-- may read or write it. Codes and tokens are stored as SHA-256 lookup hashes plus
-- Fernet-encrypted copies; no plaintext secrets are persisted.

create table if not exists public.connector_oauth (
    id                  uuid primary key default gen_random_uuid(),
    kind                text not null check (kind in ('client', 'code', 'token')),
    client_id           text,
    code_hash           text,
    token_hash          text,
    refresh_hash        text,
    data                jsonb not null default '{}'::jsonb,
    expires_at          bigint,
    refresh_expires_at  bigint,
    created_at          bigint not null default extract(epoch from now())::bigint
);

create index if not exists connector_oauth_client_id_idx  on public.connector_oauth (client_id) where kind = 'client';
create index if not exists connector_oauth_code_hash_idx   on public.connector_oauth (code_hash)  where kind = 'code';
create index if not exists connector_oauth_token_hash_idx  on public.connector_oauth (token_hash) where kind = 'token';
create index if not exists connector_oauth_refresh_idx     on public.connector_oauth (refresh_hash) where kind = 'token';

alter table public.connector_oauth enable row level security;

-- The server talks to PostgREST with the service-role key, which bypasses RLS but
-- still needs table privileges. Supabase normally grants these automatically, but
-- grant them explicitly so a fresh project (or a locked-down instance) does not
-- return "permission denied for table connector_oauth" on insert/select.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'service_role') then
        grant all privileges on table public.connector_oauth to service_role;
    end if;
end
$$;

-- Ask PostgREST to reload its schema cache so the table is visible immediately
-- instead of returning PGRST205 ("could not find the table ... in the schema
-- cache") until the next automatic reload.
notify pgrst, 'reload schema';

-- Optional hygiene: purge expired codes/tokens. Schedule with pg_cron if desired.
-- delete from public.connector_oauth
--   where (kind = 'code'  and expires_at < extract(epoch from now())::bigint)
--      or (kind = 'token' and coalesce(refresh_expires_at, expires_at) < extract(epoch from now())::bigint);
