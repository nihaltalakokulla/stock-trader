create extension if not exists pgcrypto;

create table signals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  symbol text not null,
  probability double precision not null,
  features jsonb not null default '{}'::jsonb,
  rationale text not null
);

create table proposals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  symbol text not null,
  qty integer not null check (qty > 0),
  entry_price numeric not null check (entry_price > 0),
  stop_price numeric not null check (stop_price > 0),
  confidence double precision not null,
  rationale text not null,
  expires_at timestamptz not null,
  state text not null default 'PROPOSED'
);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  proposal_id uuid not null references proposals(id),
  decision text not null check (decision in ('YES','NO','STOP')),
  idempotency_key text not null unique,
  source_number text not null
);

create table orders (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  proposal_id uuid not null references proposals(id),
  client_id text not null unique,
  symbol text not null,
  side text not null,
  qty integer not null,
  fill_price numeric,
  status text not null
);

create table positions (
  id uuid primary key default gen_random_uuid(),
  updated_at timestamptz not null default now(),
  proposal_id uuid references proposals(id),
  symbol text not null unique,
  qty integer not null,
  avg_price numeric not null,
  stop_price numeric not null,
  opened_at timestamptz not null
);

create table alerts (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  level text not null,
  message text not null
);

create table settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

alter table signals enable row level security;
alter table proposals enable row level security;
alter table approvals enable row level security;
alter table orders enable row level security;
alter table positions enable row level security;
alter table alerts enable row level security;
alter table settings enable row level security;

create policy "public dashboard reads signals" on signals
  for select to anon using (true);
create policy "public dashboard reads proposals" on proposals
  for select to anon using (true);
create policy "public dashboard reads positions" on positions
  for select to anon using (true);
create policy "public dashboard reads alerts" on alerts
  for select to anon using (true);
create policy "public dashboard reads settings" on settings
  for select to anon using (true);

create view dashboard_signals with (security_invoker = true) as
select created_at, symbol, probability, rationale from signals;

create view dashboard_proposals with (security_invoker = true) as
select created_at, id, symbol, qty, entry_price, stop_price, confidence,
       rationale, expires_at, state
from proposals;

create view dashboard_positions with (security_invoker = true) as
select symbol, qty, avg_price, stop_price, opened_at from positions;

create view dashboard_alerts with (security_invoker = true) as
select created_at, level, message from alerts;

grant select on dashboard_signals to anon;
grant select on dashboard_proposals to anon;
grant select on dashboard_positions to anon;
grant select on dashboard_alerts to anon;
