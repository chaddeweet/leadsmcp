alter table public.ghl_installations
  add column if not exists app_id text,
  add column if not exists plan_id text,
  add column if not exists is_bulk_installation boolean not null default false,
  add column if not exists install_to_future_locations boolean not null default false,
  add column if not exists approve_all_locations boolean not null default false,
  add column if not exists approved_locations jsonb,
  add column if not exists payment_status text not null default 'COMPLETE',
  add column if not exists trial jsonb,
  add column if not exists webhook_id text,
  add column if not exists updated_at timestamptz not null default now();

create table if not exists public.ghl_webhook_events (
  webhook_id text primary key,
  event_type text not null,
  app_id text,
  company_id text,
  location_id text,
  status text not null default 'processed',
  error text,
  payload jsonb not null,
  processed_at timestamptz not null default now()
);

alter table public.ghl_webhook_events enable row level security;
revoke all on public.ghl_webhook_events from anon, authenticated;

create table if not exists public.ghl_wallet_charges (
  event_id text primary key,
  install_key text not null references public.ghl_installations(install_key),
  status text not null default 'pending',
  charge_id text,
  units bigint not null,
  description text not null,
  payload jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.ghl_wallet_charges enable row level security;
revoke all on public.ghl_wallet_charges from anon, authenticated;

create index if not exists ghl_installations_active_location_idx
  on public.ghl_installations (location_id)
  where installed = true;

create index if not exists ghl_installations_active_company_idx
  on public.ghl_installations (company_id)
  where installed = true;
