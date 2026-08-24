create table if not exists public.ghl_installations (
  install_key text primary key,
  saved_at bigint not null,
  source text not null,
  tenant_id text,
  customer_id text,
  return_to text,
  company_id text not null default '',
  location_id text not null default '',
  user_id text not null default '',
  user_type text not null,
  redirect_uri text not null,
  scope jsonb,
  token_type text,
  access_token_expires_in bigint,
  access_token_fingerprint_sha256 text not null,
  access_token_encrypted text not null,
  refresh_token_encrypted text not null,
  installed boolean not null default true,
  uninstalled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ghl_installations_location_id_idx
  on public.ghl_installations (location_id);

create index if not exists ghl_installations_company_id_idx
  on public.ghl_installations (company_id);

alter table public.ghl_installations enable row level security;

revoke all on public.ghl_installations from anon, authenticated;

